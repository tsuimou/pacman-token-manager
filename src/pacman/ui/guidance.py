"""Shared guidance engine for Pacman Token Manager.

Transforms "next steps" from a decision-making control panel into
contextual guidance that resolves uncertainty.

Core principle: Resolve uncertainty, not create decisions.
Feel like guidance, not a control panel.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, List, Optional

from pacman.terminal.input_handler import get_action_state


class TaskType(Enum):
    """Classification of user task type."""
    CODING = auto()     # Complex tasks requiring Opus
    PLANNING = auto()   # Simple tasks suitable for Sonnet/Haiku
    UNKNOWN = auto()    # Cannot determine


@dataclass
class Guidance:
    """Single recommendation for the user.

    Attributes:
        primary: Main recommendation text
        context: Why this matters (optional)
        urgency: "calm", "normal", or "urgent"
        interactive: Whether this requires Y/N input
        suggested_model: Model to switch to (if applicable)
        action_prompt: Text for the action line (e.g., "Switch to Sonnet?")
        action_command: Command to execute on Y (e.g., "model sonnet")
    """
    primary: str
    context: Optional[str] = None
    urgency: str = "normal"
    interactive: bool = False
    suggested_model: Optional[str] = None
    action_prompt: Optional[str] = None
    action_command: Optional[str] = None


# Keywords indicating coding/complex tasks
CODING_KEYWORDS = [
    "implement", "fix", "debug", "refactor", "write code", "create function",
    "add feature", "bug", "error", "failing", "broken", "test", "optimize",
    "class", "method", "function", "variable", "import", "export",
    "compile", "build", "deploy", "migrate", "database", "api",
]

# Keywords indicating planning/simple tasks
PLANNING_KEYWORDS = [
    "how do i", "what is", "explain", "help me understand", "should i",
    "can you", "tell me", "describe", "summarize", "overview", "plan",
    "strategy", "approach", "best practice", "recommend", "suggest",
    "compare", "difference between", "pros and cons", "when to use",
]


def detect_task_type(recent_messages: Optional[List[str]] = None) -> TaskType:
    """Analyze recent messages to classify task type.

    Args:
        recent_messages: List of recent message contents

    Returns:
        TaskType classification
    """
    if not recent_messages:
        return TaskType.UNKNOWN

    # Combine recent messages into one text block for analysis
    combined = " ".join(recent_messages).lower()

    # Count keyword matches
    coding_score = sum(1 for kw in CODING_KEYWORDS if kw in combined)
    planning_score = sum(1 for kw in PLANNING_KEYWORDS if kw in combined)

    # Check for code indicators (file paths, code blocks)
    if ".py" in combined or ".js" in combined or ".ts" in combined:
        coding_score += 2
    if "```" in combined:
        coding_score += 2
    if "/" in combined and ("src/" in combined or "lib/" in combined):
        coding_score += 1

    # Determine task type based on scores
    if coding_score > planning_score + 1:
        return TaskType.CODING
    elif planning_score > coding_score + 1:
        return TaskType.PLANNING

    return TaskType.UNKNOWN


def _format_time(minutes: float) -> str:
    """Format minutes to human-readable time string.

    Args:
        minutes: Number of minutes

    Returns:
        Formatted string like "2h 30m" or "45m"
    """
    if minutes < 1:
        return "< 1m"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def get_primary_guidance(
    usage_percentage: float,
    burn_rate: float,
    model_distribution: Dict[str, float],
    minutes_to_reset: float,
    current_model: str = "opus",
    recent_messages: Optional[List[str]] = None,
    top_contributors: Optional[List[Dict[str, Any]]] = None,
) -> Guidance:
    """Get the single most important recommendation.

    Decision logic (priority order):
    1. Critical (>=90% usage) -> Focus on finishing current task
    2. High burn + high usage (burn_rate > 100 AND usage >= 70%) -> Wrap up or compact
    3. Smart model suggestion -> Analyze task type and suggest switch
    4. Heavy Opus usage (opus_pct > 60% AND usage >= 50%) -> Suggest Sonnet
    5. High usage (>=75%) -> Running low warning
    6. High burn rate alone (> 150) -> High velocity note
    7. Moderate usage (50-74%) -> Pacing well
    8. Healthy (< 50%) -> Good shape

    Args:
        usage_percentage: Current usage as percentage of limit
        burn_rate: Tokens per minute consumption rate
        model_distribution: Dict of model name -> percentage
        minutes_to_reset: Minutes until token reset
        current_model: Currently active model name
        recent_messages: Recent conversation messages for task detection
        top_contributors: Top token contributors data

    Returns:
        Guidance object with single recommendation
    """
    opus_pct = model_distribution.get("opus", 0)
    time_str = _format_time(minutes_to_reset)

    # Detect task type for smart model suggestions
    task_type = detect_task_type(recent_messages)

    # Priority 1: Critical usage (>=90%)
    if usage_percentage >= 90:
        return Guidance(
            primary="You're almost at your limit. Focus on finishing your current task.",
            urgency="urgent",
            action_prompt="Run /compact?",
            action_command="compact",
            interactive=True,
        )

    # Priority 2: High burn + high usage
    if burn_rate > 100 and usage_percentage >= 70:
        return Guidance(
            primary=f"Using tokens quickly at {usage_percentage:.0f}%. Consider wrapping up.",
            urgency="urgent",
            action_prompt="Run /compact?",
            action_command="compact",
            interactive=True,
        )

    # Priority 3: Smart model suggestions based on task type
    current_model_lower = current_model.lower()

    # Using Opus on simple tasks
    if task_type == TaskType.PLANNING and "opus" in current_model_lower and opus_pct > 40:
        return Guidance(
            primary="You're using Opus for planning/questions.",
            context="Sonnet handles research and planning well at lower cost.",
            interactive=True,
            suggested_model="sonnet",
            action_prompt="Switch to Sonnet?",
            action_command="model sonnet",
        )

    # Using Sonnet/Haiku on complex coding tasks
    if task_type == TaskType.CODING and "opus" not in current_model_lower and usage_percentage < 70:
        return Guidance(
            primary="This looks like a coding task.",
            context="Opus excels at complex implementation work.",
            interactive=True,
            suggested_model="opus",
            action_prompt="Switch to Opus?",
            action_command="model opus",
        )

    # Priority 4: Heavy Opus usage with moderate+ usage
    if opus_pct > 60 and usage_percentage >= 50:
        return Guidance(
            primary=f"Opus is handling {opus_pct:.0f}% of your work. Sonnet is often sufficient and more economical.",
            urgency="normal",
            action_prompt="Switch to Sonnet?",
            action_command="model sonnet",
            interactive=True,
        )

    # Priority 5: High usage (>=75%)
    if usage_percentage >= 75:
        return Guidance(
            primary=f"Running low on tokens. Resets in {time_str}.",
            urgency="normal",
            action_prompt="Run /compact?",
            action_command="compact",
            interactive=True,
        )

    # Priority 6: High burn rate alone
    if burn_rate > 150:
        return Guidance(
            primary="High token velocity. Normal if you're in a complex task.",
            urgency="calm",
        )

    # Priority 7: Moderate usage (50-74%)
    if usage_percentage >= 50:
        return Guidance(
            primary="Halfway through your window. You're pacing well.",
            urgency="calm",
        )

    # Priority 8: Healthy (<50%)
    return Guidance(
        primary="You're in good shape.",
        urgency="calm",
    )


def handle_model_switch(target_model: str) -> bool:
    """Update Claude Code configuration to switch model.

    Note: This is a placeholder. Full implementation would require
    integration with Claude Code's configuration system.

    Args:
        target_model: Model to switch to ("opus", "sonnet", "haiku")

    Returns:
        True if successful, False otherwise
    """
    # Placeholder for model switch logic
    # Would need to update ~/.claude/config.json or equivalent
    return False
