#!/usr/bin/env bash
#
# Commit and push whatever changed in this repo. Invoked by the Claude Code
# hook after any edit that lands inside skillz, and safe to run by hand.
#
# Never force-pushes: a force from one machine would destroy commits made on
# another. On a rebase conflict it stops, restores the working tree, and leaves
# a note in .sync-conflict for you to resolve.
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO" || exit 1

LOCK="$REPO/.sync.lock"
LOG="$REPO/.sync.log"

# Serialize overlapping runs; a hook can fire several times in a burst.
if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

# Safety hold. `touch .sync-hold` stops automatic pushes on this machine —
# used while the remote is not yet in the state you want, or to work offline
# without the hook publishing half-finished edits.
if [ -e "$REPO/.sync-hold" ]; then
  log "hold file present — sync skipped"
  exit 0
fi

git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ] && exit 0

# Summarize what moved, for the commit subject.
changed="$(git status --porcelain | awk '{print $NF}' \
  | sed -n 's#^\(claude\|codex\)/skills/\([^/]*\)/.*#\2#p' | sort -u | paste -sd', ' -)"
[ -z "$changed" ] && changed="config"

git add -A || { log "git add failed"; exit 1; }

if ! git commit -q -m "Sync ${changed} from $(hostname -s)"; then
  log "nothing to commit"
  exit 0
fi

if ! git pull --rebase --autostash -q 2>>"$LOG"; then
  git rebase --abort 2>/dev/null
  {
    echo "Rebase onto origin/$(git rev-parse --abbrev-ref HEAD) conflicted at $(date)."
    echo "Your commit is safe locally. Resolve with:"
    echo "  cd $REPO && git pull --rebase"
    echo "Do NOT force-push; another machine has commits this one lacks."
  } >"$REPO/.sync-conflict"
  log "rebase conflict — push skipped"
  exit 1
fi
rm -f "$REPO/.sync-conflict"

if ! git push -q 2>>"$LOG"; then
  log "push failed (offline?) — commit is local, will go out on the next sync"
  exit 1
fi

log "pushed: $changed"
