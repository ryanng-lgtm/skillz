---
name: openmarket-metrics
description: Compute named scalar metric values ad-hoc via `om metric get`, scan a universe of symbols via `om metric screen`, and discover the registry via `om metric list`. Covers the registered indicators (RSI, EMA, SMA, MACD, Bollinger Bands, ATR, Stochastic) plus the alert-engine schema-parity metrics (price, delta_pct, delta_abs, volume, funding_rate, open_interest). Chart-only indicators (CCI, MFI, OBV, VWAP, ADL, ADX, PSAR, Ichimoku) are NOT computable here — they exist only as chart overlays via `om chart indicator add`. NOT for raw-price chat questions — "what's the price of X" / "what's BTC at" / 24h-change queries always route to the `markets` tool (sparkline + lastPrice), never to `metric_get`. Use this skill when the user asks for a named indicator value ("what's RSI on BTC?", "give me MACD for ETH 4h"), wants to find symbols matching a condition ("find oversold majors", "scan top 50 by volume for high RSI"), wants to verify an alert threshold against the live value, or needs to discover what metrics exist. Always shell to `om metric`; never recompute math locally.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# Metrics

Four tools: `metric_get` (one symbol, one or many metrics — §"Compute"), `metric_series` (one symbol, ONE metric, per-bar history: §"Series"), `metric_screen` (many symbols, one metric — §"Scan"), `metric_list` (what exists). Metric ids and their params: §"Technical indicators". Failures and skipped rows: §"Errors". Arming what you just read: §"Alerts". Shell surface: §"CLI equivalents".

### Guardrails

**Never answer a price question with `metric_get`.** For "what's BTC at" / "price of SOL" / 24h-change questions call the `markets` tool — `lastPrice` plus a sparkline-ready `prices` array in one call; `metric_get` accepts `price` only so an alert spec can be sanity-checked.

**Never loop `metric_get` across a list of symbols.** One `metric_screen` call replaces N gets; a loop burns the per-turn tool budget before answering. The one exception — a few gets after a screen has already narrowed the field — is in §"Scan".

Always read values through these tools; never recompute indicator math locally — you have no candle series in context, so local math would be invented.

Chart-only indicators (CCI, MFI, OBV, VWAP, ADL, ADX, PSAR, Ichimoku) are not computable here — they exist only as chart overlays via `chart_indicator_add`.

Never present one venue's numbers as another's: when the requested venue can't serve a metric, refuse with the venue named, or state the substitution explicitly.

Prediction markets leave this surface entirely: route to the `polymarket_*` tools.

Unsure a metric name exists in this build? Probe `metric_list` first; if it's absent, say so and stop — never guess a metric id.

### Routing

Quick routing — the common asks, the call, the defaults to assume, and the offer:

| Ask | Call | What to assume or avoid — disclose it, then offer |
| --- | --- | --- |
| "what's BTC at?" / price / 24h change | `markets` | never `metric_get`; offer an alert at a level |
| "what's RSI on BTC?" | `metric_get`, one query | rsi(14), HOUR; no venue named → omit `exchange`, the result's `listing_note` names the listing read — say it in words; offer the alert at 70/30 and the chart |
| "the 200-day SMA on BTC" | `metric_get`, one query | sma with `period` from the ask, DAY; offer the alert at the cross |
| "MACD and EMA on ETH, 4h" | `metric_get`, several `queries[]` in ONE call | macd 12/26/9 (three ids — §"Technical indicators"), ema(20), FOUR_HOURS |
| "Bollinger Bands on SOL" | `metric_get`, three `queries[]` | bb_upper/bb_middle/bb_lower (20, 2); offer the chart overlay |
| "find oversold perps" / vague scan | `metric_screen` | top 25 by VOLUME_24H, rsi(14) lt:30; disclose the scanned scope, don't ask first; offer the alert and a scheduled rerun |
| "compare RSI across BTC, ETH, SOL" | one `metric_screen`, `universe.kind: symbols` | never a per-symbol `metric_get` loop |
| "alert me when …" | `alert_create` | a screen is a one-shot snapshot, not a watch |

