---
name: om-build
description: Use when an OM Chat GUI has to be built from source and put in front of Ryan — the daemon-embedded `/rooms` GUI when `om upgrade` cannot fetch a release (openmarket-releases 404s) or a local change has to reach the running daemon, the hosted `/chat/` cloud fork when it has to be built, validated, and served locally, or the OpenFloor iOS app when the simulator must show exactly the branch checked out in the openmarket-chat-app main worktree. Covers all three targets and the swap onto the live install. Trigger: /om-build [--hosted|--cloud|--mobile] [--no-gui]
---

# om-build — build an OM Chat GUI from source

Two different products live behind this skill. Pick the target before doing
anything; they share no build, no artifact shape, and no verification.

| Flag | Source repo | Artifact | Where it shows up | Touches the `om` binary |
|---|---|---|---|---|
| `--hosted` (default) | `openmarket-chat` | `assets/rooms.js` + `rooms.css` + `index.html`, embedded into `om` | `http://127.0.0.1:31337/rooms#/` | yes — recompiles and swaps it |
| `--cloud` | `openmarket-chat-cloud` | fingerprinted `assets/chat-<hash>.js` at base `/chat/` | a local server you start, at `/chat/` | never |
| `--mobile` | `openmarket-chat-app` | dev-client `.app` plus the JS bundle this worktree's Metro serves | the iPhone 17 Pro simulator | never |

Ryan's names, which read backwards if you assume "hosted" means the SaaS:
`--hosted` is the daemon **hosting** the GUI at `/rooms`; `--cloud` is the
`/chat/` fork. No flag means `--hosted`.

**Never mix them in one run.** `--cloud` never writes `~/.local/bin/om`, never
runs `om service restart`, and never stages anything into the monorepo.
`--hosted` never touches the cloud repo. `--mobile` is standalone: it touches
no monorepo, no `om` binary, no daemon, and checks no openmarket package.
`--no-gui` means nothing under `--cloud` or `--mobile`.

**Announce at start:** "Using om-build to build and install om from source"
(`--hosted`), "Using om-build to build and serve the cloud /chat/ fork"
(`--cloud`), or "Using om-build to put the checked-out branch on the simulator"
(`--mobile`).

If either fork's copy of a file in `tools/parity-manifest.json` was edited,
run `bun tools/sync-shared.ts --diff` before building. It is the only
cross-fork alarm that exists; both forks can be green while drifting.

---

## `--hosted` — daemon `/rooms` at 127.0.0.1:31337

`om upgrade` no longer works for standalone installs. It downloads from
`github.com/openmarket-xyz/openmarket-releases`
(`packages/cli/src/runner/update-check.ts:28`), that repo 404s unauthenticated,
and there is no auth path in the updater: `prodDeps().fetchBytes` / `fetchText`
(`packages/cli/src/runner/upgrade-core.ts:217-226`) are bare `fetch` calls with
no `Authorization` header, and neither module reads `GITHUB_TOKEN` / `GH_TOKEN`.
`gh auth login` does not revive it. Until the updater learns to authenticate or
the repo goes public again, a source build is the upgrade path.

The build itself is one command. The part that is easy to get wrong is the rooms
GUI: it is **not** built from the monorepo, and a plain source build serves the
placeholder shell at `/rooms` (`packages/cli/src/dashboard/rooms-gui.ts:1-32`) —
which looks exactly like the GUI broke. Steps 1, 2 and 6 reproduce locally what
`.github/workflows/release.yml:196-240` does in CI.

### Hard rules

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

A local-main build usually does **not** change the version string. Say so up
front, or the report reads as a no-op: the honest proof is the asset stamp in
step 7, not `om --version`.

**Say what you are building FROM, before you build it.** This skill compiles the
working tree, not a git ref — uncommitted edits, a feature branch, a detached
HEAD and a linked worktree all get embedded exactly as they sit on disk. Nothing
downstream records that: the `?v=` stamp is a content hash, so it moves, but it
cannot tell anyone *which branch* it came from. A build off someone's half-done
feature branch is indistinguishable from a build off `main` in every artifact
this skill produces.

Capture both repos up front and put it in the opening line and the final report:

```bash
for R in ~/Documents/GitLab/openmarket-internal ~/Documents/GitLab/openmarket-chat; do
  cd "$R" || continue
  BR=$(git rev-parse --abbrev-ref HEAD)                    # "HEAD" means detached
  [ "$BR" = HEAD ] && BR="detached@$(git rev-parse --short HEAD)"
  D=$(git status --porcelain | wc -l | tr -d ' ')
  WT=$(git rev-parse --git-common-dir)                     # differs from .git in a worktree
  [ "$WT" = .git ] && WT="" || WT=" [linked worktree]"
  UP=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo "no upstream")
  AB=$(git rev-list --left-right --count "$UP"...HEAD 2>/dev/null | awk '{print "behind "$1", ahead "$2}')
  printf '%-22s %s @ %s  %s  dirty=%s%s\n' "$(basename "$R")" "$BR" "$(git rev-parse --short HEAD)" "${AB:-$UP}" "$D" "$WT"
done
```

