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

All mutating verbs require the daemon (`om run` / `om service start`) and target a
pane via `--workspace <id>` plus optional `--chart <n-or-symbol>` (default chart 0).

| Command | Wire action | Requires daemon |
| --- | --- | --- |
| `om chart drawing auto` | `add_drawing` | yes |
| `om chart drawing add` | `add_drawing` | yes |
| `om chart drawing schema` | (local, read-only) | no |
| `om chart drawing remove` | `remove_drawing` | yes |

Every drawing tool in the chart's Super Search palette is on the wire — lines, shapes/ranges, fibonacci, arrows, markers, positions, and annotations. Use the tool name as it appears in Super Search (e.g. `TrendLine`, `FibonacciRetracement`, `Rectangle`). On the chart, both `auto` and `add` render the same way: a ghost cursor opens **Super Search**, types the tool name, arrows to the tool row, and draws at the anchors.

**Prefer `drawing auto`.** It fetches recent candles and computes trader-meaningful anchors (swing highs/lows) itself, so you pick the symbol/interval — not raw coordinates. Reach for `drawing add` only when the user named exact price/time levels (e.g. "draw a fib from 90k to 100k").

## `drawing auto` — anchors computed from market data (preferred)

```bash
om chart drawing auto \
  --workspace <workspaceId> \
  --chart 0 \
  --tool FibonacciRetracement \
  --normalized-symbol BTCUSDT \
  --exchanges BINANCE_FUTURES \
  --interval HOUR \
  [--lookback 24h] \
  [--direction up|down] \
  [--strength 3] \
  [--text "..."] \
  [--narration "..."]
```

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--chart <n>` | optional (default `0`) | Chart pane index. |
| `--tool <type>` | yes | Any Super Search drawing tool (lines, shapes, fibonacci, arrows, markers, positions, annotations) — e.g. `FibonacciRetracement`, `TrendLine`, `Rectangle`. |
| `--normalized-symbol` / `--raw-symbol` / `--coin` | one of | Which market to read candles for. Use the same identity the chart shows. |
| `--exchanges <csv>` | recommended | Comma-separated exchange ids, e.g. `BINANCE_FUTURES`. |
| `--interval <I>` | recommended | Candle size: `HOUR` or `1h`, `MINUTE` or `1m`, `DAY` or `1d`. Match the chart's timeframe. |
| `--lookback <duration>` | optional (default `24h`) | How far back to read candles. Widen it if "not enough candles". |
| `--direction <up\|down>` | optional | Force the trend leg/side; omitted = inferred from the latest confirmed pivot. |
| `--strength <n>` | optional (default `3`) | Pivot strength — higher = fewer, more significant swings. |
| `--text <text>` | annotations only | Author text for Text/Note/Callout; rejected on geometry tools. |
| `--narration <text>` | optional | Operator-visible narration. |

The CLI computes the anchors and submits `add_drawing` for you — you don't pass `--anchor`.

## `drawing schema` — discover a tool's anchor roles (read-only, no daemon)

Each tool's anchors carry tool-specific **roles**. `drawing schema` prints them (and the
count) straight from the registry, so a new tool documents itself the moment it ships.

```bash
om chart drawing schema LongPosition --format text   # roles: entry, target, stop (3 anchors)
om chart drawing schema --format text                # list every tool
om chart drawing schema FibonacciTrend               # JSON (default)
```

Common role shapes: single-point tools (markers, levels, VerticalLine, annotations) take `point`;
lines take `start`/`end`; ParallelLine takes `start`/`end`/`offset`; arrows & fib-retracement take
`from`/`to`; FibonacciTrend takes `start`/`pivot`/`retracement`; Long/ShortPosition take
`entry`/`target`/`stop`; Path/ThreePaths repeat `point`. Roles are slotted into the correct order
for you, so the order you pass them does not matter.

## `drawing add` — explicit, role-tagged anchors

Pass each point the tool needs as a repeatable `--anchor <role>=<epochSec>:<price>`. The CLI does
not auto-resolve a live price — compute anchors from the current chart state first. Run
`drawing schema <tool>` if you're unsure of the roles.

```bash
# TrendLine (2 anchors: start, end)
om chart drawing add --workspace <workspaceId> --chart 0 --tool TrendLine \
  --anchor start=$(date +%s):94000 \
  --anchor end=$(($(date +%s) + 86400)):96500

# LongPosition (3 anchors: entry, target, stop)
om chart drawing add --workspace <workspaceId> --tool LongPosition \
  --anchor entry=$(date +%s):94000 \
  --anchor target=$(($(date +%s) + 86400)):99000 \
  --anchor stop=$(date +%s):92000

# Annotation (1 anchor + text)
om chart drawing add --workspace <workspaceId> --tool Note \
  --anchor point=$(date +%s):95000 --text "Potential entry"
