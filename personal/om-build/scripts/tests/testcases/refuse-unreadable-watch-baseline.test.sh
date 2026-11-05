# @file unreadable baseline test
# @description An unreadable inventory stops installation before binary replacement or restart.
:setup-hosted-install
export TEST_CAPTURE_EXIT=1
tests:not tests:ensure bash "$TEST_HOSTED_SCRIPT" --no-gui --force
tests:assert-stderr "installation has not started"
tests:assert-equals "$TEST_INSTALL_TMP/old-om" "$(realpath "$OM_TARGET")"
tests:assert-test ! -e "$TEST_SERVICE_LOG"
