---
name: openmarket-wrun
description: Build a custom sandboxed WRUN indicator from a plain description — `wrun_author` → `wrun_build` → preview → publish — with the metadata dialect, input pins, bindable odds inputs and chart styling an author must get right. Use this skill when the user asks for an indicator to be built, styled, or its metadata written; installing, mounting, binding, repointing or removing a WRUN package is the marketplace skill.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om wrun

You can build a custom sandboxed indicator from a plain description ("score BTC conviction from Polymarket odds vs funding stress"). This is a core capability, offer it whenever the user wants a metric that isn't built in and no installable package covers it.

### Guardrails

- Search before you build: when a user asks for an indicator, `package_search` FIRST and propose what covers the need instead of hand-rolling; author from scratch only when search comes up empty (`marketplace.md §"Rules"`) — then offer `package_publish` so the work compounds.
- Consent rule for the whole loop: a draft the user named in this conversation flows end to end (author, build, local install, preview) with receipts instead of asks; the approval gates live where trust changes hands, installing REGISTRY packages and PUBLISHING.
- `@local` is reserved — author under the user's own scope before publishing (§"The authoring loop").
- WRUN source reads params, inputs, and outputs ONLY through the generated accessors (`p_<param>()`, `in_<input>()`, `out_<output>(value)` then `emitRow()`): a raw positional literal such as `getFloat(0)` or `setOutput(0, ...)` is a BUILD ERROR in scaffold builds (§"The authoring loop"). In WRUN metadata a feed pin is `symbol` AND `exchange` together (the schema refuses a lone half) and an `interval` pin is legal: a coarser source aligns as-of its candle close (§"Input pins").
- Publishing is the user's call and the marketplace's gate: `package_publish` with `dry_run=true` first (uploads nothing, raises no card), then the real publish only on the user's explicit go — the approval card on chat surfaces, `yes=true` over MCP (`marketplace.md §"Publishing and yanking"`).

### Routing

The loop: §"The authoring loop" · what `metadata` must say: §"Metadata dialect" · or declare in the source: §"Code-first indicator authoring" · a fixed reference market on a secondary input: §"Input pins" · one package for any Polymarket market: §"Bindable odds inputs" · looks: §"Chart placement and styling". Consumer tasks stay in the marketplace skill: install `marketplace.md §"Rules"` · mount on a chart, bind, repoint, list, remove `marketplace.md §"WRUN packages"`.

| Ask | Call | Disclose |
| --- | --- | --- |
| "build me an indicator" | `wrun_author` → `wrun_build` | scaffold first, edit the returned source through the generated accessors and `./sdk/ta`, fix every warning, build installs the draft locally with a receipt (no ask); publish only on the user's go |
| "make it green when rising" / "shade the band" | `wrun_author` (metadata) | decision outputs from the module, looks declared in metadata, never computed (§"Chart placement and styling") |
| "use it on any Polymarket market" | `wrun_author` with `binding: "required"` | one package, the market supplied per use; the bind question after install is the marketplace's |

## The authoring loop
Build a sandboxed indicator from a description: `wrun_author` (scaffold, edit via accessors) → `wrun_build` (local install, no ask) → preview → publish on the user's go.

**The shape.** A scaffold workspace is `wrun/metadata.json` (what the module reads and writes) plus `src/indicator.ts` (the math) on top of two SDK layers `om wrun` maintains for you: `src/gen/{params,inputs,outputs}.ts`, GENERATED from the metadata on every `wrun_author` call and again before every build, one accessor per metadata name (`p_<param>(): f64` for `init`, `in_<input>(): f64` for `state`, `out_<output>(value: f64)` plus `emitRow()` for `finalize`); and `src/sdk/ta.ts`, stateful TA classes (`Sma`, `Ema`, `Stdev`, `Zscore`, `Rsi` (Wilder), `Roc`: `new X(period)`, `.update(x): f64` once per bar, NaN until warm, `.reset()`; `Cross.update(a, b): i32` is +1 when a crosses above b, -1 below, 0 otherwise). The `sma` template, verbatim (what a scaffold call returns; edit this shape):