**State it plainly and early**, e.g.:

> Building from **openmarket-internal** `main @ 2041dae1` (clean) and
> **openmarket-chat** `main @ 20e8862f` (clean).

**Call it out loudly when it is not plain `main`, clean, and level with origin.**
Any of these belongs in the opening line *and* the final report, because the
person reading the report is otherwise entitled to assume it was `main`:

- a branch other than `main` — name it
- `dirty=N` — say how many files, and that uncommitted work is in the binary
- `ahead N` — the build contains commits that are not on origin
- `behind N` — the build is missing commits that are
- a linked worktree — say which path, since two worktrees of one repo can
  disagree and the daemon only gets the one you compiled

The two repos are independent here. Building `main` in the monorepo while the
GUI sits on a feature branch is legitimate and common — but it must be said,
because `om --version` will look like a normal release while `/rooms` serves
something that exists only on that branch.

### 0.5. The skip gate — run this before building anything

Most invocations of this skill have nothing to do. Rebuilding anyway costs a
compile, a binary swap and a daemon restart, and it re-rolls the asset stamp so
the report *looks* like work happened when nothing changed.

Six conditions. **All six clean means stop and report one line.** Any one dirty
means build, and the reason is what you say you are building for.

```bash
OM_BIN=~/.local/bin/om
MONO=~/Documents/GitLab/openmarket-internal
GUI=~/Documents/GitLab/openmarket-chat

need=0; why=""
flag() { need=1; why="${why:+$why; }$1"; }

health=$(curl -s http://127.0.0.1:31337/healthz)

# 1. the daemon is running the binary that is on disk (not a pre-swap inode)
pid=$(printf '%s' "$health" | sed -n 's/.*"pid":\([0-9]*\).*/\1/p')
if [ -z "$pid" ]; then
  flag "daemon not answering on 31337"
else
  disk=$(stat -f '%i' "$OM_BIN")
  live=$(lsof -p "$pid" 2>/dev/null | awk '$4=="txt" && $NF ~ /bin\/om/ {print $(NF-1); exit}')
  [ "$disk" = "$live" ] || flag "daemon runs inode $live, disk has $disk"
fi

# 2. version pin matches what the daemon reports
src_ver=$(grep -m1 '"version"' "$MONO/packages/cli/package.json" | grep -o '[0-9][0-9.]*')
run_ver=$(printf '%s' "$health" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
[ "$src_ver" = "$run_ver" ] || flag "daemon $run_ver, source $src_ver"

# 3. the stamp the daemon serves matches the bundle on disk
built=$(grep -o 'rooms\.js?v=[a-f0-9]*' "$GUI/dist/index.html" 2>/dev/null | head -1)
served=$(curl -s http://127.0.0.1:31337/rooms/ | grep -o 'rooms\.js?v=[a-f0-9]*' | head -1)
{ [ -n "$built" ] && [ "$built" = "$served" ]; } || flag "served $served, built $built"

# 4-6. any source newer than the artifact it produces
newer() { find "$1" -type f -newer "$2" 2>/dev/null | wc -l | tr -d ' '; }
n=$(newer "$GUI/src" "$GUI/dist/index.html");                                    [ "$n" = 0 ] || flag "$n GUI src file(s) newer than dist"
n=$(newer "$MONO/packages/rooms-client/src" "$MONO/packages/rooms-client/dist/version.js"); [ "$n" = 0 ] || flag "$n rooms-client src file(s) newer than dist"
n=$(newer "$MONO/packages/cli/src" "$OM_BIN");                                   [ "$n" = 0 ] || flag "$n packages/cli src file(s) newer than the installed binary"

[ "$need" -eq 0 ] && echo "SKIP — nothing to build" || echo "BUILD — $why"
```

**On `SKIP`, stop.** Do not build, do not stage, do not restart. Report exactly
one line and end:

> Nothing to build — daemon `<version>` (pid `<pid>`) already serving stamp
> `<stamp>`; GUI `<repo>@<sha>` and monorepo `<sha>` both clean and already
> compiled in.

That is the whole report. No tables, no per-step narration, no "checks passed"
list — there were no checks worth reporting because nothing ran.

**Why six and not two.** Version-and-stamp alone is not sufficient, and three
separate runs proved it:

- `rooms-client` `dist` and `src` can both read the same version while the
  source has moved underneath — the constant tracks releases, not content. A
  wire-contract change (`rooms-protocol.ts`) shipped stale this way.
- The GUI's own `src` can be untouched while its **dependency** moved, so the
  bundle is stale even though `find src -newer dist` says zero. Rebuilding
  `rooms-client` alone re-rolled the GUI stamp, which is the proof.
- `packages/cli/src` can move with the GUI untouched — the binary needs a
  rebuild even when `/rooms` would be byte-identical.

