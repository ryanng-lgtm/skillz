# @file installed binary continuity test
# @description Different launchd and PATH aliases both move to the new binary; service commands pin the account.
:setup-hosted-install
tests:ensure bash "$TEST_HOSTED_SCRIPT" --no-gui --force
tests:assert-stdout 'installed:'
tests:assert-equals "$OM_INSTALL_ROOT/1.2.3/bin/om" "$(realpath "$OM_TARGET")"
tests:assert-equals "$OM_INSTALL_ROOT/1.2.3/bin/om" "$(realpath "$TEST_INSTALL_TMP/bin/om")"
tests:ensure cat "$TEST_SERVICE_LOG"
tests:assert-stdout "binary=$OM_INSTALL_ROOT/1.2.3/bin/om root=$TEST_INSTALL_TMP/root account=ryan args=service restart"
tests:ensure cat "$TEST_GUARD_LOG"
tests:assert-stdout " --binary $OM_INSTALL_ROOT/1.2.3/bin/om"
tests:assert-stdout ' --version 1.2.3 --restarted'
