---
name: openmarket-chart-actions-tool-drawing
description: Draw, auto-draw, inspect, and remove chart drawing tools on a chart workspace via `om chart drawing ...`. Covers every Super Search drawing tool — trend/ray/parallel lines, rectangles/ellipses, fibonacci retracement & trend, arrows (Momentum/Flow/…), markers, price/date ranges, long/short positions, and text annotations. Read this when the user asks to draw / add / place a tool on a chart, mark a level, box a range, annotate, plot a fib, set up a long/short position, or remove a drawing. `drawing auto` computes trader-meaningful anchors from market data; `drawing add` takes caller-supplied role-tagged anchors; `drawing schema` lists a tool's anchor roles. Companion to `chart-actions.md` (the broader `om chart` bridge).
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om chart drawing

Drawing-tool lifecycle for the Collab Service Bridge. These verbs add, auto-draw,
inspect, and remove chart drawings on a workspace. For bridge health, workspace
state, chart symbol/interval/layout, and indicators, see `chart-actions.md`.

`drawing add` and `drawing remove` call the daemon but fall back to direct gateway REST
when it is down (`drawing auto` needs the running daemon; `drawing schema` is local).

Every drawing tool in the chart's Super Search palette is on the wire — lines, shapes/ranges, fibonacci, arrows, markers, positions, and annotations. Use the tool name as it appears in Super Search (e.g. `TrendLine`, `FibonacciRetracement`, `Rectangle`). On the chart, both `auto` and `add` render the same way: a ghost cursor opens **Super Search**, types the tool name, arrows to the tool row, and draws at the anchors.

### Guardrails

The mutating verbs target a pane via `workspaceId` plus `chartIndex` (chart 0 is the primary pane).

**Prefer `chart_drawing_auto`.** It fetches recent candles and computes trader-meaningful anchors (swing highs/lows) itself, so you pick the symbol/interval — not raw coordinates. Reach for `chart_drawing_add` only when the user named exact price/time levels (e.g. "draw a fib from 90k to 100k").

### Routing

| Command | Wire action | Requires daemon |
| --- | --- | --- |
| `chart_drawing_auto` (`om chart drawing auto`) | `add_drawing` | yes |
| `chart_drawing_add` (`om chart drawing add`) | `add_drawing` | falls back to gateway REST when down |
| `chart_drawing_schema` (`om chart drawing schema`) | (local, read-only) | no |
| `chart_drawing_remove` (`om chart drawing remove`) | `remove_drawing` | falls back to gateway REST when down |
| `chart_drawing_list` (`om chart drawing list`) | (live session read) | yes |

## `chart_drawing_auto` — anchors computed from market data (preferred)

Pick the tool and the pane's market (symbol/exchanges/interval); anchors come from swings — widen `lookback` on "not enough candles"; `direction`/`strength` only when named.

This verb computes the anchors for you — you never supply `anchors`; that is what separates it from `chart_drawing_add`.

Five fields the schema does not explain:

- `interval` is the **data-plane** enum, a different domain from `chart_interval`'s `1m`/`1h`/`1d` — the short forms are rejected here. Match the pane's timeframe. `THIRTY_MINUTES` is in the enum but the deployed data endpoint rejects it, and an explicitly passed interval is never rewritten for you, so use `FIFTEEN_MINUTES` or `HOUR` for a 30m pane, or omit `interval` and let the server default apply.
- `strength` is pivot strength — bars a swing must dominate on each side, default 3: **higher means fewer, more significant swings.** Raise it when the user asks for major swings only.
- `direction` omitted means the trend leg is inferred from the latest confirmed pivot; set it only when the user names a side.
- `searchTerm` defaults to the tool's own label; override it only when the label is not what the chart's search expects.
- `from` is the window start in epoch **seconds**. Omit it to let the server pick recent data.

## `chart_drawing_schema` — a tool's anchor roles (local, no daemon)

Role names and anchor counts per tool (`entry`/`target`/`stop`, `from`/`to`, `start`/`end`/`offset`, `point`) — call it before an unfamiliar `chart_drawing_add`.

Each tool's anchors carry tool-specific **roles**. `chart_drawing_schema` returns them (and the
count) straight from the registry, so a new tool documents itself the moment it ships.

Common role shapes: single-point tools (markers, levels, VerticalLine, annotations) take `point`;
lines take `start`/`end`; ParallelLine takes `start`/`end`/`offset`; arrows & fib-retracement take
`from`/`to`; FibonacciTrend takes `start`/`pivot`/`retracement`; Long/ShortPosition take
`entry`/`target`/`stop`; Path/ThreePaths repeat `point`. Roles are slotted into the correct order
for you, so the order you pass them does not matter.

## `chart_drawing_add` — explicit, role-tagged anchors