**Bias to building.** Every condition is cheap; a compile is not, but shipping a
GUI built against last release's protocol is worse. When a check cannot answer
(daemon down, `dist/` missing, `lsof` returns nothing), that counts as dirty.

**A `git pull` usually forces a build even when content is unchanged**, because
checkout stamps mtimes to now. That is the conservative direction and is fine —
say "source mtimes moved" rather than claiming a code change.

### 1. Build the rooms GUI bundle

Skip steps 1, 2 and 6 entirely on `--no-gui` (`/rooms` will serve the
placeholder; everything else works).

First check the protocol era matches, or the GUI is built against a different
wire contract than the daemon:

```bash
cd ~/Documents/GitLab/openmarket-chat && bun run rooms-client:status
```

**Compare the constants, not the package number.** `package.json` says `0.43.0`
on both the registry copy and the monorepo while their constants differ —
published `0.43.0` still carries `VERSION = "0.106.0"`, monorepo source carries
the current release. The package number stopped tracking the protocol era, so
`grep '"version"' package.json` is the wrong field to read. What matters:

```bash
grep VERSION ~/Documents/GitLab/openmarket-internal/packages/rooms-client/dist/version.js
```

That must match the version you are about to install. If it does not, or the
status line says `registry copy`, link the GUI to the monorepo source:

```bash
OM_REPO=~/Documents/GitLab/openmarket-internal bun run rooms-client:link
```

Stay linked. There is no "unlink once it publishes" milestone while the package
number is frozen — an unlink hands the GUI constants one or more releases behind
the daemon it talks to.

**A linked `rooms-client` does NOT rebuild itself when the monorepo moves.**
`src/version.ts` bumps on every release, so a GUI built against a stale linked
`dist/` silently carries the previous release's `VERSION` / `RUNNER_VERSION`.
Nothing warns you. Whenever the monorepo HEAD moved since the last run, check
and rebuild before building the GUI:

```bash
git -C ~/Documents/GitLab/openmarket-internal diff --stat <lastHEAD>..HEAD -- packages/rooms-client/src
cd ~/Documents/GitLab/openmarket-internal/packages/rooms-client && bun run build   # exits 2, still emits — see traps
grep VERSION dist/version.js
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

Note the `stamp-asset-versions OK: assets pinned to ?v=<stamp>` line the build
prints. That stamp is what proves the swap landed in step 7.

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
curl -s http://127.0.0.1:31999/rooms/ | grep -o 'rooms\.js?v=[a-f0-9]*'   # must match step 1's stamp

# Cleanup: kill by PID and PROVE it died. `pkill` returns before the process
# does, and a survivor keeps holding 31999 — the next run's verify then talks
# to the OLD binary and cheerfully prints "real GUI embedded". Seen in the wild.
TESTPID=$(curl -s http://127.0.0.1:31999/healthz | grep -o '"pid":[0-9]*' | cut -d: -f2)
kill $TESTPID 2>/dev/null; sleep 2
kill -0 $TESTPID 2>/dev/null && { kill -9 $TESTPID; sleep 1; }
rm -rf /tmp/om-gui-verify
pgrep -fl "om run" || echo "no strays"          # NOT "dist/om run" — that pattern
lsof -nP -iTCP:31999 -sTCP:LISTEN || echo "31999 free"   # cannot see ~/.local/bin/om
```