```typescript
import { in_close } from "./gen/inputs";
import { emitRow, out_sma } from "./gen/outputs";
import { p_period } from "./gen/params";
import { Sma } from "./sdk/ta";

let sma = new Sma(20);
let value: f64 = NaN;

export function init(): void {
  sma = new Sma(i32(p_period()));
}

export function state(): i32 {
  value = sma.update(in_close());
  return isNaN(value) ? 0 : 1;
}

export function finalize(): void {
  out_sma(value);
  emitRow();
}

export function reset(): void {
  sma.reset();
  value = NaN;
}
```

A metadata name becomes its accessor by lowercasing and collapsing every run outside `[a-z0-9_]` to `_` (param `fast.len` → `p_fast_len()`, input `BTC-Close` → `in_btc_close()`, output `sma` → `out_sma(value)`); two names that escape identically are refused, duplicate param names are refused, and a style-only param (`style: {...}`) gets no accessor because it never reaches the module. Editing metadata moves the SLOT inside the accessor while your source keeps the NAME, so reordering params or inputs never changes what the module computes; a RENAMED entry renames its accessor, so rename it in the source too (the compiler names the missing import).

The loop:

1. **`wrun_author`**: pick the closest `template`, then write the AssemblyScript `source` (and `metadata` if the inputs/outputs/params differ from the template). The four exports are an EXACT contract, do not redesign it: `export function init(): void`, `export function state(): i32`, `export function finalize(): void`, `export function reset(): void`. No parameters, no return values except state's i32 (1 = a row is ready, 0 = warmup). Values flow ONLY through the generated accessors: params reach `init` via `p_<param>()`, each bar's inputs reach `state` via `in_<input>()`, every output is written in `finalize` via `out_<output>(value)` and the row is committed with `emitRow()` LAST; ALL persistent state lives in module-level variables (`reset` clears them and calls `.reset()` on every TA object). WORKFLOW: call `wrun_author` once with just `name` + `template` and READ the returned `source`, then EDIT that shape rather than writing from memory. The tool lints submitted source at the write step and returns the deviations as `warnings`; fix every warning before building. This is local scratch work, no approval needed. Two failure modes to know by name:
   - Redesigned signatures (`init(args: Array<f64>)`, `state(state, inputs)`, a `finalize` that returns the value) DO compile under asc; nothing stops them until the build's static ABI check refuses the module (`WRUN export 'init' has signature (i32) -> void; the wrun-1 contract requires init() -> void`). `wrun_author` already warns at the write step (`'init' must take NO parameters (found 'args: Array<f64>')`), so a warning-free author is the cheap fix.
   - Raw positional slot literals (`getFloat(0)`, `getInt(0)`, `wrun_arg_f64(0)`, `wrun_arg_i32(0)`, `setOutput(0, ...)`, `wrun_output_f64(0, ...)`) are refused BEFORE the compiler runs, because slots silently rebind when metadata params/inputs/outputs change: `wrun_author` warns `wrun_build will fail: src/indicator.ts:<line> uses positional getFloat(0); use in_close() from ./gen/inputs in state() or p_period() from ./gen/params in init()`, and `wrun_build` throws `scaffold build blocked: raw positional slot literals silently rebind when metadata params/inputs/outputs change` with one such line per finding. Variable indexes stay legal and comments are ignored; `src/sdk/sdk.ts` (the raw `getFloat`/`setOutput` wrappers) exists for variable-index access only.
