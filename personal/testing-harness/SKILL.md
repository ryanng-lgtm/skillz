---
name: testing-harness
description: >-
  Use when a change has to be proven in the running OM Chat GUI rather than in
  tests: a cloud-versus-local visual diff, a route screenshot, a DM sent or
  read through the real UI, checking the daemon serves the working tree, or a
  one-off browser probe or journey. Trigger: /testing-harness,
  $testing-harness.
user-invocable: true
---

# testing-harness — prove a change landed in the running product through a real browser

## Overview

The browser rig for proving a change landed in the running product. It spawns a
real Chromium against a real `om` build with a real logged-in session, so it
carries its own Playwright and its own saved profiles and never reads the
project's `node_modules`.

**Scope today: the OM Chat GUI** — the cloud deployment and the local daemon's
`/rooms`. Everything below is specific to those two surfaces.

**Core principle: everything downstream is a claim about which code was running — verify the wiring before trusting any verdict.**

```sh
node ~/.claude/skills/testing-harness/scripts/om-chat.mjs <command> [flags]
```

## The mode

`--parity-check` answers *did the UI change land, and only where I meant it
to?* It compares the cloud deployment (before) against the local daemon
(after), visually. It runs as the `compare` command (see below); the flag name
is not built yet, and it is a rename, not new behavior.

A visual diff says nothing about console errors, failed requests or a broken
flow. For those, use an ad-hoc probe and say the result came from a probe.

## Procedure

### 1. Run doctor first

```sh
doctor            # verify the wiring before trusting any verdict
```

`--parity-check` refuses to capture if doctor finds problems (override with
`--force`). This is not ceremony — a report showing "no change" is worthless if
the real cause was a stale bundle or the wrong daemon. Doctor reports:

- whether `/rooms` is serving the **vite dev proxy** (your working tree), a built
  bundle, or the placeholder shell
- whether `rooms-client` is linked, and to which checkout
- branch, commit, and dirty state of both repos, stamped into the report header

Doctor is also the right first move before a probe, for the same reason:
everything downstream is a claim about which code was running.

### 2. `--parity-check`

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

### 3. Ad-hoc probes

A probe answers one question once against a live, already-logged-in page, then
gets thrown away. Reach for one when the question is about the DOM or the
runtime rather than about a rendered route: does this element exist, what
`data-` attributes did the component ship, what does the console log on mount,
does the websocket reconnect after an offline flip. Injecting temporary debug
logging into the page to capture data a probe can't otherwise reach is a
supported technique, not a hack.

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
defaults, or an output format, the question is repeatable: stop and propose it
as an `om-chat.mjs` command instead.

#### Selectors that are known-good

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

#### Journey rules

These govern any hand-written journey probe:

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

## Rules

`send` drives a real identity against the production backend. Any recipient that
is not one of the known throwaway accounts is refused unless `--confirm-real` is
passed. **Get the user's approval on both the recipient and the message text
before using that flag.** "Sent" is only reported after the message is observed
in the rendered thread.

A probe or a journey bypasses that guard entirely — it is raw Playwright against
a logged-in production session. The same approval rule applies to anything a
probe or a journey posts, reacts to, or deletes.

## Common mistakes

- **Setting `OM_ROOMS_GUI_DEV_URL` on a compiled binary.** The dev proxy dies on a compiled binary. It is triple-gated
  (`runner/http/proxy/rooms-gui-dev.ts`) and gate 1 is `isDevExecPath()` — running
  from source under `bun`. Run `./packages/cli/dist/om` and `OM_ROOMS_GUI_DEV_URL`
  is silently ignored, leaving the placeholder shell at `/rooms` unless
  `OM_ROOMS_GUI_DIR` is set. Doctor catches this.
- **Capturing the wrong daemon.** Two daemons, two ports. `31417` is the usual source-run rig; the installed
  daemon listens on `31337`. Capturing the wrong one is the quiet way to "prove" a
  change that is not there — set `OM_CHAT_LOCAL_PORT` to whichever daemon is
  actually serving the branch under test. Note that two daemons sharing one
  `OM_HOME` share one database and one credential store, so a second daemon needs
  its own isolated home.
- **Relinking rooms-client to a stale checkout.** Only `openmarket-internal` is live. The `openmarket` and `openmarket-main`
  checkouts of the same remote are stale, and `tools/link-rooms-client.ts` defaults
  to exactly those two. Always relink with
  `OM_REPO=~/Documents/GitLab/openmarket-internal bun run rooms-client:link`.

## Utility verbs

Not modes — tools that `--parity-check` and probes use, and useful on their own.

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

## What this rig does NOT duplicate

The GUI repo already has 622 `bun test` files (unit and component) and a
Playwright **visual** suite (`bun run test:visual`, `tools/visual/*.visual.ts`).
That visual suite renders hand-built static fixtures — `shell-fixture.html`,
`settings-fixture.html` — against a bare vite server on `:8097`. It never touches
the daemon, the real backend, or a logged-in session.

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
inherit it. Delete a profile directory to revoke. A profile under the legacy
`~/.claude/state/om-chat-web/` path is honoured as a fallback.

## Environment

| Variable | Default | What it moves |
| --- | --- | --- |
| `OM_CHAT_LOCAL_PORT` | `31417` | which daemon `--target local` hits |
| `OM_CHAT_STATE` | `~/.claude/state/testing-harness` | profiles, baselines, runs |
| `OM_CHAT_CREDS` | the Obsidian `Local/creds.md` | credential file |
| `OM_CHAT_REPORTS` | the Obsidian `UI Updates/` | where `--parity-check` writes |
| `OM_CHAT_REPO` | `~/Documents/GitLab/openmarket-chat` | GUI checkout stamped into reports |
| `OM_REPO` | `~/Documents/GitLab/openmarket-internal` | daemon checkout stamped into reports |
