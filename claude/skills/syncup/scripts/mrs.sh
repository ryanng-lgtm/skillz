#!/usr/bin/env bash
#
# mrs.sh — map your open GitLab MRs to local clones and say which need a rebase.
#
# Lists your open MRs, maps each to local clones under the root (ROOT/* and
# ROOT/meta_repo/*) by origin URL, fetches the MR's branches, and prints one
# TSV row per (MR, local clone):
#   path  mr  source  target  behind  needs  worktree  local  merge_status  fetch
#
# behind    commits on origin/<target> missing from origin/<source>; "?" when
#           either branch is missing on origin (an MR from a fork, say).
# needs     rebase   behind > 0
#           restack  the target is the source of another MR in the same
#                    project that needs a rebase or restack (a stacked MR)
#           ok       up to date with its target
#           ?        behind could not be measured
# worktree  the worktree of this clone that has <source> checked out, or "-".
# local     the local <source> branch against origin/<source>: none, even,
#           ahead:N, behind:N, or diverged:B/A (B behind, A ahead); "?" when
#           origin/<source> is missing.
# fetch     ok; no-source when only the source branch is missing on origin;
#           failed means the counts come from refs that could not be
#           refreshed, so treat the row as stale, exactly like scan.sh.
#
# An MR with no local clone is printed with path "-".
#
# Usage:
#   mrs.sh [--root DIR]

set -uo pipefail

ROOT="${SYNCUP_ROOT:-$HOME/Documents/GitLab}"

usage() {
	sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
	case "$1" in
	--root)
		ROOT="$2"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		printf 'mrs.sh: unknown argument: %s\n' "$1" >&2
		exit 2
		;;
	esac
done

# Reduce any GitLab remote URL to "group/sub/project".
project_of() {
	printf '%s\n' "$1" | sed -E 's#^(git@[^:]+:|[a-z+]+://([^@/]+@)?[^/]+/)##; s#\.git$##'
}

# The worktree of repo $1 that has branch $2 checked out, or "-".
worktree_of() {
	git -C "$1" worktree list --porcelain 2>/dev/null |
		awk -v ref="branch refs/heads/$2" '
			/^worktree / { wt = substr($0, 10) }
			$0 == ref { print wt; found = 1; exit }
			END { if (!found) print "-" }
		'
}

# The local branch $2 of repo $1 against origin/$2.
local_state() {
	local repo="$1" branch="$2" counts b a
	git -C "$repo" rev-parse -q --verify "refs/heads/$branch" >/dev/null 2>&1 || {
		printf 'none\n'
		return
	}
	counts="$(git -C "$repo" rev-list --left-right --count "origin/$branch...refs/heads/$branch" 2>/dev/null)" || {
		printf '?\n'
		return
	}
	read -r b a <<<"$counts"
	if [ "$b" -eq 0 ] && [ "$a" -eq 0 ]; then
		printf 'even\n'
	elif [ "$b" -eq 0 ]; then
		printf 'ahead:%s\n' "$a"
	elif [ "$a" -eq 0 ]; then
		printf 'behind:%s\n' "$b"
	else
		printf 'diverged:%s/%s\n' "$b" "$a"
	fi
}

mrs_json="$(glab api 'merge_requests?scope=created_by_me&state=opened&per_page=100' 2>&1)" || {
	printf 'mrs.sh: glab api failed: %s\n' "$mrs_json" >&2
	printf 'mrs.sh: check auth first:  glab auth status\n' >&2
	exit 1
}

# project -> local clone paths (a project can be cloned in more than one place).
clones="$(
	for d in "$ROOT"/*/ "$ROOT"/meta_repo/*/; do
		d="${d%/}"
		[ -e "$d/.git" ] || continue
		url="$(git -C "$d" remote get-url origin 2>/dev/null)" || continue
		printf '%s\t%s\n' "$(project_of "$url")" "$d"
	done
)"

# Rows are collected first because needs=restack depends on the other MRs.
# Each row carries its project as a leading column, dropped on output.
rows="$(
	printf '%s' "$mrs_json" |
		jq -r '.[] | [(.references.full | sub("!.*$"; "")), .references.full, .source_branch, .target_branch, (.detailed_merge_status // "-")] | @tsv' |
		while IFS=$'\t' read -r project ref src tgt status; do
			paths="$(printf '%s\n' "$clones" | awk -F'\t' -v p="$project" '$1 == p { print $2 }')"
			if [ -z "$paths" ]; then
				printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$project" - "$ref" "$src" "$tgt" "?" "?" - - "$status" -
				continue
			fi
			while IFS= read -r path; do
				fetch=ok
				# </dev/null: git and ssh would otherwise swallow the rest of the MR list from stdin.
				if ! git -C "$path" fetch --quiet origin "$src" "$tgt" </dev/null >/dev/null 2>&1; then
					# A source branch missing on origin (a fork MR) is not an auth problem.
					if git -C "$path" fetch --quiet origin "$tgt" </dev/null >/dev/null 2>&1; then
						fetch=no-source
					else
						fetch=failed
					fi
				fi
				if [ "$fetch" = no-source ]; then
					behind="?"
				else
					behind="$(git -C "$path" rev-list --count "origin/$src..origin/$tgt" </dev/null 2>/dev/null)" || behind="?"
					[ -n "$behind" ] || behind="?"
				fi
				case "$behind" in
				"?") needs="?" ;;
				0) needs=ok ;;
				*) needs=rebase ;;
				esac
				if [ "$behind" = "?" ]; then
					lstate="?"
				else
					lstate="$(local_state "$path" "$src" </dev/null)"
				fi
				wt="$(worktree_of "$path" "$src" </dev/null)"
				printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$project" "$path" "$ref" "$src" "$tgt" "$behind" "$needs" "$wt" "$lstate" "$status" "$fetch"
			done <<<"$paths"
		done
)"

[ -n "$rows" ] || exit 0

# An MR whose target is rewritten in this run must be restacked onto the new
# target, even when it is 0 behind the old one. Repeat until nothing changes,
# so a stack of any depth is covered.
printf '%s\n' "$rows" | awk -F'\t' -v OFS='\t' '
	{ row[NR] = $0; n = NR }
	END {
		do {
			changed = 0
			for (i = 1; i <= n; i++) {
				split(row[i], f, "\t")
				if (f[7] == "rebase" || f[7] == "restack") moving[f[1] SUBSEP f[4]] = 1
			}
			for (i = 1; i <= n; i++) {
				split(row[i], f, "\t")
				if (f[7] != "?" && f[7] != "restack" && ((f[1] SUBSEP f[5]) in moving)) {
					f[7] = "restack"
					row[i] = f[1]
					for (j = 2; j <= 11; j++) row[i] = row[i] OFS f[j]
					changed = 1
				}
			}
		} while (changed)
		for (i = 1; i <= n; i++) {
			sub(/^[^\t]*\t/, "", row[i])
			print row[i]
		}
	}
'
