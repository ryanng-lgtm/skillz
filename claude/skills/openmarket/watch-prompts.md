---
name: openmarket-watch-prompts
description: "What an ai step on a watch sees when it runs and how to write one: the header the daemon generates (verbatim), the INPUT row per source kind, the tool menu (the default set, the reaching rows and where each reaches out, every function's return shape), the three answer shapes and which readers accept each, the definitions fields for a decision or a word list, the @{Name} mention syntax, worked prompts (a judge, a note, a screen) and the refusal-is-the-fix table. Read before writing or editing any ai step's prompt, tools, output or definitions, and whenever a create answers watching_unknown_source, watching_unknown_tool, watching_reader_unsatisfied or watching_definitions_overlap."
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
---

# Writing an ai step

An ai step is one model turn per row. The daemon hands the turn a header it generated from the watch, the one update that triggered the run, and the author's instructions; the turn reads, calls the functions its menu ticks, and answers in the shape the step declared. The author writes only the instructions, and every name in them must exist on the watch.

**Guardrails**

- Read the watch first (`watch_show`), then the menu (`watch_tools`): never invent a source name or a tool name. A source is mentioned as `@{Name}` exactly as `watch_show` prints it; a tool is named exactly as `watch_tools` lists it (§"Mentions", §"The leash").
- The prompt has no hands: the turn acts only through the functions its menu ticks, and the menu is the default set unless the step says otherwise (`tools` absent = every read plus web search, `[]` = none, a list = exactly those). There is no run-a-script, write-a-file or call-any-URL function, and a money function never resolves on a menu; a prompt asking for one ends with "tool not available" in the record.
- Choose the answer shape from the reader: a person, a webhook or a next ai step reads `text`; an `order` reads a `word` from a list covering `buy`, `sell`, `none`; a `strategy` reads a `verdict`. A mismatch refuses at create, never at run time (§"Answer shapes").
- A decision or a word list is written as `definitions` fields, never as prose paragraphs; the daemon composes the INSTRUCTIONS block from them and runs one model check for overlap at create (§"Definitions").
- Test the saved step with `watch_test` preview before arming. Inspect its real input and typed output; offline fixtures are simulations, not evidence of model judgment. `run_models: true` requests a charged model preview with tools and delivery sandboxed.
- INPUT is one update. Anything else the instructions want, the turn fetches call by call under `maxToolCalls` and `budgetMs`; context never wakes the step, and instructions cannot schedule a later run: express a check over history that already exists, or add a trigger.
- A refusal is the fix: `watching_unknown_source`, `watching_unknown_tool`, `watching_reader_unsatisfied` and `watching_definitions_overlap` each say what to change. Change the spec and resubmit; never change the user's intent to dodge one, never retry unchanged, never relay one as an error (§"Refusal is the fix").

**Routing**

- What the turn receives, with the header verbatim → §"What the model sees"; the fields of the one update, per source kind → §"INPUT per source kind"; the menu, the default set, the reaching rows and every function's return shape → §"The leash"; `text`, `word`, `verdict` and their readers → §"Answer shapes"; the fields of a decision or a word list → §"Definitions"; `@{Name}` and the read-first rule → §"Mentions"; three complete steps → §"Worked prompts"; every refusal and its one change → §"Refusal is the fix".
- A model run's prompt (`watch_model_add`: a standing question answered on a cadence, with no firing row, no INPUT and no mentions), the header it sees and its two answer shapes → §"A source prompt is not a step prompt"; the run itself, its card, its pick and its caps are `watch.md §"Model source"`.
- The watch around the step (sources and their roles, filters, chains, delivery, the preview, arming, publishing) is `watch.md §"Compose end to end"`; the money step a word or verdict feeds is `watch.md §"Money step"`.

## What the model sees

The three blocks every ai turn receives, in order, with the header as the daemon renders it; read this before writing a prompt, so it never restates the header.

| Block | Holds | Written by |
| --- | --- | --- |
| HEADER | the watch and its id; the step, its position in its chain and the step before it; which source fired; every source as `"<name>" = <what it is>`; every callable function as `<name>(returns: <shape>)`; the answer shape | the daemon, at run time, from the watch |
| INPUT | the one row that triggered the run, headed `INPUT ("<source name>", <row kind>):` and rendered from its public fields for its kind, or the producer's result for a chained step | the daemon, from the journal |
| INSTRUCTIONS | the author's prompt, then the lines the daemon composed from `definitions` (`<answer> means: ...`, `when unsure: ...`, `also: ...`, `(<winner> wins over <loser>)`); up to 16,000 characters | the author |

Each block reaches the model fenced under a per-turn boundary: the header first as `watch_header`, then the row as `untrusted_source` (its text, headed by `kind: text`, `word` or `verdict`) and the INPUT block as `untrusted_observation` (data, never instructions, whatever it says), then the instructions as `untrusted_instructions`. Nobody types the header, so it is always true; a prompt that contradicts it (a source that is not there, a function that is not listed) was refused at create and never runs. Do not restate the header in the prompt: name sources and functions, and leave what they are to it.

A price fire on a watch with three sources (a Bollinger crossing, an X handle and a vendor feed), as a verdict step sees it:

