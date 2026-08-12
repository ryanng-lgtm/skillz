---
name: openmarket-metrics
description: Compute named scalar metric values ad-hoc via `om metric get`, scan a universe of symbols via `om metric screen`, and discover the registry via `om metric list`. Covers the registered indicators (RSI, EMA, SMA, MACD, Bollinger Bands, ATR, Stochastic) plus the alert-engine schema-parity metrics (price, delta_pct, delta_abs, volume, funding_rate, open_interest). Chart-only indicators (CCI, MFI, OBV, VWAP, ADL, ADX, PSAR, Ichimoku) are NOT computable here — they exist only as chart overlays via `om chart indicator add`. NOT for raw-price chat questions: "what's the price of X" / "what's BTC at" / 24h-change queries always route to the `markets` tool (sparkline + lastPrice), never to `metric_get`. Use this skill when the user asks for a named indicator value ("what's RSI on BTC?", "give me MACD for ETH 4h"), wants to find symbols matching a condition ("find oversold majors", "scan top 50 by volume for high RSI"), wants to verify an alert threshold against the live value, or needs to discover what metrics exist. Always shell to `om metric`; never recompute math locally.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om metric

Three subcommands, all backed by the same metric registry the alert engine uses (so values you read here are exactly what an alert would fire on). The registry covers both **price-class metrics** (price, delta_pct, delta_abs, volume, funding_rate, open_interest) and **indicators** (RSI, EMA, MACD, Bollinger Bands, ATR, Stochastic, etc.) under one surface.

```
om metric list   [--metric NAME ...] [--format json|text]
om metric get    --metric NAME[:k=v,k=v] ...
                 --symbol SYM --exchange ID
                 [--interval INT] [--quote QUOTE]
                 [--format json|text]
om metric screen --metric NAME[:k=v,k=v]
                 --exchange ID
                 ( --top-n N --by FIELD | --symbol SYM ... )
                 [--filter EXPR] [--sort KIND] [--limit N]
                 [--interval INT] [--quote QUOTE]
                 [--format json|text]
```

## When to use which

| Question shape | Tool |
| --- | --- |
| "What's BTC at?" / "price of SOL" / "ETH 24h change" | **`markets`, not this skill.** Returns lastPrice + sparkline-ready `prices` array. |
| "What's RSI on BTC?" (one symbol) | `get` |
| "Give me MACD and EMA on ETH 4h" (one symbol, many metrics) | `get` (multi-metric form) |
| "Find oversold majors" / "which alts are above the upper BB?" (many symbols, one metric) | `screen` |
| "Compare RSI across BTC, ETH, SOL" | `screen` with `--symbol` for each |
| "Top 25 by volume with RSI below 30" | `screen` with `--top-n` |

**Never loop `get` across a list of symbols.** That was the pattern this skill exists to replace: each iteration consumes a tool-call slot and the LLM hits its per-turn budget before answering. One `screen` call replaces N `get` calls.

**Never call `metric get --metric price` for a chat reply.** The action accepts `price` as a metric only so an alert spec using `metric: "price"` can be sanity-checked here. For "what's BTC at" / "price of SOL" / 24h-change questions, route to the `markets` tool: it returns a `prices` array (renders as a sparkline) and a populated `lastPrice` in one call. `metric get` returns a bare scalar and no chart context.

## Discovery: `om metric list`

Returns every available metric with `{ name, type, params }`. Use this when:

- The user asks "what metrics can I get?" / "what indicators can I get?"
- You're unsure whether a metric name exists in this build (a proprietary plugin may register new ones).
- You need to confirm the param shape for an unfamiliar metric.

For the standard set (everything in the table below), skip the `list` call and use the defaults. They're stable.

```bash
om metric list                       # all
om metric list --metric rsi --metric macd
om metric list --format text         # column table
```

## Compute: `om metric get`

Two equivalent forms, mutually exclusive:

```bash
# Single metric, mirrors `om alert create`.
om metric get --metric rsi --params period=14 \
  --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR

# Multi-metric, compact 'name:k=v,k=v' form, repeatable. Metrics that share
# a data type share a single fetch.
om metric get \
  --metric rsi:period=14 \
  --metric ema:period=20 \
  --metric macd:fast=12,slow=26,signal=9 \
  --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR
```

`--params` is only legal with a single bare `--metric` (no colon). For multi-metric, use the colon form.

Default JSON output:

