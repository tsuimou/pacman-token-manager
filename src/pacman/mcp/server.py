#!/usr/bin/env python3
"""MCP server for Pacman Token Manager.

Implements MCP protocol over stdio without external dependencies.
Works with Python 3.9+.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging to stderr (stdout is for MCP protocol)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def get_claude_data_path() -> Optional[Path]:
    """Find Claude data directory."""
    paths = ["~/.claude/projects", "~/.config/claude/projects"]
    for path_str in paths:
        path = Path(path_str).expanduser()
        if path.exists():
            return path
    return None


def read_usage_blocks(data_path: Path) -> List[Dict[str, Any]]:
    """Read all usage blocks from Claude data files."""
    blocks = []

    for jsonl_file in data_path.rglob("*.jsonl"):
        try:
            with open(jsonl_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "usage":
                            blocks.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Error reading {jsonl_file}: {e}")

    return blocks


def find_active_block(blocks: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the currently active usage block."""
    for block in blocks:
        if block.get("isActive"):
            return block

    if blocks:
        sorted_blocks = sorted(
            blocks,
            key=lambda b: b.get("resetAt", ""),
            reverse=True
        )
        return sorted_blocks[0] if sorted_blocks else None

    return None


def calculate_usage_stats(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate usage statistics from blocks."""
    active_block = find_active_block(blocks)

    if not active_block:
        return {"error": "No active usage block found"}

    billable_tokens = active_block.get("billableTokens") or active_block.get("totalTokens", 0)
    token_limit = active_block.get("tokenLimit", 1000000)

    usage_pct = (billable_tokens / token_limit * 100) if token_limit > 0 else 0
    tokens_remaining = max(0, token_limit - billable_tokens)

    reset_at_str = active_block.get("resetAt", "")
    minutes_to_reset = 0
    reset_time_display = ""

    if reset_at_str:
        try:
            reset_at = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
            now = datetime.now(reset_at.tzinfo)
            delta = reset_at - now
            minutes_to_reset = max(0, delta.total_seconds() / 60)

            hours = int(minutes_to_reset // 60)
            mins = int(minutes_to_reset % 60)
            reset_time_display = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        except Exception:
            pass

    model_usage: Dict[str, int] = {}
    total_model_tokens = 0

    for block in blocks:
        if block.get("isActive"):
            model = block.get("model", "unknown").lower()
            tokens = block.get("billableTokens") or block.get("totalTokens", 0)
            model_usage[model] = model_usage.get(model, 0) + tokens
            total_model_tokens += tokens

    model_distribution = {}
    for model, tokens in model_usage.items():
        pct = (tokens / total_model_tokens * 100) if total_model_tokens > 0 else 0
        model_distribution[model] = {"tokens": tokens, "percentage": round(pct, 1)}

    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    weekly_tokens = 0

    for block in blocks:
        start_time_str = block.get("startTime", block.get("resetAt", ""))
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                if start_time.replace(tzinfo=None) >= seven_days_ago:
                    block_tokens = block.get("billableTokens") or block.get("totalTokens", 0)
                    weekly_tokens += block_tokens
            except Exception:
                pass

    guidance = get_guidance(usage_pct, model_distribution, minutes_to_reset)

    alert_level = "normal"
    if usage_pct >= 90:
        alert_level = "critical"
    elif usage_pct >= 75:
        alert_level = "warning"
    elif usage_pct >= 50:
        alert_level = "caution"

    return {
        "current_session": {
            "tokens_used": billable_tokens,
            "token_limit": token_limit,
            "tokens_remaining": tokens_remaining,
            "usage_percentage": round(usage_pct, 1),
            "reset_in": reset_time_display,
            "minutes_to_reset": round(minutes_to_reset, 1),
        },
        "weekly": {
            "tokens_used": weekly_tokens,
            "note": "7-day rolling total"
        },
        "model_breakdown": model_distribution,
        "alert_level": alert_level,
        "guidance": guidance,
    }


def get_guidance(
    usage_pct: float,
    model_distribution: Dict[str, Any],
    minutes_to_reset: float
) -> Dict[str, Any]:
    """Generate contextual guidance based on usage."""
    opus_pct = 0
    for model, data in model_distribution.items():
        if "opus" in model.lower():
            opus_pct = data.get("percentage", 0)
            break

    if usage_pct >= 90:
        return {
            "message": "You're almost at your limit. Focus on finishing your current task.",
            "urgency": "critical",
            "action": {"prompt": "Run /compact?", "command": "/compact"}
        }

    if opus_pct > 60 and usage_pct >= 70:
        return {
            "message": f"Opus is handling {opus_pct:.0f}% of your work at {usage_pct:.0f}% usage. Consider switching to Sonnet.",
            "urgency": "warning",
            "action": {"prompt": "Switch to Sonnet?", "command": "/model sonnet"}
        }

    if usage_pct >= 75:
        hours = int(minutes_to_reset // 60)
        mins = int(minutes_to_reset % 60)
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        return {
            "message": f"Running low on tokens. Resets in {time_str}.",
            "urgency": "warning",
            "action": {"prompt": "Run /compact?", "command": "/compact"}
        }

    if opus_pct > 60 and usage_pct >= 50:
        return {
            "message": f"Opus is handling {opus_pct:.0f}% of your work. Sonnet is often sufficient and more economical.",
            "urgency": "normal",
            "action": {"prompt": "Switch to Sonnet?", "command": "/model sonnet"}
        }

    if usage_pct >= 50:
        return {
            "message": "Halfway through your window. You're pacing well.",
            "urgency": "normal",
            "action": None
        }

    return {
        "message": "You're in good shape.",
        "urgency": "normal",
        "action": None
    }


def format_tokens(tokens: int) -> str:
    """Format token count for display."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}m"
    elif tokens >= 1_000:
        return f"{tokens / 1_000:.0f}k"
    return str(tokens)


def handle_chomp() -> str:
    """Handle the chomp tool call."""
    data_path = get_claude_data_path()
    if not data_path:
        return "Could not find Claude data directory. Make sure Claude Code is installed."

    blocks = read_usage_blocks(data_path)
    if not blocks:
        return "No usage data found. Start using Claude Code to generate usage data."

    stats = calculate_usage_stats(blocks)

    if "error" in stats:
        return stats["error"]

    session = stats["current_session"]
    weekly = stats["weekly"]
    guidance = stats["guidance"]

    lines = []
    lines.append("## Token Usage")
    lines.append("")

    alert_level = stats["alert_level"]
    if alert_level == "critical":
        lines.append(f"**ALMOST OUT!** Resets in {session['reset_in']}")
    elif alert_level == "warning":
        lines.append(f"**Running low** - Resets in {session['reset_in']}")
    elif alert_level == "caution":
        lines.append(f"**Halfway there** - Resets in {session['reset_in']}")

    lines.append("")
    lines.append("### Current Session")
    lines.append(f"- **Usage:** {session['usage_percentage']}% ({format_tokens(session['tokens_used'])} / {format_tokens(session['token_limit'])})")
    lines.append(f"- **Remaining:** {format_tokens(session['tokens_remaining'])}")
    lines.append(f"- **Resets in:** {session['reset_in']}")

    lines.append("")
    lines.append("### Weekly Total")
    lines.append(f"- **7-day rolling:** {format_tokens(weekly['tokens_used'])}")

    if stats["model_breakdown"]:
        lines.append("")
        lines.append("### By Model")
        for model, data in stats["model_breakdown"].items():
            lines.append(f"- **{model.title()}:** {format_tokens(data['tokens'])} ({data['percentage']}%)")

    lines.append("")
    lines.append("### Guidance")
    lines.append(f"_{guidance['message']}_")

    if guidance.get("action"):
        lines.append("")
        lines.append(f"**Suggested action:** `{guidance['action']['command']}`")

    return "\n".join(lines)


def send_response(response: Dict[str, Any]) -> None:
    """Send JSON-RPC response to stdout."""
    response_str = json.dumps(response)
    # MCP uses Content-Length header style framing
    sys.stdout.write(f"Content-Length: {len(response_str)}\r\n\r\n{response_str}")
    sys.stdout.flush()


def send_result(id: Any, result: Any) -> None:
    """Send successful result."""
    send_response({"jsonrpc": "2.0", "id": id, "result": result})


def send_error(id: Any, code: int, message: str) -> None:
    """Send error response."""
    send_response({"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}})


def read_message() -> Optional[Dict[str, Any]]:
    """Read a JSON-RPC message from stdin."""
    # Read headers
    headers = {}
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            break
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

    # Read content
    content_length = int(headers.get("content-length", 0))
    if content_length == 0:
        return None

    content = sys.stdin.read(content_length)
    return json.loads(content)


def handle_request(request: Dict[str, Any]) -> None:
    """Handle incoming JSON-RPC request."""
    method = request.get("method", "")
    id = request.get("id")
    params = request.get("params", {})

    logger.debug(f"Received request: {method}")

    if method == "initialize":
        send_result(id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "pacman-token-manager",
                "version": "3.2.0"
            }
        })

    elif method == "notifications/initialized":
        # No response needed for notifications
        pass

    elif method == "tools/list":
        send_result(id, {
            "tools": [
                {
                    "name": "chomp",
                    "description": "Check Claude Code token usage. Shows current session usage, weekly total, model breakdown, and smart guidance.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        if tool_name == "chomp":
            result_text = handle_chomp()
            send_result(id, {
                "content": [
                    {"type": "text", "text": result_text}
                ]
            })
        else:
            send_error(id, -32601, f"Unknown tool: {tool_name}")

    elif method == "ping":
        send_result(id, {})

    else:
        if id is not None:  # Only respond to requests, not notifications
            send_error(id, -32601, f"Method not found: {method}")


def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Pacman Token Manager MCP server")

    try:
        while True:
            message = read_message()
            if message is None:
                break
            handle_request(message)
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