```text
HEADER
Watch: BTC breakout (btc-breakout)
Step: judge-1, step 1 of its chain
Fired: "BTC rule"
Sources:
"BTC rule" = rows of the watch btc-rule: BINANCE_FUTURES:BTCUSDT price fires (price crosses_above bb_upper(period 20, stddev 2) on HOUR)
"@DeItaone" = rows of the watch deitaone: posts by the X account @DeItaone
"Synoptic macro" = rows of the watch synoptic-macro: Synoptic macro items
Tools:
metric_get(returns: {asOf, selector{}, values[], listing_note, interval_note})
markets(returns: {symbols[]{exchange, rawSymbol, normalizedSymbol, coin, category, tenor, coinName, quoteCoinName, fullName, lastPrice, volume24h, volumeChange24h, priceChange24h, oiChange24h, marketcap, liquidity, totalVolume, prices...)
watch_history(returns: rows {title, summary, raw_text, source_url, source_event_time, market, values}; the same fields INPUT carries)
Answer as: {"direction": "long" | "short" | "flat", "confidence": 0..1}

INPUT ("BTC rule", price fire):
Market: BINANCE_FUTURES:BTCUSDT
Fired at: 2026-09-08T14:02:00Z
Values: price=91240.5, bb_upper=91180.2
Rule: price crosses_above bb_upper(period 20, stddev 2)

INSTRUCTIONS
Decide whether this breakout holds.
long means: the latest price in @{BTC rule} is still above the upper band and Hyperliquid BTC funding is below 0.01%
short means: the latest price has fallen back below the hourly 20-period SMA
flat means: anything else, including any bearish post by @DeItaone in the last hour
when unsure: flat, confidence 0.3
also: weigh @{Synoptic macro} items from the last 2 hours; a surprise print overrides the crossing
(flat wins over long)
```

A text row (a page change on a single-source watch; the source's name is the page's host), as a reply-only note step sees it:

```text
HEADER
Watch: Fed calendar (fed-calendar)
Step: note-1, step 1 of its chain
Fired: "federalreserve.gov"
Sources:
"federalreserve.gov" = federalreserve.gov page changes
Tools:
(none)
Answer as: text (your reply is delivered as written)

INPUT ("federalreserve.gov", page change):
Kind: page_change
Title: FOMC statement, September 2026
Link: https://www.federalreserve.gov/newsevents/pressreleases/monetary20260908a.htm
At: 2026-09-08T18:00:11Z
Summary: The Committee lowered the target range by 25 bp to 4.00 to 4.25 percent.
Text:
<the committed raw text, up to 2048 characters, then "(cut)">

INSTRUCTIONS
Write three lines for a person: what changed, what it means for front-end rates, and the link from INPUT. Answer NO_REPLY when the update is a schedule change with no decision in it.
```