```json
{
  "asOf": "2026-05-21T14:00:00.000Z",
  "selector": {
    "symbol": "BTCUSDT",
    "exchange": "BINANCE_FUTURES",
    "interval": "HOUR",
    "quote": "USD"
  },
  "values": [
    { "metric": "rsi", "params": { "period": 14 }, "value": 67.34, "ok": true }
  ]
}
```

`ok: false` means the metric couldn't compute (insufficient bars, fetch failure). `value` is `null` in that case. The accompanying stderr line names the metric, read it for the reason.

## Scan: `om metric screen`

Use this for any **many-symbols, one-metric** question: "find oversold majors", "which alts have RSI > 70", "top 25 by volume with funding above 0.01%". One `screen` call replaces N `get` calls and stays within the agent's per-turn tool-call budget.

```bash
# Top 25 perps by 24h volume on Binance Futures with 4h RSI < 30.
om metric screen \
  --metric rsi:period=14 \
  --exchange BINANCE_FUTURES \
  --interval FOUR_HOURS \
  --top-n 25 --by VOLUME_24H \
  --filter lt:30

# Explicit symbol list. No /v1/markets call; skips straight to fan-out.
om metric screen \
  --metric rsi:period=14 \
  --exchange BINANCE_FUTURES \
  --symbol BTCUSDT --symbol ETHUSDT --symbol SOLUSDT
```

### Universe

Pick **exactly one** form:

| Form | Use when |
| --- | --- |
| `--top-n N --by FIELD` | The user wants "top N by X" or didn't specify a universe and you're defaulting on their behalf (default: `--top-n 25 --by VOLUME_24H`). |
| `--symbol SYM ...` (repeatable) | The user gave you a specific list, or you're drilling down on candidates from a prior screen. |

Ranking fields for `--by` (server does the sort + paging):

- `VOLUME_24H`: most common; "find oversold majors" maps to top-N by volume.
- `PRICE_CHANGE_24H`: biggest movers up/down.
- `MARKET_SYMBOL_OI_CHANGE_24H`: biggest OI shifts (perps).
- `MARKET_SYMBOL_MARKETCAP`: by coin marketcap.
- `AVAILABLE_SINCE`: newest listings.

Optional `--direction SORT_DIRECTION_ASC|SORT_DIRECTION_DESC` (default DESC), `--category SPOT|PERPETUAL` (repeatable), `--type DATA_TYPE` (repeatable).

### Filter, sort, limit

`--filter` forms:

| Form | Meaning |
| --- | --- |
| `lt:30` / `lte:30` | value strictly / inclusively below threshold |
| `gt:70` / `gte:70` | value strictly / inclusively above threshold |
| `between:30..70` | value within inclusive range |

`--sort`:

- `value_asc`: lowest value first.
- `value_desc`: highest value first.
- `distance`: closest to the filter threshold (most marginal pass) first. Requires `--filter`.

Default sort is `value_asc` for `lt`/`lte`/`between`, `value_desc` for `gt`/`gte`. The obvious "most extreme passing value first" ordering.

`--limit N` clamps the rows returned (default 10). `scanned.matched` shows total passing values regardless of limit, so the agent can report "20 of 100 oversold, showing top 10".

### Output shape

```json
{
  "asOf": "...",
  "metric": "rsi",
  "selector": { "exchange": "BINANCE_FUTURES", "interval": "FOUR_HOURS", "quote": "USD" },
  "universe": {
    "resolved_count": 25,
    "description": "top 25 by VOLUME_24H DESC on BINANCE_FUTURES"
  },
  "scanned": {
    "count": 25,
    "matched": 4,
    "took_ms": 3120,
    "partial": false
  },
  "rows": [
    { "ok": true, "symbol": "SOLUSDT", "value": 27.1, "distanceToThreshold": 2.9, "rankValue": 1500000000 }
  ],
  "skipped": [
    { "symbol": "NEWUSDT", "reason": "insufficient_data" }
  ]
}
```

Always echo the `universe.description` in your reply so the user knows the scope you scanned. Example: *"Scanned top 25 by 24h volume on Binance Futures (4h RSI). Four are oversold: SOL (27.1), TRX (28.3), ..."*

`partial: true` means the 10s wall-clock budget tripped before every resolved symbol completed; the remaining ones moved to `skipped` with `reason: budget_exceeded`. Tell the user.

### `skipped` reasons (per-symbol, non-fatal)

