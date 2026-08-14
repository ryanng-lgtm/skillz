---
name: openmarket-chart-actions
description: Inspect and mutate the user's chart workspaces through the local OpenMarket Collab Service Bridge. Verbs live directly under `om chart` (`status`/`events` for bridge health and observed edits, `list`/`create`/`show`/`refresh`/`screenshot`/`open` for workspaces, `view`/`symbol`/`interval`/`plot-type` per-pane plus `layout`/`sync` workspace-global for chart mutations), with two grouped families, `om chart indicator` for indicator add/remove/update and `om chart drawing` for drawing add/remove. Multichart is supported on every persisting verb via `--chart <n>`. Use this skill when the user asks "is my orchestrator/bridge/daemon connected?", "what workspaces do I have?", "what's on my BTC workspace?", "what symbol / indicators / drawings are on chart N?", or asks to (a) add an indicator (RSI, MACD, EMA, BB, ATR, Stoch, Liquidations), (b) draw a trendline / fibonacci retracement between two anchor points, (c) seek / zoom / pan the visible time range, (d) change the symbol / interval / plot type / multi-chart layout, (e) toggle multi-chart sync (symbol / interval / crosshair), or (f) tune indicator settings. Read this file when invoking any `om chart ...` command.
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om chart

The Collab Service Bridge is a long-lived WebSocket from the local `om` daemon to a remote collab gateway. At boot it joins one workspace, receives a `STATE_SYNC` snapshot, caches it in-process, and stays open. The agent queries that cache (or submits mutations through the bridge) via `om chart ...`.

Commands are grouped by **resource**, not by action verb — same pattern as `kubectl get pods`, `docker container run`, `git remote add`. Picking the right group is the agent's first job; the verbs under each group are small and consistent.

## When to reach for the chart

The chart is the display plane where your work turns visible. When the user asks to SEE anything (price action around an event, a support/resistance level, market structure, a comparison between symbols), express it ON the chart: set the symbol and interval, add the indicator, draw the level or zone, and confirm with `om chart screenshot` when they ask how it looks. Prefer this over ASCII sketches, text tables of candles, or describing what a chart would show. Two checks before acting: `om chart status` for the active workspace (and whether a human is watching), and the verb map below so a grid ask lands on `om chart layout` first.

**Events on charts are their own lane: `om chart pins`** (action `chart_pins`). It plots event sources (news feeds, custom watches, price-alert fires) onto a chart's event lane as a live view; the doctrine (defaults, the one-question rule, filters, depth, workspace consent) lives in `news.md`'s "Plotting events on charts" section, so read that before plotting events. Do not confuse it with `om chart events` (action `chart_events`), the session-edit stream: that verb READS the human's and peers' recent manual chart edits and plots nothing.

**Workspace policy: frictionless, scratch by default.** A target the user NAMED is used as-is (with the consent language first); something already on screen (`here`) is painted, creating nothing. Everything else ad-hoc lands on a SCRATCH canvas: `chart_pins` mints its own fresh-or-same-view day workspace as one, and a bare fresh canvas is `chart_create` with `scratch: true` and no name (48h sliding TTL relay-side, exempt from the plan workspace count, listed only on the dim scratch shelf, zero residue when the user walks away). Never mint a NAMED workspace unless the user named it, and never promote one on your own: `om chart keep <name>` (action `chart_keep`) is the user's naming act that makes a scratch permanent IN PLACE, same id, same share link; a follow never promotes anything. When a run reports a scratch mint, disclose the expiry once and name the keep verb once.

## Single-binary setup

Same `om` binary as alerts. The daemon (`om run` foreground or `om service start` background) holds the bridge; the `om chart` subcommands either:

- **call the daemon's loopback HTTP** (`status`, `refresh`, `view`, `indicator add`, `drawing add` — they require the daemon to be running), or
- **call the upstream collab gateway REST directly** (`list` — works even when the daemon is down).

Configuration is handled by `om init`:

- **API key** — captured during the API-key step and stored in the SQLite `settings` table.
- **Default workspace** — `om init`'s workspace picker lists workspaces the API key can access and writes the chosen id to the settings table.

Both feed the daemon at boot. Users do not need to export `OM_API_KEY` or `OM_COLLAB_WORKSPACE_ID` themselves once `om init` has run. If the daemon boots without one of these, the bridge is disabled and every command except `om chart list` returns a clear `bridge_disabled` error — surface that to the user as *"the orchestrator isn't configured for collab yet — run `om init`."*

## The verb map

### `om chart status` / `om chart events`: bridge state and observed edits

| Command | Purpose | Requires daemon |
| --- | --- | --- |
| `om chart status` | Report peerId, every workspace WS state, pending intent count, whether STATE_SYNC is cached, session participants + `humanPresent`, and `stateStale`. | yes |
| `om chart events` | List the human's recent MANUAL chart edits observed on the live session (oldest first) — drawings placed (with time+price points), indicators added/removed, symbol/interval/layout changes. `--since <epochMs>` filters to edits after a watermark. | yes |

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

### Workspace verbs: list, create, show, refresh, screenshot, open

