#!/usr/bin/env bash
# @file GUI Bun commands
# @description Run Bun from the GUI root so it loads .env, with user npm configuration isolated.
# @arg $1 string GUI repository directory.
# @arg $@ string Bun command and arguments, such as install --frozen-lockfile or run build.
# @exitcode 0 Bun completed successfully.
# @exitcode 1 Configuration could not be prepared.
# @exitcode 2 Required arguments are missing.

set -uo pipefail

:cleanup() {
	rm -rf -- "$registry_config_dir"
}

:main() (
	local registry_config_dir
	if [ "$#" -lt 2 ]; then
		printf 'Usage: gui-bun.sh GUI_DIRECTORY BUN_COMMAND [ARGUMENTS...]\n' >&2
		return 2
	fi
	cd "$1" || return 1
	shift
	# Bun 1.3.14 lets a registry-wide npmrc token override bunfig scope tokens.
	# XDG isolation covers user config; refuse a conflicting project config.
	if [ -f .npmrc ] && grep -Eq '^[[:space:]]*//registry\.npmjs\.org/:[[:space:]]*(_authToken|_auth|username|_password)[[:space:]]*=' .npmrc; then
		printf 'GUI repo-local .npmrc overrides scope credentials; remove its npmjs.org auth entry and use the tokens in .env.\n' >&2
		return 1
	fi
	registry_config_dir=$(mktemp -d) || return 1
	trap :cleanup EXIT
	trap 'exit 130' INT
	trap 'exit 143' TERM
	XDG_CONFIG_HOME="$registry_config_dir" bun "$@"
)

:main "$@"