```

When choosing anchor values:

- **Timestamps are integer epoch seconds.** Never copy hard-coded epochs from prior examples (months stale). Compute fresh — `$(date +%s)`, or `date -u -j -f '%Y-%m-%d' '<YYYY-MM-DD>' +%s` on macOS.
- **Sanity-check the anchor falls in the loaded candle range.** Read `om chart refresh --workspace <id>` (visible-range or candles array). Anchors far outside render off-screen even on `ok: true`.
- **Prices within ±10% of current.** Guessing prices that turn out to be stale is the leading cause of "the drawing landed but the chart looks empty".

| Flag | Required | Notes |
| --- | --- | --- |
| `--workspace <id>` | yes | Target workspace. |
| `--chart <n>` | optional (default `0`) | Chart pane index. |
| `--tool <type>` | yes | Any Super Search drawing tool. `drawing add` handles 1/2/3/N-anchor tools via roles (run `drawing schema <tool>` for the role list). |
| `--anchor <role>=<epochSec>:<price>` | yes | Repeat once per point. `role` is tool-specific (`drawing schema`); `epochSec` MUST be integer epoch seconds (not ms); `price` any finite number. Path tools repeat `point`. |
| `--text <text>` | annotations only | Author text for Text/Note/Callout; rejected on geometry tools. |
| `--search-term <term>` | optional | Override what's typed into Super Search (defaults to the tool label). |
| `--meta-id <id>` | optional (default `main`) | Chart pane meta id; all anchors share the same pane. |
| `--narration <text>` | optional | Operator-visible narration. |

Cross-field invariants the bridge enforces locally (mirrors the server-side checks):

- All anchors target the same `--chart` index.
- `--tool` is in the supported set; the supplied roles match the tool and the anchor count matches.
- Each anchor's `time`/`price` matches the `--anchor` it came from (the bridge constructs both halves of the envelope from the same input — they cannot drift).

## `drawing remove` — delete a drawing by id

Read the overlay id from `om chart refresh --workspace <id>` — look for entries with `overlayType: "tool"`:

```bash
om chart drawing remove \
  --workspace <workspaceId> \
  --chart 0 \
  --id <drawingId>
```

The server filters strictly on `overlayType === 'tool'` so an indicator sharing the id is preserved. A `VALIDATION` error fires if the id isn't found.

Successful JSON output mirrors `om chart indicator add`:

```jsonc
{
  "ok": true,
  "action": "add_drawing",
  "version": 44,
  "transport": "rest",
  "tookMs": 287
}
```

## Workflow — user asks to draw a tool

**Default to `drawing auto`** — it computes the anchors from market data so you don't have to resolve coordinates:

1. **Parse intent** — tool, chart, and (if mentioned) trend direction.
2. **Resolve the workspace id**, and the chart's symbol/exchange/interval (`om chart refresh`).
3. **Execute** `om chart drawing auto --tool <Tool> --normalized-symbol <sym> --exchanges <ex> --interval <I>`.
   - On `ok: true` → *"Drew a `<Tool>` on chart 0 — version `<N>`."*
   - On "not enough candles" → widen `--lookback` or set `--interval`.

Only when the user names **exact** price/time levels, use `drawing add`:

1. **Parse intent** — tool, chart, anchor hints.
2. **Resolve the workspace id.** If unsure of the tool's roles, run `om chart drawing schema <tool>`.
3. **Resolve the anchors** as `(epochSeconds, price)` pairs, one per role. Strategies:
   - For specific bar timestamps, run `om chart refresh --workspace <id>` first to read the chart's viewport / OHLC.
   - For named price levels, the user usually gives the number directly.
   - For ambiguous anchors, ask via structured question — anchor errors are silent (the drawing lands on the wrong bar with no feedback).
4. **Preview + confirm** showing the anchors in human time + price.
5. **Execute** `om chart drawing add --tool <Tool> --anchor <role>=<epochSec>:<price> ...`.
   - On `ok: true` → *"Drew a `<Tool>` on chart 0 — version `<N>`."*
   - `CLIENT_VALIDATION` errors usually mean an unsupported `--tool`, a missing/foreign role, or `--text` on a geometry tool; fix and retry.
   - Server `VALIDATION` errors mean cross-field invariants disagreed; surface the detail.

## Quick recipes

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

# Discover a tool's anchor roles before drawing.
om chart drawing schema LongPosition --format text
```

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om chart drawing add` (action: `chart_drawing_add`) — Draw ANY chart tool at anchors you already know (the user named exact price/time levels, or you computed them).
- `om chart drawing auto` (action: `chart_drawing_auto`) — Draw a chart tool (trend/ray/parallel lines, rectangle/ellipse, fibonacci retracement & trend, arrows like Momentum/Flow, markers, price/date ranges, long/short positions, and annotations) with trader-meaningful anchors computed from recent candles (swing highs/lows).
- `om chart drawing list` (action: `chart_drawing_list`) — List the drawings on the live chart with their `drawingId` (the handle `chart_drawing_remove` needs), tool, anchors, and author (`self`, `peer` with its id, `human`, or `unknown` when this daemon never observed the add) plus the author's stated reason.
- `om chart drawing remove` (action: `chart_drawing_remove`) — Remove a drawing tool from a chart pane by id.
- `om chart drawing schema` (action: `chart_drawing_schema`) — Show a drawing tool's anchor schema: the role names (in wire order), how many anchors it needs, whether the role repeats, and whether it takes author text.

<!-- AUTO: END COMMAND REFERENCE -->
