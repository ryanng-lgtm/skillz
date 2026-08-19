---
name: openmarket-strategy
description: Author and operate daemon-native, signal-driven trading strategies — wire a signal (via `om signal`) to a pinned market with a sizer through `om strategy create`, arm it with `om strategy resume`, and let the daemon evaluate it each tick (observe / paper / dry_run / live). Venue- and signal-agnostic by design. Use this skill when the user wants automated signal-driven trading, asks how a strategy runs, or asks why one is not trading. The agent authors the specs but cannot set secrets or start the daemon — if the data feed, signal credentials, execution wallet, or daemon are not ready, route the user to the relevant `om setup` / `om config` / `om service install` and say so.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om strategy

A strategy turns a signal into orders along one spine: a signal emits a `{direction, conviction}` view → a programmatic sizer → an execution venue. The sizer and strategy consume **any** signal and target the venue through the same seams, so new signal kinds and new venues slot in without changing this workflow. Today the signal kinds are `text_long_short` (an LLM over an event-watch), `metric_level_rule` (a deterministic TA level rule), and `metric_band_rule` (a deterministic TA hysteresis rule), and the executors are the Polymarket CLOB and Hyperliquid; more of each are arriving.

Strategies are **daemon-native**. You author durable specs (a signal and a strategy — and, for an event-driven signal, an event-watch), arm them, and the running daemon evaluates every enabled strategy each tick. There is no foreground run command — execution happens only inside `om run` / `om service`. The rungs: `observe` (walletless, never trades), `paper` (walletless simulated account — a persistent book the fills mutate), `dry_run` (reads the real wallet, simulates), `live` (routes through the venue's capped execution path).

## When to use this skill vs `openmarket-alerts`

| User intent | Which skill |
| --- | --- |
| *"Trade a market continuously off a recurring signal (news, a metric, …)"* | **this skill** — a signal-driven strategy |
| *"Take a directional view from a text/news classifier and manage the position"* | **this skill** — a `text_long_short` signal + strategy |
| *"Go LONG when RSI is oversold / on a golden cross (a deterministic TA rule)"* | **this skill** — a `metric_level_rule` or `metric_band_rule` signal + strategy |
| *"Notify me when BTC RSI < 30"* | **alerts skill** — notification-only alert |
| *"Buy BTC when it crosses 95k (once)"* | **alerts skill** — alert with `on_fire.execute` |
| *"Buy $50 of this market right now"* | **orders skill** — one-shot `om order place` |

Rule of thumb: a **standing, signal-driven position** managed over time → this skill. A **one-shot condition→notify/execute** → the alerts skill. **Act now** → the orders skill.

## Discovery: prerequisites

ALWAYS run this first. The agent can author the specs but **cannot** set secrets or start the daemon — surface what is missing and route the user:

```bash
om status --format json
```

Check, and if absent stop and tell the user the exact command to run:

| Prerequisite | Needed for | If missing, the user runs |
| --- | --- | --- |
| Data-feed vendor (registered via event-watch) | an event-driven signal to ingest events | the relevant `om setup` for the vendor (see `openmarket-event-watches`) |
| Signal credentials (LLM, for a text/classifier signal) | classifying a `text_long_short` signal | `om config set-key` / `om config set-model` |
| OpenMarket data API key | a metric signal (`metric_level_rule` / `metric_band_rule`) to fetch its metrics (`getPoints`) | `om login` (or `om init`) — the same key `om metric get` uses; no wallet |
| Execution wallet for the venue | `--run-mode dry_run` or `live` (not `observe`) | `om setup` for the venue (`om setup hyperliquid` / `om setup polymarket`) |
| Daemon running (as a **service**) | anything to actually evaluate/execute | `om service install` then `om service start` |

`observe` mode needs no wallet, and metric signals need only the OpenMarket data API (no event-watch, no LLM, no wallet for observe). Prefer the **service** over a foreground `om run`: only the service writes `runner.log`, which is what `om logs` reads back — a foreground daemon's output is not readable.

## Discovery: what already exists

Before creating, list what is configured to avoid duplicate-slug errors and to reuse specs:

```bash
om strategy list
om signal list
om event-watch list
```

## The strategy shape

A strategy (`om strategy create`) binds a **referenced** `om signal` + an **optional pinned market** + a sizer (mode + capital) + a managed exit policy (TP/SL as PnL fractions + a time stop, enforced by the daemon watcher **while the strategy is enabled** — Polymarket in software, live Hyperliquid via native brackets plus the software time stop). **A paused strategy is fully hands-off: the daemon places NO orders, so managed exits are NOT enforced while paused** (on live Hyperliquid, already-resting native brackets keep enforcing venue-side; the software time stop and every Polymarket/paper exit stop). The market pins via `--condition-id` + `--long-outcome` (Polymarket) or `--coin` (Hyperliquid); the binding is venue-agnostic by design, so additional venues attach at the same seam.

⚠️ **`--long-outcome` is an axis, not a bet.** It names the outcome the strategy BUYS on a LONG verdict; a SHORT verdict buys the *other* outcome of the binary. The signal already defines what LONG/SHORT mean (a text signal's `--topic`; a metric rule's side mapping), so encode the inversion in **one** of the two, never both: "buy No when X happens" is either `--long-outcome No` + a topic that classifies X as **LONG**, or `--long-outcome Yes` + a topic that classifies X as **SHORT**. Encoding the inversion twice — `--long-outcome No` *and* a SHORT-on-X topic — cancels out and buys **Yes**.

**Unpinned = research-only, and it is the DEFAULT.** A strategy created without a market is a research object: backtestable against any data asset the plan serves (including series with no execution venue at all, e.g. US equities), listable, editable — and never evaluated by the daemon. The lifecycle is: create unpinned → backtest freely → when the user wants it to RUN, pin a market (`strategy_edit` with `market`; pin-once) → arm. Any explicit run-mode on an unpinned strategy fails typed (`strategy_unpinned`) with that exact recovery in the hint.

## Signal kinds (text_long_short, metric_level_rule, metric_band_rule)

A signal (`om signal create`) is a pure producer of a `{direction, conviction}` view and never trades. Full authoring detail per kind lives in the signal skill (`skill_read signal`, section = the kind name). Current kinds:

- `text_long_short` — an LLM reading the latest accepted event of an event-watch. `--topic` defines what LONG/SHORT mean **and** — when context is on — how prior context should inform the decision. **Prior context (ON by default for newly created signals: `{overview: true, recent_events: 5}`)**: with context, prior "memory" (the event-watch's `overview.md` plus a bounded list of recent accepted events) is fed as **untrusted reference**; without it the classifier judges the latest event in **isolation**. Opt out at create with `--no-context`, or later with `om signal edit --clear-context`; signals created before the default stay as they are. The classifier does **not** assume how to use that context (it is neutral framing): **you** direct it in your `--topic` — e.g. "treat a repeat of something already in the overview as already-priced (flat)", "weight escalation over the prior narrative", "go the other way on a reversal". Without such guidance the model uses its own judgment; the topic stays the sole definition of long/short/flat and context can never override it. `--context-recent-events <0..20>` sets how many recent events (default 5, counted since the overview watermark); `--no-context-overview` feeds only recent events (skip `overview.md`). When context is on but the watch has no **synthesized overview** yet (still warming up — the check is the event-watch's stored overview snapshot), it logs a notice and classifies in isolation for that tick (recent events are still supplied). **Enabling/tuning/clearing context — or editing the `--topic` — changes the signal's `producer_id`** (an identity change; see edit notes below).
- `metric_level_rule` — a deterministic TA rule (no LLM, no event-watch): a metric condition over the shared market selector (operands may read OTHER markets via their own selectors — see the cross-market paragraph below) → a side at conviction 1.0. CLI flags create the common single comparison `left <op> right`: `left` is a metric (`--metric` + `--period`); `right` is either a constant (`--threshold` — metric-vs-value, e.g. an RSI band) or a second metric (`--compare-metric` + `--compare-period` — metric-vs-metric, e.g. a golden cross). The `signal_create` action can also author an explicit `condition` tree with `{all:[...]}`, `{any:[...]}`, `{not:{...}}`, and arithmetic value expressions. `--on-true` / `--on-false` map the condition truth to a direction. Reuses the `om metric get` registry; reads the OpenMarket data API (no wallet for observe). **Evaluation cadence — `--eval` (default `bar`):** `bar` re-evaluates once per bar of the selector interval, on the **last closed bar** (deterministic, look-ahead-free — the textbook "signal on close" convention); `tick` re-evaluates every daemon tick on the live forming bar and **acts only when the emitted direction changes** (the position-aware sizer prevents double entry), optionally rate-limited by `--cooldown <dur>` (e.g. `15m`, `1h` — gates **entries only**; exits/reversals are exempt and act immediately for loss-control; inert in `bar` mode). In any non-observe mode (`paper`/`dry_run`/`live`) a **`1m` default cooldown applies when `--cooldown` is omitted** (so a tick strategy can't hammer the venue or the public data feed on entries; `observe` has no floor). Use `tick` for prompt, change-driven entries; `bar` for stable once-per-bar evaluation.
- `metric_band_rule` — a deterministic TA hysteresis rule (no LLM, no event-watch): per-side metric condition trees over the shared selector (cross-market operands supported — see below), `long.enter`/`long.exit` and `short.enter`/`short.exit`, persisted as a market-data regime (`flat`/`long`/`short`). **A side is optional: omit `long` or `short` entirely for a one-sided band (the omitted side never trades — do NOT fabricate a never-firing guard, which is rejected); at least one side is required, and a side is always enter+exit together.** From flat, exactly one fired entry enters that side; simultaneous long+short entries stay flat as ambiguous. While long or short, the exit condition is evaluated first, and exit moves to flat before any later opposite-side entry. This is the right shape for RSI bands and Bollinger-style two-threshold systems. Current CLI authoring uses JSON condition flags (`--long-enter`, `--long-exit`, `--short-enter`, `--short-exit`), or use the `signal_create` action for structured input. `--eval bar` evaluates once per closed bar; `--eval tick` evaluates every daemon tick on the forming bar and acts only when the persisted regime changes, with the same entry-only `--cooldown` semantics as `metric_level_rule`.

**Per-operand selectors (metric kinds) — cross-market conditions, bar mode only.** A metric operand normally inherits the signal's one shared `selector`; an operand MAY name its own `selector` to read a DIFFERENT market (a cross-market comparison like BTC price vs ETH price, or "conditioned on BTC+SOL, execute on XRP"). In **bar mode** (the default) these evaluate live and backtest: the shared `selector` is the CLOCK — evaluation fires at each close of its bar, and every foreign operand reads its OWN last closed bar as of that instant (a 1d operand inside a 1h rule holds one value across the day; a foreign bar closing after the clock instant is invisible — the same look-ahead rule as the home market's forming bar). An operand selector's omitted `interval`/`quote` default to HOUR/USD — they do NOT inherit the shared selector's values. Freshness is trust-latest: no staleness gate; a market's fetch failure surfaces exactly like today's single-market failures (a failed row abstains-and-holds with the market named in `last_error`; a whole-fetch failure is a tick error with cooldown backoff). In **tick mode** selector-bearing conditions stay deferred: the view abstains ("per-operand selectors are not evaluated in tick mode") and backtests of tick specs are refused anyway. `om signal create`/`edit` return a `warnings[]` note naming the cross-market operands and their sampling rule.

More signal kinds — and composite/hybrid fusion across signals — are arriving; any signal feeds the same sizer through `{direction, conviction}`, so the strategy workflow is unchanged.

### Run modes (`--run-mode`)

| Mode | Wallet | Behavior |
| --- | --- | --- |
| `observe` | none | Public market reads only, assumes flat, never places. The safe default. |
| `dry_run` | required | Reads the paired wallet's real capital + position and reports the order as SIMULATED — a per-tick mirror of what live would do. Never places, persists no position state of its own. (`dry-run` is accepted as an input alias.) |
| `paper` | none | A walletless simulated account: a persistent per-strategy book (default $10k seed; `--paper-cash` at create) that simulated fills mutate and the next tick reads — flips close the paper position, capital compounds, TP/SL/time-stop fire against the book at live marks, and a per-fill taker fee is debited (HL ~4.5 bps; PM 0; `--paper-fee-bps`, editable). Answers "would this strategy make money?". `om strategy show` renders the book; `om strategy paper reset [--cash <n>]` is the ONE destroyer of a paper P&L record (confirm-gated; refuses over standing stranded/close-park evidence — `--force` acknowledges the venue state is handled); `remove` drops the book. Pre-v3 specs that said `paper` were migrated to `dry_run` (the old wallet-bound behavior). |
| `live` | required | Same decision core as dry_run, then routes the order through the venue's capped execution path. Places real orders. |

### Sizer modes (`--sizer-mode`)

A mode decides **transitions** — what a neutral or opposing view does to what you already hold. It does not decide size; that is `--scale`.

| Mode | On a **neutral** view | On an **opposing** view while holding | Target range |
| --- | --- | --- | --- |
| `conviction` (`--on-neutral`, `--on-reversal`, `--flip-threshold`) | per `--on-neutral` — the policy-driven mode; see the policy table | per `--on-reversal` — see the policy table | `[-1, +1]` |
| `always_in` | **hold** — a neutral view never exits | **flip, unconditionally** — no threshold gates it; passing `--flip-threshold` here is a hard error | `[-1, +1]` |
| `single_sided` (`--side long\|short`, `--on-neutral`) | per `--on-neutral` — **defaulted by signal kind**: `hold` for `text_long_short`, `flatten` for metric | flatten; never crosses to the other side | `[0,+1]` or `[-1,0]` |

**`single_sided` is the answer to "one-sided, and don't close on noise."** Its `--on-neutral` is stamped from the referenced signal's kind, so on a `text_long_short` signal it **holds through a neutral classification by default** — a classifier's neutral is *no information*, and noise must not move money — while still never taking the opposite side (an opposing view closes it to cash). On a metric signal it defaults to `flatten`, because a rule's neutral **is** its exit instruction.

⚠️ **Never answer a "one-sided / never short" request with `conviction --on-reversal close_only`.** `close_only` blocks a **one-step flip**, not a two-step reversal: once an opposing view has closed the position to flat, the next fresh opposing view **enters the other side** (from flat there is no prior, so the `close_only` guard does not apply — see the worked example). `single_sided` is the only mode that guarantees the other side is never taken.

⚠️ **`--on-neutral hold` on a signal that can never emit the opposing side has NO autonomous exit.** A `metric_level_rule` with `--on-true bull` and the default `--on-false neutral` emits only `bull` or `neutral` — under `hold`, *nothing* ever closes the position, and `--tp` / `--sl` / `--time-stop` is the only way out. That is the legitimate **entry-trigger** model (the rule fires the entry; risk management owns the exit) — but only *with* an exit attached. `create` prints a note whenever `on_neutral=hold` is set with no `--tp`/`--sl`/`--time-stop`; do not ignore it.

⚠️ **`always_in` has the same hazard.** It holds through every neutral by definition, so on a signal that can never emit the opposing side (a `metric_level_rule` with the default `--on-false neutral`) it enters once and **can neither flatten nor flip** — it just holds, forever. `create` warns for exactly this pairing (it stays quiet on a two-sided signal, where flipping forever is what `always_in` advertises). Give the signal a two-sided mapping (`--on-false bear`), pick a sizer that can flatten, or attach `--tp`/`--sl`/`--time-stop`.

⚠️ **`metric_band_rule` + `--on-neutral hold` is REJECTED.** A band fires its exit *by* emitting neutral (the regime returns to `flat`), so `hold` would make the `long.exit` / `short.exit` conditions you authored dead. Leave `--on-neutral` at its `flatten` default there.

**`--on-reversal` is also inert behind a band signal.** A band never flips in one step: it always returns to `flat` (its exit condition) before entering the opposite side, so the sizer never sees a *held-position* opposing view — and the flip-vs-`close_only` distinction only matters on exactly that direct opposing view. The policy is still accepted and stamped (the metric default is `flip`), but it is never consulted; the band's own regime does the transition.

**Conviction policies.** `conviction` mode carries two deterministic policies, **defaulted from the referenced signal's kind and stamped explicitly into the spec at create** (readable in `show`; override with the flags):

| Policy | Values | `text_long_short` default | metric default |
| --- | --- | --- | --- |
| `--on-neutral` | `flatten` = a neutral view closes to cash; `hold` = a neutral view keeps the position | `hold` (a classifier's neutral is no-information — noise must not move money) | `flatten` (a rule's neutral IS its exit instruction — band exits depend on it) |
| `--on-reversal` | `flip` = an opposing view crosses to the other side when conviction ≥ `--flip-threshold` (default 0.7; below → close to flat); `close_only` = an opposing view ALWAYS closes to cash, never a one-step flip | `close_only` (never cross zero on a misread headline; a FRESH opposing event while flat then enters the other side) | `flip` (rules emit full conviction; their reversals are deliberate — note under `close_only` a metric rule's persisting direction is deduped after the close and re-enters only when the direction changes anew, whether the close fills same-tick or parks pending settlement) |

**`--flip-threshold` requires `--on-reversal flip`, and exists only on `--sizer-mode conviction`.** Both are hard rejections — passing it with `close_only`, without an `--on-reversal`, or on any other mode is an error at create. (It used to *imply* `flip` when passed alone, which silently converted a `text_long_short` strategy off its `close_only` default; and non-conviction modes used to accept it and throw it away.) Note it is also **inert behind a metric signal** — metric kinds pin conviction to 1.0, so any threshold in `0..1` is always cleared and the flip is never gated; `create` prints a note if you set one there. **`--on-reversal` exists only on `conviction`** (rejected on other modes — `single_sided` never crosses and `always_in` always flips); **`--on-neutral` exists on `conviction` AND `single_sided`** (rejected on `always_in`, which holds through a neutral by definition). **Map the user's intent, don't guess**: "get out whenever there's no clear signal" → `--on-neutral flatten`; "reverse automatically on opposing news" → `--on-reversal flip`; "one-sided, but don't close on noise" → `single_sided` (its `hold` is already the default on a text signal); otherwise omit and let the kind default apply. Note `hold` + `close_only` (the text default) has NO autonomous exit except an opposing view — pair it with `--tp/--sl/--time-stop` for loss control (create prints a note when none is set).

#### One signal, five stances

Setup: `--scale fixed`, `--capital-amount 1000`, no `--min-confidence`, and the default flip threshold of 0.7 (do **not** pass `--flip-threshold` explicitly alongside `close_only` — that combination is rejected at create). Every strategy starts flat. Numbers are the target weight (`+1.0` = fully long the base; `0` = cash).
Views, in order: **1)** bull 0.9 · **2)** neutral · **3)** bear 0.5 · **4)** bear 0.9 · **5)** bull 0.8

