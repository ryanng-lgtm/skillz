---
name: om-build
description: Use when an OM Chat GUI has to be built from source and put in front of Ryan — the daemon-embedded `/rooms` GUI when `om upgrade` cannot fetch a release (openmarket-releases 404s) or a local change has to reach the running daemon, or the hosted `/chat/` cloud fork when it has to be built, validated, and served locally. Covers both targets and the swap onto the live install. Trigger: /om-build [--hosted|--cloud] [--no-gui]
---

# om-build — build an OM Chat GUI from source

Two different products live behind this skill. Pick the target before doing
anything; they share no build, no artifact shape, and no verification.

| Flag | Source repo | Artifact | Where it shows up | Touches the `om` binary |
|---|---|---|---|---|
| `--hosted` (default) | `openmarket-chat` | `assets/rooms.js` + `rooms.css` + `index.html`, embedded into `om` | `http://127.0.0.1:31337/rooms#/` | yes — recompiles and swaps it |
| `--cloud` | `openmarket-chat-cloud` | fingerprinted `assets/chat-<hash>.js` at base `/chat/` | a local server you start, at `/chat/` | never |

Ryan's names, which read backwards if you assume "hosted" means the SaaS:
`--hosted` is the daemon **hosting** the GUI at `/rooms`; `--cloud` is the
`/chat/` fork. No flag means `--hosted`.

**Never mix them in one run.** `--cloud` never writes `~/.local/bin/om`, never
runs `om service restart`, and never stages anything into the monorepo.
`--hosted` never touches the cloud repo. `--no-gui` means nothing under
`--cloud`.

**Announce at start:** "Using om-build to build and install om from source"
(`--hosted`) or "Using om-build to build and serve the cloud /chat/ fork"
(`--cloud`).

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

Report: version before → after, the asset stamp, which binary path was replaced,
whether the GUI is embedded or placeholder, daemon restart result, worktree
state, and anything left for Ryan (a shadowed `om` still first on PATH, a
skipped GUI, a failed restart).

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
