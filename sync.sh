#!/usr/bin/env bash
#
# Commit and push whatever changed in this repo. Invoked by the Claude Code
# Stop hook, so a turn's edits go out when it ends, and safe to run by hand.
#
# --pull also brings in what other machines pushed when nothing changed here.
# The SessionStart hook runs it that way, so a session starts on the latest
# skills, links any skill the pull added, and drops links to any it removed.
#
# Never force-pushes: a force from one machine would destroy commits made on
# another. On a rebase conflict it stops, restores the working tree, and leaves
# a note in .sync-conflict for you to resolve.
#
# Commits and pushes nothing while check.py fails, and leaves its report in
# .sync-check.
#
set -uo pipefail

PULL=0
[ "${1:-}" = "--pull" ] && PULL=1

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO" || exit 1

LOCK="$REPO/.sync.lock"
LOG="$REPO/.sync.log"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >>"$LOG"; }

# Serialize overlapping runs; a hook can fire several times in a burst.
#
# The lock is a kernel flock on fd 9, not a lock directory. A directory outlives
# a run that dies before its EXIT trap fires (SIGKILL after the hook timeout, a
# closed session), and every later run then sees it and quietly exits — that
# stopped all syncing from Sep 23 to Oct 26 2026. The kernel drops a flock
# however the process dies.
#
# flock(1) is not on macOS, so perl takes the lock there. The lock belongs to
# the open file, not the process, so it stays held after perl exits.
take_lock() {
  if command -v flock >/dev/null; then
    flock -n 9
    return
  fi
  perl -MFcntl=:flock -e 'open(my $fh, ">&=", 9) or exit 2; flock($fh, LOCK_EX | LOCK_NB) or exit 1'
}

[ -d "$LOCK" ] && rmdir "$LOCK" 2>/dev/null # lock directory left by the old scheme
if ! exec 9>>"$LOCK"; then
  log "cannot open $LOCK — sync skipped"
  exit 1
fi
take_lock
case $? in
  0) ;;
  1) exit 0 ;; # another run holds it
  *)
    log "cannot lock $LOCK — sync skipped"
    exit 1
    ;;
esac

# A child that inherits fd 9 and outlives this shell (a hung push, a detached
# `git gc --auto`) would keep the lock held, so no git call gets it.
git() { command git "$@" 9>&-; }

# Safety hold. `touch .sync-hold` stops automatic pushes on this machine —
# used while the remote is not yet in the state you want, or to work offline
# without the hook publishing half-finished edits.
if [ -e "$REPO/.sync-hold" ]; then
  log "hold file present — sync skipped"
  exit 0
fi

# Commit everything that changed. Sets $changed to what the commit touched.
commit_changes() {
  git add -A || { log "git add failed"; return 1; }

  if git diff --cached --quiet; then
    log "nothing to commit"
    return 0
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
    # `paste -sd', '` would be wrong: -d takes a LIST of delimiters applied
    # cyclically, so three names join as "a,b c". Join on a comma, then space it.
    if [ "$n_skills" -le 3 ]; then
      scope="skills($(printf '%s\n' "$skills" | paste -sd, - | sed 's/,/, /g'))"
    else
      scope="skills($(printf '%s\n' "$skills" | head -3 | paste -sd, - | sed 's/,/, /g') +$((n_skills - 3)) more)"
    fi
    [ "$n_other" -gt 0 ] && scope="$scope + config"
  fi

  n_files="$(printf '%s\n' "$paths" | grep -c . || true)"
  counts="$(git diff --cached --numstat \
    | awk '{ if ($1 != "-") i += $1; if ($2 != "-") d += $2 } END { printf "+%d/-%d", i, d }')"
  [ "$n_files" -eq 1 ] && unit="file" || unit="files"

  subject="$scope: $verb ($n_files $unit, $counts)"

  # The per-file stat goes in the body, where it costs nothing and answers "what
  # did this touch" without a diff. Capped, so a bulk sync can't write an essay.
  body="$(git diff --cached --stat=100 | head -25)

Synced from $(hostname -s)."

  if ! git commit -q -m "$subject" -m "$body"; then
    log "nothing to commit"
    return 0
  fi
  changed="$scope"
}