| Command | Purpose | Requires daemon |
| --- | --- | --- |
| `om chart list` | List workspaces accessible to the API key. Direct REST call. | **no** |
| `om chart refresh --workspace <id>` | Read the LIVE workspace snapshot: force a fresh `STATE_SYNC` from the gateway and print it (charts, viewport, theme, version). | yes |
| `om chart show <id>` | Read **any** workspace's content by short id or share-link URL, WITHOUT joining a live session. Direct REST call; read-only; does not change the active workspace. | **no** |
| `om chart open <id>` | Open the workspace's LIVE view (`?live=true`) in this machine's browser; `--wait-human <ms>` blocks until a viewer joins the session (or the wait elapses). Use before the first mutation when nobody is watching — see "Make chart actions visible" below. | for `--wait-human` |

Use `om chart list` for first-run sanity ("does the key work against the gateway?") and to resolve a user-named workspace ("my BTC playground") to its `id`.

`om chart show` is the static, no-session read: use it when the user points you at a SPECIFIC workspace the daemon isn't connected to (a short id or a `openmarket.xyz/chart/<id>` link) and asks you to look at it. For the daemon's CURRENT active workspace, use `om chart refresh` (live) instead.

> **⚠️ Always read CURRENT state before you answer about — or act on — a chart: `om chart refresh`.**
>
> The user can edit the chart manually at any time. Edits made inside a **live session** (the `?live=true` view) do reach the daemon — `om chart status` flips `stateStale: true` — but edits made in the **plain chart UI** (no live session) bypass the bridge entirely: they persist straight to the workspace backend with no push, so any snapshot you hold goes stale with **no signal**. Your conversation transcript is stale in both cases.
>
> **`om chart refresh --workspace <id>` reads fresh from the source of truth.** Run it:
> - before **answering any question** about what's on the chart (indicators, symbol, interval, drawings) — *including* before refusing ("there's no RSI") — your last read may predate a manual edit;
> - immediately before **any persisting action** whose correctness depends on current state — picking a chart by symbol, choosing an indicator/drawing `id` to update or remove, computing drawing anchors from candles.
>
> Do not reuse a prior read across turns or across a mutation — re-`refresh` each time. The cost is one ~10–100ms round-trip and it eliminates the entire "agent acted on a stale snapshot" class of bug.

Use `om chart refresh` to answer ANY question about what's currently on a chart. The `workspace.*` payload is opaque pass-through from the gateway's store — read whatever field names actually appear in the JSON; do not invent. Useful traversal:

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

### Pane and layout mutations

| Command | Wire action | Persistence | Requires daemon |
| --- | --- | --- | --- |
| `om chart view` | `SET_VISIBLE_RANGE` | ephemeral (broadcast only) | yes |
| `om chart symbol` | `update_symbol` | persisting | yes |
| `om chart interval` | `update_interval` | persisting | yes |
| `om chart plot-type` | `update_plot_type` | persisting | yes |
| `om chart layout` | `update_layout` | persisting | yes |
| `om chart sync` | `update_sync` | persisting | yes |

All six verbs are wired. The per-pane verbs (`view`, `symbol`, `interval`, `plot-type`) accept `--chart <n>` (0-based) for multichart workspaces — chart 0 is the primary pane, chart 1+ are the multichart sub-cells (read them from `multiCharts.workspaces[N-1]` in the refreshed workspace snapshot). `layout` and `sync` are workspace-global and take no `--chart`.

#### `om chart view` — pan / zoom

```bash
om chart view \
  --workspace <workspaceId> \
  --chart 0 \
  --start 1762000000 \
  --end 1762086400 \
  --at 1762043200
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--chart <n>` | optional (default `0`) | Chart pane index. |
| `--start <epochSec>` | yes | Integer epoch seconds. |
| `--end <epochSec>` | yes | MUST be strictly greater than `--start`. |
| `--at <epochSec>` | yes | Cursor timestamp within `[--start, --end]`. |
| `--narration <text>` | optional | Operator-visible narration. |

Successful JSON has `version: 0` — the ephemeral sentinel.

#### `om chart symbol` — switch symbol/exchange

```bash
om chart symbol \
  --workspace <workspaceId> \
  --chart 0 \
  --symbol ETHUSDT \
  --exchange BINANCE_FUTURES
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--chart <n>` | optional (default `0`) | Chart pane index — use `--chart 1`, `--chart 2`, … to target a specific multichart cell. |
| `--symbol <s>` | yes | Wire symbol (`BTCUSDT`, `ETHUSDT`, `SOLUSDT`, …). |
| `--exchange <e>` | yes | Wire exchange (`BINANCE_FUTURES`, `BINANCE`, `BYBIT`, `COINBASE`, `HYPERLIQUID_FUTURES`, …). |
| `--coin <c>` | optional | Coin symbol (`BTC`, `ETH`, …). |
| `--transformations <t>` | optional | Lookup key — defaults to `<exchange>\|<symbol>` if omitted. |
| `--display-transformations <t>` | optional | Display key — defaults to `--transformations` if omitted. |
| `--narration <text>` | optional | Operator-visible narration. |

#### `om chart interval` — switch timeframe

