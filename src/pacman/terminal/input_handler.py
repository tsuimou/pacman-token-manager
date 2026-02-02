"""Keyboard input handler for interactive guidance actions.

Provides non-blocking keyboard polling for Y/N prompts during live monitoring.
"""

import logging
import select
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional, Set

logger = logging.getLogger(__name__)

# Check for termios availability (Unix-only)
try:
    import termios
    import tty
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False


@dataclass
class ActionState:
    """Tracks current action and dismissed actions for the session."""

    current_action: Optional[str] = None  # e.g., "model sonnet", "compact"
    dismissed_actions: Set[str] = field(default_factory=set)

    def set_action(self, action: Optional[str]) -> None:
        """Set the current pending action."""
        self.current_action = action

    def dismiss_current(self) -> None:
        """Dismiss the current action so it won't show again this session."""
        if self.current_action:
            self.dismissed_actions.add(self.current_action)
            self.current_action = None

    def is_dismissed(self, action: str) -> bool:
        """Check if an action has been dismissed."""
        return action in self.dismissed_actions

    def clear_action(self) -> None:
        """Clear current action without dismissing."""
        self.current_action = None


# Global action state for the session
_action_state = ActionState()


def get_action_state() -> ActionState:
    """Get the global action state."""
    return _action_state


def poll_keyboard(timeout: float = 0.1) -> Optional[str]:
    """Poll for keyboard input without blocking.

    Args:
        timeout: How long to wait for input (seconds)

    Returns:
        The key pressed (lowercase) or None if no input
    """
    if not HAS_TERMIOS or not sys.stdin.isatty():
        return None

    try:
        # Check if input is available
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            char = sys.stdin.read(1)
            return char.lower() if char else None
    except Exception as e:
        logger.debug(f"Keyboard poll error: {e}")

    return None


def execute_action(action: str) -> bool:
    """Execute a guidance action command.

    Args:
        action: Command to execute (e.g., "model sonnet", "compact")

    Returns:
        True if executed successfully, False otherwise
    """
    if not action:
        return False

    try:
        # Build the claude command
        # Actions are like "model sonnet" or "compact"
        cmd = ["claude", f"/{action}"]

        logger.info(f"Executing action: {cmd}")

        # Run in background, don't wait
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to execute action '{action}': {e}")
        return False


def handle_keypress(key: str) -> Optional[str]:
    """Handle a keypress for Y/N action prompts.

    Args:
        key: The key that was pressed

    Returns:
        Message to display, or None
    """
    state = get_action_state()

    if not state.current_action:
        return None

    if key == 'y':
        action = state.current_action
        if execute_action(action):
            state.clear_action()
            return f"Executed: /{action}"
        else:
            return f"Failed to execute: /{action}"

    elif key == 'n':
        action = state.current_action
        state.dismiss_current()
        return f"Dismissed suggestion"

    return None
