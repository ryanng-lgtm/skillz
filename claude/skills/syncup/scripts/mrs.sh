#!/usr/bin/env bash
#
# mrs.sh — map your open GitLab MRs and GitHub PRs to local clones and say
# which need a rebase.
#
# Lists your open MRs (glab) and PRs (gh), maps each to local clones under the
# roots (ROOT/* and ROOT/meta_repo/*) by origin URL, fetches its branches, and
# prints one TSV row per (MR, local clone):
#   path  mr  source  target  behind  needs  worktree  local  merge_status  fetch
#
# mr        group/project!123 for a GitLab MR, owner/repo#123 for a GitHub PR.
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
# An MR with no local clone is printed with path "-". A forge whose CLI is
# missing or not logged in is reported on stderr and skipped; the script fails
# only when no forge answered.
#
# Usage:
#   mrs.sh [--root DIR ...]
#
# Roots default to $SYNCUP_ROOT, a colon-separated list, else
# ~/Documents/GitLab and ~/Documents/github. --root, given once or more,
# replaces them.

set -uo pipefail

IFS=: read -r -a ROOTS <<<"${SYNCUP_ROOT:-$HOME/Documents/GitLab:$HOME/Documents/github}"
roots_from_args=0

usage() {
	sed -n '2,36p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
	case "$1" in
	--root)
		[ "$roots_from_args" = 1 ] || ROOTS=()
		roots_from_args=1
		ROOTS+=("${2%/}")
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

# Reduce any GitLab or GitHub remote URL to "group/sub/project".
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

# Every open MR and PR as "project  ref  source  target  merge_status".
answered=0
list_gitlab() {
	local json
	command -v glab >/dev/null || {
		printf 'mrs.sh: glab not installed, GitLab MRs skipped\n' >&2
		return
	}
	json="$(glab api 'merge_requests?scope=created_by_me&state=opened&per_page=100' 2>&1)" || {
		printf 'mrs.sh: glab api failed, GitLab MRs skipped: %s\n' "$json" >&2
		printf 'mrs.sh: check auth first:  glab auth status\n' >&2
		return
	}
	answered=1
	printf '%s' "$json" |
		jq -r '.[] | [(.references.full | sub("!.*$"; "")), .references.full, .source_branch, .target_branch, (.detailed_merge_status // "-")] | @tsv'
}
list_github() {
	local json
	command -v gh >/dev/null || {
		printf 'mrs.sh: gh not installed, GitHub PRs skipped\n' >&2
		return
	}
	# gh search prs has no branch fields; the GraphQL search does.
	json="$(gh api graphql -f query='query {
		search(query: "is:pr is:open author:@me archived:false", type: ISSUE, first: 100) {
			nodes { ... on PullRequest {
				number headRefName baseRefName mergeStateStatus
				repository { nameWithOwner }
			} }
		}
	}' 2>&1)" || {
		printf 'mrs.sh: gh api failed, GitHub PRs skipped: %s\n' "$json" >&2
		printf 'mrs.sh: check auth first:  gh auth status\n' >&2
		return
	}
	answered=1
	printf '%s' "$json" |
		jq -r '.data.search.nodes[] | [.repository.nameWithOwner, "\(.repository.nameWithOwner)#\(.number)", .headRefName, .baseRefName, (.mergeStateStatus // "-")] | @tsv'
}
# Not in a $(...): answered has to survive into this shell.
list_file="$(mktemp)"
trap 'rm -f "$list_file"' EXIT
list_gitlab >>"$list_file"
list_github >>"$list_file"
[ "$answered" = 1 ] || exit 1

# project -> local clone paths (a project can be cloned in more than one place).
clones="$(
	for root in "${ROOTS[@]}"; do
		for d in "$root"/*/ "$root"/meta_repo/*/; do
			d="${d%/}"
			[ -e "$d/.git" ] || continue
			url="$(git -C "$d" remote get-url origin 2>/dev/null)" || continue
			printf '%s\t%s\n' "$(project_of "$url")" "$d"
		done
	done
)"

# Rows are collected first because needs=restack depends on the other MRs.
# Each row carries its project as a leading column, dropped on output.
rows="$(
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
	done <"$list_file"
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