```bash
om chart interval \
  --workspace <workspaceId> \
  --chart 0 \
  --interval 1m
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--interval <tf>` | yes | Supported: `1s`, `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, `1M`, `3M`, `1Y`. The data-plane names (`MINUTE`, `HOUR`, `DAY`, ...) are accepted and normalized to these. **Short forms are case-sensitive: `1m` is minutes, `1M` is months.** |

`1s` requires Plus tier; everything else is on free.

#### `om chart plot-type` — switch candle/line/area/…

```bash
om chart plot-type \
  --workspace <workspaceId> \
  --chart 0 \
  --type heikinAshi
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--type <type>` | yes | `candle`, `hollowCandle`, `heikinAshi`, `line`, `spline`, `area`, `baseline`, `ohlcBar`. |

#### `om chart layout` — switch the multi-chart grid

```bash
om chart layout \
  --workspace <workspaceId> \
  --mode 4
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--mode <mode>` | yes | `1` (single), `2H`/`2V` (two panes, horizontal/vertical split), `3H`/`3V` (three panes), `4` (2x2 grid). |
| `--narration <text>` | optional | Operator-visible narration. |

**Grid dimensions ARE layout requests.** When the user gives a grid like `3x1`, `1x3`, `2x2`, `2x1`, `1x2`, or phrases like "three across", "split into 2", "stacked", "quad", "2 by 2" — that is a `chart layout` change. Read the grid as **columns × rows** (matching the layout picker: "3 × 1" = 3 columns side by side). Map to `--mode`:

| User says | Panes | `--mode` |
| --- | --- | --- |
| `1`, `1x1`, "single", "one chart" | 1 | `1` |
| `2x1`, "two across", "side by side", "two columns" | 2 | `2H` |
| `1x2`, "two stacked", "top/bottom", "two rows" | 2 | `2V` |
| `3x1`, "three across", "three columns" | 3 | `3H` |
| `1x3`, "three stacked", "three rows" | 3 | `3V` |
| `2x2`, "grid", "quad", "four charts" | 4 | `4` |

Standard layout tops out at **4 panes (2x2)**. A bigger grid (`3x3`, `4x4`, anything > 4 panes) is **Monitor mode**, which the agent cannot set — tell the user to switch to Monitor in the chart UI's layout picker.

Workspace-global — no `--chart`. Growing the grid appends new panes that inherit chart 0's symbol/exchange/interval (1:1 with a manual layout change); shrinking keeps the extra panes persisted and paints only the mode's count. On a monitor-grid (multimode) workspace the frontend exits monitor mode first, then applies the standard layout. Free tier caps at 2 panes; 3+ requires Plus.

**Set the layout BEFORE per-pane symbols.** If the user wants a multi-pane layout AND specific symbols per pane (e.g. "3x1 with BTC, XRP, SOL"), the layout change must land first — the new panes don't exist until then, so a `chart symbol --chart 2` issued before the grid grows fails with `chartIndex 2 out of range`. See the workflow under "User asks for a grid layout with specific symbols" below.

#### `om chart sync` — toggle multi-chart sync (symbol / interval / crosshair)

```bash
om chart sync \
  --workspace <workspaceId> \
  --key symbol \
  --enabled
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--key <key>` | yes | `symbol`, `interval`, or `crosshair` — one setting per call. |
| `--enabled` / `--no-enabled` | yes | Pass one: `--enabled` turns the setting on, `--no-enabled` turns it off. |
| `--narration <text>` | optional | Operator-visible narration. |

Workspace-global — no `--chart`; the sync master is the primary pane (chart 0). Enabling `symbol` or `interval` sync makes every pane follow chart 0 (the server propagates chart 0's symbol/interval onto the other panes). One key per call — to toggle two settings, issue two commands.

**Sync awareness.** Before changing a per-pane symbol or interval, check `multiCharts.syncStatus` in the refreshed workspace snapshot. If `syncStatus.symbol` is `true`, every pane shows ONE symbol — a per-pane `chart symbol` won't give panes different symbols; it changes the symbol for all of them. If the user asks for different symbols per pane while symbol sync is on, tell them sync is on and ask whether to turn it off first (`chart sync --key symbol --no-enabled`) or pick one symbol for all panes. Same for `syncStatus.interval`. On a monitor-grid (multimode) workspace only `crosshair` sync is togglable via the agent; symbol/interval sync is fixed by the grid.

#### NO_CHANGE response (the persisting verbs)

If the requested value already matches the persisted state (e.g. `chart symbol --symbol BTCUSDT` on a chart already on BTCUSDT), the CLI prints `No change — <field> is already '<value>'` and exits 0. No theater fires on the chart UI. Treat NO_CHANGE as informational — don't retry, don't surface as an error.

### `om chart indicator` — indicator lifecycle

| Command | Wire action | Requires daemon |
| --- | --- | --- |
| `om chart indicator add` | `add_indicator` | yes |
| `om chart indicator remove` | `remove_indicator` | yes |
| `om chart indicator update` | `update_settings` | yes |
| `om chart indicator list` | local (read-only) | no |

All verbs are wired. `--chart <n>` selects the multichart cell.

**Discovery first.** `om chart indicator list [--query <token>]` prints every addable
type from the local registry — canonical key, display name, placement
(onchart/offchart), friendly aliases, and whether it is single-instance. Run it
whenever the user names an indicator you cannot map to a `--type` value; do not
guess. It needs no daemon.

```bash
om chart indicator add \
  --workspace <workspaceId> \
  --chart 0 \
  --type RSI \
  --params '{"period":14}'
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--chart <n>` | optional (default `0`) | Chart pane index — `0` for the primary, `1`+ for multichart cells. |
| `--type <type>` | yes | Indicator type — see normalization table below. The CLI auto-normalizes user-friendly names; canonical registry keys also accepted. |
| `--params <json>` | optional (default `{}`) | Indicator settings as a JSON object. Shape is per-indicator. |

**Indicator type normalization.** The CLI normalizes the `--type` argument before sending. Both shorthand (`RSI`, `liquidations`, `funding`) and canonical (`TECHNICAL_SCRIPT`, `LIQUIDATIONS`, `AGGREGATED_FUNDING_RATE`) work:

| User-friendly input | Normalized to | Notes |
| --- | --- | --- |
| `RSI`, `MACD`, `EMA`, `SMA`, `BB`, `ATR`, `ADX`, `CCI`, `Stoch`, `OBV`, `MFI`, `Ichimoku`, `Supertrend`, … (~30 TA scripts) | `TECHNICAL_SCRIPT` + `settings.subType: '<NAME>'` | Standard chart-engine script indicators. Free tier. |
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

Typical `--params`:

| `--type` | Typical `--params` |
| --- | --- |
| `RSI` | `'{"period":14}'` |
| `MACD` | `'{"fast":12,"slow":26,"signal":9}'` |
| `EMA` / `SMA` | `'{"length":50}'` |
| `BollingerBands` | `'{"length":20,"stddev":2}'` |
| `ATR` | `'{"period":14}'` |
| `Stochastic` | `'{"period":14,"smoothing":3}'` |
| `Liquidations` | `'{}'` |

**Every registry native is addable.** The table above covers common shorthands only; ALL ~80 registry types (`om chart indicator list`) work as `--type` values — exact keys win over aliases, any casing accepted. A handful of interaction-only overlay types are excluded from the agent path and rejected with a clear error. If the user names an indicator not in the list output, submit anyway — the CLI's normalization layer or the server validator will return a clear `VALIDATION` error if it's unsupported. Do not silently substitute.

**Minimal params contract.** Send only the settings the user explicitly asked to change (period, funding interval, value area, ...). The chart fills every other default client-side — theme colors, widths, market identity from chart context. Do NOT invent colors or cosmetic settings unless asked. Setting keys outside the shared whitelist are dropped server-side and echoed back in the response `warnings` field — if a key you sent shows up there, it was ignored, not applied; tell the user rather than retrying blindly.

**Single-instance types.** Types flagged `single-instance` in `indicator list` (heatmaps, volume profiles, footprint) allow one instance per chart; a duplicate add returns `409 NO_CHANGE` with the existing overlay id. Treat that as "already there", not an error to retry.

**Removing an indicator** — prefer `--type` whenever the user names the indicator; it removes EVERY matching overlay on the pane and needs no id round-trip:

```bash
om chart indicator remove \
  --workspace <workspaceId> \
  --chart 0 \
  --type CME_OI          # registry key, alias (funding, heatmap, ...), or script subtype (RSI)
