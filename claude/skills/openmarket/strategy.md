---
name: openmarket-strategy
description: Author and operate daemon-native, signal-driven trading strategies — wire a signal (via `om signal`) to a pinned market with a sizer through `om strategy create`, arm it with `om strategy resume`, and let the daemon evaluate it each tick (observe / paper / dry_run / live). Venue- and signal-agnostic by design. Use this skill when the user wants automated signal-driven trading, asks how a strategy runs, or asks why one is not trading. The agent authors the specs but cannot set secrets or start the daemon — if the data feed, signal credentials, execution wallet, or daemon are not ready, route the user to the relevant `om setup` / `om config` / `om service install` and say so.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om strategy

### Guardrails

**Paper arms only when the user asks TO trade / run / arm / paper-trade it — "a strategy trading BTC" only names the market, so it lands disabled; `dry_run` and `live` never arm on your own: create them disabled and ask — the human's yes is `strategy_resume`, and an enabled create lands only through the approval card a surface raises on their explicit yes, never on your own initiative.** Paper and observe need no wallet; `dry_run`/`live` do, and pairing one (`om setup <venue>`) is the user's step, never yours (§"Run modes").

**Consent flags are never yours to set.** `allow_same_market`, `allow_unverified_cohort`, `allow_existing_position`, and `cohort_crash_policy: "flatten"` come only from the user's explicit yes to the named risk — relay the refusal or approval card, ask, then retry with the flag (§"Errors").

**Create the signal BEFORE the strategy** — the policies an unresolvable slug stamps from the fallback are never re-stamped, and `edit` cannot repair them. **`--long-outcome` is an axis, not a bet:** encode the LONG/SHORT inversion in exactly one of the signal's topic or `long_outcome`, never both.

### Routing

Rule of thumb: a **standing, signal-driven position** managed over time → this skill. A **one-shot condition→notify/execute** → the alerts skill. **Act now** → the orders skill. Signal authoring detail lives in `skill_read signal` (per-kind sections); backtests are the research skill's (§"Backtesting a strategy"). **Derive, disclose, override** — create with defaults and read the resolved spec back; never interrogate about sizing — the readback is the override surface (§"Workflow when a user wants a strategy").

Quick routing — one recipe per common ask; the result discloses every default, relay it:

| Ask | Recipe |
| --- | --- |
| "paper trade the golden cross on BTC" | the signal first, then `strategy_create` pinned as a `market_data` market to the listing the signal create stamped (its `listing_note` / selector give `exchange` + `symbol`), `enabled: true` because the ask says trade — it lands ARMED in paper; read the spec back in one block, say how to pause, offer `backtest_run`. |
| "a strategy on Hyperliquid BTC / this Polymarket market" | `strategy_create` with the market pinned (`coin`, or `condition_id` + `long_outcome`); a pinned create defaults to paper — the result says so — and lands disabled: only an ask TO trade / run it arms. |
| "paper trade a pair with no venue market" (any exchange+symbol the metrics plane serves) | `strategy_create` pinned `{venue: "market_data", exchange, symbol}` — observe/paper only, never `dry_run`/`live`; going live = recreate pinned to a real venue. |
| "how is my strategy doing?" | `strategy_show` by slug; unnamed → `strategy_list` first (there is no most-recent default). Reply from the result: P&L (paper or realized), trades, "waiting for: …" in words, state, the one offer. |
| "stop it" / "pause it" | `strategy_pause` — never remove, never the signal; the result's `held_position` note is relayed verbatim. |
| "go live" / "arm it" | only on an explicit yes: confirm the wallet, `strategy_edit` run_mode (escalating into live or dry_run DISARMS), then `strategy_resume` — a capital confirmation. |
| "never short" / one-sided | sizer mode `single_sided` — the only mode that never takes the other side (`close_only` blocks a one-step flip, not a reversal: §"Sizer modes and policies"). |
| "tighten the stop / change TP" | `strategy_edit` tp/sl — next entry only; a HELD position changes only via `apply_to_position` on the user's yes. An "r/r > 2"-style ask is your translation — `tp = k × sl` as plain fractions, no ratio field exists. |
| "backtest it" | saved slug → `backtest_run`; your own unsaved idea → `backtest_spec` with an inline candidate (the research skill via `skill_read`); a registry strategy template → `package_try`, the marketplace funnel's default. |

## When to use this skill vs `openmarket-alerts`

The strategy/alert/order boundary: a standing signal-driven position is this skill; one-shot condition-notify/execute is alerts; act-now is orders.

| User intent | Which skill |
| --- | --- |
| *"Trade a market continuously off a recurring signal (news, a metric, …)"* | **this skill** — a signal-driven strategy |
| *"Take a directional view from a text/news classifier and manage the position"* | **this skill** — a `text_long_short` signal + strategy |
| *"Go LONG when RSI is oversold / on a golden cross (a deterministic TA rule)"* | **this skill** — a `metric_level_rule` or `metric_band_rule` signal + strategy |
| *"Notify me when BTC RSI < 30"* | **alerts skill** — notification-only alert |
| *"Buy BTC when it crosses 95k (once)"* | **alerts skill** — alert with `on_fire.execute` |
| *"Buy $50 of this market right now"* | **orders skill** — one-shot `order_place` |

## Discovery: prerequisites

What a strategy needs before it runs, and how to route the user to each missing piece; come here when a create or resume names a gap.

A missing feed, LLM key, data API key, wallet or daemon service surfaces as a typed error; confirm it with `system_status` before claiming the gap. The agent can author the specs but **cannot** set secrets or start the daemon — surface what is missing and tell the user the exact command to run:

| Prerequisite | Needed for | If missing, the user runs |
| --- | --- | --- |
| Data-feed vendor (registered via event-watch) | an event-driven signal to ingest events | the relevant `om setup` for the vendor (the event-watches skill via `skill_read`) |
| Signal credentials (LLM, for a text/classifier signal) | classifying a `text_long_short` signal | `om config set-key` / `om config set-model` |
| OpenMarket data API key | a metric signal (`metric_level_rule` / `metric_band_rule`) to fetch its metrics (`getPoints`) | `om login` (or `om init`) — the same key `metric_get` uses; no wallet |
| Execution wallet for the venue | `run_mode` `dry_run` or `live` (not `observe`/`paper`) | `om setup` for the venue (`om setup hyperliquid` / `om setup polymarket`) |
| Daemon running (as a **service**) | anything to actually evaluate/execute | `om service install` then `om service start` |

`observe` and `paper` modes need no wallet, and metric signals need only the OpenMarket data API (no event-watch, no LLM, no wallet for observe/paper). Prefer the **service** over a foreground `om run`: only the service writes `runner.log`, which is what `logs_tail` reads back — a foreground daemon's output is not readable.

## Discovery: what already exists

List strategies, signals, and event-watches before creating — reuse specs and avoid duplicate-slug errors.

Before creating, list what is configured to avoid duplicate-slug errors and to reuse specs: `strategy_list` · `signal_list` · `event_watch_list`.

## The strategy shape

What a strategy binds — referenced signal, optional pinned market, sizer, managed exits — and why unpinned-by-default means research-only.

A strategy turns a signal into orders along one spine: a signal emits a `{direction, conviction}` view → a programmatic sizer → an execution venue. The sizer and strategy consume **any** signal and target the venue through the same seams, so new signal kinds and new venues slot in without changing this workflow. Today the signal kinds are `text_long_short` (an LLM over an event-watch), `metric_level_rule` (a deterministic TA level rule), and `metric_band_rule` (a deterministic TA hysteresis rule), and the executors are the Polymarket CLOB and Hyperliquid; more of each are arriving.

A strategy (`strategy_create`) binds a **referenced** signal + an **optional pinned market** + a sizer (mode + capital) + a managed exit policy (TP/SL as PnL fractions + a time stop, enforced by the daemon watcher **while the strategy is enabled** — Polymarket in software, live Hyperliquid via native brackets plus the software time stop). The market pins via `condition_id` + `long_outcome` (Polymarket), `coin` (Hyperliquid), or `{venue: "market_data", exchange, symbol}` (any data-plane pair the metrics plane serves, e.g. BINANCE/BTCUSDT — **observe/paper only**: no execution venue stands behind it, so `dry_run`/`live` refuse typed (`strategy_market_paper_only`, §"Errors") and leverage must stay 1; going live means recreating pinned to a real venue); the binding is venue-agnostic by design, so additional venues attach at the same seam.

**Unpinned = research-only, and it is the DEFAULT.** A strategy created without a market is a research object: backtestable against any data asset the plan serves (including series with no execution venue at all, e.g. US equities), listable, editable — and never evaluated by the daemon. The lifecycle is: create unpinned → backtest freely → when the user wants it to RUN, pin a market (`strategy_edit` with `market`; pin-once) → arm. Any explicit run-mode on an unpinned strategy fails typed (`strategy_unpinned`) with that exact recovery in the hint (§"Errors").

