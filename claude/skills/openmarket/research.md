---
name: openmarket-research
description: Run correlational event studies and costed strategy backtests over an OpenMarket event watch and one asset's candles. Use when the user asks whether a watched text-event stream coincided with market moves, wants to inspect event anchors, wants pre/post returns around accepted event-watch rows, or wants to replay a strategy (saved or candidate) over historical events or bars. Never present the result as a trade signal or tradeable edge.
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om research

Research studies answer a narrow question: did accepted rows from one event watch line up with price movement in one chosen asset? Research backtests answer the paired simulation question: if a STRATEGY had traded through that history — its signal deciding direction, its sizer the weight, its exit config the exits — after costs and latency, what would the account path have done? A backtest always replays a strategy (saved slug or unsaved candidate): the strategy is what prescribes the trade-intent the simulation needs.

## Reach for `backtest_run` (`om backtest`) FIRST

For "does this roughly make sense" questions, the one-shot verb is the right tool: `backtest_run` takes a strategy slug, a signal slug, or an event-watch, derives the window, interval, venue-realistic costs, and time basis from what is stored, auto-backfills sparse news history through the real classifier (budgeted, resumable), and reports every derived choice next to the result. It renders a benchmark comparison (buy-and-hold) so the user can eyeball the answer. Everything below — explicit windows, event filters, sweeps, cost models — is the full-control surface for when the user wants a SPECIFIC configuration, a parameter comparison, or a study rather than a simulation.

When a user finishes creating a strategy or a signal, offer to run this one-shot backtest before they arm anything: a quick eyeball of historical behavior is the natural next step and costs one tool call. Never run it unprompted on money-moving surfaces; offering is enough. When the result comes back, present the return against the buy-and-hold benchmark and the honesty notes (warnings) rather than the raw number alone, and mention that `backtest_no_history` results carry real next steps (arm the watch, paper mode, deeper backfill) instead of inventing data.

**Every backtest result carries a `chart` block — surface it.** A live projection includes the view `url` (share it as a link); `mode: "offer"` carries a one-sentence `hint` and optional `url` saying exactly how to see the backtest on the chart — end your reply with that offer (one short line). Never invent chart prerequisites beyond what the block says.

**Chart projection needs no venue, no pairing, no pinned market.** A fresh `backtest_run` auto-renders the ephemeral Strategy Tester panel when a human is watching the one live workspace the daemon can write to (disclosed as `chart.auto`). For "show that backtest on the chart" after the fact, rerun `backtest_run` with the same target plus `open_chart=<workspace id>` (an explicit `open_chart` also unlocks the persistent marker fallback). Never refuse projection over venue or pairing state.

**On the `cli` surface, do NOT re-list the numbers.** The terminal renders the full result card itself (equity chart vs buy-and-hold, return, drawdown, trades and win rate, costs, honesty notes) directly under the tool call. Repeating those stats in prose doubles the output and buries the judgment; give a one-line verdict, ONE insight the card cannot show (why it behaved that way, what the notes imply), and the suggested next step. On remote channels (Telegram/Discord/Slack) there is no card, so summarize the key numbers in text there.

Use this skill when:

- The user asks whether a news/social/event stream moved a market.
- The user wants to sanity-check where a watch fired before fetching candles.
- The user wants forward returns around discrete event timestamps.
- The user asks for a structured artifact that can later be inspected or plotted.
- The user wants a costed account-path simulation for a simple hold-after-event strategy.

Do not use this as a trading signal. The study is correlational, and the backtest is a simulated account path. Neither proves causality, tradeability, fill quality, execution cost, or forward edge.

**Time basis — load the full tool schema before deciding what is possible.** Both `research_study` and `backtest_spec` accept `time_basis: observed_at | source_event_time` and `data_mode: live | backfill`. Backfill rows have no `observed_at`, so for them you must pass `--time-basis source_event_time --data-mode backfill` — an `observed_at` study of backfill rows is misleading, and a default-basis study returns nothing. If your loaded tool schema appears to offer only `observed_at`, re-load the tool with `tool_search` rather than concluding the basis is unavailable.

