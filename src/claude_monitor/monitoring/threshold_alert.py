"""Threshold-based automatic alerts for token usage."""

import shutil
import sys
from typing import Optional, Set


class ThresholdAlert:
    """Monitors usage and prints alerts when thresholds are crossed."""

    # Thresholds to alert on (percentage)
    THRESHOLDS = [50, 75, 90]

    # Box dimension constraints
    MIN_BOX_WIDTH = 40  # Minimum usable width
    MAX_BOX_WIDTH = 58  # Maximum width (original design)

    def __init__(self):
        self._alerted_thresholds: Set[int] = set()
        self._last_usage_pct: float = 0

    def _get_box_dimensions(self) -> tuple[int, int]:
        """Calculate box dimensions based on terminal width.

        Returns:
            Tuple of (box_width, content_width)
        """
        terminal_width = shutil.get_terminal_size().columns
        # Leave 2 chars margin on each side
        available_width = terminal_width - 4
        box_width = max(self.MIN_BOX_WIDTH, min(available_width, self.MAX_BOX_WIDTH))
        content_width = box_width - 4  # Account for "│  " and "  │"
        return box_width, content_width

    def reset(self) -> None:
        """Reset alerted thresholds (call when usage resets)."""
        self._alerted_thresholds.clear()
        self._last_usage_pct = 0

    def check_and_alert(
        self,
        tokens_used: int,
        token_limit: int,
        plan_name: Optional[str] = None,
        time_left: Optional[str] = None,
    ) -> Optional[int]:
        """Check if a threshold was crossed and print alert.

        Args:
            tokens_used: Current tokens used
            token_limit: Token limit
            plan_name: User's plan name
            time_left: Time remaining until reset (e.g., "2h 15m left")

        Returns:
            Threshold that was crossed, or None
        """
        if token_limit <= 0:
            return None

        usage_pct = (tokens_used / token_limit) * 100

        # Check if usage went down (reset occurred)
        if usage_pct < self._last_usage_pct - 10:
            self.reset()

        self._last_usage_pct = usage_pct

        # Check each threshold
        for threshold in self.THRESHOLDS:
            if usage_pct >= threshold and threshold not in self._alerted_thresholds:
                self._alerted_thresholds.add(threshold)
                self._print_alert(threshold, tokens_used, token_limit, plan_name, time_left)
                return threshold

        return None

    def _truncate(self, text: str, max_width: int) -> str:
        """Truncate text to fit within max_width, adding ellipsis if needed."""
        if len(text) <= max_width:
            return text
        return text[: max_width - 1] + "…"

    def _print_alert(
        self,
        threshold: int,
        tokens_used: int,
        token_limit: int,
        plan_name: Optional[str],
        time_left: Optional[str] = None,
    ) -> None:
        """Print a terminal alert for the threshold."""
        # Get responsive dimensions
        box_width, content_width = self._get_box_dimensions()

        plan_display = plan_name.upper() if plan_name else "PRO"
        tokens_left = token_limit - tokens_used

        # Format tokens with commas
        tokens_left_fmt = f"{tokens_left:,}"
        token_limit_fmt = f"{token_limit:,}"
        tokens_display = f"{tokens_left_fmt} / {token_limit_fmt} tokens left"

        # Build alert message based on threshold
        if threshold >= 90:
            color = "\033[91m"  # Bright red
            message = "ALMOST OUT!"
            suggestion = time_left if time_left else "Resets soon"
        elif threshold >= 75:
            color = "\033[38;5;208m"  # Orange (256-color)
            message = "Running low"
            suggestion = time_left if time_left else "Switch to Sonnet or run /compact"
        else:  # 50%
            color = "\033[93m"  # Bright yellow
            message = "Halfway there"
            suggestion = "Keep an eye on usage"

        reset = "\033[0m"
        dim = "\033[90m"

        # Build content lines with dynamic width (truncate if needed)
        header = self._truncate(f"{message} · {plan_display} · {threshold}% used", content_width)
        tokens_display = self._truncate(tokens_display, content_width)
        suggestion = self._truncate(suggestion, content_width)
        chomp_line = self._truncate("Run `chomp` for details", content_width)

        # Print the alert box (all in status color)
        print(f"\n{color}╭{'─' * box_width}╮")
        print(f"│  {header.ljust(content_width)}  │")
        print(f"│  {dim}{tokens_display.ljust(content_width)}{reset}{color}  │")
        print(f"│  {dim}{suggestion.ljust(content_width)}{reset}{color}  │")
        print(f"│{' ' * box_width}│")
        print(f"│  {dim}{chomp_line.ljust(content_width)}{reset}{color}  │")
        print(f"╰{'─' * box_width}╯{reset}\n")

        # Flush to ensure immediate display
        sys.stdout.flush()


# Global instance for use across the application
_threshold_alert: Optional[ThresholdAlert] = None


def get_threshold_alert() -> ThresholdAlert:
    """Get the global threshold alert instance."""
    global _threshold_alert
    if _threshold_alert is None:
        _threshold_alert = ThresholdAlert()
    return _threshold_alert


def check_threshold(
    tokens_used: int,
    token_limit: int,
    plan_name: Optional[str] = None,
    time_left: Optional[str] = None,
) -> Optional[int]:
    """Convenience function to check thresholds.

    Args:
        tokens_used: Current tokens used
        token_limit: Token limit
        plan_name: User's plan name
        time_left: Time remaining until reset (e.g., "2h 15m left")

    Returns:
        Threshold that was crossed, or None
    """
    return get_threshold_alert().check_and_alert(tokens_used, token_limit, plan_name, time_left)