2. **`wrun_build`**: compile it. On a compile error it throws with the diagnostics: read them, rewrite via `wrun_author`, build again. Iterate until it builds. A successful build regenerates `src/gen`, runs the local AssemblyScript build (the CLI receipt prints `Compiler: assemblyscript (bun run build)`), checks the module statically against the wrun-1 export ABI, ALSO installs the draft locally, and returns the receipt (`installed.path`, `installed.removeCommand`, `metrics`, any `warnings`): the user commissioned this draft by name, so that commission IS the consent (do not ask again); state the receipt (installed path + `om wrun remove <package>` as the undo) instead of asking. `package_install` is NOT part of this loop: it is for REGISTRY packages, where someone else's code enters the user's daemon, and there the ask stays. Opaque builds (`om wrun build --wasm <module.wasm>` or `--compile-command`, CLI-only) skip the accessor lint, so their receipt carries `positionalAbi: true` (text: `ABI: positional (metadata order binds params and inputs)`): params and inputs bind by metadata POSITION, so never reorder the metadata entries of such a package; scaffold builds are name-attached and omit the flag.
3. **Preview**: straight after a green build, `metric_get` the new `wrun/...` metric on a symbol so the user sees a real value; `metric_series` (same selector, `bars` 1..500, default 30) when they want to see it MOVE, one `[barOpenSec, value]` pair per bar (CLI `om metric series` renders a sparkline; metrics.md §"Series"); and `chart_indicator_preview` draws the draft on their chart (no publish needed; `plot: "line"` outputs only, one output per preview).
4. **Publish**: `package_publish` the same `packageDir` once the user approves. The human always approves publishing. Before publishing, AUTHOR UNDER A PUBLISHABLE SCOPE: `@local` is reserved and the registry rejects it; re-author the same source/metadata under the user's own scope (their account scope, e.g. `@om-core` if they own it) so the publish can succeed. Publish is also what unlocks hosted charting (bindable packages excepted, §"Bindable odds inputs"): `chart_indicator_add` mounts registry packages only (`marketplace.md §"WRUN packages"`); the local preview never needs it.

Keep inputs to the OM-native sources the SDK exposes (ohlcv, funding, open interest, Polymarket odds); the module has no network of its own. Every `inputSources` pin is fixed at authoring time and no pin is user-configurable after install (repointing a PINNED odds input is `om wrun source set` on the authoring workspace followed by a rebuild — a code-first workspace edits the `input(...)` declaration instead; the consumer-side write-up is `marketplace.md §"WRUN packages"`). Before publish, a wrong pin is fixed in the normal loop (re-author, rebuild, reinstall the preview); after publish it can only be fixed by publishing a bumped version.


<!-- AUTO: CODE-FIRST AUTHORING - do not edit by hand; source: docs/indicators (snippet: code-first); regenerate with `bun packages/cli/scripts/gen-indicator-docs.ts` -->

## Code-first indicator authoring
Declarations in the source, sheet derived at build: the grammar, the refusals, and the wrun-2 notes; read before editing a workspace whose sheet says `generated_from`.

How this mode enters the agent loop, beside (never instead of) the metadata-first loop above:

