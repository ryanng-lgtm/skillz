---
name: openmarket-event-watches
description: Create, inspect, pause, resume, remove, and read OpenMarket event watches and their local event journals. Use when the user wants to monitor a non-price event stream over time, asks what watched topics exist, or asks for the saved events/overview of a watched topic. Event journals are on-demand context only and must not be injected unless the user asks or the topic is relevant.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om event watches

Event watches are persistent local monitors for non-price event streams. A watch is stored at `~/.openmarket/event-watches/<id>.json`; its human-readable journal lives at `~/.openmarket/event-journal/<slug>/`, and its structured event rows live in SQLite.

Use this skill when:

- The user asks to track, monitor, follow, or keep an event journal for a news/social/account/event stream.
- The user asks what event watches are configured, whether a topic is being watched, or what the daemon has captured for a watched topic.
- `om status` reports enabled event watches and the user's question may be about one of those watched topics.

Do not treat event journals as live venue state or sufficient trading authority. For market prices, positions, balances, orders, or probabilities, use the live market and venue tools.

## Discovery

Start with `om status --format json` for state questions. If `event_watches.enabled` is greater than zero, call `om event-watch list --format json` before deciding whether a journal is relevant.

Use `om event-watch list --enabled --format json` when the user asks what is currently active. Use `om event-watch show <id-or-slug> --format json` before editing, pausing, resuming, removing, or pulling a journal for a specific watch.

## Create a watch

`om news` feed acquisitions (follow/add/create/fork) auto-attach a per-feed event-watch by default, so for news/social streams check `om event-watch list` before creating one by hand — the watch may already exist (auto-created watches carry an `origin` field naming the provider + feed). Manual creation remains the path for `openmarket` market streams and backfill.

Never hand-build a stream ref to watch a news feed. `om news follow` / `om news create` already attach a correctly scoped watch; a hand-built one is how a watch ends up consuming the WHOLE vendor feed instead of the one feed the user asked for. A news stream ref is only complete with its per-feed id — `attention` and `attention-briefs` need `extra.subscription_id`, `synoptic` needs `extra.stream_id` (all available from `om news list --format json`). An adapter-wide ref like `{"adapter":"attention-briefs","channel":"briefs"}` is rejected at creation.

**Repairing a feed that has no watch is its own verb: `news_attach`.** When the user already holds the feed but nothing consumes it (`eventWatchLinked: false`, or a `feed_unwatched` warning from `watching_overview`), that is the call — not `event_watch_create`. It attaches exactly what an acquisition would (the feed's own trigger becomes the goal, the user's classifier and routing settings apply) and is idempotent, so a feed that is already covered reports `exists` and nothing is written. `event_watch_create` on a news stream ref fills a missing `channel` and claims the watch for news when the feed is demonstrably the user's, but the claim depends on the vendor's owned list being readable at that moment, and an offline create leaves the watch hand-built, which `news_delete` will not retire. One call that cannot get either wrong beats two that can. See `news.md`.

Creation requires a concrete source stream from a registered listener adapter. Ask for the missing source detail if the user has not supplied it; do not invent adapter credentials or stream identifiers. Current production adapters include `openmarket` market streams, `synoptic` news/social streams, and the `attention` / `attention-briefs` news feeds.

Synoptic news/social stream delivery is live and at-most-once. OpenMarket drops the historical `lastPosts` frame that predates subscription open, reconnects idle sockets, and does not replay posts missed while the daemon is offline or reconnecting.

Synoptic also supports bounded historical post pulls through `om event-watch backfill`. Backfill rows are written with `data_mode=backfill`, `observed_at=null`, and `source_event_time` from the upstream source timestamp when available. If Synoptic does not provide that timestamp, OpenMarket uses Synoptic `createdAt` as the best available provider-created clock and records `source_event_time_origin=provider_created_at`; true upstream clocks use `source_event_time_origin=source`. A live event whose timestamp had to be scraped from payload text fields records `derived` in its stored context (the row column stays empty — a scraped guess is never presented as a provider clock). Backfill does not require pausing the watch — it imports silently and coordinates with live ingest. Explicit backfill NEVER draws from the watch's daily live classifier budgets, in either direction: each run spends only its own per-run LLM-call ceiling (`max_llm_calls`, default 500; 0 means no ceiling), so a big backfill cannot starve live classification and a busy live day cannot gate a backfill. If more remains for another reason the run returns `truncated` with a `resume_cursor` (pass it back as `from` to continue); a shed batch stops the run with the cursor at the earliest shed event (shed events are not stored), resuming shortly for `stop_reason: backpressure` (transient classifier backpressure). The silent 7-day restart catch-up is a **pull-feed** mechanism (the `attention` / `attention-briefs` news feeds); **Synoptic does not have it.** As the paragraph above states, Synoptic delivery is at-most-once and does **not** replay posts missed while the daemon was offline or reconnecting, so nothing self-heals a Synoptic gap on restart. For any Synoptic offline window, run an immediate bounded `om event-watch backfill` to recover the gap rather than waiting on a catch-up that never arrives. Use `--data-mode backfill --time-basis source_event_time` for follow-on research.

