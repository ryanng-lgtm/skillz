---
name: openmarket-signal
description: Author and tune `om signal` producers — the pure {direction, conviction} views that strategies, studies, and backtests consume. Use when the user asks what signal kinds exist, wants to create or edit a signal (text_long_short, metric_level_rule, metric_band_rule), asks about signal context/memory, the decision cache, evaluation cadence (bar vs tick, cooldown), or why editing a signal was refused. For wiring a signal to a market and trading it, see strategy.md.
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om signal — directional signal producers

A signal is a **pure producer**: it emits a `{direction, conviction}` view (`bull`/`bear`/`neutral` at `0..1`) and never trades, reads no account, and touches no venue. Strategies (`om strategy`), research studies, and backtests all consume the same signal by slug. Lifecycle: `create · list · show · edit · pause · resume · remove`.

The consumer contract: a strategy references a signal by slug and turns its view into orders through a sizer — how a view becomes a position (flip thresholds, neutral/reversal policy, capital) is **strategy** configuration, not signal configuration. See `strategy.md`.

## Kinds and their tunables

Three kinds, each with its own `##` section below: `text_long_short` (LLM over an event-watch), `metric_level_rule` (deterministic TA level rule), `metric_band_rule` (stateful TA hysteresis rule). Routing between the create tools follows the rule's nature, not its vocabulary: market words alone never make a metric signal — a thesis ABOUT a market judged from streamed text is still `text_long_short`, and the metric kinds apply only where a deterministic computation over market data decides.

## `text_long_short` — an LLM over an event-watch

Reads the latest accepted event of an event-watch and classifies it against the user's thesis.

