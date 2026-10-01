---
name: openmarket-indicators
description: Build a custom sandboxed Indicator package from a plain description — `wrun_author` → `wrun_build` → preview → publish — with the metadata dialect, input pins, bindable odds inputs and chart styling an author must get right. Use this skill when the user asks for an indicator to be built, styled, or its metadata written; installing, mounting, binding, repointing or removing an Indicator package is the marketplace skill.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om indicator

Build a custom sandboxed indicator when no built-in metric or installable package covers the request.

### Guardrails

- A rule over stock indicators is a condition or a strategy, never a new Indicator: a level, a crossing or a band over `ema`, `rsi`, `macd` and the rest is a condition source (`watch.md §"Condition source"`), and a standing position, a target, a regime or an accumulation is a sizer mode or kind; pick the style in `strategy.md` first.
- Search with `package_search` before building; propose an existing match. If none fits, author and offer `package_publish` (`marketplace.md §"Rules"`).
- A draft named in this conversation is authorized for author, build, local install and preview. Return receipts; registry installs and publishing retain their approval gates.
- `@local` is reserved; publish under the user's own scope (§"The authoring loop").
- Use generated `p_<param>()`, `in_<input>()`, `out_<output>(value)` and `emitRow()`. Raw positional literals fail scaffold builds (§"The authoring loop"). Feed pins require `symbol` AND `exchange`; coarser `interval` pins align at candle close (§"Input pins").
- Publishing: `package_publish` with `dry_run=true` first, then publish only on the user's explicit go, through the chat approval card or `yes=true` over MCP (`marketplace.md §"Publishing and deleting"`).

### Routing

Build: §"The authoring loop" · sheet: §"Metadata dialect" · source declarations: §"Source-declared indicators (code-first)" · reference markets: §"Input pins" · per-use markets: §"Bindable odds inputs" · plot styles: §"Chart placement and styling" · frames, profiles, panels, HUDs and watch series: §"Snapshots, panels and pane placement" · a package that trades: §"A package that trades". Install: `marketplace.md §"Rules"` · mount, bind, repoint, list, remove: `marketplace.md §"Indicator packages"`.

| Ask | Call | Disclose |
| --- | --- | --- |
| Build an indicator | `wrun_author` → `wrun_build` | edit the scaffold through generated accessors and `./sdk/ta`; fix warnings before building |
| Style a plot | `wrun_author` | declare styles in metadata or source declarations (§"Chart placement and styling") |
| Reuse across Polymarket markets | `wrun_author`, `binding: "required"` | supply the market per use |

## The authoring loop
Build a sandboxed indicator from a description: `wrun_author` (scaffold, edit via accessors) → `wrun_build` (local install, no ask) → preview → publish on the user's go.

**The shape.** A scaffold workspace is `wrun/metadata.json` (what the module reads and writes) plus `src/indicator.ts` (the math) on top of two SDK layers `om wrun` maintains for you: `src/gen/{params,inputs,outputs}.ts`, GENERATED from the metadata on every `wrun_author` call and again before every build, one accessor per metadata name (`p_<param>(): f64` for `init`, `in_<input>(): f64` for `state`, `out_<output>(value: f64)` plus `emitRow()` for `finalize`); and `src/sdk/ta.ts`, stateful TA classes (`Sma`, `Ema`, `Stdev`, `Zscore`, `Rsi` (Wilder), `Roc`: `new X(period)`, `.update(x): f64` once per bar, NaN until warm, `.reset()`; `Cross.update(a, b): i32` is +1 when a crosses above b, -1 below, 0 otherwise). An Indicator is ONE file for now: helper functions, classes and constants go in `src/indicator.ts` too, and `wrun_build` refuses a workspace holding any other author file under `src/` (`wrun_single_file_only`, naming each file to move in). The `sma` template, verbatim (what a scaffold call returns; edit this shape):

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

**Kit modules.** `src/sdk/ta.ts` has nine siblings, every scaffold ships them, and the compiler reads a module only when the source imports it. Same shape as the TA classes (construct in `init()`, `update()` once per bar, `reset()` from `reset()`), no allocation per bar, `f64` everywhere with NaN for nothing:

- `./sdk/fmt`: `TextBuilder`, the allocation-free line builder the generated `sb_*` calls write into; `price`, `pct`, `signed`, `compact`, `time`, `duration`.
- `./sdk/clock`: `Clock` (hour, weekday, day/week/month keys, is-new-period, bar index, inferred interval, named zones with DST) and `Session` (`"HHMM-HHMM"` in a zone on listed weekdays, Sunday = 0).
- `./sdk/resample`: a higher timeframe from the chart's own bars, the built-ins' Timeframe semantics: `Resampler(tf.*, waitForClose)` fed `update(t, trade_date, o, h, l, c, v)` per bar (5m..4h rolling epoch keys, 1D/1W on `time.trade_date`; `closed()`, `last`, `forming`, `confirmed()`, `refused()`), `ClosedWindow` (push on `closed()`, `mean`/`wma`/`stdev`/`highest`/`lowest`/`sum`/`vwma`/`back` with the forming value as `x, withX`), `Smoothed("ema" | "rma", p)` (`commit`, `value`, `peek`). `refused()` blanks nothing: write NaN to every output while it is true.
- `./sdk/color`: `ink.*` packed colors, `fromHex`, `alpha`, `mix`, `lighten`, `darken` for drawing handles; `ColorScale`, `Thresholds` for a `color_by` bucket.
- `./sdk/ta-plus`: 26 textbook indicators the catalog lacks (`Dema`, `Tema`, `Zlema`, `Trix`, `Kama`, `Ultimate`, `Vortex`, `Aroon`, `Choppiness`, `AccDist`, `Nvi`, `Pvi`, `Pvt`, ...).
- `./sdk/stats`: `stats.*` list math over a `StaticArray<f64>` (`mean`, `stdev`, `slope`, `correlation`, `median`, `percentile`, ...) and `History` (`x[n]`: `push`, `ago(n)`).
- `./sdk/orderflow`: `delta`, `deltaPct`, `Cvd`, `VolumeProfile` (POC, value area), `BookImbalance`, `Absorption`, `LiquidationBurst`.
- `./sdk/levels`: `PeriodLevels`, `SessionLevels`, `PivotPoints` (standard, fibonacci, camarilla, woodie), `roundLevels`, `SupportResistance`.
- `./sdk/structure`: `Swings`, `MarketStructure` (BOS, CHoCH), `FairValueGaps`, `OrderBlocks`, `Divergence`, `candles.*` predicates.

The public reference is `docs/indicators/functions/` (text-formatting, time-and-sessions-kit, colors-kit, extra-indicators, order-flow-kit, levels-kit, market-structure-kit), one worked sample per class; `docs/indicators-internal/llms.txt` is the kit primer.

The loop:

