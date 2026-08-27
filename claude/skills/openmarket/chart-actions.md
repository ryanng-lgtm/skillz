---
name: openmarket-chart-actions
description: Inspect and mutate the user's chart workspaces through the local OpenMarket Collab Service Bridge. Verbs live directly under `om chart` (`status`/`events` for bridge health and observed edits, `list`/`select`/`create`/`show`/`refresh`/`screenshot`/`open` for workspaces, `view`/`symbol`/`interval`/`plot-type` per-pane plus `layout`/`sync` workspace-global for chart mutations), with two grouped families, `om chart indicator` for indicator add/remove/update and `om chart drawing` for drawing add/remove. Multichart is supported on every persisting verb via `--chart <n>`. Use this skill when the user asks "is my orchestrator/bridge/daemon connected?", "what workspaces do I have?", "what's on my BTC workspace?", "what symbol / indicators / drawings are on chart N?", or asks to (a) add an indicator (RSI, MACD, EMA, BB, ATR, Stoch, Liquidations), (b) draw a trendline / fibonacci retracement between two anchor points, (c) seek / zoom / pan the visible time range, (d) change the symbol / interval / plot type / multi-chart layout, (e) toggle multi-chart sync (symbol / interval / crosshair), or (f) tune indicator settings. Read this file when invoking any `om chart ...` command.
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om chart

The Collab Service Bridge is a long-lived WebSocket from the local `om` daemon to a remote collab gateway. At boot it joins one workspace, receives a `STATE_SYNC` snapshot, caches it in-process, and stays open. The agent queries that cache (or submits mutations through the bridge) via the chart tools — `chart_status`, `chart_refresh`, `chart_symbol`, … (`om chart …` on the CLI).

Commands are grouped by **resource**, not by action verb — same pattern as `kubectl get pods`, `docker container run`, `git remote add`. Picking the right group is the agent's first job; the verbs under each group are small and consistent.

The chart is the display plane where your work turns visible. When the user asks to SEE anything (price action around an event, a support/resistance level, market structure, a comparison between symbols), express it ON the chart: set the symbol and interval, add the indicator, draw the level or zone, and confirm with `chart_screenshot` when they ask how it looks. Prefer this over ASCII sketches, text tables of candles, or describing what a chart would show. Two checks before acting: `chart_status` for the active workspace (and whether a human is watching), and the verb section the ask names (§"Panes and layout" for a grid) so a grid ask lands on `chart_layout` first.

Quick routing — the common asks, each row a recipe (tool + the decisions to make and say; the loaded tool schema owns argument shapes):

| Ask | Recipe |
| --- | --- |
| "show me BTC" / "open a chart" | `chart_create` — scratch, no name; default the market like a price ask (BTC/ETH/SOL → Binance spot, 1h); say "temporary, 48h — say keep to make it permanent". |
| "add RSI and the 200 EMA" | one `chart_indicator_add` per indicator on the active chart (omit the workspace id); defaults RSI 14, EMA 200 — state them. |
| "screenshot it" / "how does it look" | `chart_screenshot` on the active chart. |
| "2x2 with BTC, ETH, SOL, DOGE" | `chart_layout` FIRST (2x2 = mode `4`), then one `chart_symbol` per pane whose target differs; `NO_CHANGE` = done, never re-issue. |
| "mark 21,350" (a named exact level) | `chart_drawing_add`, HorizontalLine at the named price — the explicit-anchor verb is for user-named levels only. |
| "draw the fib / trendline for the swing" | `chart_drawing_auto` — anchors computed from candles; read the drawing detail file first. |
| "plot my headlines / alert fires" | `chart_pins` — its own day workspace by default, no approval; a NAMED workspace or `here` needs the user's explicit yes. |
| "what's on my chart?" | `chart_refresh` with the workspace id omitted — never answered from `chart_list`. |

**Workspace policy: frictionless, scratch by default.** A target the user NAMED is used as-is (with the consent language first); something already on screen (`here`) is painted, creating nothing. Everything else ad-hoc lands on a SCRATCH canvas: `chart_pins` mints its own fresh-or-same-view day workspace as one, and a bare fresh canvas is `chart_create` with `scratch: true` and no name (48h sliding TTL relay-side, exempt from the plan workspace count, listed only on the dim scratch shelf, zero residue when the user walks away). Never mint a NAMED workspace unless the user named it, and never promote one on your own: `chart_keep` is the user's naming act that makes a scratch permanent IN PLACE, same id, same share link; a follow never promotes anything. When a run reports a scratch mint, disclose the expiry once and name the keep verb once.

> **⚠️ Always read CURRENT state before you answer about — or act on — a chart: `chart_refresh` (a workspace the user NAMES: `chart_show`).**
>
> The user can edit the chart manually at any time. Edits made inside a **live session** (the `?live=true` view) do reach the daemon — `chart_status` flips `stateStale: true` — but edits made in the **plain chart UI** (no live session) bypass the bridge entirely: they persist straight to the workspace backend with no push, so any snapshot you hold goes stale with **no signal**. Your conversation transcript is stale in both cases.
>
> **`chart_refresh` reads fresh from the source of truth** (for a workspace the user NAMES, `chart_show` is that read — no live session needed). Run it:
> - before **answering any question** about what's on the chart (indicators, symbol, interval, drawings) — *including* before refusing ("there's no RSI") — your last read may predate a manual edit;
> - immediately before **any persisting action** whose correctness depends on current state — picking a chart by symbol, choosing an indicator/drawing `id` to update or remove, computing drawing anchors from candles.
>
> Do not reuse a prior read across turns or across a mutation — re-`refresh` each time. The cost is one ~10–100ms round-trip and it eliminates the entire "agent acted on a stale snapshot" class of bug.

> **⚠️ This applies to MUTATIONS too, not just questions.** When the user says "add RSI", "switch to SOL", "draw a trendline" without naming a workspace, OMIT the workspace id and the mutation lands on the daemon's active workspace, resolved at call time. **Never reuse a workspace id from earlier in the conversation** — the user may have switched since (via `/workspace` or `chart_workspace_select`, a switch you don't see in the transcript), so an id you "remember" can silently mutate the workspace they just left. Omit, or select first, then act.

**Never loop. NO_CHANGE and out-of-range are terminal, not retryable:**

- `No change — symbol is already 'X'` → that pane is **already correct**. Treat as done. Do NOT re-issue it.
- `chartIndex N out of range (have M charts)` → pane N **doesn't exist yet**. This means the layout step didn't run or didn't grow enough panes. Run `chart_layout` to the right mode FIRST, then set that pane **once**. Do NOT retry the `chart_symbol` against the missing pane.

If you ever find yourself issuing the same `chart_symbol` call a second time, stop — you are looping. Re-read current state with one `chart_refresh`, then act on the diff only.

NEVER call `indicator add` while trying to remove; if you lack information, use `--type`/`--every-indicator` (no id needed) or read state first.

Pane targeting on a multichart: `--chart 0` / `--chart 1` guesses misroute — identify the target pane from current state first (on the CLI, `--chart <SYMBOL>` resolves the pane by symbol; agent tools take the numeric `chartIndex` you verified).

**Events on charts are their own lane: `chart_pins`.** It plots event sources (news feeds, custom watches, price-alert fires) onto a chart's event lane as a live view; the call shape is §"Pins", and the doctrine (defaults, the one-question rule, filters, depth, workspace consent) lives in `news.md`'s "Plotting events on charts" section, so read that before plotting events. Do not confuse it with `chart_events`, the session-edit stream: that verb READS the human's and peers' recent manual chart edits and plots nothing.