```

- Absent type / empty pane → `409 NO_CHANGE` ("already gone") — treat as success, do not retry.
- "Remove ALL indicators" → `--every-indicator` (clears the whole pane; hidden system overlays are kept). Whole workspace = `--every-indicator` once per `--chart` index (0..N-1).
- "Remove X from all charts" → the same `--type` command once per `--chart` index; `NO_CHANGE` on panes that never had it is expected.
- NEVER call `indicator add` while trying to remove; if you lack information, use `--type`/`--every-indicator` (no id needed) or read state first.

`--id <indicatorId>` remains for exact-id removal (id from the add response or `om chart refresh`). The server filters BOTH `onchart` and `offchart` (overlayType-aware — a drawing sharing the id is preserved). Id path: `VALIDATION` error if the id isn't found on the target chart.

**Tuning indicator settings** by overlay id — settings replace the persisted object verbatim (not merged). Read existing settings from `om chart refresh`, modify the keys you want, and pass the full result:

```bash
om chart indicator update \
  --workspace <workspaceId> \
  --chart 0 \
  --id <indicatorId> \
  --params '{"period":21,"overbought":75,"oversold":25}'
```

### `om chart drawing` — drawing lifecycle

| Command | Wire action | Requires daemon |
| --- | --- | --- |
| `om chart drawing auto` | `add_drawing` | yes |
| `om chart drawing add` | `add_drawing` | yes |
| `om chart drawing schema` | (local, read-only) | no |
| `om chart drawing remove` | `remove_drawing` | yes |

**Drawing tools have their own detail file → read [`chart-actions-tool-drawing.md`](chart-actions-tool-drawing.md).**
It covers every Super Search tool (lines, shapes/ranges, fibonacci, arrows, markers, positions,
annotations), `drawing auto` (anchors computed from market data — preferred), `drawing add`
(caller-supplied role-tagged `--anchor`s), `drawing schema` (discover a tool's anchor roles), and
`drawing remove`. Read it before drawing, adding, or removing any chart tool.

## Workflows

### User asks "is my orchestrator/bridge connected?"

Run `om chart status`. Interpret as in the table above; answer in one sentence.

### User asks "what workspaces do I have?"

Run `om chart list`. Render each as `<name> (id: <id>)` if name is present, else just `<id>`. Don't dump raw JSON to the user.

If the response is empty, say so plainly: *"No workspaces under this API key."*.

### User asks "what workspace am I / are you on?"

Run `om chart status` and report the `open` (else `workspaces[0]`) `workspaceId` — that's the workspace the daemon is connected to and where chart-actions land. Map it to a friendly name with `om chart list` if helpful. **Do not say you "aren't on a workspace"** — the daemon always has an active one. The answer changes after the user runs `/workspace`, so always read it live; never answer from memory of an earlier turn.

### User asks "what's on my workspace?" / "what's on chart 0?" / "what indicators are on the chart?"

Two steps:

1. **Resolve the workspace id — re-resolve EVERY turn, never reuse a prior turn's id.**
   - If the user named one by id, use it.
   - If they used a friendly name (*"my BTC playground"*), run `om chart list` first to map name → id.
   - If they didn't name one, the target is **the daemon's ACTIVE workspace** — run `om chart status` and take the `open` entry in `workspaces[]` (else `workspaces[0]`). This is the source of truth for "my workspace" / "this workspace" / "what do you see". It **changes when the user runs `/workspace`**, so a workspace id you resolved on a previous turn may now be wrong — resolve it fresh here, do not carry one over.
2. **Run `om chart refresh --workspace <id>`** and answer from the JSON.

Never answer "what's on my chart / workspace" from `om chart list` (that only enumerates all workspaces — it doesn't say which one is active or what's on it), and never tell the user you aren't on any workspace: the daemon is always connected to one, and `om chart status` reports it.

> **⚠️ This applies to MUTATIONS too, not just questions.** When the user says "add RSI", "switch to SOL", "draw a trendline" without naming a workspace, the `--workspace <id>` you pass MUST be the daemon's active workspace resolved *this turn* from `om chart status`. **Never reuse a workspace id from earlier in the conversation** — the user may have run `/workspace` since (a switch you don't see in the transcript), so an id you "remember" can silently mutate the workspace they just left. Resolve the active id first, then act.

Reading rules:

- **Quote actual values, not types.** *"BTCUSDT on Binance Futures, 1h"* — pull the specific values from `workspace.charts[0]`. Don't say *"chart 0 has a symbol selector"*.
- **Humanize enums** per the table below.
- **One short answer per question.** Don't tail with the full workspace JSON.

### User asks "did anything change since last time?"

Track the `version` field. Re-run `om chart refresh`; if `version` is higher, diff the relevant sub-tree against the prior snapshot.

### User asks for a grid layout (with or without per-pane symbols)

Triggers: any grid dimension (`3x1`, `1x3`, `2x2`, `2x1`, `1x2`) or layout phrasing ("three across", "split into two", "stacked", "quad", "2 by 2"). This is the `om chart layout` path — see the grid→`--mode` table above.

**Order matters — layout first, then symbols.** A combined request like *"change to 3x1 with BTC, XRP, SOL"* is ONE layout change plus per-pane symbol sets, in this exact order:

1. **Resolve the workspace id** (same default rules as above).
2. **Change the layout once** — map the grid to `--mode` and call `om chart layout --mode 3H`. This grows the workspace to 3 panes; the new panes inherit chart 0's symbol.
3. **Then set each pane's symbol once**, lowest index first: `chart symbol --chart 0 --symbol BTCUSDT`, `--chart 1 --symbol XRPUSDT`, `--chart 2 --symbol SOLUSDT`. Chart 0 already holds the primary symbol and new panes inherit it — only issue a `chart symbol` for a pane whose target differs from what's already there. Map the symbols to panes in the order the user listed them.
4. **One brief preview is enough** — don't confirm each pane separately.

**Never loop. NO_CHANGE and out-of-range are terminal, not retryable:**

- `No change — symbol is already 'X'` → that pane is **already correct**. Treat as done. Do NOT re-issue it.
- `chartIndex N out of range (have M charts)` → pane N **doesn't exist yet**. This means the layout step didn't run or didn't grow enough panes. Run `chart layout` to the right mode FIRST, then set that pane **once**. Do NOT retry the `chart symbol` against the missing pane.

If you ever find yourself issuing the same `chart symbol` call a second time, stop — you are looping. Re-read current state with one `chart_refresh`, then act on the diff only.

### User asks to seek / pan / zoom

This is the `om chart view` path — ephemeral viewport change, broadcasts to peers, no persistence.

1. **Parse the target time range** (*"last 24h"*, *"yesterday"*, *"the hour around 2026-05-15 14:00"*).
2. **Resolve the workspace id** (same default rules as above).
3. **Compute `--start`, `--end`, `--at`** in integer epoch seconds. The cursor MUST lie within `[start, end]` — derive missing flags sensibly.
4. **One-liner preview + confirm** (low-stakes since ephemeral):

   > *Set chart 0 to view 2026-05-19 → 2026-05-20 (cursor at midday). Ephemeral, no persistence. OK?*

5. **Execute** `om chart view ...`. Success response has `version: 0` — expected, not an error.

### User asks to add an indicator

Five-step flow:

1. **Parse intent** — extract `--type`, chart pane, and params if named.

2. **Resolve the workspace id** (same default rules).

3. **If chart pane isn't named, default to chart 0**; the user can correct in a follow-up.

4. **If params aren't named, ask once via the structured-question tool.** Bundle all knobs into one question per indicator. Skip if the user already specified them.

   Example — RSI:
   > Question: *"Which lookback period for RSI?"*
   > Options: *14 (recommended)* / *7 (faster)* / *21 (slower)* / *Other*

   Example — MACD:
   > Question: *"Which MACD preset?"*
   > Options: *12/26/9 (recommended)* / *8/21/5 (faster)* / *5/35/5 (slower)* / *Other*

5. **Plain-language preview + confirm.**

   > *Add indicator to chart:*
   > - *Workspace: BTC playground*
   > - *Chart: 0 (BTCUSDT on Binance Futures, 1h)*
   > - *Indicator: RSI, period 14*
   >
   > *OK to add?*

6. **Execute** `om chart indicator add ...`.

   - On `ok: true` → *"Added RSI(14) to chart 0 — version `<N>`."*
   - On `code: "VALIDATION"` → surface the server detail verbatim; most often unsupported `--type`.
   - On `code: "FORBIDDEN"` → *"The API key doesn't own this workspace. Pick one from `om chart list`."*

### User asks to draw / add / remove a chart tool

Drawing tools (trendlines, fibs, shapes, arrows, markers, positions, annotations) have their own
detail file → read [`chart-actions-tool-drawing.md`](chart-actions-tool-drawing.md) for the full
workflow. In short: **default to `om chart drawing auto`** (it computes anchors from market data);
use `om chart drawing add --anchor <role>=<epochSec>:<price>` only when the user named exact
price/time levels (run `om chart drawing schema <tool>` for the roles).

Span tools (LongPosition/ShortPosition/PositionForecast, Rectangle/Ellipse, Price/Date ranges,
FixedRangeVolumeProfile) get their WIDTH from the anchor time span: anchor target/stop or the
second corner at least 2 bars AFTER the first anchor, or the shape paints as an invisible
zero-width sliver (the verb refuses such calls and names the required span). `drawing auto`
is immune: its computed swing anchors are always time-separated.

### The user edits the chart too — offer alerts on drawn levels

Live-session manual edits stream to the daemon. `om chart events --workspace <id>` lists them oldest-first; each drawing event's `data.tool.points` carries exact `{ time, price }` anchors. When the user just placed a line/level tool (HorizontalLine, TrendLine, a Fib level they call out) and the conversation touches the chart, offer ONCE to arm a price alert at that level — quote the price, ask, and only create it on a yes (alerts skill). Don't propose alerts for annotation/cosmetic tools (Text, Note, arrows, emoji), and don't repeat the offer if they pass.

### Read-only (VIEWER) workspaces

A user can join **someone else's** live session by short id with `/workspace join <short-id>`. The
role is assigned by the server from the API-key identity: **HOST** if they own that workspace,
**VIEWER** if they don't. `chart_status` reports the active workspace's `role`.

When `role` is **`VIEWER`**:

- **Reads work normally** — answer "what's on the chart?" etc. from `chart_refresh` as usual; you see the host's live chart.
- **Writes are blocked** — every chart mutation (indicator/drawing/symbol/interval/plot-type/layout/sync add·remove·update) is refused locally (`FORBIDDEN`) and server-side. Don't attempt them.
- If the user asks for an edit, say briefly: *you're viewing this workspace read-only and can't modify a workspace you don't own.* (Proposing changes for the owner to approve is not available yet.)

When `role` is `HOST`/`CO_HOST` (or absent — your own workspace), chart actions work as normal.

## Make chart actions visible — presence-aware live view

Watching the agent drive the chart live (ghost cursor, narration) is the primary feedback loop for chart-actions. Whether the user is watching is REPORTED, not guessed: `om chart status` → `humanPresent` on the active workspace. Theater a viewer misses is NOT replayed — a late joiner only gets the end state — so seat the audience BEFORE mutating, not after.

Decide by presence and surface:

- **`humanPresent: true`** — the user (or another viewer) already has the live chart open. Just act. Don't print the live link.
- **`humanPresent: false`, local CLI surface** — before this conversation's FIRST chart mutation, run `om chart open <id> --wait-human 10000` (action: `chart_open`). It opens `https://openmarket.xyz/chart/{workspaceId}?live=true` in the user's browser and waits for them to land, then your mutations play visibly. Do this once per conversation; if the user declines or told you to stop, don't repeat it. On a headless box it opens nothing (`opened: false`) — fall through to sharing the URL.
- **`humanPresent: false`, remote surface (Telegram/Discord/web)** — never spawn a browser; after the mutation's success summary, share this once, on its own line:

  > To experience your AI Agent working on your chart, head to https://openmarket.xyz/chart/{workspaceId}?live=true

  Substitute `{workspaceId}` with the actual id. One link per turn at most; don't re-send while `humanPresent` is true, after a failed action, or once the user has said to stop.