This is a config-level truth table, so the same view sequence is run through all five stances. Treat the fractional convictions as illustrative: only `text_long_short` actually varies its conviction (metric kinds pin it to 1.0), so a metric rule can never produce the sub-threshold reversal at tick 3.

```
always_in
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  hold — a neutral view never exits
 +1.0 → bear 0.5 → -1.0  flip — the threshold is never consulted
 -1.0 → bear 0.9 → -1.0  hold (same side)
 -1.0 → bull 0.8 → +1.0  flip

conviction --on-neutral hold --on-reversal close_only     (the text_long_short default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  hold — a classifier's neutral is no information
 +1.0 → bear 0.5 →  0    close to cash — close_only NEVER crosses in one step
  0   → bear 0.9 → -1.0  enter short — a FRESH opposing view arriving while flat.
                         ** close_only is NOT one-sided: it blocks a one-step flip,
                            not a two-step reversal. It DID take the short. **
 -1.0 → bull 0.8 →  0    close to cash

conviction --on-neutral flatten --on-reversal flip        (the metric default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  →  0    close — a rule's neutral IS its exit instruction
  0   → bear 0.5 → -1.0  enter short — an ENTRY from flat, not a flip
 -1.0 → bear 0.9 → -1.0  hold
 -1.0 → bull 0.8 → +1.0  flip — opposing, and 0.8 ≥ 0.7 clears the threshold
                         (at 0.5 it would close to 0 instead — "close first")

single_sided --side long --on-neutral hold                (the text_long_short default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  HOLD — an irrelevant headline does not close the position
 +1.0 → bear 0.5 →  0    close to cash — the opposing view still flattens...
  0   → bear 0.9 →  0    ...and it NEVER shorts. This is the true one-sided stance.
  0   → bull 0.8 → +1.0  re-enter long

single_sided --side long --on-neutral flatten            (the metric default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  →  0    CLOSE — a rule's neutral IS its exit instruction
  0   → bear 0.5 →  0    stays flat — never shorts
  0   → bear 0.9 →  0    stays flat
  0   → bull 0.8 → +1.0  re-enter long
```