**Drawing tools have their own detail file → read [`chart-actions-tool-drawing.md`](chart-actions-tool-drawing.md).**
It covers every Super Search tool (lines, shapes/ranges, fibonacci, arrows, markers, positions,
annotations), `chart_drawing_auto` (anchors computed from market data — preferred),
`chart_drawing_add` (caller-supplied role-tagged anchors), `chart_drawing_schema` (a tool's anchor
roles), and `chart_drawing_remove`. Read it before drawing, adding, or removing any chart tool.

Watching the agent drive the chart live (ghost cursor, narration) is the primary feedback loop for chart-actions. Whether the user is watching is REPORTED, not guessed: `chart_status` → `humanPresent` on the active workspace. Theater a viewer misses is NOT replayed — a late joiner only gets the end state — so seat the audience BEFORE mutating, not after.

## Single-binary setup

Daemon requirement classes per verb, the REST-floor fallback, `bridge_disabled` recovery, and what persists server-side when sharing links.

Same `om` binary as alerts. The daemon (`om run` foreground or `om service start` background) holds the bridge; the `om chart` subcommands either:

- **call the daemon's loopback HTTP** (`status`, `refresh`, `view`, `indicator add` — they require the daemon to be running),
- **call the daemon but fall back to direct gateway REST when it is down** (`symbol`, `interval`, `drawing add`, `drawing remove` — the persistent quartet: the change lands in the workspace document either way; daemon-down you lose only session extras like playback and blackboard reads), or
- **call the upstream collab gateway REST directly** (`list` — works even when the daemon is down).

Durability when relaying results: the workspace DOCUMENT (symbols, intervals, drawings, indicators, persistent backtest fill markers) is relay-stored, and the OM payload lanes (Strategy Tester panels, `chart pins` event pins, WRUN previews) are stored server-side by the platform's relay payload store — a share link renders all of it to any signed-in viewer with the user's daemon off. The store write-behind is best-effort: a running daemon re-pushes anything it missed, plus live updates, so routine URL hand-offs need no daemon-down warning.

Configuration is handled by `om init`:

- **API key** — captured during the API-key step and stored in the SQLite `settings` table.
- **Default workspace** — `om init`'s workspace picker lists workspaces the API key can access and writes the chosen id to the settings table.

Both feed the daemon at boot. Users do not need to export `OM_API_KEY` or `OM_COLLAB_WORKSPACE_ID` themselves once `om init` has run. If the daemon boots without one of these, the bridge is disabled and every command except `om chart list` returns a clear `bridge_disabled` error — surface that to the user as *"the orchestrator isn't configured for collab yet — run `om init`."*

## Status and sessions

Bridge health and presence (`om chart status`: `humanPresent`, `stateStale`), the live session edit log (`om chart events`), and the one-time alert offer on drawn levels.

| Tool (CLI) | Purpose | Requires daemon |
| --- | --- | --- |
| `chart_status` (`om chart status`) | Report peerId, every workspace WS state, pending intent count, whether STATE_SYNC is cached, session participants + `humanPresent`, and `stateStale`. | yes |
| `chart_events` (`om chart events`) | List the human's recent MANUAL chart edits observed on the live session (oldest first) — drawings placed (with time+price points), indicators added/removed, symbol/interval/layout changes. `--since <epochMs>` filters to edits after a watermark. | yes |

```jsonc
{
  "peerId": "agent:720ecfa0-79de-4328-984f-798f12ae598e",
  "workspaces": [
    {
      "workspaceId": "<workspaceId>",
      "state": "open",          // idle | connecting | open | reconnecting | closed
      "pendingIntents": 0,
      "hasStateSync": true,     // false → first STATE_SYNC hasn't landed yet
      "participants": [ { "userId": "…", "username": "openmarket", "sessionRole": "HOST" } ],
      "humanPresent": true,     // a human has the live chart open right now
      "stateStale": false,      // true → a manual edit landed after the cached snapshot
      "lastHumanEditAt": 1783300000000,     // epoch ms, absent until a manual edit is seen
      "lastHumanActivityAt": 1783300000000  // epoch ms, mouse/viewport activity on the live chart
    }
  ]
}
```

Interpretation:

| Output | Meaning |
| --- | --- |
| `state: "open"` + `hasStateSync: true` | Fully connected, safe to query state. |
| `state: "open"` + `hasStateSync: false` | Connected, STATE_SYNC pending. Retry in ~2 seconds. |
| `state: "connecting"` / `"reconnecting"` | Transient — recovers automatically. |
| `state: "closed"` | Terminal (almost always 1008 policy violation — key revoked or non-owner). |
| `workspaces: []` | Bridge disabled (missing config) or no session yet. |
| `humanPresent: true` | The user (or another person) is watching the live chart RIGHT NOW — chart actions are visible immediately; no need to push the live-view link this turn. |
| `humanPresent: false` | Nobody is watching. After a mutation, surface the live-view link so the user can open the chart. |
| `stateStale: true` | The user edited the chart manually after the last snapshot; the daemon auto-resyncs within ~2s, but run `om chart refresh` before answering anything state-dependent. |

### User asks "is my orchestrator/bridge connected?"

Call `chart_status`. Interpret as in the table above; answer in one sentence.

### The user edits the chart too — offer alerts on drawn levels

Live-session manual edits stream to the daemon. `chart_events` lists them oldest-first; each drawing event's `data.tool.points` carries exact `{ time, price }` anchors. When the user just placed a line/level tool (HorizontalLine, TrendLine, a Fib level they call out) and the conversation touches the chart, offer ONCE to arm a price alert at that level — quote the price, ask, and only create it on a yes (alerts skill). Don't propose alerts for annotation/cosmetic tools (Text, Note, arrows, emoji), and don't repeat the offer if they pass.

## Workspaces

List, select, show, refresh, open; the omitted-id active default, friendly-name → id lookup, VIEWER read-only joins, and `version` change checks.

| Tool (CLI) | Purpose | Requires daemon |
| --- | --- | --- |
| `chart_list` (`om chart list`) | List the account's workspaces: the same names and ids the user sees in the web app. Direct REST call. `mine: true` lists this agent's own housekeeping ledger instead (a subset), never the user's list. | **no** |
| `chart_workspace_select` (`om chart select`) | Make a workspace the ACTIVE chart-actions target: persists the default and repoints the live bridge (the same switch as the TUI `/workspace` command, minus its restart fallback: a failed live repoint reports the remedy and rolls the default back instead of bouncing the daemon). Accepts a short id or share-link URL. Selecting a workspace the user does not own joins it READ-ONLY (VIEWER). | yes |
| `chart_refresh` (`om chart refresh`) | Read the LIVE workspace snapshot: force a fresh `STATE_SYNC` from the gateway and print it (charts, viewport, theme, version). | yes |
| `chart_show` (`om chart show`) | Read **any** workspace's content by short id or share-link URL, WITHOUT joining a live session. Direct REST call; read-only; does not change the active workspace. | **no** |
| `chart_open` (`om chart open`) | Open the workspace's LIVE view (`?live=true`) in this machine's browser; `--wait-human <ms>` blocks until a viewer joins the session (or the wait elapses). Use before the first mutation when nobody is watching — see "Make chart actions visible" below. | for `--wait-human` |

Use `chart_list` for first-run sanity ("does the key work against the gateway?") and to resolve a user-named workspace ("my BTC playground") to its `id`.

`chart_show` is the static, no-session read: use it whenever the user points you at a SPECIFIC workspace (a short id or a `openmarket.xyz/chart/<id>` link) to look at its content or before an edit on it — it needs no live session, and `chart_refresh` on a workspace the daemon has no session for fails with a no-session error that is NOT "workspace missing". `chart_refresh` is the live read: the daemon's CURRENT active workspace with the id omitted, or a named workspace only when the user asks for its LIVE state.