## The blackboard — attributed marks, peers, and receipts

The canvas is shared. Three read surfaces keep you honest about what is on it and who put it there:

- **`om chart drawing list --workspace <id>`** (action: `chart_drawing_list`) — the drawings on the live chart, oldest first, with the `drawingId` that `chart_drawing_remove` needs, its author (`self` = you, `peer <peerId>` = another agent, `human`, or `unknown` when the daemon never observed the add), and the author's stated reason when one was given. Membership comes from the live workspace document (the same store removes are verified against, so every `presence: "live"` id is removable); author/reason comes from what the daemon observed while attached. Use it before drawing (don't duplicate what exists), when asked to clean up ("remove that line" needs its id), and to read what another agent has argued on the chart. Pass `includeRemoved` to also see marks the daemon once observed that are no longer on the live chart (`presence: "ledger-only"`), each with the `transformation` (market) it was drawn on: a pane whose symbol changed hides its old marks rather than deleting them.
- **`om chart events`** (action: `chart_events`) — now split by author: `events` are the human's manual edits; `peerEvents` are other agents' edits, each with its peer id and quoted narration. When `activePeerRun` is present, another agent is mid-performance: prefer reads over writes until it ends (your own submits briefly auto-wait for the floor and warn if they proceeded during a peer run).
- **`om nervous status`** (action: `nervous_status`) — the nervous system's audit trail: event-driven chart moments (news watch fires, alert fires, strategy entries/exits) that were expressed on the chart without anyone asking, each with a story, per-verb outcomes, and the live view link. After an alert or news fire, check it before replying so you can tell the user what was already marked and hand them the link instead of re-drawing it.

