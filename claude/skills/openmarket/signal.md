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

A signal is a **pure producer** — it never trades, reads no account, and touches no venue; how a view becomes a position (flip thresholds, neutral/reversal policy, capital) is **strategy** configuration, not signal configuration. Load the strategy skill via `skill_read`.

### Guardrails

⚠️ **A text signal only classifies events accepted AFTER the strategy was last enabled.** There is no backlog pickup on arm: events that landed while the strategy was paused are never classified (cutoff detail: §"`text_long_short` — an LLM over an event-watch").

⚠️ **Not-ready data is an ABSTAIN, not a flat.** When the verdict depends on data that is not ready, the signal emits conviction **0** — the strategy reads *"I have no view"* and **holds** its current exposure. It never flattens on missing data.

⚠️ **A band fires its exit BY emitting neutral.** A sizer stance that holds through a neutral would swallow the exit conditions you authored — `strategy_create` **refuses** a band signal with mode `always_in` or with `--on-neutral hold`.

⚠️ **Pausing a signal auto-pauses every strategy that references it** — and **`signal_resume` does NOT re-enable them**: re-arm each with `strategy_resume`, and warn the user before pausing a referenced signal.

**Identity guard:** editing a signal an acting-mode (`paper`/`dry_run`/`live`) strategy references — even just its label — or editing any identity input (the model pin, `topic`, or context policy) is refused without `force`; observe-only consumers are disclosed in `warnings[]`, not gated. Details: §"`text_long_short` — an LLM over an event-watch"; the refusal: §"Errors".

**Derive, disclose, override — create immediately.** For a signal ask, create with the defaults for everything unspecified and read the resolved spec back in one compact block; never interrogate up front about periods, cadence, or context — the readback is the override surface.

**Author only what was asked.** A signal ask creates a signal and nothing else — never an unrequested strategy, alert, or order (the user consented to one object). Offer the strategy wiring as a next step; do not build it.

### Routing

Routing between the create tools follows the rule's nature, not its vocabulary: market words alone never make a metric signal — a thesis ABOUT a market judged from streamed text is still `text_long_short`; the metric kinds apply only where a deterministic computation decides. Per-kind neutral semantics drive different strategy-side defaults (hold-through-neutral for text, flatten for metric — the strategy skill via `skill_read`). On a Polymarket-pinned strategy the topic pairs with `--long-outcome`: the long/short inversion is encoded in exactly ONE of the two, never both (the axis rule rides the strategy skill's intro).

Quick routing — one recipe per common ask; disclose every default you assume:

| Ask | Recipe |
| --- | --- |
| "signal when RSI < 30 on BTC" | `signal_create_metric` `metric_level_rule`: rsi(14) `lt` 30, `HOUR` unless phrased otherwise, `on_true` from the ask (the false side defaults to neutral — say so); `exchange` only when the user named a venue — omitted, the create stamps the coin's default listing and the result's `listing_note` says which, in words; a named venue is never substituted. |
| "golden cross" | level rule sma(50) `gt` sma(200), `DAY`, `on_true` 1 (bull) + `on_false` -1 (bear) — two-sided. |
| "enter above X, exit below Y" / a band | `metric_band_rule`: per-side enter+exit trees; omit an unused side — never fabricate a guard. |
| "watch <news>, go long/short" | `signal_create_text` over an EXISTING event-watch (none → the event-watches skill via `skill_read`); the topic is the whole LONG/SHORT policy; context defaults on — disclose. |
| "change my signal's topic / memory / model" | `signal_edit` — an identity change, refused without `force`: relay, ask, retry only on an explicit yes (§"Errors"). |
| "pause / stop / delete the signal" | `signal_pause` (consumers auto-pause; resume does not re-arm them) · `signal_remove` raises the card — never volunteer `force`. |

## Kinds and their tunables

What a signal emits and the three kinds — text_long_short, metric_level_rule, metric_band_rule — with the lifecycle verbs and consumer contract.

A signal emits a `{direction, conviction}` view (`bull`/`bear`/`neutral` at `0..1`). Strategies (the strategy skill), research studies, and backtests all consume the same signal by slug — a strategy turns its view into orders through a sizer. Lifecycle: `create · list · show · edit · pause · resume · remove`. Three kinds, each with its own `##` section below: `text_long_short` (LLM over an event-watch), `metric_level_rule` (deterministic TA level rule), `metric_band_rule` (stateful TA hysteresis rule).

