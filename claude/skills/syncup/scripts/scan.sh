#!/usr/bin/env bash
#
# scan.sh — list local git repos and how far out of sync they are.
#
# Prints one TSV row per repo:
#   name  branch  default  ahead  behind  dirty  state  path
#
# state is one of:
#   sync     needs a pull and/or a rebase
#   clean    on the default branch, up to date, nothing uncommitted
#   blocked  cannot be synced unattended (see reason in the branch column)
#
# Usage:
#   scan.sh [--root DIR] [--no-fetch] [--jobs N] [--all]

set -uo pipefail

ROOT="${SYNCUP_ROOT:-$HOME/Documents/GitLab}"
DO_FETCH=1
JOBS=8
SHOW_ALL=0

usage() {
	sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
	case "$1" in
	--root)
		ROOT="$2"
		shift 2
		;;
	--no-fetch)
		DO_FETCH=0
		shift
		;;
	--jobs)
		JOBS="$2"
		shift 2
		;;
	--all)
		SHOW_ALL=1
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		printf 'scan.sh: unknown argument: %s\n' "$1" >&2
		exit 2
		;;
	esac
done

if [ ! -d "$ROOT" ]; then
	printf 'scan.sh: root not found: %s\n' "$ROOT" >&2
	exit 2
fi

# Collect candidate repo paths (a worktree has .git as a file, not a dir).
repos=()
for d in "$ROOT"/*/; do
	d="${d%/}"
	if [ -e "$d/.git" ]; then
		repos+=("$d")
	fi
done

if [ "${#repos[@]}" -eq 0 ]; then
	printf 'scan.sh: no git repos under %s\n' "$ROOT" >&2
	exit 1
fi

# A failed fetch is not a warning, it is a correctness problem: every ahead/behind
# count below would be measured against stale refs and silently understate drift.
# Failures are recorded per repo and surfaced as state=stale.
FAIL_DIR=""
if [ "$DO_FETCH" -eq 1 ]; then
	FAIL_DIR="$(mktemp -d)"
	# shellcheck disable=SC2064  # expand FAIL_DIR now, not at trap time
	trap "rm -rf '$FAIL_DIR'" EXIT INT TERM

	printf '%s\n' "${repos[@]}" |
		xargs -P "$JOBS" -I{} sh -c '
			if ! git -C "$1" fetch --quiet --prune origin >/dev/null 2>&1; then
				: >"$2/$(basename "$1")"
			fi
		' _ {} "$FAIL_DIR"

	nfail="$(find "$FAIL_DIR" -type f | grep -c '^' | tr -d ' ')"
	if [ "$nfail" -gt 0 ]; then
		printf 'scan.sh: fetch FAILED for %s repo(s) — their counts are from stale refs.\n' "$nfail" >&2
		printf 'scan.sh: check auth first:  ssh-add -l  &&  ssh -T git@github.com\n' >&2
	fi
fi

fetch_state() {
	[ "$DO_FETCH" -eq 0 ] && {
		printf 'skipped\n'
		return
	}
	if [ -f "$FAIL_DIR/$1" ]; then printf 'failed\n'; else printf 'ok\n'; fi
}

default_branch() {
	# Resolve the remote's default branch without a network call.
	local repo="$1" ref
	ref="$(git -C "$repo" symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null)"
	if [ -n "$ref" ]; then
		printf '%s\n' "${ref#origin/}"
		return 0
	fi
	for cand in main master develop; do
		if git -C "$repo" rev-parse -q --verify "refs/remotes/origin/$cand" >/dev/null 2>&1; then
			printf '%s\n' "$cand"
			return 0
		fi
	done
	return 1
}

in_progress() {
	local gitdir="$1"
	[ -d "$gitdir/rebase-merge" ] && return 0
	[ -d "$gitdir/rebase-apply" ] && return 0
	[ -f "$gitdir/MERGE_HEAD" ] && return 0
	[ -f "$gitdir/CHERRY_PICK_HEAD" ] && return 0
	[ -f "$gitdir/BISECT_LOG" ] && return 0
	return 1
}

# Columns 1-8 are stable; the fetch column is appended as 9 so callers that
# index $8 for the path keep working.
emit() {
	printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$@" "$(fetch_state "$1")"
}

for repo in "${repos[@]}"; do
	name="$(basename "$repo")"
	gitdir="$(git -C "$repo" rev-parse --git-dir 2>/dev/null)"
	case "$gitdir" in
	/*) ;;
	*) gitdir="$repo/$gitdir" ;;
	esac

	if ! git -C "$repo" remote | grep -qx origin; then
		[ "$SHOW_ALL" -eq 1 ] && emit "$name" "no-origin" "-" 0 0 0 blocked "$repo"
		continue
	fi

	if ! git -C "$repo" rev-parse -q --verify HEAD >/dev/null 2>&1; then
		[ "$SHOW_ALL" -eq 1 ] && emit "$name" "no-commits" "-" 0 0 0 blocked "$repo"
		continue
	fi

	branch="$(git -C "$repo" branch --show-current 2>/dev/null)"
	if [ -z "$branch" ]; then
		emit "$name" "detached-head" "-" 0 0 0 blocked "$repo"
		continue
	fi

	if in_progress "$gitdir"; then
		emit "$name" "op-in-progress" "-" 0 0 0 blocked "$repo"
		continue
	fi

	if ! def="$(default_branch "$repo")"; then
		emit "$name" "$branch" "no-default" 0 0 0 blocked "$repo"
		continue
	fi

	counts="$(git -C "$repo" rev-list --left-right --count "origin/$def...HEAD" 2>/dev/null)"
	behind="$(printf '%s' "$counts" | awk '{print ($1 == "") ? 0 : $1}')"
	ahead="$(printf '%s' "$counts" | awk '{print ($2 == "") ? 0 : $2}')"
	[ -n "$behind" ] || behind=0
	[ -n "$ahead" ] || ahead=0

	dirty="$(git -C "$repo" status --porcelain 2>/dev/null | grep -c '^' | tr -d ' ')"

	# Dirtiness alone is not a reason to sync — it only complicates one.
	state=clean
	if [ "$behind" -gt 0 ] || [ "$branch" != "$def" ]; then
		state=sync
	fi

	# Counts computed from refs we could not refresh are not evidence of anything.
	if [ "$(fetch_state "$name")" = failed ]; then
		state=stale
	fi

	if [ "$state" = clean ] && [ "$SHOW_ALL" -eq 0 ]; then
		continue
	fi

	emit "$name" "$branch" "$def" "$ahead" "$behind" "$dirty" "$state" "$repo"
done