- Scaffold code-first with `template: "sma-codefirst"` on `wrun_author` (or `om wrun create @scope/name --template sma-codefirst`): a complete SMA in 14 non-blank source lines, sheet derived, same build and preview loop as any draft. For the wrun-2 surface (a celled volume-profile input, a string slot, a text renderer) scaffold `template: "vp-buy-share-codefirst"` instead and edit that shape.
- On a code-first workspace, `wrun_author`'s `metadata` argument is REFUSED with `wrun_metadata_generated`, and `wrun_source_set` is refused with `wrun_source_set_generated`: the sheet is derived state, so pass updated `source` with edited declarations instead, and the build re-derives sheet + accessors together.
- `abi_version: "wrun-2"` is additive (scalar wrun-2 packages compute bit-identically to wrun-1). Celled inputs (`cellType: "array"` + required `max_cells`, counted in source tuples) read the celled source classes and FETCH LIVE for `volume_profile` ([low, high, buy, sell] cells) and `book` ([price, size, side] cells; `block_size` required, `om block-sizes` lists the venue's); `trade_volume_by_size` is declared but refused by name (`wrun_cells_unavailable`). Backtests and screens refuse whole celled packages by name (`wrun_celled_metric_unsupported`); alerts, `metric_get`/`metric_series`, and chart previews are the supported consumers.
- wrun-2 sheets may also declare `string_slots` (byte-capped per-bar text written in `finalize()` via generated `str_<slot>` senders; slots are never metrics), `renderers` (`text`, `label`, `table`, `shape`, `stats_row`), and `drawings` (`line`, `box`, `polyline`, `label`; coordinates from named outputs, x in epoch seconds). Modules read celled blocks through generated `in_<input>_cells()` / `in_<input>_read(ptr)` accessors; raw `wrun_arg_len` / `wrun_arg_bytes` / `wrun_output_str` literals are a scaffold build error like any positional access.

Instead of hand-writing `wrun/metadata.json`, declare params, inputs, and
outputs as typed top-level statements of `src/indicator.ts`, imported from
`./sdk/declare`:

```typescript
import { input, line, lower, ohlcv, output, overlay, param } from "./sdk/declare";

param("period", 14, { min: 2, max: 200, description: "Lookback window" });
input("close", ohlcv.close);
input("btc_close", ohlcv.close, { symbol: "BTCUSDT", exchange: "BINANCE_FUTURES" });
output("value", line, lower, { unit: "score" });
```

The build derives the sheet from these declarations and generates the
accessors from the SAME in-memory object, so the two can never disagree. The
grammar is static and literal-only:

- `param(name, default, options?)` with options `required`, `min`, `max`,
  `description`.
- `input(name, source.field, options?)` with options `exchange`, `symbol`,
  `interval`, `outcome`, `binding`, `tenor`, `side`, `token`, `description`.
  Sources are bare member references from `./sdk/declare`: `ohlcv`, `trades`,
  `funding`, `oi`, `liquidations`, `implied_volatility`, `skew`,
  `token_supply`, `odds`, `time` (metric composition inputs stay
  metadata-first and are refused by name).
- `output(name, plot?, panel?, options?)` with plots `line`, `bar`, `area`,
  `histogram`, `candle`, `shape`, `scatter`, `none` (data-only), panels
  `overlay`, `lower`, and options `description`, `unit`, `color`, `width`,
  `opacity`, `line_style`, `color_by`, `shape_where`.

The wrun-2 vocabulary has declaration forms too, and deriving a sheet that
uses any of them stamps `abi_version: "wrun-2"` automatically (scalar-only
declarations keep deriving wrun-1 sheets):

- Celled inputs: `input(name, <class>.cells, options)` with classes
  `volume_profile`, `book`, `trade_volume_by_size` referenced as
  `volume_profile.cells` etc. `max_cells` is REQUIRED; `block_size`
  (required on `book`) and `max_depth` are the book fetch facets; `symbol` +
  `exchange` pin together; `description`. Scalar-feed knobs (`interval`,
  `side`, ...) are refused on celled inputs.
- String slots: `string(name, { max_bytes, description? })`.
- Renderers: `render.text(name, { y, text })`, `render.label(name, { x, y,
  text })`, `render.table(name, { rows, cols, cells, position? })`,
  `render.shape(name, { output, shape, where? })`, `render.stats_row(name,
  { output, title?, format?, polarity? })`. Numeric references name declared
  outputs; `text` and table `cells` name declared string slots.
- Drawings: `draw.line(name, { x1, y1, x2, y2, color?, width?,
  line_style? })`, `draw.box(name, { left, top, right, bottom, color? })`,
  `draw.polyline(name, { points, color?, width?, line_style? })` where
  `points` is a flat `["x0", "y0", "x1", "y1", ...]` list of output-name
  pairs, `draw.label(name, { x, y, text, color? })`.

Rules the extractor enforces, each as a named build error:

- Names are string literals; defaults and option values are literals; the
  code never runs at build time.
- Declarations are top-level statements of `src/indicator.ts` only; one
  anywhere else names the file and line.
- Indexes follow declaration order: the first `input(...)` is slot 0 (the
  primary input), and reordering declarations reorders slots while the
  generated accessors keep your source name-attached.

The derived sheet records `generated_from: "declarations"` plus a
`source_digest` (sha256 of the source), serializes canonically (an unchanged
source rewrites nothing), and is DERIVED state from then on: `om wrun source
set` refuses with `wrun_source_set_generated` and the agent's metadata
argument refuses with `wrun_metadata_generated`, both pointing at the
declaration to edit instead. A sheet claiming generated provenance over a
declaration-free source blocks the build naming both ways out (restore the
declarations, or delete `generated_from` and `source_digest` to hand-edit
again). A workspace with no declarations stays metadata-first: byte-identical
behavior to a hand-written sheet, and the supported mode for languages
without an extractor (Rust, Zig, pre-built wasm).

The `sma-codefirst` template is the worked example: scaffold it and read the
source it returns; the whole user file is 14 non-blank lines with zero
hand-written sheet. The `vp-buy-share-codefirst` template is the wrun-2
worked example (a celled volume-profile input, a string slot, and a text
renderer in 20 non-blank lines), and the generated accessors for the wrun-2
forms are `in_<input>_cells()` / `in_<input>_read(ptr)` /
`in_<input>_capacity` for celled inputs and the `src/gen/strings.ts` line
builder (`sb_clear` / `sb_text` / `sb_int` / `sb_f64`) with per-slot
`str_<slot>(s)` / `str_<slot>_sb()` senders for string slots.

<!-- AUTO: END CODE-FIRST AUTHORING -->

## Metadata dialect
The `metadata` skeleton — `params` array, `inputSources` keyed by input name, `source` enum — validated at author, build, install and publish; read before writing any `metadata`.

**Metadata skeleton** (the dialect; the structural bullets below and the pin pair rule are validated at author, build, install, and publish; the rest of the pin block is authoring policy):
```json
{
  "id": "my-indicator", "name": "My Indicator", "abi_version": "wrun-1", "warmup_bars": 1,
  "params": [{ "name": "period", "default": 14, "min": 2, "max": 200 }],
  "inputSources": { "close": { "source": "ohlcv", "field": "close" } },
  "inputs": [{ "index": 0, "name": "close" }],
  "outputs": [{ "index": 0, "name": "value", "plot": "line", "panel": "overlay", "unit": "price" }]
}
```
- `params` is an ARRAY of `{name, default, min?, max?}` objects with unique names; each compute param is read in `init()` through its `p_<name>()` accessor (underneath, values reach the module positionally in declaration order and the accessor pins that slot; a style knob keeps its position zero-filled, so its neighbours never shift).
- `inputSources` is keyed BY INPUT NAME and each input must have a matching entry: `inputs[i].name` == the key. Feed sources need `field`. `inputs[i].index` is the slot `in_<name>()` reads; index 0 is the PRIMARY input and sets the grid every other input aligns to.
- `source` must be one of: `ohlcv`, `trades`, `funding`, `oi`, `liquidations`, `implied_volatility`, `skew`, `token_supply`, `odds`, `metric`, `time` (there is no "market"/"price" source; close prices are `ohlcv`+`close`). A `time` input carries the primary bar's open timestamp (sole field `bar_open_sec`, epoch seconds; never the primary input) so a module can do session/calendar math deterministically.
- A `shape_where`/`color_by` gate must be a DIFFERENT output (usually `"plot": ""` data-only); an output cannot gate or color itself.

## Input pins
Pinning a secondary input to a fixed reference market: `symbol` + `exchange` together, primary follows the selector; `interval` pins are legal and run on the as-of clock.

**Cross-symbol pins.** A non-odds, non-time FEED source may pin `symbol` and `exchange` TOGETHER so a secondary input reads a fixed reference market while the rest of the package follows the selector: `"btc_close": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES" }` gives any alt selector a BTC context input (ratios, cross-venue context). The pair rule is SCHEMA-ENFORCED: a lone `symbol` or a lone `exchange` is refused with the issue on the missing half (`feed sources pin a fixed market with symbol AND exchange together (never one alone: symbols are venue-native, so a lone symbol or a lone exchange names a market that does not exist on that venue); pin both, or omit both to follow the selector`). The rest is authoring policy the schema cannot check:
- Pin `symbol` and `exchange` together, never one alone: symbols are venue-native strings (`BTCUSDT` on BINANCE_FUTURES is `BTC` on HYPERLIQUID).
- Keep the PRIMARY input (index 0) selector-following; pins belong on secondary context inputs. A package with every input pinned computes the same value for every selector symbol (screens and chart legends mislabel it).
- Cross-symbol price/notional arithmetic is only dimensionally sane under the shared default USD quote (normalization covers ohlcv/trades/oi). Never mix with `quote: COIN`; avoid native-cross raw symbols (no per-source quote override).
- Exceptions: `odds` keeps its own rule (conditionId as `symbol`, exchange implicitly Polymarket); `time` takes no knobs; do not pin `metric` composition sources.
- Packages with cross-symbol pins are UNVERIFIED on hosted charts: keep them off `chart_indicator_add` until the chart lane verifies pins (odds-pinned packages chart as they always have), and a signal on a pinned-package metric must use `eval: "bar"` — `marketplace.md §"WRUN packages"`.

**Interval pins and the as-of clock.** `interval` is an independent pin on any feed source (odds included), and it is legal. A symbol/exchange pin alone still reads on the SELECTOR's interval and quote; an `interval` pin moves that one source onto its own grid, `"btc_4h": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES", "interval": "FOUR_HOURS" }`, and a bare `{ "source": "ohlcv", "field": "close", "interval": "DAY" }` reads the selector's own market on the daily grid. Causality is the engine's job, not the author's: a source COARSER than the primary grid (an explicit coarse pin, or an unpinned secondary that inherits the selector's interval when the primary input is pinned finer) contributes to a primary row only as-of its candle CLOSE, `candle.ts + sourceSec <= min(now, row.ts + primarySec)`: the value becomes visible on the first primary row whose own close is at or after the source candle's close, and never before evaluation time, so a forming 4h candle never leaks its final value into the 1h rows under it, live or historical; sparse coarse observations (odds) carry the latest CLOSED observation forward; an observation older than two source intervals before the window head reads as not-ready. Equal or finer sources align by bar open, row for row, exactly as an unpinned source does. Any interval validates; compatibility with the primary grid is resolved at runtime, not by schema. What it costs: a coarse leg needs its own history (the fetch widens by two source intervals) and its value steps once per source candle, so a `DAY` pin on a `MINUTE` primary is a step function. Hosted charts have not adopted this clock yet, so an interval-pinned package previews locally and stays off `chart_indicator_add` for now.

- Permissions: `read:openmarket` covers every feed source and is required whenever any FEED source follows the selector (metric and time sources need no permission), so the standard shape needs only `read:openmarket`; templates already carry it. Venue reads (`read:binance`, `read:bybit`, `read:hyperliquid`, `read:polymarket`) are a NARROWING option only for packages whose every feed source pins one of those four venue families; the check fires only when `read:openmarket` is absent, and a pin outside those families still requires `read:openmarket`.

## Bindable odds inputs
An odds input declared `binding: "required"` instead of a pinned symbol serves any Polymarket market — the exact metadata shape and what the schema refuses.

- Bindable markets: an odds input may declare `binding: "required"` INSTEAD of a pinned symbol: one published package then serves ANY Polymarket market, with the conditionId supplied per use (`sourceBindings` on the alert/signal operand or metric query, `om metric get --bind input=0x...`). Never both on one input; a bindable input's outcome comes from the binding (metadata `outcome` is refused); screens refuse bindable packages (no per-row market exists).

**Bindable odds metadata, the exact shape** (copy it; the schema refuses symbol+binding, outcome+binding, and exchange on odds; `panel: "lower"` puts a small-magnitude output in its own pane, where chart preview draws it on v2-aware charts; overlay outputs share the price axis; preview is a bindable package's only chart surface either way):
```json
{
  "id": "pm-mom", "abi_version": "wrun-1", "warmup_bars": 1,
  "params": [{ "name": "period", "default": 5, "min": 1, "max": 200 }],
  "inputSources": { "yes_odds": { "source": "odds", "binding": "required" } },
  "inputs": [{ "index": 0, "name": "yes_odds" }],
  "outputs": [{ "index": 0, "name": "momentum", "plot": "line", "panel": "lower" }]
}
```

## Chart placement and styling
How outputs draw (`plot`, `panel`, `unit` per output) and the declarative styling vocabulary (colors, gates, fills, style knobs): declared in metadata, never computed in code.

**Chart placement basics**, per output: `plot` is one of `line|bar|area|histogram|candle|shape|scatter` (or `""` for data-only), `panel` is `overlay` (price chart) or `lower` (own pane), `unit` (`price`, `%`, else abbreviated) sets the axis format. `wrun_author`'s `display_name` names the package in chart legends and listings.

**Chart styling** is declared in metadata, never computed in the module: outputs are numbers, some numbers are decisions, metadata maps decisions to looks. Vocabulary:
- Static, on any output: `color`/`colors`, `width`, `opacity`, `line_style`.
- Per-bar coloring: emit the decision as an ordinary output (e.g. regime 0/1) marked `"plot": ""` (data-only, never drawn), then on the styled output set `color_by: "<that output>"` + a `colors` palette (at least 2 entries); each bar's value indexes the palette, clamped to its bounds.
- Gated markers: a `plot: "shape"` output with `shape_where: "<gate output>"` renders only where the gate is nonzero.
- Shaded bands: metadata-level `fills: [{ "between": ["upper", "lower"], "color": "#94a3b8", "opacity": 0.15 }]`; both sides must be rendered outputs.
- User style knobs: a param with `style: { "output": "<name>", "property": "color"|"width"|"opacity"|"lineStyle" }` never reaches the module (no `p_` accessor, its slot stays zero-filled), shows in the settings dialog (color knobs take string defaults like "#22c55e"), and redraws without recompute. Param names are lowercase (`line_color`).
When the user describes looks ("green when rising, red when falling, shade the band"), emit decision outputs from the module and declare the looks here; `om publish` cross-validates every reference and names the broken field on mistakes.

## CLI equivalents
The shell forms of the authoring loop — `om wrun create` scaffolds a workspace on disk, `om wrun build --install` compiles and installs it — and the command-to-action mapping.

`om wrun create <@scope/name> [dir] --template <id>` scaffolds an authoring workspace (the same template `wrun_author` returns as `source` when given the same `template`; the CLI defaults to `conviction-score`, both actions to `sma`); `om wrun build <dir>` compiles it and installs the draft locally only with `--install` (`om wrun install <dir>` does both in one step — the MCP `wrun_build` always installs); `om wrun remove <package>` is the undo. Opaque WRUN builds are CLI-only too: `om wrun build <dir> --wasm <module.wasm>` (a pre-built module) or `--compile-command "<cmd>"` (an external compiler writing the wasm as its last argument) export a package whose receipt says `ABI: positional (metadata order binds params and inputs)`; those packages must never have their metadata entries reordered. The command-to-action mapping:

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

- `om wrun create` (action: `wrun_create`) — Scaffold a WRUN authoring workspace.

<!-- AUTO: END COMMAND REFERENCE -->