Use `chart_refresh` to answer ANY question about what's currently on the active chart (`chart_show` for a workspace the user names). The `workspace.*` payload is opaque pass-through from the gateway's store — read whatever field names actually appear in the JSON; do not invent. Useful traversal:

- `workspace.charts[i]` — per-chart config (symbol, exchange, interval, plot type).
- `workspace.onchart[]` — price-axis overlays (EMA, SMA, Bollinger Bands).
- `workspace.offchart[]` — sub-pane indicators (RSI, MACD, Stochastic, ATR, Liquidations).
- `workspace.charts[i].drawings[]` (or `tools[]`) — trendlines, fibs.
- `viewport[i]` — current visible time range per chart.
- `version` — monotonic int. Use it to answer "did anything change since I last looked?".

**Naming overlays — two identity encodings; enumerate EVERY entry.** An overlay in `onchart[]`/`offchart[]` is not always identified by its `type`:

- `type: "TECHNICAL_SCRIPT"` → a TA script; its name is `settings.name` (fallback `settings.subType`) — e.g. RSI, MACD, EMA, Bollinger Bands.
- any OTHER `type` → a **native** overlay whose identity IS the `type` value and which carries **no** `settings.name` — e.g. `OPEN_INTEREST` → Open Interest, `LIQUIDATIONS` → Liquidations, `AGGREGATED_FUNDING_RATE` → funding, `PM_SIGNAL` → PolyMarket signal. Resolve the enum to a friendly name with `om chart indicator list`.

When you report what's on a chart, walk **every** `onchart[]`/`offchart[]` entry and name it by that rule — TECHNICAL_SCRIPT from `settings.name`, everything else from `type`. Never drop an entry just because it has no `settings.name`: a nameless entry is a native indicator (open interest, liquidations, funding…), not noise. Skip only entries flagged `isHidden: true`.

### User asks "what workspaces do I have?"

Call `chart_list`. Render each as `<name> (id: <id>)` if name is present, else just `<id>`. Don't dump raw JSON to the user.

If the response is empty, say so plainly: *"No workspaces under this API key."*.

### User asks "delete my workspaces" / "delete all my workspaces" / "clean up my workspaces"

Two inventories exist and only one of them is the user's:

- `chart_list` (no arguments) is the account's own list: the names the user sees in the web app. This is the list a user means.
- `chart_list` with `mine: true` is this agent's housekeeping ledger: the scratch canvases, bare-plot day charts, feed and backtest charts it minted itself. A subset, usually a small one, and never the answer to "all my workspaces".

Three steps, one list:

1. Call `chart_list` (no arguments), show the names with the count, and ask for consent over THAT list.
2. After consent, pass those ids to `chart_delete` (`targets`, up to 50 per call; batch a bigger account). Do not re-list with `mine: true` between the consent and the call: the batch the user approved is the batch that runs.
3. Report from the result, not from memory. `deleted` is how many went; `remaining` is the account's count afterwards, read from the same list as step 1. If the user asked for all and `remaining` is not zero, say which are left (`refused_session_active` is the workspace with a live stream: end the stream or leave it) and re-run with their ids.

### User asks "what workspace am I / are you on?"

Call `chart_status` and report the `open` (else `workspaces[0]`) `workspaceId` — that's the workspace the daemon is connected to and where chart-actions land. Map it to a friendly name with `om chart list` if helpful. **Do not say you "aren't on a workspace"** — the daemon always has an active one. The answer changes after the user runs `/workspace`, so always read it live; never answer from memory of an earlier turn.

### User asks "what's on my workspace?" / "what's on chart 0?" / "what indicators are on the chart?"

Two steps:

1. **Pick the target — omission is the default.**
   - If the user did NOT name a workspace, **omit the workspace id entirely** (agent tools: omit `workspaceId`; CLI: `--workspace` may be omitted on the chart verbs). The daemon resolves the ACTIVE workspace live at call time, so an omitted id can never be stale. This is the correct call for "my workspace" / "this workspace" / "what do you see".
   - If they named one for a ONE-OFF action ("also add RSI on Y"), pass that id explicitly for that call only.
   - If they used a friendly name (*"my BTC playground"*), call `chart_list` first to map name → id.
   - If they asked to **work on** a workspace ("switch to X", "do stuff on X from now on"), call `chart_workspace_select` FIRST — it moves the active pointer exactly like the TUI `/workspace` command — then keep omitting the id; later turns inherit it.
2. **Call `chart_refresh`** (workspace id omitted; a workspace the user names is read with `chart_show` instead, unless they ask for its LIVE state) and answer from the JSON.

Never answer "what's on my chart / workspace" from `chart_list` (that only enumerates all workspaces — it doesn't say which one is active or what's on it), and never tell the user you aren't on any workspace: the daemon is always connected to one, and `om chart status` reports it.

Reading rules:

- **Quote actual values, not types.** *"BTCUSDT on Binance Futures, 1h"* — pull the specific values from `workspace.charts[0]`. Don't say *"chart 0 has a symbol selector"*.
- **Humanize enums** per the table below.
- **One short answer per question.** Don't tail with the full workspace JSON.

### User asks "did anything change since last time?"

Track the `version` field. Re-run `chart_refresh`; if `version` is higher, diff the relevant sub-tree against the prior snapshot.

### Read-only (VIEWER) workspaces

A user can join **someone else's** live session by short id with `/workspace join <short-id>`. The
role is assigned by the server from the API-key identity: **HOST** if they own that workspace,
**VIEWER** if they don't. `chart_status` reports the active workspace's `role`.

When `role` is **`VIEWER`**:

- **Reads work normally** — answer "what's on the chart?" etc. from `chart_refresh` as usual; you see the host's live chart.
- **Writes are blocked** — every chart mutation (indicator/drawing/symbol/interval/plot-type/layout/sync add·remove·update) is refused locally (`FORBIDDEN`) and server-side. Don't attempt them.
- If the user asks for an edit, say briefly: *you're viewing this workspace read-only and can't modify a workspace you don't own.* (Proposing changes for the owner to approve is not available yet.)

When `role` is `HOST`/`CO_HOST` (or absent — your own workspace), chart actions work as normal.

## Panes and layout

Symbol, interval (`1m` minutes vs `1M` months), plot type, view zoom/pan; layout grids (`2H`/`3V`/`4`, 4-pane cap), sync, multichart cells, `NO_CHANGE`, `chartIndex out of range`.

| Tool (CLI) | Wire action | Persistence | Requires daemon |
| --- | --- | --- | --- |
| `chart_view` (`om chart view`) | `SET_VISIBLE_RANGE` | ephemeral (broadcast only) | yes |
| `chart_symbol` (`om chart symbol`) | `update_symbol` | persisting | falls back to gateway REST when down |
| `chart_interval` (`om chart interval`) | `update_interval` | persisting | falls back to gateway REST when down |
| `chart_plot_type` (`om chart plot-type`) | `update_plot_type` | persisting | yes |
| `chart_layout` (`om chart layout`) | `update_layout` | persisting | yes |
| `chart_sync` (`om chart sync`) | `update_sync` | persisting | yes |

All six verbs are wired. The per-pane verbs (`chart_view`, `chart_symbol`, `chart_interval`, `chart_plot_type`) take a REQUIRED 0-based `chartIndex` — chart 0 is the primary pane, chart 1+ are the multichart sub-cells (read them from `multiCharts.workspaces[N-1]` in the refreshed workspace snapshot). There is no default: identify the pane from a fresh read. `chart_layout` and `chart_sync` are workspace-global and take no `chartIndex`.