Every drawing you add returns its `drawingId` — keep it if you may need to adjust or remove that mark later in the conversation.

When you draw as part of a disagreement or a joint analysis with another agent, put your reasoning in the mark itself: a `narration` on every mutation, and Callout/Text/Note content that states the claim. Peers and humans read the chart, not your private chain of thought.

On-chart text renders as a SINGLE unwrapped line: keep Callout/Text/Note content to a short phrase (a side tag plus a handful of words) and put the full argument in the session chat or the narration. Place annotations inside the currently visible time range (read the viewport from the refreshed workspace snapshot) — a mark the audience cannot see argues nothing. Text marks must never overlap: before placing Callout/Text/Note, read the existing marks' anchors (chart_drawing_list) and choose a spot clearly separated in time and price from every other text mark.

## Behaviors to avoid

- **Do not surface infrastructure concerns proactively.** The `OM_API_KEY` is captured by `om init` (settings DB): only mention it if a `UNAUTHORIZED` error points there. The collab gateway URLs default to the hosted relay; `OM_COLLAB_REST_URL` / `OM_COLLAB_WS_URL` / `OM_CHART_URL` are documented env vars (docs/USER_GUIDE.md, "Environment variables") for self-hosted or alternate relays. Bring them up only when the user asks about self-hosting, a local relay, or pointing at a different chart deployment, never as troubleshooting for the hosted service.
- **Do not call `om chart list` when the user only asked about the default workspace.** The id is in `om chart status` already — one round-trip is cheaper than two.
- **Do not retry `no_state_sync` more than 2–3 times.** If STATE_SYNC hasn't landed within ~10 seconds, something is wrong server-side.
- **Do not assume the `workspace.*` JSON shape.** Pass-through from service. Read what's actually there; don't invent field names.
- **Do not invent `om chart` subcommands.** Wired verbs:
  - `status`, `events` (the multiplayer session verbs `session say` / `session start` / `session end` exist only when the operator opted in with `OM_CHART_MULTIPLAYER=1`; never suggest them otherwise)
  - `list`, `create` (new workspace by name + symbol/exchange/interval; find-or-create, so re-running with the same name reuses it), `delete`, `keep` (promote a scratch workspace to permanent), `show`, `refresh`, `screenshot`, `open`
  - `view`, `symbol`, `interval`, `plot-type`, `layout`, `sync`
  - `pins` (the events lane; doctrine in `news.md`, "Plotting events on charts")
  - `indicator list`, `indicator add`, `indicator remove`, `indicator update`
  - `drawing auto`, `drawing add`, `drawing schema`, `drawing remove`
  - Anything else (e.g. a drawing update) doesn't exist: fall back to the chart UI and tell the user honestly.
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