Role-tagged anchors, `anchors[].time` in epoch MILLISECONDS; sanity-check anchors in the loaded range, prices within ±10%; text on annotations only.

Pass one role-tagged anchor per point the tool needs. Neither surface auto-resolves a live price —
compute anchors from the current chart state first, and check `chart_drawing_schema` if you're
unsure of the roles. **`anchors[].time` is epoch MILLISECONDS** — the CLI's seconds-based form is
in §"CLI equivalents".
Worked tool call (times in ms — compute fresh, never reuse example epochs):

```jsonc
chart_drawing_add { "chartIndex": 0, "tool": "TrendLine", "anchors": [
  { "role": "start", "time": 1787270400000, "price": 94000 },
  { "role": "end",   "time": 1787356800000, "price": 96500 } ] }
```

When choosing anchor values:

- **Timestamps are integers, computed fresh — never copied from stale examples.**
- **Sanity-check the anchor falls in the loaded candle range.** Read `chart_refresh` (visible-range or candles array). Anchors far outside render off-screen even on `ok: true`.
- **Prices within ±10% of current.** Guessing prices that turn out to be stale is the leading cause of "the drawing landed but the chart looks empty".

Cross-field invariants the bridge enforces locally (mirrors the server-side checks):

- All anchors target the same `chartIndex`.
- `tool` is in the supported set; the supplied roles match the tool and the anchor count matches.
- Each anchor's `time`/`price` matches the input it came from (the bridge constructs both halves of the envelope from the same input — they cannot drift).

## `chart_drawing_remove` — delete a drawing by id

Remove by `drawingId` — ids read from a workspace refresh, strict `overlayType: "tool"` filter (indicators sharing the id survive), `VALIDATION` when the id is absent.

Read the `drawingId` from `chart_drawing_list` — it lists every observed drawing with the handle this verb needs (a `chart_refresh` snapshot also shows overlay ids with `overlayType: "tool"`).

The server filters strictly on `overlayType === 'tool'` so an indicator sharing the id is preserved. A `VALIDATION` error fires if the id isn't found.

Several drawings = ONE call with `ids` (`om chart drawing remove --id a --id b`): one card lists every member, the drawing list is read once for the whole set, and each member rides its own bridge intent, so a member that fails never voids the others.

Successful JSON output mirrors `chart_indicator_add`:

```jsonc
{
  "ok": true,
  "action": "remove_drawing",
  "version": 44,
  "transport": "rest",
  "tookMs": 287
}
```

## Workflow — user asks to draw a tool

Auto path: parse tool, resolve workspace and market, run. Add path (user-named exact levels only): schema roles, anchors, run; failures defined in §"Errors".

**Default to `chart_drawing_auto`** — it computes the anchors from market data so you don't have to resolve coordinates:

1. **Parse intent** — tool, chart, and (if mentioned) trend direction.
2. **Resolve the workspace id**, and the chart's symbol/exchange/interval (`chart_refresh`; `chart_show` when the user named the workspace).
3. **Execute** `chart_drawing_auto` with the tool, the pane's market identity, and its interval.
   - On `ok: true` → *"Drew a `<Tool>` on chart 0 — version `<N>`."*
   - On "not enough candles" → widen `lookback` or set `interval`.

Only when the user names **exact** price/time levels, use `chart_drawing_add`:

1. **Parse intent** — tool, chart, anchor hints.
2. **Resolve the workspace id.** If unsure of the tool's roles, check `chart_drawing_schema`.
3. **Resolve the anchors** as `(epochMilliseconds, price)` pairs, one per role. Strategies:
   - For specific bar timestamps, read the chart's viewport / OHLC from `chart_refresh` first.
   - For named price levels, the user usually gives the number directly.
   - For ambiguous anchors, ask via structured question — anchor errors are silent (the drawing lands on the wrong bar with no feedback).
4. **Execute** `chart_drawing_add` with the role-tagged anchors — no preview, no confirmation; name the anchors in human time + price in the outcome line.
   - On `ok: true` → *"Drew a `<Tool>` on chart 0 — version `<N>`."*
   - `CLIENT_VALIDATION` / server `VALIDATION` → the shapes and recoveries are defined in §"Errors".

## Errors

Pre-submit refusals return `ok: false` with `CLIENT_VALIDATION` (no network call); server `VALIDATION` means cross-field invariants disagreed — every shape and recovery is here.

