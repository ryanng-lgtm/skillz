---
name: setup-statusline
description: >-
  Use when a Claude Code user wants a status line under the prompt showing the
  model, working folder, git branch, context used, usage limits or reasoning
  effort, or wants to change which of those it shows. Claude Code only; a
  one-time setup per machine. Trigger: /setup-statusline.
disable-model-invocation: true
---

# setup-statusline — set up a Claude Code status line with the parts the user picks

## Overview

Claude Code runs the `statusLine` command in its `settings.json` and shows what it prints under the prompt. This skill writes `statusline.sh` into the Claude Code config folder (`$CLAUDE_CONFIG_DIR`, default `~/.claude`) and points `statusLine` at it. With every part on, the line reads:

```
Opus 5.5 | my-app | main | ctx 42% | 5h 63% 7d 85% | high
```

| Part | Shows | Colour |
| --- | --- | --- |
| `model` | current model | bold cyan |
| `folder` | working folder | blue |
| `branch` | git branch, hidden outside a repo | magenta |
| `ctx` | context window used | green under 50%, yellow from 50%, red from 80% |
| `limits` | 5-hour and weekly usage limits; absent on an API key | same as `ctx` |
| `effort` | reasoning effort | grey |

The chosen parts always print in this order, and any part Claude Code doesn't report is skipped. The script is a copy, not a link into this skill, so plugin updates never change it; rerunning the skill does.

**Core principle: change only the `statusLine` key, and never replace a status line the user already has without their yes.**

## Procedure

1. Check `command -v jq git`. If `jq` is missing, ask before installing it (`brew install jq` on macOS, `sudo apt install jq` on Debian or Ubuntu).
2. Show the user the example line and the parts table above.
3. Ask which parts to show with `AskUserQuestion`, multi-select. It takes at most four options per question, so ask two: Session with `model`, `folder`, `branch`, `effort`, and Usage with `ctx`, `limits`. At least one part must be picked.
4. Run `python3 -I "${CLAUDE_SKILL_DIR}/scripts/install.py" --parts <picked parts, comma-separated>`. It writes the script, backs up `settings.json` to `settings.json.bak-<timestamp>`, and sets `statusLine`. When a different status line is already set, or `statusline.sh` exists and this skill didn't write it, it prints what is there, exits 1 and changes nothing: show the user that, and rerun with `--force` only if they agree to replace it. `--force` backs up what it replaces.
5. Run the script `install.py` reported writing on the sample, `<script> < "${CLAUDE_SKILL_DIR}/scripts/sample.json"`, and show the user the output: their picked parts in colour, without the branch. Empty output means `jq` is missing or not on `PATH`, unless `branch` is the only part.
6. Tell the user the line appears from their next Claude Code session, and that rerunning `/setup-statusline` changes the parts.

## Rules

- Never edit `settings.json` by hand or rewrite it whole; `install.py` changes the one key and keeps a backup.
