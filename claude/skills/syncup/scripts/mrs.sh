#!/usr/bin/env bash
#
# mrs.sh — find local clones whose open MRs (authored by you) need a rebase.
#
# Lists your open GitLab MRs, maps each to local clones under the root
# (ROOT/* and ROOT/meta_repo/*) by origin URL, fetches, and measures how far
# the MR's source branch is behind its target branch on origin.
#
# Prints one TSV row per (MR, local clone):
#   path  mr  source  target  behind  checked_out  merge_status  fetch
#
# behind is "?" when either branch is missing on origin. fetch=failed means
# behind was measured from refs that could not be refreshed — treat the row as
# stale, exactly like scan.sh. An MR with no local clone is printed with path
# "-". MRs 0 behind are omitted unless --all.
#
# Usage:
#   mrs.sh [--root DIR] [--all]

set -uo pipefail

ROOT="${SYNCUP_ROOT:-$HOME/Documents/GitLab}"
SHOW_ALL=0

usage() {
	sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
	case "$1" in
	--root)
		ROOT="$2"
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
		printf 'mrs.sh: unknown argument: %s\n' "$1" >&2
		exit 2
		;;
	esac
done

# Reduce any GitLab remote URL to "group/sub/project".
project_of() {
	printf '%s\n' "$1" | sed -E 's#^(git@[^:]+:|[a-z+]+://([^@/]+@)?[^/]+/)##; s#\.git$##'
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

printf '%s' "$mrs_json" |
	jq -r '.[] | [(.references.full | sub("!.*$"; "")), .references.full, .source_branch, .target_branch, (.detailed_merge_status // "-")] | @tsv' |
	while IFS=$'\t' read -r project ref src tgt status; do
		paths="$(printf '%s\n' "$clones" | awk -F'\t' -v p="$project" '$1 == p { print $2 }')"
		if [ -z "$paths" ]; then
			printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' - "$ref" "$src" "$tgt" "?" - "$status" -
			continue
		fi
		while IFS= read -r path; do
			fetch=ok
			# </dev/null: ssh would otherwise swallow the rest of the MR list from stdin.
			git -C "$path" fetch --quiet origin "$src" "$tgt" </dev/null >/dev/null 2>&1 || fetch=failed
			behind="$(git -C "$path" rev-list --count "origin/$src..origin/$tgt" 2>/dev/null)" || behind="?"
			[ -n "$behind" ] || behind="?"
			# A 0 from unrefreshed refs proves nothing, so only a fresh 0 is dropped.
			[ "$behind" = 0 ] && [ "$fetch" = ok ] && [ "$SHOW_ALL" -eq 0 ] && continue
			cur="$(git -C "$path" branch --show-current 2>/dev/null)"
			printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$path" "$ref" "$src" "$tgt" "$behind" "${cur:--}" "$status" "$fetch"
		done <<<"$paths"
	done