## Workflow

Start by finding the watch:

```bash
om event-watch list --format json
om event-watch events <watch-slug> --journal-committed --limit 20 --format json
```

If the watch has accepted rows, locate occurrences first. This does not fetch candles and does not need market-data credentials:

```bash
om research study \
  --watch <watch-slug> \
  --locate-only \
  --format json
```

Then run the study with a specific asset, horizons, and pre-window:

```bash
om research study \
  --watch <watch-slug> \
  --asset BINANCE_FUTURES:BTCUSDT \
  --horizon 5m \
  --horizon 1h \
  --horizon 4h \
  --pre 15m \
  --time-basis observed_at \
  --format json
```

For historical backfill rows, use the source timestamp basis and filter the data mode explicitly:

```bash
om research study \
  --watch <watch-slug> \
  --asset BINANCE_FUTURES:BTCUSDT \
  --horizon 1h \
  --pre 1h \
  --time-basis source_event_time \
  --data-mode backfill \
  --from 2026-01-01T00:00:00Z \
  --until 2026-06-01T00:00:00Z \
  --format json
```

For an agent tool call, load and call `research_study` with the same fields:

```json
{
  "watch": "<watch-slug>",
  "asset": "BINANCE_FUTURES:BTCUSDT",
  "horizons": ["5m", "1h", "4h"],
  "pre": "15m",
  "time_basis": "observed_at",
  "data_mode": "live"
}
```

Use `locate_only: true` when you only need the occurrences and provenance. Use `from` and `until` to bound occurrences on the chosen time basis.

The strategy's venue and `--asset` must agree on BOTH lanes (a Polymarket strategy replays only against `--asset POLYMARKET:<its conditionId>`; mismatches refuse with `asset_market_mismatch`, and Polymarket runs resolve the price axis via the CLOB — see the bar-mode bullet for the full identity/axis rules). To simulate a hold-after-event strategy over the same occurrence set, use `om backtest spec` with a strategy source. There is no strategy-less lane: prescribe the trade-intent explicitly — an inline candidate whose signal is a `constant` (direction bull or bear, conviction as the weight) reproduces the classic hold-after-event run without saving anything. Prefer compact JSON for agent summaries unless the user needs the full fill/equity artifact.

```bash
om backtest spec \
  --watch <watch-slug> \
  --asset BINANCE_FUTURES:BTCUSDT \
  --candidate-file hold-long.json \
  --hold 1h \
  --fee-bps 5 \
  --slippage-bps 10 \
  --latency-bars 1 \
  --time-basis source_event_time \
  --data-mode backfill \
  --format json \
  --compact
```

with `hold-long.json` (the candidate is creatable verbatim via `om strategy create` / `om signal create`; the sizer owns the weight):

```json
{
  "strategy": {
    "slug": "hold-long-probe",
    "signal": "hold-long-signal",
    "market": { "venue": "hyperliquid", "coin": "BTC" },
    "sizer": {
      "config": { "mode": "single_sided", "side": "long" },
      "scale": "fixed",
      "capital": { "source": "fixed", "amount": 10000 }
    }
  },
  "signal": {
    "slug": "hold-long-signal",
    "spec": { "kind": "constant", "direction": 1, "conviction": 0.05 }
  }
}
```

### Replaying a saved strategy

