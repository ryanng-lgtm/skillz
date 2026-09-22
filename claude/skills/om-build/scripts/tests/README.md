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
