---
name: openmarket-strategy
description: How a view or a rule becomes positions over time, on any market the platform serves. The menu of styles a person names (notify, one order on a fire, a standing position, a position re-targeted on every view, accumulate and exit above cost, a regime with a flat state, an Indicator strategy package), each mapped to its door and its backtest form; the sizer modes and their defaults, the setups that never exit, capital as equity, how flips and managed exits execute, what a pause leaves, and what a backtest owes. Read before opening the watch or the indicators skill for any ask that names a style, in trading or investing words.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om strategy

How a view or a rule becomes positions over time, on any market the platform serves. There are several ways to turn a view into positions; this page picks one, and the mechanics stay in the file that owns them.

### Guardrails

- A rule over stock indicators is a condition or a strategy, never a new Indicator: a level, a crossing or a band over `ema`, `rsi`, `macd` and the rest is a condition source (`watch.md §"Condition source"`). Reach for `wrun_author` only on the menu's "Anything else" row, after `package_search` (`marketplace.md §"Rules"`).
- The consent flags (`allow_same_market`, `allow_unverified_cohort`, `allow_existing_position`) are the user's yes, supplied by the arm card or the terminal flags, never by you; the runtime strips a model-passed value.
- `paper` is the arm's default; `dry_run` and `live` are reached only by an explicit mode on the arm card at the installing machine's terminal (`watch.md §"Arming"`). Never pick one on your own.
- Capital is the user's number, typed on the arm card; the recipe carries hints only (`watch.md §"Money step"`).
- A backtest result names its window and its in-market share beside the return, never the return alone (§"What a backtest owes").

### Routing

Pick the style first, then its door. One row per style a person names, in trading or investing words:

| Style the person names | Door | Backtest form |
| --- | --- | --- |
| "tell me when" (notify, no money) | a condition source with delivery and no money step (`watch.md §"Condition source"`) | none: a backtest replays a strategy, and a notification is not one |
| One order on a fire ("buy $50 when BTC crosses 95k", once or a few times) | a money step in `order` mode, `max_fires` the count (`watch.md §"Money step"`) | none as an order step; replay the rule as a level candidate when the person wants a read (`research.md §"Candidates and promotion"`) |
| A standing position on a view ("long while RSI is under 30", "trade my classifier's calls", "flip on the death cross") | a strategy money step reading the watch's own condition level (`on_true` / `on_false`) or a verdict step; sizer mode `conviction`, `always_in` or `single_sided` (`watch.md §"Strategy mode"`, §"Sizer modes") | candidate `source` with `on_true` / `on_false`, or `watch` with the ai verdict step |
| A position re-targeted on every view ("rebalance to my signal", "hold 20% while it says so", a target allocation) | the same strategy step; the target sizer is the default kind (one position re-sized on every view), shaped by `scale`, `sides` and a `fraction_of_wallet` capital (§"Capital and leverage") | a candidate with `sizer.kind` absent, which reads as `target` |
| Accumulate and exit above cost ("buy $10 every dip, sell everything 5% above my average", DCA, average in) | a `backtest_spec` candidate with `sizer.kind: "accumulate"` (`cash_per_entry`, `max_lots`), the dip as its condition `source` with `on_true: long`, the exit as `exit.bracket.tp`; it does not promote to a watch yet (`research.md §"Candidates and promotion"`) | the same candidate, replayed on the engine's broker |
| A regime with a flat state ("long above the 50 EMA, short below, flat in between", "in the trend or out") | a band condition `{long: {enter, exit}, short: {enter, exit}}` beside a strategy step whose sizer can flatten (`watch.md §"Condition source"`, §"Regime or trigger") | candidate `source` carrying the band, with no `on_true` / `on_false` |
| Anything else (order builders, per-fill logic, a rule no condition expresses) | `package_search` first; then an Indicator strategy package, a package that trades (`indicators.md §"A package that trades"`, the authoring pages under `docs/indicators/strategies/`) | `wrun_strategy: "@scope/name"` on `backtest_run` or `backtest_spec`, `params` by declared name |
| "do it now" | `order_place` / `order_place_polymarket` (`orders.md §"Place an order"`) | none |

When the words leave regime and trigger open: §"Regime or trigger". The stance and what a neutral or opposing view does under it: §"Sizer modes"; the setups that never exit: §"Hazards"; one view sequence through every stance: §"Five stances"; the base and how leverage scales it: §"Capital and leverage"; how a flip and a managed exit execute: §"Flips and exits"; what a pause leaves: §"Pause and the held position"; the disclosures: §"What a backtest owes"; where each lane's mechanics live: §"Where each lane lives".

