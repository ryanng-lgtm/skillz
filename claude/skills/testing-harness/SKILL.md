---
name: testing-harness
description: Use when a change has to be proven in the real running product rather than in tests — visually diffing the cloud deployment against the local daemon, sweeping the running app for regressions after a change, screenshotting a route, sending or reading a DM through the real UI, checking whether the local daemon is serving the working tree, writing a one-off browser probe against a logged-in session, or walking an end-to-end journey through the GUI. Trigger: /testing-harness.
user-invocable: true
---

# testing-harness

The browser rig for proving a change landed in the running product. It spawns a
real Chromium against a real `om` build with a real logged-in session, so it
carries its own Playwright and its own saved profiles and never reads the
project's `node_modules`.

**Scope today: the OM Chat GUI** — the cloud deployment and the local daemon's
`/rooms`. Everything below is specific to those two surfaces.

```sh
node ~/.claude/skills/testing-harness/scripts/om-chat.mjs <command> [flags]
```

## The two modes

Both answer "did my change break something", from opposite directions.

| Mode | Question it answers | Compares |
| --- | --- | --- |
| `--parity-check` | *Did the UI change land, and only where I meant it to?* | cloud (before) vs local daemon (after), visually |
| `--regression` | *Did anything else quietly break?* | the running app against invariants and a recorded baseline |

Parity-check is a **visual** verdict on one intended change. Regression is a
**behavioral** verdict on everything around it — console, network, hydration,
journeys. They are complementary; a change that ships clean on both is proven.

> **Status.** `--parity-check` is live today, currently spelled `compare` (see
> below); the mode flag is a rename, not new behavior. `--regression` is
> **designed but not built** — the design of record is
> [references/regression-mode.md](references/regression-mode.md). Do not report
> a regression verdict from this skill until that mode exists; use an ad-hoc
> probe and say it was a probe.

## Run doctor first — both modes

```sh
doctor            # verify the wiring before trusting any verdict
```

`--parity-check` refuses to capture if doctor finds problems (override with
`--force`), and `--regression` inherits the same gate. This is not ceremony — a
report showing "no change", or a regression run showing "clean", is worthless if
the real cause was a stale bundle or the wrong daemon. Doctor reports:

- whether `/rooms` is serving the **vite dev proxy** (your working tree), a built
  bundle, or the placeholder shell
- whether `rooms-client` is linked, and to which checkout
- branch, commit, and dirty state of both repos, stamped into the report header

Doctor is also the right first move before a probe, for the same reason:
everything downstream is a claim about which code was running.

## `--parity-check`

The two surfaces:

| Target  | URL                                | Role                                     |
| ------- | ---------------------------------- | ---------------------------------------- |
| `cloud` | `https://openmarket.xyz/chat/#/`   | parity baseline — what `openmarket-chat-cloud` has |
| `local` | `http://127.0.0.1:31417/rooms#/`   | candidate — the daemon serving your branch |

Changes land in `openmarket-chat` first and are synced to
`openmarket-chat-cloud` afterwards, so **cloud is "before" and local is
"after"**. Both proxy to the same production rooms backend
(`ROOM_CHAT_API_URL`, `ROOMS_WS_URL` in `packages/cli/src/constants.ts`), so the
account, rooms, and messages are identical on both sides. The only variable is
the GUI build — which is what makes a pixel diff between them meaningful.

```sh
compare --routes '#/home,#/dm/nic'       # cloud vs local into an HTML report
snap --target local --routes '#/home'    # PNGs from one surface, no diff
```

The report lands in `~/Library/.../Obsidian/UI Updates/` as one self-contained
HTML file — images inlined, no external requests, opens over `file://`. Each
route gets side-by-side, a drag slider, a blink toggle, and a client-side
pixel-diff heatmap. The header stamps both repos' branch and commit, so two
builds of the same code can never be silently compared.

## `--regression`

Targeted at the latest changes rather than at one intended visual delta. Four
legs, over one shared run artifact:

| Leg | What it catches |
| --- | --- |
| **Runtime health sweep** | console errors, uncaught pageerrors, failed or unexpected network calls, websocket drops, stub/blank renders |
| **Critical journeys** | a fixed suite of real flows — hydrate, open a DM, send and confirm rendered, reload, reconnect |
| **Self-baseline diff** | drift against a run recorded on `main` and replayed on the branch |
| **Change-driven targeting** | maps the branch's diff onto which routes and journeys to exercise, so a run stays fast |