### Reply shape

The first line answers with the value, its defaults in words, and freshness — "BTC RSI(14) on the hourly is 61.2 (Binance, 2 minutes ago)" — then two to four offers tailored to what was read (the alert at the threshold just compared, the chart, the scheduled rerun). Venue and interval names in user text are words — "Binance Futures", "hourly" — never registry ids; raw ids and JSON never reach the user.

## Compute

One symbol's metric values with metric_get: parameter defaults, venue and canonical intervals, discovery via metric_list, worked examples.

`metric_get` takes `queries` (each `{ metric, params }`) and one shared `selector` (`{ symbol, exchange, interval, quote }`). Several metrics on one symbol belong in ONE call — queries sharing a data type share a single fetch.

What to send, per field:

| Field | Behavior |
| --- | --- |
| `queries[].metric` | From the user request (`rsi`). Registry ids only — the probe rule in the intro; the full id list is §"Technical indicators". |
| `queries[].params` | Optional wherever §"Technical indicators" shows numbers: omit them and the documented values apply (`rsi` 14, `macd` 12/26/9, `bb_*` 20/2), filled before validation and echoed back on the value so you can state what was read. A partial object keeps the keys you sent and fills the rest. Send params when the ask means something other than the textbook setting — "RSI 7", "the 50-day SMA" — verbatim, and don't ask just to confirm a default. Three ids document no value and are rejected with `invalid_query` without one: `volume_sma` (`period`), `rolling_high` / `rolling_low` (`bars`). |
| `selector.symbol` | Required. Venue-raw (`BTCUSDT`) when `exchange` is named; a bare coin (`BTC`) is enough only when `exchange` is omitted. With `exchange` omitted the tool resolves the coin's default listing itself — spot for price-class reads, the perpetuals book for funding/OI, a US equity on its primary listing — reads it, and echoes it in `selector` and `listing_note`. State that listing in one line, in words. The `symbols` tool enumerates a coin's listings when the wording doesn't fit. |
| `selector.exchange` | Optional. From the user when named — canonical IDs via the `exchanges` tool; "Binance Futures" maps to `BINANCE_FUTURES`, "Bybit" to `BYBIT` — and never substituted. Otherwise omit it: the tool chooses the default listing and discloses it; a coin listed only on venues without a default is refused as `venue_unresolved`, naming them — relay them and ask. Only `metric_get` (and `signal_create_metric`) resolve an omitted venue; `metric_series`, `metric_screen` and `alert_create` need it named. A `wrun/…` metric needs it named too — its source book is not known before the package resolves, so the omitted form is refused as `venue_unresolved`. A read never blocks on a venue question otherwise — ask only when the choice commits real money. |
| `selector.interval` | Defaults to `HOUR`. Map a mentioned timeframe to its canonical token — the interval enum is inline in the tool schema; the `enum` tool lists all. |
| `selector.quote` | Defaults to `USD`. Override only when the user explicitly asks for a quote currency. |

Discovery: `metric_list` returns every available metric with `{ name, type, params }`. Call it when the user asks what metrics exist, when a name might not exist in this build (a proprietary plugin may register new ones), or to confirm an unfamiliar metric's param shape. For the standard set (§"Technical indicators"), skip the list call and use the documented values. They're stable.

Worked calls:

User: **"Give me the 4h MACD for ETH"** → one `metric_get`, three queries:

```json
{
  "queries": [
    { "metric": "macd", "params": { "fast": 12, "slow": 26, "signal": 9 } },
    { "metric": "macd_signal", "params": { "fast": 12, "slow": 26, "signal": 9 } },
    { "metric": "macd_histogram", "params": { "fast": 12, "slow": 26, "signal": 9 } }
  ],
  "selector": { "symbol": "ETH", "interval": "FOUR_HOURS" }
}
```