## Regime or trigger

Classify by what the condition describes, a state to hold a position through or a moment to act on; read when the words leave it open.

A REGIME is a state the person wants to be positioned through: "while RSI is under 30", "above the 50 EMA", "when the classifier says bullish". It is a standing position: a strategy step reads the level or the verdict, enters when the state begins and exits (or flips) when it ends. Recurring phrasing ("every time", "whenever") does not make it a trigger; a stance exits and re-enters each episode. Two states with a gap between them ("long above, short below, flat in the middle") is the band.

A TRIGGER is a moment: "when BTC crosses 95k, buy $50". One order per fire, a cap on fires, no rule-driven exit: the `order` mode. Repeated one-sided adds with an exit above cost ("buy $10 each dip, sell all 5% above my average") are neither: that is the `accumulate` sizer kind, one lot per dip episode, every lot closed together at the take-profit over the average entry.

"Act now" with no condition is the orders skill. A genuinely open ask, one the words fit as a regime and as a trigger alike, gets ONE structured question naming both readings; never a question about size, which the arm card asks. Exits are the step's own `exit` terms, and a step saved without one says so in the outcome line.

## Sizer modes

The three stances, what a neutral or opposing view does under each, and the policies that fit each producer; read before choosing or explaining a sizer.

A mode decides transitions, what a neutral or an opposing view does to what is held; `scale` decides size.

| Mode | Neutral view | Opposing view |
| --- | --- | --- |
| `always_in` | holds; never goes flat | flips, no threshold (`flip_threshold` there is refused) |
| `conviction` | `on_neutral: flatten` closes to cash; `hold` keeps the position | `on_reversal: flip` crosses when the view's confidence clears `flip_threshold` (default 0.7) and closes to flat below it; `close_only` always closes to flat, and the other side is entered only by a fresh opposing view while flat |
| `single_sided` (`side: long` or `short`) | as `conviction` | flattens; the other side is never entered |

State `on_neutral` and `on_reversal` yourself on every producer: the watch doors stamp nothing, and an omitted policy reads as `flatten` and `flip` at run time whatever the producer. What fits each producer:

| Producer | `on_neutral` | `on_reversal` | Why |
| --- | --- | --- | --- |
| an ai verdict step | `hold` | `close_only` | noisy: its neutral is no information, and one misread headline must not cross zero |
| a condition level | `flatten` | `flip` | deterministic: its neutral IS the exit instruction |

A `metric_rule` verdict rides the verdict lane but is deterministic, so it takes the level row; leave `min_confidence` unset behind one, since its no-match flat carries confidence 0 and any floor swallows that exit. `flip_threshold` is accepted only beside an explicit `on_reversal: flip` on `conviction`; alone, or with `close_only`, it is refused.

`scale: conviction` sizes by the view's confidence; a level reader carries confidence 1, so it does nothing there. `min_confidence` is the acting floor on every mode. `sides` multiplies the base per side (`{long: 1, short: 0.5}`; a missing side is 1).

## Hazards

The setups that never exit and the band's refusals; read before saving a step that holds through neutral or carries no managed exit.

- `on_neutral: hold` (or `always_in`) behind a producer that can never emit the opposing side has NO autonomous exit: a neutral does not close the position and the opposing view never arrives. A level mapped `on_true: long` with `on_false` absent is exactly that producer. No door warns about it: say so yourself before saving, and name the fix: attach `exit.bracket` (`tp`, `sl`) or a `time_stop`, or use `on_neutral: flatten` so the neutral closes.
- `always_in` behind a one-sided producer enters once and can neither flatten nor flip; say the same. Give the producer both sides (`on_false: short`), pick a sizer that can flatten, or attach an exit.
- A band beside `always_in`, or beside `on_neutral: hold`, is refused: the band fires its exit BY emitting neutral (the regime returns to flat), so `hold` would make its `exit` conditions dead. Leave `on_neutral` at `flatten` behind a band.
- `on_reversal` is inert behind a band: a band returns to flat before it enters the other side, so the sizer never sees an opposing view on a held position. The policy is never consulted.

## Five stances

One view sequence through every stance, as the sizer computes it; read to predict what a saved step does on its next view.