**`status: budget_paused` is a question, never a completion.** When a run's own ceiling binds, the report is `budget_paused` carrying `resume_cursor`, `llm_calls_spent`, and a `budget_paused` object with the classified-through date, an estimate of what remains, and the exact `resume_command`. Relay it to the user as a CHOICE: continue from the cursor (re-run with `from: <resume_cursor>`), raise or drop the ceiling (`max_llm_calls`, 0 = none), or stop here. Always include the resume command. Never summarize a `budget_paused` (or any budget stop) as "done", "complete", or a finished backfill: the window is not covered, and presenting it as covered is exactly the silent-stop failure this contract exists to prevent.

```bash
om event-watch create \
  --goal "Track live BTC trade prints that may affect a named event watch" \
  --stream-ref '{"adapter":"openmarket","exchange":"binance","symbol":"BTCUSDT","channel":"TRADE"}' \
  --source-name "OpenMarket BTCUSDT trades" \
  --format json
```

The `--stream-ref` value is a JSON `StreamRef`. The top-level `adapter` defaults to `stream_ref.adapter`. Optional `--id` and `--slug` must be path-safe lowercase slugs. Use `--disabled` when the user wants to draft the watch without starting daemon consumption.

Use `--classifier-provider <id>` and optionally `--classifier-model <id>` when the user wants this watch to use a specific LLM route for every incoming event. A model override requires an explicit provider. If omitted, the daemon uses the active LLM configuration from exported variables or stored auth profiles.

`llm_every_event` watches default to 1000 LIVE classified incoming items per watch per UTC day and 2000 LIVE classifier LLM calls per watch per UTC day. The call budget sits above one call per event on purpose, so the 1000-item budget is normally the one that binds. These budgets gate live ingest only; explicit `om event-watch backfill` spends its own per-run ceiling instead.

**Never lower a daily cap the user did not ask you to lower.** `--classifier-max-daily-events <n>` and `--classifier-max-daily-llm-calls <n>` are for an explicit user request only — not a precaution, not a cost guess, not a tidy round number you prefer. The defaults are sized for real feeds; a watch created under a smaller one silently drops real events for the rest of the UTC day, and the user never sees what they missed. There is no "safe" small cap: a quiet feed never reaches 1000, and a busy feed is exactly the one whose events matter.

When the user DOES ask for a lower cap, confirm it back in one line with the consequence before you create or edit: name the number and state the consequence in the unit that cap actually counts. For `--classifier-max-daily-events <n>`: once the watch classifies that many LIVE items in a UTC day, the rest of that day's events are shed unclassified. For `--classifier-max-daily-llm-calls <n>`: once the watch spends that many LIVE classifier calls in a UTC day, the rest of that day's events are shed unclassified — and a call covers a whole coalesced batch (up to 25 items), so `n` calls cover `n` items on a feed that trickles and up to 25× that on a bursty one. Never quote the call cap as an item count. Either way the shed is not queued and not delivered late — it is a hole in the journal that only `om event-watch backfill` can refill. Say where the shed shows up — `om event-watch show <id>` prints a `Shed:` line counting dropped events and a `degraded` status, and in `om chat` the footer under your create/edit call names the caps in force. Raising a cap needs no such warning.

