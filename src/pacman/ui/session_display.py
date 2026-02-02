"""Session display components for Claude Monitor.

Handles formatting of active session screens and session data display.
"""

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, List

import pytz

from pacman.ui.components import CostIndicator, VelocityIndicator
from pacman.ui.guidance import get_primary_guidance
from pacman.terminal.input_handler import get_action_state
from pacman.ui.layouts import HeaderManager
from pacman.ui.progress_bars import (
    ModelUsageBar,
    TimeProgressBar,
    TokenProgressBar,
)
from pacman.utils.time_utils import (
    format_display_time,
    get_time_format_preference,
    percentage,
)


@dataclass
class SessionDisplayData:
    """Data container for session display information.

    This replaces the 21 parameters in format_active_session_screen method.
    """

    plan: str
    timezone: str
    tokens_used: int
    token_limit: int
    usage_percentage: float
    tokens_left: int
    elapsed_session_minutes: float
    total_session_minutes: float
    burn_rate: float
    session_cost: float
    per_model_stats: dict[str, Any]
    sent_messages: int
    entries: list[dict]
    predicted_end_str: str
    reset_time_str: str
    current_time_str: str
    show_switch_notification: bool = False
    show_exceed_notification: bool = False
    show_tokens_will_run_out: bool = False
    original_limit: int = 0