## `text_long_short` — an LLM over an event-watch

The LLM classifier kind: the topic defines LONG/SHORT, context memory, the model pin, and the decision cache that dedupes paid verdicts.

Reads the latest accepted event of an event-watch and classifies it against the user's thesis. A consuming strategy classifies only events accepted after it was last enabled — the cutoff is the strategy's `enabled_at`, falling back to `created_at`; there is no backlog pickup on arm.

The paid baseline: every accepted event a consuming strategy sees costs one classifier LLM call, and only the decision cache (below) makes a repeat free — `no_context` and pinned models change what is judged (and so the cache key), not whether a miss is paid. A signal is created enabled (`enabled=true`) — it starts classifying the moment a strategy references it — pass `enabled=false` to create it paused, and `signal_pause` / `signal_resume` flip it later.

- **`topic`** — the entire trading policy: what LONG and SHORT mean, and (when context is on) how prior context should inform the decision. The shared classifier prompt is deliberately neutral — interpretation rules ("a repeat of something already in the overview is priced in — stay NEUTRAL") live in the topic, nowhere else.
- **`context`** (ON by default for newly created signals — `{overview: true, recent_events: 5}`; opt out at create with `no_context`, or later with `signal_edit` (`clear_context`); a signal whose spec carries no context block classifies in isolation until you add one) — without it the classifier judges each event in **isolation**. With it, the event-watch's `overview.md` plus a bounded list of recent accepted events is supplied as untrusted reference. `context.recent_events` (0..20, default 5) sizes the memory; `context.overview=false` feeds only the recent events. If the watch has no synthesized overview yet, that tick logs a notice and classifies in isolation. (`overview=false` **and** `recent_events=0` is rejected — that would be context with nothing in it.)
- **`model` pin** (`provider` + `model_ref`, both-or-neither) and **`prompt_ref`** — pin the classifier; unpinned signals follow the configured default.
- **Decision cache** — classifier verdicts are stored durably and reused instead of re-calling the LLM. The key is a **pair**, and *both* halves must match for a hit: a **criteria** fingerprint (`topic`, context policy, `prompt_ref`, the resolved provider/model + base URL) and an **input** hash (the event text, plus the overview and recent-events memory actually fed that tick). ⚠️ **Neither half includes the event-watch or the slug** — they are provenance only. So two signals with the same criteria **share verdicts on any event whose assembled input is identical**, even across different watches: renaming a signal changes nothing, and a second signal over the same criteria pays nothing. (With `context` on, two different watches usually supply different overviews, so their inputs differ and they do *not* share — the criteria half still matches, the input half doesn't.) To inspect or permanently invalidate pinned verdicts use `signal_decisions_list` / `signal_decisions_purge` (each purged row recomputes at one LLM call on its next classify); for a run-scoped bypass that deletes nothing, `backtest_run`'s `no_signal_cache`. A fresh slug alone never forces a fresh, paid classification — only fresh criteria or a purge do.

**Neutral means "no information" here.** A classifier's neutral is noise, not an exit instruction — which is why a strategy defaults to `on_neutral: hold` behind a `text_long_short` signal (the strategy skill via `skill_read`). Nothing about that lives on the signal.

**Identity guard**: the model pin (including `prompt_ref`), `topic`, and context policy define the signal's `producer_id`. Editing any of them — or editing a signal an acting-mode (`paper`/`dry_run`/`live`) strategy references, even just its label — is refused without `force` (observe-only consumers are disclosed in `warnings[]`, not gated), because downstream consumers and cached decisions key on that identity. The `event_watch` is **not** an identity input; changing it is not an identity change (but still needs `force` if an acting-mode strategy references the signal). The refusal is typed `signal_edit_requires_force` (§"Errors").

## `metric_level_rule` — a deterministic TA level rule

The deterministic level-rule kind: selector, comparison flags vs condition trees, the on-true/on-false direction mapping, eval cadence and cooldown.

A metric condition over one market selector → a direction at **conviction 1.0** when the data is ready; not-ready data — indicator warm-up, an empty fetch, a non-finite expression — is the abstain the intro mandates. No LLM, no event-watch; reads the OpenMarket data API through the same registry as `metric_get`.

⚠️ **A perpetuals-only metric pointed at a SPOT venue saves — and then abstains forever.** The class is the funding/open-interest family (`funding_rate`, `open_interest`, `open_interest_delta_pct`): those series exist only on derivatives venues, so that operand reads empty on every evaluation. Create/edit accept the spec with an advisory `warnings[]` note (the alert lane refuses the same shape outright). Relay the note verbatim and offer the repoint — `om exchanges --type <TYPE>` lists the venues serving the series. Applies to **both** metric kinds.

A compound condition abstains only when the missing leg could change the answer: `any(true, not-ready)` fires and `all(false, not-ready)` settles false (the outcome is the same for every value the blind leg could have taken, and the rationale names it inline), while `all(true, not-ready)` and `any(false, not-ready)` genuinely hang on the missing leg and abstain. That is a different thing from an acting neutral (below), which conviction 1.0 makes a deliberate instruction.

- **Selector** — `symbol` + `interval` (+ `quote`), and `exchange` when the user named a venue. Omitted, the create (like `metric_get`, and unlike `alert_create`, `metric_series` or `metric_screen`, which need the venue named) resolves the coin's default listing — spot for a price-class rule, the perpetuals book when an operand reads funding or open interest — stamps venue and venue symbol on the saved spec, and discloses them as `listing_note`; a named venue is never rewritten. A `wrun/…` operand on the shared selector is the exception: name the venue, its source book is not known before the package resolves (omitted → `venue_unresolved`).
- **Comparison** — `metric`+`period` vs a `threshold` (metric-vs-value: RSI < 30) or vs a second metric (`compare_metric`+`compare_period`, metric-vs-metric: golden cross). `signal_create_metric` also accepts an explicit `condition` tree (`{all:[…]}`, `{any:[…]}`, `{not:{…}}`, arithmetic value expressions) for compound and multi-param-indicator rules the shorthand fields can't express — multi-param indicators (`macd`, `bb_*`, `stoch_*`) go through an explicit `params` object. (The CLI's `--metric` flag accepts a narrower subset: §"CLI equivalents".)
- **Don't use `eq` against a computed metric.** All the comparison operators (`gt`/`gte`/`lt`/`lte`/`eq`) test the exact computed float with no tolerance, and `eq` in particular is a bare IEEE `===` — so `eq` on a continuously-valued indicator — RSI, SMA, EMA, ATR, a delta, price — effectively **never fires**: a computed float almost never lands on the exact bit-pattern you name. Express "around this level" as a **banded condition** instead — a `gte`/`lte` window (e.g. `rsi gte 49 AND rsi lte 51`), or a `metric_band_rule` with enter/exit thresholds. `eq` is only sound against a genuinely discrete value.
- **`on_true` / `on_false`** — direction mapping for the condition's truth. **`on_false` defaults to neutral**, which makes the rule *one-sided*: `on_true: 1` (bull) with the default emits only `bull` or `neutral`, **never `bear`**. That is usually what you want ("long *while* oversold, flat otherwise") — but it means the rule can never emit an opposing view, so pairing it with a sizer stance that holds through a neutral produces a strategy that can never exit. `strategy_create` warns; see the strategy skill (`skill_read`). For a two-sided rule (a golden/death cross) set `on_false: -1` (bear) explicitly. And note **a metric rule's neutral IS its exit instruction** — "the condition I entered on is no longer true" — which is why a strategy defaults to `on_neutral: flatten` behind a metric signal, the opposite of the text lane.
- **`eval`** (default `bar`) — `bar` re-evaluates once per closed bar of the selector interval (look-ahead-free "signal on close"); `tick` re-evaluates every daemon tick on the forming bar and acts only when the emitted direction changes. **`cooldown`** is **tick-only** (supplying one in `bar` mode is rejected) and rate-limits entries — exits and reversals are exempt and act immediately; in any non-observe mode a 1m default cooldown applies when unset.

