#!/usr/bin/env bash
# @file om-hosted shell tests
# @description Test credential isolation, source-link detection and the GitLab alias using the repository vendor.bash harness.
# @exitcode 0 All tests passed.
# @exitcode 1 A test failed.

:main() {
	local root
	root=$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel) || return
	export TEST_SCRIPT="$root/claude/skills/om-build/scripts/gui-bun.sh"
	export TEST_HOSTED_SCRIPT="$root/claude/skills/om-build/scripts/hosted.sh"
	export TEST_GLAB_SCRIPT="$root/claude/skills/om-glab/scripts/hosted.sh"
	cd "$root" || return
	# shellcheck disable=SC1091
	source vendor.bash/github.com/reconquest/import.bash/import.bash
	import:use github.com/reconquest/test-runner.bash
	test-runner:set-testcases-dir claude/skills/om-build/scripts/tests/testcases
	test-runner:set-local-setup claude/skills/om-build/scripts/tests/setup.sh
	test-runner:set-local-teardown claude/skills/om-build/scripts/tests/teardown.sh
	test-runner:run "$@"
}

:main "$@"