Setup: `scale: fixed`, a fixed capital of 1000, no `min_confidence`, the default flip threshold 0.7. Every stance starts flat. Numbers are the target weight (+1.0 fully long the base, 0 cash). Views in order: 1) long 0.9 · 2) neutral · 3) short 0.5 · 4) short 0.9 · 5) long 0.8. Only an ai verdict varies its confidence; a level carries 1, so a level reader never produces the sub-threshold reversal at view 3.

```
always_in
 flat → long 0.9  → +1.0  enter long
 +1.0 → neutral   → +1.0  hold: a neutral view never exits
 +1.0 → short 0.5 → -1.0  flip: no threshold is consulted
 -1.0 → short 0.9 → -1.0  hold (same side)
 -1.0 → long 0.8  → +1.0  flip

conviction on_neutral=hold on_reversal=close_only        (the fit for an ai verdict)
 flat → long 0.9  → +1.0  enter long
 +1.0 → neutral   → +1.0  hold: a classifier's neutral is no information
 +1.0 → short 0.5 →  0    close to cash: close_only never crosses in one step
  0   → short 0.9 → -1.0  enter short: a FRESH opposing view arriving while flat
                          (close_only blocks a one-step flip, not a two-step reversal)
 -1.0 → long 0.8  →  0    close to cash

conviction on_neutral=flatten on_reversal=flip           (the fit for a level; what an omitted policy reads as)
 flat → long 0.9  → +1.0  enter long
 +1.0 → neutral   →  0    close: a rule's neutral IS its exit instruction
  0   → short 0.5 → -1.0  enter short: an entry from flat, not a flip
 -1.0 → short 0.9 → -1.0  hold
 -1.0 → long 0.8  → +1.0  flip: opposing, and 0.8 clears the 0.7 threshold
                          (at 0.5 it would close to 0 instead)

single_sided side=long on_neutral=hold                   (the fit for an ai verdict)
 flat → long 0.9  → +1.0  enter long
 +1.0 → neutral   → +1.0  hold: an irrelevant headline does not close the position
 +1.0 → short 0.5 →  0    close to cash: the opposing view still flattens
  0   → short 0.9 →  0    and it never shorts
  0   → long 0.8  → +1.0  re-enter long

single_sided side=long on_neutral=flatten                (the fit for a level)
 flat → long 0.9  → +1.0  enter long
 +1.0 → neutral   →  0    close: a rule's neutral IS its exit instruction
  0   → short 0.5 →  0    stays flat, never shorts
  0   → short 0.9 →  0    stays flat
  0   → long 0.8  → +1.0  re-enter long
```

Three rules the walk rests on: `flip_threshold` gates a flip out of a held position and never an entry from flat; `close_only` blocks a one-step flip, not a reversal (on the verdict lane every accepted row is fresh, so re-entry is immediate; on the condition lane a persisting level is one view until it moves); `on_neutral: hold` governs neutral views only and never stops an opposing view from acting.

## Capital and leverage

The capital base, the equity that bounds it, and how leverage and the side multipliers scale a leg; read before explaining a size or a "how much will it trade".

The `capital` box is typed at the arm: `{source: "fixed", amount}` resolves to min(amount, available); `wallet` is the whole available; `{source: "fraction_of_wallet", fraction}` a share of it. `available` is EQUITY, not free cash: free cash plus the held position's equity contribution (its posted margin on a leveraged perp, its notional on fully paid shares). So a `fixed` base shrinks below its amount only on a real mark-to-market loss, never because cash was deployed. Non-positive equity while a position is held is a fail-closed no-op: the position stays held, the sizer cannot steer it, and the step's note says so.

A leg is capital base x side multiplier x leverage x confidence, capped by `caps.max_size`; the executor places the delta between that target and the current holding, in base-asset units, and an unpriceable mark is a no-op, never a flatten. `leverage` is 1 to 100 on perps only and 1 when omitted; above 1 it is refused on Polymarket, on a `market_data` pin and on a step with no market pinned. Under leverage the base is margin committed and the notional is base x leverage. A watch-strategy replay models no margin and no liquidation, and refuses leverage above 1 outright (`research.md §"Warnings and limits"`); an Indicator strategy package replays on the engine's broker instead: a package whose sheet declares `instrument: "perps"` gets its declared leverage, isolated margin and liquidation modelled, with a liquidation reported in `warnings`; a spot package, the default, ignores `leverage` and is never liquidated.

## Flips and exits

