---
name: om-build
description: Use when the installed `om` binary is stale and `om upgrade` cannot fetch a release — the openmarket-releases repo 404s, the asset download fails, or a local source change has to reach the running daemon. Covers the GUI-embedded source build and the swap onto the live install. Trigger: /om-build [--no-gui]
---

# om-build — build `om` from source and move the running daemon onto it

`om upgrade` no longer works for standalone installs. It downloads from
`github.com/openmarket-xyz/openmarket-releases`
(`packages/cli/src/runner/update-check.ts:28`), that repo 404s unauthenticated,
and there is no auth path in the updater: `prodDeps().fetchBytes` / `fetchText`
(`packages/cli/src/runner/upgrade-core.ts:217-226`) are bare `fetch` calls with
no `Authorization` header, and neither module reads `GITHUB_TOKEN` / `GH_TOKEN`.
`gh auth login` does not revive it. Until the updater learns to authenticate or
the repo goes public again, a source build is the upgrade path.

The build itself is one command. The part that is easy to get wrong is the rooms
GUI: it is **not** built from this repo, and a plain source build serves the
placeholder shell at `/rooms` (`packages/cli/src/dashboard/rooms-gui.ts:1-32`) —
which looks exactly like the GUI broke. Steps 1, 2 and 6 reproduce locally what
`.github/workflows/release.yml:196-240` does in CI.

**Announce at start:** "Using om-build to build and install om from source."

## Hard rules

- **The staged GUI assets are never committed.** They are a working-tree
  overwrite of committed stubs. Restore them in step 6 — including when the
  build fails or the session is interrupted. `extra.json.txt` alone is ~14 MB of
  base64; committing it permanently bloats the repo.
- **Never `cp` over the live binary.** Use `mv` (rename) — atomic on POSIX, and
  the running daemon keeps its old inode until restart. `cp` truncates a file
  another process is executing.
- **Never overwrite a Homebrew install.** If the target's realpath contains
  `/Cellar/openmarket/`, brew owns that file (`detectChannel`,
  `upgrade-core.ts:99`); a hand-placed binary drifts from brew's version
  tracking and gets clobbered on the next `brew upgrade`. Install to the
  standalone path instead, or stop and ask.
- **Smoke-test before installing.** `./packages/cli/dist/om --version` must
  print the version you expect. Never swap a binary you have not run.
- **Never sudo.** A bin dir that needs root is a signal to stop and ask, not to
  escalate.

## Steps

### 0. Preflight

```bash
cd ~/Documents/GitLab/openmarket-internal
git status --short                     # note anything dirty BEFORE staging assets
git log -1 --oneline
grep '"version"' packages/cli/package.json

which -a om                            # every om on PATH; the FIRST one wins
om --version
```

Then find the binary the daemon actually runs — it is not necessarily the one
your shell resolves:

```bash
grep -A2 ProgramArguments ~/Library/LaunchAgents/xyz.openmarket.runner.plist   # macOS
```

Report the delta (installed version → source version) and which path you intend
to replace before building. Two installs on one box is normal and is the usual
cause of "I upgraded and `om --version` didn't change": on Ryan's machine
`~/.local/bin/om` is the standalone install launchd runs, and
`/opt/homebrew/bin/om` is an older Cellar install shadowed behind it.

If the target is a Cellar path, stop — see the hard rule.

### 1. Build the rooms GUI bundle

Skip steps 1, 2 and 6 entirely on `--no-gui` (`/rooms` will serve the
placeholder; everything else works).

First check the protocol era matches, or the GUI is built against a different
wire contract than the daemon:

```bash
grep '"version"' ~/Documents/GitLab/openmarket-internal/packages/rooms-client/package.json
cd ~/Documents/GitLab/openmarket-chat && bun run rooms-client:status
```

Same version → proceed. Different → link the GUI to the monorepo source instead
of the registry copy:

```bash
OM_REPO=~/Documents/GitLab/openmarket-internal bun run rooms-client:link
```

Then build:

```bash
cd ~/Documents/GitLab/openmarket-chat
bun install
bun run build
```

`bun install` needs the granular npm token in `~/.npmrc` while
`@openmarket/rooms-client` is private. If the install 404s, do not switch
registries or accounts — use the link flow above, which bypasses npm.

Verify the five files the embed slots need:

```bash
for f in dist/assets/rooms.js dist/assets/rooms.css dist/index.html dist/sw.js dist/manifest.webmanifest; do
  [ -f "$f" ] && echo "ok $f" || echo "MISSING $f"
done
```

Any `MISSING` means the GUI build failed silently — fix it there, do not
continue with a partial bundle.

### 2. Stage the bundle into the embed slots

Working-tree only. Order matters: the embed is resolved at compile time, so this
must happen before step 3.

