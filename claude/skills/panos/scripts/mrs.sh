#!/usr/bin/env bash
#
# mrs.sh — map your open GitLab MRs to the local worktree that has each MR's
# source branch checked out.
#
# With no REF, lists every open MR you created, most recently updated first.
# REF is project!iid (quote it: 'tsdb-gateway!2402'), group/project!iid, or an
# MR URL. A REF that is not one of your open MRs is reported on stderr.
#
# Prints one TSV row per MR:
#   ref  pid  iid  draft  source  target  head  behind  others  clone  path  local  fetch
#
# head is the MR's full head SHA on GitLab. behind counts commits on
# origin/target that origin/source lacks. others counts human notes on the MR
# by anyone but you. clone is a local clone of the project under ROOT/* or
# ROOT/meta_repo/*; path is the worktree of that clone with the source branch
# checked out; "-" when there is none. local compares that worktree's HEAD
# with origin/source: same, ahead N, behind N, diverged or unknown, with
# "+dirty" for uncommitted changes. fetch=failed means behind and local were
# measured from refs that could not be refreshed.
#
# Usage:
#   mrs.sh [--root DIR] [REF ...]

set -uo pipefail

ROOT="${PANOS_ROOT:-$HOME/Documents/GitLab}"
REFS=()

usage() {
	sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
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
	-*)
		printf 'mrs.sh: unknown flag: %s (pass only MR refs)\n' "$1" >&2
		exit 2
		;;
	*)
		# An MR URL becomes group/project!iid.
		REFS+=("$(printf '%s\n' "$1" | sed -E 's#^https?://[^/]+/##; s#/-/merge_requests/([0-9]+).*$#!\1#')")
		shift
		;;
	esac
done

# Reduce any GitLab remote URL to "group/sub/project".
project_of() {
	printf '%s\n' "$1" | sed -E 's#^(git@[^:]+:|[a-z+]+://([^@/]+@)?[^/]+/)##; s#\.git$##'
}

me="$(glab api user 2>/dev/null | jq -r '.username')"
[ -n "$me" ] && [ "$me" != null ] || {
	printf 'mrs.sh: glab api failed; check auth first:  glab auth status\n' >&2
	exit 1
}

mrs_json="$(glab api 'merge_requests?scope=created_by_me&state=opened&order_by=updated_at&per_page=100' 2>&1)" || {
	printf 'mrs.sh: glab api failed: %s\n' "$mrs_json" >&2
	exit 1
}

refs_json="$(printf '%s\n' "${REFS[@]+"${REFS[@]}"}" | jq -R . | jq -s 'map(select(. != ""))')"

for ref in "${REFS[@]+"${REFS[@]}"}"; do
	printf '%s' "$mrs_json" | jq -e --arg r "$ref" \
		'any(.[]; .references.full == $r or (.references.full | endswith("/" + $r)))' >/dev/null ||
		printf 'mrs.sh: %s is not one of your open MRs\n' "$ref" >&2
done

# An unlistable root would report every MR as having no worktree.
ls "$ROOT" >/dev/null 2>&1 || {
	printf 'mrs.sh: cannot list %s (macOS Files and Folders access for this terminal?)\n' "$ROOT" >&2
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

# worktree_for CLONE BRANCH — print the worktree of CLONE with BRANCH checked out.
worktree_for() {
	git -C "$1" worktree list --porcelain 2>/dev/null |
		awk -v b="refs/heads/$2" '/^worktree /{p=substr($0, 10)} $0 == "branch " b {print p; exit}'
}

printf '%s' "$mrs_json" |
	jq -r --argjson refs "$refs_json" '
		.[]
		| .references.full as $full
		| select(($refs | length) == 0 or any($refs[]; . as $r | $full == $r or ($full | endswith("/" + $r))))
		| [$full, ($full | sub("!.*$"; "")), .project_id, .iid, .draft, .source_branch, .target_branch, .sha]
		| @tsv' |
	while IFS=$'\t' read -r ref project pid iid draft src tgt head; do
		others="$(glab api "projects/$pid/merge_requests/$iid/notes?per_page=100" 2>/dev/null |
			jq --arg me "$me" '[.[] | select(.system | not) | select(.author.username != $me)] | length' 2>/dev/null)"

		# Prefer the clone that has the source branch checked out somewhere.
		clone=- path=-
		while IFS= read -r c; do
			[ -n "$c" ] || continue
			[ "$clone" = - ] && clone="$c"
			p="$(worktree_for "$c" "$src")"
			if [ -n "$p" ]; then
				clone="$c" path="$p"
				break
			fi
		done <<<"$(printf '%s\n' "$clones" | awk -F'\t' -v p="$project" '$1 == p { print $2 }')"

		behind="?" local_state=- fetch=-
		if [ "$clone" != - ]; then
			fetch=ok
			# </dev/null: ssh would otherwise swallow the rest of the MR list from stdin.
			git -C "$clone" fetch --quiet origin "$src" "$tgt" </dev/null >/dev/null 2>&1 || fetch=failed
			behind="$(git -C "$clone" rev-list --count "origin/$src..origin/$tgt" 2>/dev/null)" || behind="?"
			[ -n "$behind" ] || behind="?"
		fi

		if [ "$path" != - ]; then
			counts="$(git -C "$path" rev-list --left-right --count "HEAD...origin/$src" 2>/dev/null)" || counts="? ?"
			read -r ahead lag <<<"$counts"
			case "$ahead/$lag" in
			\?/*) local_state=unknown ;;
			0/0) local_state=same ;;
			0/*) local_state="behind $lag" ;;
			*/0) local_state="ahead $ahead" ;;
			*) local_state=diverged ;;
			esac
			[ -n "$(git -C "$path" status --porcelain --ignore-submodules=all 2>/dev/null)" ] && local_state="$local_state+dirty"
		fi

		printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
			"$ref" "$pid" "$iid" "$draft" "$src" "$tgt" "$head" "$behind" "${others:-?}" "$clone" "$path" "$local_state" "$fetch"
	done