The caps are also disclosed as they fill, so answer "why did this feed go quiet?" from those surfaces rather than guessing. `om event-watch show <id>` always prints the resolved budgets and a `Used today:` line; at 80%+ of either budget the watch appears in `watching_overview`'s `attention_needed` as `watch_budget_pressure`, in the `om news` pane as its feed's problem row, in `om doctor`, and as a badge in the `om chat` header, and `om event-watch list` names it under the table. Every one of those that has room for a command ends in the raise command, which is the only fix; the `om chat` header badge is a one-line badge and names the watch and the percentage alone, so quote the raise command yourself when you relay it. A shed is never re-delivered, so raising the cap protects the REST of the day and `om event-watch backfill` refills the hole already made.

Use `--classifier-mode accept_all` only when the user explicitly wants every incoming stream item accepted without LLM classification. Do not combine accept-all mode with include/exclude filters or extra classifier guidance; those controls require `llm_every_event`. Accepted-all events still write SQLite rows, update the retained `events.md` projection, run overview synthesis, and pass through notification gates. They store NO classifier confidence (no classifier ran), so a research `--min-confidence` floor always excludes them — the research report warns when that happens.

Use `--notify` only when the user explicitly wants immediate human nudges. A notify-enabled watch routes its sends like price alerts, **materialized** and literal (`notify.channels[]` stores channel ids): `--notify-channel <name>` sets the destinations; a notify-enabled watch created without one seeds the default (or lone) channel, and with several channels but no default it is card-only. An **empty** destination set is card-only — the fire shows as an inline `om chat` card only, no push. There is no read-time fan-out. Each fire must reach all of its resolved channels (partial failures retry per channel on restart recovery). The om agent writes the alert by default (`--notify-style agent`): its message posts in its paired chat and the same text is delivered to the watch's channels, so every sink carries one message. Whenever you create or edit a notify-enabled watch, TELL the user who writes their alerts and where they arrive — when the agent is not paired, channels receive the plain alert instead until `om setup telegram` pairs it (then restart the daemon — `om service restart`, or re-run `om run` if it runs in the foreground — since chat surfaces start at boot); creating or editing an agent watch on an unpaired host prints a WARN with that same fix, and the style goes live once the agent is paired. Pass `--notify-style alert` only when the user wants the plain alert with no LLM. With ZERO channels configured, notify stays ENABLED but delivery is inline cards in an open `om chat` session only (plus the paired chat when the agent is paired) until a channel exists. Send failures to a configured channel remain pending for bounded startup recovery; OpenMarket does not continuously retry notification failures inside the same daemon run.

The live classifier stores outcome classes: `irrelevant`, `duplicate`, `corroboration`, `update`, or `major_update`. `corroboration`, `update`, and `major_update` append to the journal. Classifier `notify` is advice only; OpenMarket still applies channel, confidence, cooldown, and user preference gates before delivery.

Incoming stream bursts are coalesced per watch before classification. Batch classification is only a cost/context optimization: each source item still receives its own SQLite row, `batch_id`/`batch_index`, event-journal append if accepted, and item-level notification decision. Runtime status `degraded` means local backpressure shed input, classifier budget pressure, or another runtime failure happened recently; successful appends preserve that status until a lifecycle recovery path refreshes it.

## Read journals

Use `om event-journal get <slug>` for the current `overview.md` projection. Use `om event-journal get <slug> --file events.md` for the retained accepted-event Markdown projection; it is tail-bounded on read and older entries may be trimmed from Markdown after the retention cap. The journal files are `metadata.md`, `events.md`, and `overview.md` (plus a legacy `background.md` on older journals); do not look for `timeline.md`, `sources.md`, `summary.md`, `summary.previous.md`, or `summary.json`.

An `overview.md` that no synthesis has ever written comes back with an `overview_status` block instead of standing on its own. Read the cause out rather than reading the placeholder out as an overview: `no_events` and `waiting_for_threshold` mean the watch is working and has not accumulated enough accepted events yet, `classifier_failing` means events arrived and failed classification (the block counts them in `error_events` and quotes `runtime_error`), `overview_disabled` and `synthesis_not_run` mean a pass has to be asked for, and `watch_removed` means nothing will ever write the file again. The block's `fix` is the command that writes it now, and it is null exactly in the `watch_removed` case.

Use `om event-journal search <query> --format json` when the user asks whether the retained Markdown journals mention a subject and you do not know the slug.

Use `om event-watch events <id-or-slug> --format json` when the user needs structured filtering by outcome, observed time, source, confidence, journal-commit state, or notification state, or when they need batch metadata for grouping burst decisions. This reads SQLite event rows, not Markdown, and is the preferred surface for event queries that need filters. Raw source text is omitted by default; pass `--include-raw-text` only when the user specifically needs the original source body.