1. **`wrun_author`**: pick the closest `template`, then write the AssemblyScript `source` (and `metadata` if the inputs/outputs/params differ from the template). The four exports are an EXACT contract, do not redesign it: `export function init(): void`, `export function state(): i32`, `export function finalize(): void`, `export function reset(): void`. No parameters, no return values except state's i32 (1 = a row is ready, 0 = warmup). Values flow ONLY through the generated accessors: params reach `init` via `p_<param>()`, each bar's inputs reach `state` via `in_<input>()`, every output is written in `finalize` via `out_<output>(value)` and the row is committed with `emitRow()` LAST; ALL persistent state lives in module-level variables (`reset` clears them and calls `.reset()` on every TA object). WORKFLOW: call `wrun_author` once with just `name` + `template` and READ the returned `source`, then EDIT that shape rather than writing from memory. The tool lints submitted source at the write step and returns the deviations as `warnings`; fix every warning before building. This is local scratch work, no approval needed. Two failure modes to know by name:
   - Redesigned signatures (`init(args: Array<f64>)`, `state(state, inputs)`, a `finalize` that returns the value) DO compile under asc; nothing stops them until the build's static ABI check refuses the module (`WRUN export 'init' has signature (i32) -> void; the wrun-1 contract requires init() -> void`). `wrun_author` already warns at the write step (`'init' must take NO parameters (found 'args: Array<f64>')`), so a warning-free author is the cheap fix.
   - Raw positional slot literals (`getFloat(0)`, `getInt(0)`, `wrun_arg_f64(0)`, `wrun_arg_i32(0)`, `setOutput(0, ...)`, `wrun_output_f64(0, ...)`) are refused BEFORE the compiler runs, because slots silently rebind when metadata params/inputs/outputs change: `wrun_author` warns `wrun_build will fail: src/indicator.ts:<line> uses positional getFloat(0); use in_close() from ./gen/inputs in state() or p_period() from ./gen/params in init()`, and `wrun_build` throws `scaffold build blocked: raw positional slot literals silently rebind when metadata params/inputs/outputs change` with one such line per finding. Variable indexes stay legal and comments are ignored; `src/sdk/sdk.ts` (the raw `getFloat`/`setOutput` wrappers) exists for variable-index access only.
2. **`wrun_build`**: compile it. On a compile error it throws with the diagnostics: read them, rewrite via `wrun_author`, build again. Iterate until it builds. A successful build regenerates `src/gen`, runs the local AssemblyScript build (the CLI receipt prints `Compiler: assemblyscript (bun run build)`), checks the module statically against the wrun-1 export ABI, ALSO installs the draft locally, and returns the receipt (`installed.path`, `installed.removeCommand`, `metrics`, any `warnings`): the user commissioned this draft by name, so that commission IS the consent (do not ask again); state the receipt (installed path + `om wrun remove <package>` as the undo) instead of asking. `package_install` is NOT part of this loop: it is for REGISTRY packages, where someone else's code enters the user's daemon, and there the ask stays. Opaque builds (`om wrun build --wasm <module.wasm>` or `--compile-command`, CLI-only) skip the accessor lint, so their receipt carries `positionalAbi: true` (text: `ABI: positional (metadata order binds params and inputs)`): params and inputs bind by metadata POSITION, so never reorder the metadata entries of such a package; scaffold builds are name-attached and omit the flag.
3. **Preview**: straight after a green build, `metric_get` the new `wrun/...` metric on a symbol so the user sees a real value; `metric_series` (same selector, `bars` 1..500, default 30) when they want to see it MOVE, one `[barOpenSec, value]` pair per bar (CLI `om metric series` renders a sparkline; metrics.md §"Series"); and `chart_indicator_preview` draws the draft on their chart (no publish needed; `plot: "line"` outputs only, one output per preview).
4. **Publish**: `package_publish` the same `packageDir` once the user approves. The human always approves publishing. Before publishing, AUTHOR UNDER A PUBLISHABLE SCOPE: `@local` is reserved and the registry rejects it; re-author the same source/metadata under the user's own scope (their account scope, e.g. `@om-core` if they own it) so the publish can succeed. Publish is also what unlocks hosted charting (bindable packages excepted, §"Bindable odds inputs"): `chart_indicator_add` mounts registry packages only (`marketplace.md §"Indicator packages"`); the local preview never needs it.

Keep inputs to declared SDK sources; daemon-only `series` inputs read watch values or installed series snapshots (§"Snapshots, panels and pane placement"). The module has no network of its own. Every `inputSources` pin is fixed at authoring time and no pin is user-configurable after install (repointing a PINNED odds input is `om wrun source set` on the authoring workspace followed by a rebuild; a code-first workspace edits the `input(...)` declaration instead; the consumer-side write-up is `marketplace.md §"Indicator packages"`). Before publish, a wrong pin is fixed in the normal loop (re-author, rebuild, reinstall the preview); after publish it can only be fixed by publishing a bumped version.


<!-- AUTO: CODE-FIRST AUTHORING - do not edit by hand; source: docs/indicators (snippet: code-first); regenerate with `bun packages/cli/scripts/gen-indicator-docs.ts` -->

## Source-declared indicators (code-first)
Declarations in the source, sheet derived at build: the grammar, the refusals, and the wrun-2 notes; read before editing a workspace whose sheet says `generated_from`.

How this mode enters the agent loop, beside (never instead of) the metadata-first loop above:

