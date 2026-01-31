"""Simplified human-first display for Pacman Token Manager."""

from typing import Any, Dict, List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box


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

    def _get_state(self, usage_percentage: float) -> Tuple[str, str, str]:
        """Determine state based on usage percentage."""
        if usage_percentage < self.GREEN_THRESHOLD:
            return ("green", "🟢", "green")
        elif usage_percentage < self.ORANGE_THRESHOLD:
            return ("orange", "🟠", "yellow")
        else:
            return ("red", "🔴", "red")

    def _get_human_status(self, usage_percentage: float) -> str:
        """Get human-readable status text."""
        if usage_percentage < 30:
            return "Plenty left"
        elif usage_percentage < 50:
            return "Looking good"
        elif usage_percentage < 70:
            return "Using a lot"
        elif usage_percentage < 85:
            return "Running low"
        else:
            return "Almost out"

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

    def _render_bar(
        self,
        percentage: float,
        width: int = 12,
    ) -> str:
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

    def _pad_line(self, content: str, align: str = "left") -> str:
        """Pad content to fixed width with borders."""
        # Strip ANSI codes for length calculation
        import re
        stripped = re.sub(r'\x1b\[[0-9;]*m', '', content)
        padding = self.width - 4 - len(stripped)
        if padding < 0:
            padding = 0
        if align == "left":
            return f"{self.VERTICAL}  {content}{' ' * padding}  {self.VERTICAL}"
        return f"{self.VERTICAL}  {content}{' ' * padding}  {self.VERTICAL}"

    def _get_actions(self, state: str, why_reason: Optional[str]) -> List[str]:
        """Get list of actionable options."""
        actions = []

        if "Opus" in (why_reason or ""):
            actions.append("Switch to a lighter model")
        else:
            actions.append("Use Sonnet instead of Opus")

        actions.append("Run /compact to reduce context")
        actions.append("Clean up long conversations")
        actions.append("Do nothing for now")

        return actions[:4]

    def _get_why_reason(
        self,
        model_distribution: Dict[str, float],
        burn_rate: float,
        output_ratio: float,
    ) -> Optional[str]:
        """Determine the 'why' reason for high usage."""
        opus_pct = model_distribution.get("opus", 0)
        if opus_pct > 50:
            return "Heavy use of Opus (expensive model)"
        if output_ratio > 2.0:
            return "Long responses are being generated"
        if burn_rate > 100:
            return "Fast-paced conversation"
        if burn_rate > 50:
            return "Long prompts are being reused"
        return None

    def _get_alert(
        self,
        usage_pct: float,
        minutes_to_reset: float,
    ) -> Optional[Tuple[str, str]]:
        """Get alert banner if threshold is crossed.

        Returns:
            Tuple of (ANSI color code, alert message) or None
        """
        # Critical: 90%+ usage
        if usage_pct >= 90:
            return ("31;1", "ALMOST OUT! Consider starting a new session")

        # Warning: 75%+ usage
        if usage_pct >= 75:
            return ("33;1", "Running low on tokens")

        # Notice: 50%+ usage
        if usage_pct >= 50:
            return ("33", "Token usage is moderate")

        # Time-based: less than 10 minutes to reset
        if minutes_to_reset <= 10 and usage_pct >= 30:
            return ("36", "Session resets soon - use remaining tokens!")

        return None

    def render(
        self,
        tokens_used: int,
        token_limit: int,
        minutes_to_reset: float,
        model_distribution: Dict[str, float],
        burn_rate: float = 0,
        output_ratio: float = 1.0,
        usage_over_time: Optional[Dict[str, int]] = None,
    ) -> Text:
        """Render the simplified status card.

        Args:
            tokens_used: Current tokens used
            token_limit: Token limit
            minutes_to_reset: Minutes until reset
            model_distribution: Dict of model name -> percentage
            burn_rate: Tokens per minute
            output_ratio: Output tokens / input tokens ratio
            usage_over_time: Dict with 'recent', 'today', 'month' token counts

        Returns:
            Rich Text renderable
        """
        usage_pct = (tokens_used / token_limit * 100) if token_limit > 0 else 0
        state_name, state_emoji, state_style = self._get_state(usage_pct)
        human_status = self._get_human_status(usage_pct)
        why_reason = self._get_why_reason(model_distribution, burn_rate, output_ratio)

        lines = []

        # Top border with title (all yellow)
        lines.append(f"\033[33m{self.TOP_LEFT}{self.HORIZONTAL * (self.width - 2)}{self.TOP_RIGHT}\033[0m")
        lines.append(f"\033[33m{self.VERTICAL}  Pacman Token Manager{' ' * (self.width - 25)}{self.VERTICAL}\033[0m")
        lines.append(f"\033[33m{self._horizontal_line()}\033[0m")

        # Alert banner (only shows at thresholds)
        alert = self._get_alert(usage_pct, minutes_to_reset)
        if alert:
            alert_color, alert_text = alert
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[{alert_color}m⚠️  {alert_text}\033[0m{' ' * (self.width - len(alert_text) - 8)}\033[33m{self.VERTICAL}\033[0m")
            lines.append(f"\033[33m{self._horizontal_line()}\033[0m")

        # Empty line
        lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Token bar with numbers
        bar = self._render_bar(usage_pct, width=20)
        tkn_line = f"TKN      {state_emoji} \033[33m{bar}\033[0m {tokens_used:,} / {token_limit:,}"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {tkn_line}{' ' * (self.width - len(tkn_line) - 4 + 9)}\033[33m{self.VERTICAL}\033[0m")

        # Tokens LEFT (the key info!)
        tokens_left = max(0, token_limit - tokens_used)
        left_str = self._format_tokens(tokens_left)
        left_line = f"\033[32m{left_str} left\033[0m before you have to wait"
        left_stripped = f"{left_str} left before you have to wait"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {left_line}{' ' * (self.width - len(left_stripped) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Empty line
        lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Reset time
        time_str = self._format_time(minutes_to_reset)
        reset_line = f"Resets in \033[36m{time_str}\033[0m \033[90m(rolling 5h window)\033[0m"
        reset_stripped = f"Resets in {time_str} (rolling 5h window)"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  {reset_line}{' ' * (self.width - len(reset_stripped) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Empty line
        lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Why section (model usage)
        lines.append(f"\033[33m{self.LEFT_T}─ Why {self.HORIZONTAL * (self.width - 8)}{self.RIGHT_T}\033[0m")

        # Table header
        header = "Model               Usage           TKN"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{header}\033[0m{' ' * (self.width - len(header) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Model rows
        sorted_models = sorted(model_distribution.items(), key=lambda x: x[1], reverse=True)
        max_pct = max(model_distribution.values()) if model_distribution else 1

        for model_name, pct in sorted_models[:2]:
            display_name = model_name.capitalize()
            bar = self._render_bar((pct / max_pct) * 100, width=12)
            # Estimate tokens from percentage
            model_tokens = int((pct / 100) * tokens_used)
            tkn_str = self._format_tokens(model_tokens)
            row = f"{display_name:<18} {bar} {tkn_str}"
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row}{' ' * (self.width - len(row) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Empty line
        lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Usage over time section
        lines.append(f"\033[33m{self.LEFT_T}─ Usage over time {self.HORIZONTAL * (self.width - 20)}{self.RIGHT_T}\033[0m")

        # Table header
        header = "Period              Usage           TKN"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{header}\033[0m{' ' * (self.width - len(header) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Time period rows
        if usage_over_time:
            time_data = [
                ("Recent session", usage_over_time.get("recent", 0)),
                ("Today", usage_over_time.get("today", 0)),
                ("This month", usage_over_time.get("month", 0)),
            ]
        else:
            time_data = [
                ("Recent session", int(tokens_used * 0.15)),
                ("Today", int(tokens_used * 0.4)),
                ("This month", int(tokens_used * 0.7)),
            ]

        max_tokens = max(t[1] for t in time_data) if time_data else 1

        for label, tkn in time_data:
            bar = self._render_bar((tkn / max_tokens) * 100 if max_tokens > 0 else 0, width=12)
            tkn_str = self._format_tokens(tkn)
            row = f"{label:<18} {bar} {tkn_str}"
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  {row}{' ' * (self.width - len(row) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Empty line
        lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Next step section (only if not green)
        actions = self._get_actions(state_name, why_reason)
        if actions:
            lines.append(f"\033[33m{self.LEFT_T}─ Next step {self.HORIZONTAL * (self.width - 14)}{self.RIGHT_T}\033[0m")

            for i, action in enumerate(actions, 1):
                action_line = f"[{i}] {action}"
                lines.append(f"\033[33m{self.VERTICAL}\033[0m  {action_line}{' ' * (self.width - len(action_line) - 4)}\033[33m{self.VERTICAL}\033[0m")

            # Empty line
            lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

            # Input prompt
            prompt = "Enter a number and press Enter"
            lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{prompt}\033[0m{' ' * (self.width - len(prompt) - 4)}\033[33m{self.VERTICAL}\033[0m")

            # Empty line
            lines.append(f"\033[33m{self.VERTICAL}\033[0m{' ' * (self.width - 2)}\033[33m{self.VERTICAL}\033[0m")

        # Footer
        footer = "Ctrl+C to exit"
        lines.append(f"\033[33m{self.VERTICAL}\033[0m  \033[90m{footer}\033[0m{' ' * (self.width - len(footer) - 4)}\033[33m{self.VERTICAL}\033[0m")

        # Bottom border
        lines.append(f"\033[33m{self.BOTTOM_LEFT}{self.HORIZONTAL * (self.width - 2)}{self.BOTTOM_RIGHT}\033[0m")

        return Text.from_ansi("\n".join(lines))

    def render_to_console(self, **kwargs) -> None:
        """Render directly to console."""
        text = self.render(**kwargs)
        self.console.print(text)


def demo():
    """Demo the simple display."""
    display = SimpleDisplayComponent()

    # Orange state demo
    display.render_to_console(
        tokens_used=45323,
        token_limit=86000,
        minutes_to_reset=134,
        model_distribution={"sonnet": 65, "opus": 35},
        burn_rate=75,
        output_ratio=1.5,
    )


if __name__ == "__main__":
    demo()