class SessionDisplayComponent:
    """Main component for displaying active session information."""

    def __init__(self):
        """Initialize session display component with sub-components."""
        self.token_progress = TokenProgressBar()
        self.time_progress = TimeProgressBar()
        self.model_usage = ModelUsageBar()

    def _compute_context_health(
        self,
        usage_percentage: float,
        burn_rate: float,
        top_contributors: Optional[list[dict[str, Any]]],
        auto_compact: bool,
    ) -> tuple[str, str]:
        """Compute context health status from existing metrics.

        Args:
            usage_percentage: Current token usage percentage
            burn_rate: Current burn rate in tokens/min
            top_contributors: Top token contributors data
            auto_compact: Whether auto-compact is enabled

        Returns:
            Tuple of (emoji, status_text)
        """
        # Critical: usage at/above compact threshold (70%) with auto-compact, or ≥80%
        if usage_percentage >= 80:
            return "🔴", "Critical"
        if auto_compact and usage_percentage >= 70:
            return "🔴", "Critical"

        # Moderate: high burn rate or heavy Opus usage
        if burn_rate > 100:
            return "🟡", "Moderate"

        if top_contributors:
            for contrib in top_contributors:
                name_lower = contrib.get("name", "").lower()
                pct = contrib.get("percentage", 0)
                if "opus" in name_lower and pct > 50:
                    return "🟡", "Moderate"

        return "🟢", "Healthy"

    def _render_wide_progress_bar(self, percentage: float) -> str:
        """Render a wide progress bar (50 chars) using centralized progress bar logic.

        Args:
            percentage: Progress percentage (can be > 100)

        Returns:
            Formatted progress bar string
        """
        from pacman.terminal.themes import get_cost_style

        if percentage < 50:
            color = "🟢"
        elif percentage < 80:
            color = "🟡"
        else:
            color = "🔴"

        progress_bar = TokenProgressBar(width=50)
        bar_style = get_cost_style(percentage)

        capped_percentage = min(percentage, 100.0)
        filled = progress_bar._calculate_filled_segments(capped_percentage, 100.0)

        if percentage >= 100:
            filled_bar = progress_bar._render_bar(50, filled_style=bar_style)
        else:
            filled_bar = progress_bar._render_bar(
                filled, filled_style=bar_style, empty_style="table.border"
            )

        return f"{color} [{filled_bar}]"

    def format_active_session_screen_v2(self, data: SessionDisplayData) -> list[str]:
        """Format complete active session screen using data class.

        This is the refactored version using SessionDisplayData.

        Args:
            data: SessionDisplayData object containing all display information

        Returns:
            List of formatted lines for display
        """
        return self.format_active_session_screen(
            plan=data.plan,
            timezone=data.timezone,
            tokens_used=data.tokens_used,
            token_limit=data.token_limit,
            usage_percentage=data.usage_percentage,
            tokens_left=data.tokens_left,
            elapsed_session_minutes=data.elapsed_session_minutes,
            total_session_minutes=data.total_session_minutes,
            burn_rate=data.burn_rate,
            session_cost=data.session_cost,
            per_model_stats=data.per_model_stats,
            sent_messages=data.sent_messages,
            entries=data.entries,
            predicted_end_str=data.predicted_end_str,
            reset_time_str=data.reset_time_str,
            current_time_str=data.current_time_str,
            show_switch_notification=data.show_switch_notification,
            show_exceed_notification=data.show_exceed_notification,
            show_tokens_will_run_out=data.show_tokens_will_run_out,
            original_limit=data.original_limit,
        )

    def _render_top_contributors_section(
        self, top_contributors: list[dict[str, Any]]
    ) -> list[str]:
        """Render the top token contributors section.

        Args:
            top_contributors: List of contributor dicts with type, name, tokens, percentage

        Returns:
            List of formatted lines for the contributors section
        """
        lines: list[str] = []

        if not top_contributors:
            return lines

        lines.append("")
        lines.append("[bold]📈 Top Token Contributors[/bold] [dim](estimated)[/dim]")

        for i, contrib in enumerate(top_contributors[:5], 1):
            name = contrib.get("name", "Unknown")
            tokens = contrib.get("tokens", 0)
            pct = contrib.get("percentage", 0)
            input_tokens = contrib.get("input_tokens", 0)
            output_tokens = contrib.get("output_tokens", 0)

            # Create a mini bar visualization
            bar_width = 12
            filled = int((pct / 100) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Format tokens compactly (e.g., 45.2K)
            if tokens >= 1_000_000:
                tokens_str = f"{tokens / 1_000_000:.1f}M"
            elif tokens >= 1_000:
                tokens_str = f"{tokens / 1_000:.1f}K"
            else:
                tokens_str = str(tokens)

            # Show input/output breakdown
            if input_tokens >= 1_000:
                in_str = f"{input_tokens / 1_000:.0f}K"
            else:
                in_str = str(input_tokens)
            if output_tokens >= 1_000:
                out_str = f"{output_tokens / 1_000:.0f}K"
            else:
                out_str = str(output_tokens)

            lines.append(
                f"   {i}. [value]{name:<18}[/] [dim]{bar}[/] [info]{tokens_str:>6}[/] ({pct:4.1f}%) [dim]in:{in_str} out:{out_str}[/]"
            )

        lines.append("[dim]   Token Manager: optimization engine (coming soon)[/dim]")

        return lines

    def _render_guidance_section(
        self,
        usage_percentage: float,
        burn_rate: float,
        top_contributors: Optional[list[dict[str, Any]]],
        minutes_to_reset: float = 0.0,
        current_model: str = "opus",
    ) -> list[str]:
        """Render the guidance section with a single recommendation.

        Args:
            usage_percentage: Current token usage percentage
            burn_rate: Current burn rate
            top_contributors: Top token contributors data
            minutes_to_reset: Minutes until token reset
            current_model: Currently active model name

        Returns:
            List of formatted lines for the guidance section
        """
        # Extract model distribution from top contributors
        model_distribution: dict[str, float] = {}
        if top_contributors:
            for contrib in top_contributors:
                name_lower = contrib.get("name", "").lower()
                pct = contrib.get("percentage", 0)
                if "opus" in name_lower:
                    model_distribution["opus"] = model_distribution.get("opus", 0) + pct
                elif "sonnet" in name_lower:
                    model_distribution["sonnet"] = model_distribution.get("sonnet", 0) + pct
                elif "haiku" in name_lower:
                    model_distribution["haiku"] = model_distribution.get("haiku", 0) + pct

        guidance = get_primary_guidance(
            usage_percentage=usage_percentage,
            burn_rate=burn_rate,
            model_distribution=model_distribution,
            minutes_to_reset=minutes_to_reset,
            current_model=current_model,
        )

        lines: list[str] = []
        lines.append("")
        lines.append(f"[bold]💡 {guidance.primary}[/bold]")

        if guidance.context:
            lines.append(f"   [dim]{guidance.context}[/dim]")

        # Add action prompt if available
        if guidance.action_prompt and guidance.interactive:
            lines.append(f"   [info]→ {guidance.action_prompt}[/]  [success][Y][/]es  [dim][N][/]o thanks")

        return lines

    def format_active_session_screen(
        self,
        plan: str,
        timezone: str,
        tokens_used: int,
        token_limit: int,
        usage_percentage: float,
        tokens_left: int,
        elapsed_session_minutes: float,
        total_session_minutes: float,
        burn_rate: float,
        session_cost: float,
        per_model_stats: dict[str, Any],
        sent_messages: int,
        entries: list[dict],
        predicted_end_str: str,
        reset_time_str: str,
        current_time_str: str,
        show_switch_notification: bool = False,
        show_exceed_notification: bool = False,
        show_tokens_will_run_out: bool = False,
        original_limit: int = 0,
        top_contributors: Optional[list[dict[str, Any]]] = None,
        auto_compact: bool = False,
        no_motion: bool = False,
        **kwargs,
    ) -> list[str]:
        """Format complete active session screen.

        Args:
            plan: Current plan name
            timezone: Display timezone
            tokens_used: Number of tokens used
            token_limit: Token limit for the plan
            usage_percentage: Usage percentage
            tokens_left: Remaining tokens
            elapsed_session_minutes: Minutes elapsed in session
            total_session_minutes: Total session duration
            burn_rate: Current burn rate
            session_cost: Session cost in USD
            per_model_stats: Model usage statistics
            sent_messages: Number of messages sent
            entries: Session entries
            predicted_end_str: Predicted end time string
            reset_time_str: Reset time string
            current_time_str: Current time string
            show_switch_notification: Show plan switch notification
            show_exceed_notification: Show exceed limit notification
            show_tokens_will_run_out: Show token depletion warning
            original_limit: Original plan limit

        Returns:
            List of formatted screen lines
        """

        screen_buffer = []

        header_manager = HeaderManager()
        screen_buffer.extend(header_manager.create_header(plan, timezone))

        # Add context health line
        health_emoji, health_status = self._compute_context_health(
            usage_percentage, burn_rate, top_contributors, auto_compact
        )
        if health_status == "Critical":
            health_style = "error"
        elif health_status == "Moderate":
            health_style = "warning"
        else:
            health_style = "success"
        screen_buffer.append(f"{health_emoji} [value]Context health:[/] [{health_style}]{health_status}[/]")

        if plan in ["custom", "pro", "max5", "max20"]:
            from pacman.core.plans import DEFAULT_COST_LIMIT

            cost_limit_p90 = kwargs.get("cost_limit_p90", DEFAULT_COST_LIMIT)
            messages_limit_p90 = kwargs.get("messages_limit_p90", 1500)

            screen_buffer.append("")
            if plan == "custom":
                screen_buffer.append("[bold]📊 Session-Based Dynamic Limits[/bold]")
                screen_buffer.append(
                    "[dim]Based on your historical usage patterns when hitting limits (P90)[/dim]"
                )
                screen_buffer.append(f"[separator]{'─' * 60}[/]")
            else:
                screen_buffer.append("")

            cost_percentage = (
                min(100, percentage(session_cost, cost_limit_p90))
                if cost_limit_p90 > 0
                else 0
            )
            cost_bar = self._render_wide_progress_bar(cost_percentage)
            screen_buffer.append(
                f"💰 [value]Cost Usage:[/]           {cost_bar} {cost_percentage:4.1f}%    [value]${session_cost:.2f}[/] / [dim]${cost_limit_p90:.2f}[/]"
            )
            screen_buffer.append("")

            token_bar = self._render_wide_progress_bar(usage_percentage)
            screen_buffer.append(
                f"📊 [value]Token Usage:[/]          {token_bar} {usage_percentage:4.1f}%    [value]{tokens_used:,}[/] / [dim]{token_limit:,}[/]"
            )
            screen_buffer.append("")

            messages_percentage = (
                min(100, percentage(sent_messages, messages_limit_p90))
                if messages_limit_p90 > 0
                else 0
            )
            messages_bar = self._render_wide_progress_bar(messages_percentage)
            screen_buffer.append(
                f"📨 [value]Messages Usage:[/]       {messages_bar} {messages_percentage:4.1f}%    [value]{sent_messages}[/] / [dim]{messages_limit_p90:,}[/]"
            )
            screen_buffer.append(f"[separator]{'─' * 60}[/]")

            time_percentage = (
                percentage(elapsed_session_minutes, total_session_minutes)
                if total_session_minutes > 0
                else 0
            )
            time_bar = self._render_wide_progress_bar(time_percentage)
            time_remaining = max(0, total_session_minutes - elapsed_session_minutes)
            time_left_hours = int(time_remaining // 60)
            time_left_mins = int(time_remaining % 60)
            screen_buffer.append(
                f"⏱️  [value]Time to Reset:[/]       {time_bar} {time_left_hours}h {time_left_mins}m"
            )
            screen_buffer.append("")

            if per_model_stats:
                model_bar = self.model_usage.render(per_model_stats)
                screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
            else:
                model_bar = self.model_usage.render({})
                screen_buffer.append(f"🤖 [value]Model Distribution:[/]   {model_bar}")
            screen_buffer.append(f"[separator]{'─' * 60}[/]")

            velocity_emoji = VelocityIndicator.get_velocity_emoji(burn_rate)
            screen_buffer.append(
                f"[dim]🔥 Burn Rate:              {burn_rate:.1f} tokens/min {velocity_emoji}[/dim]"
            )

            cost_per_min = (
                session_cost / max(1, elapsed_session_minutes)
                if elapsed_session_minutes > 0
                else 0
            )
            screen_buffer.append(
                f"[dim]💲 Cost Rate:              ${cost_per_min:.4f} $/min[/dim]"
            )
        else:
            cost_display = CostIndicator.render(session_cost)
            cost_per_min = (
                session_cost / max(1, elapsed_session_minutes)
                if elapsed_session_minutes > 0
                else 0
            )
            screen_buffer.append(f"💲 [value]Session Cost:[/]   {cost_display}")
            screen_buffer.append(
                f"[dim]💲 Cost Rate:      ${cost_per_min:.4f} $/min[/dim]"
            )
            screen_buffer.append("")

            token_bar = self.token_progress.render(usage_percentage)
            screen_buffer.append(f"📊 [value]Token Usage:[/]    {token_bar}")
            screen_buffer.append("")

            screen_buffer.append(
                f"🎯 [value]Tokens:[/]         [value]{tokens_used:,}[/] / [dim]~{token_limit:,}[/] ([info]{tokens_left:,} left[/])"
            )

            velocity_emoji = VelocityIndicator.get_velocity_emoji(burn_rate)
            screen_buffer.append(
                f"[dim]🔥 Burn Rate:      {burn_rate:.1f} tokens/min {velocity_emoji}[/dim]"
            )

            screen_buffer.append(
                f"📨 [value]Sent Messages:[/]  [info]{sent_messages}[/] [dim]messages[/]"
            )

            if per_model_stats:
                model_bar = self.model_usage.render(per_model_stats)
                screen_buffer.append(f"🤖 [value]Model Usage:[/]    {model_bar}")

            screen_buffer.append("")

            time_bar = self.time_progress.render(
                elapsed_session_minutes, total_session_minutes
            )
            screen_buffer.append(f"⏱️  [value]Time to Reset:[/]  {time_bar}")
            screen_buffer.append("")

        # Add top contributors section
        if top_contributors:
            screen_buffer.extend(self._render_top_contributors_section(top_contributors))

        # Add guidance section
        minutes_to_reset = max(0, total_session_minutes - elapsed_session_minutes)
        # Determine current model from per_model_stats
        current_model = "opus"  # default
        if per_model_stats:
            # Find the model with highest usage
            max_usage = 0
            for model_name, stats in per_model_stats.items():
                usage = stats.get("percentage", 0) if isinstance(stats, dict) else 0
                if usage > max_usage:
                    max_usage = usage
                    current_model = model_name
        screen_buffer.extend(
            self._render_guidance_section(
                usage_percentage,
                burn_rate,
                top_contributors,
                minutes_to_reset=minutes_to_reset,
                current_model=current_model,
            )
        )

        # Add auto actions status
        auto_status = "[success]ON[/]" if auto_compact else "[dim]OFF[/]"
        screen_buffer.append("")
        screen_buffer.append(f"⚡ [value]Auto actions:[/] {auto_status}")

        screen_buffer.append("")
        screen_buffer.append("[dim]🔮 Predictions:[/dim]")
        screen_buffer.append(
            f"[dim]   Tokens will run out: {predicted_end_str}[/dim]"
        )
        screen_buffer.append(
            f"[dim]   Limit resets at:     {reset_time_str}[/dim]"
        )
        screen_buffer.append("")

        self._add_notifications(
            screen_buffer,
            show_switch_notification,
            show_exceed_notification,
            show_tokens_will_run_out,
            original_limit,
            token_limit,
        )

        screen_buffer.append(
            f"⏰ [dim]{current_time_str}[/] 📝 [success]Active session[/] | [dim]Ctrl+C to exit[/] 🟢"
        )

        return screen_buffer

    def _add_notifications(
        self,
        screen_buffer: list[str],
        show_switch_notification: bool,
        show_exceed_notification: bool,
        show_tokens_will_run_out: bool,
        original_limit: int,
        token_limit: int,
    ) -> None:
        """Add notification messages to screen buffer.

        Args:
            screen_buffer: Screen buffer to append to
            show_switch_notification: Show plan switch notification
            show_exceed_notification: Show exceed limit notification
            show_tokens_will_run_out: Show token depletion warning
            original_limit: Original plan limit
            token_limit: Current token limit
        """
        notifications_added = False

        if show_switch_notification and token_limit > original_limit:
            screen_buffer.append(
                f"🔄 [warning]Token limit exceeded ({token_limit:,} tokens)[/]"
            )
            notifications_added = True

        if show_exceed_notification:
            screen_buffer.append(
                "⚠️  [error]You have exceeded the maximum cost limit![/]"
            )
            notifications_added = True

        if show_tokens_will_run_out:
            screen_buffer.append(
                "⏰ [warning]Cost limit will be exceeded before reset![/]"
            )
            notifications_added = True

        if notifications_added:
            screen_buffer.append("")

    def format_no_active_session_screen(
        self,
        plan: str,
        timezone: str,
        token_limit: int,
        current_time: Optional[datetime] = None,
        args: Optional[Any] = None,
    ) -> list[str]:
        """Format screen for no active session state.

        Args:
            plan: Current plan name
            timezone: Display timezone
            token_limit: Token limit for the plan
            current_time: Current datetime
            args: Command line arguments

        Returns:
            List of formatted screen lines
        """

        screen_buffer = []

        header_manager = HeaderManager()
        screen_buffer.extend(header_manager.create_header(plan, timezone))

        empty_token_bar = self.token_progress.render(0.0)
        screen_buffer.append(f"📊 [value]Token Usage:[/]    {empty_token_bar}")
        screen_buffer.append("")

        screen_buffer.append(
            f"🎯 [value]Tokens:[/]         [value]0[/] / [dim]~{token_limit:,}[/] ([info]0 left[/])"
        )
        screen_buffer.append(
            "🔥 [value]Burn Rate:[/]      [warning]0.0[/] [dim]tokens/min[/]"
        )
        screen_buffer.append(
            "💲 [value]Cost Rate:[/]      [cost.low]$0.00[/] [dim]$/min[/]"
        )
        screen_buffer.append("📨 [value]Sent Messages:[/]  [info]0[/] [dim]messages[/]")
        screen_buffer.append("")

        if current_time and args:
            try:
                display_tz = pytz.timezone(args.timezone)
                current_time_display = current_time.astimezone(display_tz)
                current_time_str = format_display_time(
                    current_time_display,
                    get_time_format_preference(args),
                    include_seconds=True,
                )
                screen_buffer.append(
                    f"⏰ [dim]{current_time_str}[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
                )
            except (pytz.exceptions.UnknownTimeZoneError, AttributeError):
                screen_buffer.append(
                    "⏰ [dim]--:--:--[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
                )
        else:
            screen_buffer.append(
                "⏰ [dim]--:--:--[/] 📝 [info]No active session[/] | [dim]Ctrl+C to exit[/] 🟨"
            )

        return screen_buffer
