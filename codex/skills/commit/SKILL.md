---
name: commit
description: Commit the currently staged git changes only. Use when the user invokes /commit, asks to commit staged changes, or requests a concise commit from the existing index without staging additional files.
---

# Commit

## Overview

Create one or more git commits from the current staged changes only. Do not stage unrelated files or include unstaged work unless the user explicitly changes the request.

## Workflow

1. Run `git diff --cached --stat`.
   - If nothing is staged, tell the user and stop.
2. Run `git diff --cached` to understand the staged changes.
3. Run `git log --oneline -5` to match the repository's commit style.
4. Decide whether the staged diff spans distinct concerns.
   - If one logical concern, commit the staged index as-is.
   - If distinct concerns are staged together, unstage and re-stage subsets as needed so each commit is logical.
   - Do not stage files or hunks that were not already staged at the start of the workflow.
5. Commit with a short message.

## Commit Message

Use one summary line plus a body with at most three bullet points. Keep every line brief and direct. Do not add AI, co-authored-by, generated-by, or other watermark text.
