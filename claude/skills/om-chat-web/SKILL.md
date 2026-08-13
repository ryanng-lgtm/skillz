---
name: om-chat-web
description: Drive the OM Chat GUI in a real browser with a logged-in session, and prove UI changes landed by diffing the cloud deployment against the local daemon into a self-contained before/after HTML report. Use when asked to verify a chat UI change visually, compare cloud vs local, screenshot the chat app, send or read a DM through the real UI, or check whether the local daemon is actually serving the working tree. Trigger: /om-chat-web.
user-invocable: true
---

# om-chat-web

A browser harness for the OM Chat GUI. Works from any directory in any session —
it carries its own Playwright and never reads the project's `node_modules`.

```sh
node ~/.claude/skills/om-chat-web/scripts/om-chat.mjs <command> [flags]
```

## The two surfaces

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

## Commands

```sh
doctor                                   # verify the wiring; run before trusting a capture
compare --routes '#/home,#/dm/nic'       # cloud vs local into an HTML report
snap --target local --routes '#/home'    # PNGs from one surface
login   --target cloud                   # establish or refresh the saved session
whoami  --target local
people  --target cloud                   # list DM candidates
read    --to <handle> --n 20
send    --to <handle> --text "..."       # sends, then confirms it rendered
```

Flags: `--target cloud|local`, `--account prod|plus|guest`, `--viewport 1440x900`,
`--full-page`, `--headed`, `--note "what changed"`, `--out <path>`, `--open`,
`--force`, `--confirm-real`.

## Run doctor first

`compare` refuses to capture if `doctor` finds problems (override with
`--force`). This is not ceremony — a report showing "no change" is worthless if
the real cause was a stale bundle. Doctor reports:

- whether `/rooms` is serving the **vite dev proxy** (your working tree), a built
  bundle, or the placeholder shell
- whether `rooms-client` is linked, and to which checkout
- branch, commit, and dirty state of both repos, stamped into the report header

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

## Credentials

Read at runtime from `~/Library/.../Obsidian/Local/creds.md` (override with
`OM_CHAT_CREDS`), parsed by label — `prod user` is `--account prod`. Nothing is
ever written into this skill or logged. Sessions persist per account and target
under `~/.claude/state/om-chat-web/profiles/`, so login happens once; delete a
profile directory to revoke.

## Sending is guarded

`send` drives a real identity against the production backend. Any recipient that
is not one of the known throwaway accounts is refused unless `--confirm-real` is
passed. **Get the user's approval on both the recipient and the message text
before using that flag.** "Sent" is only reported after the message is observed
in the rendered thread.

## Reports

Land in `~/Library/.../Obsidian/UI Updates/` as one self-contained HTML file —
images inlined, no external requests, opens over `file://`. Each route gets
side-by-side, a drag slider, a blink toggle, and a client-side pixel-diff
heatmap. The header stamps both repos' branch and commit, so two builds of the
same code can never be silently compared.
