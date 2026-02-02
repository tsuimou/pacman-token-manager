"""Simplified human-first display for Pacman Token Manager."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from rich.console import Console
from rich.text import Text

from pacman.ui.guidance import get_primary_guidance, Guidance
from pacman.terminal.input_handler import get_action_state


class SimpleDisplayComponent:
    """Clean, human-first status card display."""

    # State thresholds
    GREEN_THRESHOLD = 50  # Below 50% = green
    ORANGE_THRESHOLD = 80  # Below 80% = orange, above = red

    # Box drawing characters
    TOP_LEFT = "┌"
    TOP_RIGHT = "┐"
    BOTTOM_LEFT = "└"
    BOTTOM_RIGHT = "┘"
    HORIZONTAL = "─"
    VERTICAL = "│"
    LEFT_T = "├"
    RIGHT_T = "┤"

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.width = 64  # Fixed width for consistency

    def _get_state(self, usage_percentage: float) -> Tuple[str, str]:
        """Determine state based on usage percentage."""
        if usage_percentage < self.GREEN_THRESHOLD:
            return ("green", "32")  # Green ANSI
        elif usage_percentage < self.ORANGE_THRESHOLD:
            return ("orange", "33")  # Yellow ANSI
        else:
            return ("red", "31")  # Red ANSI

    def _format_tokens(self, tokens: int) -> str:
        """Format token count to human readable (e.g., 29k)."""
        if tokens >= 1_000_000:
            return f"{tokens / 1_000_000:.1f}m"
        elif tokens >= 1_000:
            return f"{tokens // 1_000}k"
        else:
            return str(tokens)

    def _format_time(self, minutes: float) -> str:
        """Format minutes to Xh Xm format."""
        if minutes < 1:
            return "< 1m"
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"

    def _get_window_start_time(self, minutes_to_reset: float) -> str:
        """Calculate and format when the 5-hour window started."""
        # 5-hour window = 300 minutes
        minutes_elapsed = 300 - minutes_to_reset
        start_time = datetime.now() - timedelta(minutes=minutes_elapsed)
        return start_time.strftime("%I:%M %p").lstrip("0")

    def _render_bar(self, percentage: float, width: int = 12) -> str:
        """Render a progress bar."""
        filled = int((min(percentage, 100) / 100) * width)
        empty = width - filled
        return "█" * filled + "░" * empty

    def _horizontal_line(self, label: str = "") -> str:
        """Create a horizontal divider line with optional label."""
        if label:
            label_part = f"─ {label} "
            remaining = self.width - 2 - len(label_part)
            return f"{self.LEFT_T}{label_part}{self.HORIZONTAL * remaining}{self.RIGHT_T}"
        else:
            return f"{self.LEFT_T}{self.HORIZONTAL * (self.width - 2)}{self.RIGHT_T}"

    def _clean_project_name(self, project_path: str) -> str:
        """Extract clean folder name from project path."""
        # Handle encoded paths like "-Users-hsiaotsui-mou-Desktop-Learn-Code---Token-Manager-CLI"
        if project_path.startswith("-"):
            # Split by dash and get last meaningful part
            parts = project_path.split("-")
            # Filter out empty parts and common path components
            meaningful = [p for p in parts if p and p not in ["Users", "Desktop", "Documents"]]
            if meaningful:
                # Return last 2-3 parts joined
                return "-".join(meaningful[-3:])[:20]
        return project_path[:20]

    def _get_alert(
        self,
        usage_pct: float,
        minutes_to_reset: float,
    ) -> Optional[Tuple[str, str]]:
        """Get alert banner if threshold is crossed.

        Returns:
            Tuple of (ANSI color code, alert message) or None
        """
        time_str = self._format_time(minutes_to_reset)
        window_start = self._get_window_start_time(minutes_to_reset)

        # Critical: 90%+ usage
        if usage_pct >= 90:
            return ("31;1", f"ALMOST OUT! Resets in {time_str} (started {window_start})")

        # Warning: 75%+ usage
        if usage_pct >= 75:
            return ("38;5;208", f"Running low · Resets in {time_str} (started {window_start})")

        # Notice: 50%+ usage
        if usage_pct >= 50:
            return ("33", f"Halfway there · Resets in {time_str} (started {window_start})")

        return None

    def _empty_line(self) -> str:
        """Return an empty line with borders."""
        return f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m"

    def _wrap_text(self, text: str, max_width: int) -> List[str]:
        """Word-wrap text to fit within max_width.

        Args:
            text: Text to wrap
            max_width: Maximum line width

        Returns:
            List of wrapped lines
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + (1 if current_line else 0) <= max_width:
                current_line.append(word)
                current_length += len(word) + (1 if len(current_line) > 1 else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [""]

    def render(
        self,
        tokens_used: int,
        token_limit: int,
        minutes_to_reset: float,
        model_distribution: Dict[str, float],
        project_distribution: Optional[Dict[str, int]] = None,
        usage_over_time: Optional[Dict[str, int]] = None,
        burn_rate: float = 0.0,
        current_model: str = "opus",
    ) -> Text:
        """Render the simplified status card.

        Args:
            tokens_used: Current tokens used
            token_limit: Token limit
            minutes_to_reset: Minutes until reset
            model_distribution: Dict of model name -> percentage
            project_distribution: Dict of project name -> tokens
            usage_over_time: Dict with 'window_5hr' and 'weekly' token counts
            burn_rate: Current token burn rate (tokens/min)
            current_model: Currently active model name

        Returns:
            Rich Text renderable
        """
        usage_pct = (tokens_used / token_limit * 100) if token_limit > 0 else 0
        state_name, state_color = self._get_state(usage_pct)

        lines = []

        # === HEADER ===
        title = "Pacman Token Manager"
        lines.append(f"\033[33m{self.TOP_LEFT}{self.HORIZONTAL * (self.width - 2)}{self.TOP_RIGHT}\033[0m")
        lines.append(f"\033[33m{self.VERTICAL}  {title}{' ' * (self.width - len(title) - 4)}{self.VERTICAL}\033[0m")
        lines.append(f"\033[33m{self._horizontal_line()}\033[0m")

        # === ALERT (conditional) ===
        alert = self._get_alert(usage_pct, minutes_to_reset)
        if alert:
            alert_color, alert_text = alert
            padding = self.width - len(alert_text) - 4
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[{alert_color}m{alert_text}\033[0m{' ' * padding}\033[33m{self.VERTICAL}\033[0m")
            lines.append(f"\033[33m{self._horizontal_line()}\033[0m")

        # === TOKEN STATUS ===
        lines.append(self._empty_line())

        # Token bar with percentage
        bar = self._render_bar(usage_pct, width=20)
        pct_str = f"{usage_pct:.0f}%"
        tkn_line = f"TKN \033[{state_color}m{bar}\033[0m \033[{state_color}m{pct_str:>4}\033[0m  \033[36m{tokens_used:,}\033[0m / {token_limit:,}"
        tkn_line_stripped = f"TKN {bar} {pct_str:>4}  {tokens_used:,} / {token_limit:,}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {tkn_line}{' ' * (self.width - len(tkn_line_stripped) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Tokens left + reset time
        tokens_left = max(0, token_limit - tokens_used)
        left_str = self._format_tokens(tokens_left)
        time_str = self._format_time(minutes_to_reset)
        left_line = f"\033[32m{left_str} left\033[0m · Resets in \033[36m{time_str}\033[0m"
        left_stripped = f"{left_str} left · Resets in {time_str}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {left_line}{' ' * (self.width - len(left_stripped) - 4)}\033[33m{self.VERTICAL}\033[0m")

        lines.append(self._empty_line())

        # === USAGE OVER TIME ===
        lines.append(f"\033[33m{self.LEFT_T}─ Usage over time {self.HORIZONTAL * (self.width - 20)}{self.RIGHT_T}\033[0m")
        lines.append(self._empty_line())

        header = "Period             Usage              TKN"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{header}\033[0m{' ' * (self.width - len(header) - 4)}\033[33m{self.VERTICAL}\033[0m")

        if usage_over_time:
            window_5hr = usage_over_time.get("window_5hr", 0)
            weekly = usage_over_time.get("weekly", 0)
        else:
            window_5hr = tokens_used
            weekly = int(tokens_used * 2)

        # Current session - show percentage of limit (matches Claude /usage)
        bar_session = self._render_bar(usage_pct, width=12)
        tkn_str_session = self._format_tokens(window_5hr)
        pct_session = f"{usage_pct:.0f}%"
        time_str = self._format_time(minutes_to_reset)
        row_session = f"{'Current session':<18} {bar_session} {pct_session:>4} {tkn_str_session:>6}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row_session}{' ' * (self.width - len(row_session) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Reset time for session
        reset_info = f"Resets in {time_str}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{reset_info}\033[0m{' ' * (self.width - len(reset_info) - 4)}\033[33m{self.VERTICAL}\033[0m")

        lines.append(self._empty_line())

        # Current week - show tokens only (we don't have access to weekly limit)
        tkn_str_weekly = self._format_tokens(weekly)
        row_weekly = f"{'Current week':<18}              {tkn_str_weekly:>6}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row_weekly}{' ' * (self.width - len(row_weekly) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Note about weekly
        weekly_note = "(7-day rolling total)"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{weekly_note}\033[0m{' ' * (self.width - len(weekly_note) - 4)}\033[33m{self.VERTICAL}\033[0m")

        lines.append(self._empty_line())

        # === BREAKDOWN ===
        lines.append(f"\033[33m{self.LEFT_T}─ Breakdown {self.HORIZONTAL * (self.width - 14)}{self.RIGHT_T}\033[0m")
        lines.append(self._empty_line())

        # By Model
        header = "By Model           Usage        TKN"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{header}\033[0m{' ' * (self.width - len(header) - 4)}\033[33m{self.VERTICAL}\033[0m")

        sorted_models = sorted(model_distribution.items(), key=lambda x: x[1], reverse=True)
        max_pct = max(model_distribution.values()) if model_distribution else 1

        for model_name, pct in sorted_models[:2]:
            display_name = model_name.capitalize()
            bar = self._render_bar((pct / max_pct) * 100, width=12)
            model_tokens = int((pct / 100) * tokens_used)
            tkn_str = self._format_tokens(model_tokens)
            row = f"{display_name:<18} {bar} {tkn_str}"
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row}{' ' * (self.width - len(row) - 4)}\033[33m{self.VERTICAL}\033[0m")

        lines.append(self._empty_line())

        # By Project
        if project_distribution:
            header = "By Project         Usage        TKN"
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{header}\033[0m{' ' * (self.width - len(header) - 4)}\033[33m{self.VERTICAL}\033[0m")

            sorted_projects = sorted(project_distribution.items(), key=lambda x: x[1], reverse=True)
            max_proj_tokens = max(project_distribution.values()) if project_distribution else 1

            for proj_name, proj_tokens in sorted_projects[:3]:
                clean_name = self._clean_project_name(proj_name)
                bar = self._render_bar((proj_tokens / max_proj_tokens) * 100 if max_proj_tokens > 0 else 0, width=12)
                tkn_str = self._format_tokens(proj_tokens)
                row = f"{clean_name:<18} {bar} {tkn_str}"
                lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row}{' ' * (self.width - len(row) - 4)}\033[33m{self.VERTICAL}\033[0m")

            lines.append(self._empty_line())

        # === GUIDANCE ===
        guidance = get_primary_guidance(
            usage_percentage=usage_pct,
            burn_rate=burn_rate,
            model_distribution=model_distribution,
            minutes_to_reset=minutes_to_reset,
            current_model=current_model,
        )

        lines.append(f"\033[33m{self.LEFT_T}─ Guidance {self.HORIZONTAL * (self.width - 13)}{self.RIGHT_T}\033[0m")
        lines.append(self._empty_line())

        # Word-wrap the guidance text to fit within the box
        content_width = self.width - 6  # Account for borders and padding
        wrapped_lines = self._wrap_text(guidance.primary, content_width)

        for wrapped_line in wrapped_lines:
            padding = self.width - len(wrapped_line) - 4
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  {wrapped_line}{' ' * padding}\033[33m{self.VERTICAL}\033[0m")

        # Add action prompt if available and not dismissed
        action_state = get_action_state()
        show_action = (
            guidance.action_prompt
            and guidance.interactive
            and guidance.action_command
            and not action_state.is_dismissed(guidance.action_command)
        )

        if show_action:
            # Set this as the current action for keyboard handling
            action_state.set_action(guidance.action_command)

            lines.append(self._empty_line())
            # Format: → Switch to Sonnet?  [Y]es  [N]o thanks
            action_line = f"\033[36m→\033[0m {guidance.action_prompt}  \033[32m[Y]\033[0mes  \033[90m[N]\033[0mo thanks"
            action_stripped = f"→ {guidance.action_prompt}  [Y]es  [N]o thanks"
            padding = self.width - len(action_stripped) - 4
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  {action_line}{' ' * padding}\033[33m{self.VERTICAL}\033[0m")
        else:
            # Clear current action if no action to show
            action_state.clear_action()

        lines.append(self._empty_line())

        # === FOOTER ===
        footer = "Ctrl+C to exit"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{footer}\033[0m{' ' * (self.width - len(footer) - 4)}\033[33m{self.VERTICAL}\033[0m")

        lines.append(f"\033[33m{self.BOTTOM_LEFT}{self.HORIZONTAL * (self.width - 2)}{self.BOTTOM_RIGHT}\033[0m")

        return Text.from_ansi("\n".join(lines))

    def render_to_console(self, **kwargs) -> None:
        """Render directly to console."""
        text = self.render(**kwargs)
        self.console.print(text)


def demo():
    """Demo the simple display."""
    display = SimpleDisplayComponent()

    display.render_to_console(
        tokens_used=580000,
        token_limit=1000000,
        minutes_to_reset=225,
        model_distribution={"opus": 75, "sonnet": 25},
        project_distribution={
            "-Users-hsiaotsui-mou-Desktop-Learn-Code---Token-Manager-CLI": 278000,
            "subagents": 302000,
        },
        usage_over_time={"window_5hr": 580000, "weekly": 1250000},
        burn_rate=85.0,
        current_model="opus",
    )


if __name__ == "__main__":
    demo()