- `CLIENT_VALIDATION` — the call was refused before any submit; the message names the fix: an unsupported `tool`, a foreign/duplicate/missing role, `text` on a geometry tool, or a zero-width span. It arrives as a NORMAL result envelope (`ok: false`), not an error flag — read it, fix the named field once, never claim drawn.
- **Position tools carry a profit direction** (refused pre-submit, stated with the relationship): `LongPosition prices must satisfy target > entry > stop (longs profit UP)`; `ShortPosition prices must satisfy target < entry < stop (shorts profit DOWN)`. Offer the corrected shape or the opposite tool; never swap silently.
- **Span tools refuse zero-width shapes**: anchors sharing one timestamp paint an invisible sliver; the refusal names the required span (≥ 2 bars). Re-anchor with time separation.
- `VALIDATION` (server) — the envelope reached the server and a cross-field invariant disagreed; surface the detail verbatim.
- "not enough candles" (`chart_drawing_auto`) — widen the lookback or match the chart's interval.

Where a failure arises in context, its section names the shape and points here.

## CLI equivalents

The `om chart drawing` command forms for shell agents — copy-paste recipes, seconds-based `--anchor` syntax; chat tools use field names and ms times, not flags.

```bash
# Auto-draw a trendline from market-data swings (preferred).
om chart drawing auto --workspace <workspaceId> --chart 0 --tool TrendLine \
  --normalized-symbol BTCUSDT --exchanges BINANCE_FUTURES --interval HOUR

# Draw a trendline between explicit anchors (role=epoch seconds:price).
om chart drawing add --workspace <workspaceId> --chart 0 --tool TrendLine \
  --anchor start=$(date +%s):94000 --anchor end=$(($(date +%s) + 86400)):96500

# Draw a Fibonacci retracement between a swing high and low (roles: from, to).
om chart drawing add --workspace <workspaceId> --chart 0 --tool FibonacciRetracement \
  --anchor from=$(date +%s):92000 --anchor to=$(($(date +%s) + 86400)):98000

# Remove a drawing by id (ids from `om chart drawing list`).
om chart drawing remove --workspace <workspaceId> --chart 0 --id <drawingId>

# Discover a tool's anchor roles before drawing.
om chart drawing schema LongPosition --format text

# BSD date has no GNU -d, and an unspecified time-of-day is taken from the CURRENT
# clock, not midnight — always pin the time explicitly.
date -u -j -f '%Y-%m-%d %H:%M:%S' '2026-05-15 00:00:00' +%s
```

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `chart_drawing_add` · `chart_drawing_auto` · `chart_drawing_list` · `chart_drawing_remove`
  - `workspaceId` — OMIT to act on the user's ACTIVE workspace (the daemon resolves it live); omitting is the default and the correct call for 'my chart' / 'this workspace'.
- `chart_drawing_add` · `chart_drawing_auto`
  - `chartIndex` — default 0
  - `metaId` — default "main"
- `chart_drawing_auto`
  - `normalizedSymbol` — Supply ONE of the three symbol forms, or omit all to use the chart pane's current market.
  - `lookback` — default "24h"
- `chart_drawing_list`
  - `includeRemoved` — default false

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `chart_drawing_add`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
  - on `TIMEOUT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.
  - on `TRANSPORT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.
- `chart_drawing_auto`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
  - on `TIMEOUT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.
  - on `TRANSPORT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.
- `chart_drawing_remove`
  - on `NO_CHANGE` — NO_CHANGE is a no-op, not a failure: the chart already shows what was asked (an unchanged market, an already-removed overlay). Report it as done and do not retry the call or reach for another tool.
  - on `TIMEOUT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.
  - on `TRANSPORT` — The bridge dropped or timed out with this intent in flight, so the outcome is UNKNOWN — the change may already have applied. Re-read the chart with chart_refresh and retry only if the change is absent from the fresh read; a blind retry can apply it twice.

<!-- AUTO: END RESULT CONTRACT -->

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om chart drawing add` (action: `chart_drawing_add`) — Draw ANY chart tool at anchors you already know (the user named exact price/time levels, or you computed them).
- `om chart drawing auto` (action: `chart_drawing_auto`) — Draw a chart tool (trend/ray/parallel lines, rectangle/ellipse, fibonacci retracement & trend, arrows like Momentum/Flow, markers, price/date ranges, long/short positions, and annotations) with trader-meaningful anchors computed from recent candles (swing highs/lows).
- `om chart drawing list` (action: `chart_drawing_list`) — List the drawings on the live chart with their `drawingId` (the handle `chart_drawing_remove` needs), tool, anchors, and author (`self`, `peer` with its id, `human`, or `unknown` when this daemon never observed the add) plus the author's stated reason.
- `om chart drawing remove` (action: `chart_drawing_remove`) — Remove drawing tools from a chart pane by id: `drawingId` for one, or `ids` for several on the same pane in ONE call, never a loop of single calls.
- `om chart drawing schema` (action: `chart_drawing_schema`) — Show a drawing tool's anchor schema: the role names (in wire order), how many anchors it needs, whether the role repeats, and whether it takes author text.

<!-- AUTO: END COMMAND REFERENCE -->