## `metric_band_rule` — a stateful TA hysteresis rule

The hysteresis kind: per-side enter/exit condition trees persisted as a flat/long/short regime; sides are optional, and regimes are per consumer.

Per-side condition trees — `long.enter`/`long.exit` and `short.enter`/`short.exit` — persisted as a `flat`/`long`/`short` regime. From flat, exactly one fired entry enters that side (simultaneous long+short entries stay flat as ambiguous); while positioned, the exit condition is evaluated first. The right shape for RSI bands and Bollinger-style two-threshold systems. Same `eval`/`cooldown`/abstain semantics as `metric_level_rule` — including the perps-only-metric-on-a-spot-venue advisory (§"`metric_level_rule` — a deterministic TA level rule").

**A side is optional.** For a short-only (or long-only) band, OMIT the other side entirely — an omitted side simply never trades that direction. Do NOT fabricate a never-firing guard condition for the unused side; every supplied condition must reference at least one metric operand, so a constant "never" guard is rejected (typed `invalid_signal_input`; §"Errors"). At least one side is required, and a side is always `enter`+`exit` together.

⚠️ **A band signal's regime is per consuming strategy, not shared.** Unlike `metric_level_rule` (a pure function of the current bar), a band signal's emitted view depends on the `flat`/`long`/`short` state — and that state is kept **per strategy that references the signal**, not once on the signal. So a band signal reused by two strategies emits from two independent regimes: while the metric sits inside the dead zone it can return `long` to a strategy that entered earlier and is still holding, and `flat` to a strategy that started flat, **at the same instant**. Each consumer stays internally consistent, but the "one producer, many consumers" reuse promise does **not** give identical views here — a paper twin, a two-consumer comparison, or a backtest replay that starts flat will diverge from a live consumer mid-regime. When you need identical views, author a separate band signal per consumer.

