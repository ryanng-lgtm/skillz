export TEST_BUN_EXIT=17
tests:eval bash "$TEST_SCRIPT" "$TEST_GUI" install --frozen-lockfile
tests:assert-exitcode 17
tests:not test -e "$(cat "$TEST_RECORD")"