- Scaffold code-first with `template: "sma-codefirst"` on `wrun_author` (or `om wrun create @scope/name --template sma-codefirst`): a complete SMA in 14 non-blank source lines, sheet derived, same build and preview loop as any draft. For the wrun-2 surface (a celled volume-profile input, a string slot, a text renderer) scaffold `template: "vp-buy-share-codefirst"` instead and edit that shape. For a package that trades, scaffold `template: "strategy-ma-cross"` (a moving-average cross: `strategy({ ... })` declared beside the outputs, the order calls in `finalize()`) or `template: "strategy-risk-reversion"` (the risk per entry as a param linked into `qtyValue`, an ATR-sized stop and target re-armed each bar, a `positionSize()` guard) and edit that shape (§"A package that trades"). For a complete chart Indicator, scaffold the cookbook template nearest the ask (`om wrun templates` lists them by picker group: On price, Order flow, Dashboards, Beyond the time axis, Strategies) and edit that shape.
- On a code-first workspace, `wrun_author`'s `metadata` argument is REFUSED with `wrun_metadata_generated`, and `wrun_source_set` (`om wrun source set` on the CLI) is refused with `wrun_source_set_generated`: the sheet is derived state, so pass updated `source` with edited declarations instead, and the build re-derives sheet + accessors together.
- A string slot named `debug` prints in the chart editor's Console; off the chart (the daemon, `om metric`) it is an ordinary string slot with no special treatment.
- The grammar below is the chart's (the public docs share it). Off the chart the daemon also serves: input options `binding` / `bindingClasses` (a market bound per use) and `token` (the `token_supply` source); `missing: "nan"` / `"zero"` on the first input densifying the request grid; celled `tape.cells` (`[offset_ms, price, size, side]`, 4; `min_size` REQUIRED, `history` "0" = live prints only), a `symbol` + `exchange` pin pair on celled inputs, and `block_size` / `max_depth` as the book fetch facets. Metric composition inputs have no declaration spelling and stay metadata-first (refused by name). A workspace with no declarations stays metadata-first: byte-identical to a hand-written sheet and the supported mode for languages without an extractor (Rust, Zig, a pre-built module); a sheet claiming generated provenance over a declaration-free source blocks the build naming both ways out (restore the declarations, or delete `generated_from` and `source_digest` to hand-edit). The chart's editor refuses a declaration-free source.
- `abi_version: "wrun-2"` is additive (scalar wrun-2 packages compute bit-identically to wrun-1). Celled inputs (`cellType: "array"` + required `max_cells`, counted in source tuples) read the celled source classes and FETCH LIVE for `volume_profile` ([low, high, buy, sell] cells) and `book` ([price, size, side] cells; `block_size` required, `om block-sizes` lists the venue's); `trade_volume_by_size` is declared but refused by name (`wrun_cells_unavailable`). Backtests and screens refuse whole celled packages by name (`wrun_celled_metric_unsupported`); alerts, `metric_get`/`metric_series`, and chart previews are the supported consumers.
- wrun-2 sheets may also declare `string_slots` (byte-capped per-bar text written in `finalize()` via generated `str_<slot>` senders; slots are never metrics), `renderers` (`text`, `label`, `table`, `shape`, `stats_row`), `drawings` (`line`, `box`, `polyline`, `label`; coordinates from named outputs, x in epoch seconds), and per-bar `boxes` / `segments` (`box(...)` / `segment(...)` over declared outputs with bar offsets and an optional `when` gate; sheet-only, ABI-neutral). Modules read celled blocks through generated `in_<input>_cells()` / `in_<input>_read(ptr)` accessors; raw `wrun_arg_len` / `wrun_arg_bytes` / `wrun_output_str` literals are a scaffold build error like any positional access.

Declare params, inputs, and outputs as typed top-level statements of the
indicator's file (`src/indicator.ts` in the package), imported from
`./sdk/declare`; Run derives the sheet, `wrun/metadata.json`, from them:

```typescript
import { input, line, lower, ohlcv, output, overlay, param } from "./sdk/declare";

param("period", 14, { min: 2, max: 200, description: "Lookback window" });
param.bool("show_raw", true, { label: "Raw line" });
input("close", ohlcv.close);
input("btc_close", ohlcv.close, { symbol: "BTCUSDT", exchange: "BINANCE_FUTURES" });
output("value", line, lower, { unit: "score", label: "Score", format: "0.00" });
```

The build extracts the declarations statically (the code never runs at
build time), derives the sheet, and generates the accessors from the
same in-memory object, so the two cannot disagree. The grammar is static
and literal-only:

- `param(name, default, options?)` with options `required`, `min`, `max`,
  `description`: a number field, read in `init()` through `p_<name>()`.
- `param.<kind>(name, default, options?)`, a typed setting: the kinds are
  `int`, `number`, `bool`, `choice`, `color`, `time`, `price`, `range`,
  `multi`, `list`, `source`, `timeframe`, `symbol`, `session`, each
  naming the control the settings dialog draws and its literal default
  (a number; `true` or `false`; a string; an array of strings, then the
  default string or strings, for `choice` and `multi`; `[lo, hi]` for
  `range`; an array of numbers for `list`; an `ohlcv.<field>` reference
  for `source`). Options, every key optional: `required`, `min`, `max`,
  `description`, `label`, `step`, `group` (`"Page"` or
  `"Page/Section"`), `row`, `hint`, `when` (the NAME of a `param.bool`),
  `hide` (with `when`), `slider` (needs `min` and `max`), `unit` (an
  array from `"price"`, `"ticks"`, `"%"`, `"atr"`), `unit_default`,
  `confirm`, and on `param.session` only `tz` (one of `UTC`,
  `America/New_York`, `America/Chicago`, `Europe/London`,
  `Europe/Berlin`, `Asia/Tokyo`, `Asia/Hong_Kong`, `Asia/Singapore`,
  `Australia/Sydney`). `min`, `max`, `step`, `slider` and `unit` are
  refused on a kind that is not a number field. Readers, all for
  `init()`: `p_<name>()` on every kind, `pb_<name>(): bool` on a `bool`,
  `p_<name>_lo()` / `p_<name>_hi()` on a `range`, `p_<name>(): f64[]` on
  a `list`, `p_<name>_start()` / `p_<name>_end()` / `p_<name>_tz()` on a
  `session`, `p_<name>_unit()` beside a number with `unit`
  (Typed inputs). `market.tick_size()` and
  `market.price_precision()` declare hidden settings the chart fills,
  read through `p_market_tick_size()` and `p_market_price_precision()`.
  A `range` counts as two sheet params, a `session` as three, a `list` as
  `max` + 1, a `unit` list as one more, and the sheet holds at most 64; a
  setting cannot take a name the chart keeps (`symbol`, `exchange`,
  `interval`, `transformations`, `ticksPerBar`, `currency`, `runMode`,
  `devViewerTier` and the overlay's own keys) or one that starts with
  `__style__`.
- `"@<param>"` as the value of `color`, an entry of `colors`, or
  `line_style` (on an output, a `render.text`, a `render.label` or a
  `render.legend`) binds that spot to a `param.color` (or, for
  `line_style`, a `param.choice` over `solid`, `dashed`, `dotted`); as the
  value of `interval` or `symbol` on an input it binds the pin to a
  `param.timeframe` or a `param.symbol` (the exchange comes from the
  symbol's default unless the input names one). The build writes the
  setting's default in the reference's place before the compiler runs
  and records the binding on the sheet (`style_targets`,
  `interval_param`, `symbol_param`, `field_param`), so the module's bytes
  never depend on a setting. A data-only output refuses a paint binding.
- `page(title)`, `section(title, { toggle?, collapsed?, when? })`,
  `divider()` and `note(text)` lay the settings dialog out in source
  order (settings before the first page land on "General"; `toggle` and
  `when` take a `param.bool` HANDLE bound with a top-level `const`;
  `note` text may hold `**bold**`); `presets({ Name: { param: value,
  ... } })` ships named settings sets (values as declared: numbers,
  `true` / `false`, a choice's label, a color string; a composite is set
  through its members, `band_lo`, `rth_start`); `legend({ title })` sets
  the legend's title template (`{{param}}` reads a setting). Sheet-only,
  compiled to nothing.
- `input(name, source.field, options?)` with options `exchange`, `symbol`,
  `interval` (`MINUTE`, `FIVE_MINUTES`, `FIFTEEN_MINUTES`,
  `THIRTY_MINUTES`, `HOUR`, `FOUR_HOURS`, `DAY`, `WEEK`, or the short
  spellings `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`; the derived
  sheet always carries the long word), `view` (with `interval` only:
  `"confirmed"`, the default, the latest leg candle closed as of the row's
  close and carried; `"forming"`, the row's own leg bucket folded from the
  leg market's rows at the primary interval up to and including it (an
  own-market `ohlcv` leg folds the primary rows, a pinned-market `ohlcv`
  leg that market's rows, an own-market `oi` / `funding` leg folds its
  rows per component, the declared field's suffix picking the one it
  reads), legs up to `WEEK`;
  `"is_new_period"`, 1 on a delivered row whose confirmed leg
  candle differs from the one the previously delivered row held, the
  first delivered row reading 1 when a candle is held, else 0; one input
  slot per view, read through the ordinary `in_<name>()`), `views` (with
  `interval` only, never beside `view`: the EXTRA readings of the leg as
  one comma-separated string of `forming` and/or `is_new_period`, each
  deriving one more input named `<name>_<view>` right after this one, the
  same source, field and pins, read through `in_<name>_forming()` /
  `in_<name>_is_new_period()`; the declaration itself stays the confirmed
  reading, and the derived sheet carries the three entries explicitly),
  `outcome`, `tenor`, `side`, `fund` (`etf_flow` only, required there: an
  ETF ticker or `"all"`), `missing` (`"carry"`, `"nan"`, or `"zero"`),
  `description`. Sources are bare member references to the feeds the
  chart serves: `ohlcv`, `trades`, `funding`, `oi`, `liquidations`,
  `implied_volatility`, `skew`, `etf_flow`, `odds`, `time`. There is no
  input that reads another indicator's outputs: each indicator on a chart
  computes on its own.
- `output(name, plot?, panel?, options?)` with plots `line`, `bar`, `area`,
  `histogram`, `candle`, `shape`, `scatter`, `none` (data-only), panels
  `overlay`, `lower`, and options `description`, `unit`, `color`, `colors`
  (the color_by palette, an array of string literals), `width`, `opacity`,
  `line_style`, `color_by`, `shape_where`, `displacement_bars` (an integer
  in -500..500; negative literals such as `-26` are fine), `width_by`, and
  `widths` (the per-bar width ladder, an array of numeric literals;
  `width_by` and `widths` go together, like `color_by` and `colors`), and
  the presentation keys `label` (the legend and Style page name),
  `format` (`"price"`, `"%"`, `"si"`, `"int"`, `"0"`, `"0.0"`,
  `"0.00"`, `"0.000"`), `legend` (false keeps the output out of the
  legend), `visible` (false starts it hidden), `price_line`,
  `axis_label`, `tooltip` (a template: `{{label}}`, `{{value}}`,
  `{{value:format}}`, `{{<output or slot>}}`), `hover` (an array of
  `block.*` constructors), `badges` (ANOTHER output, a ladder whose
  labels become chips), `hint`, `glow` (px), `corner` (px). The
  presentation keys reach the sheet only: the build strips them from the
  literal before the compiler runs, so an output declared with them
  compiles to the same bytes as one without. `output(...)` returns a
  handle; bind it with a top-level `const` when a `box`, a `segment` or a
  `hover` needs to name it.
- `hover(handle, [block.value(label, output, { format?, delta?, tooltip?,
  hint? }), block.spark(label, output, { bars?, color? }),
  block.gauge(label, output, { min, max, format? }), block.pill(label,
  slot, { color_by?, colors? }), block.rows(label?, [[label, output or
  slot, format?], ...]), block.meter(label, output, { min, max, marks?
  }), block.chips(slot or ladder output)])` is the hover card of an
  output, the top-level form of the `hover` key (one per output, either
  form). Outputs and slots are named by a bound handle or by their name
  as a string. Erased before the compiler.
- `range(upper, lower, options?)` declares a sheet-level band between two
  rendered outputs with options `color`, `colors`, `color_by`,
  `edge_width`, `edge_line_style`, `smooth`, `gradient`, `gradientMode`
  (presentation only, and ABI-neutral: declaring one never flips the
  sheet to `"wrun-2"`). `gradient` lists 2 to 8 CSS color strings (an
  array of string literals) from the top of the pane to the bottom,
  evenly spaced, and the chart shades the band's interior with that
  vertical gradient instead of the flat tint (a faded band).
  `gradientMode` (the sheet's `gradient_mode`) names the span the stops
  are laid over: `"pane"` (the pane height, the default), `"fill"` (the
  band's own vertical bounding box) or `"line"` (per column from `upper`
  down to `lower`, a heatmap under the line); it is refused without
  `gradient`. Ranges never dedupe:
  repeat the declaration for several bands, the same pair included (the
  sheet schema imposes no uniqueness).
- `box(name, options)` and `segment(name, options)` declare per-bar
  shapes over output HANDLES (Drawing objects). Box
  options: `top`, `bottom` (handles, required), `from`, `to` (bar
  offsets: integer literals in -500..500 or handles, default 0), `when`
  (a gate handle), `panel` (`"overlay"` or `"lower"`), `color`,
  `borderColor`, `opacity`, `borderWidth`. Segment options: `yFrom`,
  `yTo` (handles, required), `from`, `to`, `when`, `panel`, `color`,
  `width`, `lineStyle`. The derived sheet records output NAMES under the
  snake_case fields (`x_from`, `x_to`, `border_color`, `border_width`,
  `y_from`, `y_to`, `line_style`). ABI-neutral like `range`. A handle
  that binds no `output(...)` declaration, a string literal where a
  handle goes, a non-integer offset literal, or a `panel` outside the two
  names is a named build error.
- `alert(name, options)` declares an alert the script owns, over an output
  HANDLE: `when` (required, the handle of the output whose false-to-true
  edge fires it; any plot, a data-only `none` output included, so no 0/1
  line has to be drawn to get an alert), `message` (the fire text, with the
  delivery-time placeholders `{{symbol}}`, `{{close}}` and the rest) and
  `description` (the picker's sub-line), both up to 200 characters. Write
  the output from `finalize()` like any other: `const cross =
  output("golden_cross", none); alert("golden_cross_up", { when: cross,
  message: "{{symbol}} golden cross at {{close}}" });` and
  `out_golden_cross(fast > slow && fastPrev <= slowPrev ? 1.0 : 0.0)`. The
  derived sheet records the output's NAME under `alerts[].when`. Sheet-only
  and ABI-neutral, and erased before the compiler like `range(...)`: the
  sheet is its only reader, so its options can never move a module's
  bytes. At most 16 per package; the name follows the output grammar and
  shares the chart-object namespace with outputs, boxes, segments,
  renderers and drawings. An unbound handle, a string literal where the
  handle goes, a missing `when` or a duplicate alert name is a named build
  error.

The second runtime contract's vocabulary has declaration forms too, and
deriving a sheet that uses any of them stamps `abi_version: "wrun-2"`
automatically (scalar-only declarations keep the first contract):

- Celled inputs: `input(name, <class>.cells, options)` with the classes
  the chart serves and their tuple widths: `volume_profile` (`[low, high,
  buy, sell]`, 4), `book` (`[price, size, side]`, 3), `intrabar`
  (`[offset_ms, open, high, low, close, volume]`, 6: the finer bars
  inside each chart bar) and `options_chain`
  (`[strike, expiry_ms, side, oi, gamma, delta, mark_iv, underlying,
  multiplier]`, 9: the chart market's option chain on the live row only).
  The chart does not serve the live trade tape (`tape`) or
  `trade_volume_by_size`, and a run that declares either is refused by
  name. `max_cells` is REQUIRED; `block_size` (required on `book`) and
  `max_depth` are recorded in the sheet, while the chart serves the book
  it has stored for the chart row as it is; `description`. A celled input
  reads the chart's own market (the chart refuses a market pin on it).
  `intrabar` alone takes `interval` (REQUIRED: the finer
  bars' span, a whole divisor of the primary grid from the eight interval
  words or their short spellings, written to the sheet as the enum word;
  `max_cells` must hold every finer bar of a row, a 1h row holds 60 1m
  bars) and reads the selector's own market. `options_chain` alone takes
  `venue` (`"auto"` by default: the chart's own market when it is an
  options venue, else the coin's Deribit chain; `"deribit"` or `"cme"`)
  and `expiries` (`"all"` by default or `"nearest:N"`), reads the chart's
  own underlying (no pin pair) and sizes `max_cells` for the chain (a BTC
  chain is about 1,500 contracts). Every other scalar-feed knob
  (`side`, `missing`, `view`, `views`, ...) is refused on celled inputs.
- String slots: `string(name, { max_bytes, description? })`. The
  declaration is named `string`, which shadows the type name in a file
  that imports it; `import { string as slot }` keeps the type
  (String functions). A top-level `const s =
  string(...)` binds a handle a block, a tile or a legend entry may name
  the slot by; the build drops the binding before the compiler (the
  declaration returns nothing), so the bound form compiles to the bytes of
  the bare statement. A slot named exactly
  `debug`, written per bar in `finalize()` through its generated
  `str_debug(text)` sender, is the indicator's debug log: the chart
  editor shows its non-empty lines, oldest bar first, in its Console,
  capped to the newest 400 lines.
- Renderers: `render.text(name, { y, text, color?, size?, style?,
  tooltip?, hover?, badges? })`, `render.label(name, { x, y, text, color?,
  size?, style?, tooltip?, hover?, badges? })`, `render.table(name,
  { rows, cols, cells, position? })`, `render.shape(name, { output, shape,
  where?, color?, color_by?, colors? })`, `render.stats_row(name, { output, title?, format?,
  polarity? })`, `render.bgcolor(name, { where, color?, color_by?,
  colors? })`, `render.barcolor(name, { where, color?, color_by?,
  colors? })`. Numeric references name declared outputs; `text` and table
  `cells` name declared string slots. `style` is `"price_label"` on a
  text renderer and one of `"plain"`, `"price_label"`, `"pill"`,
  `"callout"`, `"badge"` on a label renderer; `style`, `tooltip`, `hover`
  and `badges` are presentation keys, stripped before the compiler like an
  output's. Two more words land under the sheet's `presentation` key
  instead of `renderers`, and are erased before the compiler:
  `render.legend(name, { text?, value?, format?, color?, color_by?,
  colors? })`, a legend entry (a string slot's words or an output's
  formatted value, colored by a ladder), and `render.hud(name, {
  position, title?, columns?, tiles })`, a card of `tile.*` constructors
  (the `block.*` vocabulary under its other name) at one of the nine
  anchors (Plotting).
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
- Box and segment coordinates are output handles bound by a top-level
  `const` (`let`, `var`, and `export const` bind too; a handle may be
  bound below the shape that uses it); the sheet records the output's
  name, never the handle. A section's `toggle` and `when` and a `hover`
  target are handles the same way.
- A typed setting's options belong to its kind, `when` names a declared
  `param.bool`, a `"@<param>"` reference names a setting of the kind the
  spot needs, a preset sets sheet params only, no setting takes a reserved
  name or collides with a name another setting derives (`band_lo`,
  `rth_tz`, `offset_unit`, `market_tick_size`), and the expanded sheet
  stays at or under 64 params.

The derived sheet records `generated_from: "declarations"` plus a
`source_digest` (sha256 of the source), serializes canonically (an
unchanged source rewrites nothing), and is DERIVED state from then on:
edit the declaration, never the sheet, and the next build derives the
sheet and the accessors again. In the chart's editor every indicator is
declared this way: a file with no declarations is refused at Run
("This indicator declares nothing. Add param(...), input(...), and
output(...) statements (imported from ./sdk/declare) at the top level of
the source; the metadata sheet is derived from them.").

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
- Scalar `source` must be one of: `ohlcv`, `trades`, `funding`, `oi`, `liquidations`, `implied_volatility`, `skew`, `token_supply`, `odds`, `metric`, `time`, `series` (there is no "market"/"price" source; close prices are `ohlcv`+`close`). A `time` input carries a fact of the primary bar (field `bar_open_sec`, its open in epoch seconds, the default; `trade_date`, epoch seconds at 00:00 UTC of its exchange trade date; `session`, 1 regular, 2 pre-market, 3 after-hours, 0 closed; never the primary input); the daemon refuses `trade_date` and `session` by name (`wrun_time_facts_unsupported`) on CME-group and US-equity venues, which the chart serves. A `series` input has `ref` instead of `field`, is never primary, and needs the daemon (§"Snapshots, panels and pane placement").
- Celled classes (`cellType: "array"` + `max_cells` on the input, the sheet at `abi_version: "wrun-2"`), five, with their tuple widths: `volume_profile` (`[low, high, buy, sell]`, 4), `book` (`[price, size, side]`, 3, `block_size` required), `tape` (`[offset_ms, price, size, side]`, 4, `min_size` required, daemon live only), `intrabar` (`[offset_ms, open, high, low, close, volume]`, 6) and `trade_volume_by_size` (declared, refused by name). kScript `ltf()` -> `intrabar.cells`: `input("m1", intrabar.cells, { interval: "1m", max_cells: 60 })`, the `interval` REQUIRED and a whole divisor of the chart's from the eight interval words (finer than the chart's: a coarser leg is `ohlcv` with an `interval` and a `view`), own market only, ohlcv only, `max_cells` at least the finer bars per chart bar (a 1h bar holds 60 1m bars, `wrun_intrabar_ratio_over_cap` names both numbers); the tuple carries `offset_ms` (kScript's `c[0]` = `in_time_sec() * 1000 + offset_ms`) and CLOSED finer bars only (an Indicator is FRESHER than the browser kScript lane, which froze `ltf` cells after the fetch); a covered bar with no finer bars reads 0 cells, a bar the finer history does not reach reads -1, blocks are never truncated. Browser hosts serve it; `om metric`, watches and previews refuse it by name (`wrun_intrabar_unsupported`) while `wrun_build` compiles it.
- A `shape_where`/`color_by` gate must be a DIFFERENT output (usually `"plot": ""` data-only); an output cannot gate or color itself.

## Input pins
Fixed-market pins (`symbol` + `exchange` together, primary follows the selector); `interval` pins are legal, on the as-of clock, with a `view`: confirmed, forming, is_new_period.

**Cross-symbol pins.** A non-odds, non-time FEED source may pin `symbol` and `exchange` TOGETHER so a secondary input reads a fixed reference market while the rest of the package follows the selector: `"btc_close": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES" }` gives any alt selector a BTC context input (ratios, cross-venue context). The pair rule is SCHEMA-ENFORCED: a lone `symbol` or a lone `exchange` is refused with the issue on the missing half (`feed sources pin a fixed market with symbol AND exchange together (never one alone: symbols are venue-native, so a lone symbol or a lone exchange names a market that does not exist on that venue); pin both, or omit both to follow the selector`). The rest is authoring policy the schema cannot check:
- Pin `symbol` and `exchange` together, never one alone: symbols are venue-native strings (`BTCUSDT` on BINANCE_FUTURES is `BTC` on HYPERLIQUID).
- Keep the PRIMARY input (index 0) selector-following; pins belong on secondary context inputs. A package with every input pinned computes the same value for every selector symbol (screens and chart legends mislabel it).
- Cross-symbol price/notional arithmetic is only dimensionally sane under the shared default USD quote (normalization covers ohlcv/trades/oi). Never mix with `quote: COIN`; avoid native-cross raw symbols (no per-source quote override).
- Exceptions: `odds` keeps its own rule (conditionId as `symbol`, exchange implicitly Polymarket); `time` takes no knobs; do not pin `metric` composition sources.
- Packages with cross-symbol pins are UNVERIFIED on hosted charts: keep them off `chart_indicator_add` until the chart lane verifies pins (odds-pinned packages chart as they always have), and a signal on a pinned-package metric must use `eval: "bar"` — `marketplace.md §"Indicator packages"`.

**Interval pins and the as-of clock.** `interval` is an independent pin on any feed source (odds included), and it is legal. A symbol/exchange pin alone still reads on the SELECTOR's interval and quote; an `interval` pin moves that one source onto its own grid, `"btc_4h": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES", "interval": "FOUR_HOURS" }`, and a bare `{ "source": "ohlcv", "field": "close", "interval": "DAY" }` reads the selector's own market on the daily grid. Causality is the engine's job, not the author's: a source COARSER than the primary grid (an explicit coarse pin, or an unpinned secondary that inherits the selector's interval when the primary input is pinned finer) contributes to a primary row only as-of its candle CLOSE, `candle.ts + sourceSec <= min(now, row.ts + primarySec)`: the value becomes visible on the first primary row whose own close is at or after the source candle's close, and never before evaluation time, so a forming 4h candle never leaks its final value into the 1h rows under it, live or historical; sparse coarse observations (odds) carry the latest CLOSED observation forward; an observation older than two source intervals before the window head reads as not-ready. Equal or finer sources align by bar open, row for row, exactly as an unpinned source does. Any interval validates; compatibility with the primary grid is resolved at runtime, not by schema. What it costs: a coarse leg needs its own history (the fetch widens by two source intervals) and its value steps once per source candle, so a `DAY` pin on a `MINUTE` primary is a step function. Hosted chart runs apply this same clock to interval-pinned inputs (the build writes the sheet's interval as the enum word, `FOUR_HOURS`, whatever the declaration spelled, so every host reads one spelling); the in-browser run of a pinned package is being brought onto it, so until then preview a pinned package on your machine.

**Views of a pinned leg.** An `interval`-pinned input carries one of three readings, chosen with `view` (absent = `"confirmed"`), each its own input slot read through the ordinary `in_<name>()` and each computed by the HOST at alignment, never by the module. `"confirmed"` is the rule above: the latest leg candle closed as of the row's close, carried forward, `NaN` before the first one under `missing`, gating readiness as today. `"forming"` is the row's own leg bucket folded AS-OF from the leg market's rows at the PRIMARY interval up to and including this row (open = the bucket's first primary open, high = max, low = min, close = the last joined row's close, this row's when the market has a row at its ts, volume = sum; the declared field picks the component; every row of the leg market inside the bucket with ts <= the row's ts joins, whether or not the primary grid has a row at that ts, and never-partial is judged on the fold source's own coverage): an own-market `ohlcv` leg folds the primary rows themselves, a pinned-market `ohlcv` leg (`symbol` + `exchange` beside `interval`) folds that market's rows at the primary interval as a second fetch beside the leg candles (the daemon preview reads that market's live bar off the same fetch), an own-market `oi` leg folds its rows per component the same way (open = the first real observation's open, high = max, low = min, close = the last close) and an own-market `funding` leg folds its `rate_*` (or `predicted_*`) family the same way, the declared field's suffix picking the component (`rate_close` = the bucket's last observation, `rate_high` = its max; `NaN` when none yet; a gap-fill row with no real observation never enters a fold); legs up to `WEEK`; it never gates readiness, and on the closing row it equals the confirmed value. `"is_new_period"` is `1` on a delivered row whose confirmed leg candle differs from the one the previously delivered row held (the first delivered row reads `1` when a candle is held), else `0` (`0` on the live forming row until its close lands the next candle); it never gates readiness, so a ring or a per-period reset keys on it instead of on bucket math. The rule to write by: inside your own handler you read `forming`, every other input reads `confirmed`. Code-first, `input("close_4h", ohlcv.close, { interval: "4h" })`, `input("close_4h_live", ohlcv.close, { interval: "4h", view: "forming" })`, `input("new_4h", ohlcv.close, { interval: "4h", view: "is_new_period" })`, or all three readings from ONE declaration with the `views` sugar: `input("close_4h", ohlcv.close, { interval: "4h", views: "forming,is_new_period" })` derives `close_4h` (confirmed), `close_4h_forming` and `close_4h_is_new_period`, in that order right after the base slot, same source, field and pins, read through `in_close_4h()`, `in_close_4h_forming()` and `in_close_4h_is_new_period()`; the sheet stays explicit (three `inputSources` entries, `views` never lands on it), so every host reads it unchanged. `views` is a comma string like `bindingClasses`, listing only the extra readings (`confirmed` is the declaration itself); it is refused beside `view`, without an `interval` pin, on a duplicate or unknown name, and a derived name that collides with a declared input refuses by name. In a hand sheet, `"view": "forming"` beside `"interval"`. Typed-feed interval pins (own-market `funding` / `oi`, coarser than the primary) bucket by the clock on every host: `"confirmed"` = the feed's last observation inside the latest CLOSED bucket (bucket end <= min(now, ts + P); an `oi` bucket folded per component, a `funding` bucket the same fold over its `rate_*` or `predicted_*` family, `rate_close` reading the last observation and `rate_high` the max), carried forward under `missing: "carry"` (abstaining before the first held bucket), `NaN` for a closed empty bucket under `missing: "nan"` (`0` under `"zero"`), `NaN` before the first closed bucket; `"forming"` = the row's own bucket folded from the observations up to and including the row, `NaN` when none yet; `"is_new_period"` = `1` on the delivered row whose held closed bucket differs from the previous delivered row's, so it fires on a bucket close with or without an observation; the feed is fetched at the primary interval and bucketed by the host (a typed feed pinned to a fixed market, or declared bindable, keeps the candle clock). `WEEK` legs open Monday 00:00 UTC on every host (every leg up to `DAY` floors from the epoch), and the whole-multiple rule reads seven days on them. Refused by name: a `view` without `interval`, on the primary input (it IS the forming bar), on celled, `time`, `metric` and `series` sources, beside `binding`, and `"forming"` off `ohlcv` or an own-market `funding` / `oi` leg (a pinned-market typed feed reads confirmed), past `WEEK`, or over a primary that is not own-market `ohlcv` or is bindable (`binding: "optional"`: a use could rebind the rows the bucket is folded from, so the plan checks the primary again after bindings resolve; the rule holds for every forming leg, pinned-market and typed-feed ones included). Four rules every host shares: a viewed leg must be a whole multiple of the primary interval and coarser than it (`FOUR_HOURS` over `HOUR`, `WEEK` over `DAY`; never equal: the primary bar is already the forming view, and an equal-span confirmed reading would expose the still-forming candle), refused by name at the sheet when the primary pins its interval and at plan time otherwise; the new-period signal compares delivered rows only (its cursor advances on every primary row whatever another input's readiness does), so a row another input abstains never swallows a landed candle and input order never moves the `1`; the forming fold keeps validity per component, so a `NaN` high on one bar never discards that bar's close, low or volume; and a bucket is never shipped partial: the fold's read reaches back to the bucket's start (the primary fetch for an own-market leg, the second fetch for a pinned-market one), and a bucket the data still does not reach from its start reads `NaN` in every component.

- Permissions: `read:openmarket` covers every feed source and is required whenever any FEED source follows the selector (metric and time sources need no permission), so the standard shape needs only `read:openmarket`; templates already carry it. Venue reads (`read:binance`, `read:bybit`, `read:hyperliquid`, `read:polymarket`) are a NARROWING option only for packages whose every feed source pins one of those four venue families; the check fires only when `read:openmarket` is absent, and a pin outside those families still requires `read:openmarket`.

## Bindable odds inputs
Per-use bindings: an odds input declared `binding: "required"` takes any Polymarket market; a feed or metric input declared `binding: "optional"` reads what the call names.

- Bindable inputs: a scalar feed or metric input may declare `binding: "optional"` with `bindingClasses` (the classes a use may bind it to, as one comma-separated string in code-first declarations: `input("close", ohlcv.close, { binding: "optional", bindingClasses: "ohlcv,funding,oi,metric" })`; `ohlcv`, `funding`, `oi`, `liquidations` and `metric` are the bindable classes; a sparse class such as `liquidations` on the primary input needs `missing: "zero"` or `"nan"` declared on that input, or the binding is refused). Unbound, the input reads its declared source; a use may bind it to a feed (`sourceBindings: { close: { source: "oi", field: "close" } }`, or by the feed metric's name, `{ close: { metric: "open_interest" } }`) or a metric (`{ close: { metric: "rsi" } }`). The stock `zscore`, `wma`, `sma` and `ema` declare `close` this way.
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

## A package that trades
The door for an order builder, per-fill logic or a rule no condition or sizer expresses: an Indicator package whose source declares `strategy(...)`; read before authoring one.

- Pick: `strategy.md`'s intro is the menu; this door is for what its rows do not place.
- Replay: `backtest_run` or `backtest_spec` with `wrun_strategy: "@scope/name"`, `params` by declared name.
- Pages: `docs/indicators/strategies/`, starting at `overview.md`, `first-strategy.md` and `writing-strategies.md`; the tester's output reads with `reading-the-tester.md` and `stats-reference.md`.
- Templates: `strategy-ma-cross` (a moving-average cross: `strategy({ initialCapital, qtyType, qtyValue, commissionPercent, slippageBps })`, `Cross.update`, `strategy.long("L").send()` and `strategy.closeAll()` in `finalize()`, a `range(...)` ribbon and cross marks on price) and `strategy-risk-reversion` (an RSI reversion: `const risk = param("risk_pct", ...)` linked into `qtyValue`, `strategy.exit("Protect").from("Dip").stop(stopPrice).limit(targetPrice).send()` re-armed while `strategy.positionSize() > 0`, both distances in ATR, each trade's rails as line handles); scaffold one on `wrun_author` and edit that shape.
- Build: the same loop (§"The authoring loop").

## Chart placement and styling
Declare numeric plot placement and styles in the sheet; use this section for palettes, gates and style knobs.

**Chart placement basics**, per output: `plot` is one of `line|bar|area|histogram|candle|shape|scatter|inset` (or `""` for data-only), `panel` is `overlay` (price chart) or `lower` (own pane), `unit` (`price`, `%`, else abbreviated) sets the axis format. Insets, frame panels and anchored handles have their own placement rules in §"Snapshots, panels and pane placement". `wrun_author`'s `display_name` names the package in chart legends and listings.

**Chart styling** for numeric outputs is declared in metadata: the module emits decisions and the sheet maps them to looks. Handle styling uses the generated drawing API (§"Snapshots, panels and pane placement"). Vocabulary:
- Static, on any output: `color`/`colors`, `width`, `opacity`, `line_style`.
- Per-bar coloring: emit the decision as an ordinary output (e.g. regime 0/1) marked `"plot": ""` (data-only, never drawn), then on the styled output set `color_by: "<that output>"` + a `colors` palette (at least 2 entries); each bar's floored value indexes the palette; a missing or out-of-range index falls back to entry 0. An output cannot color itself.
- Gated markers: a `plot: "shape"` output with `shape_where: "<gate output>"` renders only where the gate is nonzero.
- Band declarations: `ranges[].upper/lower` (`range(...)` code-first) reference two rendered outputs and the browser draws a filled band between them (edge width, line style, palette, or a vertical `gradient` with its `gradient_mode` span in place of the flat tint; §"Source-declared indicators (code-first)" spells both). `fills[].between` is accepted but not drawn; a fill between two line handles has no object, so use per-bar `box(...)` slices for that shape.
- User style knobs: a param with `style: { "output": "<name>", "property": "color"|"width"|"opacity"|"lineStyle" }` never reaches the module (no `p_` accessor, its slot stays zero-filled), shows in the settings dialog (color knobs take string defaults like "#22c55e"), and redraws without recompute. Param names are lowercase (`line_color`).
Emit decisions in the module and declare plot styles here; author/build validation names broken references.

## Snapshots, panels and pane placement
Choose per-bar history, a run snapshot or a persistent drawing to match the requested view; use these words for profiles, panels, compact widgets and HUDs.

Name every dependency, match each frame's payload to its consumer, and preserve
missing values. Declare only the families the requested view needs.

### Frames and panels

Declare `frames[]` with `frame(name, { max_bytes })` from `./sdk/declare`.
Write UTF-8 JSON in `finalize()` through `./gen/frames`: a frame rebuilt per
bar or live tick is built with `fb_clear()`, `fb_text(s)`, `fb_str(s)`,
`fb_int(n)`, `fb_f64(x, decimals)`, `fb_num(x)` and sent with
`writeFrameBuffer(slot)` (allocation-free); a small one-shot string goes
through `writeFrame(slot, json)`. The slot is the bound `frame()` result or
generated `FRAME_<NAME>`.
Frames require `wrun-4`: each slot holds the latest snapshot for the whole run,
never a history row. An unwritten frame omits its view; malformed payloads refuse
selection. Up to 8 frames, 96 KiB each; frames and strings share 2 MiB in transport.

| View | Sheet and declaration | Payload and bounds |
| --- | --- | --- |
| Docked profile | `levels[]`; `plot.levels({ name, frame, dock, width_frac, poc, labels })` | Frame `{ prices, values, colors? }`: 1..512 strictly monotonic prices, matching values, null gaps; at most 4 profiles; left/right dock, width fraction 0.05..0.5. |
| Separate panel | `panels[]`; `panel.bars`, `panel.line`, `panel.scatter`, `panel.histogram`, `panel.pie`, `panel.heatmap`, `panel.table`, `panel.tiles` | Every declaration binds a frame and names `name`, `title`, `x` and `place`; frame `{ rows }`. At most 8 panels. |
| Price ladder | `drawings[]`, kind `ladder`; `draw.ladder({ name, frame, side, divider })` | Frame `{ rows, divider? }`: 1..64 `[price, value, fraction, color?]` rows; fraction 0..1, value nonnegative; side left/right. |
| Text feed | `drawings[]`, kind `feed`; `draw.feed({ name, frame, anchor, offset, z })` | Frame `{ lines }`: 1..50 `[time, text, color?]` lines; time in epoch milliseconds, text 1..80 characters. |

Panel `x` is time, index or category; `place` is below or side. Bars, line and table
declare 1..8 `series`; other kinds omit it. Histogram and heatmap use category x.
Bars/line rows carry a key followed by one value per series; table rows contain
only cells. Time keys use epoch seconds. The general cap is 2000 rows; table has
32 rows, pie and tiles 24. Styled table cells and tiles can carry 1..64-point sparks.

### Insets and compact widgets

`outputs[].plot: "inset"` plus `inset` is `out.inset(name, { dock, height_px, shape })`:
a per-bar numeric output, written through `out_<name>` and `emitRow()` like any
other output. Dock top/bottom, height 16..120 px, shape histogram/area/line.
Insets work on every ABI. Ordinary lines use `output(name, line, overlay)`;
`out.line` is not a declaration in this SDK.

`draw.card(name, { title, rows, anchor, offset, z })` declares a `drawings[]` card:
at most 8 cards, 12 rows each. A row's `spark: { output, window }` names a numeric
output and takes its last 2..64 ready values, oldest first, independently of text.
`draw.meter({ name, label, fraction: { output }, ramp, text, anchor, offset, z })`
reads the last ready fraction output: emit 0..1, use 2..5 ramp colors; text is a
literal or `{ slot }`. Cards and meters need no frame. All drawings share a
64-declaration cap; the expanded render selection has a separate 2 MiB cap.

### Anchored handles and watch series

Declare `handles.line`, `handles.box`, `handles.label` or `handles.polyline` with
an optional `anchor` default. These populate the sheet's `handles` map and require
wrun-3 or later. Runtime objects come from `draw` in `./gen/draw`; after `set`,
`.anchor(ANCHOR_TOP_LEFT)` places them in CSS pixels from that pane spot.
The nine corner/centre spots change both axes; top/bottom change only y,
left/right only x. Unanchored x is epoch seconds and y is price.
Right/bottom offsets point inward; negative offsets are allowed, with no implicit
inset. `ANCHOR_CHART` restores chart coordinates. A label handle also takes `align`
(`left`, `center`, `right`): the text edge that sits on x, (x, y) staying the anchor
point; `handles.label({ align: "left" })` is the default, `.align(ALIGN_RIGHT)` or
`style.align(label, ALIGN_RIGHT)` changes a live label, `ALIGN_DEFAULT` restores
centred text. Reuse object ids across bars:
500 live per kind, 1500 total, 4096 draw calls per row, 256 points per polyline.

Use a metadata-first workspace for `inputSources[name]` with `source: "series"`,
`ref` equal to `watch/<slug>/<key>` or an installed `@scope/name`, and optional
`missing: "carry"` (default) or `"nan"`. Series works on every ABI but is daemon-only,
never the primary input, and takes no `field` or market pins. Read it through
`in_<name>()`. Values bucket to the primary grid; the last reading wins and carry
uses only an earlier or current bucket. There is no code-first series declaration;
do not add one or patch a generated sheet. Chart hosts cannot supply this input,
and a line-only `chart_indicator_preview` does not prove any frame or HUD rendered.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `wrun_create`
  - `dir` — Defaults to the package short name.
  - `source_mode` — `open` (the default; the manifest carries no source block) ships the source entry beside the module, the registry serves it to readers; `compiled` ships the module alone and the source stays local; `hosted` ships the module alone to run on…

<!-- AUTO: END ARGUMENT CONTRACT -->

## CLI equivalents
The shell forms of the authoring loop — `om wrun create` scaffolds a workspace on disk, `om wrun build --install` compiles and installs it — and the command-to-action mapping.

`om wrun create <@scope/name> [dir] --template <id>` scaffolds an authoring workspace (the same template `wrun_author` returns as `source` when given the same `template`; the CLI defaults to `conviction-score`, both actions to `sma`); `om wrun build <dir>` compiles it and installs the draft locally only with `--install` (`om wrun install <dir>` does both in one step — the MCP `wrun_build` always installs); `om wrun remove <package>` is the undo. The four odds templates (`polymarket-odds`, `conviction-score`, `event-asset-divergence`, `escalation-risk`) are code-first: their placeholder market is repointed by editing the `symbol` of the `input(<name>, odds.close, { symbol: "0x...", outcome: "YES" })` declaration in `src/indicator.ts` and rebuilding; `om wrun source set` serves hand-written sheets only (`sma` and `series-address` are the two left). Opaque WRUN builds are CLI-only too: `om wrun build <dir> --wasm <module.wasm>` (a pre-built module) or `--compile-command "<cmd>"` (an external compiler writing the wasm as its last argument) export a package whose receipt says `ABI: positional (metadata order binds params and inputs)`; those packages must never have their metadata entries reordered. The command-to-action mapping:

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

- `om wrun create` (action: `wrun_create`) — Scaffold an Indicator authoring workspace.

<!-- AUTO: END COMMAND REFERENCE -->