## Cross-market conditions (both metric kinds, bar mode)

Condition operands may read other markets via their own selectors — sampled on the shared clock, with defaults that do not inherit, and a warnings note on create.

A condition operand normally inherits the signal's shared `selector`; it MAY carry its **own** `selector` to read a different market — "BTC/ETH ratio", "conditioned on BTC+SOL, execute on XRP". In **bar mode** (the default) these evaluate live and backtest: the shared `selector` is the **clock** — evaluation fires at each close of its bar, and every foreign operand reads its own **last closed bar as of that instant** (a `DAY` operand inside an `HOUR` rule holds one value across the day; a foreign bar closing after the clock instant is invisible — the same no-look-ahead rule as the home market's forming bar). ⚠️ **An operand selector's omitted `interval`/`quote` default to `HOUR`/`USD` — they do NOT inherit the shared selector's values**; spell them out when the shared clock is not hourly. Freshness is trust-latest (no staleness gate); a foreign series' failed reading abstains-and-holds with the series named in `last_error` **when the verdict depends on it** — a failed reading on a leg the compound decided WITHOUT (a dominant sibling settled it) does not abstain: the strategy acts, and the fault surfaces as a WARN log plus the `last_issue_note` breadcrumb on `strategy_show` (deliberately not `last_error` — the verdict path is healthy). In **tick mode** selector-bearing conditions are deferred — the view abstains — and tick backtests are refused anyway. ⚠️ A `wrun/...` operand whose package pins foreign `symbol`/`exchange` input sources is a cross-market read IN DISGUISE: the tick-mode deferral scans only operand selectors written in the signal spec and cannot see pins inside package metadata, so any signal using a pinned-package WRUN operand must be authored `eval: "bar"` explicitly. Bindable-market WRUN operands (packages with a `binding: "required"` odds input) carry their `sourceBindings` on the operand like `params`; two operands may bind the same package to different markets and are distinct reads. `signal_create_metric`/`signal_edit` return a `warnings[]` note naming the cross-market operands and their sampling rule. A cross-market **level** rule is authored through the `condition` tree on `signal_create_metric` or `signal_edit` (CLI flag limits: §"CLI equivalents"); the band kind's per-side condition trees accept operand selectors directly.

## Required fields, by kind

What `create` will refuse you for. Everything else is optional.

| Kind | Required |
| --- | --- |
| `text_long_short` | `event_watch` + `topic` |
| `metric_level_rule` | the selector's `symbol` (`exchange` only when a venue was named), plus `on_true` and **either** a `condition` tree **or** `left` + `op` + `right` (the flat `metric`/`threshold`/`compare_metric` shorthands are edit and CLI forms) |
| `metric_band_rule` | the selector's `symbol` (`exchange` only when a venue was named), plus at least one full side — `long` and/or `short`, each `enter`+`exit` together (omit a side entirely to never trade that direction) |

