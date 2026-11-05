# @file failed restart check test
# @description A failed watch or bot check returns a failure instead of a successful install result.
:setup-hosted-install
export TEST_VERIFY_EXIT=1
tests:not tests:ensure bash "$TEST_HOSTED_SCRIPT" --no-gui --force
tests:assert-stderr 'watch/bot continuity check failed'
tests:assert-stderr 'No watches were re-armed or replayed'