A page is bounded: 50 rows by default, 500 at most. Report counts from `total_matching` on the result, never from how many rows came back — `truncated` says whether more match beyond the page, and `next_cursor` goes back as `before` to read the next one. A cursor is part of the query the count is taken through, so on a page read with `before`, `total_matching` is what remains past that cursor: answer "how many are there?" from a first page or from `total_stored`, the unfiltered population of the same scope, never from a resumed page's total. A cursor also belongs to the view that issued it — merged (no id) and single-watch pages sort on different clocks, and the wrong view's cursor is refused. Those totals count rows the store HOLDS: non-accepted outcomes keep only a rolling retention window per watch, so a total under `--outcome error` is a floor on what happened.

Only pull the journal that is relevant to the user's question. Do not bulk-load every journal into prompt context.

## Repair error rows

An event row with outcome `error` is an event the watch RECEIVED and stored but never got a verdict on: the classifier call failed — a lapsed or missing LLM credential, a provider outage, a malformed batch reply — and the row kept its raw text and full source context. Nothing about the event is missing except the judgement, so the repair reads from disk, never from the vendor.

`om event-watch reclassify <id-or-slug>` (action `event_watch_reclassify`) re-runs the classifier over those rows. Each row keeps its id, arrival time, source clock and data mode, so a backfilled row stays backfilled and the timeline does not jump it to the present; a row that now classifies as accepted joins the journal and the accepted history. It SPENDS — one classifier LLM call per batch of 25, charged against this watch's own daily classifier budgets — so it is bounded per call (`--limit`, default 50, max 200), reports how many rows remain for the next call, and reports a bound budget as a shed cause rather than spending silently. `--since <time>` bounds the pass to the window a failure covered.

Fix the cause before spending on the repair: a second pass against the same broken credential writes the same error rows again. Rows that retained no raw text cannot be re-judged at all and are reported separately — those need `om event-watch backfill` over their window.

An error row the watch has already classified past reads as `error (stale)` in `om event-watch events` and as `watch_error_stale` in `watching_overview`: the classifier recovered on its own and the stored failure is history, not a live break. Repairing those rows still needs an explicit reclassify — nothing re-judges them automatically.

## Overviews

OpenMarket refreshes the SQLite overview snapshot automatically on conservative event-count thresholds and after major updates. `overview.md` is the readable projection from that snapshot. Use `om event-watch synthesize <id-or-slug>` when the user asks for an immediate refresh or when automatic overview synthesis failed — it WRITES (a new overview snapshot plus a rewritten `overview.md`), each pass is a paid LLM call, and it takes the watch's exact id, not a fragment.

Synthesis drains pending accepted events in pages (default 100 per pass), and each development it authors records the newest journal row its pass read — the watermark backtest context replay uses to prove an entry knew nothing of later events. `--page-size <n>` (1-100) sets that granularity: after a bulk backfill, a single default-page pass stamps every development with the whole span's last row, so a context-replay backtest must exclude the entire backbone as future-aware; synthesizing at `--page-size 5` instead authors the timeline in 5-event steps that replay progressively. Combine with `--rebuild` to re-author an EXISTING backbone at finer granularity (also the upgrade for legacy backbones that predate watermarks and count as unproven authorship in backtests). Each pass is a paid LLM call — the projected pass count is disclosed on stderr before synthesis runs, and a rebuild that cannot finish inside the pass cap is refused before spending anything. A rebuild keeps lived overview snapshots (they are the record of what live consumers acted on) and writes its new head on top; add `--with-snapshots` to also mint one RECONSTRUCTED overview snapshot per non-final replayed page (brief included, one extra paid call per page, count disclosed) — labeled rows in a separate lineage that serve advanced-mode backtest replay over the span and never serve live consumers.

Use `--market <EXCHANGE:SYMBOL>` (repeatable) to tag the watch with related markets. Tags are metadata for price-alert catalyst pairing: when a price alert fires on a tagged market, the fire notification appends this watch's freshest accepted event as a "Possible catalyst" line. They never change what the watch matches.

## Edit a watch

