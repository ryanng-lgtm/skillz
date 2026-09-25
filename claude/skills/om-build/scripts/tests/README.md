# Hosted script tests

Requires Bun, Bash 4+, GNU coreutils, GNU sed, and GNU grep. On macOS install the GNU
utilities and place their `gnubin` directories on PATH for this test run.

The repository-root `vendor.bash/github.com/reconquest/` directory must
contain `import.bash`, `test-runner.bash`, `tests.sh`, `opts.bash`,
`types.bash`, and `coproc.bash`. These are test tooling, not runtime dependencies.

Run from the repository root:

```sh
bash claude/skills/om-build/scripts/tests/run.sh
```

Tests use dummy credentials and a Bun shim. They check automatic .env loading,
argument forwarding, isolated user configuration, failure status and cleanup,
and refusal of conflicting project credentials. They never contact a registry
or run the daemon installer.

The gate fixtures distinguish registry-store symlinks from the selected core
checkout and cover a missing link. Alias fixtures cover GitLab defaults,
explicit paths with spaces, invocation through a symlink, option forwarding
and the shared installer's exit status. Git and HTTP calls are stubbed.

The installer fixtures also cover separate launchd/PATH aliases, restarting
through the installed binary on the original account, unreadable watch
baselines, and failed post-restart checks. They install dummy executables under
the harness temporary directory through `OM_INSTALL_ROOT`; no live service runs.

Run the read-only watch/account/Discord comparison tests with:

```sh
python3 -m unittest discover -s claude/skills/om-build/scripts/tests -p 'test_*.py'
```

Before replacing a binary, the installer records the running daemon's watch
definitions as hashes under `~/.local/state/om-hosted/rebuild.*/`. A running daemon
with a readable account inventory is required for this upgrade path. It verifies
the account, version, restart, definitions, pause states, previously working watch
parts, scheduler passes and previously healthy bot connections after installation.
Existing faults are not repaired automatically. A failure leaves the receipt and
returns non-zero; it does not re-arm chains, replay signals or roll back a database.
These receipts are checks, not backups, and do not prove the next scheduled signal
or the bot's model response will succeed.
