tests:ensure bash "$TEST_SCRIPT" "$TEST_GUI" install --frozen-lockfile
tests:assert-stdout 'install --frozen-lockfile'
tests:ensure test ! -e "$(cat "$TEST_RECORD")"
tests:ensure test -f "$TEST_USER_CONFIG/.npmrc"
tests:ensure bash "$TEST_SCRIPT" "$TEST_GUI" run build
tests:assert-stdout 'run build'
tests:ensure test ! -e "$(cat "$TEST_RECORD")"
