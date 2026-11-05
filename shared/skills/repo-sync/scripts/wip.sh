#!/usr/bin/env bash
#
# wip.sh — carry a worktree's uncommitted work across a rebase as one
# temporary commit, then hand it back staged and unstaged as it was.
#
# Usage:
#   wip.sh save WORKTREE
#   wip.sh restore WORKTREE
#
# save     Nothing uncommitted: prints "clean" and changes nothing.
#          Otherwise saves the staged diff and a token, both in the
#          worktree's git dir, commits everything, untracked files included,
#          as "repo-sync-wip <epoch>" with commit hooks off and the author
#          <repo-sync-wip-<epoch>@invalid>, and prints that subject. The token
#          is that subject.
# restore  HEAD is the WIP commit when its author email matches, which no
#          hook can change, or its message holds the token, which a hook run
#          by the rebase may have prefixed. Then it resets HEAD~1 --mixed,
#          which puts every change back unstaged and untracked files back
#          untracked, applies the saved diff to the index and prints
#          "restored". When the diff no longer applies (the rebase changed
#          the staged lines), it stages the files the diff touched whole
#          instead and prints "index-approximate <files>".
#          No commit has that email or token: the rebase dropped the WIP
#          commit because all of it was already upstream. Prints
#          "wip-dropped" and changes nothing.
#          Either way the saved diff and token are removed.
#
# Exits 1, changing nothing, when git fails, a rebase is in progress, nothing
# was saved, or the WIP commit is in history below HEAD. Exits 2 on bad usage.

set -uo pipefail

PREFIX=repo-sync-wip

die() {
	printf 'wip.sh: %s\n' "$1" >&2
	exit 1
}

usage() {
	sed -n '3,30p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
-h | --help)
	usage
	exit 0
	;;
save | restore) ;;
*)
	usage >&2
	exit 2
	;;
esac
[ $# -eq 2 ] || {
	usage >&2
	exit 2
}
cmd="$1"

top="$(git -C "$2" rev-parse --show-toplevel 2>/dev/null)" || die "not a git worktree: $2"
cd -- "$top" || die "cannot enter ${top}"
patch="$(git rev-parse --git-path repo-sync-index.patch)" || die "cannot resolve the git dir of ${top}"
token_file="$(git rev-parse --git-path repo-sync-wip.token)" || die "cannot resolve the git dir of ${top}"

# The author email that marks the WIP commit carrying token $1.
email_of() {
	printf '%s-%s@invalid\n' "$PREFIX" "${1#"${PREFIX} "}"
}

# HEAD is the WIP commit for token $1 and author email $2.
head_is_wip() {
	[ "$(git log -1 --format=%ae 2>/dev/null)" = "$2" ] && return 0
	case "$(git log -1 --format=%B 2>/dev/null)" in
	*"$1"*) return 0 ;;
	*) return 1 ;;
	esac
}

# Stage the saved diff exactly, hunk for hunk.
apply_index() {
	[ -s "$patch" ] || return 0
	git apply --cached --whitespace=nowarn "$patch" 2>/dev/null
}

forget() {
	rm -f -- "$patch" "$token_file"
}

# Undo a failed save: index back to what the user had staged, then stop.
unsave() {
	apply_index || printf 'wip.sh: could not restage %s exactly\n' "$patch" >&2
	forget
	die "$1"
}

save() {
	git rev-parse -q --verify HEAD >/dev/null || die "no commits yet in ${top}"
	[ -e "$token_file" ] && die "a saved WIP state is waiting in ${top}: run restore first"
	case "$(git log -1 --format=%B)" in
	*"${PREFIX} "[0-9]*) die "HEAD is a ${PREFIX} commit: run restore first" ;;
	esac
	if [ -z "$(git status --porcelain)" ]; then
		printf 'clean\n'
		return 0
	fi
	local subject email
	subject="${PREFIX} $(date +%s)"
	email="$(email_of "$subject")"
	# diff-index is plumbing: textconv, diff.context, prefixes, colour and
	# rename detection never reach the saved diff. Intent-to-add files stay
	# out of it, so they come back untracked rather than staged empty.
	if ! git diff-index -p --binary --cached --ita-invisible-in-index HEAD >"$patch" ||
		! printf '%s\n' "$subject" >"$token_file"; then
		forget
		die "cannot save the staged diff"
	fi
	# Hooks off: a prepare-commit-msg hook would rewrite the subject.
	if ! { git add -A &&
		git -c core.hooksPath=/dev/null commit -q --no-verify --no-gpg-sign \
			--author="${PREFIX} <${email}>" -m "$subject"; }; then
		git reset -q
		unsave "the WIP commit failed; nothing was committed"
	fi
	if [ "$(git log -1 --format=%s)" != "$subject" ] || [ "$(git log -1 --format=%ae)" != "$email" ]; then
		git reset -q --mixed HEAD~1
		unsave "the WIP commit's subject or author was rewritten, so it was undone; nothing was committed"
	fi
	printf '%s\n' "$subject"
}

restore() {
	if [ -d "$(git rev-parse --git-path rebase-merge)" ] ||
		[ -d "$(git rev-parse --git-path rebase-apply)" ]; then
		die "a rebase is in progress in ${top}: finish or abort it first"
	fi
	[ -s "$token_file" ] || die "no saved WIP state in ${top}"
	local token email below
	token="$(cat "$token_file")"
	email="$(email_of "$token")"
	if ! head_is_wip "$token" "$email"; then
		below="$(git log -F --author="$email" -n 1 --format=%h HEAD)"
		[ -n "$below" ] || below="$(git log -F --grep="$token" -n 1 --format=%h HEAD)"
		[ -z "$below" ] ||
			die "the WIP commit ${below} is below HEAD in ${top}: something was committed on top of it"
		forget
		printf 'wip-dropped\n'
		return 0
	fi
	git reset -q --mixed HEAD~1 || die "reset to HEAD~1 failed in ${top}"
	if apply_index; then
		forget
		printf 'restored\n'
		return 0
	fi
	# The staged lines changed under the rebase: stage each touched file whole.
	local rec path files="" tab=$'\t'
	while IFS= read -r -d '' rec; do
		path="${rec#*"${tab}"*"${tab}"}"
		git add -A -- ":(literal)${path}" 2>/dev/null
		files="${files:+${files} }${path}"
	done < <(git apply --numstat -z "$patch")
	forget
	printf 'index-approximate %s\n' "$files"
}

"$cmd"
