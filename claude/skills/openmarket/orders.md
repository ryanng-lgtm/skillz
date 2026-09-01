---
name: openmarket-orders
description: Place orders directly on a paired execution venue (Hyperliquid or Polymarket CLOB) via `om order place`. Use this skill when the user wants to act NOW — limit-bid a level, take a position, exit a position — rather than wire a condition-triggered alert with `on_fire.execute`. Covers Hyperliquid flags, JSON-stdin specs for both venues, venue account reads, sizing modes, bracket children where supported, and the preview/confirm pattern. Always shell to `om` for these actions — `om order place …` to submit, `om execute list` / `om execute summary` to inspect what landed. NEVER pass `--yes` unless the user explicitly says "submit it" / "no preview needed" / "yes do it" — preview-then-confirm is the safety contract. If the requested venue is not paired, route the user to `om setup hyperliquid` or `om setup polymarket` and stop.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - AskUserQuestion
---

# om orders

One-shot order placement against a paired execution venue. The execute pipeline (vault unlock, signing, builder code, daily ceiling, receipts, reconciler-replay) is shared with alert-triggered auto-execution — `om order place` is just a second producer feeding the same dispatcher.

Venue config keys (all set with `om config set <key> <value>`):

| Key | Default | Effect |
| --- | --- | --- |
| `execute:daily_ceiling_usd` | `10000` | Cross-venue auto-executed notional cap per UTC day, in USD. |
| `hyperliquid:builder_code` | `on` | OpenMarket's Hyperliquid builder code (2 bps max). On by default: orders carry it once the account has approved it at the venue, and `om setup hyperliquid` requests that approval automatically for main-wallet pairings. `off` stops orders from carrying builder metadata and stops setup from requesting the approval. |

v1 supports Hyperliquid and Polymarket CLOB. Hyperliquid has a quick flag form for common orders; Polymarket uses the JSON spec form so token references, TIF, and sizing stay explicit.

## When to use this skill vs `openmarket-alerts`

| User intent | Which skill |
| --- | --- |
| *"Buy $200 of BTC at 95k right now"* | **this skill** — one-shot order |
| *"Bid $200 of BTC at 95k and let it rest"* | **this skill** — one-shot limit order |
| *"Close my SOL position"* | **this skill** — one-shot reduce-only order |
| *"Buy $200 of BTC when it crosses 95k"* | **alerts skill** — alert with `on_fire.execute` |
| *"Watch BTC and tell me when RSI < 30"* | **alerts skill** — notification-only alert |
| *"Long BTC every time RSI < 30 (up to 3 times)"* | **alerts skill** — alert with top-level `fire_mode: "recurring"` + `on_fire.execute` + `caps.max_fires: 3` |

Rule of thumb: if the user's phrasing is **"do X"**, this skill. If it's **"do X when Y"**, the alerts skill.

If you're unsure, ask the user once via the structured-question tool — never guess. Misclassifying a "do X" as an alert wastes their time wiring a condition; misclassifying a "do X when Y" as an order skips the watcher and submits immediately.

## Required environment