A chained step (it reads step 1's result, not the source row):

```text
HEADER
Watch: BTC breakout (btc-breakout)
Step: brief-1, step 2 of its chain (after judge-1)
Fired: "judge-1"
Sources:
(the same three lines step 1 sees)
Tools:
(the same lines step 1 sees)
Answer as: text (your reply is delivered as written)

INPUT ("judge-1", chained step):
Produced by step: judge-1 (answers verdict)
At: 2026-09-08T14:02:41Z
Result:
{"direction":"long","confidence":0.8}

INSTRUCTIONS
Explain the decision in two sentences for the desk channel: the direction and confidence, and the one reading that decided it. No advice, no hedging.
```

What to take from the header: the `Sources:` lines are the only source names that exist, spelled exactly as a mention must spell them; the `Tools:` lines are the whole menu as sealed (machine names, whatever plain rows a person ticked), nothing else exists, and each line's `returns:` is the shape to read the result by; the `Answer as:` line is enforced (an answer outside it is a `no_action` row and nothing downstream runs); `Fired:` names the source, or the producer step of a chained step, or `the clock (no source row)` for a timer, which has no INPUT block at all. A word step's line reads `Answer as: one word from: buy, sell, none`.

## INPUT per source kind

The one update each source kind hands the step, field by field; read this to know what a prompt can point at without a tool call.

Every INPUT block opens `INPUT ("<source name>", <row kind>):`, the row kind being `price fire`, `text row`, `page item`, `page section`, `page change` or `chained step`; then the row's fields for its kind, in this order.

| Source kind | Row kind | INPUT carries |
| --- | --- | --- |
| condition fire | `price fire` | `Market:` the selector as `EXCHANGE:SYMBOL`; `Fired at:` the fire instant; `Values:` each metric leaf's current value as `name=value`, comma separated, in the rule's order (both sides of a Compare); `Rule:` the condition as one line (every leg of an `all` / `any`). A catch-up fire (the daemon was down) is reported late and a money step never runs on it. |
| page change | `page item`, `page section` or `page change` | `Kind:` the stored kind; `Title:`; `Link:` (the row's own `source_url`); `At:` the observed instant; `Summary:` the classifier's line, when one ran; `Changed lines (- before, + after):` when an earlier excerpt exists; `Text:` then the committed raw text on the next lines, at most 2048 characters, then `(cut)`. |
| feed item (RSS, Atom, JSON, EDGAR, a declared poller) | `text row` | `Kind:` the stored kind; `Title:`; `Link:`; `At:` (`source_event_time`, the item's own clock); `Summary:`; `Text:` then the item's text, bounded like a page. |
| X post | `text row` | `Kind:`; `Title:` when the mirror gives one; `Link:` the post; `At:` the post's clock; `Summary:`; `Text:` then the post. |
| news-stream item (a vendor stream: Synoptic, Attention; a hosted search finding) | `text row` | `Kind:`; `Title:`; `Link:`; `At:`; `Summary:`; `Text:` then the story text the vendor sent. |
| model finding (a model run's row, read by a step on that watch or through an upstream) | `text row` | `Kind:` `model_finding` (`model_answer` for an `answer` run); `Title:` when the model gave one; `Link:` the finding's own url when the model gave a valid one; `At:` the instant the run reported it; `Summary:` the finding's summary (the classifier's line instead when a `goal` ran one); `Text:` then that summary, the one or two sentences the model wrote (an `answer` run: the whole answer). The model's `source` and `date` stay claims on the stored row (`source`, `reported_date`), never `At:`. |
| pushed row (the inbound door or the relay mailbox) | `text row` | `Kind:` the sender's own `kind` token when it sent one (`trade`, `filing`, `outage`); `Title:`, `Link:` (`url`), `Summary:` when sent; `At:` (`occurred_at`, else the ingest instant); `Values:` the sender's numbers as `name=value` (up to 8, `price=64250.5`); `Text:` then the `text` the door required (up to 8000 characters at the door, 2048 here). The row's `received_via` (`push` for the owner's local door, `inbound` with the sender's name for mailbox mail) rides `watch_history`, not INPUT. |
| timer tick | none | no INPUT block: the header says `Fired: the clock (no source row)`, and everything the prompt wants is a tool call. |
| upstream copy (a row of another local watch) | the producing row's own kind | the producing watch's own row with its kind's fields above; the heading names the sibling as the header lists it (`"BTC rule"`), from the slug the row carries in `context.upstream`. Only source rows cross an upstream; a sibling's step results never do. |
| followed public output | `chained step` for a published step, otherwise the source kind | The selected typed answer (`text`, `word` or `verdict`), public output name, source event identity and parent result identity. A follower can use this data locally without receiving the publisher's prompt, private script, tool arguments or execution authority. |
| chained step (`input` names a producer) | `chained step` | `Produced by step:` the producer's id and `(answers text)`, `(answers word)` or `(answers verdict)`; `At:`; `Previous result:` or `Changed lines` when an earlier result exists; `Result:` then the result on the next lines, at most 2048 characters: prose for `text`, the word itself for `word`, canonical JSON `{"direction","confidence"}` for `verdict`. |

`watch_history({source, last})` returns rows in the same fields INPUT carries (`title`, `summary`, `raw_text`, `source_url`, `source_event_time`, `market`, `values`), newest first, so a prompt written against INPUT reads history without a second vocabulary.

## A source prompt is not a step prompt

A model run's prompt has no firing row: what the run sees, the two answer shapes, the menu rule and what a good source prompt states; read this before writing one.

A model run (`watch_model_add`, `watch.md §"Model source"`) fires on its cadence, not on a row, so the turn receives two fenced blocks, not three: the header as `watch_header`, then the prompt whole as `untrusted_instructions` (`INSTRUCTIONS:` then the text, exactly as the card printed it). No `untrusted_source`, no `untrusted_observation`, no INPUT block, no `Fired:` line. `@{Name}` has nothing to point at: a braced or bare mention in a source prompt is plain text that nobody validates, so name nothing that way. The header, as the daemon renders it:

```text
HEADER
Watch: <label> (<id>)
Source: "<name>", a model run every <cadence>
Now: <the run's start, ISO>
Last run: <when the last run that reported anything finished, ISO, or never>
Sources:
"<name>" = a model run every <cadence>
Tools:
<name>(returns: <shape>)
Answer as: a JSON object {"findings": [...]}, one item per distinct finding, newest first
```

`Sources:` holds the watch's own arm (a model run watches nothing but itself); `Tools:` is the sealed list with return shapes, exactly as an ai step's header prints it (machine names; the menu's plain rows are for the person), `(none)` on an empty list; `Answer as:` reads `text (one answer; NO_REPLY when there is nothing to report)` for `output: "answer"`. `Now:` and `Last run:` are the window the prompt reasons over; the prompt never restates them.

The two answer shapes, with the contract lines the system prompt carries for each:

| `output` | The turn answers | The contract lines | Parsed as |
| --- | --- | --- | --- |
| `rows` (the default) | one JSON object, `{"findings": [...]}`, one item per distinct finding, newest first; `{"findings": []}` when nothing | `Your final reply is exactly one JSON object and nothing else: {"findings": [{"title": "...", "summary": "...", "url": "https://..." or null, "source": "..." or null, "date": "YYYY-MM-DD" or null}]}. One item per distinct finding, newest first; summary is one or two concrete sentences; url is the item's own address when it has one; date is the publication date as stated, else null.` then `No other keys, no prose before or after it. Nothing to report answers {"findings": []}.` | one source row per finding: `title` up to 240 characters, `summary` up to 1,200, `source` up to 120, `url` kept only as a valid http(s) address (else dropped, the text kept), `date` kept only as `YYYY-MM-DD` and stored as a claim (`reported_date`), never as the row's time; an item with neither title nor summary is dropped; the reply is read up to 20,000 characters; a finding's id is its url, else a digest of its title and summary, so a repeat never becomes a second row |
| `answer` | one text answer; exactly `NO_REPLY` when nothing | `Your final reply IS the deliverable. It is sent as-is to the destination the watch names. Write it for that reader, complete and self-contained.` then `If there is nothing worth delivering, reply with exactly NO_REPLY and nothing else.` (the text step's own lines) | one row per run whose text is the answer, up to 4,000 characters; none on `NO_REPLY` |

The menu rule (the same rule as a step's, §"The leash"):

- `tools` absent seals the default set (every read on this home plus web search, minus a default row the sealed lane cannot run); `[]` seals none; a list seals exactly those names (`watch_tools` lists them; a name outside refuses `watching_unknown_tool` with the nearest callable). The header's `Tools:` lines are the sealed list, whole.
- `watch_history` on the list is bound to the watch itself: `{source, last}` reads this run's own accepted rows (the `Source:` name), never another watch's, so "skip what you already reported" is one call.
- The reaching rows are where a run leaves this home: `web_research` (an isolated nested call on the sealed model, each call one more request, with the reach of the picked lane: X only on xai), `page_read` (OpenMarket's own fetcher, every lane), `search_files` (the one store the seal names), `make_image` (the sealed image lane). The card's `Reaches out:` line states them for the pick; a row the lane cannot run prints its capability row and refuses `maker_tool_unsupported` at run time.
- `max_tool_calls` (default 20, at most 32) bounds the calls per run and `max_runs_per_day` (the person's number, absent = the cadence alone) the runs per UTC day; the run's deadline (`OM_DEADLINE_MODEL_SOURCE_RUN`, 600s by default) ends it, and a run stopped by the deadline lands no rows.

What a good source prompt states (the header already says what the watch, the cadence, the tools and the shape are; say none of it again):

- The window, in the model's own terms: since the last run, or a fixed span, and what to do on the first run, when `Last run:` reads `never`. The header carries the instants; the prompt carries the rule.
- What counts as ONE finding (the unit: a post, an article, a filing, a change, a number that moved) and what makes it worth a row.
- What to skip: reposts and duplicates, the same story from a second outlet, anything `watch_history` already holds, anything outside the subject.
- Which tool answers which question, and that the cap is a bound, not a target: one good search beats many.
- The answer language and register when the rows reach a person; a `goal` on the member filters after the run, the prompt decides what is offered at all.
- For `answer`: the length, and what silence means (`NO_REPLY` when nothing is worth a row).
- It is printed whole on the card: write it for the human who approves it as much as for the model.

## The leash

The tool menu a step and a model run share: the default set, the reaching rows, what each function returns, and the names never callable; read this before naming a tool.

`tools` is one field with one rule on both the step and the model run: ABSENT seals the default set (every audited read on this home plus `web_research`, minus a default row the sealed lane cannot run), `[]` seals no tools (a reply-only step: INPUT and the header are all it has, and the header prints `Tools:` `(none)`), a list seals exactly those names. The seal stores the concrete list, frozen at the arm, so a function shipped later never joins an approved chain, and each name resolves on the installing home at the arm (`unattended_tool_unresolved` names any that does not). `watch_tools` (`om watch tools`) is the read to make before naming one: it returns every function with the plain row it sits on (`row`, `plain`, `when`, `group`, `default`, `account`, `spend`, `warn`, `needs`, `runs_on`), the concrete `default_set`, and the rows this build greys out (`not_offered`). The header prints each function as `<name>(returns: <shape>)`, the shape derived from the function's own output schema (an object lists its keys, `key[]` an array, `key{}` a nested object, `[]{...}` an array of objects, clipped past 220 characters); the plain rows are for the person, the header keeps the machine names. Unattended, `metric_get` takes at most 8 queries per call and both metric reads take built-in metrics only (a `wrun/` id refuses: a condition source reads installed indicators, a step does not).

The menu as a person sees it (the form's checklist, the cards, `om watch tools`), each row with when you want it and what comes back; every row under the master row is on by default and unticks on its own:

| Row | Functions | When you want it | What comes back | Default |
| --- | --- | --- | --- | --- |
| Everything OpenMarket can read (the master row) | the six rows below | most prompts | numbers and rows with the time they were read | on |
| Prices, stats and history | `markets`, `points`, `polymarket_orderbook` | a price, a move, an order book, a candle history | live prices and 24h change, candles, funding, open interest and order books | on |
| Indicators | `metric_get`, `metric_list`, `metric_rule`, `metric_series` | RSI, MACD, EMA, funding or open-interest reads, and a rule over them | the indicator's numbers, a series over time, or a long/short/flat decision | on |
| Market lookups | `block_sizes`, `coins`, `enum`, `exchanges`, `hyperliquid_dexes`, `market_resolve`, `normalized_symbols`, `polymarket_market_lookup`, `symbol_resolve`, `symbols`, `tenors` | turning a name into the exact market | the venue, symbol, ids and lists a market goes by | on |
| The news journal | `event_journal_get`, `event_journal_list`, `event_journal_search` | what this home already logged about a subject | journal text and matching past events | on |
| This watch's own past rows | `watch_history` | comparing with what this watch found before | this watch's earlier rows with their outcome and time | on |
| Your positions and balances | `hyperliquid_*` and `polymarket_*` account reads, `execute_*`, `usage` | a prompt about your own book | balances, positions, resting orders, fills, funding, fee tier, receipts and API quota; the card warns that what it reads can end up in what the run searches for or sends | on |
| Search the web (and X on Grok) | `web_research` | anything newer than the model's memory | headlines, snippets and links; one model request per call | on |
| Read a web page by address | `page_read` | a page the prompt names or a search returned | the page's text, bounded, through OpenMarket's own fetcher on every lane | off |
| Search files you uploaded to the maker | `search_files` | a prompt over your own documents | passages with their file names; one model request per call; the store id is typed on the row and sealed | off |
| Make images | `make_image` | a chart, a card or a picture a run should send | a file that rides the delivery; one image request per call; the image model is picked on the row and sealed | off |
| Run code on the maker's servers, Call one of your MCP connections, Drive a browser | none | | greyed in this build with the reason on the row; never tickable | off |

The reaching rows are the egress: the card's `Reaches out:` line names each one the list carries (`web + X search on this model; pages by address through OpenMarket's own fetcher; images on xAI; what it searches for and the pages it reads may carry what this run has read`) and reads `nothing beyond this home` for a list of reads alone. A row the sealed lane cannot run (images on Anthropic, files on xAI, a subscription credential for anything beyond chat) prints its capability row on the install, arm and reseal cards (`Make images: not on your lane (anthropic/claude-x: Anthropic has no image API). Connect OpenAI, xAI or Google in setup, or arm without images.`), the yes proceeds without it, and the function refuses `maker_tool_unsupported` at run time.

Market data, as the header prints them:

```text
markets(returns: {symbols[]{exchange, rawSymbol, normalizedSymbol, coin, category, tenor, coinName, quoteCoinName, fullName, lastPrice, volume24h, volumeChange24h, priceChange24h, oiChange24h, marketcap, liquidity, totalVolume, prices...)
metric_get(returns: {asOf, selector{}, values[], listing_note, interval_note})
metric_series(returns: {asOf, selector{}, metric, params{}, series[]})
metric_list(returns: {metrics[]{name, type, params[], description, package, package_version, unit}})
points(returns: {series[]{id{}, points[], flat_points[], summary{}, columns[], rows[], levels_omitted, bars_skipped, sessions[], prior_session{}, aggregations_skipped, summary_unavailable}})
symbol_resolve(returns: {query, bound, candidates[]{exchange, symbol, normalizedSymbol, instrumentType, quote, assetName, assetTicker, match, confidence}, message})
market_resolve(returns: {query, venue_hint, bound, candidates[]{venue, exchange_id, symbol, label, match, confidence, reason, market, dex, condition_id, slug, outcomes[], constraints{}, order{}, needs[], cli}, message, warnings[]})
symbols(returns: {rawSymbols[]})
normalized_symbols(returns: {normalizedSymbols[]})
coins(returns: {coins[]})
exchanges(returns: {exchanges[], refusedTypes[], failedTypes[]})
enum(returns: {domains[]{name, count, description, dynamic, sample[]}} | {domain, description, dynamic, total, offset, limit, next_offset, values[]{value, description}} | object)
block_sizes(returns: {blockSizes[]})
tenors(returns: {tenors[]})
```

`markets` is the read for a last price and the venue's own 24h change; `metric_get` (`values[]` of `{ok, metric, params, value, data_age_seconds}`) is the read for RSI, SMA, EMA, MACD, Bollinger, ATR, Stochastic, `funding_rate`, `open_interest`, `open_interest_delta_pct`, `volume`, `volume_sma`, `delta_pct`, `rolling_high` / `rolling_low`, with `data_age_seconds` saying how current a number is; `points` is candles and price history; the two resolvers turn a name into a listing or a market.

This watch and the journals:

```text
watch_history(returns: rows {title, summary, raw_text, source_url, source_event_time, market, values}; the same fields INPUT carries)
event_journal_get(returns: {slug, file, content, truncated, total_bytes, returned_bytes, omitted_bytes, limit_bytes, overview_status{}})
event_journal_list(returns: {journals[]{slug, watch_id, label}})
event_journal_search(returns: {query, total, results[]{slug, label, file, matches[]}, newest_story_at, live_fetch, cross_feed{}})
```

`watch_history` on a menu takes `{source, last}`: `source` is a source name from the header, exactly as listed (without the quotes), `last` how many of the newest accepted rows (1 to 50, default 10); the watch is the daemon's to add, so a step can never read another watch's history through it, and a published workflow's history reads stay inside its declared sources. `event_journal_get` reads `events.md` only, bounded and fenced.

The operator's own venue accounts (the `Your positions and balances` row; the card's `Tools:` line says `incl. your positions and balances` when they are on, and the row's warning rides the menu):

```text
hyperliquid_balance(returns: {perp{}, spot[]{coin, token_id, total, hold, entry_notional_usd}, account_mode{}, hip3_perp[]{dex, perp{}}, dex})
hyperliquid_positions(returns: []{coin, size, entry_px, position_value_usd, unrealized_pnl_usd, return_on_equity, liquidation_px, margin_used_usd, leverage_value, leverage_type})
hyperliquid_orders(returns: []{oid, cloid, coin, side, limit_px, size, orig_size, reduce_only, order_type, placed_at_ms, is_spot})
hyperliquid_fills(returns: []{tid, oid, cloid, coin, side, px, size, fee_usd, fee_token, closed_pnl_usd, direction, filled_at_ms, taker})
hyperliquid_funding(returns: []{coin, position_size, funding_rate, usdc_delta, paid_at_ms})
hyperliquid_fees(returns: {taker_rate, maker_rate, spot_taker_rate, spot_maker_rate, referral_discount, active_builder_fee})
hyperliquid_dexes(returns: []{name, deployer, fullName, index} | {dex, assets[]{name, szDecimals}})
hyperliquid_twap_fills(returns: []{twap_id, coin, side, px, size, fee_usd, fee_token, closed_pnl_usd, filled_at_ms, oid})
hyperliquid_twap_history(returns: []{twap_id, coin, side, total_size, filled_size, minutes, randomize, reduce_only, status, error, created_at_ms})
polymarket_balance(returns: {wallet, wallet_type, p_usd_balance, p_usd_balance_raw, collateral_allowances{}, needs_setup, open_order_count, open_order_notional_usd, position_count, position_value_usd})
polymarket_account_positions(returns: []{token_id, condition_id, outcome, outcome_index, side, shares, avg_price, current_price, current_value_usd, cash_pnl_usd, market, slug, neg_risk})
polymarket_open_orders(returns: []{id, token_id, market, market_question, market_slug, outcome, side, price, original_size, size_matched, size_remaining, notional_remaining_usd, status, order_type, created_at, expires_at})
polymarket_fills(returns: []{id, token_id, market, market_question, market_slug, outcome, side, price, size, notional_usd, fee_rate_bps, fee_usd, status, matched_at, transaction_hash, taker_order_id, trader_side})
polymarket_orderbook(returns: {token_id, market, market_question, market_slug, outcome, tick_size, min_order_size, neg_risk, last_trade_price, best_bid, best_ask, spread, midpoint, bids[]{price, size}, asks[]{price, size}})
polymarket_market_lookup(returns: {condition_id, question, market_slug, closed, selected_token_id, selected_outcome_index, selected_outcome, neg_risk, tick_size, midpoint, fee_info{}, tokens[]{token_id, outcome, outcome_index}})
execute_history(returns: []{id, watch_id, action_id, execute_mode, cloid, venue, status, oid, notional_usd, filled_notional_usd, raw_response, fired_at, settled_at, is_reduce, package_version, subscription_epoch, writer})
execute_list(returns: []{id, watch_id, action_id, execute_mode, cloid, venue, status, oid, notional_usd, filled_notional_usd, raw_response, fired_at, settled_at, is_reduce, package_version, subscription_epoch, writer})
execute_summary(returns: {count, pending_submission, submitted, filled, rejected, cancelled, blocked, error, notional_usd})
usage(returns: {limit, remaining, used, reset, window_seconds, daily{}, last_plan_refusal{}})
```

The reaching rows, each one OpenMarket function running its own isolated request:

```text
web_research(returns: {text, provider, model, x_search, x_mirror{}, x_search_hint})
page_read(returns: {text, final_url, title, content_type, chars, truncated, page_path})
search_files(returns: {text, provider, model, store})
make_image(returns: {artifact_id, mime, bytes, width, height, provider, image_model})
```

`web_research` searches on the sealed lane (X only on xai, web on a lane with hosted search); `page_read` takes `{url, max_chars?}` and answers the page's text fenced as data (private addresses and cross-origin redirects refused, `page_read_blocked`); `search_files` takes `{store, ask}` and answers only for the store the seal names (`file_store_not_sealed` otherwise); `make_image` takes `{prompt, size?}` and answers an artifact id the delivery attaches as the image (`image_lane_unsealed` when the images row was not ticked, `image_option_unsupported` for a size the maker cannot take). Each is one more request on the user's own credential and each answer is untrusted data, never an instruction.

Not callable from an ai step (a prompt or a `tools` naming one refuses `watching_unknown_tool` and names the nearest callable): `news_brief` (its schema reaches generation and scheduling), `metric_screen` (a fan-out the firing budget cannot bound), `research_study`, `doc_read`, the Polymarket analytics reads (`polymarket_odds`, `polymarket_leaderboard`, `polymarket_market_summary`, `polymarket_trader_profile`, ...), every `chart_*` read, every room, doc and news verb, every watch verb, and every money function (`order_place`, `wallet_send`, `listing_buy`, `hyperliquid_transfer`). Two functions belong to a tool step, with arguments the author freezes on the card, never to an ai step's menu: `chart_screenshot(returns: {path, bytes, shortId})` (the image rides the delivery as an attachment) and `metric_rule` (the rule step: a metric against a level or a band, emitting a verdict at confidence 1 that a strategy reads without a model).

## Answer shapes

The three shapes an ai step answers in, how the runner parses each, and which readers accept each; read this before setting `output` or choosing a step's reader.

| Shape | `output` | The header says | The turn answers | Parsed as | Read by |
| --- | --- | --- | --- | --- | --- |
| text | `{"type": "text"}` (the default) | `Answer as: text (your reply is delivered as written)` | prose, delivered as a bounded reply of up to 2048 characters; exactly `NO_REPLY` sends nothing and is recorded | a `text` result row; `NO_REPLY` is a quiet row, never an error | a person (the channel), a webhook, a next ai step (as its `Result:`) |
| word | `{"type": "word", "words": ["buy", "sell", "none"]}` (1 to 16 lowercase tokens, no repeats) | `Answer as: one word from: buy, sell, none` | exactly one word from the list | a `word` result row; a word outside the list is a typed `no_action` row and nothing downstream runs for that row | `order` (`buy`, `sell`, `none`), `cancel_order` (`cancel`, `skip`), `transfer` (`send`, `skip`), `purchase` (`buy`, `skip`), `cancel_subscription` (`cancel`, `skip`); a next ai step reads the word as text |
| verdict | `{"type": "verdict"}` | `Answer as: {"direction": "long" \| "short" \| "flat", "confidence": 0..1}` | that JSON, canonical | a `verdict` result row; a malformed verdict is a `no_action` row | `strategy` (sized capital x side multiplier x leverage x confidence); a next ai step reads it as text |

The producer declares its output; the reader's requirement is fixed by its mode. The two are checked when the step is created, imported or installed: a `text` producer cannot feed a money step and a word list must cover every word the mode reads (`watching_reader_unsatisfied` names the shape or the words the reader needs), and one producer fanning out to readers with different requirements refuses (`watching_fanout_incompatible`): an order step and a transfer step can never share one producer. A rule step (`metric_rule` in a tool step) is the model-free verdict.

## Definitions

Say in your words what makes each answer true; the model answers exactly one word. Read this instead of writing a decision as a paragraph.

- A verdict step carries `definitions` with `long`, `short` and `flat`; a word step carries one field per word of its list. Every field is prose in the author's words, 1 to 2000 characters, and may mention sources (§"Mentions"). Every answer of the list must be defined; a key outside the answers and the two extras refuses, each with the message naming the key; a `text` step takes a prompt and refuses `definitions`.
- `unsure` is optional. When the update fits no definition and no `unsure` is written, the daemon composes `when unsure: flat` for a verdict, or the no-action word of the reader for a word list (`none`, `skip`); a list with neither composes nothing, and an answer outside the list is a recorded `no_action` row that acts on nothing.
- `extra` is optional: instructions beside the answers (tone, length, what to ignore, weights, precedence, a context source to consult).
- The daemon composes the INSTRUCTIONS block from them: the `prompt` first when there is one, then `<answer> means: <text>` per answer in the list's order, `when unsure: <text>`, `also: <text>`, and `(<winner> wins over <loser>)` from `overlap_resolution`; the arm card prints that block, so what the human approves is exactly what the turn reads. With `definitions` present, `prompt` is optional (one line framing the task is enough); `prompt` alone is bounded by 16,000 characters.

```json
{
  "output": { "type": "verdict" },
  "definitions": {
    "long": "the latest price in @{BTC rule} is still above the upper band and Hyperliquid BTC funding is below 0.01%",
    "short": "the latest price has fallen back below the hourly 20-period SMA",
    "flat": "anything else, including any bearish post by @DeItaone in the last hour",
    "unsure": "flat, confidence 0.3",
    "extra": "weigh @{Synoptic macro} items from the last 2 hours; a surprise print overrides the crossing"
  },
  "overlap_resolution": { "winner": "flat", "loser": "long" }
}
```

What each answer does depends on the step that reads it:

| Reader | Answers | Effect |
| --- | --- | --- |
| `strategy` | `long`, `short`, `flat` (a verdict with a confidence) | `long` and `short` size a position on that side; `flat` holds no position and closes an open one |
| `order` | `buy`, `sell`, `none` | `buy` and `sell` place the sealed order on that side; `none` places nothing |
| `cancel_order`, `transfer`, `purchase`, `cancel_subscription` | `cancel` / `send` / `buy` / `cancel`, and `skip` | the first word runs the sealed terms; `skip` runs nothing |
| a send (a channel or a webhook), or a gate before one | the answers the author names as forwarding | a named answer forwards the row; every other answer is recorded and sends nothing |

The reader fixes the shape: an `order` reads `buy` / `sell` / `none`, a `strategy` reads a verdict, and a producer that declares another shape or a list missing a reader's word refuses `watching_reader_unsatisfied` at create, import and install, naming the shape or the words the reader needs (§"Answer shapes").

One model check runs at create over the definitions and names an overlap or a contradiction (`watching_definitions_overlap`: "long and flat can both be true when the crossing holds and a bearish post exists; say which wins"). It warns and raises a card question with the pair; the definitions stay the author's. Resolve it with `overlap_resolution: {winner, loser}` (composed into the block as `(flat wins over long)`), never by deleting a case. Write a case as a test the turn can run against INPUT and the menu: a reading, a threshold, a window over a named source. A case the turn cannot check ("the market feels weak") is what `unsure` is for.

## Mentions

The `@{Name}` syntax for naming a source inside a prompt or a definition, and the read-the-watch-first rule; read this before typing a source's name.

- Every source on a watch has a unique name. Derived from what it watches when the author gives none: a condition is `<EXCHANGE:SYMBOL> rule` (`BINANCE_FUTURES:BTCUSDT rule`), an X handle `@DeItaone`, a page its host (`federalreserve.gov`), a feed its display name or host, a vendor stream its display name, a model run its `display_name` (`watch_model_add` writes the member's `name` there, else `Model run:` and the prompt's first sentence) else `model`, an inbound door the watch's label, a timer `timer`, a follow its address; on a watch with several sources each one is named by its slug. An authored `name` on the source stands (`names` per sibling on an upstream source); a derived repeat gains ` (2)`, an authored duplicate refuses `watching_duplicate_source_name`. `watch_show` and the header print the names.
- Write `@{Name}` with the name exactly as printed (case-insensitive, otherwise exact); a single-token name may also be written bare, `@DeItaone` naming the source "@DeItaone" or "DeItaone", `@btc-rule` naming "btc-rule". A bare form glued to a word or a dot (an email, a path) is not a mention, and a bare token naming no source is plain text (`reply @everyone`, a handle): only the braced form must resolve. The model sees the name and the header says what it is; the mention survives a rename and a removed sibling.
- Never number a source in a prompt: the header lists names, not numbers, and a mention is the only thing the validator checks.
- A mention of a name the watch does not have, in the prompt or in any definition, refuses at create with the names that exist (`watching_unknown_source`), so read the watch first: `watch_show` for the sources and their names; `watch_tools` for the functions; then write. A source the prompt needs and the watch lacks is added first (`watch_create` with `sources[]`, or `watch_page_add` for a URL), as context when it should not start runs (`watch.md §"Trigger and context roles"`).
- A mention reaches a source's history through `watch_history({source, last})`, and only that: mentioning a source does not paste its rows into the prompt.
- Steps are named too, and a prompt never has to say a step's id: give every step a `label` (1 to 60 chars, unique on the watch) when you author it, because that name is what the person reads in the delivery header, `om watch history`, `om watch show`, /notis and every card (`ETH test 2 · dip or noise`, never `ETH test 2: ai-97966206`). A step left unnamed is named from what it does (its word list `dip or noise`, a verdict `long/short/flat call`, the first five words of a free-text prompt, `metric_get on BTCUSDT`, `buy ETH 100`); `om watch action rename <watch> <step> "<name>"` names it later without standing the chain down. A name is not a mention: `@{Name}` names sources only.

## Worked prompts

Three complete steps as `watch_action_add` calls: a judge (a verdict from a price fire with two context sources), a note for a person, a screen answering a word.

Every example starts the same way: `watch_show` on the watch (the source names, the steps already there), `watch_tools` (the menu), then the call; a step that names no `tools` runs on the default set, so name a list only to narrow. Each step lands disabled and the result names `om watch arm <watch> <chain>`.

A judge. The watch `btc-breakout` has `"BTC rule"` (a Bollinger crossing, the trigger), `"@DeItaone"` and `"Synoptic macro"` (context); a `strategy` money step reads this step through `input: {"action_id": "judge-1"}`, so the shape is a verdict:

```json
{
  "id_or_slug": "btc-breakout",
  "action": {
    "id": "judge-1",
    "kind": "ai",
    "payload": {
      "prompt": "Decide whether this breakout holds.",
      "output": { "type": "verdict" },
      "definitions": {
        "long": "the latest price in @{BTC rule} (metric_get price on the same selector) is still above bb_upper, and Hyperliquid BTC funding_rate is below 0.0001",
        "short": "the latest price has fallen back below the hourly 20-period sma",
        "flat": "anything else, including any bearish post by @DeItaone in the last hour (watch_history, last 5)",
        "unsure": "flat, confidence 0.3",
        "extra": "weigh @{Synoptic macro} items from the last 2 hours (watch_history, last 3); a surprise print overrides the crossing"
      },
      "overlap_resolution": { "winner": "flat", "loser": "long" },
      "tools": ["metric_get", "markets", "watch_history"]
    }
  }
}
```

A note for a person. The watch `fed-calendar` has one page source; the reader is the channel, so the shape is text and `tools` is `[]` (INPUT holds the change; nothing reaches out):

```json
{
  "id_or_slug": "fed-calendar",
  "action": {
    "id": "note-1",
    "kind": "ai",
    "payload": {
      "prompt": "Write three lines for a person: what changed, what it means for front-end rates, and the link from INPUT. Answer NO_REPLY when the update is a schedule change with no decision in it.",
      "output": { "type": "text" },
      "tools": []
    },
    "channel": "telegram-desk"
  }
}
```

A screen answering a word. The watch `eth-funding-negative` fires when ETH funding crosses below zero (its source is named `BINANCE_FUTURES:ETHUSDT rule`); an `order` money step with no `terms.side` reads this step, so the word names the side:

```json
{
  "id_or_slug": "eth-funding-negative",
  "action": {
    "id": "screen-1",
    "kind": "ai",
    "payload": {
      "prompt": "Screen this funding fire.",
      "output": { "type": "word", "words": ["buy", "sell", "none"] },
      "definitions": {
        "buy": "funding in @{BINANCE_FUTURES:ETHUSDT rule} printed below zero and open interest is falling (metric_get open_interest_delta_pct with bars 8 is negative): shorts are paying and unwinding",
        "sell": "funding printed below zero but open interest is rising: shorts are still building",
        "none": "anything else, and whenever a reading is older than 2 hours (data_age_seconds above 7200)"
      },
      "tools": ["metric_get"]
    }
  }
}
```

The money step then reads it: `{"kind": "money", "input": {"action_id": "screen-1"}, "payload": {"mode": "order", "terms": {"venue": "hyperliquid", "asset": "ETH", "order_type": "market", "size_mode": "quote"}, "boxes": {"size": {"hint": "quote size in USDC"}}, "caps": {"max_fires": 1}}}`; `none` does nothing and the row is recorded. The three steps share one rule: the definition names the reading and the threshold the turn can check, the list holds exactly the functions those checks need (or nothing, when the default set already does), and the shape is the reader's.

## Refusal is the fix

The typed refusals a prompt can get back, what each says, and the one change that clears it; read this before relaying any of them or retrying.

| Code | What it says | Change |
| --- | --- | --- |
| `watching_unknown_source` | `"Funding" is not a source on this watch; sources: "BTC rule", "@DeItaone", "Synoptic macro"` | mention one of the listed names as `@{Name}` (or its bare `@token` form), in the prompt and in every definition, or add the source to the watch first, then resubmit |
| `watching_unknown_tool` | `"funding_rate" is not callable; nearest: metric_get` | name the nearest callable, in `tools` and in the text, or drop the name; a name outside the menu is never a tool |
| `watching_reader_unsatisfied` | the producer's output does not satisfy its reader: a strategy needs a verdict, an order a word from a list covering `buy`, `sell`, `none` | set the producer's `output` to the shape the reader needs (a verdict for a strategy, the mode's words for a money step), or point the reader at a producer that answers it |
| `watching_fanout_incompatible` | one producer feeds readers that need different shapes | split the producer: one step per requirement |
| `watching_definitions_overlap` | `long and flat can both be true when the crossing holds and a bearish post exists; say which wins` | a warning with a card question: add `overlap_resolution: {winner, loser}`, or accept the overlap on the card |
| `watching_duplicate_source_name` | two sources of the watch carry the same authored name | give one a distinguishing name (`"BTC rule (VWAP)"` beside `"BTC rule (RSI)"`) |
| `invalid_input` on `definitions` | `definitions need output.type word or verdict; a text step takes a prompt`, `definitions must define every answer; missing: none`, `definitions.<key> names no answer of this step; answers: buy, sell, none` | match the fields to the declared answers: one per answer, the two extras at most, none on a text step |
| `watching_chain_too_deep` | `9 steps from the source; the limit is 8` | shorten the chain, or split it across two watches joined by an upstream |
| `watching_unknown_producer` | `input` names a step that does not exist | name a step of this watch, or of a sibling source of the same composite |
| `unattended_tool_unresolved` (at the arm) | a `tools` name does not resolve on this home, or is not on the unattended list | remove the name, or install what provides it, then arm again |

Three rules ride every row of the table: change the spec, never the user's intent (a level, a door, a price, a box value are the user's to change); never resubmit unchanged; a refusal is not an error to relay, it is the next edit. Ask the user only when the fix changes what the watch means.
