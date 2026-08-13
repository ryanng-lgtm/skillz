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

git add -A || { log "git add failed"; exit 1; }

if git diff --cached --quiet; then
  log "nothing to commit"
  exit 0
fi

# Describe what actually moved, from the staged diff.
#
# Everything below reads `git diff --cached`, not `git status`, and runs AFTER
# `git add -A`. That matters twice: untracked directories are expanded to real
# file paths by then, and each entry carries an A/M/D letter, so the subject can
# say "add" instead of guessing "update".
#
# `sed -E` is required throughout: `\(a\|b\)` alternation is a GNU extension and
# BSD sed (macOS) matches it as the literal text "claude|codex". Every subject
# read "Sync config from ..." until that was fixed, whatever had changed.
staged="$(git diff --cached --name-status)"
paths="$(printf '%s\n' "$staged" | cut -f2-)"

skills="$(printf '%s\n' "$paths" \
  | sed -nE 's#^(claude|codex)/skills/([^/]+)/.*#\2#p' | sort -u)"
n_skills="$(printf '%s\n' "$skills" | grep -c . || true)"
n_other="$(printf '%s\n' "$paths" | sed -E '/^(claude|codex)\/skills\//d' \
  | grep -c . || true)"

# One verb for the whole commit. All-new is an add, all-gone is a remove,
# anything mixed is an update — a rename beside an edit is not an "add".
case "$(printf '%s\n' "$staged" | cut -f1 | cut -c1 | sort -u | tr -d '\n')" in
  A) verb="add"    ;;
  D) verb="remove" ;;
  *) verb="update" ;;
esac

if [ "$n_skills" -eq 0 ]; then
  scope="config"
else
  if [ "$n_skills" -le 3 ]; then
    scope="skills($(printf '%s\n' "$skills" | paste -sd', ' -))"
  else
    scope="skills($(printf '%s\n' "$skills" | head -3 | paste -sd', ' -) +$((n_skills - 3)) more)"
  fi
  [ "$n_other" -gt 0 ] && scope="$scope + config"
fi

n_files="$(printf '%s\n' "$paths" | grep -c . || true)"
counts="$(git diff --cached --numstat \
  | awk '{ if ($1 != "-") i += $1; if ($2 != "-") d += $2 } END { printf "+%d/-%d", i, d }')"
[ "$n_files" -eq 1 ] && unit="file" || unit="files"

subject="$scope: $verb ($n_files $unit, $counts)"
changed="$scope"

# The per-file stat goes in the body, where it costs nothing and answers "what
# did this touch" without a diff. Capped, so a bulk sync can't write an essay.
body="$(git diff --cached --stat=100 | head -25)

Synced from $(hostname -s)."

if ! git commit -q -m "$subject" -m "$body"; then
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
