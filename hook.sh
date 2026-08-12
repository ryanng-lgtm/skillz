#!/usr/bin/env bash
#
# PostToolUse hook: sync skillz when an edit lands inside it.
#
# Claude Code pipes the tool call as JSON on stdin. Edits arrive via the
# ~/.claude/skills and ~/.codex/skills symlinks, so the path is resolved to its
# real location before deciding whether it belongs to this repo.
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# python3 handles both the JSON and the path resolution: jq is not guaranteed on
# a fresh macOS install, and BSD realpath is missing on older versions.
real="$(python3 -c '
import json, os, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
p = (d.get("tool_response") or {}).get("filePath") \
    or (d.get("tool_input") or {}).get("file_path") \
    or (d.get("tool_input") or {}).get("notebook_path")
if p:
    print(os.path.realpath(os.path.expanduser(p)))
' 2>/dev/null)" || exit 0

[ -n "$real" ] || exit 0

case "$real" in
  "$REPO"/*) ;;
  *) exit 0 ;;
esac

# Repo-internal bookkeeping must not trigger a sync of itself.
case "$real" in
  "$REPO"/.git/*|"$REPO"/.sync.log|"$REPO"/.sync-conflict) exit 0 ;;
esac

"$REPO/sync.sh"