**A managed exit can wake the agent.** `wake` on `strategy_create` / `strategy_edit` (`--wake-on-exit`) runs one agent turn once a stop-loss, time-stop, signal close, external close or flip has closed the position; the turn reads the thesis, the strategy's own trading record and its own notes, and answers with a thesis rewrite, a pause, or holding the view. `wake.mode: "propose"` (the default) RECORDS the rewrite — `om signal proposals` lists what is waiting, `om signal apply-proposal <id>` runs the edit behind a confirmation, and `watching_overview` names anything unanswered. `wake.mode: "autonomous"` is standing authority for the woken turn to apply the rewrite to that strategy's own signal, so setting it from chat raises an approval card and over MCP costs an armed window; `clear_wake` removes the block. A strategy's notes live under `<home>/memory/strategy/<id>/`, read with `om memory list --strategy <id>` and reachable from a chat turn through `memory_search`.

## Wiring each signal kind

Per-kind wiring: topic and context for text_long_short, conditions and eval cadence for metric_level_rule, per-side regimes for metric_band_rule, cross-market operands.

A signal (`signal_create_text` / `signal_create_metric`) is a pure producer of a `{direction, conviction}` view and never trades. Full authoring detail per kind lives in the signal skill (`skill_read signal`, section = the kind name). Current kinds:

- `text_long_short` — an LLM reading the latest accepted event of an event-watch. `topic` defines what LONG/SHORT mean **and** — when context is on — how prior context should inform the decision. **Prior context (ON by default for newly created signals: `{overview: true, recent_events: 5}`)**: with context, prior "memory" (the event-watch's `overview.md` plus a bounded list of recent accepted events) is fed as **untrusted reference**; without it the classifier judges the latest event in **isolation**. Opt out at create with `no_context`, or later with `signal_edit` (`clear_context`); signals created before the default stay as they are. The classifier does **not** assume how to use that context (it is neutral framing): **you** direct it in your `topic` — e.g. "treat a repeat of something already in the overview as already-priced (flat)", "weight escalation over the prior narrative", "go the other way on a reversal". Without such guidance the model uses its own judgment; the topic stays the sole definition of long/short/flat and context can never override it. `context.recent_events` (0..20) sets how many recent events (default 5, counted since the overview watermark); `context.overview: false` feeds only recent events (skip `overview.md`). When context is on but the watch has no **synthesized overview** yet (still warming up — the check is the event-watch's stored overview snapshot), it logs a notice and classifies in isolation for that tick (recent events are still supplied). **Enabling/tuning/clearing context — or editing the `topic` — changes the signal's `producer_id`** (an identity change; §"Workflow when a user wants to pause, resume, edit, or remove a strategy or signal").
- `metric_level_rule` — a deterministic TA rule (no LLM, no event-watch): a metric condition over the shared market selector (operands may read OTHER markets via their own selectors — see the cross-market paragraph below) → a side at conviction 1.0. The common single comparison is `left <op> right`: `left` a metric operand (`{metric, params}`); `right` either a constant (`{value}` — metric-vs-value, e.g. an RSI band) or a second metric operand (metric-vs-metric, e.g. a golden cross); the flat `metric`/`threshold`/`compare_metric` shorthands are the edit and CLI forms. `signal_create_metric` can also author an explicit `condition` tree with `{all:[...]}`, `{any:[...]}`, `{not:{...}}`, and arithmetic value expressions. `on_true` / `on_false` map the condition truth to a direction. Reuses the `metric_get` registry; reads the OpenMarket data API (no wallet for observe/paper). **Evaluation cadence — `eval` (default `bar`):** `bar` re-evaluates once per bar of the selector interval, on the **last closed bar** (deterministic, look-ahead-free — the textbook "signal on close" convention); `tick` re-evaluates every daemon tick on the live forming bar and **acts only when the emitted direction changes** (the position-aware sizer prevents double entry), optionally rate-limited by `cooldown` (e.g. `15m`, `1h` — gates **entries only**; exits/reversals are exempt and act immediately for loss-control; inert in `bar` mode). In any non-observe mode (`paper`/`dry_run`/`live`) a **`1m` default cooldown applies when `cooldown` is omitted** (so a tick strategy can't hammer the venue or the public data feed on entries; `observe` has no floor). Use `tick` for prompt, change-driven entries; `bar` for stable once-per-bar evaluation.
- `metric_band_rule` — a deterministic TA hysteresis rule (no LLM, no event-watch): per-side metric condition trees over the shared selector (cross-market operands supported — see below), `long.enter`/`long.exit` and `short.enter`/`short.exit`, persisted as a market-data regime (`flat`/`long`/`short`). **A side is optional: omit `long` or `short` entirely for a one-sided band (the omitted side never trades — do NOT fabricate a never-firing guard, which is rejected); at least one side is required, and a side is always enter+exit together.** From flat, exactly one fired entry enters that side; simultaneous long+short entries stay flat as ambiguous. While long or short, the exit condition is evaluated first, and exit moves to flat before any later opposite-side entry. This is the right shape for RSI bands and Bollinger-style two-threshold systems. Author it through `signal_create_metric`'s `long`/`short` side objects (the CLI's JSON condition flags: the signal skill's §"CLI equivalents"). `eval: bar` evaluates once per closed bar; `eval: tick` evaluates every daemon tick on the forming bar and acts only when the persisted regime changes, with the same entry-only `cooldown` semantics as `metric_level_rule`.

**Per-operand selectors (metric kinds) — cross-market conditions, bar mode only.** A metric operand normally inherits the signal's one shared `selector`; an operand MAY name its own `selector` to read a DIFFERENT market (a cross-market comparison like BTC price vs ETH price, or "conditioned on BTC+SOL, execute on XRP"). In **bar mode** (the default) these evaluate live and backtest: the shared `selector` is the CLOCK — evaluation fires at each close of its bar, and every foreign operand reads its OWN last closed bar as of that instant (a 1d operand inside a 1h rule holds one value across the day; a foreign bar closing after the clock instant is invisible — the same look-ahead rule as the home market's forming bar). An operand selector's omitted `interval`/`quote` default to HOUR/USD — they do NOT inherit the shared selector's values. Freshness is trust-latest: no staleness gate; a market's fetch failure surfaces exactly like today's single-market failures (a failed row abstains-and-holds with the market named in `last_error`; a whole-fetch failure is a tick error with cooldown backoff). In **tick mode** selector-bearing conditions stay deferred: the view abstains ("per-operand selectors are not evaluated in tick mode") and backtests of tick specs are refused anyway. The signal create tools and `signal_edit` return a `warnings[]` note naming the cross-market operands and their sampling rule.

More signal kinds — and composite/hybrid fusion across signals — are arriving; any signal feeds the same sizer through `{direction, conviction}`, so the strategy workflow is unchanged.

## Run modes

The rungs — observe, paper, dry_run, live — what each needs and does; strategies are daemon-native, with no foreground run command.

