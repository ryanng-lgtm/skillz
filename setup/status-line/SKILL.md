---
name: status-line
description: >-
  Use when setting up Ryan's Claude Code status line on a machine (a new
  machine, a fresh ~/.claude, or a status line that is missing or not his),
  or when changing what the status line shows. Trigger: /status-line.
disable-model-invocation: true
---

# status-line — install Ryan's Claude Code status line

## Overview

Claude Code runs the `statusLine` command in `~/.claude/settings.json` and shows what it prints under the prompt. This skill points that setting at `scripts/statusline.sh`, which prints:

```
Opus 5.5 | meta_repo | main | ctx 42% | 5h 63% 7d 85% | high
```

| Part | What it is | Colour |
| --- | --- | --- |
| `Opus 5.5` | current model | bold cyan |
| `meta_repo` | working folder | blue |
| `main` | git branch, hidden outside a repo | magenta |
| `ctx 42%` | context window used | green under 50%, yellow from 50%, red from 80% |
| `5h 63% 7d 85%` | 5-hour and weekly usage limits; absent on an API key | same as `ctx` |
| `high` | reasoning effort | grey |

Any part Claude Code doesn't report is skipped.

**Core principle: change only the `statusLine` key. Every other setting in `settings.json` stays as it was.**

## Procedure

1. Check that `jq` and `git` are installed: `command -v jq git`. If `jq` is missing, ask before installing it (`brew install jq` on macOS, `sudo apt install jq` on Debian or Ubuntu).
2. Run `python3 -I scripts/install.py`. It backs up `settings.json` to `settings.json.bak-<timestamp>` and sets `statusLine`, or reports that it is already set. If a different status line is set, it prints that one and changes nothing: show it to the user, and rerun with `--force` only if they agree to replace it.
3. Run `scripts/statusline.sh < scripts/sample.json`. It prints the example line in colour, without the branch. If it prints nothing, `jq` is missing or not on `PATH`.
4. Tell the user the line appears from their next Claude Code session.

## Changing what it shows

Edit `scripts/statusline.sh`. Each part is one `add` line, and the colour thresholds are the `80` and `50` in `pc()`. The setting runs the script from this repo, so a change reaches every machine with the next sync and needs no reinstall.

## Rules

- Never edit `settings.json` by hand or rewrite it whole; `install.py` changes the one key and keeps a backup.
