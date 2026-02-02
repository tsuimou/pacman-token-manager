# Pacman Token Manager

Tool for monitoring more detail info on token usage in your terminal.

```
┌──────────────────────────────────────────────────────────────┐
│  Pacman Token Manager                                        │
├──────────────────────────────────────────────────────────────┤
│  Halfway there · Resets in 4h 25m (started 10:00 AM)         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TKN █████░░░░░░░░░░░░░░░  27%  193,920 / 728,474            │
│  534k left · Resets in 4h 25m                                │
│                                                              │
├─ Usage over time ────────────────────────────────────────────┤
│                                                              │
│  Period             Usage              TKN                   │
│  Current session    ███░░░░░░░░░  27%   193k                 │
│  Resets in 4h 25m                                            │
│                                                              │
│  Current week                      4.6m                      │
│  (7-day rolling total)                                       │
│                                                              │
├─ Breakdown ──────────────────────────────────────────────────┤
│                                                              │
│  By Model           Usage        TKN                         │
│  Opus               ████████████ 183k                        │
│  Sonnet             ░░░░░░░░░░░░ 10k                         │
│                                                              │
├─ Guidance ───────────────────────────────────────────────────┤
│                                                              │
│  Opus is handling 75% of your work. Sonnet is often          │
│  sufficient and more economical.                             │
│                                                              │
│  → Switch to Sonnet?  [Y]es  [N]o thanks                     │
│                                                              │
│  Ctrl+C to exit                                              │
└──────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install pacman-token-manager
```

| Method | Command | What You Get |
|--------|---------|--------------|
| **PyPI (Recommended)** | `pip install pacman-token-manager` | Stable release |
| **GitHub (Latest)** | `pip install git+https://github.com/tsuimou/pacman-token-manager.git` | Latest code |
| **Local Development** | `pip install -e .` | Editable install |

## Usage

```bash
# Pick your favorite command
chomp
pac
pacman
pactkn
pacman-token-manager
```

## Features

- **Accurate token tracking** - Counts only billable tokens (excludes free cache reads)
- **All projects view** - Tracks usage across ALL your Claude Code projects
- **Matches Claude /usage** - Shows the same percentage as Claude's built-in `/usage`
- **Human-first design** - No technical jargon, just clear status
- **Smart alerts** - Warns you at 50%, 75%, and 90% usage
- **Model breakdown** - See which models are eating your tokens
- **Project breakdown** - See which projects are using your quota
- **Usage over time** - Track 5hr window and weekly usage
- **Contextual guidance** - Smart recommendations based on your usage patterns
- **Interactive actions** - Press Y/N to execute suggested actions
- **Zero token cost** - Pacman reads local files, doesn't call the API

## Display Information

| Section | Data Shown |
|---------|------------|
| **Token Status** | Progress bar + % + tokens used/limit + reset time |
| **Usage Over Time** | Current session (% + reset time) and Current week (7-day total) |
| **Breakdown** | By Model and By Project with token counts |
| **Guidance** | Context-aware recommendation + optional Y/N action |

## Smart Guidance

Pacman provides contextual guidance based on your usage:

| Condition | Guidance | Action |
|-----------|----------|--------|
| ≥90% usage | "You're almost at your limit..." | → Run /compact? [Y/N] |
| High burn + ≥70% | "Using tokens quickly..." | → Run /compact? [Y/N] |
| Heavy Opus (>60%) | "Opus is handling X%..." | → Switch to Sonnet? [Y/N] |
| ≥75% usage | "Running low on tokens..." | → Run /compact? [Y/N] |
| High burn rate | "High token velocity..." | (informational) |
| 50-74% usage | "Halfway through..." | (informational) |
| <50% usage | "You're in good shape." | (none needed) |

## Interactive Actions

When a Y/N prompt appears, you can:
- Press **Y** to execute the suggested command
- Press **N** to dismiss (won't show again this session)
- Press **Ctrl+C** to exit

## Token Calculation

Pacman correctly calculates **billable tokens** that count toward your rate limit:

| Token Type | Counts Toward Limit? |
|------------|---------------------|
| Input tokens | Yes |
| Output tokens | Yes |
| Cache creation | Yes |
| Cache reads | **No (FREE)** |

This matches how Claude's `/usage` calculates your usage.

## Alerts

| Threshold | Color | Alert |
|-----------|-------|-------|
| 50% | Yellow | Halfway there |
| 75% | Orange | Running low |
| 90% | Red | ALMOST OUT! |

## Requirements

- Python 3.9+
- Claude Code CLI (creates the usage data files in `~/.claude/projects/`)