- **`topic`** — the entire trading policy: what LONG and SHORT mean, and (when context is on) how prior context should inform the decision. The shared classifier prompt is deliberately neutral — interpretation rules ("a repeat of something already in the overview is priced in — stay NEUTRAL") live in the topic, nowhere else.
- **`context`** (ON by default for newly created signals — `{overview: true, recent_events: 5}`; opt out at create with `--no-context`/`no_context`, or later with `om signal edit --clear-context`; a signal whose spec carries no context block classifies in isolation until you add one) — without it the classifier judges each event in **isolation**. With it, the event-watch's `overview.md` plus a bounded list of recent accepted events is supplied as untrusted reference. `context.recent_events` (0..20, default 5) sizes the memory; `context.overview=false` feeds only the recent events. If the watch has no synthesized overview yet, that tick logs a notice and classifies in isolation. (`overview=false` **and** `recent_events=0` is rejected — that would be context with nothing in it.)
- **`model` pin** (`provider` + `model_ref`, both-or-neither) and **`prompt_ref`** — pin the classifier; unpinned signals follow the configured default.
- **Decision cache** — classifier verdicts are stored durably and reused instead of re-calling the LLM. The key is a **pair**, and *both* halves must match for a hit: a **criteria** fingerprint (`topic`, context policy, `prompt_ref`, the resolved provider/model + base URL) and an **input** hash (the event text, plus the overview and recent-events memory actually fed that tick). ⚠️ **Neither half includes the event-watch or the slug** — they are provenance only. So two signals with the same criteria **share verdicts on any event whose assembled input is identical**, even across different watches: renaming a signal changes nothing, and a second signal over the same criteria pays nothing. (With `context` on, two different watches usually supply different overviews, so their inputs differ and they do *not* share — the criteria half still matches, the input half doesn't.) To inspect or permanently invalidate pinned verdicts use `om signal decisions list|purge` (each purged row recomputes at one LLM call on its next classify); for a run-scoped bypass that deletes nothing, the backtest's `--no-signal-cache`. A fresh slug alone never forces a fresh, paid classification — only fresh criteria or a purge do.

**Neutral means "no information" here.** A classifier's neutral is noise, not an exit instruction — which is why a strategy defaults to `on_neutral: hold` behind a `text_long_short` signal (see `strategy.md`). Nothing about that lives on the signal.

⚠️ **A text signal only classifies events accepted AFTER the strategy was last enabled.** There is no backlog pickup on arm: events that landed while the strategy was paused are never classified. (The cutoff is the strategy's `enabled_at`, falling back to `created_at`.)

**Identity guard**: the model pin (including `prompt_ref`), `topic`, and context policy define the signal's `producer_id`. Editing any of them — or editing a signal **any** strategy references, even just its label — is refused without `force`, because downstream consumers and cached decisions key on that identity. The `event_watch` is **not** an identity input; changing it is not an identity change (but still needs `force` if a strategy references the signal).

## `metric_level_rule` — a deterministic TA level rule

A metric condition over one market selector → a direction at **conviction 1.0** when the data is ready. No LLM, no event-watch; reads the OpenMarket data API through the same registry as `om metric get`.

⚠️ **Not-ready data is an ABSTAIN, not a flat.** When the verdict depends on data that is not ready — indicator warm-up, an empty fetch, a non-finite expression — the signal emits conviction **0**, which the strategy treats as *"I have no view"* and **holds** its current exposure. It never flattens on missing data. A compound condition abstains only when the missing leg could change the answer: `any(true, not-ready)` fires and `all(false, not-ready)` settles false (the outcome is the same for every value the blind leg could have taken, and the rationale names it inline), while `all(true, not-ready)` and `any(false, not-ready)` genuinely hang on the missing leg and abstain. That is a different thing from an acting neutral (below), which conviction 1.0 makes a deliberate instruction.

- **Selector** — `symbol` + `exchange` + `interval` (+ `quote`).
- **Comparison** — `metric`+`period` vs a `threshold` (metric-vs-value: RSI < 30) or vs a second metric (`compare_metric`+`compare_period`, metric-vs-metric: golden cross). The `signal_create_metric` tool also accepts an explicit `condition` tree (`{all:[…]}`, `{any:[…]}`, `{not:{…}}`, arithmetic value expressions) for compound and multi-param-indicator rules the flags can't express. ⚠️ The `--metric` **flag** only accepts a subset: `price`, `delta_pct`, `delta_abs`, `volume`, `funding_rate`, `open_interest`, `rsi`, `sma`, `ema`, `atr` (plus installed `wrun/...` ids). **`macd`, `bb_*` and `stoch_*` are rejected from the CLI** — author those through the `signal_create_metric` action with an explicit `params` object.
- **Don't use `eq` against a computed metric.** All the comparison operators (`gt`/`gte`/`lt`/`lte`/`eq`) test the exact computed float with no tolerance, and `eq` in particular is a bare IEEE `===` — so `eq` on a continuously-valued indicator — RSI, SMA, EMA, ATR, a delta, price — effectively **never fires**: a computed float almost never lands on the exact bit-pattern you name. Express "around this level" as a **banded condition** instead — a `gte`/`lte` window (e.g. `rsi gte 49 AND rsi lte 51`), or a `metric_band_rule` with enter/exit thresholds. `eq` is only sound against a genuinely discrete value.
- **`on_true` / `on_false`** — direction mapping for the condition's truth. **`on_false` defaults to neutral**, which makes the rule *one-sided*: `--on-true bull` with the default emits only `bull` or `neutral`, **never `bear`**. That is usually what you want ("long *while* oversold, flat otherwise") — but it means the rule can never emit an opposing view, so pairing it with a sizer stance that holds through a neutral produces a strategy that can never exit. `om strategy create` warns; see `strategy.md`. For a two-sided rule (a golden/death cross) set `--on-false bear` explicitly. And note **a metric rule's neutral IS its exit instruction** — "the condition I entered on is no longer true" — which is why a strategy defaults to `on_neutral: flatten` behind a metric signal, the opposite of the text lane.
- **`eval`** (default `bar`) — `bar` re-evaluates once per closed bar of the selector interval (look-ahead-free "signal on close"); `tick` re-evaluates every daemon tick on the forming bar and acts only when the emitted direction changes. **`cooldown`** is **tick-only** (supplying one in `bar` mode is rejected) and rate-limits entries — exits and reversals are exempt and act immediately; in any non-observe mode a 1m default cooldown applies when unset.

## `metric_band_rule` — a stateful TA hysteresis rule

Per-side condition trees — `long.enter`/`long.exit` and `short.enter`/`short.exit` — persisted as a `flat`/`long`/`short` regime. From flat, exactly one fired entry enters that side (simultaneous long+short entries stay flat as ambiguous); while positioned, the exit condition is evaluated first. The right shape for RSI bands and Bollinger-style two-threshold systems. Same `eval`/`cooldown`/abstain semantics as `metric_level_rule`.

**A side is optional.** For a short-only (or long-only) band, OMIT the other side entirely — an omitted side simply never trades that direction. Do NOT fabricate a never-firing guard condition for the unused side; every supplied condition must reference at least one metric operand, so a constant "never" guard is rejected. At least one side is required, and a side is always `enter`+`exit` together.

⚠️ **A band signal's regime is per consuming strategy, not shared.** Unlike `metric_level_rule` (a pure function of the current bar), a band signal's emitted view depends on the `flat`/`long`/`short` state — and that state is kept **per strategy that references the signal**, not once on the signal. So a band signal reused by two strategies emits from two independent regimes: while the metric sits inside the dead zone it can return `long` to a strategy that entered earlier and is still holding, and `flat` to a strategy that started flat, **at the same instant**. Each consumer stays internally consistent, but the "one producer, many consumers" reuse promise does **not** give identical views here — a paper twin, a two-consumer comparison, or a backtest replay that starts flat will diverge from a live consumer mid-regime. When you need identical views, author a separate band signal per consumer.

⚠️ **A band fires its exit BY emitting neutral** (the regime returns to `flat`). So a sizer stance that holds through a neutral would swallow the exit conditions you authored — `om strategy create` **refuses** a band signal with `--sizer-mode always_in` or with `--on-neutral hold`.

## Cross-market conditions (both metric kinds, bar mode)

A condition operand normally inherits the signal's shared `selector`; it MAY carry its **own** `selector` to read a different market — "BTC/ETH ratio", "conditioned on BTC+SOL, execute on XRP". In **bar mode** (the default) these evaluate live and backtest: the shared `selector` is the **clock** — evaluation fires at each close of its bar, and every foreign operand reads its own **last closed bar as of that instant** (a `DAY` operand inside an `HOUR` rule holds one value across the day; a foreign bar closing after the clock instant is invisible — the same no-look-ahead rule as the home market's forming bar). ⚠️ **An operand selector's omitted `interval`/`quote` default to `HOUR`/`USD` — they do NOT inherit the shared selector's values**; spell them out when the shared clock is not hourly. Freshness is trust-latest (no staleness gate); a foreign series' failed reading abstains-and-holds with the series named in `last_error` **when the verdict depends on it** — a failed reading on a leg the compound decided WITHOUT (a dominant sibling settled it) does not abstain: the strategy acts, and the fault surfaces as a WARN log plus the `last_issue_note` breadcrumb on `om strategy show` (deliberately not `last_error` — the verdict path is healthy). In **tick mode** selector-bearing conditions are deferred — the view abstains — and tick backtests are refused anyway. ⚠️ A `wrun/...` operand whose package pins foreign `symbol`/`exchange` input sources is a cross-market read IN DISGUISE: the tick-mode deferral scans only operand selectors written in the signal spec and cannot see pins inside package metadata, so any signal using a pinned-package WRUN operand must be authored `eval: "bar"` explicitly. Bindable-market WRUN operands (packages with a `binding: "required"` odds input) carry their `sourceBindings` on the operand like `params`; two operands may bind the same package to different markets and are distinct reads. `signal_create_metric`/`signal_edit` return a `warnings[]` note naming the cross-market operands and their sampling rule. CLI flags cannot express a cross-market **level** rule (no `--condition` JSON on create) — author it through the `signal_create_metric` action's `condition` tree, or `signal edit`'s `condition`; the band kind's `--long-enter`-style JSON flags accept operand selectors directly.

## Required fields, by kind

What `create` will refuse you for. Everything else is optional.

| Kind | Required |
| --- | --- |
| `text_long_short` | `--event-watch` + `--topic` |
| `metric_level_rule` | `--symbol` + `--exchange` + `--metric` + `--op` + `--on-true`, **plus exactly one of** `--threshold` (metric-vs-value) or `--compare-metric` (metric-vs-metric) |
| `metric_band_rule` | `--symbol` + `--exchange` + at least one full side: `--long-enter`+`--long-exit` and/or `--short-enter`+`--short-exit` (each a JSON condition; omit a side entirely to never trade that direction) |

`--kind` itself defaults to `text_long_short`. **`kind` and `slug` are immutable** — `edit` cannot change either; remove and recreate.

## Lifecycle — pausing is not a round trip

`om signal list` enumerates every signal with its kind and enabled state; `om signal show <slug>` prints the full resolved spec. `om signal create` authors one and `om signal edit <slug>` tunes it (subject to the identity guard above). `om signal pause <slug>` stops evaluating it, `om signal resume <slug>` starts again, and `om signal remove <slug>` deletes it (refused while a strategy references it, unless you pass `--force`). The delete is permanent, so it confirms first — the tool call raises an approval card, the terminal form prompts, and `--yes` is the scripted bypass.

⚠️ **Pausing a signal auto-pauses every strategy that references it** (the daemon does it on its next tick) — and **`om signal resume` does NOT re-enable them.** You must re-arm each one with `om strategy resume`. The pause command prints this, but the asymmetry is easy to miss: pause-then-resume leaves your strategies silently dark.

## Tool-call hygiene

When creating or editing via the `signal_*` (or any `om`) tools, **omit optional fields you have no user instruction for** — do not pass a field just to restate its default. The chat surface renders what each call set versus defaulted; explicitly passing defaults misreports them as user choices.

## Quick recipes

```bash
# Event-driven text signal, context-aware
om signal create --kind text_long_short --event-watch fed-watch \
  --topic "LONG = raises the odds of a cut; SHORT = lowers them; repeats of known news are priced in — NEUTRAL" \
  --context --context-recent-events 5 --slug fed-cut-view

# Deterministic RSI band, evaluated on bar close
om signal create --kind metric_level_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --metric rsi --period 14 --op lt --threshold 30 --on-true bull --slug sig-rsi-oversold

# Short-only hysteresis band (no long side at all): enter short at RSI>75, cover at RSI<55
om signal create --kind metric_band_rule --symbol ETHUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --short-enter '{"left":{"metric":"rsi","params":{"period":14}},"op":"gt","right":{"value":75}}' \
  --short-exit  '{"left":{"metric":"rsi","params":{"period":14}},"op":"lt","right":{"value":55}}' \
  --slug sig-rsi-short-band

# Tune a text signal's memory later (a context-policy edit is an identity change — always needs --force)
om signal edit fed-cut-view --context-recent-events 10 --force
```

Verify with `om signal show <slug>`; a paused signal keeps its spec and history. For binding a signal to a market, sizing, exits, and run modes, continue in `strategy.md`.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om signal` — (bespoke; see narrative above)
- `om signal create` (action: `signal_create_text`) — Create a text_long_short signal: an LLM classifier over an event-watch's occurrences
- `om signal create` (action: `signal_create_metric`) — Create a deterministic metric rule signal (metric_level_rule or metric_band_rule)
- `om signal decisions` — (bespoke; see narrative above)
- `om signal decisions list` (action: `signal_decisions_list`) — Inspect the durable text_long_short decision cache: the pinned classifier verdicts, newest first.
- `om signal decisions purge` (action: `signal_decisions_purge`) — Permanently invalidate pinned decision-cache verdicts (filter by signal slug, event id, or spec fingerprint; no filter purges the whole cache).
- `om signal edit` (action: `signal_edit`) — Patch tunable fields of an `om signal` by id or slug.
- `om signal list` (action: `signal_list`) — List configured `om signal` directional producers (the persisted SignalSpecs).
- `om signal pause` (action: `signal_pause`) — Disable one `om signal` producer by id or slug (preserves the spec).
- `om signal remove` (action: `signal_remove`) — Remove one `om signal` producer by id or slug.
- `om signal resume` (action: `signal_resume`) — Re-enable one paused `om signal` producer by id or slug.
- `om signal show` (action: `signal_show`) — Show one `om signal` producer spec by id or slug, plus the strategies that reference it (its downstream consumers).

<!-- AUTO: END COMMAND REFERENCE -->