| User asks for | Honest response |
| --- | --- |
| Freehand brush / pencil | *"Freehand drawing isn't agent-drawable (no computable values). Use a shape, line, or annotation tool instead, or draw it in the chart UI."* |
| Watch the workspace live / stream changes | *"`om chart refresh` is point-in-time. There's no streaming subcommand yet — poll it."* |
| Author changes for someone else's workspace | *"The retail API key only authorizes workspaces its owner owns. Pick one from `om chart list`."* |
| Authenticate as a different user | *"Re-run `om init` to capture a new API key, then `om service restart` so the daemon picks it up."* |

## Errors

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
- `no_state_sync` → retry once or twice with a short delay. If persistent, check `om chart status`.
- `UNAUTHORIZED` → API key bad or revoked. Re-run `om init` and `om service restart`.
- `FORBIDDEN` → key's user isn't the workspace owner. Use `om chart list` to find one they own.
- `VALIDATION` on a mutation → server didn't accept the envelope. Surface the detail verbatim; let the user correct.

## Quick recipes

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

# 8. Tune existing indicator settings (replaces verbatim — pass full settings).
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

## Multichart support

Every persisting verb accepts `--chart <n-or-symbol>` — either a **numeric chart index** (`--chart 0`, `--chart 1`) OR a **symbol name** (`--chart ETHUSDT`, `--chart ETH`). When a symbol is passed, the CLI resolves it to the right chartIndex by reading the workspace's cached state — no need to guess which pane holds which symbol.

**Preferred: pass `--chart <SYMBOL>` when the user names a coin.** When the user says "draw a trendline on the ETH chart", the right call is:

```bash
om chart drawing add --workspace <workspaceId> --chart ETHUSDT --tool TrendLine
```