### `chart_view` (`om chart view`) — pan / zoom

Successful JSON has `version: 0` — the ephemeral sentinel.

### `chart_symbol` (`om chart symbol`) — switch symbol/exchange

`coin` is an optional base-ticker hint (`BTC`, `ETH`) — the venue symbol still goes in `symbol`.

`exchange` is the data-plane exchange id (`BINANCE_FUTURES`, `BYBIT`, `HYPERLIQUID_FUTURES`; `om exchanges` lists them), the same form `chart_create` takes. A chart-UI alias like `BINANCE.F` is stored as given and the pane then loads no data.

A market named in human form ("NQ", "Apple", "EURUSD") resolves to these wire values through `symbol_resolve` (the chart plane's names-only directory, TradFi venues included): a `bound` answer's `exchange` and `symbol` are exactly the `exchange` and `symbol` to pass, and ambiguity returns named candidates to pick with the user rather than a guess.

### `chart_interval` (`om chart interval`) — switch timeframe

The tool takes only the short forms. A snapshot reporting a data-plane name maps back — `HOUR` → `1h`, `DAY` → `1d`, `FIFTEEN_MINUTES` → `15m` — so never echo a read-back value straight into the call.

`1s` requires Plus tier; everything else is on free.

### `chart_plot_type` (`om chart plot-type`) — switch candle/line/area/…

The `plotType` enum on the tool is the authoritative domain — 18 values, wider than the common candle/line/area set (`volumeCandle`, `heatmap`, `stem`, `point`, `hlcArea`, … are all valid). Read a name off the enum rather than guessing one: there is no bare `line`, so a "line chart" ask maps to `markerLine` or `stepLine`.

### `chart_layout` (`om chart layout`) — switch the multi-chart grid

**Grid dimensions ARE layout requests.** When the user gives a grid like `3x1`, `1x3`, `2x2`, `2x1`, `1x2`, or phrases like "three across", "split into 2", "stacked", "quad", "2 by 2" — that is a `chart_layout` change. Read the grid as **columns × rows** (matching the layout picker: "3 × 1" = 3 columns side by side). Map to `mode`:

| User says | Panes | `mode` |
| --- | --- | --- |
| `1`, `1x1`, "single", "one chart" | 1 | `1` |
| `2x1`, "two across", "side by side", "two columns" | 2 | `2H` |
| `1x2`, "two stacked", "top/bottom", "two rows" | 2 | `2V` |
| `3x1`, "three across", "three columns" | 3 | `3H` |
| `1x3`, "three stacked", "three rows" | 3 | `3V` |
| `2x2`, "grid", "quad", "four charts" | 4 | `4` |

`mode` values are strings — `"1"` and `"4"` included, despite looking numeric.

Standard layout tops out at **4 panes (2x2)**. A bigger grid (`3x3`, `4x4`, anything > 4 panes) is **Monitor mode**, which the agent cannot set — tell the user to switch to Monitor in the chart UI's layout picker.

Workspace-global — no `chartIndex`. Growing the grid appends new panes that inherit chart 0's symbol/exchange/interval (1:1 with a manual layout change); shrinking keeps the extra panes persisted and paints only the mode's count. On a monitor-grid (multimode) workspace the frontend exits monitor mode first, then applies the standard layout. Free tier caps at 2 panes; 3+ requires Plus.

**Set the layout BEFORE per-pane symbols.** If the user wants a multi-pane layout AND specific symbols per pane (e.g. "3x1 with BTC, XRP, SOL"), the layout change must land first — the new panes don't exist until then, so a `chart_symbol` at `chartIndex` 2 issued before the grid grows fails with `chartIndex 2 out of range`. See the workflow under "User asks for a grid layout (with or without per-pane symbols)" below.

### `chart_sync` (`om chart sync`) — toggle multi-chart sync (symbol / interval / crosshair)

Workspace-global — no `chartIndex`; the sync master is the primary pane (chart 0). Enabling `symbol` or `interval` sync makes every pane follow chart 0 (the server propagates chart 0's symbol/interval onto the other panes). One key per call — to toggle two settings, make two calls.

**Sync awareness.** Before changing a per-pane symbol or interval, check `multiCharts.syncStatus` in the refreshed workspace snapshot. If `syncStatus.symbol` is `true`, every pane shows ONE symbol — a per-pane `chart_symbol` won't give panes different symbols; it changes the symbol for all of them. If the user asks for different symbols per pane while symbol sync is on, tell them sync is on and ask whether to turn it off first (`chart_sync` with `key: symbol`, `enabled: false`) or pick one symbol for all panes. Same for `syncStatus.interval`. On a monitor-grid (multimode) workspace only `crosshair` sync is togglable via the agent; symbol/interval sync is fixed by the grid.

### NO_CHANGE response (the persisting verbs)

A persisting verb whose requested value already matches answers `NO_CHANGE` — informational, defined with every other failure shape in §"Errors".

### Multichart panes

Every PER-PANE tool (`chart_view`, `chart_symbol`, `chart_interval`, `chart_plot_type`) takes a numeric `chartIndex`; identify the pane from a fresh read, never by guessing. (The CLI's `--chart` flag additionally resolves a symbol name to the pane — see §"CLI equivalents".)

Index semantics:
- `chartIndex` 0 is the primary pane (hoisted to the workspace's top-level `onchart` / `offchart` / `metadata`).
- `chartIndex` 1, 2, … target multichart sub-cells in `multiCharts.workspaces[N-1]`.
- `multiCharts.workspaces.length` from `chart_refresh` tells you how many cells exist.

### User asks for a grid layout (with or without per-pane symbols)

Triggers: any grid dimension (`3x1`, `1x3`, `2x2`, `2x1`, `1x2`) or layout phrasing ("three across", "split into two", "stacked", "quad", "2 by 2"). This is the `chart_layout` path — see the grid→mode table above.

**Order matters — layout first, then symbols.** A combined request like *"change to 3x1 with BTC, XRP, SOL"* is ONE layout change plus per-pane symbol sets, in this exact order:

1. **Resolve the workspace id** (same default rules — see §"Workspaces").
2. **Change the layout once** — map the grid to a layout mode and call `chart_layout`. This grows the workspace to 3 panes; the new panes inherit chart 0's symbol.
3. **Then set each pane's symbol once** with `chart_symbol`, lowest `chartIndex` first — and only for a pane whose target differs from what's already there. Map the symbols to panes in the order the user listed them. Worked calls for *"3x1 with BTC, XRP, SOL"* (chart 0 already on BTCUSDT):

```jsonc
chart_layout   { "mode": "3H" }                       // workspaceId omitted → the active workspace
chart_symbol   { "chartIndex": 1, "symbol": "XRPUSDT", "exchange": "BINANCE_FUTURES" }
chart_symbol   { "chartIndex": 2, "symbol": "SOLUSDT", "exchange": "BINANCE_FUTURES" }
// chart 0 already matches — re-sending it just earns a NO_CHANGE
```
4. **No confirmation** — chart mutations on the agent's own canvas dispatch immediately; state the outcome once.

### User asks to seek / pan / zoom

This is the `chart_view` path — ephemeral viewport change, broadcasts to peers, no persistence.

1. **Parse the target time range** (*"last 24h"*, *"yesterday"*, *"the hour around 2026-05-15 14:00"*).
2. **Resolve the workspace id** (same default rules — see §"Workspaces").
3. **Compute `startTime` and `endTime`** in integer epoch MILLISECONDS — a seconds value is schema-valid and lands the viewport in 1970. `endTime` must be after `startTime`. `cursorTimestamp` is optional and defaults to the midpoint, so pass it only when the user named a focus instant.
4. **Execute** `chart_view` — no preview, no confirmation (ephemeral, reversible). Success response has `version: 0` — expected, not an error.

## Indicators

Add, remove (by `indicatorType` or `everyIndicator`), update, list; RSI/MACD/EMA and every registry native, WRUN ids, single-instance `409 NO_CHANGE`, `VALIDATION`, defaults.

| Tool (CLI) | Wire action | Requires daemon |
| --- | --- | --- |
| `chart_indicator_add` (`om chart indicator add`) | `add_indicator` | yes |
| `chart_indicator_remove` (`om chart indicator remove`) | `remove_indicator` | yes |
| `chart_indicator_update` (`om chart indicator update`) | `update_settings` | yes |
| `chart_indicator_list` (`om chart indicator list`) | local (read-only) | no |

All verbs are wired. `chartIndex` selects the multichart cell.

**Discovery first.** `chart_indicator_list` returns every addable
type from the local registry — canonical key, display name, placement
(onchart/offchart), friendly aliases, and whether it is single-instance. Call it
whenever the user names an indicator you cannot map to an `indicatorType`; do not
guess. It needs no daemon.

**Indicator type normalization.** On `chart_indicator_add`, the `indicatorType` you pass is normalized before it is sent (`chart_indicator_remove` forwards yours verbatim and the server matches). Both shorthand (`RSI`, `liquidations`, `funding`) and canonical (`TECHNICAL_SCRIPT`, `LIQUIDATIONS`, `AGGREGATED_FUNDING_RATE`) forms work:

| User-friendly input | Normalized to | Notes |
| --- | --- | --- |
| `RSI`, `MACD`, `EMA`, `SMA`, `BB`, `ATR`, `ADX`, `CCI`, `Stoch`, `OBV`, `MFI`, `Ichimoku`, `Supertrend`, … (the registry lists 15; other standard script names pass through) | `TECHNICAL_SCRIPT` + `settings.subType: '<NAME>'` | Standard chart-engine script indicators. Free tier. |
| `liquidations` / `Liquidations` | `LIQUIDATIONS` | Basic liquidations indicator — free tier, any exchange. |
| `aggregated_liquidations` | `AGGREGATED_LIQUIDATIONS` | Aggregated across exchanges. |
| `hyperliquid_liquidations` / `liquidation_heatmap` | `HYPERLIQUID_LIQUIDATION_HEATMAP` | **Plus tier only.** |
| `tpsl` | `HYPERLIQUID_TPSL_HEATMAP` | **Plus tier only.** |
| `orderbook` / `orderbook_heatmap` / `heatmap` | `ORDERBOOK_HEATMAP` | **Plus tier only.** |
| `aggregated_orderbook` / `aggregated_heatmap` | `AGGREGATED_ORDERBOOK_HEATMAP` | **Plus tier only.** |
| `funding` / `funding_rate` | `AGGREGATED_FUNDING_RATE` | Exact key `FUNDING_RATE` instead resolves to the per-exchange native. |
| `oi` / `open_interest` | `AGGREGATED_OPEN_INTEREST` | Exact key `OPEN_INTEREST` instead resolves to the per-exchange native. |
| `dominance` / `btc_dominance` | `BITCOIN_DOMINANCE` | |
| `footprint` | `VOLUME_FOOTPRINT` | |
| `tpo` | `TIME_PRICE_OPPORTUNITY` | |
| `svp` | `SESSION_VOLUME_PROFILE` | |
| `vrvp` | `VISIBLE_RANGE_VOLUME_PROFILE` | |

For Plus-gated types on a non-Plus account, the server returns `403 TIER_FEATURE_LOCKED` — surface verbatim, do not retry. The user must upgrade or stick to free-tier types.

**WRUN packages with cross-symbol pinned input sources stay off charts for now.** A `wrun/@scope/name/output` add whose package pins a NON-odds feed source to a fixed `symbol`+`exchange` (a cross-symbol reference leg) is UNVERIFIED on the hosted chart lane (the chart backend computes with its own data path); when you KNOW a package carries such a pin (you authored it this session, or its listing says so), decline the add, say why, and offer the metric via alerts/`metric get` instead. Odds-pinned packages (conditionId markets) chart as they always have, and a package you cannot inspect is not grounds for refusal.

Typical `settings`:

| `indicatorType` | Typical `settings` |
| --- | --- |
| `RSI` | `{"period": 14}` |
| `MACD` | `{"fast": 12, "slow": 26, "signal": 9}` |
| `EMA` / `SMA` | `{"length": 50}` |
| `BB` | `{"length": 20, "stddev": 2}` |
| `ATR` | `{"period": 14}` |
| `Stochastic` | `{"period": 14, "smoothing": 3}` |
| `Liquidations` | `{}` |

**Every registry native is addable.** The table above covers common shorthands only; ALL ~80 registry types (`chart_indicator_list`) work as `indicatorType` values — exact keys win over aliases, any casing accepted. A handful of interaction-only overlay types are excluded from the agent path and rejected with a clear error. If the user names an indicator not in the list output, submit anyway — an unsupported type is rejected either way: the normalizer throws before the call goes out, and the server returns a `VALIDATION` error. Do not silently substitute.

**Minimal params contract.** Send only the settings the user explicitly asked to change (period, funding interval, value area, ...). The chart fills every other default client-side — theme colors, widths, market identity from chart context. Do NOT invent colors or cosmetic settings unless asked. Setting keys outside the shared whitelist are dropped server-side and echoed back in the response `warnings` field — if a key you sent shows up there, it was ignored, not applied; tell the user rather than retrying blindly.

**Single-instance types.** Types flagged `single-instance` by `chart_indicator_list` (heatmaps, volume profiles, footprint) allow one instance per chart; a duplicate add returns `409 NO_CHANGE` with the existing overlay id. Treat that as "already there", not an error to retry.

Multichart cells are limited to **2 indicators per cell** (a separate cap from `indicatorsPerChart`). Adding more returns a `VALIDATION` error.

**Removing an indicator** — prefer `indicatorType` whenever the user names the indicator; it removes EVERY matching overlay on the pane and needs no id round-trip.

- Absent type / empty pane → `409 NO_CHANGE` ("already gone") — treat as success, do not retry.
- "Remove ALL indicators" → `everyIndicator: true` (clears the whole pane; hidden system overlays are kept). Whole workspace = one such call per `chartIndex` (0..N-1).
- "Remove X from all charts" → the same `indicatorType` call once per `chartIndex`; `NO_CHANGE` on panes that never had it is expected.

`indicatorId` remains for exact-id removal (id from the add response or `chart_refresh`). The server filters BOTH `onchart` and `offchart` (overlayType-aware — a drawing sharing the id is preserved). Id path: `VALIDATION` error if the id isn't found on the target chart.

**Tuning indicator settings** by overlay id:

```jsonc
chart_indicator_update { "chartIndex": 0, "indicatorId": "<id>", "settings": { "period": 21 } }
```

The server MERGES `settings` on top of the persisted state, so send only the keys being changed, not a full re-read of the object. Re-read with `chart_refresh` afterwards to see the merged result.

### User asks to add an indicator

Five-step flow:

1. **Parse intent** — extract `indicatorType`, chart pane, and `settings` if named.

2. **Resolve the workspace id** (same default rules).

3. **If the chart pane isn't named, pass `chartIndex: 0`** — the field is required, so pane 0 is a deliberate policy default here, not a schema one; the user can correct in a follow-up.

4. **If params aren't named, use the textbook default** (RSI 14, MACD 12/26/9, EMA 20, BB 20/2) and name it in the outcome line. Param choice is not one of the persona's allowed questions; the user's next message changes it.

5. **Execute** `chart_indicator_add` — no preview, no confirmation; chart mutations on the agent's own canvas dispatch immediately. Worked call for RSI(14) on the active chart:

```jsonc
chart_indicator_add { "chartIndex": 0, "indicatorType": "RSI", "settings": { "period": 14 } }
```

   - On `ok: true` → *"Added RSI(14) to chart 0 — version `<N>`."*
   - On `code: "VALIDATION"` → surface the server detail verbatim; most often an unsupported `indicatorType`.
   - On `code: "FORBIDDEN"` → *"The API key doesn't own this workspace. Pick one from `chart_list`."*

## Drawings

Trendlines, fibonacci, shapes: default `drawing auto` (computed anchors); `drawing add` only for user-named exact levels; `drawing schema` roles; remove by id.

| Tool (CLI) | Wire action | Requires daemon |
| --- | --- | --- |
| `chart_drawing_auto` (`om chart drawing auto`) | `add_drawing` | yes |
| `chart_drawing_add` (`om chart drawing add`) | `add_drawing` | falls back to gateway REST when down |
| `chart_drawing_schema` (`om chart drawing schema`) | (local, read-only) | no |
| `chart_drawing_remove` (`om chart drawing remove`) | `remove_drawing` | falls back to gateway REST when down |

### User asks to draw / add / remove a chart tool

Drawing tools (trendlines, fibs, shapes, arrows, markers, positions, annotations) have their own
detail file → read [`chart-actions-tool-drawing.md`](chart-actions-tool-drawing.md) for the full
workflow. In short: **default to `chart_drawing_auto`** (it computes anchors from market data); use
`chart_drawing_add` (role-tagged anchors) only when the user named exact price/time levels
(`chart_drawing_schema` lists a tool's roles).

Span tools (LongPosition/ShortPosition/PositionForecast, Rectangle/Ellipse, Price/Date ranges,
FixedRangeVolumeProfile) get their WIDTH from the anchor time span: anchor target/stop or the
second corner at least 2 bars AFTER the first anchor, or the shape paints as an invisible
zero-width sliver (the verb refuses such calls and names the required span). `drawing auto`
is immune: its computed swing anchors are always time-separated.

## Pins

Events beside the candles — news feeds, custom watches, alert fires — in one `om chart pins` call; come here for anything that plots WHAT HAPPENED on a price chart.

`om chart pins` (action `chart_pins`) writes a live query onto a workspace's event lane: sources plus filter, window, depth, market and workspace, and the daemon keeps it true. The doctrine behind every default below — the one-question rule, chart-time filters, depth, workspace consent — lives in `news.md`'s "Plotting events on charts" section; read that before plotting.

- **Sources** are typed refs, `{kind: "feed"|"watch"|"alert", ref}`; a bare string works when it is unique across all three namespaces. No sources at all plots every chartable owned source, and a home with none gets a catalog preview.
- **Market** defaults from the active chart pane, else the sources' sole market tag. A market the user named in human form ("NQ", "Apple") is one `symbol_resolve` call first — never a guess, and never a crypto proxy for a market the chart plane carries.
- **Workspace** defaults to the view's own titled day workspace (same view, same day: the same chart), and `fresh: true` mints a new one. `workspace: <id>` and `here: true` target a chart the USER keeps: get their explicit yes before passing either, and expect a chat surface to raise a card for it.
- **Follow is on.** A plotted view keeps pinning as events land. `unfollow: true` stops it (the pins stay; `source` scopes one member) and `rearm: true` resets a degraded view's delivery health in place. Never re-plot to re-arm — that re-projects and can widen the filter frozen into the binding.

The result carries the live-view URL to share plus one structured summary, so hand the URL over. Pins live with their workspace and only `chart_delete` removes them. Two verbs this is not: `om chart events` reads recent manual chart edits and plots nothing, and `om news chart` is the deprecated CLI-only spelling kept for legacy follow rows.

## Make chart actions visible — presence-aware live view

When to open the live view (`chart_open` with `waitForHumanMs`) vs share the `?live=true` link once, decided by `humanPresent` and surface.

Decide by presence and surface:

- **`humanPresent: true`** — the user (or another viewer) already has the live chart open. Just act. Don't print the live link.
- **`humanPresent: false`, local CLI surface** — before this conversation's FIRST chart mutation, call `chart_open` with `waitForHumanMs: 10000`. It opens `https://openmarket.xyz/chart/{workspaceId}?live=true` in the user's browser and waits for them to land, then your mutations play visibly. Do this once per conversation; if the user declines or told you to stop, don't repeat it. On a headless box it opens nothing (`opened: false`) — fall through to sharing the URL.
- **`humanPresent: false`, remote surface (Telegram/Discord/web)** — never spawn a browser; after the mutation's success summary, share this once, on its own line:

  > To experience your AI Agent working on your chart, head to https://openmarket.xyz/chart/{workspaceId}?live=true

  Substitute `{workspaceId}` with the actual id. One link per turn at most; don't re-send while `humanPresent` is true, after a failed action, or once the user has said to stop.

## The blackboard — attributed marks, peers, and receipts

The canvas is shared. Three read surfaces keep you honest about what is on it and who put it there:

- **`chart_drawing_list`** — the drawings on the live chart, oldest first, with the `drawingId` that `chart_drawing_remove` needs, its author (`self` = you, `peer <peerId>` = another agent, `human`, or `unknown` when the daemon never observed the add), and the author's stated reason when one was given. Membership comes from the live workspace document (the same store removes are verified against, so every `presence: "live"` id is removable); author/reason comes from what the daemon observed while attached. Use it before drawing (don't duplicate what exists), when asked to clean up ("remove that line" needs its id), and to read what another agent has argued on the chart. Pass `includeRemoved` to also see marks the daemon once observed that are no longer on the live chart (`presence: "ledger-only"`), each with the `transformation` (market) it was drawn on: a pane whose symbol changed hides its old marks rather than deleting them.
- **`chart_events`** — now split by author: `events` are the human's manual edits; `peerEvents` are other agents' edits, each with its peer id and quoted narration. When `activePeerRun` is present, another agent is mid-performance: prefer reads over writes until it ends (your own submits briefly auto-wait for the floor and warn if they proceeded during a peer run).
- **`om nervous status`** (action: `nervous_status`) — the nervous system's audit trail: event-driven chart moments (news watch fires, alert fires, strategy entries/exits) that were expressed on the chart without anyone asking, each with a story, per-verb outcomes, and the live view link. After an alert or news fire, check it before replying so you can tell the user what was already marked and hand them the link instead of re-drawing it.

Every drawing you add returns its `drawingId` — keep it if you may need to adjust or remove that mark later in the conversation.

When you draw as part of a disagreement or a joint analysis with another agent, put your reasoning in the mark itself: a `narration` on every mutation, and Callout/Text/Note content that states the claim. Peers and humans read the chart, not your private chain of thought.

On-chart text renders as a SINGLE unwrapped line: keep Callout/Text/Note content to a short phrase (a side tag plus a handful of words) and put the full argument in the session chat or the narration. Place annotations inside the currently visible time range (read the viewport from the refreshed workspace snapshot) — a mark the audience cannot see argues nothing. Text marks must never overlap: before placing Callout/Text/Note, read the existing marks' anchors (chart_drawing_list) and choose a spot clearly separated in time and price from every other text mark.

## Behaviors to avoid

Never relay env vars or self-hosting internals unprompted, never invent verbs, prefer the cheaper read; humanize enums per the table here.

- **Do not surface infrastructure concerns proactively.** The `OM_API_KEY` is captured by `om init` (settings DB): only mention it if a `UNAUTHORIZED` error points there. The collab gateway URLs default to the hosted relay; `OM_COLLAB_REST_URL` / `OM_COLLAB_WS_URL` / `OM_CHART_URL` are documented env vars (docs/USER_GUIDE.md, "Environment variables") for self-hosted or alternate relays. Bring them up only when the user asks about self-hosting, a local relay, or pointing at a different chart deployment, never as troubleshooting for the hosted service.
- **Do not call `chart_list` when the user only asked about the default workspace.** The id is in `om chart status` already — one round-trip is cheaper than two.
- **Do not retry `no_state_sync` past its cap** — the cap and remedy are defined in §"Errors".
- **Do not assume the `workspace.*` JSON shape.** Pass-through from service. Read what's actually there; don't invent field names.
- **Do not invent chart tools or `om chart` subcommands.** The generated §"Command reference" below is this file's complete census — check it, not memory; the drawing verbs live in the companion file's reference, and `chart_pins`'s call shape is §"Pins" with its doctrine under `news.md`. (The multiplayer session verbs exist only when the operator opted in with `OM_CHART_MULTIPLAYER=1`; never suggest them otherwise.) Anything in neither census (e.g. a drawing update) doesn't exist: fall back to the chart UI and tell the user honestly.
- **Do not leak schema vocabulary** — `peerId`, `originPeerId`, `STATE_SYNC`, `AGENT_INTENT`, `1008 policy violation`, `runId`, `stepId` — internal terms only.
- **Always humanize schema enums when surfacing them.**

  | Wire | User-facing |
  | --- | --- |
  | `BINANCE_FUTURES` | Binance Futures |
  | `BINANCE` | Binance |
  | `OKEX_SWAP` | OKX Swap |
  | `BITMEX` | BitMEX |
  | `HYPERLIQUID_FUTURES` | Hyperliquid Futures |
  | `POLYMARKET` | Polymarket |
  | `FIFTEEN_MINUTES` | 15m |
  | `HOUR` | 1h |
  | `DAY` | 1d |
  | `add_drawing` / `add_indicator` / `SET_VISIBLE_RANGE` | adding a drawing / adding an indicator / setting the visible range |

  Crypto symbols (`BTCUSDT`, `ETH-USD`) stay raw. Polymarket conditionIds (66-char hex) never appear in chat.

## Out-of-scope requests

Honest refusals for freehand sketching, streaming/watch loops, and other owners' workspaces — with what to offer instead.

| User asks for | Honest response |
| --- | --- |
| Freehand brush / pencil | *"Freehand drawing isn't agent-drawable (no computable values). Use a shape, line, or annotation tool instead, or draw it in the chart UI."* |
| Watch the workspace live / stream changes | *"`chart_refresh` is point-in-time. There's no streaming subcommand yet — poll it."* |
| Author changes for someone else's workspace | *"The retail API key only authorizes workspaces its owner owns. Pick one from `chart_list`."* |
| Authenticate as a different user | *"Re-run `om init` to capture a new API key, then `om service restart` so the daemon picks it up."* |

## Errors

Every failure shape and recovery: `bridge_disabled`, `no_active_workspace`, `request_failed`, `UNAUTHORIZED`, `FORBIDDEN`, `VALIDATION`, `CLIENT_VALIDATION`, `NO_CHANGE`.

```jsonc
{ "error": "bridge_disabled",
  "message": "Collab bridge is disabled. Run `om init` to configure the API key and default workspace, then restart the daemon." }

{ "error": "daemon_down",
  "message": "Could not reach the daemon at http://127.0.0.1:31337: ...",
  "hint": "Start it with `om service start` (or install first with `om service install`); foreground fallback: `om run`." }

{ "error": "no_state_sync",
  "message": "No STATE_SYNC cached for workspace '<workspaceId>'. The bridge may not be connected to that workspace, or the initial STATE_SYNC has not yet arrived." }

{ "error": "UNAUTHORIZED",   // from the upstream gateway
  "message": "invalid api key" }

{ "error": "FORBIDDEN",
  "message": "workspace.owner !== apiAuth.userId" }

{ "error": "VALIDATION",     // from `om chart indicator add` / `drawing add` when type/params/anchors are bad
  "message": "unsupported toolType='Marker'. supported: TrendLine, FibonacciRetracement" }
```

Recovery rules:

- `bridge_disabled` → guide the user to run `om init` (captures the API key + default workspace) and `om service restart` to pick them up.
- `daemon_down` → `om service start` (or `om service install` if not yet installed). Last resort: `om run` foreground.
- `no_state_sync` → retry with a short delay, 2–3 times at most; if STATE_SYNC hasn't landed within ~10 seconds something is wrong server-side — check `chart_status`.
- `UNAUTHORIZED` → API key bad or revoked. Re-run `om init` and `om service restart`.
- `FORBIDDEN` → key's user isn't the workspace owner. Use `chart_list` to find one they own.
- `VALIDATION` on a mutation → server didn't accept the envelope. Surface the detail verbatim; let the user correct.
- `no_active_workspace` → a call omitted the workspace id and no ACTIVE workspace is configured (a fresh install has none until `om init` picks one or `chart_workspace_select` runs). Relay the remedy the error names; never invent an id or silently pick one from `chart_list`.
- `invalid_workspace_id` → the id wasn't a workspace short id or share-link URL (a friendly name like "btc desk" is not an id — resolve it via `chart_list` first).
- `workspace_select_failed` → the live repoint failed; the persisted default was rolled back, not clobbered. Relay the remedy hint; do not claim the switch happened.
- `request_failed` → a direct gateway REST call failed without a typed upstream code (network/HTTP-level). Report it as unreachable; one attempt, no retry loop.
- `CLIENT_VALIDATION` → a drawing call refused BEFORE any network submit (bad roles/anchor count/direction/`text` on geometry). It returns as a normal result with `ok: false` — read the envelope, not just an error flag. Fix the named field once; never claim drawn.
- `NO_CHANGE` (`409`) → the requested value already matches (or the overlay is already gone / already present for single-instance types). Informational — the CLI exits 0 and no theater fires on the chart UI: treat as done, never retry, never surface as an error.
- `chartIndex N out of range (have M charts)` → the pane doesn't exist yet; grow the layout first (`chart_layout`), then set that pane once.
- `403 TIER_FEATURE_LOCKED` → the indicator type is plan-gated; surface it verbatim, do not retry — the user upgrades or picks a free-tier type.

Where a failure arises in context, its section names the code and points here — this glossary is the one place recoveries are defined.

## CLI equivalents

The `om chart` command forms for shell agents: copy-paste recipes, the `--chart <SYMBOL>` pane resolver, and CLI-only flags — chat tools use the field names, not these flags.

**The `--chart <n-or-symbol>` pane resolver (CLI-only).** Every persisting `om chart` verb accepts `--chart` as a numeric index OR a symbol name (`--chart ETHUSDT`, `--chart ETH`): a symbol resolves to the right pane from the workspace's cached state (exact match, then unique prefix; ambiguous or unknown symbols error with the candidates — no silent default to chart 0). Prefer the symbol form on the CLI when the user names a coin, e.g. `om chart drawing add --workspace <id> --chart ETHUSDT --tool TrendLine`. Agent tools have no such resolver — they take the numeric `chartIndex` you verified.

```bash
# 1. Confirm the bridge is up.
om chart status

# 2. List my workspaces.
om chart list

# 3. Show what's on the bridge's default workspace.
om chart refresh --workspace $(om chart status | jq -r '.workspaces[0].workspaceId')

# 4. Add RSI(14) to chart 0.
om chart indicator add --workspace <workspaceId> --chart 0 --type RSI --params '{"period":14}'

# 5. Add MACD(12,26,9) to chart 0.
om chart indicator add --workspace <workspaceId> --chart 0 --type MACD --params '{"fast":12,"slow":26,"signal":9}'

# 6. Add a 50-bar EMA on chart 0.
om chart indicator add --workspace <workspaceId> --chart 0 --type EMA --params '{"length":50}'

# 7. Add liquidations (free tier — basic, all exchanges).
om chart indicator add --workspace <workspaceId> --chart 0 --type Liquidations

# 8. Tune existing indicator settings (server merges — send only the changed keys).
om chart indicator update --workspace <workspaceId> --chart 0 --id <indicatorId> --params '{"period":21}'

# 9-10. Draw / auto-draw any tool (trendline, fib, position, …).
#       See chart-actions-tool-drawing.md for the full drawing recipes.
om chart drawing auto --workspace <workspaceId> --chart 0 --tool TrendLine \
  --normalized-symbol BTCUSDT --exchanges BINANCE_FUTURES --interval HOUR

# 12. Switch to 1-minute candles.
om chart interval --workspace <workspaceId> --chart 0 --interval 1m

# 13. Switch the chart to ETHUSDT on Binance Futures.
om chart symbol --workspace <workspaceId> --chart 0 --symbol ETHUSDT --exchange BINANCE_FUTURES

# 14. Switch to Heikin Ashi candles.
om chart plot-type --workspace <workspaceId> --chart 0 --type heikinAshi

# 15. Multichart — target a chart BY SYMBOL (preferred when user names a coin).
#     CLI resolves ETHUSDT → the right chartIndex automatically.
om chart symbol --workspace <workspaceId> --chart ETHUSDT --symbol SOLUSDT --exchange BINANCE_FUTURES

# 15b. Same effect using a numeric index when the user is index-explicit.
om chart symbol --workspace <workspaceId> --chart 1 --symbol SOLUSDT --exchange BINANCE_FUTURES

# 16. Zoom to a 24-hour window with the cursor at midday (ephemeral).
om chart view --workspace <workspaceId> --chart 0 \
  --start $(($(date +%s) - 86400)) --end $(date +%s) --at $(($(date +%s) - 43200))
```

---

## For contributors

Where the wire contract and bridge code live for adding or changing a chart verb.

The wire contract lives in code, not a standalone doc: envelope shapes in `packages/cli/src/runner/collab/types.ts`, envelope validation in `packages/cli/src/runner/collab/validators.ts`. Bridge code under `packages/cli/src/runner/collab/`. Agent-facing CLI in `packages/cli/src/cmd/collab.ts`. Loopback RPC handlers in `packages/cli/src/runner/http/rpc/collab.ts`. Skill registration in `packages/cli/src/skills/package.ts`.

**Adding a new verb under a resource group:** find the resource's `registerXCommands(collab)` function in `cmd/collab.ts`, add a new `.command("...")` under the group, and post the appropriate `action` / `data` / `intent` shape to `collabRpc("submit", ...)`. The bridge's `validateEnvelope` (`runner/collab/validators.ts`) is the safety net; the server's controller is the authority.

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `chart_indicator_add`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_indicator_preview`
  - on `NO_CHANGE` — NO_CHANGE on a preview push is not a success: the push was refused and the stored preview was tombstoned at the same revision, so the pane renders nothing. Say the preview did not land, and re-run it to supersede rather than reporting it as already shown.
- `chart_indicator_remove`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_indicator_update`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_interval`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_keep`
  - discloses `disclosures[]` — Guard notes the keep proceeded under: market notes (the rename-in-place path discloses a pane-vs-pins mismatch or several recorded markets instead of refusing, and both paths disclose venue-spelling differences, stale or unreadable pane reads, and unparsable pin markets), a template note when a clone was seeded from defaults, and a warning when the name matches a workspace id only this machine's ledger still knows. Relay them.
- `chart_layout`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_plot_type`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_symbol`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_sync`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
- `chart_view`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.

<!-- AUTO: END RESULT CONTRACT -->

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om chart create` (action: `chart_create`) — Create a chart workspace with a clean template (your name, symbol, exchange, and interval; no inherited indicators), REST direct so it works even when the daemon is down.
- `om chart delete` (action: `chart_delete`) — PERMANENTLY delete chart workspaces (REST direct through the collab gateway).
- `om chart events` (action: `chart_events`) — Recent edits on the live session, oldest first, split by author.
- `om chart indicator add` (action: `chart_indicator_add`) — Add a technical indicator, WRUN marketplace indicator, or registry kScript indicator (RSI, MACD, EMA, LIQUIDATIONS, wrun/@scope/name/output, @scope/name, ...) to a chart pane.
- `om chart indicator list` (action: `chart_indicator_list`) — List every indicator type addable via `chart_indicator_add`: canonical keys, friendly aliases, chart placement, and single-instance rules.
- `om chart indicator preview` (action: `chart_indicator_preview`) — Draw a LOCALLY COMPUTED WRUN output on a chart pane as a PREVIEW line (draft lane: works for unpublished packages installed via `om wrun install`).
- `om chart indicator remove` (action: `chart_indicator_remove`) — Remove indicator overlays from a chart pane.
- `om chart indicator update` (action: `chart_indicator_update`) — Tune an existing indicator's settings.
- `om chart interval` (action: `chart_interval`) — Change a chart pane's candle interval (1m, 5m, 15m, 1h, 4h, 1d, 1w, ...).
- `om chart keep` (action: `chart_keep`) — Keep the current scratch chart under a name.
- `om chart layout` (action: `chart_layout`) — Change the multi-chart layout / grid.
- `om chart list` (action: `chart_list`) — List every chart workspace the account owns (REST direct, so it works even when the daemon is down): the same list, names and ids, the user sees in the web app.
- `om chart open` (action: `chart_open`) — Open a workspace's live chart view (openmarket.xyz/chart/<id>?live=true) in a browser on this machine, and optionally wait for a human viewer to join the session.
- `om chart plot-type` (action: `chart_plot_type`) — Change a chart pane's plot type (candlestick, line, bar, area, ...).
- `om chart refresh` (action: `chart_refresh`) — Read the LIVE workspace state by issuing REQUEST_STATE_SYNC over the bridge WS and returning the fresh snapshot.
- `om chart screenshot` (action: `chart_screenshot`) — Render a PNG snapshot of a workspace by short id or share-link URL.
- `om chart select` (action: `chart_workspace_select`) — Make a workspace the ACTIVE one: the live bridge repoints to it, it becomes the saved default, and every later chart action with `workspaceId` omitted lands on it (exactly what the TUI `/workspace` command does).
- `om chart show` (action: `chart_show`) — Read a workspace's content (symbol, interval, indicators, drawings, layout) by its short id or share-link URL, WITHOUT joining a live session.
- `om chart status` (action: `chart_status`) — Report the collab bridge's WS state, peerId, and pending intent counts for every active workspace.
- `om chart symbol` (action: `chart_symbol`) — Change a chart pane's symbol (e.g. BTCUSDT on BINANCE_FUTURES → ETHUSDT on BINANCE_FUTURES).
- `om chart sync` (action: `chart_sync`) — Toggle a multi-chart sync setting: symbol / interval / crosshair.
- `om chart view` (action: `chart_view`) — Set the visible time range on a chart pane (SET_VISIBLE_RANGE — ephemeral, no persist).

- `om nervous status` (action: `nervous_status`) — Recent nervous-system receipts, newest first: event-driven chart moments (news, alert, and strategy fires) with a story, per-verb outcomes, and the live view link; skipped ones carry the reason.

<!-- AUTO: END COMMAND REFERENCE -->
