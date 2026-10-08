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

**Kit modules.** `src/sdk/ta.ts` has ten siblings, every scaffold ships them, and the compiler reads a module only when the source imports it. Same shape as the TA classes (construct in `init()`, `update()` once per bar, `reset()` from `reset()`), no allocation per bar, `f64` everywhere with NaN for nothing:

- `./sdk/fmt`: `TextBuilder`, the allocation-free line builder the generated `sb_*` calls write into; `price`, `pct`, `signed`, `compact`, `time`, `duration`, and `mask` (`sb_mask(x, "#.##")`: Pine's `str.tostring(x, mask)` as TradingView spells it).
- `./sdk/clock`: `Clock` (hour, weekday, day/week/month keys, is-new-period, bar index, inferred interval, named zones with DST) and `Session` (`"HHMM-HHMM"` in a zone on listed weekdays, Sunday = 0).
- `./sdk/resample`: a higher timeframe from the chart's own bars, the built-ins' Timeframe semantics: `Resampler(tf.*, waitForClose)` fed `update(t, trade_date, o, h, l, c, v)` per bar (5m..4h rolling epoch keys, 1D/1W on `time.trade_date`; `closed()`, `last`, `forming`, `confirmed()`, `refused()`), `ClosedWindow` (push on `closed()`, `mean`/`wma`/`stdev`/`highest`/`lowest`/`sum`/`vwma`/`back` with the forming value as `x, withX`), `Smoothed("ema" | "rma", p)` (`commit`, `value`, `peek`). `refused()` blanks nothing: write NaN to every output while it is true.
- `./sdk/color`: `ink.*` packed colors, `fromHex`, `alpha`, `mix`, `fromGradient` (Pine's `color.from_gradient`, alpha-weighted as TradingView blends), `lighten`, `darken` for drawing handles; `fromPacked(p_<name>())` reads a `param.color` into such a colour (never `i32(p_<name>())`, which paints purple or cyan); `ColorScale`, `Thresholds` for a `color_by` bucket.
- `./sdk/ta-plus`: 26 textbook indicators the catalog lacks (`Dema`, `Tema`, `Zlema`, `Trix`, `Kama`, `Ultimate`, `Vortex`, `Aroon`, `Choppiness`, `AccDist`, `Nvi`, `Pvi`, `Pvt`, ...).
- `./sdk/stats`: `stats.*` list math over a `StaticArray<f64>` (`mean`, `stdev`, `slope`, `correlation`, `median`, `percentile`, ...), `History` (`x[n]`: `push` first in `onBar()`, then `ago(n)`), `List` (Pine's `array` with its capacity fixed in `init()`: `push` refuses when full, `pushEvict` drops and returns the oldest, `pop`, `shift`, `unshift`, `get`/`set`/`insert`/`remove` with a negative index counting from the end, `sort`, `sum`/`mean`/`min`/`max`/`stdev`), `HandleRing` (the newest N drawing ids; `push(id)` returns the oldest id to delete, or -1) and `roundTo(x, decimals)` (halves away from zero, Pine's `math.round(x, n)`).
- `./sdk/orderflow`: `delta`, `deltaPct`, `Cvd`, `VolumeProfile` (POC, value area), `BookImbalance`, `Absorption`, `LiquidationBurst`.
- `./sdk/levels`: `PeriodLevels`, `SessionLevels`, `PivotPoints` (standard, fibonacci, camarilla, woodie), `roundLevels`, `SupportResistance`.
- `./sdk/structure`: `Swings`, `MarketStructure` (BOS, CHoCH), `FairValueGaps`, `OrderBlocks`, `Divergence`, `candles.*` predicates.
- `./sdk/options`: `OptionsChain(maxStrikes)` loads an `options_chain` block on the live bar (`load(cells, count, nowMs, spot, nearest, windowPct)`: expiries after `nowMs`, the `nearest` soonest, strikes within `windowPct` of spot) and answers per strike `strike`, `callOi`/`putOi`, `callGex`/`putGex`/`netGex`, and for the chain `totalCallGex`/`totalPutGex`/`totalNetGex`, `zeroGamma`, `callWall`, `putWall`, `maxPain`, `putCallRatio`, the Gamma Map template's math; `OPTIONS_TUPLE` (10) is the row width. Pine has no counterpart.

The public reference is `docs/indicators/functions/` (text-formatting, time-and-sessions-kit, colors-kit, extra-indicators, order-flow-kit, levels-kit, market-structure-kit, options-kit), one worked sample per class.

The loop:

1. **`wrun_author`**: pick the closest `template`, then write the AssemblyScript `source` (and `metadata` if the inputs/outputs/params differ from the template). Write the file with `onBar()`: declarations at the top, no import lines (the build adds them), optional `function onStart(): void` (once before the first bar, params through `p_<param>()`), required `function onBar(): void` (once per bar: the chart's own candle through `bar.close()` and friends, declared feeds through `in_<input>()`, every value through `out_<output>(value)`, no `emitRow()`; an unwritten output is NaN and draws nothing). The four-function form (`export function init(): void`, `state(): i32` returning 1 when a row is ready, `finalize(): void` writing outputs then `emitRow()` LAST, `reset(): void`, with explicit import lines) is still accepted unchanged; ALL persistent state lives in module-level variables (`reset` clears them and calls `.reset()` on every TA object). WORKFLOW: call `wrun_author` once with just `name` + `template` and READ the returned `source`, then EDIT that shape rather than writing from memory. The tool lints submitted source at the write step and returns the deviations as `warnings`; fix every warning before building. This is local scratch work, no approval needed. Two failure modes to know by name:
   - Redesigned signatures (`init(args: Array<f64>)`, `state(state, inputs)`, a `finalize` that returns the value) DO compile under asc; nothing stops them until the build's static ABI check refuses the module (`WRUN export 'init' has signature (i32) -> void; the wrun-1 contract requires init() -> void`). `wrun_author` already warns at the write step (`'init' must take NO parameters (found 'args: Array<f64>')`), so a warning-free author is the cheap fix.
   - Raw positional slot literals (`getFloat(0)`, `getInt(0)`, `wrun_arg_f64(0)`, `wrun_arg_i32(0)`, `setOutput(0, ...)`, `wrun_output_f64(0, ...)`) are refused BEFORE the compiler runs, because slots silently rebind when metadata params/inputs/outputs change: `wrun_author` warns `wrun_build will fail: src/indicator.ts:<line> uses positional getFloat(0); use in_close() from ./gen/inputs in state() or p_period() from ./gen/params in init()`, and `wrun_build` throws `scaffold build blocked: raw positional slot literals silently rebind when metadata params/inputs/outputs change` with one such line per finding. Variable indexes stay legal and comments are ignored; `src/sdk/sdk.ts` (the raw `getFloat`/`setOutput` wrappers) exists for variable-index access only.
2. **`wrun_build`**: compile it. On a compile error it throws with the diagnostics: read them, rewrite via `wrun_author`, build again. Iterate until it builds. A successful build regenerates `src/gen`, runs the local AssemblyScript build (the CLI receipt prints `Compiler: assemblyscript (bun run build)`), checks the module statically against the wrun-1 export ABI, ALSO installs the draft locally, and returns the receipt (`installed.path`, `installed.removeCommand`, `metrics`, any `warnings`): the user commissioned this draft by name, so that commission IS the consent (do not ask again); state the receipt (installed path + `om wrun remove <package>` as the undo) instead of asking. `package_install` is NOT part of this loop: it is for REGISTRY packages, where someone else's code enters the user's daemon, and there the ask stays. Opaque builds (`om wrun build --wasm <module.wasm>` or `--compile-command`, CLI-only) skip the accessor lint, so their receipt carries `positionalAbi: true` (text: `ABI: positional (metadata order binds params and inputs)`): params and inputs bind by metadata POSITION, so never reorder the metadata entries of such a package; scaffold builds are name-attached and omit the flag.
3. **Preview**: straight after a green build, `metric_get` the new `wrun/...` metric on a symbol so the user sees a real value; `metric_series` (same selector, `bars` 1..500, default 30) when they want to see it MOVE, one `[barOpenSec, value]` pair per bar (CLI `om metric series` renders a sparkline; metrics.md §"Series"); and `chart_indicator_preview` draws the draft on their chart (no publish needed; `plot: "line"` outputs only, one output per preview).
4. **Publish**: `package_publish` the same `packageDir` once the user approves. The human always approves publishing. Before publishing, AUTHOR UNDER A PUBLISHABLE SCOPE: `@local` is reserved and the registry rejects it; re-author the same source/metadata under the user's own scope (their account scope, e.g. `@om-core` if they own it) so the publish can succeed. Publish is also what unlocks hosted charting (bindable packages excepted, §"Bindable odds inputs"): `chart_indicator_add` mounts registry packages only (`marketplace.md §"Indicator packages"`); the local preview never needs it.

Keep inputs to declared SDK sources; daemon-only `series` inputs read watch values or installed series snapshots (§"Snapshots, panels and pane placement"). The module has no network of its own. Every `inputSources` pin is fixed at authoring time and no pin is user-configurable after install (repointing a PINNED odds input is `om wrun source set` on the authoring workspace followed by a rebuild; a code-first workspace edits the `input(...)` declaration instead; the consumer-side write-up is `marketplace.md §"Indicator packages"`). Before publish, a wrong pin is fixed in the normal loop (re-author, rebuild, reinstall the preview); after publish it can only be fixed by publishing a bumped version.


<!-- AUTO: CODE-FIRST AUTHORING - do not edit by hand; source: docs/indicators-internal/code-first-grammar.md; regenerate with `bun packages/cli/scripts/gen-indicator-docs.ts` -->

## Source-declared indicators (code-first)
Declarations in the source, sheet derived at build: the grammar, the refusals, and the wrun-2 notes; read before editing a workspace whose sheet says `generated_from`.

How this mode enters the agent loop, beside (never instead of) the metadata-first loop above:

- Scaffold code-first with `template: "sma-codefirst"` on `wrun_author` (or `om wrun create @scope/name --template sma-codefirst`): a complete SMA in 13 non-blank source lines, sheet derived, same build and preview loop as any draft. For the wrun-3 surface (a celled volume-profile input, a string slot, a text renderer on the newest bar) scaffold `template: "vp-buy-share-codefirst"` instead and edit that shape. For a package that trades, scaffold `template: "strategy-ma-cross"` (a moving-average cross: `strategy({ ... })` declared beside the outputs, the order calls in `finalize()`) or `template: "strategy-risk-reversion"` (each entry sized so a trade stopped out loses `risk_pct` percent of the equity (`.qty(...)`, capped by the equity), an ATR-sized stop and target fixed when the order goes out, a `positionSize()` guard) and edit that shape (§"A package that trades"). For a complete chart Indicator, scaffold the cookbook template nearest the ask (`om wrun templates` lists them by picker group: On price, Order flow, HUDs, Beyond the time axis, Strategies) and edit that shape.
- On a code-first workspace, `wrun_author`'s `metadata` argument is REFUSED with `wrun_metadata_generated`, and `wrun_source_set` (`om wrun source set` on the CLI) is refused with `wrun_source_set_generated`: the sheet is derived state, so pass updated `source` with edited declarations instead, and the build re-derives sheet + accessors together.
- A string slot named `debug` prints in the chart editor's Console; off the chart (the daemon, `om metric`) it is an ordinary string slot with no special treatment.
- The grammar below is the chart's (the public docs share it). Off the chart the daemon also serves: input options `binding` / `bindingClasses` (a market bound per use) and `token` (the `token_supply` source); `missing: "nan"` / `"zero"` on the first input densifying the request grid; celled `tape.cells` (`[offset_ms, price, size, side]`, 4; `min_size` REQUIRED, `history` "0" = live prints only), a `symbol` + `exchange` pin pair on celled inputs, and `block_size` / `max_depth` as the book fetch facets. Metric composition inputs have no declaration spelling and stay metadata-first (refused by name). A workspace with no declarations stays metadata-first: byte-identical to a hand-written sheet and the supported mode for languages without an extractor (Rust, Zig, a pre-built module); a sheet claiming generated provenance over a declaration-free source blocks the build naming both ways out (restore the declarations, or delete `generated_from` and `source_digest` to hand-edit). The chart's editor refuses a declaration-free source.
- `abi_version: "wrun-2"` is additive (scalar wrun-2 packages compute bit-identically to wrun-1). Celled inputs (`cellType: "array"` + required `max_cells`, counted in source tuples) read the celled source classes and FETCH LIVE for `volume_profile` ([low, high, buy, sell] cells) and `book` ([price, size, side] cells; `block_size` required, `om block-sizes` lists the venue's); `trade_volume_by_size` (`[bucket, buy_usd, sell_usd, buy_count, sell_count]` per USD trade-size bucket, one fill each, 5) is served by the chart only and refused by name here (`wrun_trade_volume_by_size_unsupported`). Backtests and screens refuse whole celled packages by name (`wrun_celled_metric_unsupported`); alerts, `metric_get`/`metric_series`, and chart previews are the supported consumers.
- wrun-2 sheets may also declare `string_slots` (byte-capped per-bar text written in `onBar()` via generated `str_<slot>` senders; slots are never metrics), `renderers` (`text`, `label`, `table`, `shape`, `stats_row`), `drawings` (`line`, `box`, `polyline`, `label`; coordinates from named outputs, x in epoch seconds), and per-bar `boxes` / `segments` (`box(...)` / `segment(...)` over declared outputs with bar offsets and an optional `when` gate; sheet-only, ABI-neutral). Modules read celled blocks through generated `in_<input>_cells()` / `in_<input>_read(ptr)` accessors; raw `wrun_arg_len` / `wrun_arg_bytes` / `wrun_output_str` literals are a scaffold build error like any positional access.

Declare params, inputs, and outputs as typed top-level statements of the
indicator's file (`src/indicator.ts` in the package), with nothing to
import; Run derives the sheet, `wrun/metadata.json`, from them:

```typescript
param("period", 14, { min: 2, max: 200, description: "Lookback window" });
param.bool("show_raw", true, { label: "Raw line" });
input("close", ohlcv.close);
input("btc_close", ohlcv.close, { symbol: "BTCUSDT", exchange: "BINANCE_FUTURES" });
output("value", line, lower, { unit: "score", label: "Score", format: "0.00" });
```

The build extracts the declarations statically (the code never runs at
build time), derives the sheet, and generates the readers and writers
(`p_*`, `in_*`, `out_*`, `str_*`; no import line, they are simply there)
from the same in-memory object, so the two cannot disagree. The grammar
is static and literal-only:

- `param(name, default, options?)` with options `required`, `min`, `max`,
  `description`: a number field, read from `onStart()` on through `p_<name>()`.
- `param.<kind>(name, default, options?)`, a typed setting: the kinds are
  `int`, `number`,
  `bool`, `choice`,
  `color`, `time`,
  `price`, `range`,
  `multi`, `list`,
  `source`, `timeframe`,
  `symbol`, `session` and
  `text` (`param.text` for one line,
  `param.text_area` for several), each
  naming the control the settings dialog draws and its literal default
  (a number; `true` or `false`; a string, the words for `text`; an
  array of strings, then the
  default string or strings, for `choice` and `multi`; `[lo, hi]` for
  `range`; an array of numbers for `list`; an `ohlcv.<field>` reference
  for `source`). Options, every key optional: `required`, `min`, `max`,
  `description`, `label`, `step`, `group` (`"Page"` or
  `"Page/Section"`), `row`, `hint`, `when` (the NAME of a `param.bool`),
  `hide` (with `when`), `slider` (needs `min` and `max`), `unit` (an
  array from `"price"`, `"ticks"`, `"%"`, `"atr"`), `unit_default`,
  `confirm`, on `param.session` only `tz` (one of the 42 session
  zones, `UTC`, `America/New_York`, `Asia/Kolkata`, `Europe/Paris` and
  `Pacific/Auckland` among them; Sessions and
  units lists each with its offset and
  daylight rule), and on `param.text` / `param.text_area` only
  `max_bytes` (1 to 4096 UTF-8 bytes, 256 when absent; the default must
  fit and carry no newline, control or invisible character) and, on
  `param.text`, `multiline` (keep newlines). `min`, `max`, `step`,
  `slider` and `unit` are
  refused on a kind that is not a number field. Readers, all readable
  from `onStart()` on: `p_<name>()` on every kind, `pb_<name>(): bool` on a `bool`,
  `p_<name>_lo()` / `p_<name>_hi()` on a `range`, `p_<name>(): f64[]` on
  a `list`, `p_<name>_start()` / `p_<name>_end()` / `p_<name>_tz()` on a
  `session`, `p_<name>_unit()` beside a number with `unit`, and
  `pt_<name>(): string` on a `text` (the typed words, cleaned of
  invisible and control characters, where `p_<name>()` reads their UTF-8
  byte count): read the words once in `onStart()` and keep them in a
  module variable (Setting kinds). A `text`
  setting moves the sheet to `abi_version: "wrun-5"`.
  `market.tick_size()`, `market.price_precision()`,
  `chart.interval_sec()`, `chart.bg_color()` and `chart.fg_color()`
  declare hidden settings the host writes before `onStart()`, 0 where it
  cannot know one, read through `p_market_tick_size()`,
  `p_market_price_precision()`, `p_chart_interval_sec()`,
  `i32(p_chart_bg_color())` and `i32(p_chart_fg_color())`
  (Chart context). The market's facts ride the same way:
  `market.kind()` (`i32(p_market_kind())`: 1 crypto, 2 stock or ETF, 3
  forex, 4 metal, 5 index, 6 economic series, 0 unknown),
  `market.point_value()` (a futures multiplier, 1 per unit, 0 unknown),
  `market.zone()` (the exchange zone as its `SESSION_TZ_IDS` index, 0 UTC
  and unknown, passed straight to `inSession`) and
  `market.quote_is_usd()` (1 US dollars, 2 another currency or coin, 0
  unknown). A `param.source` default may be any of its menu's words, the
  blends `hl2`, `hlc3`, `ohlc4` and `hlcc4` included.
  A `range` counts as two sheet params, a `session` as three, a `list` as
  `max` + 1, a `unit` list as one more, and the sheet holds at most 128; a
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
  never depend on a setting. A data-only output refuses a paint binding
  (The Style page has the paint bindings,
  Picks, lanes, the cap the pins).
- `page(title)`, `section(title, { toggle?, collapsed?, when? })`,
  `divider()` and `note(text)` lay the settings dialog out in source
  order (settings before the first page land on "General"; `toggle` and
  `when` take a `param.bool` HANDLE bound with a top-level `const`;
  `note` text may hold `**bold**`); `presets({ Name: { param: value,
  ... } })` ships named settings sets (values as declared: numbers,
  `true` / `false`, a choice's label, a color string, a text setting's
  words within its `max_bytes`; a composite is set
  through its members, `band_lo`, `rth_start`); `legend({ title })` sets
  the legend's title template (`{{param}}` reads a setting). Sheet-only,
  compiled to nothing (Pages, sections, dividers, notes,
  Presets).
- `input(name, source.field, options?)` with options `exchange`, `symbol`,
  `interval` (`MINUTE`, `FIVE_MINUTES`, `FIFTEEN_MINUTES`,
  `THIRTY_MINUTES`, `HOUR`, `FOUR_HOURS`, `DAY`, `WEEK`, or the short
  spellings `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, and on the
  chart only its custom timeframes `2m`, `3m`, `10m`, `45m`, `2h`, `6h`,
  `8h`, `12h`, `3d` (`TWO_MINUTES` to `THREE_DAYS`); the derived sheet
  always carries the long word), `view` (with `interval` only:
  `"confirmed"`, the default, the latest leg candle closed as of the row's
  close and carried; `"forming"`, the row's own leg bucket folded from the
  leg market's rows at the primary interval up to and including it (an
  own-market `ohlcv` leg folds the primary rows, a pinned-market `ohlcv`
  leg that market's rows, an own-market `oi` / `funding` leg folds its
  rows per component, the declared field's suffix picking the one it
  reads), legs up to `WEEK`;
  `"is_new_period"`, 1 on a delivered row whose confirmed leg
  candle differs from the one the previously delivered row held, the
  first delivered row reading 1 when a candle is held, else 0;
  `"offset"`, which the `offset` option writes for you; one input
  slot per view, read through the ordinary `in_<name>()`), `views` (with
  `interval` only, never beside `view`: the EXTRA readings of the leg as
  one comma-separated string of `forming` and/or `is_new_period`, each
  deriving one more input named `<name>_<view>` right after this one, the
  same source, field and pins, read through `in_<name>_forming()` /
  `in_<name>_is_new_period()`; the declaration itself stays the confirmed
  reading, and the derived sheet carries the three entries explicitly),
  `offset` (with `interval` only, 1 to 500: the leg candle that many
  candles before the confirmed one; the build writes `view: "offset"`
  beside it), `bars` (with `interval` only, or on `candles.cells`, 1 to
  5000: the leg's fetch depth in its own candles, counted back from the
  newest; it only deepens),
  `outcome`, `tenor`, `delta` (`skew` only: 5, 15, 25 or 35, 25 when
  absent), `side`, `fund` (the ETF feeds, required there: an ETF ticker,
  or `"all"` on `etf_flow` and `etf_holdings`), `venue` (on `options_oi`
  and `options_volume`: `"deribit"`, the default, or `"binance"`),
  `publisher` and `series` (`economic`, both required), `asset`
  (`treasury_balance`: an upper-case ticker, the chart's coin when
  absent), `token` (`token_supply`, required: the token's display name),
  `missing` (`"carry"`, `"nan"`, or `"zero"`), `description`. Sources are
  bare member references to the feeds the chart serves: `ohlcv`,
  `trades`, `funding`, `oi`, `liquidations`, `long_short_ratio`,
  `implied_volatility`, `skew`, `volatility_index`, `options_oi`,
  `options_volume`, `etf_flow`, `etf_holdings`, `etf_premium`,
  `ethena_positions`, `bitfinex_funding`, `treasury_balance`,
  `token_supply`, `economic`, `odds`, `time`. There is no
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
  offsets: literals in -500..500, whole or fractional, or handles,
  default 0; a fraction places the edge inside its bar at that share of
  the bar interval, `from: -0.5, to: 0.5` one bar wide centred on it), `when`
  (a gate handle), `panel` (`"overlay"` or `"lower"`), `color`,
  `borderColor`, `opacity`, `borderWidth`. Segment options: `yFrom`,
  `yTo` (handles, required), `from`, `to`, `when`, `panel`, `color`,
  `width`, `lineStyle`. The derived sheet records output NAMES under the
  snake_case fields (`x_from`, `x_to`, `border_color`, `border_width`,
  `y_from`, `y_to`, `line_style`). ABI-neutral like `range`. A handle
  that binds no `output(...)` declaration, a string literal where a
  handle goes, an offset literal outside -500..500, or a `panel` outside
  the two names is a named build error.
- `alert(name, options)` declares an alert the script owns, over an output
  HANDLE: `when` (required, the handle of the output whose false-to-true
  edge fires it; any plot, a data-only `none` output included, so no 0/1
  line has to be drawn to get an alert), `message` (the fire text, with the
  delivery-time placeholders `{{symbol}}`, `{{close}}` and the rest, and
  `{{<output>}}` for a declared output's value on the fired bar) and
  `description` (the picker's sub-line), both up to 200 characters,
  `text` (a string slot, by its bound `const` or its name: the words the
  file writes into it on the fired bar are the message, over `message`,
  sent as one plain line of at most 200 characters) and `every_bar`
  (`true` fires on every bar `when` holds, once per bar at most; `false`,
  the default, fires on the false-to-true edge only). Write
  the output from `onBar()` like any other: `const cross =
  output("golden_cross", none); alert("golden_cross_up", { when: cross,
  message: "{{symbol}} golden cross at {{close}}" });` and
  `out_golden_cross(fast > slow && fastPrev <= slowPrev ? 1.0 : 0.0)`. The
  derived sheet records the output's NAME under `alerts[].when` and the
  slot's name under `alerts[].text` (Alerts). Sheet-only
  and ABI-neutral, and erased before the compiler like `range(...)`: the
  sheet is its only reader, so its options can never move a module's
  bytes. At most 64 per package; the name follows the output grammar and
  shares the chart-object namespace with outputs, boxes, segments,
  renderers and drawings. An unbound handle, a string literal where the
  handle goes, a missing `when` or a duplicate alert name is a named build
  error. On a published package the alerts engine checks every alert on
  the server on every price tick, at most once a second per indicator,
  reading `text` and applying `every_bar` there; the user's fire choice
  (once, once per bar, once per bar close, every time) says when a fire
  counts. A package whose runs keep failing there has its alerts paused
  (`paused_runtime`) and retried by itself, and keeps drawing on the chart.

The second runtime contract's vocabulary has declaration forms too, and
deriving a sheet that uses any of them stamps `abi_version: "wrun-2"`
automatically (scalar-only declarations keep the first contract):

- Celled inputs: `input(name, <class>.cells, options)` with the classes
  the chart serves and their tuple widths: `volume_profile` (`[low, high,
  buy, sell]`, 4), `book` (`[price, size, side]`, 3), `intrabar`
  (`[offset_ms, open, high, low, close, volume]`, 6: the finer bars
  inside each chart bar), `trade_volume_by_size` (`[bucket, buy_usd,
  sell_usd, buy_count, sell_count]`, 5: the bar's volume by USD order
  size, `bucket` 1 to 7), `options_chain`
  (`[strike, expiry_ms, side, oi, gamma, delta, mark_iv, underlying,
  multiplier, vega]`, 10: the chart market's option chain on the live row
  only) and `candles` (`[offset_ms, open, high, low, close, volume]`, 6:
  a timeframe's closed candles as a stream, the backlog on the first row
  and each candle on the row it closes with).
  The chart does not serve the live trade tape (`tape`), and a run that
  declares it is refused by name.
  `max_cells` is REQUIRED, except on `candles`, where the build declares
  the larger of `bars` and 2 when it is left out; `block_size` (required
  on `book`) and `max_depth` are recorded in the sheet, while the chart
  serves the book it has stored for the chart row as it is;
  `description`. A celled input reads the chart's own market (the chart
  refuses a market pin on it), except `intrabar` and `candles`, which
  take `symbol` and `exchange` together. Those two alone take `interval`,
  REQUIRED and written to the sheet as the enum word: on `intrabar` the
  finer bars' span, a whole divisor of the primary grid from the
  interval words or their short spellings (`max_cells` must hold every
  finer bar of a row, a 1h row holds 60 1m bars); on `candles` any
  interval word, with `bars` (1 to 5000) for the depth. `options_chain` alone takes
  `venue` (`"auto"` by default: the chart's own market when it is an
  options venue, else the coin's Deribit chain; or one venue's chain:
  `"deribit"`, `"cme"`, `"binance"`, `"okx"`, `"bybit"`, `"bullish"`,
  `"derive"`) and `expiries` (`"all"` by default or `"nearest:N"`), reads
  the chart's
  own underlying (no pin pair) and sizes `max_cells` for the chain (a BTC
  chain is about 1,500 contracts). Every other scalar-feed knob
  (`side`, `missing`, `view`, `views`, ...) is refused on celled inputs.
- String slots: `string(name, { max_bytes, description? })`. The
  declaration is named `string`, and the type `string` keeps working
  beside it (String functions). A top-level `const s =
  string(...)` binds a handle a block, a tile or a legend entry may name
  the slot by; the build drops the binding before the compiler (the
  declaration returns nothing), so the bound form compiles to the bytes of
  the bare statement. A slot named exactly
  `debug`, written per bar in `onBar()` through its generated
  `str_debug(text)` sender, is the indicator's debug log: the chart
  editor shows its non-empty lines, oldest bar first, in its Console,
  capped to the newest 400 lines.
- Renderers: `render.text(name, { y, text, color?, size?, style?,
  tooltip?, hover?, badges? })`, `render.label(name, { x, y, text, color?,
  size?, style?, tooltip?, hover?, badges? })`, `render.table(name,
  { rows, cols, cells, position?, ...look, styles? })` (the look keys and
  the per-cell `styles` entries are on Styled
  tables), `render.shape(name, { output, shape,
  where?, color?, color_by?, colors?, width? })` (`width` a positive
  number, the mark's size in pixels; absent, the chart's default), `render.stats_row(name, { output, title?, format?,
  polarity?, visible? })` (`visible` takes `true`, `false` or an
  `"@<param>"` reference to a `param.bool`; it rides the sheet only and
  leaves the compiled literal), `render.bgcolor(name, { where, color?, color_by?,
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
- Names may carry capitals (`param("fastLen", 12)`). Params, inputs,
  string slots and frames are stored lowercase (`fastlen`), with every
  option that names one (`"@lineColor"`, `when: "showBands"`, a preset's
  keys) and every `{{fastLen}}` placeholder in a legend title, tooltip or
  HUD title (only the name inside the braces); outputs keep their
  spelling. Each accessor also answers to the spelling the file uses
  (`p_fastLen()` reads `p_fastlen()`). Two params, inputs, string slots,
  frames, renderers, drawings, levels, panels or outputs that differ only
  by case are refused, naming both; boxes, segments and alerts keep their
  spelling, so `Zone` and `zone` are two boxes.
- Declarations are top-level statements of `src/indicator.ts` only; one
  anywhere else names the file and line.
- Indexes follow declaration order: the first `input(...)` is slot 0 (the
  primary input), and reordering declarations reorders slots while the
  generated accessors keep your source name-attached. A candle field read
  through `bar.<field>()` is served by a declared input that is exactly
  that feed (same source and field, no option but `description`), under
  that input's name and index; otherwise it is appended after the declared
  inputs under its own name, in the fixed order `open`, `high`, `low`,
  `close`, `volume`, `bar_t`. A file with no `input(...)` line gets `close`
  as slot 0 whether or not it reads `bar.close()`. `bar.isLast()` and
  `bar.count()` read no input: the first stamps `abi_version: "wrun-3"`
  (the last-bar signal), the second `"wrun-6"` (the row count, the bars
  the run holds, over `wrun_bar_count`), and a reference taken as a value
  (`const held = bar.count;`) stamps like the call.
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
  stays at or under 128 params.

The derived sheet records `generated_from: "declarations"` plus a
`source_digest` (sha256 of the source), serializes canonically (an
unchanged source rewrites nothing), and is DERIVED state from then on:
edit the declaration, never the sheet, and the next build derives the
sheet and the accessors again. In the chart's editor every indicator is
declared this way: a file with `onBar()` and no `output(...)` is refused
at Run ("a file with onBar() needs at least one output(...) statement:
declare what the Indicator draws, e.g. output("value", line, overlay),
and write it in onBar() with out_value(...)").

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
- Scalar `source` must be one of: `ohlcv`, `trades`, `funding`, `oi`, `liquidations`, `implied_volatility`, `skew`, `token_supply`, `odds`, `metric`, `time`, `series` (there is no "market"/"price" source; close prices are `ohlcv`+`close`), or a chart-only class: `etf_flow`, `etf_holdings`, `etf_premium`, `volatility_index`, `long_short_ratio`, `options_oi`, `options_volume`, `ethena_positions`, `economic`, `treasury_balance`, `bitfinex_funding`. The chart's browser lane serves those eleven; the daemon and the hosted alerts lane refuse each by name (`wrun_<class>_unsupported`) before any fetch, and §"Source-declared indicators (code-first)" spells their knobs. A `time` input carries a fact of the primary bar (field `bar_open_sec`, its open in epoch seconds, the default; `trade_date`, epoch seconds at 00:00 UTC of its exchange trade date; `session`, 1 regular, 2 pre-market, 3 after-hours, 0 closed; never the primary input); the daemon refuses `trade_date` and `session` by name (`wrun_time_facts_unsupported`) on CME-group and US-equity venues, which the chart serves. A `series` input has `ref` instead of `field`, is never primary, and needs the daemon (§"Snapshots, panels and pane placement").
- Celled classes (`cellType: "array"` + `max_cells` on the input, the sheet at `abi_version: "wrun-2"`), seven, with their tuple widths: `volume_profile` (`[low, high, buy, sell]`, 4), `book` (`[price, size, side]`, 3, `block_size` required), `tape` (`[offset_ms, price, size, side]`, 4, `min_size` required, daemon live only), `intrabar` (`[offset_ms, open, high, low, close, volume]`, 6), `trade_volume_by_size` (`[bucket, buy_usd, sell_usd, buy_count, sell_count]`, 5, `bucket` 1..7 by the USD size of an order), `options_chain` (ten values per listed contract, the live row only) and `candles` (`[offset_ms, open, high, low, close, volume]`, 6); the chart serves the last four; the daemon serves `intrabar` and `candles` and refuses `trade_volume_by_size` and `options_chain` by their own names. kScript `ltf()` -> `intrabar.cells`: `input("m1", intrabar.cells, { interval: "1m", max_cells: 60 })`, the `interval` REQUIRED and a whole divisor of the chart's from the eight interval words (finer than the chart's: a coarser leg is `ohlcv` with an `interval` and a `view`), the selector's own market or a `symbol` + `exchange` pin (kScript `ltf(interval, type, symbol, exchange)`), ohlcv only, `max_cells` at least the finer bars per chart bar (a 1h bar holds 60 1m bars, `wrun_intrabar_ratio_over_cap` names both numbers); the tuple carries `offset_ms` (kScript's `c[0]` = `in_time_sec() * 1000 + offset_ms`) and CLOSED finer bars only (an Indicator is FRESHER than the browser kScript lane, which froze `ltf` cells after the fetch); a covered bar with no finer bars reads 0 cells, a bar the finer history does not reach reads -1, blocks are never truncated. `candles.cells` is a leg's CLOSED candles as a stream: `interval` REQUIRED (any of the eight words: finer than, equal to or coarser than the chart's), `bars` the depth, the selector's market or a `symbol` + `exchange` pin; the first delivered row carries the backlog, each later one the candles that closed since; `max_cells` may be left out (the build declares max(bars, 2)); never index 0, so a lean file keeps a scalar `input` line above it. v1 limits: the daemon clamps leg history to what the key's data plan serves (about 365 days; 167 hours on Free) and puts a note naming the served start on the run, while the chart reaches 15,000 candles per interval; backtests and screens refuse every celled package, `intrabar` and `candles` included; an intraday `candles` leg pinned to a 24/7 market over a session-market chart can carry more than `max_cells` on the first row after a weekend (raise `max_cells`, or read in-bar candles through `intrabar`).
- A `shape_where`/`color_by` gate must be a DIFFERENT output (usually `"plot": ""` data-only); an output cannot gate or color itself.

## Input pins
Fixed-market pins (`symbol` + `exchange` together, primary follows the selector); `interval` pins are legal, on the as-of clock, with a `view`: confirmed, forming, is_new_period, offset; `bars` deepens a leg, and the `candles` class carries a leg's history.

**Cross-symbol pins.** A non-odds, non-time FEED source may pin `symbol` and `exchange` TOGETHER so a secondary input reads a fixed reference market while the rest of the package follows the selector: `"btc_close": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES" }` gives any alt selector a BTC context input (ratios, cross-venue context). The pair rule is SCHEMA-ENFORCED: a lone `symbol` or a lone `exchange` is refused with the issue on the missing half (`feed sources pin a fixed market with symbol AND exchange together (never one alone: symbols are venue-native, so a lone symbol or a lone exchange names a market that does not exist on that venue); pin both, or omit both to follow the selector`). The rest is authoring policy the schema cannot check:
- Pin `symbol` and `exchange` together, never one alone: symbols are venue-native strings (`BTCUSDT` on BINANCE_FUTURES is `BTC` on HYPERLIQUID).
- Keep the PRIMARY input (index 0) selector-following; pins belong on secondary context inputs. A package with every input pinned computes the same value for every selector symbol (screens and chart legends mislabel it).
- Cross-symbol price/notional arithmetic is only dimensionally sane under the shared default USD quote (normalization covers ohlcv/trades/oi). Never mix with `quote: COIN`; avoid native-cross raw symbols (no per-source quote override).
- Exceptions: `odds` keeps its own rule (conditionId as `symbol`, exchange implicitly Polymarket); `time` takes no knobs; do not pin `metric` composition sources.
- Packages with cross-symbol pins are UNVERIFIED on hosted charts: keep them off `chart_indicator_add` until the chart lane verifies pins (odds-pinned packages chart as they always have), and a signal on a pinned-package metric must use `eval: "bar"` — `marketplace.md §"Indicator packages"`.

**Interval pins and the as-of clock.** `interval` is an independent pin on any feed source (odds included), and it is legal. A symbol/exchange pin alone still reads on the SELECTOR's interval and quote; an `interval` pin moves that one source onto its own grid, `"btc_4h": { "source": "ohlcv", "field": "close", "symbol": "BTCUSDT", "exchange": "BINANCE_FUTURES", "interval": "FOUR_HOURS" }`, and a bare `{ "source": "ohlcv", "field": "close", "interval": "DAY" }` reads the selector's own market on the daily grid. Causality is the engine's job, not the author's: a source COARSER than the primary grid (an explicit coarse pin, or an unpinned secondary that inherits the selector's interval when the primary input is pinned finer) contributes to a primary row only as-of its candle CLOSE, `candle.ts + sourceSec <= min(now, row.ts + primarySec)`: the value becomes visible on the first primary row whose own close is at or after the source candle's close, and never before evaluation time, so a forming 4h candle never leaks its final value into the 1h rows under it, live or historical; sparse coarse observations (odds) carry the latest CLOSED observation forward; an observation older than two source intervals before the window head reads as not-ready. Equal or finer sources align by bar open, row for row, exactly as an unpinned source does. Any interval validates; compatibility with the primary grid is resolved at runtime, not by schema. What it costs: a coarse leg needs its own history (the fetch widens by two source intervals) and its value steps once per source candle, so a `DAY` pin on a `MINUTE` primary is a step function. Hosted chart runs apply this same clock to interval-pinned inputs (the build writes the sheet's interval as the enum word, `FOUR_HOURS`, whatever the declaration spelled, so every host reads one spelling); the in-browser run of a pinned package is being brought onto it, so until then preview a pinned package on your machine.

**Views of a pinned leg.** An `interval`-pinned input carries one of three readings, chosen with `view` (absent = `"confirmed"`), each its own input slot read through the ordinary `in_<name>()` and each computed by the HOST at alignment, never by the module. `"confirmed"` is the rule above: the latest leg candle closed as of the row's close, carried forward, `NaN` before the first one under `missing`, gating readiness as today. `"forming"` is the row's own leg bucket folded AS-OF from the leg market's rows at the PRIMARY interval up to and including this row (open = the bucket's first primary open, high = max, low = min, close = the last joined row's close, this row's when the market has a row at its ts, volume = sum; the declared field picks the component; every row of the leg market inside the bucket with ts <= the row's ts joins, whether or not the primary grid has a row at that ts, and never-partial is judged on the fold source's own coverage): an own-market `ohlcv` leg folds the primary rows themselves, a pinned-market `ohlcv` leg (`symbol` + `exchange` beside `interval`) folds that market's rows at the primary interval as a second fetch beside the leg candles (the daemon preview reads that market's live bar off the same fetch), an own-market `oi` leg folds its rows per component the same way (open = the first real observation's open, high = max, low = min, close = the last close) and an own-market `funding` leg folds its `rate_*` (or `predicted_*`) family the same way, the declared field's suffix picking the component (`rate_close` = the bucket's last observation, `rate_high` = its max; `NaN` when none yet; a gap-fill row with no real observation never enters a fold); legs up to `WEEK`; it never gates readiness, and on the closing row it equals the confirmed value. `"is_new_period"` is `1` on a delivered row whose confirmed leg candle differs from the one the previously delivered row held (the first delivered row reads `1` when a candle is held), else `0` (`0` on the live forming row until its close lands the next candle); it never gates readiness, so a ring or a per-period reset keys on it instead of on bucket math. The rule to write by: inside your own handler you read `forming`, every other input reads `confirmed`. Code-first, `input("close_4h", ohlcv.close, { interval: "4h" })`, `input("close_4h_live", ohlcv.close, { interval: "4h", view: "forming" })`, `input("new_4h", ohlcv.close, { interval: "4h", view: "is_new_period" })`, or all three readings from ONE declaration with the `views` sugar: `input("close_4h", ohlcv.close, { interval: "4h", views: "forming,is_new_period" })` derives `close_4h` (confirmed), `close_4h_forming` and `close_4h_is_new_period`, in that order right after the base slot, same source, field and pins, read through `in_close_4h()`, `in_close_4h_forming()` and `in_close_4h_is_new_period()`; the sheet stays explicit (three `inputSources` entries, `views` never lands on it), so every host reads it unchanged. `views` is a comma string like `bindingClasses`, listing only the extra readings (`confirmed` is the declaration itself); it is refused beside `view`, without an `interval` pin, on a duplicate or unknown name, and a derived name that collides with a declared input refuses by name. In a hand sheet, `"view": "forming"` beside `"interval"`. Typed-feed interval pins (own-market `funding` / `oi`, coarser than the primary) bucket by the clock on every host: `"confirmed"` = the feed's last observation inside the latest CLOSED bucket (bucket end <= min(now, ts + P); an `oi` bucket folded per component, a `funding` bucket the same fold over its `rate_*` or `predicted_*` family, `rate_close` reading the last observation and `rate_high` the max), carried forward under `missing: "carry"` (abstaining before the first held bucket), `NaN` for a closed empty bucket under `missing: "nan"` (`0` under `"zero"`), `NaN` before the first closed bucket; `"forming"` = the row's own bucket folded from the observations up to and including the row, `NaN` when none yet; `"is_new_period"` = `1` on the delivered row whose held closed bucket differs from the previous delivered row's, so it fires on a bucket close with or without an observation; the feed is fetched at the primary interval and bucketed by the host (a typed feed pinned to a fixed market, or declared bindable, keeps the candle clock). `WEEK` legs open Monday 00:00 UTC on every host (every leg up to `DAY` floors from the epoch), and the whole-multiple rule reads seven days on them. Refused by name: a `view` without `interval`, on the primary input (it IS the forming bar), on celled, `time`, `metric` and `series` sources, beside `binding`, and `"forming"` off `ohlcv` or an own-market `funding` / `oi` leg (a pinned-market typed feed reads confirmed), past `WEEK`, or over a primary that is not own-market `ohlcv` or is bindable (`binding: "optional"`: a use could rebind the rows the bucket is folded from, so the plan checks the primary again after bindings resolve; the rule holds for every forming leg, pinned-market and typed-feed ones included). Four rules every host shares: a viewed leg must be a whole multiple of the primary interval and coarser than it (`FOUR_HOURS` over `HOUR`, `WEEK` over `DAY`; never equal: the primary bar is already the forming view, and an equal-span confirmed reading would expose the still-forming candle), refused by name at the sheet when the primary pins its interval and at plan time otherwise; the new-period signal compares delivered rows only (its cursor advances on every primary row whatever another input's readiness does), so a row another input abstains never swallows a landed candle and input order never moves the `1`; the forming fold keeps validity per component, so a `NaN` high on one bar never discards that bar's close, low or volume; and a bucket is never shipped partial: the fold's read reaches back to the bucket's start (the primary fetch for an own-market leg, the second fetch for a pinned-market one), and a bucket the data still does not reach from its start reads `NaN` in every component.

**Leg depth, offsets and history (scaffold 33).** `bars` (1..5000) on an interval-pinned leg or a `candles` input is the leg's fetch depth in its own candles, counted back from the leg bucket holding now; it only deepens the automatic pre-roll (one leg span before the head, two on a coarser leg) and is refused on the primary and on any input that is not a leg. `offset: N` (1..500, with `interval` only) reads the leg candle N candles before the confirmed one; the build writes `view: "offset"` beside it, the input reads `NaN` (0 under `missing: "zero"`) until N + 1 candles are held, never gates readiness, and pre-rolls N more leg spans. The kScript map: `htf()` / `request()` confirmed -> the `confirmed` view; `mode: "developing"` -> `"forming"`; `offset: N` -> `offset: N`; `request(..., { bars: N })` -> `bars: N`; calendar tokens `"1W"` / `"1M"` / `"1Q"` / `"1Y"` -> a `1d` `candles` stream through `./sdk/candles` `Periods(period.WEEK | MONTH | QUARTER | YEAR)` (`confirmed(n)` the closed periods newest first, `developing()` the current one; a `1w` stream reproduces the engine's weekly-backed `"1Q"` / `"1Y"` bit for bit when the `Periods` is told so with `period.WEEK` as its third argument (`new Periods(period.YEAR, 2, period.WEEK)`), which clocks on the row's week start and files a straddling week under the period it opens in; the leg is declared, never inferred from the candles); `vwap(anchor="quarter" | "year")` -> `Periods(...).developing()` `pv` / `pvVolume` plus the forming day's own bars; `requestBars(sym, tf, { bars: N + 1 })` -> a `candles` stream with `bars: N` read through `CandleList(N)` (N closed candles; kScript's last row is the forming candle, the `forming` view); a developing request's running open on any bar (Woodie pivots read it on a period's first bar) -> a `candles` input with `view: "forming_open"`, on every row the open of the leg candle holding it as `[offset_ms, open, NaN, NaN, NaN, NaN]` (settled once that candle trades, so it never looks ahead, the forming candle's rows included; an empty block where no leg candle holds the row; no `bars`, `max_cells` 1) beside the stream's folded periods; `ltf()` -> `intrabar`. A yearly VWAP, whole: `input("close", ohlcv.close); input("d", candles.cells, { interval: "1d", bars: 400 }); output("yvwap", line, overlay); const year = new Periods(period.YEAR); function onBar(): void { year.load(in_d_view(), in_d_cells(), bar.time()); out_yvwap(year.developing().vwap()); }`, feeding EVERY row's block (an empty one moves the period clock); a period that began before the stream's first candle reads `NaN`, never partial.

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
- Templates: `strategy-ma-cross` (a moving-average cross: `strategy({ initialCapital, qtyType, qtyValue, commissionPercent, slippageBps })`, `Cross.update`, `strategy.long("L").send()` and `strategy.closeAll()` in `finalize()`, a `range(...)` ribbon and cross marks on price) and `strategy-risk-reversion` (an RSI reversion: `risk_pct` sizing each entry by the loss at its stop (`.qty(equity * risk_pct / 100 / stopDistance)`, capped by the equity), `strategy.exit("Protect").from("Dip").stop(stopPrice).limit(targetPrice).send()` re-armed while `strategy.positionSize() > 0`, both distances in ATR, each trade's rails as line handles); scaffold one on `wrun_author` and edit that shape.
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
64-declaration cap; the expanded render selection has a separate 8 MiB cap.

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
500 live per kind, 1500 total, 4096 draw calls per row, 100,000 points per polyline
and 524,288 across the live ones.

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