**Rules the example depends on:**

- `--flip-threshold` gates a **flip out of a held position**. It never gates an entry from flat.
- `close_only` blocks a **one-step flip**, not a reversal. From flat it enters the other side, so it is **not** a way to get one-sided exposure — `single_sided` is. (On the text lane every accepted event is fresh, so re-entry is immediate, as in the example. On the metric lane a *persisting* rule direction is deduped after the close, so re-entry waits for the direction to change anew.)
- `--on-neutral hold` governs **neutral views only**. It never stops an *opposing* view from acting — under `single_sided` an opposing view still flattens.
- `always_in`'s flip is **unconditional** — no threshold gates it, and passing `--flip-threshold` there is now a hard error rather than a silently-dropped flag.
- A view below `--min-confidence` is a **skip**: hold current exposure, in every mode. Never a flatten.
- An **abstain** (a metric signal whose data isn't ready yet — conviction 0, not a neutral) is likewise a hold, never a flatten.

### Magnitude, capital, and leverage

The sizer object is five fields: `config` (the mode above), `scale`, `capital`, `leverage`, `min_confidence`.

- **`--scale`** — `fixed` (full weight) or `conviction` (size by the view's conviction value). Orthogonal to `--sizer-mode`, despite the shared word: mode picks the *transition*, scale picks the *size*. Note both metric kinds pin conviction to 1.0, so `--scale conviction` is a **no-op** behind a metric signal — it only does real work behind `text_long_short`.
- **`--capital-source`** — `fixed` (+ `--capital-amount`, resolves to `min(amount, available)`), `wallet` (the whole equity), or `fraction_of_wallet` (+ `--capital-fraction 0..1`). **`available` is EQUITY, not free cash** — free cash *plus the held position's equity contribution*. That contribution is the position's **notional** for fully-paid holdings (Polymarket shares) but only its **posted margin** on a leveraged perp (the unrealized PnL is already inside the venue's free-capital figure). So `fixed` shrinks below `amount` only on a real mark-to-market loss, not merely because cash was deployed. `observe` **requires** `fixed`; the wallet-shaped sources are rejected there.
- **`--leverage`** — perp venues only, `1..100`, omitted ⇒ 1×. Rejected above 1 on Polymarket and in `observe`. `base = capital_base × leverage`, so under leverage the capital base is *margin committed*, not exposure. The strategy never writes the venue's setting — it sizes within it, and **the clamp only binds on a position you already hold** (that is where the venue surfaces its setting). **Opening from flat sizes to the FULL strategy leverage**, so if the coin's venue setting is lower the order is **rejected at execution** rather than quietly downsized — `om strategy create` prints a note about this. Leverage is also **not** frozen into a held position: editing it re-sizes what you already hold on the next acting tick, which on a `live` strategy places a real order.
- **`--min-confidence`** — the confidence acting gate, on every mode. It is the strategy's only confidence knob: signals carry none.

Then `target_qty = (target_weight × base) / price`, and the order is the delta `target_qty − current_qty`. An unpriceable mark (`price ≤ 0`) is a **no-op, never a flatten**.

**Flip execution is venue-specific.** On Polymarket a flip is two sequential legs (SELL the held outcome, then BUY the target outcome). The BUY is submitted **only if the SELL comes back `filled`**; on any other status (`submitted`, `blocked`, `rejected`, `error`) the sequence stops and the BUY is never sent, so the flip does not complete. **Where that leaves you depends on the SELL, and one branch is dangerous:** a `blocked` / `rejected` / pre-submit `error` SELL placed *nothing*, so the strategy **still holds the OLD side — fully exposed to the very view it just reversed against**. A `submitted` SELL parks pending settlement and resolves to flat. Either way the target side is never entered; the next tick re-plans from actual holdings. On Hyperliquid a perp flip is **one netting order** that crosses zero — no two-leg sequence, so this failure mode does not exist there.

**`edit` cannot change the sizer's shape.** *Within the sizer*, only `--min-confidence`, `--leverage`, and the capital trio (`--capital-source/--capital-amount/--capital-fraction`) are patchable; changing `mode`, `scale`, or any conviction policy requires remove-and-recreate. Capital swaps as a **whole object** (switching source needs the matching value and drops the old one; `observe` still requires `fixed`), and like leverage it is **not frozen into a held position**: the sizer reads the new base immediately, so the next acting tick re-sizes what you already hold, which on a `live` strategy places a real order. (Outside the sizer, `edit` freely patches label, run-mode, TP/SL/time-stop, notify-channel and paper fee; see the edit section below.)

⚠️ **Create the signal BEFORE the strategy.** With an unresolvable signal slug `create` cannot read the signal's kind, and two things go wrong:

- **Every `metric_band_rule` rejection stops firing** (both `--sizer-mode always_in` and `--on-neutral hold`), because `create` needs the signal's kind to apply them. The daemon still refuses to trade such a strategy on every tick — it just does so *after* you have already created it. Nothing warns about *the band rejection itself* — `create` cannot know the kind. You may still get the *"the signal does not resolve yet, so this cannot be checked"* note, but that one is about the **no-autonomous-exit** analysis and it fires **only when no `--tp`/`--sl`/`--time-stop` is set**. Attach a managed exit and it is suppressed (correctly — you *do* have an exit), so an operator who did the safe thing gets **no warning at all here** and only finds out at the daemon. Create the signal first and every check is definitive.
- The conviction policies are stamped from the *fallback*: `on_neutral: flatten` + `on_reversal: flip`. For a `text_long_short` signal, that is the **exact inverse** of its intended default (`hold` + `close_only`), and **nothing ever re-stamps it**, because `edit` cannot patch the conviction policies. The strategy will flatten on every neutral classification and one-step-flip on a single misread headline. `create` returns a warning naming exactly which policies it defaulted; it rides the result (`warnings`), so it reaches the CLI, MCP, and `--format json` alike.

### Order routing

Every strategy order is a marketable taker order — Polymarket FAK (fill-and-kill), Hyperliquid market IOC. It crosses the spread at the opposite top-of-book price and cancels any unfilled remainder; a strategy order never rests on the venue. There is no order-type knob (resting GTC orders remain available on the manual `om order place` lane only).

## Workflow when a user wants a strategy

### 1. Discovery

Run `om status` (above), confirm the prerequisites for the requested run-mode and signal kind, and route any missing setup to the user. For `observe` you can proceed once the signal's inputs exist; for `dry_run`/`live` confirm the wallet is paired.

### 2. Create (or reuse) the event-watch — for an event-driven signal

A `text_long_short` signal reads an event-watch; metric signals read market metrics via the data API (no event-watch). Create the watch with `om event-watch create` over the user's configured data vendor and keep it enabled (the daemon subscribes to enabled watches). The `--stream-ref` names the vendor's adapter — see `openmarket-event-watches` for the per-vendor shape and lifecycle.

### 3. Create the signal

```bash
om signal create --kind text_long_short --event-watch <watch-slug> \
  --topic "<what LONG vs SHORT mean for this market>" \
  --slug my-signal

# …or context-aware (judge each event against prior memory, not in isolation):
om signal create --kind text_long_short --event-watch <watch-slug> \
  --topic "<what LONG vs SHORT mean>" --slug my-signal \
  --context --context-recent-events 5
```

For a deterministic TA rule (no LLM, no event-watch) — an RSI band:

```bash
om signal create --kind metric_level_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --metric rsi --period 14 --op lt --threshold 30 --on-true bull --slug sig-rsi-oversold
```

…or a golden cross (metric-vs-metric; `--on-false` sets the death-cross side):

```bash
om signal create --kind metric_level_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval DAY \
  --metric sma --period 50 --op gt --compare-metric sma --compare-period 200 \
  --on-true bull --on-false bear --slug sig-golden-cross
```

…or the same RSI band evaluated every tick (acts the moment the direction flips), rate-limited to at most once per 15 minutes:

```bash
om signal create --kind metric_level_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --metric rsi --period 14 --op lt --threshold 30 --on-true bull \
  --eval tick --cooldown 15m --slug sig-rsi-oversold-tick
```

…or a stateful RSI hysteresis band:

```bash
om signal create --kind metric_band_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval HOUR \
  --long-enter '{"left":{"metric":"rsi","params":{"period":14}},"op":"lt","right":{"value":30}}' \
  --long-exit '{"left":{"metric":"rsi","params":{"period":14}},"op":"gt","right":{"value":45}}' \
  --short-enter '{"left":{"metric":"rsi","params":{"period":14}},"op":"gt","right":{"value":70}}' \
  --short-exit '{"left":{"metric":"rsi","params":{"period":14}},"op":"lt","right":{"value":55}}' \
  --slug sig-rsi-hysteresis
```

Add `--eval tick --cooldown 15m` to make that hysteresis band evaluate every daemon tick while rate-limiting new flat entries. Exits remain exempt from cooldown.

Multi-param indicators (`macd`, `bb_*`, `stoch_*`) and compound metric conditions aren't expressible via the simple `metric_level_rule` flags — author those via the `signal_create` action with an explicit `params` object or `condition` tree. Discover metrics + their params with `om metric list`.

### 4. Create the strategy

It is **created disabled by default** (nothing trades until you arm it).

**Derive, disclose, override — do NOT interrogate the user.** Create immediately with the defaults for everything the user did not specify, then read the resolved spec back in ONE compact block so they can correct anything. Never ask upfront questions about sizing, capital, venue, or indicator parameters; the only decisions that warrant a question are (a) real money — arming `dry_run`/`live`, wallet-sourced capital — and (b) a genuinely unresolvable market reference. The defaults:

| Knob | Default when unspecified |
| --- | --- |
| `market` | **OMIT — unpinned research strategy.** Pin at create only when the user names a venue/market or asks to trade. |
| `sizer` | OMIT — resolves to conviction mode, conviction scale, fixed $10,000 (the backtest's own defaults, so backtests describe the real strategy). `single_sided` only on explicit "never short"-style language. |
| exit | OMIT — no kind stamps a managed exit (a metric rule's neutral/reversal IS the exit). A text/news strategy left without one gets the no-autonomous-exit note: relay it and offer `--tp`/`--sl`/`--time-stop`. |
| indicator params | The user's phrase supplies levels ("RSI under 30"); periods default to textbook values (RSI 14, MA cross 50/200, MACD 12/26/9, Bollinger 20/2). |
| cadence | From phrasing ("hourly"); else HOUR. |
| run-mode / enabled | observe, disabled — the schema defaults; never pass them unprompted. |

Every default the action resolves is echoed in the result's `warnings[]` — surface them verbatim; they are the disclosure. The readback is the override surface: the user corrects, you `strategy_edit`.

```bash
om strategy create --signal my-signal --slug my-strategy   # unpinned research strategy, all defaults
```

Pinned variant, only when the user asked to trade a specific market:

```bash
om strategy create --signal my-signal --condition-id <CID> --long-outcome Yes \
  --run-mode observe --slug my-strategy
```

Note there is no `--flip-threshold` here: 0.7 is already the default, and passing one *requires* an explicit `--on-reversal flip` (it would otherwise silently override a text signal's `close_only` default). Only pass it when the user actually wants conviction-gated flips.

**After the create lands, offer a quick backtest before arming.** One call: `backtest_run` with the new strategy's slug (the one-shot verb derives window, interval, costs, and time basis from what is stored, and returns the result against a buy-and-hold benchmark). It is the cheapest way for the user to eyeball whether the idea roughly behaves before any mode change; offer, do not auto-run.

**Hand the chart URL over honestly.** The result's `chart` block carries the live-view URL — relay it. Read `chart.mode` before promising what the link shows: `strategy_panel` means a watching viewer has the Strategy Tester live; `panel+markers` means the run ALSO drew persistent fill markers because nobody was watching or the daemon session could not attach (`chart.markers_reason` says which) — those markers are relay-stored and survive reloads and the daemon being down; `markers` means only the persistent markers landed (panel unavailable). The panel itself is re-pushed per viewer by the user's om daemon: if their daemon is stopped, say the link shows the markers now and the full tester panel once the daemon is back. The full report is also on disk at `report_path` — cite it for anything the compact result dieted away.

### 5. Confirm the daemon is running

Strategies execute only under the daemon. If `om status` showed it down, route the user to `om service install` then `om service start` (run as a service, not foreground, so decisions land in `runner.log`). The agent cannot start it.

### 6. Verify the setup (still paused)

Confirm the wiring before arming — the strategy is still paused, so it is listed but not yet evaluated or trading:

```bash
om strategy list                                            # enabled=false (paused), expected run_mode
om event-watch events <watch-slug> --limit 1 --include-raw-text  # latest event landed; data_mode=live (vs backfill) = live push
om logs                                                     # [strategy] scanned=[...] evaluated=[...] skipped=[...] + per-decision summary
```

### 7. Ask whether to arm — never auto-arm

A created strategy stays **paused and harmless** until armed. Only once the setup above checks out, **ask the user whether to arm it** — do not `resume` on your own. **This is also the pin moment for an unpinned strategy**: propose the market in the same breath ("Hyperliquid BTC perp, 1x — arm in observe?"), pin it via `strategy_edit` with `market` on their yes, then resume. Arm only on an explicit yes, and for `dry_run`/`live` treat that as a capital-affecting confirmation (a `live` strategy starts placing real orders once armed):

```bash
om strategy resume my-strategy    # ONLY after the user says to arm it
```

Once armed, the daemon evaluates it **once per new accepted event** (for metric signals, once per bar of the selector interval, or — with `--eval tick` — every daemon tick, acting only when the direction/regime changes) and the decision shows in `om logs` (`[strategy] … evaluated=[…]` + a one-line summary); later ticks on the same input show `skipped=[...]` (runtime dedupe).

## Workflow when a user wants to pause, resume, edit, or remove a strategy or signal

```bash
om strategy pause my-strategy     # disarm (preserves the spec + runtime history) — HANDS-OFF: exits are NOT managed while paused
om strategy resume my-strategy    # re-arm
om strategy edit  my-strategy --min-confidence 0.6   # patch label / min-confidence / run-mode / TP-SL / leverage / capital / notify-channel
om strategy edit  my-strategy --clear-tp             # unset an exit trigger (--clear-sl / --clear-time-stop likewise)
om strategy show  my-strategy     # spec + persisted daemon runtime state
om strategy remove my-strategy    # delete the strategy and its runtime rows (prompts; --yes to script)

om signal show   my-signal        # spec + the strategies that reference it (its consumers)
om signal edit   my-signal --period 28               # patch tuning / metric rule fields
om signal pause  my-signal        # disable the producer — SEE THE CASCADE WARNING BELOW
om signal resume my-signal        # re-enable the producer
om signal remove my-signal        # delete the producer
```

Signals now have the full lifecycle (`show` / `edit` / `pause` / `resume` / `remove`), gated for consumer safety. **These consumer relationships are surprising — call them out to the user before acting:**

- **`om strategy edit` has an edit/apply split for managed exits:** plain `--tp` / `--sl` / `--time-stop` edits update the spec for the next entry/flip only; an already-held position keeps its frozen active contract unless the operator explicitly runs `om strategy edit <slug> --apply-to-position --tp ... --sl ... --time-stop ...` and confirms the venue/runtime update. `--clear-tp` / `--clear-sl` / `--clear-time-stop` unset a trigger (spec-only; refused with `--apply-to-position`) — clearing the LAST trigger while a position is held retires the persisted policy on the next tick (native brackets canceled, position left to the signal), so warn the user before a full clear mid-hold.
- **`om strategy remove` prompts for confirmation** (naming any open position and resting native bracket oids that would go unmanaged); pass `-y`/`--yes` in scripts. `--force` additionally cancels resting Hyperliquid TP/SL children first — the open position itself is never touched.
- **`om strategy pause` while a position is held leaves it UNMANAGED.** Pause means hands-off: the daemon places no orders while paused, so TP/SL/time-stop do NOT fire (on live Hyperliquid, already-resting native brackets keep enforcing venue-side; the software time stop and every Polymarket/paper exit stop). The pause output carries a `held_position` disclosure — surface its `note` to the user verbatim. To stop trading while keeping protection: flatten first, or clear the exit criteria (`edit --clear-sl` etc.) and manage the position manually, or `om strategy remove` after flattening.
- **`om signal edit` can patch metric trigger structure in place.** For `metric_level_rule`, patch the simple-condition pieces with `--metric`, `--period`, `--op`, `--threshold`, `--compare-metric`, `--compare-period`, or selector flags (`--symbol`, `--exchange`, `--interval`, `--quote`). For `metric_band_rule`, replace individual side conditions with `--long-enter`, `--long-exit`, `--short-enter`, `--short-exit`, plus selector flags. Compound `metric_level_rule` trees are edited through the `signal_edit` action by replacing `condition`; flat CLI flags intentionally reject those trees.
- **`om signal edit` can change a `text_long_short` signal's context policy.** `--context` / `--context-overview` / `--no-context-overview` / `--context-recent-events <n>` **merge** onto the current policy (only supplied fields change); `--clear-context` removes it (back to isolation). Because context feeds the `producer_id`, any of these is an **identity change** (see below).
- **`om signal remove` / `om signal edit`** are **refused** (RESTRICT) while a strategy references the signal, or (for `edit`) when the change touches the **model pin, the `--topic`, or the context policy** (each recomputes the signal's `producer_id` and breaks replay comparability). The `--topic` is a `producer_id` input because it defines the thesis and drives how context is interpreted; `--event-watch` (the data source) is NOT — re-pointing it is ordinary tuning. Pass `--force` to proceed. A forced `remove` leaves those strategies dangling; the daemon then **auto-pauses** each on its next tick. A rule/selector edit keeps the same `producer_id`, but already-emitted records still reflect the prior rule, so mention that comparability caveat. Run `om signal show <slug>` first to see the consumers.
- **`om signal pause` CASCADES:** on the next daemon tick, every strategy referencing a paused (or removed) signal is **auto-paused** (persisted `enabled=false`) and sent a warning notification — and **`om signal resume` does NOT re-enable those strategies.** After resuming the signal, re-arm each consumer with `om strategy resume`. Warn the user of this before pausing a referenced signal.
- **`om strategy edit --run-mode live`** never starts live trading on its own: escalating a strategy from a non-live mode **into `live` disarms it** (persists `enabled=false`), so you must explicitly **`om strategy resume <slug>`** to begin live trading. This is scoped to the escalation transition — tuning an already-live strategy (a label/TP/`--min-confidence` edit, or re-passing `--run-mode live`) leaves `enabled` untouched and does NOT halt a running live strategy; de-escalating to observe/dry_run also leaves it enabled. Tell the user the strategy is armed for live but dormant until they resume it.
- **Downgrading a HELD live strategy away from live is REFUSED** (`strategy_live_position_held` — the position would lose every software exit, and the walletless daemon would false-record an exit for a still-open position). `--force` bypasses the guard and mirrors `om strategy pause` at the venue: the position and any resting native brackets are left EXACTLY as they are (Hyperliquid keeps enforcing its native TP/SL) — but **unlike a pause it will NOT resume into management**; the user must flatten manually. Surface the returned warning verbatim and never suggest `--force` casually — flattening first is the safe remediation.
- **One live strategy per (venue, market, wallet) — anything else needs the user's explicit consent.** A cohort-forming call (create, a run-mode escalation, a market pin on a live strategy, resume, a marketplace install's later arming) refuses with `same_market_consent_required` unless it carries `allow_same_market: true`; when the conflict check could not read every strategy spec, a cohort-forming call landing live+pinned refuses with `same_market_unverified_consent_required` unless it carries `allow_unverified_cohort: true` (a SEPARATE consent — neither flag satisfies the other's gate; prefer telling the user to repair the unreadable spec for a real answer); on chat surfaces the approval card carries the matching consent — never set either flag from your own judgment, only after the user explicitly agreed to the named conflict (or to proceeding without a verified answer). The configuration is unsupported: **we cannot guarantee correct behavior when multiple strategies act on one netted position** — while a cohort stands a fired TP/SL/time-stop MAY close the whole netted position, the sibling's exposure included, at a price it did not choose; native brackets size to the net, not each strategy's own share; P&L can misbook; and after a crash the crash-heal re-arms exits for neither sibling (a position the strategy's own filled receipt explains re-books on the next pass and its exits re-arm; the durable gap is a position no om receipt explains). The fired close pages the sibling and the crash-heal exclusion notifies (each held for `om status` on a channel-less install), but the misbooking is silent — the per-strategy figures just read wrong. Consents are journaled (`om strategy history`). What lifts the cohort state is removing a sibling or downgrading its run mode — pausing does NOT (a paused live spec still counts). The crash gap has a consent-time posture (`cohort_crash_policy`: `flatten` | `hold`, default hold, journaled with the consent): under unanimous `flatten`, om closes the whole naked net (reduce-only) after ~3 confirming sweeps and pages; `hold` pages and waits. Setting `flatten` arms an autonomous close, so it raises an approval card — never set it from your own judgment, only after the user explicitly chose it.
- **Arming over a position the strategy did not open needs consent too** (`existing_position_consent_required` / `position_unverified_consent_required` → `allow_existing_position: true`, same ask-the-user-first rule). The sizer trades `target − venue_position` with no provenance: a foreign position is trimmed, extended, or closed as the strategy's own on its first evaluation, and its value inflates the sizing base. This is the enforced edge of the general rule: **any trading om did not place — manual orders, the exchange UI, another bot — changes the position a live strategy sizes against**, at any cohort size including one.
- **A live level rule is a standing reconciler against manual intervention.** A `metric_level_rule` strategy re-enters over the user's deliberate manual close within a tick while its condition holds. Tell the user to pause the strategy BEFORE intervening by hand.

## Workflow when a user wants to inspect what a strategy is doing

- `om strategy list` — which strategies exist, enabled state, and run_mode.
- `om logs` — the daemon's per-tick `[strategy] …` lines plus a one-line decision summary (view, sized order) per evaluated strategy. This is the primary window into what a strategy decided; it requires the daemon running as a service.
- `om event-watch events <slug>` — what an event-driven signal last saw.

## Backtesting a strategy

Backtests are the research skill's job: `skill_read research` documents `backtest_run` (the default one-shot verb: saved slugs only) and `backtest_spec` (explicit windows/costs and UNSAVED inline candidates). Two routing facts that live here because they bite strategy authors:

- **An unsaved idea backtests via `backtest_spec` with an inline `candidate`** ({strategy, signal?} in the authoring shapes of `strategy_create`/`signal_create`); nothing is persisted, and a winning candidate is creatable verbatim — except a `constant` signal, which is replay-only (the kind is retired from `signal_create`; re-author it as a metric/text kind to trade the idea).
- **Authoring the candidate's signal spec?** The per-kind condition shapes and worked JSON examples are in `skill_read("signal", section = the kind name)` (e.g. `metric_band_rule` for band regimes like a golden cross: enter `{"left":{"metric":"sma","params":{"period":50}},"op":"gt","right":{"metric":"sma","params":{"period":200}}}`).

## Behaviors to follow

- **Run `om status` first** to confirm prerequisites; route any missing feed / signal-credential / wallet / daemon setup to the user with the exact command.
- **Default to `observe`.** It is walletless and never trades — the safe way to confirm the wiring before dry_run/live.
- **Don't interrogate about sizing.** Sizer mode and capital default at create (conviction mode/scale, fixed $10,000) and every defaulted choice is echoed in the result's `warnings[]`: create first, then read the resolved spec back so the user can correct it (see step 4). The only sizing questions worth asking upfront are the real-money ones (arming `dry_run`/`live`, wallet-sourced capital).
- **Report the resolved params after every create** — signal, market + long-outcome, sizer mode (+ flip-threshold/side), scale, capital, run-mode, enabled — so the user sees exactly what was set or defaulted.
- **Run the daemon as a service**, not foreground, whenever the user needs to read decisions — only the service writes `runner.log` for `om logs`.
- **Create disabled; ask before arming — never auto-arm.** A freshly created strategy is paused and harmless; `om strategy resume` only after the user explicitly says to arm it (and for `dry_run`/`live`, treat arming as a capital-affecting confirmation).
- **Reuse or list existing specs** (`om strategy list` / `om signal list` / `om event-watch list`) before creating, to avoid duplicate-slug errors.

## Behaviors to avoid

- **Don't reach for a foreground run command** — there is none; strategies execute only inside the daemon.
- **Don't auto-arm.** Never `om strategy resume` a strategy you just created unless the user explicitly asked to arm it — especially in `dry_run`/`live`.
- **Don't expect a created strategy to trade** before it is resumed AND the daemon is running.
- **Don't run the daemon in the foreground** if you need to read its decisions back — its output won't reach `om logs`.
- **Don't try to set secrets or pair the wallet yourself** (`om setup` / `om config set-key` capture credentials) — route those to the user.
- **Don't put a strategy in `live`** unless the user explicitly asked for real orders and the wallet is paired; `observe`/`dry_run` first.

## See also

- `openmarket-event-watches` — create, configure (per data vendor), and inspect the event-watch that feeds an event-driven signal.
- `openmarket-orders` — one-shot manual orders via `om order place` (act now, rather than wire a standing strategy).
- `openmarket-research` — correlational event studies / backtests over accepted event-watch rows.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om strategy` — (bespoke; see narrative above)
- `om strategy create` (action: `strategy_create`) — Create a slug-addressed trading strategy from a referenced `om signal`.
- `om strategy digest` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy digest list` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy digest run` (action: `strategy_digest_run`) — Generate and persist a strategy-digest edition NOW over the last 24 hours (every enabled strategy).
- `om strategy digest schedule` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy digest schedule off` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy digest schedule set` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy digest show` (action: `strategy_digest`) — Read stored strategy-digest editions (a daily prose briefing over the last 24h of every enabled strategy: fills, reversals, exits, P&L, skip gates, anomalies) and manage THE daily schedule.
- `om strategy edit` (action: `strategy_edit`) — Patch tuning fields of a daemon-native strategy by id or slug (label, acting min_confidence, run mode, TP/SL bracket + time stop — set or clear —, leverage, capital base, notify channel), and PIN a market on an unpinned research strategy (the arm-time step; pin-once).
- `om strategy history` (action: `strategy_history`) — Show the durable event timeline for one daemon-native strategy, including entry/add/flip/exit/external-close/retired events, stranded-holding evidence (a live fill or a still-in-flight close/flip that raced a run-mode downgrade), pause-family disclosures (paused/auto_paused), bracket_lost/bracket_fired/bracket_stale/replacement_pending/bracket_reconciled/bracket_restored/bracket_verified coverage events, trigger_rejection_suspected escalations (the venue repeatedly rejected a native tp/sl re-place with an undocumented reason — the venue's stated reasons live here, scrubbed and length-bounded), ledger_anomaly rows (a venue fill the realized-PnL ledger refused to book, a booking gap it could not book, or a book-vs-venue divergence episode), live-ledger fill joins by cloid (the booked price and realized figure per order), resolution settlements (trade-less redemptions the cloid join cannot carry), and any joined execution receipt by cloid.
- `om strategy list` (action: `strategy_list`) — List configured trading strategies (the persisted StrategyDefs), across every venue (Polymarket, Hyperliquid).
- `om strategy paper` — (bespoke; see narrative above)
- `om strategy paper reset` (action: `strategy_paper_reset`) — Reseed a paper strategy's simulated book: cash returns to starting_cash (or a new --cash), the open position and every recorded fill are DROPPED, and the runtime exit contract is cleared.
- `om strategy pause` (action: `strategy_pause`) — Disable one daemon-native strategy by id or slug.
- `om strategy remove` (action: `strategy_remove`) — Remove one daemon-native strategy by id or slug and clear its strategy runtime/outbox rows.
- `om strategy resume` (action: `strategy_resume`) — Re-enable one paused daemon-native strategy by id or slug.
- `om strategy show` (action: `strategy_show`) — Show one daemon-native strategy spec by id or slug, plus its persisted daemon runtime row (last run, last signal, last error), the paper book's simulated P&L (paper mode), and the live realized-PnL ledger block (net/gross/fees, round trips, venue cross-check drift, seeded-basis and anomaly disclosures) whenever live fills were ever booked.

<!-- AUTO: END COMMAND REFERENCE -->