The tools are kind-split: `signal_create_text` is always `text_long_short`; `signal_create_metric` requires `kind` (the CLI's `--kind` defaults to `text_long_short`). **`kind` and `slug` are immutable** — `edit` cannot change either; remove and recreate.

## Lifecycle — pausing is not a round trip

The lifecycle verbs — list, show, create, edit, pause, resume, remove — with the removal confirm and the identity guard on edits.

`signal_list` enumerates every signal with its kind and enabled state; `signal_show` prints the full resolved spec plus the strategies that reference it. The create tools author one and `signal_edit` tunes it (subject to the identity guard above). `signal_pause` stops evaluating it, `signal_resume` starts again, and `signal_remove` deletes it (refused while a strategy references it, unless `force` is passed — typed `signal_has_consumers`; §"Errors"). The delete is permanent, so it confirms first — the tool call raises an approval card, the terminal form prompts, and `--yes` is the scripted bypass.

A thesis a strategy's exit wake wants rewritten arrives as a PROPOSAL, not an edit. `signal_propose_thesis` is the agent-only write half of the loop: it records the rewrite against the signal and changes nothing a strategy evaluates, which is why it is an everyday write rather than a card. The operator answers it — `om signal proposals` lists what is waiting (`--all` includes the applied and dismissed), `om signal apply-proposal <id>` runs the edit behind a confirmation (`--yes` scripts it), and `om signal dismiss-proposal <id>` discards it and leaves the signal reading as it does. A strategy set to `--wake-mode autonomous` skips the queue: its woken turn applies the rewrite to its own signal directly.

Several signals = ONE call: `signal_remove` / `signal_pause` / `signal_resume` take `ids` (id-or-slug, resolved slug-first) beside `id_or_slug` (`om signal remove <id> <id>`, `om signal pause <id> <id>`); one card lists every member (a remove names each member's consuming strategies; two ids that address the same signal refuse as `invalid_input`), ids that do not exist are skipped rows, and a batch pause in auto mode prints one receipt block with one `signal_resume` undo. Never loop single-id calls for a set: that raises one card per signal.

## Tool-call hygiene

The omit-optional-fields rule for every create and edit call, and why passing a default is a misreport.

When creating or editing via the `signal_*` tools, **omit optional fields you have no user instruction for** — do not pass a field just to restate its default. The chat surface renders what each call set versus defaulted; explicitly passing defaults misreports them as user choices.

## Quick recipes

Worked tool calls for each kind, plus an identity-guarded edit; args verified against the input schemas.

Event-driven text signal, tuning the context memory off its default:

```json
signal_create_text {"event_watch": "fed-watch", "slug": "fed-cut-view",
  "topic": "LONG = raises the odds of a cut; SHORT = lowers them; repeats of known news are priced in — NEUTRAL",
  "context": {"recent_events": 10}}
```

Deterministic RSI level rule, evaluated on bar close (`on_true`/`on_false` are numeric: +1 bull, -1 bear, 0 neutral; the unset false side stays neutral — one-sided). No venue was named, so `exchange` is omitted: the create stamps the coin's default listing and the result's `listing_note` says which — relay it in words:

```json
signal_create_metric {"kind": "metric_level_rule", "slug": "sig-rsi-oversold",
  "selector": {"symbol": "BTC", "interval": "HOUR"},
  "left": {"metric": "rsi", "params": {"period": 14}}, "op": "lt", "right": {"value": 30},
  "on_true": 1}
```

Short-only hysteresis band (no long side at all — never fabricate one); here the user named the venue, so the selector carries it verbatim:

```json
signal_create_metric {"kind": "metric_band_rule", "slug": "sig-rsi-short-band",
  "selector": {"symbol": "ETHUSDT", "exchange": "BINANCE_FUTURES", "interval": "HOUR"},
  "short": {"enter": {"left": {"metric": "rsi", "params": {"period": 14}}, "op": "gt", "right": {"value": 75}},
            "exit":  {"left": {"metric": "rsi", "params": {"period": 14}}, "op": "lt", "right": {"value": 55}}}}
```

Tune a text signal's memory later: a context-policy edit is an identity change, so the plain edit is REFUSED — relay that refusal, and only after the user's explicit yes:

```json
signal_edit {"id_or_slug": "fed-cut-view", "context": {"recent_events": 10}, "force": true}
```

Verify with `signal_show`; a paused signal keeps its spec and history. For binding a signal to a market, sizing, exits, and run modes, continue in the strategy skill (`skill_read`, name = strategy).

## Errors

Every typed refusal on the signal surface — when each code fires and its recovery — plus the result-side disclosures to relay and the one approval card.

Sections above may *name* a code; this glossary defines them. A result-interpretation fetch lands here.

**Request-level typed codes** (grouped; recovery is what the agent does, then says):

| Code(s) | When it fires | Recovery |
| --- | --- | --- |
| `invalid_signal_input` | `create` rejected a field combination: level-vs-band field mix, missing `on_true`, `condition` tree alongside flat fields, no band side (or a fabricated never-firing guard), `cooldown` off `eval: tick`, context with nothing in it | fix exactly the named fields and re-create; do not guess substitutes |
| `invalid_signal_edit` | conflicting or ambiguous patch (context + clear_context, `condition` + flat fields, threshold + compare, half of an absent band side), or the merged spec fails validation | drop one of the two conflicting shapes and resend |
| `signal_not_found` | no stored signal matches the slug/id | `signal_list`, confirm the slug, retry |
| `invalid_signal_spec` | the stored spec file is corrupt (parse detail in the message) | surface the detail; repairing or removing the file is the operator's step |
| `signal_exists` · `signal_slug_exists` | id/slug collision with an existing signal | pick a different slug, or omit it for a fresh id |
| `signal_unreadable_conflict` | the id's on-disk file exists but is unreadable — create refuses to overwrite | pick a different slug; file surgery is operator work |
| `signal_id_slug_divergence` | explicit id ≠ explicit slug | pass only the slug |
| `event_watch_not_found` · `event_watch_unreadable` · `event_watch_check_failed` | the referenced event-watch is missing / corrupt / could not be verified | point at an existing watch or create it first (the event-watches skill via `skill_read`); `check_failed` means the reference was NOT validated — retry when the store is readable |
| `unknown_provider` | the model pin names an unknown LLM provider | lowercase the provider name, or omit the pin to use the configured default |
| `signal_edit_requires_force` | the edit touches identity (model pin, `topic`, context policy) or a referenced signal (observe-only consumers ride `warnings[]` instead), or consumer specs were unreadable (fail-closed) | relay the stated reasons and ask; the hint names the `force` retry, but consent comes first — retry with `force` only on the user's explicit yes |
| `signal_edit_field_kind_mismatch` · `compound_condition` · `signal_kind_retired` | the field is not editable for the stored kind · flat flags cannot patch a compound tree · a legacy `constant` signal cannot be edited | use the listed editable set · replace the whole `condition` via `signal_edit` · author a replacement metric/text signal and re-point the strategy |
| `signal_edit_empty` | the patch supplies no fields | resend with at least one field |
| `signal_has_consumers` | remove refused: strategies reference the signal (or consumer specs were unreadable — fail-closed) | re-point or remove the consumers first; a forced remove dangles them and the daemon auto-pauses each — only on the user's explicit yes |
| `signal_remove_failed` | the spec resolved but the file changed or vanished mid-remove | `signal_list`, then retry if it is still present |
| `wrun_package_not_installed` · `wrun_package_lock_missing` · `wrun_package_lock_mismatch` · `wrun_package_lock_invalid` · `wrun_params_invalid` | a `wrun/...` operand's package is not installed, its pin no longer matches the installed output, or its params fail the package schema | install the package, or `om wrun upgrade` to re-pin; fix the operand params per the message |
| `invalid_limit` | decisions listing limit outside 1..500 | clamp the limit |

**Result-side disclosures (not errors — relay them):** `warnings[]` on create and edit is the disclosure surface — surface it verbatim (cross-market sampling notes, the perps-only-metric-on-a-spot-venue abstains-forever note, the event-watch repoint freshness floor, cooldown add/drop notes, band-regime reset notes). `identity_changed` / `rule_or_selector_changed` on edit disclose a replay-comparability break. `referencing_strategies` (show/edit/pause/resume) names the consumers; `cascade_note` + `unreadable_consumers` on pause/resume — a non-zero unreadable count means the cascade list is incomplete. `signal_list` returns `unreadable`/`skipped` rows rather than hiding broken specs. Decisions: `truncated` on list; `removed` on purge — each purged row recomputes at one paid LLM call.

**Approval card:** `signal_remove` raises the card (the delete is permanent). A declined card is the user's no — never retry it or route around it.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `signal_create_metric`
  - `selector.exchange` — Omit the field and the coin's default listing is used and disclosed on the result; a named venue is never rewritten.
  - `condition` — Metric operands inherit the signal's shared selector by default; an operand MAY carry its own selector to read a DIFFERENT market (cross-market condition).
  - `on_false` — Direction otherwise (metric_level_rule); default 0 neutral.
  - `eval` — Evaluation cadence for metric signal kinds: bar (once per bar, default) | tick (every daemon tick, act on direction/regime change).
  - `long` — Omit the side entirely for a short-only band (never fabricate a can't-fire guard); at least one side is required.
  - `short` — Omit the side entirely for a long-only band; at least one side is required.
- `signal_create_metric` · `signal_edit`
  - `selector.displayName` — Cosmetic only: the fetch is by `symbol`, and an absent label falls back to it.
- `signal_create_text`
  - `context` — Absent ⇒ the CREATE DEFAULT applies ({overview:true, recent_events:5}); pass no_context:true to opt out into isolation.
  - `context.overview` — default true — Feed the event-watch's synthesized overview.md as context (default on).
  - `context.recent_events` — default 5 — How many recent accepted events to feed as memory (0..20, default 5; 0 = overview only).
  - `no_context` — Opt out of the default prior-context memory: the classifier judges each event in isolation.
- `signal_decisions_list`
  - `limit` — Maximum rows returned (default 50, newest first).
- `signal_edit`
  - `context` — Merges onto the current policy (or defaults if off).
  - `condition` — Metric operands inherit the signal's shared selector — omitted interval/quote on an operand selector default to HOUR/USD
  - `threshold` — `delta_pct` is percent points (2 means a 2% move, NOT 0.02) — price-class metrics are in the selector's quote currency, USD by default

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `signal_create_metric`
  - discloses `enabled`
  - discloses `listing_note` — Present only when the create chose the venue: no `selector.exchange` was named, so the coin's default listing was resolved, stamped on the saved spec, and is named here in words with its venue symbol. Absent when the caller named the venue.
  - discloses `interval_note` — Present only when no `selector.interval` was named: the rule reads hourly bars by default, and this says so in words.
  - discloses `warnings[]` — Advisory notes about the signal just created. SURFACE THESE TO THE USER. Possible notes: an operand reading a perpetuals-only series (funding rate, open interest) on a SPOT venue, which the alert lane refuses outright and this lane saves — it abstains forever until repointed; a cross-market condition naming which operands read a different market series than the shared selector and how they are sampled (bar mode: each at the shared selector's evaluation clock); or a tick-mode selector-bearing condition that will abstain until eval is set to bar or the operand selectors are removed.
  - on `missing_api_key` — An omitted venue is resolved against the market catalog, which needs the OpenMarket data key: route the user to `om login`, or name `selector.exchange` — a named venue needs no catalog read.
  - on `venue_unresolved` — No default listing could be chosen: relay the venues the message names and ask which one (when it names none, ask the user which venue; when it says the catalog could not be read, the fix is a retry or `om login`, not a venue) — never pick a venue yourself, never swap the coin for another.
- `signal_create_text`
  - discloses `enabled`
  - discloses `warnings[]` — Advisory notes about the signal just created. SURFACE THESE TO THE USER. Possible notes: an operand reading a perpetuals-only series (funding rate, open interest) on a SPOT venue, which the alert lane refuses outright and this lane saves — it abstains forever until repointed; a cross-market condition naming which operands read a different market series than the shared selector and how they are sampled (bar mode: each at the shared selector's evaluation clock); or a tick-mode selector-bearing condition that will abstain until eval is set to bar or the operand selectors are removed.

<!-- AUTO: END RESULT CONTRACT -->

## CLI equivalents

Every `om signal` command form for shell users — flag spellings, CLI-only limits, and the generated command↔action mapping.

The shell lane has no eval coverage; these forms are review-verified.

```bash
# Event-driven text signal, context-aware
om signal create --kind text_long_short --event-watch fed-watch \
  --topic "LONG = raises the odds of a cut; SHORT = lowers them; repeats of known news are priced in — NEUTRAL" \
  --context --context-recent-events 10 --slug fed-cut-view

# Deterministic RSI level rule, evaluated on bar close (no --exchange: the default listing is stamped and disclosed)
om signal create --kind metric_level_rule --symbol BTC --interval HOUR \
  --metric rsi --period 14 --op lt --threshold 30 --on-true bull --slug sig-rsi-oversold

# Short-only hysteresis band: enter short at RSI>75, cover at RSI<55
om signal create --kind metric_band_rule --symbol ETHUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --short-enter '{"left":{"metric":"rsi","params":{"period":14}},"op":"gt","right":{"value":75}}' \
  --short-exit  '{"left":{"metric":"rsi","params":{"period":14}},"op":"lt","right":{"value":55}}' \
  --slug sig-rsi-short-band

# Identity-guarded edit (plain form refused; --force after the user's yes)
om signal edit fed-cut-view --context-recent-events 10 --force
```

CLI-only limits and spellings: the `--metric` flag accepts only `price`, `delta_pct`, `delta_abs`, `volume`, `funding_rate`, `open_interest`, `rsi`, `sma`, `ema`, `atr` (plus installed `wrun/...` ids) — `macd`, `bb_*` and `stoch_*` are rejected from the CLI and go through the action's `params` object. There is no `--condition` JSON flag on create, so a cross-market or compound LEVEL rule is action-only (the `signal_edit` action's `condition` field can replace one later — also action-only); the band kind's `--long-enter`/`--long-exit`/`--short-enter`/`--short-exit` JSON flags accept operand selectors directly. Context flags: `--context`, `--context-recent-events <0..20>`, `--no-context-overview`, `--no-context`, `--clear-context` (edit). `--force` is the `force` field; `--yes` scripts the removal confirm. The proposal verbs are shell-only: `om signal proposals` (`--all`), `om signal apply-proposal <id>` (`--yes` scripts its confirm) and `om signal dismiss-proposal <id>`.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

- `om signal` — (bespoke; see narrative above)
- `om signal apply-proposal` — (bespoke; see narrative above)
- `om signal create` (action: `signal_create_text`) — Create a text_long_short signal: an LLM classifier over an event-watch's occurrences
- `om signal create` (action: `signal_create_metric`) — Create a deterministic metric rule signal (metric_level_rule or metric_band_rule)
- `om signal decisions` — (bespoke; see narrative above)
- `om signal decisions list` (action: `signal_decisions_list`) — Inspect the durable text_long_short decision cache: the pinned classifier verdicts, newest first.
- `om signal decisions purge` (action: `signal_decisions_purge`) — Permanently invalidate pinned decision-cache verdicts (filter by signal slug, event id, or spec fingerprint; no filter purges the whole cache).
- `om signal dismiss-proposal` — (bespoke; see narrative above)
- `om signal edit` (action: `signal_edit`) — Patch tunable fields of an `om signal` by id or slug.
- `om signal list` (action: `signal_list`) — List configured `om signal` directional producers (the persisted SignalSpecs).
- `om signal pause` (action: `signal_pause`) — Disable `om signal` producers by id or slug (`id_or_slug` for one, `ids` for several in ONE call; one approval card covers the set).
- `om signal proposals` — (bespoke; see narrative above)
- `om signal remove` (action: `signal_remove`) — Remove `om signal` producers by id or slug: `id_or_slug` for one, or `ids` for several in ONE call (one approval card covers the set; never a loop of single calls).
- `om signal resume` (action: `signal_resume`) — Re-enable paused `om signal` producers by id or slug (`id_or_slug` for one, `ids` for several in ONE call; one approval card covers the set).
- `om signal show` (action: `signal_show`) — Show one `om signal` producer spec by id or slug, plus the strategies that reference it (its downstream consumers).

<!-- AUTO: END COMMAND REFERENCE -->