unpushed() { [ -n "$(git rev-list '@{upstream}..HEAD' 2>/dev/null)" ]; }

# Publish nothing that fails check.py. It checks the whole tree, so a failure
# holds back earlier local commits as well as this turn's edits.
check_ok=1
if [ -f "$REPO/check.py" ] && ! report="$(python3 -I "$REPO/check.py" 2>&1)"; then
  check_ok=0
  {
    echo "check.py failed at $(date), so sync committed and pushed nothing."
    echo "Fix what it reports; the next sync after that goes out as usual:"
    echo "  cd $REPO && python3 -I check.py"
    echo
    echo "$report"
  } >"$REPO/.sync-check"
  log "check.py failed — commit and push held back, see .sync-check"
else
  rm -f "$REPO/.sync-check"
fi

changed=""
if [ "$check_ok" = 1 ] && [ -n "$(git status --porcelain)" ]; then
  commit_changes || exit 1
fi

# A failed check still pulls on --pull when the tree is clean, so a fix pushed
# from another machine can arrive. A dirty tree would need the autostash, which
# can leave conflict markers in uncommitted work.
if [ "$check_ok" = 0 ]; then
  [ "$PULL" = 1 ] && [ -z "$(git status --porcelain)" ] || exit 1
fi

# A clean tree still pushes commits an earlier run left local (a commit made
# by hand, a push that failed). Without that, or --pull, there is nothing to do.
[ -z "$changed" ] && [ "$PULL" = 0 ] && ! unpushed && exit 0

# A branch with no upstream can't be pulled. Say so rather than letting the
# failed pull below read as a network problem.
if ! git rev-parse -q --verify '@{upstream}' >/dev/null 2>&1; then
  log "no upstream for $(git rev-parse --abbrev-ref HEAD) — pull and push skipped"
  exit 1
fi

# A hook can start without a usable ssh agent, and every pull and push then
# fails with "Permission denied (publickey)". Use the agent kept for Claude
# sessions when this machine has one.
if ! ssh-add -l >/dev/null 2>&1 && [ -S "$HOME/.ssh/claude-agent.sock" ]; then
  export SSH_AUTH_SOCK="$HOME/.ssh/claude-agent.sock"
fi

before="$(git rev-parse HEAD)"
if ! git pull --rebase --autostash -q 2>>"$LOG"; then
  # Only a rebase that stopped is a conflict. A pull that failed to reach the
  # remote (offline, ssh auth) used to be reported as one too.
  if [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
    git rebase --abort 2>/dev/null
    {
      echo "Rebase onto origin/$(git rev-parse --abbrev-ref HEAD) conflicted at $(date)."
      echo "Your commit is safe locally. Resolve with:"
      echo "  cd $REPO && git pull --rebase"
      echo "Do NOT force-push; another machine has commits this one lacks."
    } >"$REPO/.sync-conflict"
    log "rebase conflict — push skipped"
  else
    log "pull failed (offline?) — local commits go out on the next sync"
  fi
  exit 1
fi
rm -f "$REPO/.sync-conflict"

if [ "$(git rev-parse HEAD)" != "$before" ]; then
  log "pulled $(git rev-list --count "$before..HEAD") commits"
  # Skills are linked one by one, so one another machine added has no link
  # here, and one it removed leaves a dead link, until install.sh runs.
  # --links-only skips the Codex plugin step, which can hang, and the hook
  # registration. --no-renames reports a moved skill as an add and a delete,
  # which a rename filter would miss.
  if [ -n "$(git diff --no-renames --name-only --diff-filter=AD "$before" HEAD -- \
    'claude/skills/*/SKILL.md' 'codex/skills/*')" ]; then
    "$REPO/install.sh" --links-only >>"$LOG" 2>&1 9>&- || log "install.sh --links-only failed"
  fi
fi

[ "$check_ok" = 1 ] || exit 1
unpushed || exit 0

if ! git push -q 2>>"$LOG"; then
  log "push failed (offline?) — commit is local, will go out on the next sync"
  exit 1
fi

log "pushed: ${changed:-commits left local by an earlier run}"