Strategies are **daemon-native**. You author durable specs (a signal and a strategy — and, for an event-driven signal, an event-watch), arm them, and the running daemon evaluates every enabled strategy each tick. There is no foreground run command — execution happens only inside `om run` / `om service`. The rungs: `observe` (walletless, never trades), `paper` (walletless simulated account — a persistent book the fills mutate), `dry_run` (reads the real wallet, simulates), `live` (routes through the venue's capped execution path).

**Pairing a wallet is the user's step, and only `dry_run` and `live` need one.** The agent authors specs only — it never sets secrets, never pairs a wallet, never starts the daemon; those steps capture credentials, which are the user's to hold. When the feed, signal credentials, wallet, or daemon are missing for the mode the user asked for, route them to the exact `om setup` / `om config` / `om service install` command; call `system_status` when you are about to claim something is or is not configured.

| Mode | Wallet | Behavior |
| --- | --- | --- |
| `observe` | none | Public market reads only, assumes flat, never places. The default for an **unpinned** (research) create. |
| `dry_run` | required | Reads the paired wallet's real capital + position and reports the order as SIMULATED — a per-tick mirror of what live would do. Never places, persists no position state of its own. (the CLI accepts `dry-run` as an alias.) |
| `paper` | none | A walletless simulated account: a persistent per-strategy book (default $10k seed; `daemon.paper.starting_cash` at create) that simulated fills mutate and the next tick reads — flips close the paper position, capital compounds, TP/SL/time-stop fire against the book at live marks, and a per-fill taker fee is debited (HL ~4.5 bps; PM 0; market_data 5; `daemon.paper.fee_bps`, editable as `paper_fee_bps`). The default for a **pinned** create with no explicit mode (the defaulted mode is echoed in the result's `warnings[]`). Answers "would this strategy make money?". `strategy_show` renders the book; `strategy_paper_reset` is the ONE destroyer of a paper P&L record (confirm-gated; refuses over standing stranded/close-park evidence — `force` acknowledges the venue state is handled); `remove` drops the book. Pre-v3 specs that said `paper` were migrated to `dry_run` (the old wallet-bound behavior). |
| `live` | required | Same decision core as dry_run, then routes the order through the venue's capped execution path. Places real orders. |

## Sizer modes and policies

Transitions: conviction, always_in, single_sided; the neutral and reversal policies with per-kind defaults, the flip threshold, and the five-stances table.

A mode decides **transitions** — what a neutral or opposing view does to what you already hold. It does not decide size; that is `scale`.

| Mode | On a **neutral** view | On an **opposing** view while holding | Target range |
| --- | --- | --- | --- |
| `conviction` (`on_neutral`, `on_reversal`, `flip_threshold`) | per `on_neutral` — the policy-driven mode; see the policy table | per `on_reversal` — see the policy table | `[-1, +1]` |
| `always_in` | **hold** — a neutral view never exits | **flip, unconditionally** — no threshold gates it; passing `flip_threshold` here is a hard error | `[-1, +1]` |
| `single_sided` (`side: long\|short`, `on_neutral`) | per `on_neutral` — **defaulted by signal kind**: `hold` for `text_long_short`, `flatten` for metric | flatten; never crosses to the other side | `[0,+1]` or `[-1,0]` |

**`single_sided` is the answer to "one-sided, and don't close on noise."** Its `on_neutral` is stamped from the referenced signal's kind, so on a `text_long_short` signal it **holds through a neutral classification by default** — a classifier's neutral is *no information*, and noise must not move money — while still never taking the opposite side (an opposing view closes it to cash). On a metric signal it defaults to `flatten`, because a rule's neutral **is** its exit instruction.

⚠️ **`on_neutral: hold` on a signal that can never emit the opposing side has NO autonomous exit.** A `metric_level_rule` with `on_true: 1` (bull) and the default `on_false: 0` (neutral) emits only `bull` or `neutral` — under `hold`, *nothing* ever closes the position, and a `tp` / `sl` / `time_stop` exit is the only way out. That is the legitimate **entry-trigger** model (the rule fires the entry; risk management owns the exit) — but only *with* an exit attached. `create` prints a note whenever `on_neutral=hold` is set with no `tp`/`sl`/`time_stop`; do not ignore it.

⚠️ **`always_in` has the same hazard.** It holds through every neutral by definition, so on a signal that can never emit the opposing side (a `metric_level_rule` with the default `on_false: 0`) it enters once and **can neither flatten nor flip** — it just holds, forever. `create` warns for exactly this pairing (it stays quiet on a two-sided signal, where flipping forever is what `always_in` advertises). Give the signal a two-sided mapping (`on_false: -1`), pick a sizer that can flatten, or attach `tp`/`sl`/`time_stop`.

⚠️ **`metric_band_rule` + `on_neutral: hold` is REJECTED.** A band fires its exit *by* emitting neutral (the regime returns to `flat`), so `hold` would make the `long.exit` / `short.exit` conditions you authored dead. Leave `on_neutral` at its `flatten` default there.

**`on_reversal` is also inert behind a band signal.** A band never flips in one step: it always returns to `flat` (its exit condition) before entering the opposite side, so the sizer never sees a *held-position* opposing view — and the flip-vs-`close_only` distinction only matters on exactly that direct opposing view. The policy is still accepted and stamped (the metric default is `flip`), but it is never consulted; the band's own regime does the transition.

**Conviction policies.** `conviction` mode carries two deterministic policies, **defaulted from the referenced signal's kind and stamped explicitly into the spec at create** (readable in `strategy_show`; override in `sizer.config`):

| Policy | Values | `text_long_short` default | metric default |
| --- | --- | --- | --- |
| `on_neutral` | `flatten` = a neutral view closes to cash; `hold` = a neutral view keeps the position | `hold` (a classifier's neutral is no-information — noise must not move money) | `flatten` (a rule's neutral IS its exit instruction — band exits depend on it) |
| `on_reversal` | `flip` = an opposing view crosses to the other side when conviction ≥ `flip_threshold` (default 0.7; below → close to flat); `close_only` = an opposing view ALWAYS closes to cash, never a one-step flip | `close_only` (never cross zero on a misread headline; a FRESH opposing event while flat then enters the other side) | `flip` (rules emit full conviction; their reversals are deliberate — note under `close_only` a metric rule's persisting direction is deduped after the close and re-enters only when the direction changes anew, whether the close fills same-tick or parks pending settlement) |

**`flip_threshold` requires `on_reversal: flip`, and exists only on mode `conviction`.** Both are hard rejections — passing it with `close_only`, without an explicit `on_reversal`, or on any other mode is an error at create. (It used to *imply* `flip` when passed alone, which silently converted a `text_long_short` strategy off its `close_only` default; and non-conviction modes used to accept it and throw it away.) Note it is also **inert behind a metric signal** — metric kinds pin conviction to 1.0, so any threshold in `0..1` is always cleared and the flip is never gated; `create` prints a note if you set one there. **`on_reversal` exists only on `conviction`** (rejected on other modes — `single_sided` never crosses and `always_in` always flips); **`on_neutral` exists on `conviction` AND `single_sided`** (rejected on `always_in`, which holds through a neutral by definition). **Map the user's intent, don't guess**: "get out whenever there's no clear signal" → `on_neutral: flatten`; "reverse automatically on opposing news" → `on_reversal: flip`; "one-sided, but don't close on noise" → `single_sided` (its `hold` is already the default on a text signal); otherwise omit and let the kind default apply. Note `hold` + `close_only` (the text default) has NO autonomous exit except an opposing view — pair it with `tp`/`sl`/`time_stop` for loss control (create prints a note when none is set).

#### One signal, five stances

Setup: `scale: fixed`, capital `{source: fixed, amount: 1000}`, no `min_confidence`, and the default flip threshold of 0.7 (do **not** pass `flip_threshold` explicitly alongside `close_only` — that combination is rejected at create). Every strategy starts flat. Numbers are the target weight (`+1.0` = fully long the base; `0` = cash).
Views, in order: **1)** bull 0.9 · **2)** neutral · **3)** bear 0.5 · **4)** bear 0.9 · **5)** bull 0.8

This is a config-level truth table, so the same view sequence is run through all five stances. Treat the fractional convictions as illustrative: only `text_long_short` actually varies its conviction (metric kinds pin it to 1.0), so a metric rule can never produce the sub-threshold reversal at tick 3.

```
always_in
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  hold — a neutral view never exits
 +1.0 → bear 0.5 → -1.0  flip — the threshold is never consulted
 -1.0 → bear 0.9 → -1.0  hold (same side)
 -1.0 → bull 0.8 → +1.0  flip

conviction on_neutral=hold on_reversal=close_only         (the text_long_short default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  hold — a classifier's neutral is no information
 +1.0 → bear 0.5 →  0    close to cash — close_only NEVER crosses in one step
  0   → bear 0.9 → -1.0  enter short — a FRESH opposing view arriving while flat.
                         ** close_only is NOT one-sided: it blocks a one-step flip,
                            not a two-step reversal. It DID take the short. **
 -1.0 → bull 0.8 →  0    close to cash

conviction on_neutral=flatten on_reversal=flip            (the metric default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  →  0    close — a rule's neutral IS its exit instruction
  0   → bear 0.5 → -1.0  enter short — an ENTRY from flat, not a flip
 -1.0 → bear 0.9 → -1.0  hold
 -1.0 → bull 0.8 → +1.0  flip — opposing, and 0.8 ≥ 0.7 clears the threshold
                         (at 0.5 it would close to 0 instead — "close first")

single_sided side=long on_neutral=hold                    (the text_long_short default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  → +1.0  HOLD — an irrelevant headline does not close the position
 +1.0 → bear 0.5 →  0    close to cash — the opposing view still flattens...
  0   → bear 0.9 →  0    ...and it NEVER shorts. This is the true one-sided stance.
  0   → bull 0.8 → +1.0  re-enter long

single_sided side=long on_neutral=flatten                 (the metric default)
 flat → bull 0.9 → +1.0  enter long
 +1.0 → neutral  →  0    CLOSE — a rule's neutral IS its exit instruction
  0   → bear 0.5 →  0    stays flat — never shorts
  0   → bear 0.9 →  0    stays flat
  0   → bull 0.8 → +1.0  re-enter long
```

**Rules the example depends on:**