NOT `--chart 0` and NOT `--chart 1` — those are guesses that misroute when the user's multichart layout doesn't match the agent's assumption. The CLI does an O(1) lookup against `workspace.metadata.symbol` (for the primary pane) and `multiCharts.workspaces[*].metadata.symbol` (for sub-cells), so symbol resolution is reliable.

Resolution rules:
- **Numeric input** (e.g. `--chart 1`) — passed through as-is, no workspace fetch.
- **Exact symbol match** — `--chart ETHUSDT` → the chart whose `metadata.symbol === 'ETHUSDT'`.
- **Prefix match** — `--chart ETH` → the chart whose symbol starts with `ETH`, when exactly one matches.
- **Multiple matches** — CLI errors with a clear "ambiguous, pass numeric index" message. No silent default to chart 0.
- **No match** — CLI errors listing the available charts so the AI can correct.

Index semantics (when you DO pass a number):
- `--chart 0` is the primary pane (hoisted to the workspace's top-level `onchart` / `offchart` / `metadata`).
- `--chart 1`, `--chart 2`, … target multichart sub-cells in `multiCharts.workspaces[N-1]`.
- `multiCharts.workspaces.length` from `om chart refresh` tells you how many cells exist.

Multichart cells are limited to **2 indicators per cell** (a separate cap from `indicatorsPerChart`). Adding more returns a `VALIDATION` error.

---

## For contributors

The wire contract lives in code, not a standalone doc: envelope shapes in `packages/cli/src/runner/collab/types.ts`, envelope validation in `packages/cli/src/runner/collab/validators.ts`. Bridge code under `packages/cli/src/runner/collab/`. Agent-facing CLI in `packages/cli/src/cmd/collab.ts`. Loopback RPC handlers in `packages/cli/src/runner/http/rpc/collab.ts`. Skill registration in `packages/cli/src/skills/package.ts`.

**Adding a new verb under a resource group:** find the resource's `registerXCommands(collab)` function in `cmd/collab.ts`, add a new `.command("...")` under the group, and post the appropriate `action` / `data` / `intent` shape to `collabRpc("submit", ...)`. The bridge's `validateEnvelope` (`runner/collab/validators.ts`) is the safety net; the server's controller is the authority.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om chart create` (action: `chart_create`) — Create a chart workspace with a clean template (your name, symbol, exchange, and interval; no inherited indicators), REST direct so it works even when the daemon is down.
- `om chart delete` (action: `chart_delete`) — PERMANENTLY delete chart workspaces (REST direct through the collab gateway).
- `om chart events` (action: `chart_events`) — Recent edits on the live session, oldest first, split by author.
- `om chart indicator add` (action: `chart_indicator_add`) — Add a technical indicator or WRUN marketplace indicator (RSI, MACD, EMA, LIQUIDATIONS, wrun/@scope/name/output, ...) to a chart pane.
- `om chart indicator list` (action: `chart_indicator_list`) — List every indicator type addable via `chart_indicator_add`: canonical keys, friendly aliases, chart placement, and single-instance rules.
- `om chart indicator remove` (action: `chart_indicator_remove`) — Remove indicator overlays from a chart pane.
- `om chart indicator update` (action: `chart_indicator_update`) — Tune an existing indicator's settings.
- `om chart interval` (action: `chart_interval`) — Change a chart pane's candle interval (1m, 5m, 15m, 1h, 4h, 1d, 1w, ...).
- `om chart keep` (action: `chart_keep`) — Keep the current scratch chart under a name.
- `om chart layout` (action: `chart_layout`) — Change the multi-chart layout / grid.
- `om chart list` (action: `chart_list`) — List workspaces accessible to the configured collab API key (REST direct — works even when the daemon is down).
- `om chart open` (action: `chart_open`) — Open a workspace's live chart view (openmarket.xyz/chart/<id>?live=true) in a browser on this machine, and optionally wait for a human viewer to join the session.
- `om chart plot-type` (action: `chart_plot_type`) — Change a chart pane's plot type (candlestick, line, bar, area, ...).
- `om chart refresh` (action: `chart_refresh`) — Read the LIVE workspace state by issuing REQUEST_STATE_SYNC over the bridge WS and returning the fresh snapshot.
- `om chart screenshot` (action: `chart_screenshot`) — Render a PNG snapshot of a workspace by short id or share-link URL.
- `om chart show` (action: `chart_show`) — Read a workspace's content (symbol, interval, indicators, drawings, layout) by its short id or share-link URL, WITHOUT joining a live session.
- `om chart status` (action: `chart_status`) — Report the collab bridge's WS state, peerId, and pending intent counts for every active workspace.
- `om chart symbol` (action: `chart_symbol`) — Change a chart pane's symbol (e.g. BTCUSDT on BINANCE.F → ETHUSDT on BINANCE.F).
- `om chart sync` (action: `chart_sync`) — Toggle a multi-chart sync setting: symbol / interval / crosshair.
- `om chart view` (action: `chart_view`) — Set the visible time range on a chart pane (SET_VISIBLE_RANGE — ephemeral, no persist).

- `om nervous status` (action: `nervous_status`) — Recent nervous-system receipts, newest first: event-driven chart moments (news, alert, and strategy fires) with a story, per-verb outcomes, and the live view link; skipped ones carry the reason.

<!-- AUTO: END COMMAND REFERENCE -->