Use `om event-watch edit <id-or-slug>` to change an existing watch in place (goal, include/exclude filters, extra classifier guidance, classifier mode/provider/model/budgets, notify, overview, label, `--market` tags with `--clear-markets` to remove) instead of removing and recreating it. Omitted flags are untouched, `--clear-*` flags reset an override to its default, and `--include`/`--exclude` replace the whole list. The stream binding is immutable — rebind by creating a new watch. Enabling notify on a watch that was never routed homes it the same way create does — to the channel this conversation posts to, else the configured default, else card-only if no channel is set — and the edit result names where it landed, so relay that to the user. A watch whose channels you deliberately cleared (`--clear-notify-channel`) stays card-only; enabling notify does not silently re-home it. Passing `--notify-channel <name>` overrides the homing, and a NAMED but non-existent `--notify-channel` is still rejected (a typo, not a default). To route a watch onto or off a channel from the channel's side, `om channel <name> --add <slug>` / `--remove <slug>`.

## Lifecycle

- `om event-watch pause <id-or-slug>` disables a watch and keeps its journal.
- `om event-watch resume <id-or-slug>` re-enables a watch.
- `om event-watch remove <id-or-slug>` removes the spec and preserves its journal. It also destroys the watch's stored events, its backbone, every snapshot it holds (the lived synthesis passes and any materialized backtest lineage), its chart binding and any room shares bound to it, so it confirms first and prints what it destroyed; `--yes` is the scripted form. `om event-watch rotate-token` confirms the same way, because rotating revokes the token every live producer is pushing with. Both raise an approval card in chat.
- Deleting, removing, or unfollowing a news feed retires the watch it auto-attached and keeps that watch's journal; the result names it as `removedWatch`. A hand-built watch on the same stream is never auto-retired — it comes back as `keptWatch`, and `om event-watch remove <id>` is its explicit cleanup.

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

- `om event` — (bespoke; see narrative above)
- `om event push` (action: `event_push`) — Push one event into an inbound event watch.

- `om event-journal` — (bespoke; see narrative above)
- `om event-journal get` (action: `event_journal_get`) — Return one local event journal Markdown file by slug.
- `om event-journal list` (action: `event_journal_list`) — List local event journals by slug, including the backing watch id/label when a watch spec still exists.
- `om event-journal search` (action: `event_journal_search`) — Search local event journal Markdown files by plain substring.

- `om event-watch` — (bespoke; see narrative above)
- `om event-watch backfill` (action: `event_watch_backfill`) — Run a historical backfill for an existing (live or paused) or newly-created event watch.
- `om event-watch create` (action: `event_watch_create`) — Create a daemon-owned event watch from a natural-language goal and a structured stream reference.
- `om event-watch edit` (action: `event_watch_edit`) — Update a watch's goal, filters, extra guidance, classifier, notify, overview, or related-market tags.
- `om event-watch events` (action: `event_watch_events`) — Query structured SQLite event rows by outcome, time, source, confidence, and notification state.
- `om event-watch list` (action: `event_watch_list`) — List configured event watches with their daemon runtime status.
- `om event-watch pause` (action: `event_watch_pause`) — Disable one event watch by id or slug — consuming strategies are NOT auto-paused: entries stop arming (a paused watch produces no events) while managed exits stay enforced.
- `om event-watch reclassify` (action: `event_watch_reclassify`) — Re-run the classifier over event rows this watch already stored with outcome `error` (a failed classification, e.g. a missing or expired LLM credential), using each row's retained raw text and source context.
- `om event-watch remove` (action: `event_watch_remove`) — Remove one event watch by id or slug — consuming strategies auto-pause, the journal is preserved, and the watch's stored artifacts and room shares go with it.
- `om event-watch resume` (action: `event_watch_resume`) — Re-enable one paused event watch by id or slug — event flow returns automatically and consuming strategies need no re-arm.
- `om event-watch rotate-token` (action: `event_watch_rotate_token`) — Mint a fresh ingest token for an inbound event watch and invalidate the old one immediately (rotation IS revocation: only the token's sha256 is stored, so the previous token stops authorizing the instant the new hash lands).
- `om event-watch show` (action: `event_watch_show`) — Show one event watch spec and its daemon runtime status by id or slug, plus the signals and strategies that depend on it (the blast radius of a later pause or remove).
- `om event-watch synthesize` (action: `event_watch_synthesize`) — Refresh one event watch's overview.md from its accepted event history.

<!-- AUTO: END COMMAND REFERENCE -->
