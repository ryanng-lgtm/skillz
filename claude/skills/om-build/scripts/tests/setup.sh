# @file om-hosted test fixtures
# @description Isolated GUI, dummy credentials, and a Bun shim; no daemon or registry is contacted.
TEST_REAL_BUN=$(command -v bun)
TEST_GUI="$(tests:get-tmp-dir)/gui with spaces"
TEST_RECORD="$(tests:get-tmp-dir)/config-path"
mkdir -p "$TEST_GUI" "$(tests:get-tmp-dir)/bin" "$(tests:get-tmp-dir)/user-config"
printf 'NPM_READ_TOKEN=dummy-openmarket\nORANGECHARTS_NPM_READ_TOKEN=dummy-orangecharts\n' >"$TEST_GUI/.env"
export TEST_SCRIPT TEST_REAL_BUN TEST_GUI TEST_RECORD
export XDG_CONFIG_HOME="$(tests:get-tmp-dir)/user-config"
export TEST_USER_CONFIG="$XDG_CONFIG_HOME"
printf '//registry.npmjs.org/:_authToken=dummy-wrong-token\n' >"$XDG_CONFIG_HOME/.npmrc"
unset NPM_READ_TOKEN ORANGECHARTS_NPM_READ_TOKEN
cat >"$(tests:get-tmp-dir)/bin/bun" <<'SHIM'
#!/usr/bin/env bash
printf '%s' "$XDG_CONFIG_HOME" >"$TEST_RECORD"
[ "$XDG_CONFIG_HOME" != "$TEST_USER_CONFIG" ] || exit 90
[ -d "$XDG_CONFIG_HOME" ] || exit 91
[ ! -e "$XDG_CONFIG_HOME/.npmrc" ] || exit 92
[ "$PWD" = "$TEST_GUI" ] || exit 93
"$TEST_REAL_BUN" -e 'if (process.env.NPM_READ_TOKEN !== "dummy-openmarket" || process.env.ORANGECHARTS_NPM_READ_TOKEN !== "dummy-orangecharts") process.exit(94)' || exit 94
printf '%s\n' "$*"
exit "${TEST_BUN_EXIT:-0}"
SHIM
chmod +x "$(tests:get-tmp-dir)/bin/bun"
export PATH="$(tests:get-tmp-dir)/bin:$PATH"
