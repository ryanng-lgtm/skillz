printf '//registry.npmjs.org/:_authToken=dummy-project-token\n' >"$TEST_GUI/.npmrc"
tests:eval bash "$TEST_SCRIPT" "$TEST_GUI" install --frozen-lockfile
tests:assert-fail
tests:assert-stderr-re 'repo-local .npmrc'
tests:not test -e "$TEST_RECORD"
tests:ensure test -f "$TEST_GUI/.npmrc"