| reason | meaning |
| --- | --- |
| `insufficient_data` | Indicator warm-up not satisfied (e.g. RSI(14) on a coin listed 5 bars ago). |
| `rate_limited` | Upstream 429 on this symbol. Try again later or narrow the universe. |
| `timeout` | The per-call 2s deadline tripped. |
| `budget_exceeded` | The overall 10s wall-clock budget tripped before this symbol fetched. |
| `fetch_failed` | Generic upstream error (5xx, network). |

### Errors that bail the whole screen

These come back as a typed `ActionError` on stderr (exit non-zero), not as `skipped` rows. They'd fail for every symbol so trying is pointless:

| code | Meaning | Recovery |
| --- | --- | --- |
| `invalid_query` | Unknown metric name, missing param, etc. | `om metric list`; fix the name/params. |
| `unsupported_exchange_for_metrics` | Exchange has no OHLCV-style data (e.g. POLYMARKET). | Route to the right action surface; for prediction markets use the `polymarket_*` actions. |
| `missing_api_key` | No credential at all. | Tell the user to run `om init` (a guest key normally mints itself; this usually means the auth service was unreachable). |
| `api_key_invalid` | The key is dead (401). | Call `auth_relogin`: it returns an approval URL + code to relay; the user approves in a signed-in browser and the machine heals itself. Do NOT suggest minting/pasting keys first. |
| `tier_forbidden` | Plan does not cover the request (403); the key is fine. | Never suggest replacing the key or re-logging in. Point at `om upgrade --show` / their plan on openmarket.xyz. |
| `rate_limited` (top-level) | Upstream rate limit on the universe resolution call itself. | Wait and retry. |

### Scoping when the user is vague

For "find oversold majors", "scan for X", or "you decide":

1. **Ask once** with concrete options if the universe is genuinely ambiguous:
   *"Want me to scan top 25 by 24h volume on Binance Futures, a different ranking (price change / OI change / marketcap), or a specific symbol list?"*
2. **If the user has already delegated** ("you find out", "just pick", "scan some"), don't re-ask. Default to `--top-n 25 --by VOLUME_24H` on the most relevant exchange. Disclose what you scanned in the reply.
3. **Honor whatever size the user gives.** `--top-n 500` is fine; API budget is the user's concern.

### Drilldown pattern (compound conditions)

For "oversold AND high volume" or similar AND-of-conditions, compose two calls instead of asking for a multi-condition tool:

```bash
# Step 1: screen on the primary metric, narrow to candidates.
om metric screen \
  --metric rsi:period=14 --exchange BINANCE_FUTURES --interval FOUR_HOURS \
  --top-n 50 --by VOLUME_24H --filter lt:30 --limit 5
# result might be SOLUSDT, TRXUSDT, XRPUSDT, ...

# Step 2: drill down on those candidates with a second metric.
om metric get \
  --metric volume \
  --symbol SOLUSDT --exchange BINANCE_FUTURES --interval FOUR_HOURS
# (one `get` per candidate; N is small now, well within budget)
```

For cross-exchange comparisons ("RSI on BTC across Binance and Bybit"), call `screen` once per exchange with `--symbol BTCUSDT` and compare the two results.

### Don't use `screen` for

- **Subjective questions** ("good entries", "safe bets"): ask the user to pick a metric and threshold first.
- **Historical / point-in-time** ("yesterday's oversold"): `screen` is current-snapshot only. Offer `om alert create` instead.
- **Pair / ratio / spread metrics** ("ETH/BTC ratio", "funding spread"): not a single-metric screen.
- **Polymarket / prediction markets**: use `polymarket_market_summary` etc.
- **"Watch / alert me / notify when"**: that's `om alert create`, not a screen.

## Parameter defaults

Each metric's canonical defaults live in its tool-schema description (the same place the LLM reads when picking the metric). When the user names params explicitly ("RSI 7", "the 50-day SMA"), use those values verbatim; otherwise apply the documented default silently. Don't ask just to confirm a textbook default.

## What to ask, what to default, what to require

For a request like "get the RSI for BTCUSDT on Binance Futures":