How a flip executes per venue, the taker order every leg is, and the managed exits the daemon enforces; read before promising what a reversal or a stop will do.

Every strategy order is a marketable taker order (Polymarket fill-and-kill, Hyperliquid market IOC): it crosses the spread, cancels any remainder, and never rests on the venue. A resting order is the orders skill's.

On Polymarket a flip is two legs: SELL the held outcome to flat, then BUY the target outcome, and the BUY is routed only once the SELL fills. An unconfirmed SELL parks the step pending settlement; a SELL that placed nothing leaves the OLD side held, still exposed to the view it just reversed against, and the next pass plans again from what is held. On Hyperliquid a flip is one signed order that crosses zero, so that gap does not exist there.

Managed exits are `exit.bracket` (`tp`, `sl` as P&L fractions, or `tp_price` / `sl_price`) and a `time_stop`, enforced by the daemon while the chain is armed; live Hyperliquid also rests native bracket children. A close-only leg of a position the chain opened still dispatches after the chain stood down. `wake.mode` says what an exit-wake turn may do (`propose` records a thesis rewrite, `autonomous` is standing authority to apply it), but the watch doors carry no switch that turns the wake on, so no such turn runs from a watch strategy step today (`watch.md §"Strategy mode"`).

## Pause and the held position

What pausing the watch that carries the step, pausing its source watch and an edit each leave managed; read before pausing or editing a watch that holds money.

Pausing the watch that carries the strategy step (`watch_pause`) is the operator's stop, exits included: the software tp, sl and time stop end with it; on live Hyperliquid, already-resting native bracket children keep enforcing venue-side, and everything else stops. The verb answers `held_position` naming the holding, the resting bracket ids and a venue-aware note: relay it verbatim. A resume that leaves the step off with no marker owes the same disclosure. The daemon's own auto-pause keeps its managed exits running, so nothing is unmanaged and nothing is reported.

Pausing the SOURCE watch auto-pauses a strategy step on another watch reading its verdict rows, at that step's next tick (`signal_disabled`): entries stop and managed exits stay enforced. Resuming the source does not bring the step back: only arming its chain again does (`om watch arm <watch> <chain>` at the terminal, which resumes the source with it); `watch_resume` on the step's own watch arms nothing, and a pause then resume of that watch ends the managed exits instead. An edit to any step, box, pin or delivery stands its chain down until it is armed again, and a close-only leg of a position the chain opened still dispatches (`watch.md §"Arming"`).

## What a backtest owes

The disclosures a replay result carries beside its return; read before presenting one.

- The window. `window` is capped at 365 days ending at `until` (default now); with nothing asked, a run looks back a year on HOUR and coarser bars, a month on finer ones and 90 days on an event-anchored run (the verdict-step form). Beyond what the data plan serves, `backtest_run` narrows to what it serves and `backtest_spec` refuses. Say what was replayed.
- The interval, and why: a condition candidate folds on its primary operand's own cadence.
- The in-market share: `time_in_market_pct` (a fraction) beside the trade count. About two bars per trade is a sign the rule encoded a trigger, not a regime, whatever the return says.
- No short margin on a watch-strategy replay: adverse shorts ride to the window edge un-liquidated (`short_margin_unmodeled` in `warnings`); a perps package replay models liquidation and warns when one fired, and a spot package has no margin or liquidation model.
- The buy-and-hold benchmark and the one honesty note that changes the reading (`research.md §"Reach for backtest_run FIRST"`), never the raw number alone.

## Where each lane lives

One pointer per lane to the file that owns its mechanics; read to know which skill to open next.

- A condition source and its band form, delivery, the money step's six modes and the strategy mode's fields: `watch.md §"Condition source"`, `watch.md §"Money step"`, `watch.md §"Strategy mode"`; arming and the terminal flags: `watch.md §"Arming"`.
- An ai verdict step's prompt and output: the watch-prompts skill.
- A candidate's decision inputs, the sizer kinds and promotion to a watch, the one-shot replay and the sweeps: `research.md §"Candidates and promotion"`, `research.md §"Reach for backtest_run FIRST"`, `research.md §"Sweeps"`.
- An Indicator strategy package: `indicators.md §"A package that trades"` for the door and the build, `docs/indicators/strategies/` for the order builders and position getters, `package_search` and the try-before-install arc in `marketplace.md §"Rules"`.
- Acting now: `orders.md §"Place an order"`.
