# @file om-hosted test fixtures
# @description Isolated GUI, dummy credentials, and a Bun shim; no daemon or registry is contacted.
TEST_REAL_BUN=$(command -v bun)
TEST_GUI="$(tests:get-tmp-dir)/gui with spaces"
TEST_RECORD="$(tests:get-tmp-dir)/config-path"
mkdir -p "$TEST_GUI" "$(tests:get-tmp-dir)/bin" "$(tests:get-tmp-dir)/user-config"
printf 'NPM_READ_TOKEN=dummy-openmarket\nORANGECHARTS_NPM_READ_TOKEN=dummy-orangecharts\n' >"$TEST_GUI/.env"
export TEST_SCRIPT TEST_REAL_BUN TEST_GUI TEST_RECORD
XDG_CONFIG_HOME="$(tests:get-tmp-dir)/user-config"
export XDG_CONFIG_HOME
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
PATH="$(tests:get-tmp-dir)/bin:$PATH"
export PATH

# Only the gate tests call this fixture; no Git remote or daemon is touched.
:setup-gate() {
	OM_GUI="$(tests:get-tmp-dir)/gate gui"
	OM_MONO="$(tests:get-tmp-dir)/gate core"
	OM_TARGET="$(tests:get-tmp-dir)/om"
	export OM_GUI OM_MONO OM_TARGET
	mkdir -p "$OM_GUI/node_modules/@openmarket" "$OM_GUI/dist" "$OM_GUI/src" \
		"$OM_MONO/packages/cli/src" "$OM_MONO/packages/rooms-client/src" \
		"$OM_MONO/packages/rooms-client/dist"
	printf '{"version":"1.2.3"}\n' >"$OM_MONO/packages/cli/package.json"
	printf '{"version":"1.2.3"}\n' >"$OM_MONO/packages/rooms-client/package.json"
	printf '{"@openmarket/rooms-client":"1.2.3"}\n' >"$OM_GUI/package.json"
	printf 'VERSION = "1.2.3"\n' >"$OM_MONO/packages/rooms-client/dist/version.js"
	printf 'rooms.js?v=abc123\n' >"$OM_GUI/dist/index.html"
	touch "$OM_TARGET"
	# Exported command stubs are invoked by the child hosted script.
	# shellcheck disable=SC2329
	git() { return 0; }
	# shellcheck disable=SC2329
	curl() { return 1; }
	export -f git curl
}

:setup-glab() {
	TEST_GLAB_FIXTURE="$(tests:get-tmp-dir)/skills/om-glab/scripts/hosted.sh"
	export TEST_GLAB_FIXTURE
	local hosted
	hosted="$(tests:get-tmp-dir)/skills/om-build/scripts/hosted.sh"
	mkdir -p "$(dirname "$TEST_GLAB_FIXTURE")" "$(dirname "$hosted")"
	cp "$TEST_GLAB_SCRIPT" "$TEST_GLAB_FIXTURE"
	cat >"$hosted" <<'SHIM'
#!/usr/bin/env bash
printf 'GUI=%s\nMONO=%s\n' "$OM_GUI" "$OM_MONO"
printf 'arg=%s\n' "$@"
exit "${TEST_HOSTED_EXIT:-0}"
SHIM
}

# Full installer fixture: every process/service/network operation is local.
:setup-hosted-install() {
	:setup-gate
	TEST_INSTALL_TMP=$(realpath "$(tests:get-tmp-dir)")
	OM_INSTALL_ROOT="$TEST_INSTALL_TMP/install"
	XDG_STATE_HOME="$TEST_INSTALL_TMP/state"
	TEST_SERVICE_LOG="$TEST_INSTALL_TMP/service.log"
	TEST_GUARD_LOG="$TEST_INSTALL_TMP/guard.log"
	TEST_PYTHON=$(command -v python3)
	export TEST_INSTALL_TMP OM_INSTALL_ROOT XDG_STATE_HOME TEST_SERVICE_LOG TEST_GUARD_LOG TEST_PYTHON
	rm "$OM_TARGET"
	printf '#!/usr/bin/env bash\necho old-cli\n' >"$TEST_INSTALL_TMP/old-om"
	chmod +x "$TEST_INSTALL_TMP/old-om"
	ln -s "$TEST_INSTALL_TMP/old-om" "$OM_TARGET"
	ln -s "$TEST_INSTALL_TMP/old-om" "$TEST_INSTALL_TMP/bin/om"
	# shellcheck disable=SC2329
	uname() { echo Darwin; }
	# shellcheck disable=SC2329
	curl() {
		case "$*" in
		*healthz*) printf '{"pid":999,"version":"1.2.3"}\n' ;;
		*rooms/*) echo OM_ROOMS_GUI_DIR ;;
		*) return 0 ;;
		esac
	}
	# shellcheck disable=SC2329
	lsof() { return 0; }
	# shellcheck disable=SC2329
	sleep() { return 0; }
	# shellcheck disable=SC2329
	python3() {
		if [[ $1 != */watch-check.py ]]; then
			"$TEST_PYTHON" "$@"
			return
		fi
		printf '%s\n' "$*" >>"$TEST_GUARD_LOG"
		case "$2" in
		capture) return "${TEST_CAPTURE_EXIT:-0}" ;;
		home) printf '%s/accounts/ryan\n' "$TEST_INSTALL_TMP/root" ;;
		verify) return "${TEST_VERIFY_EXIT:-0}" ;;
		esac
	}
	# shellcheck disable=SC2329
	bun() {
		[[ $* == 'run build' ]] || return 0
		mkdir -p "$OM_MONO/packages/cli/dist"
		cat >"$OM_MONO/packages/cli/dist/om" <<'BINARY'
#!/usr/bin/env bash
if [ "$1" = --version ]; then echo 1.2.3; exit 0; fi
printf 'binary=%s root=%s account=%s args=%s\n' "$0" "${OM_HOME:-}" "${OM_ACCOUNT:-}" "$*" >>"$TEST_SERVICE_LOG"
BINARY
		chmod +x "$OM_MONO/packages/cli/dist/om"
	}
	export -f uname curl lsof sleep python3 bun
}