Network and console are **scraped on every leg**, not just the sweep — the
request log and the console log are part of the run artifact, so a journey that
passes while quietly firing a 500 is still a finding. Injecting temporary debug
logging into the page to capture data a probe can't otherwise reach is a
supported technique, not a hack.

Baselines and runs share one on-disk shape:

```
~/.claude/state/testing-harness/
  baselines/<branch>@<sha>/    shots/  dom.json  network.jsonl  console.jsonl  meta.json
  runs/<timestamp>/            the same, plus verdict.json
```

Full design — leg-by-leg semantics, the record/replay contract, baseline
staleness rules, and the open questions still to settle — is in
[references/regression-mode.md](references/regression-mode.md). Read it before
implementing or extending this mode.

## Utility verbs

Not modes — tools both modes use, and useful on their own.

```sh
login   --target cloud                   # establish or refresh the saved session
whoami  --target local
people  --target cloud                   # list DM candidates
read    --to <handle> --n 20
send    --to <handle> --text "..."       # sends, then confirms it rendered
```

Flags: `--target cloud|local`, `--account prod|plus|guest`, `--viewport 1440x900`,
`--full-page`, `--headed`, `--note "what changed"`, `--out <path>`, `--open`,
`--force`, `--confirm-real`.

## Ad-hoc probes

A probe answers one question once against a live, already-logged-in page, then
gets thrown away. Reach for one when the question is about the DOM or the
runtime rather than about a rendered route: does this element exist, what
`data-` attributes did the component ship, what does the console log on mount,
does the websocket reconnect after an offline flip. It is also the honest
stand-in while `--regression` does not exist yet — just say the result came from
a probe, not from a mode.

Start from the scaffold — copy it out, edit the `QUESTION` block, run it with
plain `node`:

```sh
cp ~/.claude/skills/testing-harness/scripts/probe-template.mjs /tmp/probe.mjs
node /tmp/probe.mjs
```

Two absolute paths are what make it work from anywhere, and both are already in
the template: Playwright resolved out of this skill's `node_modules`, and
`launchPersistentContext` pointed at the saved profile under
`~/.claude/state/testing-harness/profiles/<target>-<account>/`. That profile is
what `login` wrote, so the page comes up authenticated with no login step.

**Do not grow a probe into a command.** If you find yourself adding flags,
defaults, or an output format, the question was repeatable — it belongs in a
`--regression` leg instead.

### Selectors that are known-good

Read off the real components, not guessed. `om-chat.mjs` keeps the same set in
its `SEL` block; reuse from there rather than re-deriving.

| Selector | What it is |
| --- | --- |
| `textarea[data-composer-input]` | the message composer — also the "chat shell is up" signal |
| `.message-row` | one rendered message |
| `#login-identity`, `#login-password`, `#login-twofa` | the GUI's own login form (`src/components/Login.tsx`) |
| `[data-testid="rebrand-close-btn"]` | the rebrand overlay that swallows clicks on a fresh cloud profile |
| `[data-testid="profile-guest-mode-btn"]` | the chart shell's guest pill |

Wait on `textarea[data-composer-input], .message-row` rather than a fixed sleep:
the shell hydrates fast but rooms arrive over the websocket afterwards, so a
timeout tuned on a warm run goes flaky on a cold one.

### Journey rules

These govern the critical-journeys leg and any hand-written journey probe:

- **Assert the observable, not the action.** "Clicked send" proves nothing. Wait
  for the message to appear in `.message-row` — which is exactly what the `send`
  verb already does before it reports success.
- **Cross a real boundary.** A journey that never reloads, reconnects, or
  re-fetches is testing local component state, which the GUI repo's 622 unit
  tests already cover. Reload the page, or drive `context.setOffline(true)` and
  back.
- **Run it against both targets when the claim is a regression.** "Broken on
  local" is only a regression if it works on cloud; the same journey pointed at
  `https://openmarket.xyz/chat/` is the control.

## What this rig does NOT duplicate

The GUI repo already has 622 `bun test` files (unit and component) and a
Playwright **visual** suite (`bun run test:visual`, `tools/visual/*.visual.ts`).
That visual suite renders hand-built static fixtures — `shell-fixture.html`,
`settings-fixture.html` — against a bare vite server on `:8097`. It never touches
the daemon, the real backend, or a logged-in session.

