#!/usr/bin/env bash
#
# mrs.sh — map your open GitLab MRs and GitHub PRs to local clones and say
# which need a rebase.
#
# Lists your open MRs (glab) and PRs (gh), maps each to local clones by origin
# URL, fetches its branches, and prints one TSV row per (MR, local clone):
#   path  mr  source  target  behind  needs  worktree  local  merge_status  fetch
#
# mr        group/project!123 for a GitLab MR, owner/repo#123 for a GitHub PR.
# behind    commits on origin/<target> missing from origin/<source>; "?" when
#           either branch is missing on origin, or the MR is from a fork.
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
#           refreshed, so treat the row as stale, exactly like scan.sh;
#           fork for an MR from a fork; other-host for a clone that has the
#           MR's repo path on another host. Neither is fetched or measured.
#
# An MR is measured against a clone only when the clone's origin is the MR's
# own target repo: same path, and the host written in the URL or the one the
# ssh config resolves it to. When no clone matches on host, a clone with the
# same path on another host (an ssh host the forge's web URL never shows) gets
# a fetch=other-host row. An MR from a fork gets a fetch=fork row for each clone
# of its target repo, and is named on stderr: its source branch is not on
# origin, and a branch of that name there or locally is not the MR's. Both
# rows carry needs=?, so the branch is claimed by the MR and never synced. An
# MR with no clone at all is printed with path "-". A forge whose CLI is
# missing or not logged in is reported on stderr and skipped; the script fails
# only when no forge answered.
#
# Usage:
#   mrs.sh [--root DIR ...] [REPO_PATH ...]
#
# The local clones are the REPO_PATHs when given, else every repo directly
# under the roots. Roots come from --root, given once or more, else from
# $REPO_SYNC_ROOT, a colon-separated list. With no REPO_PATH and no root it
# asks no forge and exits 2.

set -uo pipefail

ROOTS=()
[ -n "${REPO_SYNC_ROOT:-}" ] && IFS=: read -r -a ROOTS <<<"${REPO_SYNC_ROOT}"
roots_from_args=0
PATHS=()

usage() {
	sed -n '3,36p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
	case "$1" in
	--root)
		[ $# -ge 2 ] || {
			printf 'mrs.sh: --root needs a directory\n' >&2
			exit 2
		}
		[ "$roots_from_args" = 1 ] || ROOTS=()
		roots_from_args=1
		ROOTS+=("${2%/}")
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	-*)
		printf 'mrs.sh: unknown argument: %s\n' "$1" >&2
		exit 2
		;;
	*)
		PATHS+=("${1%/}")
		shift
		;;
	esac
done

if [ "${#PATHS[@]}" -eq 0 ] && [ "${#ROOTS[@]}" -eq 0 ]; then
	printf 'mrs.sh: no clones to map: pass repo paths, or set roots with --root DIR or REPO_SYNC_ROOT\n' >&2
	exit 2
fi