| Field | Behavior |
| --- | --- |
| `--metric` | From the user request (`rsi`). |
| `--params` | Use the default from the table (`period=14`). Don't ask. |
| `--symbol` | Required. Must come from the user. If they said "BTC" alone, ask whether they mean `BTCUSDT`, `BTCUSDC`, etc., or run `om symbols --coin BTC --exchange BINANCE_FUTURES` to enumerate. |
| `--exchange` | Required. From the user. Canonical IDs via `om exchanges`. Common synonyms: "Binance Futures" maps to `BINANCE_FUTURES`, "Bybit" to `BYBIT`. If ambiguous, ask. |
| `--interval` | Defaults to `HOUR`. If the user mentions a timeframe ("4h", "5m", "daily"), map to a canonical interval and pass `--interval`. |
| `--quote` | Defaults to `USD`. Override only if the user explicitly asks for a quote currency. |

Canonical intervals (`om enum --interval` for the full list):
`MINUTE`, `FIVE_MINUTES`, `FIFTEEN_MINUTES`, `THIRTY_MINUTES`, `HOUR`, `FOUR_HOURS`, `DAY`, `WEEK`.

Mapping common phrases: "1m" maps to `MINUTE`, "5m" to `FIVE_MINUTES`, "15m" to `FIFTEEN_MINUTES`, "30m" to `THIRTY_MINUTES`, "1h" / "hourly" to `HOUR`, "4h" to `FOUR_HOURS`, "daily" / "1d" to `DAY`, "weekly" to `WEEK`.

## Worked examples

User: **"What's the RSI on BTC Binance Futures?"**

```bash
om metric get \
  --metric rsi --params period=14 \
  --symbol BTCUSDT --exchange BINANCE_FUTURES
# (--interval defaults to HOUR)
```

User: **"Give me the 4h MACD for ETH"**

```bash
om metric get \
  --metric macd:fast=12,slow=26,signal=9 \
  --metric macd_signal:fast=12,slow=26,signal=9 \
  --metric macd_histogram:fast=12,slow=26,signal=9 \
  --symbol ETHUSDT --exchange BINANCE_FUTURES --interval FOUR_HOURS
```

User: **"Is BTC overbought right now? 1-hour."**

```bash
om metric get \
  --metric rsi:period=14 \
  --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR
# Compare value to 70 (overbought) / 30 (oversold) thresholds in your reply.
```

User: **"Show me Bollinger Bands on SOL"**

```bash
om metric get \
  --metric bb_upper:period=20,stddev=2 \
  --metric bb_middle:period=20,stddev=2 \
  --metric bb_lower:period=20,stddev=2 \
  --symbol SOLUSDT --exchange BINANCE_FUTURES
```

User: **"What's CVD on BTC?"** (proprietary indicator; may or may not be in this build)

```bash
om metric list --metric cvd
# If empty, tell the user "cvd isn't registered in this build" and stop.
# If present, use the params reported by list.
```

## Errors you should recognize

The action returns these typed error codes via the standard JSON envelope (stderr) on non-zero exit:

| code | Meaning | Recovery |
| --- | --- | --- |
| `invalid_query` | Unknown metric name, missing/invalid param, or unknown interval. | Re-prompt for the param, or call `om metric list` to confirm the metric exists. |
| `missing_api_key` | `OM_API_KEY` not set. | Tell the user to run `om init` or `export OM_API_KEY=...`. |
| Upstream code (e.g. `rate_limited`, `not_found`) | Forwarded from the OpenMarket Data API. | Wait + retry, or refine the selector. |

Per-metric compute failures (insufficient bars, malformed bar data) surface as `ok: false, value: null` in the response; they don't fail the whole request. Read the stderr hint to know which metric and why.

## Relationship to `om alert`

`om metric get` uses **the same metric registry, the same parameter validators, and the same data-fetch path** the alert engine uses. If you can compute it here, you can alert on it via `om alert create --metric <same name> --params <same shape>` (see `alerts.md`). If a metric doesn't show up in `om metric list`, it can't be used in an alert either.

A common pattern: use `om metric get` to sanity-check what the metric currently reads, then write an alert with thresholds informed by that value.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om metric get` (action: `metric_get`) — Compute one or more named scalar values over the latest candle window for a (symbol, exchange, interval) tuple.
- `om metric list` (action: `metric_list`) — List every available scalar metric — name, source data type, and accepted parameter names.
- `om metric screen` (action: `metric_screen`) — screen a universe of symbols on a single scalar metric (price, delta_pct, volume, funding_rate, open_interest, RSI, MACD, EMA, ATR, etc.).

<!-- AUTO: END COMMAND REFERENCE -->