`--strategy-slug <slug>` replays a strategy created with `om strategy create` through the SAME live decision core (`planStrategyTick`), including its exit config. **Stored-spec honesty:** when the saved file needed a read-time repair (a legacy field stripped, a value migrated), the report discloses each repair as a `spec_repaired_on_read` note; a repair that changed the exit or sizer block — e.g. an out-of-bounds stop dropped on read — refuses the run with `spec_repair_changes_semantics` instead (the replay will not quietly test a stop-less variant of the strategy you saved; fix the stored spec with `om strategy edit` and re-run — the daemon reads the same repaired spec, so those fields never applied live either). The replay includes the (possibly repaired) exit config (take-profit / stop-loss behave like brackets RESTING at the venue: each held bar's real high/low can touch a trigger level, the fill prices at that level — or at the open when the bar gapped through it — on the touching bar, and when one bar touches both levels the stop-loss wins, conservatively — unless the bar OPENS at-or-beyond the take-profit level, which fills at the open first; the time-stop evaluates at bar closes and flattens at the next bar open; trigger fills are exempt from `--latency-bars`; trades carry an `exit_reason`). The invocation depends on the strategy's signal kind:

- **Constant signal** — occurrence-anchored: keep `--watch` (entries anchor to accepted rows), add `--strategy-slug`.
- **Bar-mode metric signal (`metric_level_rule` / `metric_band_rule`)** — strategy-native: NO `--watch`; the signal decides on every bar of the traded asset. Requires `--asset` and both `--from`/`--until` (the decision window; align them to bar boundaries — a partially-covered bar at either edge is excluded whole, since it would trade on data outside the window). `--hold`, `--time-basis`, and the event filters (`--outcome`, `--min-confidence`, `--source`, `--data-mode`, `--limit`) are rejected here — they shape event-watch occurrences, which a bar-cadence replay has none of. Tick-mode metric signals cannot be replayed (a bar is the backtest's cadence). A condition carrying a **per-operand selector** (a cross-market operand naming its own market) replays natively: the prefetch fetches one series per (market, data type) across every operand — sweep variants included, unioned into one covering pass — and each foreign operand is sampled as-of the clock (shared-selector) bar's close, exactly as live evaluation samples it (an operand selector's omitted interval/quote default to HOUR/USD). Signals on installed WRUN metrics (`wrun/@scope/name/output`) replay exactly like built-ins — the package must be installed, or the gate rejects with `wrun_metric_not_installed`. When a signal's own decision acts on a bar, the decision owns that bar and the bracket is not evaluated there — so fast mean-reversion signals can close trades before their brackets ever stamp; bracket stamps under-count bracket-level breaches by design. A `bar_extremes_repaired` warning means some source bars under-reported their own open/close range and the trigger evaluation widened them — treat tp/sl fills on those bars as data-quality-limited. **Band-regime seeding:** a `metric_band_rule` replay always seeds its regime FLAT at the window start and folds it forward per bar at the signal level, independent of fill outcomes — live instead seeds from the strategy's persisted regime and advances it only when a decision's fills actually reach. Two consequences to keep in mind when comparing against a live run: a window opening while the live strategy is mid-regime replays as a fresh entry, and an entry whose fill dies leaves the fold already advanced (the replay can enter inside the hysteresis dead zone where live would have re-evaluated the enter condition and stayed flat). **Asset/market identity is enforced**: the strategy's venue and `--asset` must agree — a Polymarket strategy replays only against its OWN condition's series (`--asset POLYMARKET:<conditionId>`), a non-Polymarket strategy never against a Polymarket series (non-Polymarket proxy series stay allowed for non-Polymarket venues); mismatches refuse with `asset_market_mismatch`. Polymarket runs also resolve which side of the binary the series prices: when the strategy's `long_outcome` is the complement (second) outcome the series is complement-mapped before the replay and the report's `backtest.price_axis` says `"complement"`; an unresolvable outcome order (CLOB unreachable, non-binary market, unknown `long_outcome`) refuses with `long_outcome_axis_unresolved` rather than guessing an axis.

- **Text signal (`text_long_short`)** — occurrence-anchored, but the watch is DERIVED from the signal: OMIT `--watch` (a conflicting value errors). Each accepted event in the window is classified with a REAL LLM call through the durable decision cache, so the first run spends money (`text_classifier_usage` reports exactly how many paid calls) and every rerun of the same criteria + events is FREE and reproduces the same verdicts — sweeps and iterations are cheap after the first pass. A classifier failure aborts the run; already-computed verdicts are cached, so re-running resumes and re-pays only the failed call. Pass `no_signal_cache` (`--no-signal-cache`) to bypass the durable cache for one run — classify fresh, pin nothing, delete nothing (pinned verdicts stay untouched, and the rerun-is-free guarantee does not apply to a bypassed run); to permanently invalidate pinned verdicts instead, `om signal decisions purge`. Cap spend with `max_llm_calls` (`--max-llm-calls`): the run stops with `backtest_llm_budget_exceeded` BEFORE exceeding the cap, cache hits never count (a warm rerun replays free under any cap), and everything paid before a stop stays cached — solo runs default to unlimited (the occurrence cap bounds them), sweeps to 500 across ALL variants. Context-enabled signals (a `context` policy — the default for newly created text signals) replay too: `--context-replay normal` (the default) rebuilds each event's memory from the watch's durable development timeline as it provably stood at that event, `advanced` feeds the overview snapshot that stood at that moment where snapshot history survives — the report's `context_replay_mode` note names the mode and its bias direction, with companion notes for degraded assemblies and unprovable authorship. Passing `--context-replay` for a signal with no context policy is a typed error. Granularity caveat for backfilled watches: the authorship fence admits a development only when its synthesis pass read nothing at-or-after the occurrence, so a bulk backfill synthesized in one default page replays with an EMPTY overview throughout (disclosed via `context_empty_overview`) — re-author the timeline first with `om event-watch synthesize --rebuild --page-size <n>` (paid passes, count disclosed) and the replay picks up the finer-grained backbone. Advanced mode over imported history materializes on demand: a run whose span has no qualifying snapshots refuses with the projected paid-call count and runs only with explicit consent (`--materialize`, or a TTY confirm; `--materialize-page-size` sets snapshot spacing) — undrained imports are synthesized first, then one labeled RECONSTRUCTED brief per page persists durably, so later advanced runs replay free. Reconstructed-fed occurrences are disclosed with a hindsight disclaimer (`context_reconstructed`: the authoring model's training may include the period's outcomes — weigh against a `--no-context` control) plus a per-tier directional-verdict split (`context_tier_composition`); lived snapshots always win where both exist. Classification runs up to 4 calls in flight (`--classify-concurrency`, env `OM_BACKTEST_CLASSIFY=sequential` reverts to serial) — completed runs are identical to a serial run, only wall-clock changes. Live-decision parity on the event lane: when several accepted events anchor to ONE decision bar, only the newest acts (live reads only the newest accepted event per heartbeat; the decision bar is the replay's heartbeat analog) — superseded events open no holds and are never classified, and the `burst_events_superseded` warning counts them. Every classified verdict is actionable, zero-confidence included (fixed scaling enters at full magnitude, conviction scaling targets zero) — only textless abstains hold.

```bash
om backtest spec \
  --strategy-slug <strategy-slug> \
  --asset BINANCE_FUTURES:BTCUSDT \
  --from 2026-03-01T00:00:00Z \
  --until 2026-04-01T00:00:00Z \
  --fee-bps 5 \
  --slippage-bps 10 \
  --format json --compact
```

Heed the honesty warnings when summarizing: `metric_not_ready` (the signal's data went missing — abstained bars held exposure; the message names the starving selector), `window_edge_undecidable` (the last bars of any window cannot fill under next-bar-open), `hold_exit_unexecuted` (a scheduled `--hold` exit could not flatten the book — the position rode past its scheduled exit and the affected trades are exit-clamped to the data edge, not closed), `no_time_stop_rides_to_window_end` (no scheduled exit existed — a no-time-stop strategy, or an explicit `--hold none` — so positions close only via the strategy's own managed exits or a signal-driven close, else ride to the end of the priced window, reported open-at-edge), `fill_gap_spanned` (a next-bar-open fill landed across a wall-clock hole in the bar series — the decision executed stale at the post-gap price), `time_stop_spanned_gap` (a time-stop's elapsed clock counted holding time across a barless hole — live would have evaluated in real time), `exit_attribution_unresolved` (a managed-exit fill could not be resolved onto any trade — its trigger label is omitted, never guessed, so the labeled-exit arithmetic under-counts), `burst_events_superseded` (several accepted events shared one decision bar — only the newest acted, matching live's newest-only heartbeat read; the count is the older same-bar events that never acted or classified), `coverage_gap` (the series covers less than the requested window — check `backtest.coverage` for the covered range), and `cadence_mismatch` (an explicitly chosen replay interval differs from the signal's declared cadence — an omitted `--interval` already defaults to the signal's; drop the flag or pass the suggested value for live parity).

### Backtesting an unsaved candidate

`--candidate-file <path>` replays a strategy that exists nowhere on disk — a JSON file of shape `{strategy, signal?}` where `strategy` carries the authoring fields of `om strategy create` (slug, signal, market, sizer, optional label/exit/daemon) and the optional inline `signal` carries `{slug, spec, label?}`. Omit `signal` to reference a saved signal by the strategy's `signal` slug. Nothing is persisted, and the report's `backtest.query.candidate: true` marks its origin.

The contract is **promotability**: a candidate is validated by the exact create-path schemas and validators, so a candidate that backtests is creatable once it earns it — the strategy fields pass to `om strategy create` verbatim; an inline signal maps mechanically onto `signal_create` (its `spec` fields become the flat create inputs: kind, selector, condition, long/short, direction/conviction, eval). Candidate slugs must NOT collide with saved ones — including by DERIVED id (slugs slugify to ids by collapsing separator runs) — pick fresh names.

### Sweeping spec variants

`om backtest sweep` compares N variants of one base strategy (saved `--strategy-slug` or unsaved `--candidate-file`) in a single invocation over ONE shared market-data pass — the natural tool for threshold sweeps and exit-policy comparisons:

```bash
om backtest sweep \
  --strategy-slug <slug> \
  --sweep-file sweep.json \
  --asset BINANCE_FUTURES:BTCUSDT \
  --from 2026-03-01T00:00:00Z --until 2026-04-01T00:00:00Z \
  --format json
```

`sweep.json` holds `{"variants": [...]}` — up to 32 entries of `{name?, strategy_patch?, signal_patch?}`. Patches are RFC 7386 merge patches over the base's AUTHORING form (the candidate shape above): objects merge, `null` deletes a key, arrays/scalars replace wholesale. `{}` is the baseline row — it replays the base resolution unchanged, never a re-assembled copy (identical to a solo run of the base; include it for comparison). Examples: `{"signal_patch": {"spec": {"condition": {"right": {"value": 105}}}}}` moves a threshold; `{"strategy_patch": {"exit": {"bracket": {"tp": 0.02}}}}` adds a take-profit.

Rules of the road: all variants share the run knobs (asset, window, costs, watch/hold, and the occurrence filters — `--time-basis`, `--data-mode`, `--outcome`, `--min-confidence`, `--source`, `--limit` — so backfill sweeps use `--time-basis source_event_time --data-mode backfill` exactly like a solo backtest) — only the specs vary; variants must stay in the base's data lane (metric bar-cadence vs occurrence-anchored — cross-lane comparisons are separate sweeps); patching a saved base's signal runs an ephemeral shadow, never a write-back.

Reading the summary: each row carries the full metrics block, warning magnitude per code, and `exit_reasons` counts for MANAGED exits only (take_profit / stop_loss / time_stop — signal-driven closes are unlabeled; their count is `trade_count` minus the labeled sum). The summary is for ranking; re-run the winning variant solo with `om backtest spec` for its full report, and promote it with `om strategy create` when it earns it.

A strategy whose sizer sets `leverage` above 1 refuses to backtest outright (`leverage_unmodeled`): the venue models no margin, no funding, and no liquidation, so a leveraged equity path would be fiction — losses that would have liquidated the account instead ride to the window edge. Backtest at leverage 1 and apply leverage only after promotion, remembering that results then scale in exposure but NOT in liquidation risk. Heed `metric_not_ready` (the signal's data went missing — abstained bars held exposure) and `window_edge_undecidable` (the last bars of any window cannot fill under next-bar-open) warnings when summarizing. The venue models no short-side margin or liquidation: an adverse short rides to the window edge un-liquidated, so short-heavy results read optimistic versus a real venue — and once such a short drives equity non-positive, the sizer's fail-closed guard freezes ALL decisions including signal-driven exits (`equity_exhausted_decisions_suppressed` counts those bars). On text runs also heed `textless_events` (events with no extractable text abstain rather than classify) and `text_all_abstain` (NO occurrence produced an actionable verdict — exposure never changed) and report the `text_classifier_usage` spend line to the user.

## Interpretation

Read the table as an event study, not as a strategy.

- `t0` is the event timestamp on the chosen time basis.
- `px@t0` is aligned to the next closed candle.
- `pre` measures whether the market had already moved before the event anchor.
- Forward returns measure what happened after the anchor over each horizon.
- `moved_after` means the forward move was larger than the pre move under the simple A1 verdict rule.
- `already_repriced` means the pre move was at least as large and in the same direction as the forward move.
- `no_move` means the measured move was below the current simple threshold.
- `insufficient_data` means every horizon's return was null for that row — usually because the horizon has not closed yet, bars are missing for that window (`target_bar_missing`), a data gap collapsed the measurement window onto a single bar (`gap_collapsed_window`), or the anchor bar's close was degenerate (`degenerate_anchor_close`). The `exclusions` tally names which. The tally can also carry source-level drops that never became rows at all: `row_excluded_null_observed_at`, `row_excluded_null_source_event_time`, and `row_excluded_invalid_source_event_time` (rows whose event timestamps were unusable under the chosen time basis).
- The aggregate line reads `raw` (rows before cooldown clustering) / `eff` (rows after folding same-cluster rows — the n the stats use) / `distinct t0` (distinct event instants among effective rows; same-instant rows inflate n past this).

Always mention caveats when summarizing:

- Strictly correlational, never a trade signal.
- Small samples are weak evidence.
- Overlapping forward windows can make rows look more independent than they are.
- Closely clustered event rows may be the same story repeated.
- `observed_at` is the live/actionable observation basis.
- `source_event_time` is for historical/source timestamps, especially `data_mode=backfill`; it is non-actionable and should be described that way.

Prefer JSON when the user wants reproducibility. The study JSON artifact carries watch id/slug, event row ids, horizons, pre-window, candle window, alignment policy, aggregate, and warnings. Full backtest JSON includes intents, fills, and the equity curve; compact backtest JSON returns only the spec, metrics, and warnings.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om backtest` (action: `backtest_run`) — THE DEFAULT BACKTEST TOOL: whenever the user asks to backtest something or whether a strategy/signal/news idea would have worked, call THIS, not backtest_spec.
- `om backtest run` (action: `backtest_run`) — Explicit spelling of the bare `om backtest <target>` one-shot (the default kind of the backtest group).
- `om backtest spec` (action: `backtest_spec`) — Replay a strategy (constant, text_long_short, or bar-mode metric signal) from a saved slug OR an unsaved candidate spec; the strategy prescribes the trade-intent (direction, sizing, exits) the simulation replays.
- `om backtest sweep` (action: `backtest_sweep`) — Replay N spec variants of one base strategy (saved slug or unsaved candidate) over ONE shared market-data pass.

- `om research` — (bespoke; see narrative above)
- `om research study` (action: `research_study`) — Run a strictly correlational event-anchored study over accepted event-watch rows and one asset's candles, or use locate_only to return just the event occurrences.

<!-- AUTO: END COMMAND REFERENCE -->
