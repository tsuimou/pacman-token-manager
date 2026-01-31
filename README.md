# Pacman Token Manager

A human-first CLI tool for monitoring Claude AI token usage.

```
┌──────────────────────────────────────────────────────────────┐
│  Pacman Token Manager                                        │
├──────────────────────────────────────────────────────────────┤
│  ⚠️  Running low on tokens                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TKN      🟠 ███████████████░░░░░ 65,000 / 86,000            │
│  Running low                                                 │
│                                                              │
│  TKN limit refreshes in 2h 14m                               │
│                                                              │
├─ Why ────────────────────────────────────────────────────────┤
│  Model               Usage           TKN                     │
│  Sonnet             ████████████ 42k                         │
│  Opus               ██████░░░░░░ 23k                         │
│                                                              │
├─ Usage over time ────────────────────────────────────────────┤
│  Period              Usage           TKN                     │
│  Recent session     ██░░░░░░░░░░ 9k                          │
│  Today              ██████░░░░░░ 26k                         │
│  This month         ████████████ 45k                         │
│                                                              │
├─ Next step ──────────────────────────────────────────────────┤
│  [1] Use Sonnet instead of Opus                              │
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

- **Real-time token monitoring** - Reads actual usage from Claude Code
- **Human-first design** - No technical jargon, just clear status
- **Smart alerts** - Warns you at 50%, 75%, and 90% usage
- **Model breakdown** - See which models are eating your tokens
- **Usage over time** - Track session, daily, and monthly usage
- **Actionable suggestions** - Know what to do when running low

## Status Indicators

| Status | Meaning |
|--------|---------|
| 🟢 | Plenty left (< 50%) |
| 🟠 | Using a lot (50-80%) |
| 🔴 | Almost out (> 80%) |

## Alerts

| Threshold | Alert |
|-----------|-------|
| ≥ 90% | ⚠️ ALMOST OUT! Consider starting a new session |
| ≥ 75% | ⚠️ Running low on tokens |
| ≥ 50% | ⚠️ Token usage is moderate |

## Requirements

- Python 3.9+
- Claude Code CLI (creates the usage data files)