Same as the alerts skill — the daemon must be reachable (or, for `om order place`, the CLI opens its own db handle so the daemon doesn't strictly need to be running):

| Var | Purpose |
| --- | --- |
| `OM_API_KEY` | OpenMarket Data API auth. Captured by `om init` (stored in `~/.openmarket/om.sqlite`) or exported. |

Execution credentials live in the local vault (`~/.openmarket/om.sqlite`, sealed with a master key at `~/.openmarket/vault.key` — mode 0600, same filesystem trust as channel tokens). Operator-managed. Reads, resolution and discovery never pre-flight: call `system_status` only when about to claim something about pairing state, and let a typed error name anything missing. Placing an order is the exception — it checks once before the preview (workflow step 1), because the preview names the network and the confirmation gate is never spent on an unpaired venue. Hyperliquid is paired with `om setup hyperliquid`; Polymarket execution requires the Deposit Wallet flow. Pair with `om setup polymarket` (auto-derives the signer's Deposit Wallet from the EOA), or deploy a fresh one headlessly with `om setup polymarket --create-deposit-wallet`.

## Discovery: is the venue paired?

Run this once before placing an order — the preview names the network (mainnet vs testnet), which only this check can supply, and a confirmation gate spent on an unpaired venue is a wasted yes. On every other path (reads, resolution, discovery) run it only when about to claim pairing state or after a typed pairing failure. It is a fast local read, never a venue call:

```bash
om status --format json
```

Inspect `venues[]`. If the requested venue is absent, stop and tell the user which setup command to run: `om setup hyperliquid` for Hyperliquid, or `om setup polymarket` (or `om setup polymarket --create-deposit-wallet` for headless deploy) for Polymarket. Do not try to place an order.

If `venues[]` contains `hyperliquid`, note the `network` (`mainnet` or `testnet`) — the same network is used for the order. If it contains `polymarket`, v1 is mainnet only; mention the wallet type in the preview when relevant ("Submitting on Polymarket mainnet from the deposit wallet.").

## Discovery: which instrument did the user mean?

When the user names an instrument in human form (a ticker they half-remember, a company name, a HIP-3 market, a prediction-market question), resolve it BEFORE authoring the spec. One call replaces knowing exchange enums, dex names, and hex token ids:

```bash
om resolve "SKHX on HIP-3" --format json
om resolve "will-the-fed-cut-rates-in-march" --outcome Yes --format json
```

The answer carries everything an order needs: `venue`, `exchange_id`, the canonical `symbol`, the HIP-3 `dex`, the Polymarket `condition_id` and outcome tokens, venue `constraints` (size decimals, max leverage, tick size, mid), the `order` object to paste straight into the spec, and `needs` (the fields still missing).

The binding rule is the same one the order path uses: **an exact name binds, anything fuzzy never does.**

- `bound` is non-null: that is the instrument. Use `bound.order` verbatim.
- `bound` is null: `candidates` is a ranked list and `message` says why. Show the user the candidates and ask; do NOT pick one yourself. A bare ticker carried by several HIP-3 dexes (`GOLD` lives on six) resolves to candidates on purpose.

`om order place` can do the resolution inline with `--instrument`, and refuses the same way:

```bash
om order place --instrument "SKHX on HIP-3" --side buy --size 250 --plan
om order place --instrument "will-the-fed-cut-rates-in-march" --outcome Yes --side buy --size 5 --plan
```

`--plan` prints the fully-populated spec and stops without submitting: use it to show the user the filled-in order form before asking for confirmation. `--instrument` and `--asset` are mutually exclusive; `--asset` remains the machine form for a symbol you already know exactly. `--instrument` is also the only flag-form route to a Polymarket order, because the resolver is what supplies the pinned condition id and outcome index.

`om resolve` covers Hyperliquid (canonical perps, spot, every HIP-3 dex) and Polymarket. It needs no paired venue account, so it is safe to call during discovery.

## Discovery: read account state

Read-only account commands surface live state from the paired execution account. ALL of them accept `--format json` for clean agent parsing. None of them place orders — they're situational awareness.

| Command | Returns | When to call |
| --- | --- | --- |
| `om hyperliquid balance` | Perp equity, free margin, withdrawable; spot token balances; per-dex perp equity for each HIP-3 dex the account holds value or margin on | Before sizing with `pct_equity` (resolve $ amount upfront), before any "how much can I afford" question |
| `om hyperliquid positions` | Open perp positions on every dex — canonical and HIP-3: size, side, entry, unrealized PnL, liquidation price, leverage | Before "close my position" / "reduce my X" / `reduce_only` orders; for "how am I doing?" queries |
| `om hyperliquid orders` | Resting orders on every dex, perp + spot, with oid, price, size, age | Before "cancel my bid" / "modify my limit"; for "what's pending?" queries |
| `om hyperliquid fills` | Recent fills with side, price, fee, closed PnL, taker/maker | For "what did I trade today?" / PnL retrospectives |
| `om hyperliquid funding` | Funding payments received and paid | For "what funding did I pay?" — relevant when holding leveraged perp positions |
| `om hyperliquid fees` | Current fee tier (perp + spot, maker + taker, referral discount) | When the user asks about their fee rate or volume tier |

Those three reads sweep the canonical perp dex plus every deployed HIP-3 dex, so an `xyz:TSLA` position or resting order is visible without being asked for. HIP-3 rows carry the dex-qualified coin name, which is what keeps a merged list unambiguous. `--dex <name>` narrows any of them to that one dex, and `canonical` is the reserved name of the canonical (nameless) dex, so `--dex canonical` reads the plain perp account on its own. A scoped read carries that scope's rows and no others: the account's spot orders belong to the canonical scope, so `--dex canonical` is where they show, never under a HIP-3 banner. The balance read's per-dex section appears only when some HIP-3 dex actually holds value.

A dex that cannot be reached fails the whole listing loudly — a partial account picture is never presented as a complete one. The refusal names every scope that failed and then the scopes that do answer, spelled as the argument this surface takes (`--dex xyz` on the CLI, `dex` on the tools): retry with one of the values it lists, `canonical` included, never with the scope that just refused. Tell the user which dex is missing, because a scoped read is a partial picture by construction.

The two account actions take the same scope: `om hyperliquid leverage <asset> <n>` and `om hyperliquid margin <asset> <usd>` accept `--dex <name>` (or `--dex canonical`), and a dex-qualified `xyz:TSLA` asset names its own dex without the flag. Asset ids live in a separate space per dex, so a symbol two dexes both carry is two markets: name the dex when the position being managed is a HIP-3 one, or the change lands on the canonical market of the same name.

Modern Hyperliquid accounts are usually unified: spot USDC backs perp positions directly, so do not infer that a perp-side `$0` display means the user needs a spot/perp transfer when spot USDC is present. Do not preemptively suggest `om hyperliquid transfer` before a perp order just to "fund perps"; on unified accounts the transfer is unnecessary and HL will reject it with messages such as *"Action disabled when unified account is active"* or *"Must deposit before performing actions"*. Treat either message as confirmation that the account is unified, skip the transfer, and continue with the perp-order workflow if the requested order otherwise makes sense.

Polymarket CLOB read-side commands are separate from `om polymarket ...` analytics, which still hits OpenMarket analytics data. Use `om polymarket-account ...` for the user's paired CLOB account:

| Command | Returns | When to call |
| --- | --- | --- |
| `om polymarket-account balance` | pUSD balance, allowance posture, open-order notional, position value | Before `pct_equity` sizing and before any Polymarket order if `needs_setup` is true |
| `om polymarket-account positions` | Open CLOB positions with token id, condition id, outcome, shares, avg/current price, PnL | Before position-close sizing or "what do I hold?" queries |
| `om polymarket-account orders` | Resting CLOB orders with order id, token id, side, price, remaining size, expiration | Before cancel/modify/disambiguation requests |
| `om polymarket-account fills` | Recent CLOB trades with timestamp, price, size, notional, fee estimate, market | For trade history and receipt reconciliation checks |
| `om polymarket-account market` | tokenId / conditionId resolution, outcome tokens, tick size, neg-risk flag, midpoint | Before authoring JSON specs from conditionId/outcomeIndex |
| `om polymarket-account orderbook` | best bid/ask, spread, midpoint, tick size, min size, depth | Mandatory for preview math on Polymarket market orders or quote sizing |

**Always run a read before authoring an order whose sizing depends on live state.** Concretely:

- User says *"buy 5% of my equity in BTC"* → run `om hyperliquid balance --format json`, multiply equity × 0.05, **state the dollar amount in the preview** ("≈ $245 of BTC at current equity"). Do not submit `pct_equity` sizing blindly without telling the user the resolved dollar amount.
- User says *"close my BTC position"* → run `om hyperliquid positions --format json`, find the BTC entry, state the size and unrealized PnL in the preview ("Closing 0.05 BTC long, +$23 unrealized PnL"). Use `reduce_only: true` and `--size-mode base` with the actual position size.
- User says *"cancel my BTC bid at 90k"* → run `om hyperliquid orders --format json` to find the matching `oid`; disambiguate via structured question if multiple match.
- User says *"buy $50 of YES on this Polymarket"* → run `om polymarket-account market --condition-id ... --outcome-index ... --format json` if you only have condition/outcome, then `om polymarket-account orderbook --token-id ... --format json` to preview expected shares and price.
- User says *"close half my YES"* → run `om polymarket-account positions --format json`, find the token, and use Polymarket `size.mode: "position", value: 50` with `side: "sell"` after previewing the shares being closed.

**Do not chain reads as a routine before every order.** When sizing is in `base` or `quote` mode and the user is opening a new position, no read is needed — the spec is fully specified. Reads exist to resolve state-dependent sizing and to disambiguate "this thing I already have" references.

## The order shape

`om order place` accepts either a flag form (quick) or a JSON spec via stdin (rich). Both validate against the same schema, used in identical form by `on_fire.execute` on alerts:

```jsonc
{
  "venue": "hyperliquid",
  "asset": "BTC",                          // coin symbol on HL — NOT a rawSymbol like BTCUSDT
  "side": "buy",                           // "buy" | "sell"
  "order_type": "limit",                   // "market" | "limit" (defaults to "market")
  "size": {
    "mode": "quote",                       // "base" | "quote" | "pct_equity" | "position"
    "value": 250                           // interpretation depends on mode; percent modes take percent points, never 0-1 fractions
  },
  "limit_px": 95000,                       // required when order_type is "limit"
  "reduce_only": false,                    // true → can only close an existing position
  "brackets": {                            // optional; either or both
    "stop_loss_px": 92000,
    "take_profit_px": 101000
  },
  "caps": {                                // optional; for parity with `on_fire.execute`
    "max_size": 250                        // per-order notional ceiling in USD
  }
}
```

The `caps.max_fires` / `caps.expires_at` fields are accepted but ignored for manual orders (they only make sense for recurring alerts).

Polymarket orders use the JSON form. Token can be direct `tokenId` or `{conditionId, outcomeIndex}`; condition/outcome is resolved at prepare time. Market orders are FAK semantics in the pinned SDK; limit orders currently support GTC and GTD. FAK/FOK limit orders are intentionally rejected until the pinned Polymarket SDK exposes those placement paths. GTD requires a future ISO `expiration`.

```jsonc
{
  "venue": "polymarket",
  "token": { "conditionId": "0x...", "outcomeIndex": 0 },
  "side": "buy",
  "order_type": "limit",
  "time_in_force": "GTC",
  "limit_price": 0.52,
  "size": {
    "mode": "quote",
    "value": 50
  },
  "caps": {
    "max_size": 50
  }
}
```

Polymarket prices are probabilities in `(0, 1)` and must align to the market tick size (`0.1`, `0.01`, `0.001`, or `0.0001`). The schema cannot know tick size; the executor fetches metadata and rejects misaligned limits at prepare time. Neg-risk markets are routed from market metadata; never hard-code router assumptions.

### Sizing modes

The mode is the single most important field to get right. Get it wrong and you'll submit 100 BTC when the user meant $100.

Hyperliquid trades a minimum order value of **$10**. It binds every order type, every market including HIP-3, and reduce-only closes as tightly as opens, so a request worth less than $10 is not worth proposing: a quote-mode order under the floor is refused locally, before the venue is called and before a confirmation gate is spent on it. When the user asks for "buy $5 of BTC", say the floor and offer $10 — or a base-mode size, if what they meant was a quantity.

Just above the floor, the venue's lot grid decides the size: every quote-mode order — market or limit, perp or spot — is stepped onto that grid until it clears $10 at both prices the venue could value it by. The step is bounded at **1.5× the value asked for**, so on a coarse grid a requested $10 legitimately goes out worth up to $14.99. `om order place` resolves that figure from public reads before it asks, so the confirm line and the order form name the size that goes out and the value it carries, with the requested figure beside them whenever the grid moved it. A market order's figure is quoted at a mid the placement re-reads, so it is stated with a `~`; a limit order divides by the caller's own limit price and is exact. Where the public reads do not answer, the confirmation states the requested value instead and the placement raises its own refusals. On the typed-action path the same duty is yours: state the value that goes out — bounded by 1.5× — and not only the one requested. The receipt records what actually went out either way.

Two shapes refuse instead of stepping — a market whose smallest expressible size is worth more than 1.5× the request (the refusal names that size), and an order whose `caps.max_size` / `--max-size` sits below the size the floor needs (the refusal names the cap). Both raise ahead of the confirmation, alongside the sub-$10 refusal, so a yes is never spent on an order that cannot go out. All three are deterministic: the recovery is a different number, never a retry.

| User wording | `size.mode` | `size.value` example |
| --- | --- | --- |
| *"$100 of BTC"* | `quote` | `100` (USD notional) |
| *"100 USDT of BTC"* | `quote` | `100` (USDT ≈ USD) |
| *"0.05 BTC"* | `base` | `0.05` (BTC units) |
| *"5% of my equity"* | `pct_equity` | `5` (percent points) |
| *"my whole equity"* | `pct_equity` | `100` |
| *"1% risk"* (with a stop attached) | `pct_equity` | `1` — but flag this is sizing by equity %, NOT by risk-to-stop; if the user wanted risk-sized, ask |
| *"close half my position"* | `position` | `50` (percent of the open position) |
| *"close my whole position"* | `position` | `100` — though `base` with the actual size read from `hyperliquid positions` is the preferred full-close form (see above) |

`pct_equity` and `position` values are percent points, never 0–1 fractions: `value: 100` is the whole thing, `value: 1` closes just 1% of a position. Sending `1` to mean "all of it" is the classic mistake — the order fills, silently, at one-hundredth the intended size.

If the user's phrasing is ambiguous (*"buy 100 of BTC"* — 100 what?), ASK via the structured-question tool. Default is `quote` because it's the most common natural-language anchor, but never silently apply it when the user said an unambiguous-but-different number.

Polymarket sizing modes are `shares`, `quote`, `pct_equity`, and `position`. `quote` is pUSD notional; `shares` is outcome-token shares; `pct_equity` reads pUSD balance; `position` closes a percentage of the existing outcome-token position and must be a sell (same percent points: `50` closes half, `100` closes all). For `quote` and market orders, use `polymarket_orderbook` / `om polymarket-account orderbook` in the preview so the user sees estimated shares, best bid/ask, and midpoint before approval. The typed-action surface is split by venue to keep Anthropic tool-use happy: call `order_place` for Hyperliquid, `order_place_polymarket` for Polymarket. Same dispatcher, same receipt model, same safety contract (preview-then-confirm before invoking).

### Asset name normalization

HL uses coin symbols (`BTC`, `ETH`, `SOL`, `HYPE`, …), not exchange-style rawSymbols (`BTCUSDT`, `ETH-USD`). The single most likely failure mode is passing a rawSymbol — the executor will error at preparation with *"Hyperliquid asset not found: BTCUSDT"*.

| User said | Pass as `asset` |
| --- | --- |
| *"BTC"* | `BTC` |
| *"BTCUSDT"* | `BTC` (strip the quote suffix) |
| *"BTC-USD"* | `BTC` |
| *"BTC perp"* | `BTC` |
| *"hype" / "HYPE token"* | `HYPE` |
| *"TSLA on the xyz dex"* | `xyz:TSLA` (or `TSLA` with `--dex xyz`) |

HIP-3 markets live on a builder-deployed dex and their names are dex-qualified. Three spellings reach the same market, all of them case-insensitive: `--instrument "TSLA on xyz"` (the resolver route, and the one to reach for whenever the user named the market in human form), `--asset xyz:TSLA` on its own (the `dex:` prefix is what carries the routing), and `--asset TSLA --dex xyz`. An `--asset` prefix that names one dex while `--dex` names another is refused rather than guessed at. `om resolve` prints both forms: its `order` object (`asset`, `hl_dex`) is the paste-ready spec fragment and its `cli` field is the same instrument as flags.

For anything the user phrased in human form — a company name, "TSLA on HIP-3", a half-remembered ticker — resolve first (§"Discovery: which instrument did the user mean?") rather than assembling a qualified name yourself: a bare ticker several dexes carry is ambiguous by design and comes back as candidates.

If unsure, verify against HL's universe before submitting. The runner caches it once per process; checking is cheap.

## Workflow when a user requests an order

Follow these steps in order. Do not skip the preview; do not pass `--yes` without explicit user direction.

### 1. Confirm venue is paired

`om status --format json` → if the venue this order needs is absent from `venues[]`, stop and route to the setup command for that venue: `om setup hyperliquid`, or `om setup polymarket` for a CLOB order.

### 2. Parse intent

Extract:
- **side** — buy / sell (or "long" → buy, "short" → sell, "close" → opposite of the open side + `reduce_only: true`)
- **asset** — normalize to the HL coin symbol (see above)
- **type** — limit (user named a price) or market (user said "now" / "at market")
- **price** — required for limit
- **size mode + value** — disambiguate via structured question if needed

### 3. Resolve missing fields via the structured-question tool

NEVER guess at:
- The sizing mode if it's ambiguous (`"100 BTC"` vs `"$100"`)
- The asset if there's any chance of confusion (e.g., user said "stables" → which stable?)
- Whether to attach a stop-loss (see §4)

ALWAYS ask in the order: side → asset → type → price (if limit) → size mode → size value → stop-loss → take-profit. Same one-question-at-a-time discipline as the alerts skill.

### 4. Stop-loss nudge

If the user didn't attach `brackets.stop_loss_px`, ask once via the structured-question tool:

> Question: *"Add a stop-loss?"*
> Options:
> - *Yes, set a stop (recommended)*
> - *Skip — I'll manage exits manually*
> - *Other (specify a level)*

If the user picks "Yes", ask once more for the level — never pick the level for them. Suggest a sane anchor (*"For a long at $95,000, a stop near $92,000–$93,000 is a typical 2–3% buffer"*) but let the user decide. Do not silently compute and apply a stop.

This nudge is identical to the alerts skill's brackets nudge — keep the UX consistent across the two surfaces so users get one mental model.

### 5. Submit and confirm

The user must see exactly one explicit confirmation gate before any capital-committing call. How that gate is produced depends on the surface reading this skill:

**Typed-action path (in-house `om` chat, where `order_place` / `order_place_polymarket` / `order_twap` exist as tools you can call):**
Use this path for Hyperliquid only. Write a one-line plain-English summary AND call the tool in the same turn. The runtime intercepts the call and shows a readline-style `[Y/n]` banner with the resolved args (type y/yes/n/no + Enter, empty Enter takes the capital-Y default). That banner IS the gate. Do NOT ask "submit?" in text and wait for "yes", that's a second prompt for the same decision and produces a worse UX. If the user declines, the tool returns `"User declined this action."`. Acknowledge in one line and move on — no "what instead?" question; the next steps carry the alternatives, and the same shape is refused for the rest of the turn.

**Bash path (Claude Code / Codex / Cursor / any external agent shelling `om *` via a Bash tool):**
The CLI's interactive `[y/N]` prompt is not reliably answerable from a Bash tool, most will hang or EOF to default-N. Confirm via your own structured-question UI first, THEN run `om order place ... --yes`. Passing `--yes` here is correct, not a safety bypass: the safety happened in the agent UI moments earlier.

Useful preview lines (build the right one for the action):

> *order_place*: "Placing on Hyperliquid mainnet: buy $250 of BTC, limit at $95,000, stop at $92,000, not reduce-only."
> *Polymarket CLI JSON path*: "Placing on Polymarket mainnet: buy $50 of YES, limit 0.52 GTC, estimated 96.15 shares, token 0x123…abcd, neg-risk false."
> *order_twap*: "TWAP on Hyperliquid mainnet: buy 0.0026 BTC (≈ $250 at current price) over 30 minutes, randomize off, not reduce-only."

Note: `order_twap.sz` is base-asset units only, there is no `quote` size mode like `order_place` has. Resolve dollar amounts to base units yourself (read `markets` for the current price, divide), and state BOTH the base size and the dollar equivalent in the preview so the user can spot a misconversion before approving.

### 6. Execute (Bash path)

For the flag form:

```bash
om order place \
  --asset BTC --side buy --type limit \
  --price 95000 --size 250 --size-mode quote \
  --stop-loss 92000 --yes
```

A HIP-3 market is the same call with the dex-qualified asset name (`--asset TSLA --dex xyz` and `--instrument "TSLA on xyz"` name the same market):

```bash
om order place \
  --asset xyz:TSLA --side buy --type market \
  --size 250 --size-mode quote --yes
```

For the JSON form (brackets, caps, anything more elaborate):

```bash
echo '{
  "venue": "hyperliquid", "asset": "BTC", "side": "buy",
  "order_type": "limit", "size": { "mode": "quote", "value": 250 },
  "limit_px": 95000, "brackets": { "stop_loss_px": 92000 }
}' | om order place - --yes
```

For a Polymarket JSON order, use the CLI JSON/file path rather than the `order_place` typed action:

```bash
echo '{
  "venue": "polymarket",
  "token": { "conditionId": "0x...", "outcomeIndex": 0 },
  "side": "buy",
  "order_type": "limit",
  "time_in_force": "GTC",
  "limit_price": 0.52,
  "size": { "mode": "quote", "value": 50 }
}' | om order place - --yes
```

Omit `--yes` only if you've verified your Bash tool can drive an interactive stdin prompt and want the CLI's `[y/N]` as the gate. Most can't.

### 7. Report once

On success the CLI prints:

```
status:   submitted
cloid:    0x<hash>
oid:      <hl order id>
notional: $250.00
```

Report this back to the user in plain language, one line: *"Submitted — buy $250 of BTC at 95k. Order ID 0x123…abc. View on HL or run `om execute list` to inspect."*

Do not tail with "want me to place another?" or any follow-up question unless the user opens that door.

## Workflow when an order needs to be cancelled

Use `om order cancel <oid>` or `om order cancel-cloid <cloid>`. The resting-order lookup searches every dex and routes the cancel to the dex it finds the order on, so an order resting on a HIP-3 market cancels by its id alone, and one unreachable dex does not block a cancel for an order found elsewhere. `--dex <name>` scopes the search to that one dex, `--dex canonical` to the canonical one. `--asset` skips the lookup altogether and routes on the name given, so a dex-qualified `--asset xyz:TSLA` goes to `xyz` on its own. A cloid matches by hex value, so the casing it is typed in does not matter. When a scope the search needed could not be read, the message names it: on `cancel` and `cancel-cloid` the way past it is `--asset`, which reaches the order without the search at all, while `modify` and `batch-modify` reach an order only through the search, so their recovery is retrying once that scope answers. If the id matches an execution receipt, the receipt's venue controls routing. Hyperliquid can cancel by numeric oid or cloid; Polymarket cancels by the stored CLOB order id. If a Polymarket receipt has no CLOB order id because the SDK response was dropped or the pinned SDK did not return one, the CLI will say clientOrderId cancellation is unavailable; ask the user for the CLOB order id from `om polymarket-account orders` and cancel by that id.

Several orders = ONE call, one card: `order_cancel` takes `ids` (order ids as strings) with one `venue` (`om order cancel <oid...>`); the card lists every member (asset, side, size, price), a reduce-only member or one with no local receipt is named on the card and holds it off auto mode, Hyperliquid members go through one signed batch cancel per DEX, Polymarket members loop the single cancel, and a mixed-venue set refuses before any write. `order_twap_cancel` takes `ids` (up to 25, one venue and one asset per call, `om order twap-cancel <id...>`); a TWAP already finished comes back as an unchanged row. Never loop single-id cancels for a set: that raises one card per order.

For a recurring auto-execute alert the user wants to stop submitting, use `om alert pause <id>` or `om alert remove <id>`. That's the alerts skill, not this one. If the user says "cancel my order", clarify whether they mean a resting venue order or the alert that may submit more.

## Workflow when a user wants to inspect what landed

```bash
om execute list                          # last 50, all sources (alert + manual)
om execute list --manual                 # only manual orders (alert_id null)
om execute list --since 24h              # narrow by window
om execute list --since 24h --format json
om execute summary --since 7d            # rollup: counts, total notional
```

Render in plain English, one row per receipt. Show: status, venue, notional, OID (or short cloid), and how long ago. Don't dump JSON unless the user explicitly asks for raw.

Receipts whose `alert_id` is null are manual orders. Receipts with an alert_id came from an alert's `on_fire.execute` — for those, the user can also run `om execute history <alert_id>` (alerts skill territory).

## Common errors and how to recover

The CLI emits structured JSON errors with `--format json`; in text mode they print on stderr with an `om:` prefix. Map the error code to a recovery instruction:

| Error | Meaning | Recovery |
| --- | --- | --- |
| `venue_not_paired` (exit 4) | Requested venue not paired | Run `om setup hyperliquid` or `om setup polymarket`. Stop ordering until paired. |
| `order_place_failed` with *"Hyperliquid asset not found"* | Asset name wrong | Re-prompt the user for the asset; check HL's universe; strip exchange suffixes (`BTCUSDT` → `BTC`). |
| `order_place_failed` with *"Hyperliquid trades a minimum order value of $10 — this order asks for $N. Raise the size to at least $10."* (N is the requested value) | Quote-mode request worth less than $10, refused before any venue call and before the confirmation. `om order place` exits 1 with no receipt; reached through the dispatcher instead (typed action, alert leg) it settles a receipt with status `error` that reserves nothing against the daily ceiling | Not transient — a retry submits the same doomed order. Tell the user the venue floor and ask for a size of $10 or more, or a base-mode quantity. |
| `order_place_failed` with *"Hyperliquid's lot grid on this market cannot express an order near $N: the smallest order clearing the venue's $10 minimum is worth $M"* | Quote-mode request on a market whose smallest $10-clearing size is worth more than 1.5× the request; judged from public reads before the confirmation, nothing signed | Not transient. Quote the $M figure the message names and ask the user for a size at least that big, or a different market. |
| `order_place_failed` with *"Hyperliquid's $10 order minimum needs a size worth $M on this market's lot grid, above the order's max_size cap of $C"* | The size the $10 floor needs exceeds the order's own `caps.max_size` / `--max-size`; judged from public reads before the confirmation, nothing signed | Not transient. Quote both figures and ask the user to raise the cap to at least $M or leave the order unplaced. |
| `order_batch_modify_failed` (exit 1), or `ok: false` with `error: batch_modify_partial` on the action | A batch spanning dexes signs one action per dex and stops at the first refusal. The entries before it already rest at NEW oids — HL's modify is cancel-replace — and the payload tags every entry `landed` / `failed` / `not_attempted` with the replacement oid of each landed one | Never re-run the same batch: the venue has replaced those oids. Report the landed entries and their new oids, then batch only the entries that did not land. |
| `order_place_failed` with *"tick size"* | Polymarket limit price not aligned | Run `om polymarket-account market` or `orderbook`, choose a price aligned to the returned tick size. |
| `not_supported_on_venue` | Requested operation has no native venue primitive | For Polymarket modify, cancel and re-place manually after preview; for TWAP, use Hyperliquid only. |
| `order_place_failed` with `limit_px is required` | Limit order without a price | Ask for the limit price. |
| `order_place_failed` with `caps.expires_at must be ISO 8601` | Bad timestamp format | Re-ask in ISO format or compute it from a duration. |
| Receipt status `blocked`, reason `venue_unconfigured` | Vault unlocked but no PK found | Re-pair: `om setup hyperliquid`. |
| Receipt status `blocked`, reason `max_size` | `caps.max_size` triggered | Tell the user the cap blocked them; ask if they want to raise the cap or lower the size. |
| Receipt status `blocked`, reason `daily_ceiling` | Global daily notional ceiling hit | Tell the user the ceiling blocked them. Raise it with `om config set execute:daily_ceiling_usd <amount>` if appropriate. |
| Receipt status `rejected` (from HL) | Venue refused — insufficient margin, bad params, etc. | Inspect the `raw_response` field of the receipt for HL's error text. Surface it back to the user. |
| Receipt status `error` | Adapter / signing / network failure, or a sizing refusal that never reached the venue (order minimum, lot grid, size cap — the rows above). A refusal that provably signed nothing leaves `notional_usd` null, so it spends none of the day's ceiling | Read the receipt's `raw_response` first and let the message decide: a sizing refusal is deterministic, so change the number rather than retry. Network errors usually self-heal on retry; signing errors mean the API wallet key is malformed (rare). |

## Behaviors to follow

- **Exactly one explicit confirmation gate.** Typed-action path: just call the tool (runtime shows `[Y/n]`). Bash path: confirm via your structured-question UI first, then pass `--yes`. The thing to avoid is ZERO gates (auto-submit) or hanging on a CLI prompt your Bash tool can't answer. Do not double-prompt by also asking "submit?" in text before the gate, that's the regression this rule exists to prevent.
- **NEVER guess at the sizing mode.** Ambiguous "100 of BTC" → ask via structured question.
- **NEVER guess at the asset name.** Strip exchange suffixes; verify against HL's universe if there's any doubt.
- **NEVER auto-apply a stop-loss level the user didn't specify.** Suggest a range, let the user choose.
- **NEVER place an order without first checking `om status`** to confirm the venue is paired.
- **NEVER suggest a spot/perp transfer solely because perp-side balance reads `$0`.** Unified Hyperliquid accounts use spot USDC as perp collateral directly; only transfer if the user explicitly asks for it.
- **DO mention the network** (mainnet vs testnet) in the preview. The user should always know which network their money is on.
- **DO show the receipt summary** after submission so the user sees what landed.
- **DO route to the unpaired venue's own setup command immediately** — `om setup hyperliquid`, or `om setup polymarket` for a CLOB order. Don't try to be clever.

## Behaviors to avoid

- Don't suggest order types this skill doesn't expose (stop-market, trailing stop, OCO). v1 supports `market` and `limit`; brackets give you TP/SL children. If the user asks for trailing-stop semantics, route them to the alerts skill (a custom-script alert can implement a trailing stop and call `om order place` from its body).
- Don't render the receipt's `raw_response` JSON to the user verbatim — extract the relevant field (oid, error message) and speak it.
- Don't combine multiple orders into one CLI invocation — each `om order place` submits exactly one parent (plus optional bracket children).
- Don't try to construct an OCO group manually. v1 doesn't support it.

## See also

- `openmarket-alerts` — author alerts that watch a condition and (optionally) auto-execute on fire via `on_fire.execute`. Use that skill when the user's intent is "do X when Y", not "do X now."
- `openmarket-metrics` — read live scalar metric values (RSI, MACD, EMA, funding rate, open interest, etc.) for a symbol. Useful as a pre-flight check before authoring an order ("what's the 4h RSI on BTC?" then "below 30, oversold" then user decides whether to long here).

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om execute history` (action: `execute_history`) — Read the execution receipts triggered by a specific alert, newest-first.
- `om execute list` (action: `execute_list`) — List execution receipts ordered newest-first.
- `om execute summary` (action: `execute_summary`) — Aggregate execution receipt counts by status, plus total notional.

- `om hyperliquid balance` (action: `hyperliquid_balance`) — Read the paired Hyperliquid account's perp equity (account value, withdrawable, margin used, notional) and spot token balances (USDC + any other tokens), plus `account_mode`.
- `om hyperliquid dexes` (action: `hyperliquid_dexes`) — Without args: list HIP-3 (builder-deployed) perp DEXes available on Hyperliquid (name, deployer, fullName, index).
- `om hyperliquid fees` (action: `hyperliquid_fees`) — Read the paired account's current fee tier: perp/spot taker + maker rates (decimal, e.g. 0.00045 = 4.5 bps), referral discount, and the maximum builder fee approved for the OM builder address (also decimal).
- `om hyperliquid fills` (action: `hyperliquid_fills`) — Fill history for the paired account.
- `om hyperliquid funding` (action: `hyperliquid_funding`) — Funding payments received and paid on perp positions.
- `om hyperliquid leverage` (action: `hyperliquid_leverage`) — Set the leverage for a perp asset on the paired account.
- `om hyperliquid margin` (action: `hyperliquid_margin`) — Add or remove USDC margin on an existing isolated perp position.
- `om hyperliquid orders` (action: `hyperliquid_orders`) — List resting orders on the paired account (perp and spot together).
- `om hyperliquid positions` (action: `hyperliquid_positions`) — List open perp positions on the paired account: coin, signed size (positive=long, negative=short), entry price, position value, unrealized PnL, liquidation price, margin used, leverage (value + cross/isolated).
- `om hyperliquid transfer` (action: `hyperliquid_transfer`) — Internal USDC move between the paired account's spot and perp wallets on Hyperliquid.
- `om hyperliquid twap-fills` (action: `hyperliquid_twap_fills`) — Individual slice fills from TWAP orders.
- `om hyperliquid twap-history` (action: `hyperliquid_twap_history`) — Past TWAP orders on the paired account (active, finished, terminated, or errored).

- `om order batch-modify` (action: `order_batch_modify`) — Modify N resting Hyperliquid orders in one signed action per perp DEX.
- `om order cancel` (action: `order_cancel`) — Cancel resting orders by order id: `oid` for one, or `ids` for several in ONE call (one approval card covers the set; never a loop of single calls).
- `om order cancel-cloid` (action: `order_cancel_cloid`) — Cancel a resting order by execution cloid.
- `om order modify` (action: `order_modify`) — Change the limit price and/or base-asset size of a resting Hyperliquid order.
- `om order place` (action: `order_place`) — Submit a Hyperliquid order through the full execution pipeline (cap-check, daily ceiling, vault unlock, signing, receipt, reconciler-replayable cloid).
- `om order place` (action: `order_place_polymarket`) — Submit a Polymarket CLOB order through the full execution pipeline (cap-check, daily ceiling, vault unlock, signing, receipt, reconciler-replayable cloid).
- `om order schedule-cancel` (action: `order_schedule_cancel`) — HL dead-man's switch: schedule all open orders to auto-cancel at a future time, or clear an existing schedule.
- `om order twap` (action: `order_twap`) — Place a native Hyperliquid TWAP order.
- `om order twap-cancel` (action: `order_twap_cancel`) — Cancel running TWAP orders: `twapId` for one, or `ids` for several on the same asset in ONE call (at most 25; one approval card covers the set, never a loop of single calls).

- `om polymarket-account balance` (action: `polymarket_balance`) — Read the paired Polymarket CLOB account's pUSD balance, collateral allowance posture, total notional resting in open orders, and current position value.
- `om polymarket-account fills` (action: `polymarket_fills`) — Recent Polymarket CLOB trades for the paired account.
- `om polymarket-account market` (action: `polymarket_market_lookup`) — Resolve a Polymarket CLOB token reference.
- `om polymarket-account orderbook` (action: `polymarket_orderbook`) — Fetch top-of-book for a Polymarket CLOB token, named by token id or by market (slug/question) plus outcome name.
- `om polymarket-account orders` (action: `polymarket_open_orders`) — List resting Polymarket CLOB orders for the paired account.
- `om polymarket-account positions` (action: `polymarket_account_positions`) — List open positions in the paired Polymarket CLOB account with token id, condition id, outcome, shares, average price, current price/value, PnL, and neg-risk marker when available.

- `om resolve` (action: `market_resolve`) — Resolve a free-form instrument phrase to ranked, order-ready instruments across execution venues (Hyperliquid canonical perps, spot, HIP-3 DEX markets, and Polymarket).

<!-- AUTO: END COMMAND REFERENCE -->