The stray check must match `om run`, not `dist/om run`. The narrow pattern only
sees the build-path binary, so it reports "none" while a stray standalone `om`
is still running — a narrower assurance than it sounds like.

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
curl -s http://127.0.0.1:31337/rooms/ | grep -o 'rooms\.js?v=[a-f0-9]*'
```

`/healthz` is the authoritative version check: `om --version` reports the binary
your shell resolved, which can differ from the one the supervisor is running.
(There is no `om system status` CLI verb — `system_status` is an MCP tool name.)
The served `?v=` stamp is the authoritative *GUI* check, and the only one that
moves when the version does not.

Report: **the branch and sha each repo was built from** (flagged if not clean
`main` level with origin, or a linked worktree), version before → after, the
asset stamp, which binary path was replaced, whether the GUI is embedded or
placeholder, daemon restart result, worktree state, and anything left for Ryan
(a shadowed `om` still first on PATH, a skipped GUI, a failed restart).

Also report **any daemon error line seen after the restart, and whether it
predates this build.** `om service status` shows the most recent error even
after the daemon recovered from it, so the status line alone cannot tell a
regression from a pre-existing condition. Check the log's history before
attributing anything to the swap:

```bash
grep -c "<the error text>" ~/.openmarket/runner.log     # total ever
grep "<the error text>" ~/.openmarket/runner.log | head -1   # first occurrence
```

A count that stops growing after the restart means the new version FIXED it —
worth reporting as such.

### Traps (`--hosted`)

| Symptom | Cause | Fix |
|---|---|---|
| `om --version` unchanged after install | either a different `om` is first on PATH, or local main simply never bumped the version | `which -a om`; then confirm via the `?v=` stamp, not the version |
| Ran the whole build and the stamp came out identical | nothing had changed; the skip gate (step 0.5) was not run | run it first — six conditions, all clean means stop and report one line |
| Skip gate says BUILD right after a `git pull`, with no code change | checkout rewrites mtimes to now | expected and conservative; say "source mtimes moved", not "code changed" |
| `/rooms` shows an install-instructions page | stubs were compiled in | redo steps 1-3; check the stub marker gate in step 2 |
| Daemon still on the old version | binary swapped, daemon not restarted | `om service restart` |
| `bun install` 404s in openmarket-chat | `@openmarket/rooms-client` is private on npm | link from the monorepo (`rooms-client:link`), never a different registry |
| GUI builds but behaves oddly against the daemon | rooms-client era mismatch | compare `dist/version.js` constants in step 1 — NOT the package number; link to source |
| GUI carries the previous release's version constants | linked `rooms-client` `dist/` is stale; it does not rebuild when the monorepo moves | rebuild `packages/rooms-client` before the GUI build (step 1) |
| `bun run build` in `rooms-client` exits 2 with `TS2835` | three extensionless relative imports in `src/shared/` (`attention.ts:18`, `read-state.ts:16,17`); `tsc` emits anyway | expected today — confirm `dist/` is fresh and continue |
| Several `om` processes in Activity Monitor | each Claude Code session spawns two `om mcp serve --stdio` children (one `--catalog operator`); they outlive daemon restarts | `ps -o ppid=` — parented by a `claude` PID means not a leak; only PPID 1 is a daemon |
| `Last error: ... You're reading too fast` after restart | the librarian scans rooms in a burst on startup and trips a read rate limit | pre-existing since 2026-08-09, self-resolves in ~5s; confirm `errors=[]` on the next `[schedule]` line before reporting it |
| Huge diff / 14 MB file in `git status` | staged GUI assets not restored | `git checkout packages/cli/assets/rooms-gui/` |
| `OM_ROOMS_GUI_DIR` set but the daemon ignores it | the launchd plist has no `EnvironmentVariables` key, so the supervised daemon never sees your shell's env; and the watch-and-re-read path is source-only (`setRoomsGuiHotReload(isDevExecPath())`, `rooms-routes.ts:95`) | it is a hand-run-daemon tool, not a shortcut around the embed — do the compile |
| `cannot upgrade: process.execPath is ...` from `om upgrade` | you ran the source entrypoint, not a compiled binary | expected — that guard is `upgrade-core.ts:424` |

### When to stop and hand over the runbook

This skill is tuned to one machine. Other people run these repos with different
paths, a different npm identity, no linked `rooms-client`, or no daemon at all.

**Bail out instead of debugging when any of these is true:**

- Two attempts at the same step have failed.
- The failure is not in the Traps table and is not obviously a typo.
- The environment differs from what step 0 assumes — no `~/.local/bin/om`, no
  launchd plist, repos somewhere else, a Cellar install as the only `om`.
- Anything needs a credential you do not have (the private `@openmarket` scope).

Do not keep probing. Print the runbook below, say which step failed and what the
error was, and stop. A person with the right access finishes it in ten minutes;
an agent guessing at it burns an hour and can leave a half-installed binary.

### The manual runbook — build and run the latest daemon from source

Hand this over verbatim. It assumes nothing this skill set up.

**What you need first**

- `bun` on PATH (`bun --version`).
- Both repos cloned. They are separate — the GUI is **not** in the monorepo:
  - monorepo (daemon + CLI + `rooms-client`): `openmarket-internal`
  - rooms GUI: `openmarket-chat`
- Write access to wherever `om` is installed. Never `sudo`.

If you do not know where the repos are:

```bash
find ~ -maxdepth 4 -type d -name openmarket-internal 2>/dev/null
find ~ -maxdepth 4 -type d -name openmarket-chat 2>/dev/null
```

**Set the paths once. Every step below uses them.**

```bash
export MONO=~/Documents/GitLab/openmarket-internal   # <- yours may differ
export GUI=~/Documents/GitLab/openmarket-chat
export OM_BIN="$(command -v om || echo ~/.local/bin/om)"
echo "$MONO"; echo "$GUI"; echo "$OM_BIN"
```

> If `$OM_BIN` resolves inside `/Cellar/openmarket/`, **stop.** Homebrew owns
> that file and a hand-placed binary gets clobbered on the next `brew upgrade`.
> Install to `~/.local/bin/om` instead and make sure it comes first on PATH.

**1. Get both repos current**

```bash
git -C "$MONO" status --short && git -C "$MONO" pull --ff-only
git -C "$GUI"  status --short && git -C "$GUI"  pull --ff-only
```

Commit or stash anything the status lines show before pulling.

**2. Point the GUI at the monorepo's `rooms-client`, and rebuild it**

`@openmarket/rooms-client` is private on npm. If you cannot install it, link it
from the monorepo instead — that bypasses the registry entirely:

```bash
cd "$GUI" && OM_REPO="$MONO" bun run rooms-client:link
bun run rooms-client:status          # expect: LINKED -> .../packages/rooms-client
```