`8097` is the operator's reserved dev-server port: if you run that suite here,
preflight it and never kill a process you did not start. The full reserved-port table is `## Reserved ports` in `~/.claude/CLAUDE.md`; take an assigned port, never a merely-free one.

So: appearance, contrast, and mobile-layout snapshots belong there. This rig owns
what fixtures cannot reach — real data shapes, real hydration, real wire, real
auth. A journey that would pass against a fixture belongs in the GUI repo, not
here.

## Wiring facts worth knowing

**`/rooms` resolves in a fixed order** (`packages/cli/src/dashboard/rooms-gui.ts`):
`OM_ROOMS_GUI_DEV_URL` dev proxy → `OM_ROOMS_GUI_DIR` bundle → compile-time embed
→ placeholder shell. The chat GUI is *not* built from `openmarket-internal`; the
committed `packages/cli/assets/rooms-gui/` files are stubs that only the release
workflow overwrites.

**The dev proxy dies on a compiled binary.** It is triple-gated
(`runner/http/proxy/rooms-gui-dev.ts`) and gate 1 is `isDevExecPath()` — running
from source under `bun`. Run `./packages/cli/dist/om` and `OM_ROOMS_GUI_DEV_URL`
is silently ignored, leaving the placeholder shell at `/rooms` unless
`OM_ROOMS_GUI_DIR` is set. Doctor catches this.

**Two daemons, two ports.** `31417` is the usual source-run rig; the installed
daemon listens on `31337`. Capturing the wrong one is the quiet way to "prove" a
change that is not there — set `OM_CHAT_LOCAL_PORT` to whichever daemon is
actually serving the branch under test. Note that two daemons sharing one
`OM_HOME` share one database and one credential store, so a second daemon needs
its own isolated home.

**Only `openmarket-internal` is live.** The `openmarket` and `openmarket-main`
checkouts of the same remote are stale, and `tools/link-rooms-client.ts` defaults
to exactly those two. Always relink with
`OM_REPO=~/Documents/GitLab/openmarket-internal bun run rooms-client:link`.

**Cloud login detours through the chart app.** `openmarket.xyz/chat/` bounces a
logged-out visitor to `/chart/`, login happens there, and the redirect back is
broken so the harness navigates to `/chat/` by hand. That bounce is also the
login detector. A first-time profile gets a `rebrand-dialog` overlay that
swallows clicks until dismissed.

**Local needs no login.** The daemon stamps an operator-session cookie and
injects the API key into its `/api/rooms` and `/ws/rooms` proxies.

## Credentials and profiles

Credentials are read at runtime from `~/Library/.../Obsidian/Local/creds.md`
(override with `OM_CHAT_CREDS`), parsed by label — `prod user` is
`--account prod`. Nothing is ever written into this skill or logged.

Sessions persist per account and target under
`~/.claude/state/testing-harness/profiles/`, so login happens once and probes
inherit it. Delete a profile directory to revoke. A profile still sitting at the
old `~/.claude/state/om-chat-web/` path is honoured as a fallback.

## Sending is guarded

`send` drives a real identity against the production backend. Any recipient that
is not one of the known throwaway accounts is refused unless `--confirm-real` is
passed. **Get the user's approval on both the recipient and the message text
before using that flag.** "Sent" is only reported after the message is observed
in the rendered thread.

A probe or a journey bypasses that guard entirely — it is raw Playwright against
a logged-in production session. The same approval rule applies to anything a
probe, a journey, or a regression leg posts, reacts to, or deletes.

## Environment

| Variable | Default | What it moves |
| --- | --- | --- |
| `OM_CHAT_LOCAL_PORT` | `31417` | which daemon `--target local` hits |
| `OM_CHAT_STATE` | `~/.claude/state/testing-harness` | profiles, baselines, runs |
| `OM_CHAT_CREDS` | the Obsidian `Local/creds.md` | credential file |
| `OM_CHAT_REPORTS` | the Obsidian `UI Updates/` | where `--parity-check` writes |
| `OM_CHAT_REPO` | `~/Documents/GitLab/openmarket-chat` | GUI checkout stamped into reports |
| `OM_REPO` | `~/Documents/GitLab/openmarket-internal` | daemon checkout stamped into reports |
