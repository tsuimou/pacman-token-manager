# Pacman Token Manager

Tool for monitoring more detail info on token usage in your terminal.

```
┌──────────────────────────────────────────────────────────────┐
│  Pacman Token Manager                                        │
├──────────────────────────────────────────────────────────────┤
│  Running low · Resets in 2h 14m (started 5:00 PM)            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TKN ███████████████░░░░░ 580,000 / 1,000,000                │
│  420k left before you have to wait                           │
│                                                              │
│  Resets in 2h 14m (started 5:00 PM)                          │
│                                                              │
├─ Usage over time ────────────────────────────────────────────┤
│                                                              │
│  Period             Usage        TKN                         │
│  Recent session     ██░░░░░░░░░░ 116k                        │
│  Today              ██████░░░░░░ 311k                        │
│  This month         ████████████ 545k                        │
│                                                              │
├─ Breakdown ──────────────────────────────────────────────────┤
│                                                              │
│  By Model           Usage        TKN                         │
│  Opus               ████████████ 580k                        │
│                                                              │
│  By Project         Usage        TKN                         │
│  subagents          ████████████ 302k                        │
│  my-project         ███████████░ 278k                        │
│                                                              │
├─ Next step ──────────────────────────────────────────────────┤
│                                                              │
│  [1] Switch to a lighter model                               │
│  [2] Run /compact to reduce context                          │
│  [3] Clean up long conversations                             │
│  [4] Do nothing for now                                      │
│                                                              │
│  Ctrl+C to exit                                              │
└──────────────────────────────────────────────────────────────┘
```

## Installation

```bash
pip install -e .
```

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
- **Usage over time** - Track session, daily, and monthly usage
- **Actionable suggestions** - Know what to do when running low
- **Zero token cost** - Pacman reads local files, doesn't call the API

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