A linked `rooms-client` does **not** rebuild itself when the monorepo moves, so
rebuild it by hand every time:

```bash
cd "$MONO/packages/rooms-client" && bun run build
grep VERSION dist/version.js         # must match the version you are installing
```

**3. Build the GUI bundle**

```bash
cd "$GUI"
bun install     # skip if it 404s on @openmarket/rooms-client — the link covers it
bun run build
```

Note the `assets pinned to ?v=<stamp>` line. That stamp is your proof later.
Then confirm all five embed inputs exist — a missing one means the build failed
quietly and you must not continue:

```bash
for f in dist/assets/rooms.js dist/assets/rooms.css dist/index.html dist/sw.js dist/manifest.webmanifest; do
  [ -f "$f" ] && echo "ok $f" || echo "MISSING $f"
done
```

**4. Stage the GUI into the binary's embed slots** (working tree only — never commit these)

```bash
cd "$MONO"
SLOT=packages/cli/assets/rooms-gui
cp "$GUI/dist/assets/rooms.js"  "$SLOT/rooms.js"
cp "$GUI/dist/assets/rooms.css" "$SLOT/rooms.css"
cp "$GUI/dist/index.html"       "$SLOT/index.html.txt"
bun packages/cli/scripts/pack-rooms-gui-extra.ts "$GUI/dist" "$SLOT/extra.json.txt"

grep -l "__OM_ROOMS_GUI_STUB__" "$SLOT/rooms.js" "$SLOT/extra.json.txt" \
  && echo "STILL STUBBED — stop" || echo "staged"
```

Skipping this step is the single most common mistake: the build succeeds and
`/rooms` serves an install-instructions page, which looks exactly like the GUI
broke.

**5. Compile**

```bash
cd "$MONO" && bun install && bun run build
ls -la packages/cli/dist/om && ./packages/cli/dist/om --version
```

**6. Install and restart**

```bash
mv packages/cli/dist/om "$OM_BIN"     # mv, never cp — cp truncates a running binary
om service restart
```

**7. Verify — the served stamp, not the version**

```bash
curl -s http://127.0.0.1:31337/healthz | head -c 120
curl -s http://127.0.0.1:31337/rooms/ | grep -o 'rooms\.js?v=[a-f0-9]*'
```

The stamp must equal step 3's. A local build often does **not** change
`om --version`, so the version proves nothing; the stamp is the real check.
If `/rooms` shows install instructions, step 4 did not take.

**8. Put the stubs back — always, including after a failure**

```bash
cd "$MONO"
git checkout packages/cli/assets/rooms-gui/
rm -f packages/cli/.*.bun-build
git status --short                    # must be clean
```

`extra.json.txt` alone is ~14 MB of base64. Committing it permanently bloats the
repo, and `git add -A` will happily sweep it up.

**If it still does not work**, report: which step, the exact error, `om --version`,
the served stamp, and whether `git status` is clean in both repos.

### The real fix (`--hosted` only)

This target is a workaround. The durable repair is teaching the updater to
authenticate: an `OM_GITHUB_TOKEN` → `Authorization: Bearer` header in the two
`prodDeps` fetchers plus `fetchLatestVersion`, and swapping the
latest-release redirect probe for the REST API (the redirect trick only resolves
on public repos). Mention it when this target runs more than once.

---

## `--cloud` — hosted `/chat/` fork, served locally

`openmarket-chat-cloud` is the hosted browser product at
`https://openmarket.xyz/chat/`. This target builds it, validates it, and puts it
in front of Ryan on a local port. It is **not** an upgrade path for anything and
it never goes near the daemon.

### Hard rules

- **Never deploy, push, or publish an image.** Deployment is GitOps and
  controller-owned (`docs/CLOUD_HOSTING.md`): Reflectful + ArgoCD apply
  `charts/openmarket-chat-cloud`. No manual `kubectl`, no `helm install`, no
  image push without Ryan's explicit per-instance OK.
- **Never commit `dist/`.** The cloud repo's policy forbids committing generated
  output, dependencies, credentials, or local endpoint overrides.
- **A cloud bundle can never be embedded in the daemon.** It builds at base
  `/chat/` with code-split `assets/chat-<hash>.js`; `/rooms` accepts only
  `index.html` + `assets/rooms.js` + `assets/rooms.css`, for both the embed and
  the `OM_ROOMS_GUI_DIR` loader (`rooms-gui.ts:296-303`). If Ryan wants a GUI at
  `/rooms`, that is `--hosted`. Making the cloud fork embeddable is a build-mode
  change in the cloud repo, not a flag.
- **Never add a serving API key to the gateway.** The gateway forwards the
  user's bearer token only; the market sidecar mints guest keys per user. A
  shared serving key must never exist.

### 0. Preflight

```bash
cd ~/Documents/GitLab/openmarket-chat-cloud
git status --short
git rev-parse --abbrev-ref HEAD && git log -1 --oneline
bun tools/sync-shared.ts --diff        # drift vs the openmarket-chat twin
```

