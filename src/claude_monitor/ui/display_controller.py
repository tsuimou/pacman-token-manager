"""Main display controller for Claude Monitor.

Orchestrates UI components and coordinates display updates.
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.text import Text

from claude_monitor.core.calculations import calculate_hourly_burn_rate
from claude_monitor.core.models import normalize_model_name
from claude_monitor.core.plans import Plans
from claude_monitor.ui.components import (
    AdvancedCustomLimitDisplay,
    ErrorDisplayComponent,
    LoadingScreenComponent,
)
from claude_monitor.ui.layouts import ScreenManager
from claude_monitor.ui.session_display import SessionDisplayComponent
from claude_monitor.ui.simple_display import SimpleDisplayComponent
from claude_monitor.utils.notifications import NotificationManager
from claude_monitor.utils.time_utils import (
    TimezoneHandler,
    format_display_time,
    get_time_format_preference,
    percentage,
)


class DisplayController:
    """Main controller for coordinating UI display operations."""

    def __init__(self, use_simple_display: bool = True) -> None:
        """Initialize display controller with components.

        Args:
            use_simple_display: Use the new simplified human-first display
        """
        self.use_simple_display = use_simple_display
        self.session_display = SessionDisplayComponent()
        self.simple_display = SimpleDisplayComponent()
        self.loading_screen = LoadingScreenComponent()
        self.error_display = ErrorDisplayComponent()
        self.screen_manager = ScreenManager()
        self.live_manager = LiveDisplayManager()
        self.advanced_custom_display = None
        self.buffer_manager = ScreenBufferManager()
        self.session_calculator = SessionCalculator()
        config_dir = Path.home() / ".claude" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        self.notification_manager = NotificationManager(config_dir)

    def _extract_session_data(self, active_block: Dict[str, Any]) -> Dict[str, Any]:
        """Extract basic session data from active block."""
        return {
            "tokens_used": active_block.get("totalTokens", 0),
            "session_cost": active_block.get("costUSD", 0.0),
            "raw_per_model_stats": active_block.get("perModelStats", {}),
            "sent_messages": active_block.get("sentMessagesCount", 0),
            "entries": active_block.get("entries", []),
            "start_time_str": active_block.get("startTime"),
            "end_time_str": active_block.get("endTime"),
        }

    def _calculate_token_limits(self, args: Any, token_limit: int) -> Tuple[int, int]:
        """Calculate token limits based on plan and arguments."""
        if (
            args.plan == "custom"
            and hasattr(args, "custom_limit_tokens")
            and args.custom_limit_tokens
        ):
            return args.custom_limit_tokens, args.custom_limit_tokens
        return token_limit, token_limit

    def _calculate_time_data(
        self, session_data: Dict[str, Any], current_time: datetime
    ) -> Dict[str, Any]:
        """Calculate time-related data for the session."""
        return self.session_calculator.calculate_time_data(session_data, current_time)

    def _calculate_cost_predictions(
        self,
        session_data: Dict[str, Any],
        time_data: Dict[str, Any],
        args: Any,
        cost_limit_p90: Optional[float],
    ) -> Dict[str, Any]:
        """Calculate cost-related predictions."""
        # Determine cost limit based on plan
        if Plans.is_valid_plan(args.plan) and cost_limit_p90 is not None:
            cost_limit = cost_limit_p90
        else:
            cost_limit = 100.0  # Default

        return self.session_calculator.calculate_cost_predictions(
            session_data, time_data, cost_limit
        )

    def _check_notifications(
        self,
        token_limit: int,
        original_limit: int,
        session_cost: float,
        cost_limit: float,
        predicted_end_time: datetime,
        reset_time: datetime,
    ) -> Dict[str, bool]:
        """Check and update notification states."""
        notifications = {}

        # Switch to custom notification
        switch_condition = token_limit > original_limit
        if switch_condition and self.notification_manager.should_notify(
            "switch_to_custom"
        ):
            self.notification_manager.mark_notified("switch_to_custom")
            notifications["show_switch_notification"] = True
        else:
            notifications["show_switch_notification"] = (
                switch_condition
                and self.notification_manager.is_notification_active("switch_to_custom")
            )

        # Exceed limit notification
        exceed_condition = session_cost > cost_limit
        if exceed_condition and self.notification_manager.should_notify(
            "exceed_max_limit"
        ):
            self.notification_manager.mark_notified("exceed_max_limit")
            notifications["show_exceed_notification"] = True
        else:
            notifications["show_exceed_notification"] = (
                exceed_condition
                and self.notification_manager.is_notification_active("exceed_max_limit")
            )

        # Cost will exceed notification
        run_out_condition = predicted_end_time < reset_time
        if run_out_condition and self.notification_manager.should_notify(
            "cost_will_exceed"
        ):
            self.notification_manager.mark_notified("cost_will_exceed")
            notifications["show_cost_will_exceed"] = True
        else:
            notifications["show_cost_will_exceed"] = (
                run_out_condition
                and self.notification_manager.is_notification_active("cost_will_exceed")
            )

        return notifications

    def _format_display_times(
        self,
        args: Any,
        current_time: datetime,
        predicted_end_time: datetime,
        reset_time: datetime,
    ) -> Dict[str, str]:
        """Format times for display."""
        tz_handler = TimezoneHandler(default_tz="Europe/Warsaw")
        timezone_to_use = (
            args.timezone
            if tz_handler.validate_timezone(args.timezone)
            else "Europe/Warsaw"
        )

        # Convert times to display timezone
        predicted_end_local = tz_handler.convert_to_timezone(
            predicted_end_time, timezone_to_use
        )
        reset_time_local = tz_handler.convert_to_timezone(reset_time, timezone_to_use)

        # Format times
        time_format = get_time_format_preference(args)
        predicted_end_str = format_display_time(
            predicted_end_local, time_format, include_seconds=False
        )
        reset_time_str = format_display_time(
            reset_time_local, time_format, include_seconds=False
        )

        # Current time display
        try:
            display_tz = pytz.timezone(args.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            display_tz = pytz.timezone("Europe/Warsaw")

        current_time_display = current_time.astimezone(display_tz)
        current_time_str = format_display_time(
            current_time_display, time_format, include_seconds=True
        )

        return {
            "predicted_end_str": predicted_end_str,
            "reset_time_str": reset_time_str,
            "current_time_str": current_time_str,
        }

    def create_data_display(
        self, data: Dict[str, Any], args: Any, token_limit: int
    ) -> RenderableType:
        """Create display renderable from data.

        Args:
            data: Usage data dictionary
            args: Command line arguments
            token_limit: Current token limit

        Returns:
            Rich renderable for display
        """
        if not data or "blocks" not in data:
            screen_buffer = self.error_display.format_error_screen(
                args.plan, args.timezone
            )
            return self.buffer_manager.create_screen_renderable(screen_buffer)

        # Find the active block
        active_block = None
        for block in data["blocks"]:
            if isinstance(block, dict) and block.get("isActive", False):
                active_block = block
                break

        # Use UTC timezone for time calculations
        current_time = datetime.now(pytz.UTC)

        if not active_block:
            screen_buffer = self.session_display.format_no_active_session_screen(
                args.plan, args.timezone, token_limit, current_time, args
            )
            return self.buffer_manager.create_screen_renderable(screen_buffer)

        # Use simplified display if enabled
        if self.use_simple_display:
            return self._create_simple_display(active_block, data, args, token_limit, current_time)

        cost_limit_p90 = None
        messages_limit_p90 = None

        if args.plan == "custom":
            temp_display = AdvancedCustomLimitDisplay(None)
            session_data = temp_display._collect_session_data(data["blocks"])
            percentiles = temp_display._calculate_session_percentiles(
                session_data["limit_sessions"]
            )
            cost_limit_p90 = percentiles["costs"]["p90"]
            messages_limit_p90 = percentiles["messages"]["p90"]
        else:
            # Use centralized cost limits
            from claude_monitor.core.plans import get_cost_limit

            cost_limit_p90 = get_cost_limit(args.plan)

            messages_limit_p90 = Plans.get_message_limit(args.plan)

        # Process active session data with cost limit
        try:
            processed_data = self._process_active_session_data(
                active_block, data, args, token_limit, current_time, cost_limit_p90
            )
        except Exception as e:
            # Log the error and show error screen
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing active session data: {e}", exc_info=True)
            screen_buffer = self.error_display.format_error_screen(
                args.plan, args.timezone
            )
            return self.buffer_manager.create_screen_renderable(screen_buffer)

        # Add P90 limits to processed data for display
        if Plans.is_valid_plan(args.plan):
            processed_data["cost_limit_p90"] = cost_limit_p90
            processed_data["messages_limit_p90"] = messages_limit_p90

        try:
            screen_buffer = self.session_display.format_active_session_screen(
                **processed_data
            )
        except Exception as e:
            # Log the error with more details
            logger = logging.getLogger(__name__)
            logger.error(f"Error in format_active_session_screen: {e}", exc_info=True)
            logger.exception(f"processed_data type: {type(processed_data)}")
            if isinstance(processed_data, dict):
                for key, value in processed_data.items():
                    if key == "per_model_stats":
                        logger.exception(f"  {key}: {type(value).__name__}")
                        if isinstance(value, dict):
                            for model, stats in value.items():
                                logger.exception(
                                    f"    {model}: {type(stats).__name__} = {stats}"
                                )
                        else:
                            logger.exception(f"    value = {value}")
                    elif key == "entries":
                        logger.exception(
                            f"  {key}: {type(value).__name__} with {len(value) if isinstance(value, list) else 'N/A'} items"
                        )
                    else:
                        logger.exception(f"  {key}: {type(value).__name__} = {value}")
            screen_buffer = self.error_display.format_error_screen(
                args.plan, args.timezone
            )
            return self.buffer_manager.create_screen_renderable(screen_buffer)

        no_motion = processed_data.get("no_motion", False)
        return self.buffer_manager.create_screen_renderable(screen_buffer, no_motion=no_motion)

    def _create_simple_display(
        self,
        active_block: Dict[str, Any],
        data: Dict[str, Any],
        args: Any,
        token_limit: int,
        current_time: datetime,
    ) -> RenderableType:
        """Create the simplified human-first display.

        Args:
            active_block: Active session block data
            data: Full usage data
            args: Command line arguments
            token_limit: Current token limit
            current_time: Current UTC time

        Returns:
            Rich Panel renderable
        """
        # Extract basic data
        tokens_used = active_block.get("totalTokens", 0)
        per_model_stats = active_block.get("perModelStats", {})

        # Calculate time to reset
        time_data = self.session_calculator.calculate_time_data(
            {
                "start_time_str": active_block.get("startTime"),
                "end_time_str": active_block.get("endTime"),
            },
            current_time,
        )
        minutes_to_reset = time_data.get("minutes_to_reset", 300)

        # Calculate model distribution
        model_distribution = {}
        total_tokens = 0
        for model, stats in per_model_stats.items():
            if isinstance(stats, dict):
                model_tokens = stats.get("input_tokens", 0) + stats.get("output_tokens", 0)
                total_tokens += model_tokens

        if total_tokens > 0:
            for model, stats in per_model_stats.items():
                if isinstance(stats, dict):
                    model_tokens = stats.get("input_tokens", 0) + stats.get("output_tokens", 0)
                    normalized = normalize_model_name(model)
                    # Simplify to just "sonnet" or "opus"
                    if "sonnet" in normalized.lower():
                        key = "sonnet"
                    elif "opus" in normalized.lower():
                        key = "opus"
                    elif "haiku" in normalized.lower():
                        key = "haiku"
                    else:
                        key = normalized
                    model_distribution[key] = model_distribution.get(key, 0) + (model_tokens / total_tokens * 100)

        # Calculate burn rate
        burn_rate = calculate_hourly_burn_rate(data["blocks"], current_time)

        # Calculate output ratio
        total_input = sum(
            stats.get("input_tokens", 0)
            for stats in per_model_stats.values()
            if isinstance(stats, dict)
        )
        total_output = sum(
            stats.get("output_tokens", 0)
            for stats in per_model_stats.values()
            if isinstance(stats, dict)
        )
        output_ratio = total_output / total_input if total_input > 0 else 1.0

        # Render with simple display
        return self.simple_display.render(
            tokens_used=tokens_used,
            token_limit=token_limit,
            minutes_to_reset=minutes_to_reset,
            model_distribution=model_distribution,
            burn_rate=burn_rate,
            output_ratio=output_ratio,
        )

    def _calculate_top_contributors(
        self,
        per_model_stats: Dict[str, Any],
        entries: List[Dict[str, Any]],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Calculate top token contributors from session data.

        Estimates token attribution from available data sources:
        - Models: Which Claude model consumed tokens
        - Messages: Individual API calls (grouped by message_id if available)

        Args:
            per_model_stats: Per-model token statistics
            entries: List of usage entries
            limit: Maximum number of contributors to return

        Returns:
            List of contributor dicts with type, name, tokens, percentage
        """
        contributors: List[Dict[str, Any]] = []
        total_tokens = 0

        # Calculate total tokens from per_model_stats
        for model, stats in per_model_stats.items():
            if isinstance(stats, dict):
                model_tokens = (
                    stats.get("input_tokens", 0)
                    + stats.get("output_tokens", 0)
                    + stats.get("cache_creation_tokens", 0)
                    + stats.get("cache_read_tokens", 0)
                )
                total_tokens += model_tokens

        if total_tokens == 0:
            return []

        # Model-level attribution
        for model, stats in per_model_stats.items():
            if isinstance(stats, dict):
                model_tokens = (
                    stats.get("input_tokens", 0)
                    + stats.get("output_tokens", 0)
                    + stats.get("cache_creation_tokens", 0)
                    + stats.get("cache_read_tokens", 0)
                )
                if model_tokens > 0:
                    normalized = normalize_model_name(model)
                    # Shorten model name for display
                    display_name = normalized.replace("claude-", "").replace("-", " ").title()
                    contributors.append({
                        "type": "model",
                        "name": display_name,
                        "tokens": model_tokens,
                        "percentage": (model_tokens / total_tokens) * 100,
                        "input_tokens": stats.get("input_tokens", 0),
                        "output_tokens": stats.get("output_tokens", 0),
                    })

        # Sort by tokens descending and limit
        contributors.sort(key=lambda x: x["tokens"], reverse=True)
        return contributors[:limit]

    def _process_active_session_data(
        self,
        active_block: Dict[str, Any],
        data: Dict[str, Any],
        args: Any,
        token_limit: int,
        current_time: datetime,
        cost_limit_p90: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Process active session data for display.

        Args:
            active_block: Active session block data
            data: Full usage data
            args: Command line arguments
            token_limit: Current token limit
            current_time: Current UTC time
            cost_limit_p90: Optional cost limit

        Returns:
            Processed data dictionary for display
        """
        # Extract session data
        session_data = self._extract_session_data(active_block)

        # Calculate model distribution
        model_distribution = self._calculate_model_distribution(
            session_data["raw_per_model_stats"]
        )

        # Calculate top token contributors
        top_contributors = self._calculate_top_contributors(
            session_data["raw_per_model_stats"],
            session_data["entries"],
        )

        # Calculate token limits
        token_limit, original_limit = self._calculate_token_limits(args, token_limit)

        # Calculate usage metrics
        tokens_used = session_data["tokens_used"]
        usage_percentage = (
            percentage(tokens_used, token_limit) if token_limit > 0 else 0
        )
        tokens_left = token_limit - tokens_used

        # Calculate time data
        time_data = self._calculate_time_data(session_data, current_time)

        # Calculate burn rate
        burn_rate = calculate_hourly_burn_rate(data["blocks"], current_time)

        # Calculate cost predictions
        cost_data = self._calculate_cost_predictions(
            session_data, time_data, args, cost_limit_p90
        )

        # Check notifications
        notifications = self._check_notifications(
            token_limit,
            original_limit,
            session_data["session_cost"],
            cost_data["cost_limit"],
            cost_data["predicted_end_time"],
            time_data["reset_time"],
        )

        # Format display times
        display_times = self._format_display_times(
            args, current_time, cost_data["predicted_end_time"], time_data["reset_time"]
        )

        # Build result dictionary
        return {
            "plan": args.plan,
            "timezone": args.timezone,
            "tokens_used": tokens_used,
            "token_limit": token_limit,
            "usage_percentage": usage_percentage,
            "tokens_left": tokens_left,
            "elapsed_session_minutes": time_data["elapsed_session_minutes"],
            "total_session_minutes": time_data["total_session_minutes"],
            "burn_rate": burn_rate,
            "session_cost": session_data["session_cost"],
            "per_model_stats": session_data["raw_per_model_stats"],
            "model_distribution": model_distribution,
            "sent_messages": session_data["sent_messages"],
            "entries": session_data["entries"],
            "predicted_end_str": display_times["predicted_end_str"],
            "reset_time_str": display_times["reset_time_str"],
            "current_time_str": display_times["current_time_str"],
            "show_switch_notification": notifications["show_switch_notification"],
            "show_exceed_notification": notifications["show_exceed_notification"],
            "show_tokens_will_run_out": notifications["show_cost_will_exceed"],
            "original_limit": original_limit,
            "top_contributors": top_contributors,
            "auto_compact": getattr(args, "auto_compact", False),
            "no_motion": getattr(args, "no_motion", False),
        }

    def _calculate_model_distribution(
        self, raw_per_model_stats: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate model distribution percentages from current active session only.

        Args:
            raw_per_model_stats: Raw per-model token statistics from the active session block

        Returns:
            Dictionary mapping model names to usage percentages for the current session
        """
        if not raw_per_model_stats:
            return {}

        # Calculate total tokens per model for THIS SESSION ONLY
        model_tokens = {}
        for model, stats in raw_per_model_stats.items():
            if isinstance(stats, dict):
                # Normalize model name
                normalized_model = normalize_model_name(model)
                if normalized_model and normalized_model != "unknown":
                    # Sum all token types for this model in current session
                    total_tokens = stats.get("input_tokens", 0) + stats.get(
                        "output_tokens", 0
                    )
                    if total_tokens > 0:
                        if normalized_model in model_tokens:
                            model_tokens[normalized_model] += total_tokens
                        else:
                            model_tokens[normalized_model] = total_tokens

        # Calculate percentages based on current session total only
        session_total_tokens = sum(model_tokens.values())
        if session_total_tokens == 0:
            return {}

        model_distribution = {}
        for model, tokens in model_tokens.items():
            model_percentage = percentage(tokens, session_total_tokens)
            model_distribution[model] = model_percentage

        return model_distribution

    def create_loading_display(
        self,
        plan: str = "pro",
        timezone: str = "Europe/Warsaw",
        custom_message: Optional[str] = None,
    ) -> RenderableType:
        """Create loading screen display.

        Args:
            plan: Current plan name
            timezone: Display timezone

        Returns:
            Rich renderable for loading screen
        """
        return self.loading_screen.create_loading_screen_renderable(
            plan, timezone, custom_message
        )

    def create_error_display(
        self, plan: str = "pro", timezone: str = "Europe/Warsaw"
    ) -> RenderableType:
        """Create error screen display.

        Args:
            plan: Current plan name
            timezone: Display timezone

        Returns:
            Rich renderable for error screen
        """
        screen_buffer = self.error_display.format_error_screen(plan, timezone)
        return self.buffer_manager.create_screen_renderable(screen_buffer)

    def create_live_context(self) -> Live:
        """Create live display context manager.

        Returns:
            Live display context manager
        """
        return self.live_manager.create_live_display()

    def set_screen_dimensions(self, width: int, height: int) -> None:
        """Set screen dimensions for responsive layouts.

        Args:
            width: Screen width
            height: Screen height
        """
        self.screen_manager.set_screen_dimensions(width, height)


class LiveDisplayManager:
    """Manager for Rich Live display operations."""

    def __init__(self, console: Optional[Console] = None) -> None:
        """Initialize live display manager.

        Args:
            console: Optional Rich console instance
        """
        self._console = console
        self._live_context: Optional[Live] = None
        self._current_renderable: Optional[RenderableType] = None

    def create_live_display(
        self,
        auto_refresh: bool = True,
        console: Optional[Console] = None,
        refresh_per_second: float = 0.75,
    ) -> Live:
        """Create Rich Live display context.

        Args:
            auto_refresh: Whether to auto-refresh
            console: Optional console instance
            refresh_per_second: Display refresh rate (0.1-20 Hz)

        Returns:
            Rich Live context manager
        """
        display_console = console or self._console

        self._live_context = Live(
            console=display_console,
            refresh_per_second=refresh_per_second,
            auto_refresh=auto_refresh,
            vertical_overflow="visible",  # Prevent screen scrolling
        )

        return self._live_context


class PacManBorder:
    """Pac-Man animated border around the dashboard.

    Pac-Man moves along the outer border, eating dots.
    """

    YELLOW = "\033[33m"
    RESET = "\033[0m"

    # Box drawing characters
    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    HORIZONTAL = "─"
    VERTICAL = "│"

    # Pac-Man characters
    PAC_RIGHT = "ᗧ"
    PAC_LEFT = "ᗤ"
    PAC_UP = "ᗢ"
    PAC_DOWN = "ᗣ"
    PAC_CLOSED = "○"

    # Dots
    BIG_DOT = "●"
    SMALL_DOT = "•"

    def __init__(self, width: int = 70, height: int = 30, no_motion: bool = False):
        self._width = width
        self._height = height
        self._no_motion = no_motion
        self._position = 0
        self._mouth_open = True
        self._perimeter = 2 * (width - 2) + 2 * (height - 2)
        try:
            import sys
            self._is_tty = sys.stdout.isatty()
        except Exception:
            self._is_tty = False

    def _get_border_char(self, pos: int) -> tuple:
        """Get position info for a border position.

        Returns: (row, col, direction) where direction is 'right', 'down', 'left', 'up'
        """
        w, h = self._width - 2, self._height - 2

        if pos < w:  # Top edge (left to right)
            return (0, pos + 1, 'right')
        elif pos < w + h:  # Right edge (top to bottom)
            return (pos - w + 1, self._width - 1, 'down')
        elif pos < 2 * w + h:  # Bottom edge (right to left)
            return (self._height - 1, self._width - 2 - (pos - w - h), 'left')
        else:  # Left edge (bottom to top)
            return (self._height - 2 - (pos - 2 * w - h), 0, 'up')

    def advance(self) -> None:
        """Advance animation to next frame."""
        if self._no_motion or not self._is_tty:
            return
        self._position = (self._position + 1) % self._perimeter
        self._mouth_open = not self._mouth_open

    def render_top(self) -> str:
        """Render top border line."""
        if self._no_motion or not self._is_tty:
            return f"{self.YELLOW}{self.TOP_LEFT}{self.HORIZONTAL * (self._width - 2)}{self.TOP_RIGHT}{self.RESET}"

        parts = [f"{self.YELLOW}{self.TOP_LEFT}"]
        w = self._width - 2

        for i in range(w):
            pos = i
            if pos == self._position:
                pac = self.PAC_RIGHT if self._mouth_open else self.PAC_CLOSED
                parts.append(pac)
            elif pos < self._position:
                parts.append(self.SMALL_DOT)
            else:
                parts.append(self.BIG_DOT)

        parts.append(f"{self.TOP_RIGHT}{self.RESET}")
        return "".join(parts)

    def render_middle(self, content: str, row: int) -> str:
        """Render a middle row with left and right borders."""
        w, h = self._width - 2, self._height - 2

        # Left border position
        left_pos = 2 * w + h + (h - row)
        # Right border position
        right_pos = w + row

        if self._no_motion or not self._is_tty:
            left_char = self.VERTICAL
            right_char = self.VERTICAL
        else:
            # Left border
            if left_pos % self._perimeter == self._position:
                left_char = self.PAC_UP if self._mouth_open else self.PAC_CLOSED
            elif left_pos % self._perimeter > self._position or self._position > 2 * w + h:
                left_char = self.BIG_DOT
            else:
                left_char = self.SMALL_DOT

            # Right border
            if right_pos == self._position:
                right_char = self.PAC_DOWN if self._mouth_open else self.PAC_CLOSED
            elif right_pos < self._position:
                right_char = self.SMALL_DOT
            else:
                right_char = self.BIG_DOT

        # Pad content to width
        visible_len = len(content.encode('utf-8').decode('utf-8'))
        # Strip ANSI codes for length calculation
        import re
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', content)
        padding = self._width - 2 - len(stripped)
        if padding > 0:
            content = content + " " * padding

        return f"{self.YELLOW}{left_char}{self.RESET}{content}{self.YELLOW}{right_char}{self.RESET}"

    def render_bottom(self) -> str:
        """Render bottom border line."""
        if self._no_motion or not self._is_tty:
            return f"{self.YELLOW}{self.BOTTOM_LEFT}{self.HORIZONTAL * (self._width - 2)}{self.BOTTOM_RIGHT}{self.RESET}"

        parts = [f"{self.YELLOW}{self.BOTTOM_LEFT}"]
        w, h = self._width - 2, self._height - 2
        bottom_start = w + h

        for i in range(w):
            pos = bottom_start + (w - 1 - i)
            if pos == self._position:
                pac = self.PAC_LEFT if self._mouth_open else self.PAC_CLOSED
                parts.append(pac)
            elif pos < self._position:
                parts.append(self.SMALL_DOT)
            else:
                parts.append(self.BIG_DOT)

        parts.append(f"{self.BOTTOM_RIGHT}{self.RESET}")
        return "".join(parts)


# Shared border instance
_pacman_border: Optional[PacManBorder] = None


def get_pacman_border(no_motion: bool = False) -> PacManBorder:
    """Get or create the shared Pac-Man border instance."""
    global _pacman_border
    if _pacman_border is None:
        _pacman_border = PacManBorder(width=70, height=35, no_motion=no_motion)
    return _pacman_border


class ScreenBufferManager:
    """Manager for screen buffer operations and rendering."""

    def __init__(self) -> None:
        """Initialize screen buffer manager."""
        self.console: Optional[Console] = None

    def create_screen_renderable(
        self, screen_buffer: List[str], no_motion: bool = False
    ) -> Group:
        """Create Rich renderable from screen buffer with Pac-Man border.

        Args:
            screen_buffer: List of screen lines with Rich markup
            no_motion: Whether to disable border animation

        Returns:
            Rich Group renderable
        """
        from claude_monitor.terminal.themes import get_themed_console

        if self.console is None:
            self.console = get_themed_console()

        border = get_pacman_border(no_motion)

        text_objects = []

        # Top border
        text_objects.append(Text(border.render_top()))

        # Content with side borders
        for idx, line in enumerate(screen_buffer):
            if isinstance(line, str):
                # Strip Rich markup for border wrapping, then re-add
                bordered_line = border.render_middle(line, idx + 1)
                text_objects.append(Text(bordered_line))
            else:
                text_objects.append(line)

        # Bottom border
        text_objects.append(Text(border.render_bottom()))

        # Advance animation for next frame
        border.advance()

        return Group(*text_objects)


# Legacy functions for backward compatibility
def create_screen_renderable(screen_buffer: List[str]) -> Group:
    """Legacy function - create screen renderable.

    Maintained for backward compatibility.
    """
    manager = ScreenBufferManager()
    return manager.create_screen_renderable(screen_buffer)


class SessionCalculator:
    """Handles session-related calculations for display purposes.
    (Moved from ui/calculators.py)"""

    def __init__(self) -> None:
        """Initialize session calculator."""
        self.tz_handler = TimezoneHandler()

    def calculate_time_data(
        self, session_data: Dict[str, Any], current_time: datetime
    ) -> Dict[str, Any]:
        """Calculate time-related data for the session.

        Args:
            session_data: Dictionary containing session information
            current_time: Current UTC time

        Returns:
            Dictionary with calculated time data
        """
        # Parse start time
        start_time = None
        if session_data.get("start_time_str"):
            start_time = self.tz_handler.parse_timestamp(session_data["start_time_str"])
            start_time = self.tz_handler.ensure_utc(start_time)

        # Calculate reset time
        if session_data.get("end_time_str"):
            reset_time = self.tz_handler.parse_timestamp(session_data["end_time_str"])
            reset_time = self.tz_handler.ensure_utc(reset_time)
        else:
            reset_time = (
                start_time + timedelta(hours=5)  # Default session duration
                if start_time
                else current_time + timedelta(hours=5)  # Default session duration
            )

        # Calculate session times
        time_to_reset = reset_time - current_time
        minutes_to_reset = time_to_reset.total_seconds() / 60

        if start_time and session_data.get("end_time_str"):
            total_session_minutes = (reset_time - start_time).total_seconds() / 60
            elapsed_session_minutes = (current_time - start_time).total_seconds() / 60
            elapsed_session_minutes = max(0, elapsed_session_minutes)
        else:
            total_session_minutes = 5 * 60  # Default session duration in minutes
            elapsed_session_minutes = max(0, total_session_minutes - minutes_to_reset)

        return {
            "start_time": start_time,
            "reset_time": reset_time,
            "minutes_to_reset": minutes_to_reset,
            "total_session_minutes": total_session_minutes,
            "elapsed_session_minutes": elapsed_session_minutes,
        }

    def calculate_cost_predictions(
        self,
        session_data: Dict[str, Any],
        time_data: Dict[str, Any],
        cost_limit: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate cost-related predictions.

        Args:
            session_data: Dictionary containing session cost information
            time_data: Time data from calculate_time_data
            cost_limit: Optional cost limit (defaults to 100.0)

        Returns:
            Dictionary with cost predictions
        """
        elapsed_minutes = time_data["elapsed_session_minutes"]
        session_cost = session_data.get("session_cost", 0.0)
        current_time = datetime.now(timezone.utc)

        # Calculate cost per minute
        cost_per_minute = (
            session_cost / max(1, elapsed_minutes) if elapsed_minutes > 0 else 0
        )

        # Use provided cost limit or default
        if cost_limit is None:
            cost_limit = 100.0

        cost_remaining = max(0, cost_limit - session_cost)

        # Calculate predicted end time
        if cost_per_minute > 0 and cost_remaining > 0:
            minutes_to_cost_depletion = cost_remaining / cost_per_minute
            predicted_end_time = current_time + timedelta(
                minutes=minutes_to_cost_depletion
            )
        else:
            predicted_end_time = time_data["reset_time"]

        return {
            "cost_per_minute": cost_per_minute,
            "cost_limit": cost_limit,
            "cost_remaining": cost_remaining,
            "predicted_end_time": predicted_end_time,
        }
