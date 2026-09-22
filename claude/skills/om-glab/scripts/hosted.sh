#!/usr/bin/env bash
# @file GitLab OM daemon build
# @description Run the shared hosted build with the GitLab GUI. OM_GUI and OM_MONO override the default source checkouts; all arguments and the exit status pass through.

set -uo pipefail

:main() {
	local script_dir
	script_dir=$(dirname "$(realpath "${BASH_SOURCE[0]}")") || return 1
	export OM_GUI="${OM_GUI:-$HOME/Documents/GitLab/openmarket-chat-gitlab}"
	export OM_MONO="${OM_MONO:-$HOME/Documents/GitLab/openmarket-internal}"
	exec bash "$script_dir/../../om-build/scripts/hosted.sh" "$@"
}

:main "$@"