`main` must stay deployable; feature work belongs on a branch.

### 1. Install and build

pnpm is the contract here, not bun — `package.json` pins
`packageManager: pnpm@10.22.0`, and `AGENTS.md` specifies a frozen install.
A `bun.lock` also exists; ignore it for installs.

```bash
pnpm install --frozen-lockfile
pnpm run build            # vite build + worker build + sw build
pnpm run check:dist       # node tools/check-dist.mjs
```

Expected: `check-dist OK: cloud artifact is fingerprinted, source-map free, and
daemon-agent free`. That check is the boundary guard — it fails if daemon-only
endpoints or `/rooms/` packaging leak into the cloud distribution.

Verify the artifact is fingerprinted and rooted at `/chat/`:

```bash
grep -o 'assets/chat-[A-Za-z0-9_-]*\.js' dist/index.html | head -3
ls dist                   # index.html, assets/, icons/, manifest.webmanifest, sw.js
```

### 2. Serve it locally

Three rigs; pick by what Ryan needs to see. All of them need a port — check
`~/WebstormProjects/PORTS.md` first if it exists (it did not as of 2026-08-12),
otherwise stay off 8097 (the repo's strict dev port) and 31337 (the daemon).

**A. Static preview of the artifact you just built** — layout, shell, visual work:

```bash
pnpm exec vite preview --port 8098 --strictPort
# open http://localhost:8098/chat/
```

`vite preview` binds `[::1]` **only**: `curl http://127.0.0.1:8098/` refuses the
connection while `localhost` works. Use `localhost`, or pass `--host 127.0.0.1`.
Deep links resolve (`/chat/rooms` → 200, SPA fallback).

No gateway is present in this rig, so `/chat/api/*`, `/chat/ws/rooms`, and
`/api/v1/auth-v2` are unproxied — login and live data will fail. That is
expected, not a regression.

**B. Dev server with proxies** — iterating on source:

```bash
pnpm run dev              # vite on 8097, strictPort, base /chat/
```

It proxies `/api/v1` → `localhost:3000` and `/chat/api/rooms` →
`localhost:3002`; those backends must be running or you get the same auth
failures as rig A.

**C. Gateway parity** — closest to production, when the nginx behavior itself is
what is in question:

```bash
docker build -t om-chat-cloud .
docker run --rm -p 8081:8080 \
  -e CHAT_SERVICE=<host:port> -e ROOMS_WS_SERVICE=<host:port> \
  -e THARAMINE_SERVICE=<host:port> -e AUTH_SERVICE=<host:port> \
  om-chat-cloud
# open http://localhost:8081/chat/
```

Only those four names are substituted into the template
(`NGINX_ENVSUBST_FILTER` in the Dockerfile); anything else in the config stays
literal. Unknown gateway paths return 404 by design.

Kill whatever you started when you are done, and say in the report that it is
gone.

### 3. Full gate before claiming the work is done

`AGENTS.md` names six, and all six are expected before "complete":

```bash
pnpm install --frozen-lockfile
pnpm run lint
pnpm run typecheck
pnpm run build
pnpm run check:dist
bun test
```

Add the chart validation when anything under `charts/` or `deploy/` changed:

```bash
helm lint charts/openmarket-chat-cloud
helm template openmarket-chat-cloud charts/openmarket-chat-cloud \
  --namespace pub --values charts/openmarket-chat-cloud/values.production.yaml
```

### 4. Report

Branch and HEAD, the entry hash from `dist/index.html`, which rigs were started
and on which ports, whether each still runs or was killed, `check:dist` and
gate results, parity drift from step 0, and anything left for Ryan. Never
report a deploy — this target does not do one.

### Traps (`--cloud`)

| Symptom | Cause | Fix |
|---|---|---|
| `curl 127.0.0.1:<port>` refuses but the log says it is serving | `vite preview` binds `[::1]` only | use `localhost`, or `--host 127.0.0.1` |
| Login fails / no rooms load in preview | rig A has no gateway; API and WS paths are unproxied | rig B with backends up, or rig C |
| `pnpm install --frozen-lockfile` complains about the pnpm version | `packageManager` pins 10.22.0; PATH pnpm may be older (9.15.9 on this box, which builds fine) | `corepack pnpm install --frozen-lockfile`, or proceed if it installs cleanly |
| Tempted to `bun install` because `bun.lock` is there | both lockfiles are committed; the build contract is pnpm | pnpm for install/lint/typecheck/build; bun only for `bun test` |
| Build output has no `rooms.js` | correct — this fork emits `assets/chat-<hash>.js` at base `/chat/` | if `/rooms` is the goal, run `--hosted` |
| Shared file changed but the twin did not move | `test/shared-parity.test.ts` only checks a fork against its own manifest | `bun tools/sync-shared.ts --diff`, then `--refresh` here and a plain sync in the twin |

---

## `--mobile` — OpenFloor iOS app on the simulator

Goal: after this runs, the simulator shows **exactly** the branch checked out in
the `openmarket-chat-app` main worktree — no other branch's JS, no stale build.

Standalone target. No monorepo, no `om` binary, no daemon, no
`@openmarket/rooms-client` check — the app consumes it as a published
dependency and this skill does not build or verify it.

The native shell and the JS come from different places, and that split is where
this goes wrong. The `.app` is compiled from `ios/`; everything a feature branch
usually changes is JS served live by Metro. So the build is cheap **and** the
exactness problem is entirely about which Metro the app is talking to.

```bash
APP=~/Gitlab/openmarket-chat-app
SIM=${OM_MOBILE_SIM:-27AA105E-752C-491F-8047-A4C23420E150}   # iPhone 17 Pro
PORT=${OM_MOBILE_PORT:-8081}
BUNDLE_ID=sh.openmarket.openfloor
```

### Hard rules

- **The main worktree is the source.** Build what is checked out there, working
  tree and all. Never check out a branch, stash, or clean to make it build.
- **Exactly one Metro, and it must be this worktree's.** Several dev servers run
  on this box (8081/8082/8083, and lane Metros on 8090+). The dev client will
  happily load another worktree's bundle onto this build, which reads as "my
  change isn't there". Own the port or stop.
- **Never target a verification device.** `OpenFloor-Template*` and
  `OpenFloor <slug>` clones belong to `$om-mobile-feature` runs; taking one
  corrupts a run in flight. `--mobile` uses Daryl's interactive simulator only.
- **`node_modules` must be a real directory.** A symlink to another worktree's
  copy makes Expo Router resolve the app root through it and boot the "Welcome
  to Expo" fallback — an app with no routes, which looks like a broken build.
- **Never rebuild native to ship a JS change.** It costs ten minutes and proves
  nothing the bundle does not already prove.

### 0. Preflight — say what you are about to ship

```bash
cd "$APP"
BR=$(git rev-parse --abbrev-ref HEAD); [ "$BR" = HEAD ] && BR="detached@$(git rev-parse --short HEAD)"
git log -1 --oneline
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
[ -L node_modules ] && echo "FATAL: node_modules is a symlink — pnpm install here first"
xcrun simctl list devices | grep -F "$SIM" || echo "FATAL: simulator $SIM not found"
```

State the branch, HEAD, and dirty count in the opening line. Uncommitted edits
ship as-is; that is intended, but it has to be said or the report is misleading.

Install dependencies only when the lockfile moved:

```bash
[ pnpm-lock.yaml -nt node_modules/.modules.yaml ] && pnpm install --frozen-lockfile
```

### 0.5. The skip gate — decide whether native has to be rebuilt

Rebuild the `.app` only when a native input changed or nothing is installed.
Everything else is a JS change and needs Metro alone.

```bash
INSTALLED=$(xcrun simctl get_app_container "$SIM" "$BUNDLE_ID" app 2>/dev/null)

need=0; why=""
flag() { need=1; why="${why:+$why; }$1"; }
[ -z "$INSTALLED" ] && flag "app not installed on this simulator"
if [ -n "$INSTALLED" ]; then
  for f in package.json pnpm-lock.yaml app.json; do
    [ "$f" -nt "$INSTALLED" ] && flag "$f newer than installed app"
  done
  n=$(find plugins ios/OpenFloor ios/Podfile ios/Podfile.lock -newer "$INSTALLED" 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" = 0 ] || flag "$n native file(s) newer than installed app"
fi
[ "$need" -eq 0 ] && echo "JS-ONLY — reuse the installed build" || echo "NATIVE REBUILD — $why"
```

`get_app_container` needs the simulator booted; boot it first if the lookup
fails for that reason rather than concluding the app is missing.

### 1. Pin one Metro on this worktree

```bash
xcrun simctl bootstatus "$SIM" -b && open -a Simulator
OWNER=$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t | head -1)
if [ -n "$OWNER" ]; then
  lsof -p "$OWNER" | awk '$4=="cwd"{print $NF}'      # must be $APP
fi
```

If the port is held by a server rooted anywhere else, stop and say so — do not
kill another session's Metro, and do not fall back to a different port silently.
Either the user frees it or you re-run with `OM_MOBILE_PORT` set.

When the port is free:

```bash
(cd "$APP" && nohup npx expo start --dev-client --port "$PORT" >/tmp/om-mobile-metro.log 2>&1 &)
until curl -sf "http://127.0.0.1:$PORT/status" >/dev/null; do sleep 2; done
```

### 2. Build native — only when the gate said so

```bash
npx expo run:ios --device "$SIM" --no-bundler
```

`--no-bundler` matters: without it `expo run:ios` starts its own Metro on 8081
and the app may bind to that one instead of the pinned server. On `JS-ONLY`,
skip this step entirely.

### 3. Bind the app to that Metro

The dev client remembers previously used servers and will reconnect to a dead or
foreign one. Always bind explicitly:

```bash
xcrun simctl openurl "$SIM" \
  "openfloor://expo-development-client/?url=http%3A%2F%2F127.0.0.1%3A$PORT"
```

iOS then shows an "Open in OpenFloor?" confirmation. Confirm it —
`agent-device press` if driving headless, otherwise ask the user to tap Open.
Bundling takes up to a minute on a cold Metro.

If the app lands on the sign-in screen, sign in with Daryl's credentials —
`security find-generic-password -a daryl@trontalgroup.com -s claude-agent-login -w`
— then allow the notifications prompt. This simulator is his, so its session is
his to restore; unlike a verification clone, the credential persists here and
the next run starts signed in.

### 4. Verify provenance before claiming anything

Three checks; all three must pass:

```bash
lsof -p "$(lsof -nP -iTCP:$PORT -sTCP:LISTEN -t | head -1)" | awk '$4=="cwd"{print $NF}'
curl -s -o /dev/null -w 'bundle bytes=%{size_download}\n' \
  "http://127.0.0.1:$PORT/.expo/.virtual-metro-entry.bundle?platform=ios&dev=true&transform.engine=hermes"
```

1. Metro's cwd is `$APP` — the bundle can only come from this worktree.
2. The bundle is **~16 MB**. Around 5 MB is the Expo "no routes" fallback, not
   the app; treat it as a failed build and check the symlink rule.
3. The simulator shows real app content — the Chats inbox, not the launcher's
   "DEVELOPMENT SERVERS" list and not "Welcome to Expo".

A screenshot of the running app is the only honest proof the branch is on
screen. Take one.

### 5. Report

Branch, HEAD, dirty count, whether native was rebuilt (and why) or the installed
build was reused, the port and simulator, and the verified bundle size. If the
branch was dirty, say that the simulator shows uncommitted work.

### Switching branches while Metro runs

A `git checkout` in the main worktree usually needs **no rebuild and no re-run
of this skill**. Metro watches the tree, rebuilds on change, and Fast Refresh
pushes the new JS into the running app. Re-run only when the checkout crosses a
native or dependency boundary — the same conditions the 0.5 gate tests:

| What the checkout changed | What is needed |
|---|---|
| any `src/**` JS/TS | nothing; Metro rebuilds, then reload if unsure |
| `pnpm-lock.yaml` / `package.json` deps | `pnpm install --frozen-lockfile`, restart Metro |
| `app.json`, `plugins/`, `ios/` | full `--mobile` run — native rebuild |

Fast Refresh is best-effort: it silently degrades to a full reload, and it does
not reliably re-run module side effects, so after a many-file branch switch do
not trust it. Make it deterministic instead — a relaunch keeps the pinned dev
server and needs no confirmation dialog:

```bash
xcrun simctl terminate "$SIM" "$BUNDLE_ID"; sleep 2
xcrun simctl launch "$SIM" "$BUNDLE_ID"
```

`agent-device metro reload` is not a substitute here: it tries an HTTP
`/reload` route this Expo server does not serve and times out.

**How to tell whether the running app is current.** Watch Metro's own log — it
prints a line per rebuild, and the module count tells you which kind:

```bash
tail -f /tmp/om-mobile-metro.log      # "iOS Bundled 1006ms … (1 module)" = incremental
```

A rebuild line stamped *after* the checkout means Metro has picked the branch
up. No line means nothing rebuilt — the app is still running the previous
branch's JS. For a positive check rather than an absence, hash the served
bundle before and after; a changed hash proves new code is being served:

```bash
curl -s "http://127.0.0.1:$PORT/.expo/.virtual-metro-entry.bundle?platform=ios&dev=true&transform.engine=hermes" | shasum -a 256
```

The bundle is always built from disk on request, so a fresh fetch reflects the
working tree even when the app on screen does not. That is the gap a relaunch
closes.

One thing a reload never fixes: persisted state written by another branch.
After a checkout that crosses a SQLite migration, wipe the app's data
(`xcrun simctl uninstall` then reinstall, or clear from the app) instead of
debugging a database the current code did not create.

### Traps (`--mobile`)

| Symptom | Cause | Fix |
|---|---|---|
| App runs but the change is missing | bound to another worktree's Metro | re-bind with the step 3 deep link; check Metro's cwd |
| "Welcome to Expo — create a file in src/app" | `node_modules` symlinked to another worktree; Expo Router resolves the app root through it | real `pnpm install` in this worktree, restart Metro |
| Bundle is ~5 MB | same fallback as above | never ship it; fix and re-bundle |
| Launcher shows "DEVELOPMENT SERVERS" and never loads | the deep link was not confirmed | tap Open, then wait for bundling |
| `Failed to load app from 127.0.0.1:<port>` | app raced Metro's startup | wait for `/status`, then Reload in the app |
| Rebuilds native every run | comparing against the wrong artifact, or `ios/build` churn | the gate compares against the *installed* container, not DerivedData |
| Another run's device gets hijacked | targeted a template or lane clone | `--mobile` uses the interactive simulator only |