```bash
cd ~/Documents/GitLab/openmarket-internal
GUI=~/Documents/GitLab/openmarket-chat/dist
SLOT=packages/cli/assets/rooms-gui

cp "$GUI/assets/rooms.js"  "$SLOT/rooms.js"
cp "$GUI/assets/rooms.css" "$SLOT/rooms.css"
cp "$GUI/index.html"       "$SLOT/index.html.txt"
bun packages/cli/scripts/pack-rooms-gui-extra.ts "$GUI" "$SLOT/extra.json.txt"
```

`index.html` lands as `index.html.txt` because Bun types `*.html` text imports
as `HTMLBundle`. Everything else in `dist/` (service worker, manifest, icons,
fonts, lazy chunks) packs into the one extras slot — ~137 files today — so new
GUI assets never need a new slot.

Gate on the stub marker being gone:

```bash
grep -l "__OM_ROOMS_GUI_STUB__" "$SLOT/rooms.js" "$SLOT/extra.json.txt" && echo "STILL STUBBED — stop" || echo "staged"
```

While that marker is present, `embeddedRoomsGuiAssets()` returns null and the
daemon serves the placeholder no matter what you compile.

### 3. Compile

```bash
cd ~/Documents/GitLab/openmarket-internal
bun install
bun run build          # prebuild builds apps/dashboard, then compiles -> packages/cli/dist/om
```

### 4. Smoke-test the artifact

```bash
ls -la packages/cli/dist/om
./packages/cli/dist/om --version
```

A GUI-embedded binary is noticeably larger than a plain source build (~112 MB
vs ~92 MB). If you want proof rather than inference, boot it in isolation — this
touches neither the live daemon nor `~/.openmarket`:

```bash
OM_HOME=/tmp/om-gui-verify OM_BIND=127.0.0.1:31999 ./packages/cli/dist/om run &
sleep 8
curl -s http://127.0.0.1:31999/rooms/ | grep -q OM_ROOMS_GUI_DIR \
  && echo "PLACEHOLDER — the embed did not take" || echo "real GUI embedded"
pkill -f "dist/om run"; rm -rf /tmp/om-gui-verify
```

### 5. Install and restart

```bash
mv packages/cli/dist/om ~/.local/bin/om      # or whatever step 0 identified
om service restart
om --version && om service status
```

`mv` across filesystems is not atomic — keep source and destination on the same
volume (both under `$HOME` is fine). The daemon must be restarted explicitly:
a new binary with a still-running old daemon is the half-upgraded state that
reads as a failed upgrade.

### 6. Restore the stubs — always

```bash
cd ~/Documents/GitLab/openmarket-internal
git checkout packages/cli/assets/rooms-gui/
rm -f packages/cli/.*.bun-build
git status --short          # must match what step 0 recorded
```

`bun build --compile` leaves a `packages/cli/.<hash>-00000000.bun-build` temp
file that is not in `.gitignore`, so it shows up as untracked and rides along in
any `git add -A`.

### 7. Verify and report

```bash
om --version
om service status
curl -s http://127.0.0.1:31337/healthz | head -c 200      # the DAEMON's version, not the CLI's
curl -s http://127.0.0.1:31337/rooms/ | grep -q OM_ROOMS_GUI_DIR \
  && echo "live daemon serving PLACEHOLDER" || echo "live daemon serving real GUI"
```

`/healthz` is the authoritative check: `om --version` reports the binary your
shell resolved, which can differ from the one the supervisor is running.
(There is no `om system status` CLI verb — `system_status` is an MCP tool name.)

Report: version before → after, which binary path was replaced, whether the GUI
is embedded or placeholder, daemon restart result, worktree state, and anything
left for Ryan (a shadowed `om` still first on PATH, a skipped GUI, a failed
restart).

## Traps

| Symptom | Cause | Fix |
|---|---|---|
| `om --version` unchanged after install | a different `om` is first on PATH | `which -a om`; replace the one that wins, or fix PATH order |
| `/rooms` shows an install-instructions page | stubs were compiled in | redo steps 1-3; check the stub marker gate in step 2 |
| Daemon still on the old version | binary swapped, daemon not restarted | `om service restart` |
| `bun install` 404s in openmarket-chat | `@openmarket/rooms-client` is private on npm | link from the monorepo (`rooms-client:link`), never a different registry |
| GUI builds but behaves oddly against the daemon | rooms-client era mismatch | compare versions in step 1; link to source |
| Huge diff / 14 MB file in `git status` | staged GUI assets not restored | `git checkout packages/cli/assets/rooms-gui/` |
| `cannot upgrade: process.execPath is ...` from `om upgrade` | you ran the source entrypoint, not a compiled binary | expected — that guard is `upgrade-core.ts:424` |

## The real fix

This skill is a workaround. The durable repair is teaching the updater to
authenticate: an `OM_GITHUB_TOKEN` → `Authorization: Bearer` header in the two
`prodDeps` fetchers plus `fetchLatestVersion`, and swapping the
latest-release redirect probe for the REST API (the redirect trick only resolves
on public repos). Mention it when this skill runs more than once.