- `flip_threshold` gates a **flip out of a held position**. It never gates an entry from flat.
- `close_only` blocks a **one-step flip**, not a reversal (the routing row's note). On the text lane every accepted event is fresh, so re-entry is immediate, as in the example; on the metric lane a *persisting* rule direction is deduped after the close, so re-entry waits for the direction to change anew.
- `on_neutral: hold` governs **neutral views only**. It never stops an *opposing* view from acting — under `single_sided` an opposing view still flattens.
- `always_in`'s flip is **unconditional** — no threshold gates it, and passing `flip_threshold` there is now a hard error rather than a silently-dropped flag.
- A view below `min_confidence` is a **skip**: hold current exposure, in every mode. Never a flatten.
- An **abstain** (a metric signal whose data isn't ready yet — conviction 0, not a neutral) is likewise a hold, never a flatten.

## Magnitude, capital, and leverage

Sizing: scale, capital sources and equity, leverage clamps, min-confidence, venue-specific flip execution, and what edit cannot change in the sizer.

The sizer object is five fields: `config` (the mode above), `scale`, `capital`, `leverage`, `min_confidence`.

- **`scale`** — `fixed` (full weight) or `conviction` (size by the view's conviction value). Orthogonal to the sizer `mode`, despite the shared word: mode picks the *transition*, scale picks the *size*. Note both metric kinds pin conviction to 1.0, so `scale: conviction` is a **no-op** behind a metric signal — it only does real work behind `text_long_short`.
- **`capital.source`** — `fixed` (+ `capital.amount`, resolves to `min(amount, available)`), `wallet` (the whole equity), or `fraction_of_wallet` (+ `capital.fraction` 0..1). **`available` is EQUITY, not free cash** — free cash *plus the held position's equity contribution*. That contribution is the position's **notional** for fully-paid holdings (Polymarket shares) but only its **posted margin** on a leveraged perp (the unrealized PnL is already inside the venue's free-capital figure). So `fixed` shrinks below `amount` only on a real mark-to-market loss, not merely because cash was deployed. `observe` **requires** `fixed`; the wallet-shaped sources are rejected there.
- **`leverage`** — perp venues only, `1..100`, omitted ⇒ 1×. Rejected above 1 on Polymarket, on a `market_data` pin (no margin model), and in `observe`. Backtests model no margin, and neither backtests nor paper model funding or liquidation: a leveraged result scales in exposure, never in liquidation risk (a leveraged sizer refuses to backtest outright — the research skill's `leverage_unmodeled`). `base = capital_base × leverage`, so under leverage the capital base is *margin committed*, not exposure. The strategy never writes the venue's setting — it sizes within it, and **the clamp only binds on a position you already hold** (that is where the venue surfaces its setting). **Opening from flat sizes to the FULL strategy leverage**, so if the coin's venue setting is lower the order is **rejected at execution** rather than quietly downsized — `strategy_create` prints a note about this. Editing leverage does **not** re-size a held position: the new value applies on the next fresh acting evaluation (to re-size now: `apply_to_position` with only sizing fields, on the user's confirmed yes). Sizing-only calls: an edit that also changes a behavioral field stamps the identity and re-plans the held position with the new sizing immediately.
- **`min_confidence`** — the confidence acting gate, on every mode. It is the strategy's only confidence knob: signals carry none.

Then `target_qty = (target_weight × base) / price`, and the order is the delta `target_qty − current_qty`. An unpriceable mark (`price ≤ 0`) is a **no-op, never a flatten**.

**Flip execution is venue-specific.** On Polymarket a flip is two sequential legs (SELL the held outcome, then BUY the target outcome). The BUY is submitted **only if the SELL comes back `filled`**; on any other status (`submitted`, `blocked`, `rejected`, `error`) the sequence stops and the BUY is never sent, so the flip does not complete. **Where that leaves you depends on the SELL, and one branch is dangerous:** a `blocked` / `rejected` / pre-submit `error` SELL placed *nothing*, so the strategy **still holds the OLD side — fully exposed to the very view it just reversed against**. A `submitted` SELL parks pending settlement and resolves to flat. Either way the target side is never entered; the next tick re-plans from actual holdings. On Hyperliquid a perp flip is **one netting order** that crosses zero — no two-leg sequence, so this failure mode does not exist there.

**`edit` cannot change the sizer's shape.** *Within the sizer*, only `min_confidence`, `leverage`, and `capital` (the whole object — `source` with its `amount`/`fraction`) are patchable; changing `mode`, `scale`, or any conviction policy requires remove-and-recreate. Capital swaps as a **whole object** (switching source needs the matching value and drops the old one; `observe` still requires `fixed`), and like leverage it is **deferred for a held position**: editing capital leaves what you already hold as-is — the new base applies on the next fresh acting evaluation (to re-size now: `apply_to_position` with only sizing fields, on the user's confirmed yes — the daemon places the delta on its next heartbeat; the deferral is sizing-only — mixing in a behavioral field re-acts and applies the sizing immediately). (Outside the sizer, `edit` freely patches label, run-mode, TP/SL/time-stop, notify-channel and paper fee; see the edit section below.)

⚠️ **Create the signal BEFORE the strategy.** With an unresolvable signal slug `create` cannot read the signal's kind, and two things go wrong:

- **Every `metric_band_rule` rejection stops firing** (both mode `always_in` and `on_neutral: hold`), because `create` needs the signal's kind to apply them. The daemon still refuses to trade such a strategy on every tick — it just does so *after* you have already created it. Nothing warns about *the band rejection itself* — `create` cannot know the kind. You may still get the *"the signal does not resolve yet, so this cannot be checked"* note, but that one is about the **no-autonomous-exit** analysis and it fires **only when no `tp`/`sl`/`time_stop` is set**. Attach a managed exit and it is suppressed (correctly — you *do* have an exit), so an operator who did the safe thing gets **no warning at all here** and only finds out at the daemon. Create the signal first and every check is definitive.
- The conviction policies are stamped from the *fallback*: `on_neutral: flatten` + `on_reversal: flip`. For a `text_long_short` signal, that is the **exact inverse** of its intended default (`hold` + `close_only`), and **nothing ever re-stamps it**, because `edit` cannot patch the conviction policies. The strategy will flatten on every neutral classification and one-step-flip on a single misread headline. `create` returns a warning naming exactly which policies it defaulted; it rides the result (`warnings`), so it reaches tool callers and the CLI alike.

## Order routing

What the daemon actually places: the per-venue taker order forms, and why nothing a strategy sends ever rests on the venue.

Every strategy order is a marketable taker order — Polymarket FAK (fill-and-kill), Hyperliquid market IOC. It crosses the spread at the opposite top-of-book price and cancels any unfilled remainder; a strategy order never rests on the venue. There is no order-type knob (resting GTC orders remain available on the manual order lane — the orders skill).

## Workflow when a user wants a strategy

The create path end to end: discovery, event-watch, signal, strategy with derive-disclose defaults, the backtest offer, daemon check, verify, ask-before-arm.

### 1. Discovery

Confirm the prerequisites for the requested run-mode and signal kind, and route any missing setup to the user. `observe` and `paper` never pre-flight — proceed once the signal's inputs exist and let a typed error name anything missing. `dry_run`/`live` are the exception: check `system_status` once here and confirm the venue is paired before the create — the create names the wallet pairing, and the confirmation is never spent on an unpaired venue.

### 2. Create (or reuse) the event-watch — for an event-driven signal

A `text_long_short` signal reads an event-watch; metric signals read market metrics via the data API (no event-watch). Create the watch with `event_watch_create` over the user's configured data vendor and keep it enabled (the daemon subscribes to enabled watches). The `stream_ref` names the vendor's adapter — load the event-watches skill via `skill_read` for the per-vendor shape and lifecycle.

### 3. Create the signal

Author it per the signal skill — `skill_read signal`, signal.md §"Quick recipes" carries a worked tool call per kind (text over an event-watch; a level rule; a hysteresis band; the identity-guarded edit). Decisions to make here: two-sided rules set `on_false` explicitly (a golden cross's death side); prompt change-driven entries use `eval: tick` with a `cooldown` (entries only — exits stay exempt); multi-param indicators (`macd`, `bb_*`, `stoch_*`) and compound conditions go through an explicit `params` object or `condition` tree. Discover metrics and their params with `metric_list`.

### 4. Create the strategy

It is **created disabled by default** (nothing trades until you arm it) — the one exception is a paper ask that says trade / run / arm, which may pass `enabled: true` and land armed in paper.

**Derive, disclose, override — do NOT interrogate the user.** Create immediately with the defaults for everything the user did not specify, then read the resolved spec back in ONE compact block so they can correct anything. Never ask upfront questions about sizing, capital, venue, or indicator parameters; the only decisions that warrant a question are (a) real money — arming `dry_run`/`live`, wallet-sourced capital — and (b) a genuinely unresolvable market reference. The defaults:

| Knob | Default when unspecified |
| --- | --- |
| `market` | **OMIT — unpinned research strategy.** Pin at create only when the user names a venue/market or asks to trade. |
| `sizer` | OMIT — resolves to conviction mode, conviction scale, fixed $10,000 (the backtest's own defaults, so backtests describe the real strategy). `single_sided` only on explicit "never short"-style language. |
| exit | OMIT — no kind stamps a managed exit (a metric rule's neutral/reversal IS the exit). A text/news strategy left without one gets the no-autonomous-exit note: relay it and offer a managed exit (`strategy_edit` `tp`/`sl`/`time_stop_secs`). Ratio asks ("r/r > 2") translate agent-side: `tp = k × sl`, plain fractions — no ratio field. |
| indicator params | The user's phrase supplies levels ("RSI under 30"); periods default to textbook values (RSI 14, MA cross 50/200, MACD 12/26/9, Bollinger 20/2). |
| cadence | From phrasing ("hourly"); else HOUR. |
| run-mode / enabled | `paper` when a market is pinned, `observe` when unpinned; disabled — never pass them unprompted; a defaulted `paper` mode is echoed in `warnings[]`. |

Every default the action resolves is echoed in the result's `warnings[]` — surface them verbatim; they are the disclosure. The readback is the override surface: the user corrects, you `strategy_edit`.

Unpinned research strategy, all defaults:

```json
strategy_create {"signal": "my-signal", "slug": "my-strategy"}
```

Pinned variant, only when the user asked to trade a specific market (a Polymarket pin carries the axis rule from the intro; pinned ⇒ the run mode defaults to `paper`):

```json
strategy_create {"signal": "my-signal", "slug": "my-strategy",
  "market": {"venue": "polymarket", "condition_id": "<CID>", "long_outcome": "Yes"}}
```

Note no `flip_threshold` is passed: 0.7 is already the default, and passing one *requires* an explicit `on_reversal: flip` (it would otherwise silently override a text signal's close-only default). Only pass it when the user actually wants conviction-gated flips.

**After the create lands, offer a quick backtest before arming.** One call: `backtest_run` with the new strategy's slug (the one-shot verb derives window, interval, costs, and time basis from what is stored, and returns the result against a buy-and-hold benchmark). It is the cheapest way for the user to eyeball whether the idea roughly behaves before any mode change; offer, do not auto-run.

**Replaying against another venue's series is gated.** A Polymarket market's series never pairs with a non-Polymarket strategy, and a Polymarket strategy replays only against its own condition's series (`asset_market_mismatch`); wrapping the same signal in an unpinned candidate to dodge the gate is not a replay of the strategy. Before any replay ask that names a venue or market different from the strategy's, read `skill_read("research", section = "Replaying a saved strategy")` — it carries the identity and price-axis rules and the flags per signal kind.

**Hand the chart URL over honestly.** The result's `chart` block carries the live-view URL — relay it. Read `chart.mode` before promising what the link shows: `strategy_panel` means a watching viewer has the Strategy Tester live; `panel+markers` means the run ALSO drew persistent fill markers because nobody was watching or the daemon session could not attach (`chart.markers_reason` says which) — those markers are relay-stored document content; `markers` means only the persistent markers landed (panel unavailable). The panel itself is stored server-side by the platform's payload store (best-effort write-behind) and replays to any signed-in viewer who opens the link, daemon or not; a running om daemon re-pushes anything the store missed. The full report is also on disk at `report_path` — cite it for anything the compact result dieted away.

### 5. Confirm the daemon is running

Strategies execute only under the daemon. Do not pre-flight for this: the daemon-down fact arrives as a typed error, or in step 6's `logs_tail`. If a typed error or a `system_status` you already have names the daemon down, route the user to `om service install` then `om service start` (run as a service, not foreground, so decisions land in `runner.log`). The agent cannot start it.

### 6. Verify the setup (still paused)

Confirm the wiring before arming — the strategy is still paused, so it is listed but not yet evaluated or trading: `strategy_list` (enabled=false, expected run_mode) · `event_watch_events` with `limit: 1` (the latest event landed; `data_mode: live` vs `backfill` = live push) · `logs_tail` (`[strategy] scanned=[...] evaluated=[...] skipped=[...]` plus the per-decision summary).

### 7. Ask whether to arm — never auto-arm

The arm-consent rule is the intro's — created disabled (a paper trade/run ask excepted, which may arm at create), `strategy_resume` only on the user's explicit yes, `dry_run`/`live` arming a capital-affecting confirmation. **This is also the pin moment for an unpinned strategy**: propose the market in the same breath ("Hyperliquid BTC perp, 1x — arm in observe?"), pin it on their yes, then resume — as tool calls. Pinning at arm-time does NOT re-default the run mode (defaulting happens only at create, so the unpinned create's `observe` stays); pass `run_mode: "paper"` in the same edit if the user wants the simulated book:

```json
strategy_edit {"id_or_slug": "my-strategy", "market": {"venue": "hyperliquid", "coin": "BTC"}}
strategy_resume {"id_or_slug": "my-strategy"}
```

A `live` strategy starts placing real orders once armed, and escalating INTO `live` (or into `dry_run`) disarms first — resume again after. Once armed, the daemon evaluates it **once per new accepted event** (for metric signals, once per bar of the selector interval, or — with `eval: tick` — every daemon tick, acting only when the direction/regime changes) and the decision shows in `logs_tail` (`[strategy] … evaluated=[…]` + a one-line summary); later ticks on the same input show `skipped=[...]` (runtime dedupe).

## Workflow when a user wants to pause, resume, edit, or remove a strategy or signal

Operating existing specs: the edit/apply split, pause leaves positions unmanaged, remove confirms, signal cascades, live escalation and downgrade, cohort consent.

The verbs: `strategy_pause` (disarm — preserves the spec + runtime history; HANDS-OFF: exits are NOT managed while paused) · `strategy_resume` (re-arm) · `strategy_edit` (patch label / `min_confidence` / `run_mode` / `tp`/`sl`/`time_stop_secs` — set or `clear_*` — / leverage / capital / notify) · `strategy_show` (spec + persisted daemon runtime) · `strategy_remove` (deletes the strategy and its runtime rows; raises the card) · `signal_show` (spec + consumers) · `signal_edit` · `signal_pause` (SEE THE CASCADE WARNING BELOW) · `signal_resume` · `signal_remove`. The pause/edit lifecycle as tool calls:

```json
strategy_pause {"id_or_slug": "my-strategy"}
strategy_edit {"id_or_slug": "my-strategy", "min_confidence": 0.6}
strategy_resume {"id_or_slug": "my-strategy"}
```

Signals now have the full lifecycle (`show` / `edit` / `pause` / `resume` / `remove`), gated for consumer safety. **These consumer relationships are surprising — call them out to the user before acting:**

- **`strategy_edit` has an edit/apply split for managed exits AND sizing:** plain `tp` / `sl` / `time_stop_secs` edits update the spec for the next entry/flip only; an already-held position keeps its frozen active contract unless the edit carries `apply_to_position` on the user's confirmed yes. The same flag with ONLY sizing fields (leverage / capital) consents an immediate re-size instead — the approved save stamps the dedup identity and the daemon places the delta on its next heartbeat at the then-current price (one concern per apply; mixed sizing+exit applies are refused, and the result's disclosed drift/delta are advisory, not the execution price). `clear_tp` / `clear_sl` / `clear_time_stop` unset a trigger (spec-only; refused with `apply_to_position`) — clearing the LAST trigger while a position is held retires the persisted policy on the next tick (native brackets canceled, position left to the signal), so warn the user before a full clear mid-hold.
- **`strategy_remove` raises the approval card** (naming any open position and resting native bracket oids that would go unmanaged). `force` additionally cancels resting Hyperliquid TP/SL children first — the open position itself is never touched.
- **Several strategies are ONE call, one card.** `strategy_remove` and `strategy_pause` take `ids` (id-or-slug) beside `id_or_slug` (`om strategy remove <id> <id>`, `om strategy pause <id> <id>`): the card lists every member with its mode, held position and resting brackets, and a live member holds the card off auto mode. `force` with `ids` refuses the whole call (`strategy_batch_force_refused`: venue signing per member is a single-strategy act, so a forced remove stays single-id). Never loop single-id calls for a set: that raises one card per strategy.
- **`strategy_pause` while a position is held leaves it UNMANAGED.** Pause means hands-off: the daemon places no orders while paused, so TP/SL/time-stop do NOT fire (on live Hyperliquid, already-resting native brackets keep enforcing venue-side; the software time stop and every Polymarket/paper exit stop). The pause output carries a `held_position` disclosure — surface its `note` to the user verbatim. To stop trading while keeping protection: flatten first, or clear the exit criteria (`clear_sl` etc.) and manage the position manually, or `strategy_remove` after flattening.
- **`signal_edit` can patch metric trigger structure in place.** For `metric_level_rule`, patch the simple-condition pieces (`metric`, `period`, `op`, `threshold`, `compare_metric`, `compare_period`, or the selector fields). For `metric_band_rule`, replace individual side conditions (the `long`/`short` enter/exit trees), plus the selector. Compound `metric_level_rule` trees are edited by replacing `condition`; the flat shorthand fields intentionally reject those trees.
- **`signal_edit` can change a `text_long_short` signal's context policy.** The `context` fields (`overview`, `recent_events`) **merge** onto the current policy (only supplied fields change); `clear_context` removes it (back to isolation). Because context feeds the `producer_id`, any of these is an **identity change** (see below).
- **`signal_remove` / `signal_edit`** are **refused** (RESTRICT) — `remove` while any strategy references the signal; `edit` while an acting-mode (`paper`/`dry_run`/`live`) strategy references it (observe-only consumers are named in `warnings[]`, not gated), or when the change touches the **model pin, the `topic`, or the context policy** (each recomputes the signal's `producer_id` and breaks replay comparability). The `topic` is a `producer_id` input because it defines the thesis and drives how context is interpreted; `event_watch` (the data source) is NOT — re-pointing it is ordinary tuning. Pass `force` to proceed (only on the user's explicit yes). A forced `remove` leaves those strategies dangling; the daemon then **auto-pauses** each on its next tick. A rule/selector edit keeps the same `producer_id`, but already-emitted records still reflect the prior rule, so mention that comparability caveat. Call `signal_show` first to see the consumers.
- **`signal_pause` CASCADES:** on the next daemon tick, every strategy referencing a paused (or removed) signal is **auto-paused** (persisted `enabled=false`) and sent a warning notification — and **`signal_resume` does NOT re-enable those strategies.** After resuming the signal, re-arm each consumer with `strategy_resume`. Warn the user of this before pausing a referenced signal.
- **A `strategy_edit` to `run_mode: live` or `run_mode: dry_run`** never starts live trading or real-wallet reads on its own: escalating a strategy from a walletless mode **into `live` or `dry_run` disarms it** (persists `enabled=false`), so you must explicitly **`strategy_resume`** — which cards for both modes — to begin. This is scoped to the escalation transition — tuning an already-live strategy (a label/TP/`min_confidence` edit, or re-passing `run_mode: live`) leaves `enabled` untouched and does NOT halt a running live strategy; de-escalating (live → dry_run/paper/observe) also leaves it enabled. Tell the user the strategy is set for that mode but dormant until they resume it. On a `market_data` pin the escalation itself is refused typed (`strategy_market_paper_only`) — going live means recreating pinned to a real venue.
- **Downgrading a HELD live strategy away from live is REFUSED** (`strategy_live_position_held` — the position would lose every software exit, and the walletless daemon would false-record an exit for a still-open position). `force` bypasses the guard and mirrors `strategy_pause` at the venue: the position and any resting native brackets are left EXACTLY as they are (Hyperliquid keeps enforcing its native TP/SL) — but **unlike a pause it will NOT resume into management**; the user must flatten manually. Surface the returned warning verbatim and never suggest `force` casually — flattening first is the safe remediation.
- **One live strategy per (venue, market, wallet) — anything else needs the user's explicit consent.** A cohort-forming call (create, a run-mode escalation, a market pin on a live strategy, resume, a marketplace install's later arming) refuses with `same_market_consent_required` unless it carries `allow_same_market: true`; when the conflict check could not read every strategy spec, a cohort-forming call landing live+pinned refuses with `same_market_unverified_consent_required` unless it carries `allow_unverified_cohort: true` (a SEPARATE consent — neither flag satisfies the other's gate; prefer telling the user to repair the unreadable spec for a real answer); on chat surfaces the approval card carries the matching consent — never set either flag from your own judgment, only after the user explicitly agreed to the named conflict (or to proceeding without a verified answer). The configuration is unsupported: **we cannot guarantee correct behavior when multiple strategies act on one netted position** — while a cohort stands a fired TP/SL/time-stop MAY close the whole netted position, the sibling's exposure included, at a price it did not choose; native brackets size to the net, not each strategy's own share; P&L can misbook; and after a crash the crash-heal re-arms exits for neither sibling (a position the strategy's own filled receipt explains re-books on the next pass and its exits re-arm; the durable gap is a position no om receipt explains). The fired close pages the sibling and the crash-heal exclusion notifies (each held for `system_status` on a channel-less install), but the misbooking is silent — the per-strategy figures just read wrong. Consents are journaled (`strategy_history`). What lifts the cohort state is removing a sibling or downgrading its run mode — pausing does NOT (a paused live spec still counts). The crash gap has a consent-time posture (`cohort_crash_policy`: `flatten` | `hold`, default hold, journaled with the consent): under unanimous `flatten`, om closes the whole naked net (reduce-only) after ~3 confirming sweeps and pages; `hold` pages and waits. Setting `flatten` arms an autonomous close, so it raises an approval card — never set it from your own judgment, only after the user explicitly chose it.
- **Arming over a position the strategy did not open needs consent too** (`existing_position_consent_required` / `position_unverified_consent_required` → `allow_existing_position: true`, same ask-the-user-first rule). The sizer trades `target − venue_position` with no provenance: a foreign position is trimmed, extended, or closed as the strategy's own on its first evaluation, and its value inflates the sizing base. This is the enforced edge of the general rule: **any trading om did not place — manual orders, the exchange UI, another bot — changes the position a live strategy sizes against**, at any cohort size including one.
- **A live level rule is a standing reconciler against manual intervention.** A `metric_level_rule` strategy re-enters over the user's deliberate manual close within a tick while its condition holds. Tell the user to pause the strategy BEFORE intervening by hand.

## Workflow when a user wants to inspect what a strategy is doing

Reading what a strategy decided: `strategy_list`, `logs_tail` (service-only), and `event_watch_events` for the event-watch's latest events.

- `strategy_list` — which strategies exist, enabled state, and run_mode.
- `logs_tail` — the daemon's per-tick `[strategy] …` lines plus a one-line decision summary (view, sized order) per evaluated strategy. This is the primary window into what a strategy decided; it requires the daemon running as a service.
- `event_watch_events` — what an event-driven signal last saw.
- `strategy_show` with `live: true` — the venue position beside the exit distances, plus `market_clock` on a Polymarket pin: the CLI renders a `resolves in` countdown row while the market still trades and a `market` row once it has settled.
- `strategy_history` (`om strategy history`) — the durable event timeline. A row a cached classifier verdict commanded carries `decision_source` (`hit`, `computed`, `coalesced`) in `--format json` and renders as `verdict <source>` in the text table; a row no cached verdict stands behind says nothing about a cache.
- `om memory list --strategy <id>` — the notes an exit-wake turn wrote for that strategy, kept in its own partition rather than the shared store.

## Backtesting a strategy

Backtests route to the research skill: backtest_run for saved slugs, backtest_spec for your own unsaved candidates, package_try for registry templates.

Backtests are the research skill's job: `skill_read research` documents `backtest_run` (the default one-shot verb: saved slugs only) and `backtest_spec` (explicit windows/costs and UNSAVED inline candidates). Two routing facts that live here because they bite strategy authors:

- **An unsaved idea backtests via `backtest_spec` with an inline `candidate`** ({strategy, signal?} in the authoring shapes of `strategy_create` and the signal create tools); nothing is persisted, and a winning candidate is creatable verbatim — except a `constant` signal, which is replay-only (the kind is retired from the create surface; re-author it as a metric/text kind to trade the idea).
- **A registry strategy template is not an inline candidate.** `package_try` — the marketplace funnel's default — backtests the tuned template candidate and mints its install token; `backtest_spec` is only for manual replay knobs on it.
- **Authoring the candidate's signal spec?** The per-kind condition shapes and worked JSON examples are in `skill_read("signal", section = the kind name)` and its signal.md §"Quick recipes" (one worked call per kind).

## Behaviors to follow

Operating habits beyond the intro's guardrails: run the daemon as a service, report resolved params, reuse before create.

- **Run the daemon as a service**, not foreground, whenever the user needs to read decisions — only the service writes `runner.log` for `logs_tail`.
- **Report the resolved params after every create** — signal, market + long-outcome, sizer mode (+ flip-threshold/side), scale, capital, run-mode, enabled — so the user sees exactly what was set or defaulted.
- **Reuse or list existing specs** (`strategy_list` / `signal_list` / `event_watch_list`) before creating, to avoid duplicate-slug errors.

The rest of the follow-list is the intro's guardrail block (arm only on the user's verb or explicit yes, consent flags never yours, the signal before the strategy, derive-disclose — no sizing interrogation) plus §"Run modes" and the create tool's run-mode field (omit it for the default).

## Behaviors to avoid

Pitfalls beyond the intro's guardrails: no foreground runs, no expecting trades before armed-and-running.

- **Don't reach for a foreground run command** — there is none; strategies execute only inside the daemon, and a foreground daemon's output never reaches `logs_tail`.
- **Don't expect a created strategy to trade** before it is resumed AND the daemon is running.

The rest of the avoid-list is the intro's guardrail block: no arming beyond the user's verb or yes, no unprompted `live`; and §"Run modes": no secrets or wallet pairing.

## Errors

Every typed refusal on the strategy surface, by family — shape, lookup, lifecycle, consent, paper reset, remove, held-position edits — plus the disclosures and cards.

Sections above may *name* a code; this glossary defines them. Rows marked † are reachable only behind a held position, resting venue orders, or daemon-written runtime state — they cannot fire on a fresh clean-room spec.

**Create/edit shape:**

| Code(s) | When it fires | Recovery |
| --- | --- | --- |
| `invalid_strategy_create` · `invalid_strategy_edit` | the input (or the edited spec) fails validation — the message names the bound | fix exactly the named field |
| `invalid_strategy_slug` | slug not path-safe | lowercase/digits/hyphens, ≤80 chars — or omit it |
| `invalid_strategy_capital` | capital fields mismatch their source (fraction-on-fixed, fixed-without-amount, wallet-takes-none), or a wallet-shaped source in observe | pass the matching source+value pair; observe requires `fixed` |
| `invalid_strategy_leverage` | leverage above 1 on an unpinned spec, on Polymarket, on a `market_data` pin, or in observe | drop it, or pin a perp market in a wallet mode |
| `strategy_market_paper_only` | `dry_run`/`live` requested on a `market_data` pin — at create, edit, or a backtest candidate (no execution venue stands behind the pin) | stay in observe/paper, or recreate pinned to a real venue |
| `invalid_strategy_sizer` | `flip_threshold` without an explicit flip reversal policy (or alongside the close-only policy), or a band signal paired with `always_in` / an explicit hold-through-neutral | drop `flip_threshold` or set `on_reversal: flip` explicitly; behind a band signal leave `on_neutral` at its default |
| `invalid_strategy_paper_config` | `daemon.paper` fields off run-mode `paper` | drop them or switch the run mode |
| `notify_channel_unresolved` | notify requested with no configured (or no default) channel | name a channel, set a default, or create with notify off |

**Collisions and lookup:** `strategy_exists` · `strategy_slug_exists` (collision — different slug) · `strategy_unreadable_conflict` (the id's file is unreadable; create refuses to overwrite — different slug, file surgery is operator work) · `strategy_not_found` (`strategy_list`, confirm, retry) · `invalid_strategy_spec` (stored spec corrupt — surface the parse detail).

**Lifecycle and live-downgrade guards:**

| Code(s) | When it fires | Recovery |
| --- | --- | --- |
| `strategy_edit_empty` · `strategy_edit_conflict` | empty patch · set-and-clear of the same trigger in one edit | resend with one coherent shape |
| `strategy_market_pinned` | market patch on an already-pinned spec (pin-once) | remove and re-create |
| `strategy_unpinned` | an explicit run mode — or the paper knobs (`daemon.paper`) — with no pinned market | pin via `strategy_edit` with `market`, then arm |
| `strategy_live_position_held` † | leaving `live` while a live position is held | flatten first; `force` leaves the position UNMANAGED and never resumes management — user's explicit choice only |
| `strategy_live_holding_crossing` † | leaving `live` for **paper** while a close is in flight (observe/dry_run carry the latch through instead) | wait for settlement, then re-edit |
| `strategy_live_brackets_resting` † | leaving `live` with native brackets resting | cancel the named oids first, or the user explicitly accepts leaving them resting |
| `strategy_downgrade_state_split` † | a forced downgrade SAVED but the exit-state clear failed — partial state | check `strategy_show`; flatten manually or restore `live`; never retry blindly |

**Consent refusals (the flags are never yours to set — relay, ask, retry only on the explicit yes):** `same_market_consent_required` (a second live strategy would share one market/wallet → `allow_same_market`) · `same_market_unverified_consent_required` (the cohort scan could not read every spec → `allow_unverified_cohort`; the two consents are separate — neither satisfies the other, and repairing the unreadable spec is the better answer) · `existing_position_consent_required` † (arming over a position om did not place → `allow_existing_position`) · `position_unverified_consent_required` † (the venue position read failed at an arming edge → the same flag, journaled as unverified; prefer retrying when the venue is reachable). Consents apply to that one action and are journaled.

**Paper reset:** `strategy_not_paper` (the strategy is not in paper mode) · `strategy_exit_in_flight` † (managed exit pending — wait) · `strategy_stranded_holding` † / `strategy_close_park_standing` † (a REAL venue position or in-flight close stands unmanaged; flatten or restore `live` first — `force` only as the user's explicit acknowledgment) · `strategy_reset_latch_release_failed` † (rolled back — nothing destroyed, safe to retry).

**Remove and orphan state †:** `strategy_orphan_brackets` / `strategy_orphan_paper_book` / `strategy_orphan_holding` (a prior same-id strategy left brackets / a paper book / recorded holdings — inspect, cancel/flatten, `strategy_remove` the old id, or pick a different slug) · `strategy_orphan_force_uncancelable` (cancel the oids manually, then re-run WITHOUT force) · `strategy_brackets_not_hyperliquid` · `strategy_force_wallet_unpaired` (pair the wallet or cancel manually — nothing was removed).

**Held-position edits (`apply_to_position`, all † except the first two):** `apply_to_position_mixed_edit` (one concern per apply — exit fields OR sizing fields, nothing else; split the rest into a plain edit) · `apply_to_position_not_holding` (no position — a plain edit already covers future entries) · `_order_pending` / `_position_unavailable` / `_basis_unavailable` / `_mark_unavailable` / `_holding_clock_invalid` (state not readable or in flight — wait or inspect `strategy_show` with `live` for drift, then retry) · `_undecodable_children` / `_legacy_children` / `_multiple_native_children` (bracket state this build cannot safely identify — stop and report; never force) · `_trigger_not_representable` / `_trigger_breached` / `_time_stop_breached` (the requested trigger would fire immediately or cannot be represented — choose a value beyond the current mark, or the user closes intentionally) · `apply_to_position_live_read_required` (non-live modes have no venue reader — use a plain edit). Native-modify guards (`native_modify_unsupported_venue`, `native_modify_invalid_oid`, `native_order_not_resting`, `native_order_mismatch`, `native_order_kind_unconfirmed`, `trigger_price_missing`) mean the venue state has drifted from the record — report the mismatch verbatim and never retry with guessed values.

**Misc:** `invalid_strategy_history_cursor` (cursors are opaque — reuse `next_cursor` verbatim or drop `before`) · `invalid_options` (digest schedule needs `when`).

**Result-side disclosures (not errors — relay them):** `warnings[]` on create/edit/resume is the disclosure surface — surface it verbatim (defaulted sizer and policies, no-autonomous-exit, venue-leverage-below-strategy, cohort and consent journal notes, the Polymarket axis notes, the forced-downgrade retirement warning). `held_position` (+ its `note`) on pause — verbatim; a non-null `held_position_error` means the disclosure read FAILED and must never be rendered as "nothing at risk". On `strategy_show`: `last_error`, `last_skip_reason` ("why is it not trading"), `last_issue_note` (an operand fault while still acting), and the bracket-coverage fields. `strategy_list` carries a per-row `warning`.

**Approval cards:** `strategy_remove` and `strategy_paper_reset` raise cards; `strategy_create`/`strategy_edit`/`strategy_resume` card on the args-gated shapes (an enabled `live` or `dry_run` create, a `live` or `dry_run` resume, an edit that touches a live spec's exposure — leverage, capital, `apply_to_position`, `force` — or forms a same-market cohort, and the consent flags — the card IS the consent on chat surfaces). A bare escalation into `live`/`dry_run` lands disarmed and does not card on its own; the resume that arms it does. A declined card is the user's no — never retry it or route around it.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `strategy_create`
  - `market` — OMIT to create an unpinned research strategy (backtestable against any data asset — including ones with no execution venue, like US equities); pin later with strategy_edit when the user wants to arm it.
  - `sizer` — OMIT the whole field for the defaults: conviction mode, conviction scale, fixed $10,000 capital (matches the backtest default so backtests describe the strategy that exists).
  - `sizer.leverage` — Strategy leverage for perp venues (Hyperliquid), a number 1..100; omitted = 1x unleveraged.
  - `exit.track_target` — default true — When true (default), a FRESH acting evaluation re-sizes a held position toward its current target, so exposure tracks the view's conviction
  - `entry_freshness` — Omit for the defaults.
  - `slippage` — A named side states `ticks`, `frac`, or both; omit a side, or the whole block, for the defaults.
  - `wake` — Omit for no wake.
  - `wake.on_exit` — default false
  - `wake.mode` — default "propose"
  - `daemon.mode` — OMIT for the default — paper when a market is pinned, observe when unpinned — and tell the user which mode the strategy landed in; the result's warnings echo a defaulted mode.
  - `notify` — OMIT the field for default-on: create resolves the marked-default or sole configured channel
- `strategy_create` · `strategy_edit` · `strategy_resume`
  - `cohort_crash_policy` — 'flatten' = om closes the whole net (reduce-only) once the naked state is confirmed across ~3 sweeps, then pages; 'hold' (and absent, the default) = om pages and waits.
- `strategy_digest`
  - `channel` — schedule_set only: a configured channel name or id to deliver each edition to, 'default' for the home default, or 'none' to keep the digest local.
  - `limit` — list only: max editions returned (default 10).
- `strategy_edit`
  - `entry_drift_frac` — Entry-freshness gate (event-driven text_long_short signals only): new drift bound as a fraction of the stamped reference price (default 0.05, floored at one Polymarket tick).
  - `entry_max_age_secs` — Entry-freshness gate: new cap on how old the arming event may be at any entry attempt, integer SECONDS (default 600).
  - `clear_entry_freshness` — Remove both entry-freshness overrides so the gate falls back to its defaults.
  - `slippage` — Defaults: entry 2 ticks or 2%, exit 3 ticks or 5%.
  - `clear_slippage` — Remove the slippage overrides so orders fall back to the default bounds.
- `strategy_history`
  - `limit` — default 50
- `strategy_paper_reset`
  - `cash` — Omitted = keep the book's current starting_cash (or the default 10000 on a first seed).

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `strategy_create`
  - discloses `enabled`
  - discloses `daemon.mode` — Continuous run mode: observe (walletless decisions only) | paper (walletless simulated account — persistent book, simulated fills) | dry_run (real wallet reads, execution suppressed) | live (real capped execution).
  - discloses `warnings[]` — Advisory notes about the strategy just created. SURFACE THESE TO THE USER — they are money-relevant and there is no other channel that carries them. Possible notes: a stance with NO autonomous exit (nothing will ever close the position; only --tp/--sl/--time-stop can); trade alerts defaulted OFF because no notification channel is configured; a Hyperliquid coin whose venue leverage is below the strategy's, so the OPENING ORDER WILL BE REJECTED until it is raised; a Hyperliquid dry_run/live strategy with no paired account; a flip_threshold that is inert behind a metric signal; a signal that did not resolve, so its kind-derived policies were stamped from the fallback and nothing will ever re-stamp them; a same-market live cohort disclosure (2+ live strategies pinned to one market from one wallet); on a live pinned create, a notice that the same-market conflict check could not read every strategy spec file, so its answer is INCOMPLETE (the unreadable files could hide a live strategy on this market — reachable only through an explicit consent: allow_unverified_cohort, or allow_same_market when a named cohort formed over the partially readable store; an unconsented blind create refuses); an existing-position consent/journal note; or a first-strategy notice that the daily strategy digest was auto-scheduled (unbound — local until routed; when a destination is resolvable the note names it and the `schedule set` that routes there, so a surface can put the question to the user); or, on a Hyperliquid-pinned create, a note that the pinned coin — and, on a HIP-3 pin, the DEX — was stored under the venue's exact spelling, or that the spelling could not be verified against the venue and was stored as typed. Every Polymarket-pinned create also carries the standing verdict-to-outcome axis note (a LONG verdict buys the pinned long_outcome; a SHORT verdict buys the market's other outcome), plus, when the referenced signal resolves as text_long_short, a quote of the signal's own topic to check the axis against — or, when the referenced signal cannot be read, an explicit could-not-read notice instead of silence.
- `strategy_pause`
  - discloses `held_position`
  - discloses `held_position_error`
- `strategy_show`
  - discloses `spec.enabled`
  - discloses `spec.daemon.mode` — Continuous run mode: observe (walletless decisions only) | paper (walletless simulated account — persistent book, simulated fills) | dry_run (real wallet reads, execution suppressed) | live (real capped execution).
  - discloses `signal.spec`
  - discloses `referenced_signal` — found: `signal` is the referenced signal's spec. missing: the referenced slug no longer exists (every spec file was readable). unreadable: the signal store could not be fully read, so the reference is unresolved, not absent.
  - discloses `paper.cash_pnl_usd`
  - discloses `paper.cash_pnl_fraction`
  - discloses `paper.round_trips`

<!-- AUTO: END RESULT CONTRACT -->

## See also

Neighbouring skills, each loaded via `skill_read`: event-watches for the feeds, orders for act-now, research for studies and backtests.

- the event-watches skill (`skill_read`, name = event-watches) — create, configure (per data vendor), and inspect the event-watch that feeds an event-driven signal.
- the orders skill (`skill_read`, name = orders) — one-shot manual orders (act now, rather than wire a standing strategy).
- the research skill (`skill_read`, name = research) — correlational event studies / backtests over accepted event-watch rows.

## CLI equivalents

Every `om strategy` command form for shell users — flag spellings, worked create/operate shapes, and the generated command↔action mapping.

The shell lane has no eval coverage; these forms are review-verified.

```bash
om status --format json                  # the system_status read (the agent checks this only for dry_run/live)
om strategy list ; om signal list ; om event-watch list

# Create — the CLI always pins (an unpinned research strategy is tool-only)
om strategy create --signal my-signal --condition-id <CID> --long-outcome Yes \
  --slug my-strategy                     # pinned ⇒ run-mode defaults to paper

# Signal authoring forms live in the signal skill's CLI equivalents; a golden cross:
om signal create --kind metric_level_rule --symbol BTCUSDT --exchange BINANCE_FUTURES --interval DAY \
  --metric sma --period 50 --op gt --compare-metric sma --compare-period 200 \
  --on-true bull --on-false bear --slug sig-golden-cross

# Verify before arming, then arm (ONLY after the user says to)
om strategy list
om event-watch events <watch-slug> --limit 1 --include-raw-text
om logs
om strategy resume my-strategy

# Operate
om strategy pause my-strategy
om strategy edit  my-strategy --min-confidence 0.6
om strategy edit  my-strategy --clear-tp             # --clear-sl / --clear-time-stop likewise
om strategy edit  my-strategy --apply-to-position --tp 0.1 --sl 0.05   # held position, confirmed
om strategy edit  my-strategy --tp-price 0.72 --entry-slippage 3t   # absolute level (Polymarket) + a wider entry bound
om strategy edit  my-strategy --wake-on-exit --wake-mode propose    # record a thesis rewrite when an exit closes the position
om strategy show  my-strategy
om strategy remove my-strategy                       # prompts; --yes to script; --force cancels HL children
om signal pause my-signal ; om signal resume my-signal
om signal edit my-signal --period 28 ; om signal remove my-signal
```

Flag↔field spellings (edit-side names; on `strategy_create` they nest — `daemon.mode`, `sizer.min_confidence`, `exit.bracket.tp`/`sl`, `exit.time_stop.max_hold_secs`, `daemon.paper.starting_cash`/`fee_bps`): `--run-mode` = `run_mode` (the CLI also accepts `dry-run`), `--min-confidence` = `min_confidence`, `--tp`/`--sl`/`--time-stop` = `tp`/`sl`/`time_stop_secs`, `--clear-tp`-family = `clear_tp`/`clear_sl`/`clear_time_stop`, `--apply-to-position` = `apply_to_position`, `--allow-same-market`/`--allow-unverified-cohort`/`--allow-existing-position` = the consent fields, `--paper-cash`/`--paper-fee-bps` = the paper fields, `--tp-price`/`--sl-price` = `tp_price`/`sl_price` (an absolute venue price in (0,1) of the token the position HOLDS, Polymarket only; it sits beside the fraction form and whichever the price reaches first fires), `--clear-tp-price`/`--clear-sl-price` = `clear_tp_price`/`clear_sl_price` (independent of `clear_tp`/`clear_sl`), `--entry-slippage`/`--exit-slippage` = `slippage.entry`/`slippage.exit` (each takes `ticks` and `frac` — `3t`, `2%`, or both — and the wider binds; defaults entry 2t/2%, exit 3t/5%, and on Hyperliquid only `frac` binds), `--clear-slippage` = `clear_slippage`, `--wake-on-exit`/`--no-wake-on-exit` = `wake.on_exit`, `--wake-mode propose|autonomous` = `wake.mode`, `--clear-wake` = `clear_wake`, `--yes`/`-y` scripts a confirm, `--force` = `force`. The CLI `create` always pins — `--condition-id` + `--long-outcome` (`--venue` defaults to polymarket), `--venue hyperliquid --coin`, or `--venue market_data --exchange <ID> --symbol <SYM>`; an unpinned research strategy is tool-only (`strategy_create` without `market`), `om strategy edit` has no market flags (pin later with `strategy_edit` `market`), and tool callers state `market.venue` explicitly.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

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
- `om strategy list` (action: `strategy_list`) — List configured trading strategies (the persisted StrategyDefs), across every venue (Polymarket, Hyperliquid, market_data pins).
- `om strategy paper` — (bespoke; see narrative above)
- `om strategy paper reset` (action: `strategy_paper_reset`) — Reseed a paper strategy's simulated book: cash returns to starting_cash (or a new --cash), the open position and every recorded fill are DROPPED, and the runtime exit contract is cleared.
- `om strategy pause` (action: `strategy_pause`) — Disable daemon-native strategies by id or slug: `id_or_slug` for one, or `ids` for several in ONE call (one approval card covers the set; never a loop of single calls).
- `om strategy remove` (action: `strategy_remove`) — Remove daemon-native strategies by id or slug and clear their strategy runtime/outbox rows: `id_or_slug` for one, or `ids` for several in ONE call (one approval card covers the set; never a loop of single calls).
- `om strategy resume` (action: `strategy_resume`) — Re-enable one paused daemon-native strategy by id or slug.
- `om strategy show` (action: `strategy_show`) — Show one daemon-native strategy spec by id or slug, plus its persisted daemon runtime row (last run, last signal, last error), the paper book's simulated P&L (paper mode), and the live realized-PnL ledger block (net/gross/fees, round trips, venue cross-check drift, seeded-basis and anomaly disclosures) whenever live fills were ever booked.

<!-- AUTO: END COMMAND REFERENCE -->