(`quote` omitted — the USD default applies; omit `interval` and the HOUR default applies the same way, and the result carries an `interval_note`. No venue was named, so `exchange` is omitted and the result's `listing_note` says which listing was read — relay it in words; had the user said "on Binance Futures", the selector would carry `BINANCE_FUTURES` and the venue-raw symbol verbatim.)

User: **"Is BTC overbought right now? 1-hour."** → `metric_get` rsi(14) on `BTC`, `HOUR`, no `exchange` (the listing read comes back in words), then compare the value to 70 (overbought) / 30 (oversold) thresholds in your reply — never report a bare number for an overbought/oversold question.

User: **"What's CVD on BTC?"** (proprietary; may or may not be in this build) → `metric_list` filtered to `cvd` first. If empty, tell the user "cvd isn't registered in this build" and stop. If present, use the params the list reports.

Result shape: `{ asOf, selector, values: [{ metric, params, value, ok, data_age_seconds }] }`. Freshness rides each value as `data_age_seconds` — say that as relative time ("2 minutes ago"), never `asOf`, which is only the request moment: two metrics in one call age independently, and an undated market number reads as current when it may not be. It counts from the newest observation behind the value, which is the bar's CLOSE, so a still-forming bar reads `0` — its window runs to the answering instant — and that zero means "as of now", not "unknown". `ok` and per-metric failures are defined in §"Errors".

## Technical indicators

The full built-in registry: every metric id with its params and unit — the Stochastic, Bollinger and MACD ids, rolling highs and lows, and the funding fraction unit.

| id | params | unit | answers |
| --- | --- | --- | --- |
| `price` | — | price | alert-spec sanity checks ONLY — price chat routes to `markets` |
| `delta_pct` | bars (optional, default 1) | percent points | % change over the last N bars |
| `delta_abs` | bars (optional, default 1) | price | absolute change over the last N bars |
| `volume` | — | quote-dependent | last-bar volume |
| `funding_rate` | — | **fraction** (0.01% = `0.0001`) | perp funding |
| `open_interest` | — | quote-dependent | open interest |
| `open_interest_delta_pct` | bars (optional, default 1) | percent points | OI change over N bars |
| `rsi` | period (14) | score 0–100 | overbought / oversold |
| `sma` | period (20) | price | simple moving average |
| `ema` | period (20) | price | exponential moving average |
| `atr` | period (14) | price | volatility range |
| `volume_sma` | period | quote-dependent | volume vs its average (the prior `period` bars, current bar excluded), with `volume` |
| `rolling_high` | bars | price | breakout level (high of the prior N bars) |
| `rolling_low` | bars | price | breakdown level (low of the prior N bars) |
| `macd` / `macd_signal` / `macd_histogram` | fast, slow, signal (12/26/9) | price | the MACD family — send all three ids for "MACD"; slow must exceed fast |
| `bb_upper` / `bb_middle` / `bb_lower` / `bb_width` | period, stddev (20/2) | price | the Bollinger family — no metric is named `bollinger`; `bb_middle` takes both params and computes from `period` alone |
| `stoch_k` / `stoch_d` | period, smoothing (14/3) | score 0–100 | the Stochastic pair — no metric is named `stochastic` |

The parenthesized numbers are what a paramless call reads: omit `params`, or any single key of it, and they fill before validation, so a bare `rsi` is RSI(14) and its value comes back carrying `period: 14`. Send params when the ask means something else. Rows naming a bare param with no number (`volume_sma`, `rolling_high`, `rolling_low`) have no conventional value — take it from the ask ("20-bar rolling high"); when the ask is silent, choose a sensible window, say which, and send it. Those three are the rows a missing param fails: `invalid_query` before any fetch, with the metric and the offending key named. The delta rows' `bars` is optional (default 1), and the four params-less rows (`price`, `volume`, `funding_rate`, `open_interest`) need no params object at all.

Installed WRUN packages add their own `wrun/@scope/name/output` ids per machine — `metric_list` is the discovery surface for those; they never appear in this table.

## Series

One metric's per-bar history with metric_series: the trend/context sibling of metric_get, when to reach for it, and how to read the pairs.

`metric_series` takes ONE `metric` (+ `params`, `sourceBindings` for bindable WRUN odds inputs), the same `selector` as `metric_get`, and `bars` (how many most-recent bars, 1 to 500, default 30). It answers "how has it moved", where `metric_get` answers "what is it now": "RSI over the last day", "is funding trending up", "how close has RSI been to 70". Same registry, same validators, same data path, so every point equals what `metric_get` would have answered at that bar's live read.

Result shape: `{ asOf, selector, metric, params, series }` where `series` is `[barOpenSec, value]` pairs (epoch seconds), oldest first. Warm-up and not-ready bars are omitted, so the array can be shorter than `bars`; the newest pair reads the still-forming bar and moves until that bar closes. Timestamps let you speak in time ("since 14:00 UTC"); never paste raw epoch seconds to the user.

Boundaries, same as the rest of this surface: price history routes to `markets` (its `prices` array is the price sparkline), one metric per call (several metrics = several calls), and a many-symbols question is a §"Scan", not a per-symbol series loop. A series is still a snapshot of the past: for the standing version of the ask, offer the alert.

## Scan

Scan many symbols on one metric with metric_screen: universe forms, filter/sort/limit and scanned.matched, skipped rows, and how to scope and drill down on a vague scan.

Use this for any **many-symbols, one-metric** question: "find oversold majors", "which alts have RSI > 70", "top 25 by volume with funding above 0.01%". One `metric_screen` call replaces N `metric_get` calls and stays within the per-turn tool budget. Mind the units when the ask is percent-worded: `funding_rate` is a fraction, so "above 0.01%" filters at `gt:0.0001` — copying `0.01` literally is a hundredfold overshoot that matches nothing.

`metric_screen` takes one `metric` (+ `params`, `interval`), a `universe`, and optional `filter` / `sort` / `limit`.

### Universe

Exactly one form — the schema is a discriminated union on `universe.kind`:

| Form | Use when |
| --- | --- |
| `{ "kind": "top_n", "exchange": …, "n": 25, "by": "VOLUME_24H" }` | The user wants "top N by X" or didn't specify a universe and you're defaulting on their behalf (default: top 25 by `VOLUME_24H`). |
| `{ "kind": "symbols", "exchange": …, "symbols": ["BTCUSDT", …] }` | The user gave you a specific list, or you're drilling down on candidates from a prior screen. |

Ranking fields for `by` (server does the sort + paging):

- `VOLUME_24H`: most common; "find oversold majors" maps to top-N by volume.
- `PRICE_CHANGE_24H`: biggest movers up/down.
- `MARKET_SYMBOL_OI_CHANGE_24H`: biggest OI shifts (perps).
- `MARKET_SYMBOL_MARKETCAP`: by coin marketcap.
- `AVAILABLE_SINCE`: newest listings.

Optional narrowing on the top_n form: `direction` (`SORT_DIRECTION_ASC`|`SORT_DIRECTION_DESC`, default DESC), `categories` (`SPOT`|`PERPETUAL`), `types` (data types).

**Screens assume the metric follows the universe symbol.** A `wrun/...` metric whose package pins its inputs to fixed markets computes the same value for every universe row (a fully pinned package) or mixes the universe's venue-native symbols with a foreign pinned leg. Screen with WRUN metrics only when the package's primary input follows the selector (the wrun skill's pin rules say which shapes do). Load `skill_read("wrun")` for those pin rules.

### Filter, sort, limit

`filter` is `{ op, value }` or `{ op: "between", range: [lo, hi] }`:

| Form | Meaning |
| --- | --- |
| `lt` / `lte` + `value` | metric strictly / inclusively below the threshold |
| `gt` / `gte` + `value` | metric strictly / inclusively above the threshold |
| `between` + `range: [lo, hi]` | metric within the inclusive range — ascending order, low first |

`sort`: `value_asc` (lowest first), `value_desc` (highest first), or `distance` (closest to the filter threshold — the most marginal pass — first; requires `filter`). Default sort is `value_asc` for `lt`/`lte`/`between`, `value_desc` for `gt`/`gte` — the "most extreme passing value first" ordering.

`limit` clamps the rows returned (default 10). `scanned.matched` shows total passing values regardless of limit, so report "20 of 100 oversold, showing top 10".

### Reading and reporting a scan

Result shape (compact — every field name verbatim):

```
{ asOf, metric, selector: { exchange, interval, quote },
  universe: { resolved_count, description },   // e.g. "top 25 by VOLUME_24H DESC on BINANCE_FUTURES"
  scanned: { count, matched, took_ms, partial },
  rows: [ { ok, symbol, value, distanceToThreshold, rankValue, data_age_seconds } ],
  nearest: { symbol, value, distanceToThreshold },   // only when a filter matched nothing
  skipped: [ { symbol, reason } ] }
```

Always state the scanned scope in your reply, in words — translate `universe.description`, never paste it: *"Scanned top 25 by 24h volume on Binance Futures (4h RSI). Four are oversold: SOL (27.1), TRX (28.3), ..."* Freshness is per row here — `data_age_seconds`, said as relative time, `0` on a bar still forming — because a thin market's bar lags a liquid one's in the same scan.

When `scanned.matched` is 0, never reply a bare "none found": the same call carries `nearest`, the closest value that missed the filter among the symbols scanned, so report it — "none under 30 right now; closest SOL at 34" — and offer the alert at the threshold instead. A second scan buys nothing. `nearest` is absent only when every symbol landed in `skipped`, which is a scan failure to report as one.

Per-symbol misses land in `skipped` with a `reason` (e.g. `budget_exceeded`), and `partial: true` means the scan was cut short — §"Errors" defines every reason and what to tell the user.

### Scoping when the user is vague

For "find oversold majors", "scan for X", "you find out", "just pick", or "you decide":

1. **Default and disclose — don't ask, don't re-ask. Default to** top 25 by `VOLUME_24H` on the most relevant exchange. Disclose what you scanned in the reply, and offer to change the ranking (price change / OI change / marketcap) or switch to a specific symbol list.
2. **Honor whatever size the user gives.** `n: 500` is fine; API budget is the user's concern.

### Drilldown pattern (compound conditions)

For "oversold AND high volume" or similar AND-of-conditions, compose two calls instead of asking for a multi-condition tool: step 1, `metric_screen` on the primary metric narrowed with `filter` + `limit` (say, top 50 by volume, rsi lt:30, limit 5); step 2, drill down on those few candidates with a second metric via `metric_get` — one get per candidate is fine here, N is small after the narrowing, which is the one sanctioned exception to the never-loop rule.

For cross-exchange comparisons ("RSI on BTC across Binance and Bybit"), screen once per exchange with the same `universe.symbols` list and compare the two results.

### Don't use a screen for

- **Subjective questions** ("good entries", "safe bets"): ask the user to pick a metric and threshold first.
- **Historical / point-in-time** ("yesterday's oversold"): a screen reads the latest bar only and nothing here reads the past — say so rather than answering from the current value. An alert watches forward, so offer it for the standing version of the ask, not as the answer.
- **Pair / ratio / spread metrics** ("ETH/BTC ratio", "funding spread"): not a single-metric screen.

## Errors

Every failure shape on this surface: typed codes (invalid_query, tier_forbidden) and their recovery, per-metric ok:false, skipped reasons, partial scans.

`metric_get` and `metric_screen` return these typed error codes via the standard JSON envelope (stderr on the CLI) on failure; `metric_list` reads the in-binary registry and returns none of them. On a screen they bail the whole request rather than landing in `skipped`: they would fail for every symbol, so trying the rest is pointless.

| code | Meaning | Recovery — and what to say |
| --- | --- | --- |
| `invalid_query` | Unknown metric name, an out-of-range param value, a missing param on the three rows that document none (`volume_sma`, `rolling_high`, `rolling_low`), a period whose window exceeds the lookback cap, or an unknown interval. | Fix what the message names, or call `metric_list` to confirm the metric exists and what it takes. An indicator you simply left params off reads its documented default, so a rejection on a params key is about the VALUE, never the omission. Tell the user what was corrected when it changes their ask. |
| `unsupported_exchange_for_metrics` | Exchange has no OHLCV-style data (e.g. POLYMARKET). | Route to the right action surface; for prediction markets use the `polymarket_*` tools. Name the boundary in words ("Polymarket has odds, not candles"). |
| `unsupported_universe_for_exchange` | A `top_n` universe on a venue with no ranked listings — POLYGON (equity listings serve, ranking stats don't), POLYGON_FX, POLYGON_INDICES, FX_OTC, CME (entitlement-gated). | Re-screen with `universe.kind: "symbols"` and an explicit list; `symbol_resolve` finds the venue spellings. Say the venue can't be *ranked*, never that it has no data. |
| `missing_api_key` | No credential at all. | Tell the user to run `om init` (a guest key normally mints itself; this usually means the auth service was unreachable). |
| `api_key_invalid` | The key is dead (401). | Call `auth_relogin`: it returns an approval URL + code to relay; the user approves in a signed-in browser and the machine heals itself. Say what's happening in words while the flow runs. Do NOT suggest minting/pasting keys first. |
| `tier_forbidden` | Plan does not cover the request (403); the key is fine. | Name the plan wall in words and give the upgrade path in one line — the user can run `om upgrade --show` or check their plan on openmarket.xyz. Never suggest replacing the key or re-logging in. When the wall is the history lookback behind a long interval (a 4h indicator needs days of candles), rerun the same request once at the nearest interval the plan serves and lead the answer with the substitution: "ran it on the 1h — the 4h window needs more history than this plan reaches". The user asked for the scan, not the interval. |
| `access_denied` | The server denied the request with a 403 that named no plan limit (the gateway's bare `forbidden`): a policy denial or a brief policy-engine outage, indistinguishable on the wire; the key is fine. | Retry once after a few seconds. If it persists, say the data may be outside the plan and give `om upgrade --show`; never suggest replacing the key. |
| Upstream code (e.g. `rate_limited`, `not_found`) | Forwarded from the OpenMarket Data API; on a screen, `rate_limited` at top level is the universe resolution call itself. | Wait and retry, or refine the selector. |

Per-metric compute failures (insufficient bars, malformed bar data) surface as `ok: false, value: null` in the response; they don't fail the whole request. The accompanying stderr line names the metric — read it for the reason before replying.

Per-symbol skip reasons on a screen (non-fatal — the row moves to `skipped`, the scan continues):

| reason | meaning |
| --- | --- |
| `insufficient_data` | Indicator warm-up not satisfied (e.g. RSI(14) on a coin listed 5 bars ago). |
| `rate_limited` | Upstream 429 on this symbol. Try again later or narrow the universe. |
| `timeout` | The per-call 2s deadline tripped. |
| `budget_exceeded` | The overall 10s wall-clock budget tripped before this symbol fetched. |
| `fetch_failed` | Generic upstream error (5xx, network). |

`partial: true` on a scan means the 10s wall-clock budget tripped before every resolved symbol completed; the remaining ones moved to `skipped` with `reason: budget_exceeded`. Summarize skips and partial scans in words — "scanned 18 of 25 before the time budget; want me to rerun the remainder?" — raw reason codes never reach the user.

## Alerts

alert_create shares this registry and validators — read the live value before arming, take the spec from skill_read("alerts"), and offer the chart and scheduled-rerun follow-ups.

`metric_get` uses **the same metric registry, the same parameter validators, and the same data-fetch path** the alert engine uses. If you can compute it here, you can alert on it via `alert_create` with the same metric name and the same params shape — `skill_read("alerts")` carries the spec. If a metric doesn't show up in `metric_list`, it can't be used in an alert either.

A common pattern: read the metric's current value with `metric_get`, then write the alert with thresholds informed by that value — offer it at the threshold the reply just compared against (70/30 for RSI).

The other two follow-ups a metric answer earns: the chart (a computed indicator can be shown, not just told — the chart indicator tools overlay RSI/EMA/Bollinger on the symbol's chart) and the standing rerun ("same scan daily at 08:00" routes to the schedule tools, never a re-ask).

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `metric_get`
  - `selector.exchange` — Omit the field and the coin's default listing is used and disclosed on the result; a named venue is never rewritten.
- `metric_get` · `metric_series`
  - `selector.interval` — Candle interval token (default HOUR).
- `metric_series`
  - `bars` — default 30 — How many most-recent bars to return (1-500, default 30).

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `metric_get`
  - discloses `listing_note` — Present only when the read chose the venue: no `selector.exchange` was named, so the coin's default listing was resolved and is named here in words with its venue symbol. Absent when the caller named the venue.
  - discloses `interval_note` — Present only when no `selector.interval` was named: hourly bars were read.
  - on `venue_unresolved` — No default listing could be chosen: relay the venues the message names and ask which one (when it names none, ask the user which venue; when it says the catalog could not be read, the fix is a retry or `om login`, not a venue) — never pick a venue yourself, never swap the coin for another.

<!-- AUTO: END RESULT CONTRACT -->

## CLI equivalents

The om command forms of these tools — flag syntax, the two --metric forms, and the command-to-action mapping.

```
om metric list   [--metric NAME ...] [--format json|text]
om metric get    --metric NAME[:k=v,k=v] ... [--params k=v,k=v]
                 --symbol SYM --exchange ID
                 [--interval INT] [--quote QUOTE]
                 [--format json|yaml|text]
om metric series --metric NAME[:k=v,k=v] [--params k=v,k=v]
                 --symbol SYM --exchange ID [--bars N]
                 [--interval INT] [--quote QUOTE]
                 [--format json|text]
om metric screen --metric NAME[:k=v,k=v] [--params k=v,k=v]
                 --exchange ID
                 ( --top-n N --by FIELD | --symbol SYM ... )
                 [--filter EXPR] [--sort KIND] [--limit N]
                 [--interval INT] [--quote QUOTE]
                 [--format json|text]
```

`om metric get` takes two equivalent, mutually exclusive forms: a single bare `--metric` with `--params` (the shape `om alert create` mirrors), or the repeatable compact `--metric name:k=v,k=v` colon form for several metrics. `--params` is only legal with a single bare `--metric` (no colon); for multi-metric, use the colon form. `om metric series` takes the same two forms but exactly one metric, and its text mode renders the series as a sparkline.

CLI filters are the compact spellings of the same fields: `--filter lt:30`, `--filter between:30..70`, `--top-n 25 --by VOLUME_24H`. JSON output (`--format json`) is byte-identical to the tool results shown above. The command-to-action mapping:

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

- `om metric get` (action: `metric_get`) — Compute one or more named scalar values over the latest candle window for a (symbol, exchange?, interval) tuple — omit `exchange` and the coin's default listing is read and echoed back (a `wrun/…` metric needs the venue named).
- `om metric list` (action: `metric_list`) — List every available scalar metric — name, source data type, and accepted parameter names.
- `om metric screen` (action: `metric_screen`) — screen a universe of symbols on a single scalar metric (price, delta_pct, volume, funding_rate, open_interest, RSI, MACD, EMA, ATR, etc.).
- `om metric series` (action: `metric_series`) — Per-bar HISTORY of one scalar metric over the last N bars for a (symbol, exchange, interval) tuple, as [barOpenSec, value] pairs, oldest first, newest = the still-forming bar.

<!-- AUTO: END COMMAND REFERENCE -->