# Every "host/group/sub/project" a remote URL stands for, one per line: user
# and port dropped, host lowercased. For ssh, the host written in the URL and,
# when the ssh config resolves it to another, that one too. Prints nothing for
# a local path.
keys_of() {
	local url="$1" host path real
	case "$url" in
	*://*)
		path="${url#*://}"
		host="${path%%/*}"
		path="${path#*/}"
		;;
	*/*:* | /*) return 0 ;; # a slash before the first colon: a local path, as git reads it
	*:*)
		host="${url%%:*}"
		path="${url#*:}"
		;;
	*) return 0 ;;
	esac
	host="${host##*@}"
	host="${host%%:*}"
	[ -n "$host" ] || return 0
	path="${path%/}"
	path="${path%.git}"
	host="$(printf '%s' "$host" | tr '[:upper:]' '[:lower:]')"
	printf '%s/%s\n' "$host" "$path"
	case "$url" in
	*://*) case "$url" in ssh://* | git+ssh://*) ;; *) return 0 ;; esac ;;
	esac
	real="$(ssh -G -- "$host" 2>/dev/null </dev/null | awk '$1 == "hostname" { print tolower($2); exit }')"
	[ -z "$real" ] || [ "$real" = "$host" ] || printf '%s/%s\n' "$real" "$path"
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

# Every open MR and PR as "host/project  ref  source  target  merge_status  fork",
# fork being "fork" for an MR whose source repo is not its target repo, else "-".
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
		jq -r '.[] | [
			((((.web_url // "") | [capture("^[a-z]+://(?<h>[^/:]+)")][0].h) // "" | ascii_downcase) + "/" + (.references.full | sub("!.*$"; ""))),
			.references.full, .source_branch, .target_branch, (.detailed_merge_status // "-"),
			(if .source_project_id != .target_project_id then "fork" else "-" end)
		] | @tsv'
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
				number url headRefName baseRefName mergeStateStatus isCrossRepository
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
		jq -r '.data.search.nodes[] | [
			((((.url // "") | [capture("^[a-z]+://(?<h>[^/:]+)")][0].h) // "" | ascii_downcase) + "/" + .repository.nameWithOwner),
			"\(.repository.nameWithOwner)#\(.number)", .headRefName, .baseRefName, (.mergeStateStatus // "-"),
			(if .isCrossRepository then "fork" else "-" end)
		] | @tsv'
}
# Not in a $(...): answered has to survive into this shell.
list_file="$(mktemp)"
trap 'rm -f "$list_file"' EXIT
list_gitlab >>"$list_file"
list_github >>"$list_file"
[ "$answered" = 1 ] || exit 1

# The candidate clones: the REPO_PATHs, else every repo directly under a root.
candidates() {
	local root d
	if [ "${#PATHS[@]}" -gt 0 ]; then
		printf '%s\n' "${PATHS[@]}"
		return
	fi
	for root in "${ROOTS[@]}"; do
		for d in "$root"/*/; do
			printf '%s\n' "${d%/}"
		done
	done
}

# host/project -> local clone paths (a project can be cloned in more than one
# place, and a clone can stand under two hosts).
clones="$(
	candidates | while IFS= read -r d; do
		[ -e "$d/.git" ] || continue
		url="$(git -C "$d" remote get-url origin </dev/null 2>/dev/null)" || continue
		keys_of "$url" | while IFS= read -r key; do
			printf '%s\t%s\n' "$key" "$d"
		done
	done
)"

# The clones whose key is $1, each once.
clones_on() {
	printf '%s\n' "$clones" | awk -F'\t' -v k="$1" '$1 == k && !seen[$2]++ { print $2 }'
}
# The clones whose key has the path of key $1, on any host, each once.
clones_with_path() {
	printf '%s\n' "$clones" | awk -F'\t' -v k="$1" '
		{ p = $1; sub(/^[^\/]*\//, "", p); q = k; sub(/^[^\/]*\//, "", q) }
		p == q && !seen[$2]++ { print $2 }'
}

# Rows are collected first because needs=restack depends on the other MRs.
# Each row carries its project as a leading column, dropped on output.
rows="$(
	while IFS=$'\t' read -r project ref src tgt status fork; do
		why=
		paths="$(clones_on "$project")"
		if [ -z "$paths" ]; then
			paths="$(clones_with_path "$project")"
			[ -z "$paths" ] || why=other-host
		fi
		if [ "$fork" = fork ]; then
			printf 'mrs.sh: %s is from a fork, not handled\n' "$ref" >&2
			why=fork
		fi
		if [ -z "$paths" ]; then
			printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$project" - "$ref" "$src" "$tgt" "?" "?" - - "$status" "${why:--}"
			continue
		fi
		if [ -n "$why" ]; then
			# Claim the branch for this MR so it is never synced, but fetch and measure nothing.
			while IFS= read -r path; do
				wt="$(worktree_of "$path" "$src" </dev/null)"
				printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$project" "$path" "$ref" "$src" "$tgt" "?" "?" "$wt" "?" "$status" "$why"
			done <<<"$paths"
			continue
		fi
		while IFS= read -r path; do
			fetch=ok
			# </dev/null: git and ssh would otherwise swallow the rest of the MR list from stdin.
			if ! git -C "$path" fetch --quiet origin "$src" "$tgt" </dev/null >/dev/null 2>&1; then
				# A source branch missing on origin is not an auth problem.
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
			# Leading-paren patterns: bash 3.2 misparses bare ones inside a command substitution.
			case "$behind" in
			("?") needs="?" ;;
			(0) needs=ok ;;
			(*) needs=rebase ;;
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
