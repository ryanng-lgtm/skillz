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

### Guardrails

- Do not treat event journals as live venue state or sufficient trading authority. For market prices, positions, balances, orders, or probabilities, use the live market and venue tools.
- Never hand-build a stream ref to watch a news feed — `om news follow` / `om news create` attach a correctly scoped watch, and a hand-built one can consume the WHOLE vendor feed; the per-feed id forms live in §"Create a watch". A ref the user supplies complete — its per-feed id included — is not hand-built; the rule is against INVENTING that id. A feed the user already holds is still `news_attach`'s job, not `event_watch_create`'s.
- Creating a vendor-fed watch requires a concrete source stream from a registered listener adapter — ask for what is missing; never invent adapter credentials or stream identifiers; a watch the user feeds themselves takes `--inbound` and no stream ref (§"Create a watch").
- Never lower a daily classifier cap the user did not ask you to lower — a smaller cap silently sheds real events for the rest of the UTC day, and an asked-for cap is confirmed back with its consequence (§"Budgets and caps").
- `status: budget_paused` is a question, never a completion — relay the choice and always include the resume command; never summarize a budget stop as done (§"Backfill").
- `om event-watch remove` preserves the journal but destroys the watch's stored events, backbone, snapshots, chart binding and room shares — it confirms first, as does rotate-token (§"Lifecycle").
- Only pull the journal that is relevant to the user's question. Do not bulk-load every journal into prompt context.
- An X account is watched keyless through the `x` adapter (`extra.handle`, a 5-minute timeline poll); `om event-watch show` prints its backend coverage, and `Coverage: partial` means silence from it is not evidence of no posts; a `known gap since` note on that line is a window the poller moved past during a flood without reading, which no `om event-watch` verb clears (a backfill that reads it would), so the watch stays incomplete over that window even while its state reads ok. Live X search across X (an xAI credential: SuperGrok / X Premium subscription or API key) stays the escalation beyond one handle's timeline, reached through `web_research`, never by the poller. Create the watch either way; if the result carries `x_search_hint`, relay it once and never nag afterward.

- A watch request names a subject, not a source, and the composer verb owns that shape end to end: `watch_compose` (`om watch <sentence>`) researches the subject's channels, probes and commits the covering set under one group with notify enabled, and orients once in the same reply. Open with the dated read of where the subject stands (what they last said or did, dates kept), then the committed members and delivery state; offer the found-but-unwatched sources as ONE natural sentence the user can answer (could also watch: X, Y; say add them; never auto-commit one, the user confirms and a re-run with `sources` commits it); state every gap plainly. Reach for the individual verbs below only when the user names ONE concrete source or stream ref. "Tell me whenever <subject> posts about <topic>" is the same shape: topic in `intent`, never hand-rolled `event_watch_create`.

- A CADENCE BRIEF is not a watch request: "every weekday at 8, tell me only if X said something new" routes to `skill_read("schedules")` and ONE errand with `web_research`, no watches, no composer. The composer answers "watch X for me" (continuous, event-by-event). When composed watches exist only to feed a scheduled digest, pass `notify: false` at compose time so they record silently from birth; never create them noisy and edit them quiet.
- A request to watch something is an instruction, not a question: run `watch_compose` in the turn it was asked. When an equivalent watch already stands the composer adopts or extends it and says so; never answer a watch request with a status report alone, and never decompose the subject by hand when the composer covers it.

### Routing

- A news feed's watch: check `om event-watch list` first (acquisitions auto-attach one); an unwatched feed is repaired with `news_attach`, never `event_watch_create` (news.md).
- A watch task that names a news, social, or text feed is a news task first: read `news.md` (`skill_read("news")`) before creating, editing, or retiring that watch — the feed surface owns acquisition, mute/noise, and retirement, and this file owns only the watch mechanics under it.
- Backfilled rows have no `observed_at` — follow-on research needs `--data-mode backfill --time-basis source_event_time` (research.md).
- `accept_all` events store no classifier confidence, so a research `--min-confidence` floor always excludes them (research.md; §"Create a watch").
- Filtered or structured event queries go to `event_watch_events`, never hand-parsed Markdown (§"Read journals").
- Alert shadow watches are alert-managed — generic lifecycle AND edit refuse `event_watch_alert_managed`; drive the alert verbs instead (alerts.md; §"Lifecycle").

## Discovery

List and inspect before acting — `event_watch_list` / `event_watch_show` ahead of any edit, pause, resume, remove, or journal pull.

Call `event_watch_list` for state questions — it answers "what am I watching?" on its own, and an empty list is an answer, not a reason to look elsewhere. In a `system_status` payload the `event_watches.enabled` count is what is still armed to capture, not what is readable, because paused and removed watches keep their journals; check `event_journal_list` before deciding whether a journal is relevant. Reach for `system_status` itself only when the ask is about local setup state beyond the watches.

Use `om event-watch list --enabled --format json` when the user asks what is currently active. Use `om event-watch show <id-or-slug> --format json` before editing, pausing, resuming, removing, or pulling a journal for a specific watch.

## Create a watch

Create from a concrete stream ref — for news feeds check the auto-attached watch first; `news_attach` repairs an unwatched feed, and a news ref is never hand-built.

As an action: `event_watch_create({ user_goal, source: { adapter, stream_ref } })`. `user_goal` is the plain-language goal the watch serves; `source.adapter` names the listener; `source.stream_ref` is the ref object described below and is always required — an inbound watch carries `stream_ref: { adapter: "inbound" }`, which simply takes no routing keys. In the action form the adapter is named in both places and the two must agree — a `stream_ref.adapter` that differs from `source.adapter` is rejected. All three objects reject unknown keys, so `channel` belongs on `stream_ref` and the per-feed id inside `stream_ref.extra`, never beside them.

`om news` feed acquisitions (follow/add/create/fork) auto-attach a per-feed event-watch by default, so for news/social streams check `om event-watch list` before creating one by hand — the watch may already exist (auto-created watches carry an `origin` field naming the provider + feed). Manual creation remains the path for `openmarket` market streams and backfill.

Never hand-build a stream ref to watch a news feed. `om news follow` / `om news create` already attach a correctly scoped watch; a hand-built one is how a watch ends up consuming the WHOLE vendor feed instead of the one feed the user asked for. A news stream ref is only complete with its per-feed id: `attention` and `attention-briefs` need `extra.subscription_id`, `synoptic` needs `extra.stream_id` (all available from `om news list --format json`), and the keyless `x` adapter needs `extra.handle`, one X account per watch (`{"adapter":"x","channel":"posts","extra":{"handle":"DeItaone"}}`; case does not matter and a leading @ is fine). An adapter-wide ref like `{"adapter":"attention-briefs","channel":"briefs"}` is rejected at creation.

**Repairing a feed that has no watch is its own verb: `news_attach`.** When the user already holds the feed but nothing consumes it (`eventWatchLinked: false`, or a `feed_unwatched` warning from `watching_overview`), that is the call — not `event_watch_create`. It attaches exactly what an acquisition would (the feed's own trigger becomes the goal, the user's classifier and routing settings apply) and is idempotent, so a feed that is already covered reports `exists` and nothing is written. `event_watch_create` on a news stream ref fills a missing `channel` and claims the watch for news when the feed is demonstrably the user's, but the claim depends on the vendor's owned list being readable at that moment, and an offline create leaves the watch hand-built, which `news_delete` will not retire. One call that cannot get either wrong beats two that can; the feed-side doctrine is news.md §"After any acquisition, verify the pair".

Creating a vendor-fed watch requires a concrete source stream from a registered listener adapter. Ask for the missing source detail if the user has not supplied it; do not invent adapter credentials or stream identifiers. Current production adapters include `openmarket` market streams, `synoptic` news/social streams, the `attention` / `attention-briefs` news feeds, the keyless `feed` poller, and the keyless `x` account timelines (`extra.handle`; the runtime row's `collection_state` reports the backend's coverage every poll).

A `feed` watch polls one public URL with no credential: an RSS 2.0 / RSS 1.0 / Atom feed (a Google News search RSS, a YouTube channel feed, a podcast feed), a JSON Feed, or an EDGAR per-CIK submissions JSON (`https://data.sec.gov/submissions/CIK##########.json`). Its stream ref is exactly `{"adapter":"feed","channel":"items","extra":{"url":"<normalized http(s) URL>"}}`: creation requires the normalized spelling (lowercase scheme and host, no default port, no userinfo, no fragment) and the refusal quotes the spelling to use. The first poll sweeps the feed's current entries silently (`swept=<n>`, nothing fires), and every entry that appears afterwards is an event; entries the feed drops while the daemon is down are gone for good, and `event_watch_backfill` answers `backfill_unsupported` for this adapter. Feed text is a stranger's writing, so the classifier and overview prompts frame it as untrusted data and the notification quotes the source text inside a fence. Polls run every five minutes by default (`OM_FEED_POLL_INTERVAL_MS`, 60s floor); a URL on `127.0.0.0/8` is refused unless the test-rig switch `OM_FEED_ALLOW_LOOPBACK=1` is set.

A watch whose events the user pushes themselves takes no stream ref: `om event-watch create --inbound` opens a door at `POST /ingest/v1/<watch-id>` (also reachable as `om event push`), bounded by `--ingest-daily-cap <n>` (default 2000 accepted pushes per UTC day; a typed 429 above it). The door starts closed — no token hash, a uniform 401 on every request — until `om event-watch rotate-token <id>` mints the token on a stdio surface, which prints it once.

```bash
om event-watch create \
  --goal "Track live BTC trade prints that may affect a named event watch" \
  --stream-ref '{"adapter":"openmarket","exchange":"binance","symbol":"BTCUSDT","channel":"TRADE"}' \
  --source-name "OpenMarket BTCUSDT trades" \
  --format json
```

The `--stream-ref` value is a JSON `StreamRef`. The top-level `adapter` defaults to `stream_ref.adapter`. Optional `--id` and `--slug` must be path-safe lowercase slugs. Use `--disabled` when the user wants to draft the watch without starting daemon consumption.

Use `--classifier-provider <id>` and optionally `--classifier-model <id>` when the user wants this watch to use a specific LLM route for every incoming event. A model override requires an explicit provider. If omitted, the daemon uses the active LLM configuration from exported variables or stored auth profiles.

Use `--classifier-mode accept_all` only when the user explicitly wants every incoming stream item accepted without LLM classification. Do not combine accept-all mode with include/exclude filters or extra classifier guidance; those controls require `llm_every_event`. Accepted-all events still write SQLite rows, update the retained `events.md` projection, run overview synthesis, and pass through notification gates. They store NO classifier confidence (no classifier ran), so a research `--min-confidence` floor always excludes them — the research report warns when that happens.

The live classifier stores outcome classes: `irrelevant`, `duplicate`, `corroboration`, `update`, or `major_update`. `corroboration`, `update`, and `major_update` append to the journal. Classifier `notify` is advice only; OpenMarket still applies channel, confidence, cooldown, and user preference gates before delivery.

Incoming stream bursts are coalesced per watch before classification. Batch classification is only a cost/context optimization: each source item still receives its own SQLite row, `batch_id`/`batch_index`, event-journal append if accepted, and item-level notification decision. Runtime status `degraded` means local backpressure shed input, classifier budget pressure, or another runtime failure happened recently; successful appends preserve that status until a lifecycle recovery path refreshes it.

## Backfill

Bounded historical import — `event_watch_backfill` spends its own `max_llm_calls` ceiling and reports `truncated` or `budget_paused` with a `resume_cursor`, never a silent stop.

Synoptic news/social stream delivery is live and at-most-once. OpenMarket drops the historical `lastPosts` frame that predates subscription open, reconnects idle sockets, and does not replay posts missed while the daemon is offline or reconnecting.

Synoptic also supports bounded historical post pulls through `om event-watch backfill`. Backfill rows are written with `data_mode=backfill`, `observed_at=null`, and `source_event_time` from the upstream source timestamp when available. If Synoptic does not provide that timestamp, OpenMarket uses Synoptic `createdAt` as the best available provider-created clock and records `source_event_time_origin=provider_created_at`; true upstream clocks use `source_event_time_origin=source`. A live event whose timestamp had to be scraped from payload text fields records `derived` in its stored context (the row column stays empty — a scraped guess is never presented as a provider clock).

Backfill does not require pausing the watch — it imports silently and coordinates with live ingest. Explicit backfill NEVER draws from the watch's daily live classifier budgets, in either direction: each run spends only its own per-run LLM-call ceiling (`max_llm_calls`, default 500; 0 means no ceiling), so a big backfill cannot starve live classification and a busy live day cannot gate a backfill. If more remains for another reason the run returns `truncated` with a `resume_cursor` (pass it back as `from` to continue); a shed batch stops the run with the cursor at the earliest shed event (shed events are not stored), resuming shortly for `stop_reason: backpressure` (transient classifier backpressure); after UTC midnight for `stop_reason: budget` (the daily classification bound — a fallback arm an explicit backfill's classifier never charges, so you should not normally see it); and immediately for `stop_reason: run_budget` (this run's own `max_llm_calls` ceiling, status `budget_paused`).

The silent 7-day restart catch-up is a **pull-feed** mechanism (the `attention` / `attention-briefs` news feeds); **Synoptic does not have it.** As the paragraph above states, Synoptic delivery is at-most-once and does **not** replay posts missed while the daemon was offline or reconnecting, so nothing self-heals a Synoptic gap on restart. For any Synoptic offline window, run an immediate bounded `om event-watch backfill` to recover the gap rather than waiting on a catch-up that never arrives. Use `--data-mode backfill --time-basis source_event_time` for follow-on research.

**`status: budget_paused` is a question, never a completion.** When a run's own ceiling binds, the report is `budget_paused` carrying `resume_cursor`, `llm_calls_spent`, and a `budget_paused` object with the classified-through date, an estimate of what remains, and the exact `resume_command`. Relay it to the user as a CHOICE: continue from the cursor (re-run with `from: <resume_cursor>`), raise or drop the ceiling (`max_llm_calls`, 0 = none), or stop here. Always include the resume command. Never summarize a `budget_paused` (or any budget stop) as "done", "complete", or a finished backfill: the window is not covered, and presenting it as covered is exactly the silent-stop failure this contract exists to prevent.

## Budgets and caps

Daily live-classifier budgets, the shed they cause, and `watch_budget_pressure` — caps like `--classifier-max-daily-events` are lowered only on an explicit user ask.

`llm_every_event` watches default to 1000 LIVE classified incoming items per watch per UTC day and 2000 LIVE classifier LLM calls per watch per UTC day. The call budget sits above one call per event on purpose, so the 1000-item budget is normally the one that binds. These budgets gate live ingest only; explicit `om event-watch backfill` spends its own per-run ceiling instead.

**Never lower a daily cap the user did not ask you to lower.** `--classifier-max-daily-events <n>` and `--classifier-max-daily-llm-calls <n>` are for an explicit user request only — not a precaution, not a cost guess, not a tidy round number you prefer. The defaults are sized for real feeds; a watch created under a smaller one silently drops real events for the rest of the UTC day, and the user never sees what they missed. There is no "safe" small cap: a quiet feed never reaches 1000, and a busy feed is exactly the one whose events matter.

When the user DOES ask for a lower cap, confirm it back in one line with the consequence before you create or edit: name the number and state the consequence in the unit that cap actually counts. For `--classifier-max-daily-events <n>`: once the watch classifies that many LIVE items in a UTC day, the rest of that day's events are shed unclassified. For `--classifier-max-daily-llm-calls <n>`: once the watch spends that many LIVE classifier calls in a UTC day, the rest of that day's events are shed unclassified — and a call covers a whole coalesced batch (up to 25 items), so `n` calls cover `n` items on a feed that trickles and up to 25× that on a bursty one. Never quote the call cap as an item count. Either way the shed is not queued and not delivered late — it is a hole in the journal that only `om event-watch backfill` can refill. Say where the shed shows up — `om event-watch show <id>` prints a `Shed:` line counting dropped events and a `degraded` status, and in `om chat` the footer under your create/edit call names the caps in force. Raising a cap needs no such warning.

The caps are also disclosed as they fill, so answer "why did this feed go quiet?" from those surfaces rather than guessing. `om event-watch show <id>` always prints the resolved budgets and a `Used today:` line; at 80%+ of either budget the watch appears in `watching_overview`'s `attention_needed` as `watch_budget_pressure`, in the `om news` pane as its feed's problem row, in `om doctor`, and as a badge in the `om chat` header, and `om event-watch list` names it under the table. Every one of those that has room for a command ends in the raise command, which is the only fix; the `om chat` header badge is a one-line badge and names the watch and the percentage alone, so quote the raise command yourself when you relay it. A shed is never re-delivered, so raising the cap protects the REST of the day and `om event-watch backfill` refills the hole already made.

## Notify

Route watch fires to channels — `--notify` / `--notify-channel` homing, the card-only fallback, and who writes the alert (`--notify-style agent`) and where it arrives.

Use `--notify` only when the user explicitly wants immediate human nudges. A notify-enabled watch routes its sends like price alerts, **materialized** and literal (`notify.channels[]` stores channel ids): `--notify-channel <name>` sets the destinations; a notify-enabled watch created without one homes to the channel this conversation posts to, else the configured default (or the lone channel), and with several channels and no default it is card-only. An **empty** destination set is card-only — the fire shows as an inline `om chat` card only, no push. There is no read-time fan-out. Each fire must reach all of its resolved channels (partial failures retry per channel on restart recovery).

The om agent writes the alert by default (`--notify-style agent`): its message posts in its paired chat and the same text is delivered to the watch's channels, so every sink carries one message. Whenever you create or edit a notify-enabled watch, TELL the user who writes their alerts and where they arrive — when the agent is not paired, channels receive the plain alert instead until a chat is paired (`/setup` in a terminal `om chat` runs the guided connect inline and is the nearest door from chat; `om setup telegram` is the terminal verb); a daemon serving that home follows the new pairing on its own and brings the bot online within about half a minute, so never prescribe a restart. Creating or editing an agent watch on such a host prints a WARN naming the step that host is missing — the guided connect where no bot is configured, the bot's first DM where one is already online — and the style goes live once the agent is paired. Pass `--notify-style alert` only when the user wants the plain alert with no LLM.

With ZERO channels configured, notify stays ENABLED but delivery is inline cards in an open `om chat` session only (plus the paired chat when the agent is paired) until a channel exists. Send failures to a configured channel remain pending for bounded startup recovery; OpenMarket does not continuously retry notification failures inside the same daemon run.

## Read journals

Read what a watch captured — `event_journal_get` for the Markdown projections, `event_journal_search` across journals, `event_watch_events` for filtered SQLite rows with paging.

Use `om event-journal get <slug>` for the current `overview.md` projection. Use `om event-journal get <slug> --file events.md` for the retained accepted-event Markdown projection; it is tail-bounded on read and older entries may be trimmed from Markdown after the retention cap. The journal files are `metadata.md`, `events.md`, and `overview.md`, plus `background.md` on the journals that carry one; do not look for `timeline.md`, `sources.md`, `summary.md`, `summary.previous.md`, or `summary.json`.

An `overview.md` that no synthesis has ever written comes back with an `overview_status` block instead of standing on its own. Read the cause out rather than reading the placeholder out as an overview: `no_events` and `waiting_for_threshold` mean the watch is working and has not accumulated enough accepted events yet, `classifier_failing` means events arrived and failed classification (the block counts them in `error_events` and quotes `runtime_error`), `overview_disabled` and `synthesis_not_run` mean a pass has to be asked for, and `watch_removed` means nothing will ever write the file again. The block's `fix` is the command that writes it now, and it is null exactly in the `watch_removed` case.

Use `om event-journal search <query> --format json` when the user asks whether the retained Markdown journals mention a subject and you do not know the slug.

Use `om event-watch events <id-or-slug> --format json` when the user needs structured filtering by outcome, observed time, source, confidence, journal-commit state, or notification state, or when they need batch metadata for grouping burst decisions. This reads SQLite event rows, not Markdown, and is the preferred surface for event queries that need filters. Raw source text is omitted by default; pass `--include-raw-text` only when the user specifically needs the original source body.

A page is bounded: 50 rows by default, 500 at most. Report counts from `total_matching` on the result, never from how many rows came back — `truncated` says whether more match beyond the page, and `next_cursor` goes back as `before` to read the next one. A cursor is part of the query the count is taken through, so on a page read with `before`, `total_matching` is what remains past that cursor: answer "how many are there?" from a first page or from `total_stored`, the unfiltered population of the same scope, never from a resumed page's total. A cursor also belongs to the view that issued it — merged (no id) and single-watch pages sort on different clocks, and the wrong view's cursor is refused. Those totals count rows the store HOLDS: non-accepted outcomes keep only a rolling retention window per watch, so a total under `--outcome error` is a floor on what happened.

## Repair error rows

Rows with outcome `error` kept their raw text — `event_watch_reclassify` re-judges them (paid, bounded by `--limit`) once the broken credential or provider is fixed.

An event row with outcome `error` is an event the watch RECEIVED and stored but never got a verdict on: the classifier call failed — a lapsed or missing LLM credential, a provider outage, a malformed batch reply — and the row kept its raw text and full source context. Nothing about the event is missing except the judgement, so the repair reads from disk, never from the vendor.

`om event-watch reclassify <id-or-slug>` (action `event_watch_reclassify`) re-runs the classifier over those rows. Each row keeps its id, arrival time, source clock and data mode, so a backfilled row stays backfilled and the timeline does not jump it to the present; a row that now classifies as accepted joins the journal and the accepted history. It SPENDS — one classifier LLM call per batch of 25, charged against this watch's own daily classifier budgets — so it is bounded per call (`--limit`, default 50, max 200), reports how many rows remain for the next call, and reports a bound budget as a shed cause rather than spending silently. `--since <time>` bounds the pass to the window a failure covered.

Fix the cause before spending on the repair: a second pass against the same broken credential writes the same error rows again. Rows that retained no raw text cannot be re-judged at all and are reported separately — those need `om event-watch backfill` over their window.

An error row the watch has already classified past reads as `error (stale)` in `om event-watch events` and as `watch_error_stale` in `watching_overview`: the classifier recovered on its own and the stored failure is history, not a live break. Repairing those rows still needs an explicit reclassify — nothing re-judges them automatically.

## Overviews

Overview snapshots and `overview.md` — `event_watch_synthesize` refreshes on demand (paid per pass), `--page-size` sets watermark granularity, `--rebuild` re-authors a backbone.

OpenMarket refreshes the SQLite overview snapshot automatically on conservative event-count thresholds and after major updates. `overview.md` is the readable projection from that snapshot. Use `om event-watch synthesize <id-or-slug>` when the user asks for an immediate refresh or when automatic overview synthesis failed — it WRITES (a new overview snapshot plus a rewritten `overview.md`), each pass is a paid LLM call, and it takes the watch's exact id, not a fragment.

Synthesis drains pending accepted events in pages (default 100 per pass), and each development it authors records the newest journal row its pass read — the watermark backtest context replay uses to prove an entry knew nothing of later events. `--page-size <n>` (1-100) sets that granularity: after a bulk backfill, a single default-page pass stamps every development with the whole span's last row, so a context-replay backtest must exclude the entire backbone as future-aware; synthesizing at `--page-size 5` instead authors the timeline in 5-event steps that replay progressively. Combine with `--rebuild` to re-author an EXISTING backbone at finer granularity (also the upgrade for legacy backbones that predate watermarks and count as unproven authorship in backtests). Each pass is a paid LLM call — the projected pass count is disclosed on stderr before synthesis runs, and a rebuild that cannot finish inside the pass cap is refused before spending anything. A rebuild keeps lived overview snapshots (they are the record of what live consumers acted on) and writes its new head on top; add `--with-snapshots` to also mint one RECONSTRUCTED overview snapshot per non-final replayed page (brief included, one extra paid call per page, count disclosed) — labeled rows in a separate lineage that serve advanced-mode backtest replay over the span and never serve live consumers.

## Edit a watch

Change a watch in place with `event_watch_edit` — goal, filters, classifier, budgets, notify homing, `--market` tags; the stream binding is immutable, so rebinding is a new watch.

Use `om event-watch edit <id-or-slug>` to change an existing watch in place (goal, include/exclude filters, extra classifier guidance, classifier mode/provider/model/budgets, notify, overview, label, `--market` tags with `--clear-markets` to remove) instead of removing and recreating it. Omitted flags are untouched, `--clear-*` flags reset an override to its default, and `--include`/`--exclude` replace the whole list. The stream binding is immutable — rebind by creating a new watch. Enabling notify on a watch that was never routed homes it the same way create does — to the channel this conversation posts to, else the configured default, else card-only if no channel is set — and the edit result names where it landed, so relay that to the user. A watch whose channels you deliberately cleared (`--clear-notify-channel`) stays card-only; enabling notify does not silently re-home it. Passing `--notify-channel <name>` overrides the homing, and a NAMED but non-existent `--notify-channel` is still rejected (a typo, not a default). To route a watch onto or off a channel from the channel's side, `om channel <name> --add <slug>` / `--remove <slug>`.

Use `--market <EXCHANGE:SYMBOL>` (repeatable) to tag the watch with related markets. Tags are metadata for price-alert catalyst pairing: when a price alert fires on a tagged market, the fire notification appends this watch's freshest accepted event as a "Possible catalyst" line. They never change what the watch matches.

`--brief-alert-fires` / `--no-brief-alert-fires` is the per-watch switch for relayed alert fires (rows of kind `om_alert`: the author's price-alert fires on a followed or installed alert stream). Off is the default and needs no flag: those rows stay out of the daily brief, the news lookups and the possible-catalyst lines, because a price move is not news. On admits them, labeled with the stream address, and `event_watch_show` states the switch either way (`brief_alert_fires`). Accepted on any watch; inert on one that never holds such rows.

## Lifecycle

Pause, resume, remove — remove preserves the journal, destroys stored events, backbone, snapshots, shares, and confirms first; alert shadows refuse (`event_watch_alert_managed`).

Every event-watch lifecycle verb below takes `id_or_slug`. Several watches by EXACT id are ONE call: `event_watch_remove` / `event_watch_pause` / `event_watch_resume` take `ids` beside `id_or_slug` and `group` (`om event-watch remove <id> <id>`, `om event-watch pause <id> <id>`); one card lists every member (state, group, `shadow` and `consumers` flags), ids that do not exist are reported as skipped and never dispatched, alert shadows come back as `skipped_unsafe` rows, and a batch resume refuses the whole call over a member with consumers unless the card carried it. Never loop single-id calls for a set: that raises one card per watch.

- `om event-watch pause <id-or-slug>` disables a watch and keeps its journal.
- `om event-watch resume <id-or-slug>` re-enables a watch.
- `om event-watch remove <id-or-slug>` removes the spec and preserves its journal. It also destroys the watch's stored events, its backbone, every snapshot it holds (the lived synthesis passes and any materialized backtest lineage), its chart binding and any room shares bound to it, so it confirms first and prints what it destroyed; `--yes` is the scripted form. `om event-watch rotate-token` confirms the same way, because rotating revokes the token every live producer is pushing with. Both raise an approval card in chat.
- Deleting, removing, or unfollowing a news feed retires the watch it auto-attached and keeps that watch's journal; the result names it as `removedWatch`. A hand-built watch on the same stream is never auto-retired — it comes back as `keptWatch`, and `om event-watch remove <id>` is its explicit cleanup.
- **Alert shadow watches are alert-managed.** Every price alert mirrors its fires into the journal through a shadow watch, which is what makes alert fires chartable via `chart_pins` (news.md §"Plotting events on charts"). Shadows take no generic lifecycle and no generic edit: `event_watch_pause` / `event_watch_resume` / `event_watch_remove` / `event_watch_edit` on one refuses with `event_watch_alert_managed`, naming the alert verb to use instead (an accepted edit would evaporate anyway — the mirror rebuilds the shadow spec from the alert). Drive the ALERT (`om alert pause` / `resume` / `remove`) and the shadow follows; never route around the refusal.

When one request spawns several members, put them under one `group` at creation and name the group in the orientation reply: the set answers to that name from then on. Route later work through the group handle: `event_watch_show {group}` renders the composite's card (members worst state first, with the schedules bound to them), `event_watch_list {group}` its roster, and pause/resume/remove take the same `group` selector with a per-member report, while alert legs stay `om alert` business, reported as skips, never flipped. Membership itself is edited per leg (`event_watch_edit {id_or_slug, group}`; null leaves), so joining or leaving is never a reason to delete and recreate.

## Streams: share, follow, fork, stats

A watch (or alert) shared under a registry address `@scope/name` is a stream: rule plus signed history as a one-member package, plus a relay lane on a live share.

- `stream_share` (`om share <ref>`): dry-run by default (zero network); `live: true` mints the
  lane, stamps `stream: {address, role: "own"}` and publishes. Preview first, always: answer a
  share ask with a `dry_run: true` call and relay the preview (address, version, history count,
  and the space-scope line) before any live call; the live share is a second call the user asked
  for after seeing the preview. Never make the first call a live one. Disclose on every live share:
  **lanes are space-scoped** — readable only by members of the author's space. Scope comes from
  `scope` or the `registry_scope` setting (`missing_scope` otherwise).
- `stream_follow` (`om follow <address>`): creates a PAUSED accept_all watch fed by the author's
  signed relay postcards (0 LLM calls, execution never); resume it to start folding. `stream_unfollow`
  removes the follow, journal preserved; several follows = ONE call with `ids` (`om unfollow <ref> <ref>`),
  one card naming what each unfollow retires. News-vendor follows stay on `news_follow`.
  `brief_alert_fires` (`om follow --brief-alert-fires`, default off) admits the author's alert fires
  into the daily brief and catalyst notes, labeled with the address; the consent card states it
  when on, and `event_watch_edit` flips it later (§"Edit a watch").
- Knock doors: a topic-carrier live share with `--door knock` gates followers — each one asks and
  the publisher decides. `stream_knocks` (`om knocks [ref]`) lists who is knocking (and where every
  knock stands) across every owned knock-door topic; `stream_knock_resolve`
  (`om knocks approve|deny|revoke <ref> <user>`) is the ONE decision verb: approve admits (and works
  as preapproval for an account that never knocked, or re-admission of a denied/revoked one), deny
  refuses a pending knock, revoke cuts off an approved follower. Idempotent: re-deciding what
  already holds is an unchanged OK, and a stale decision reports the knock's CURRENT status instead
  of failing. Pending knocks also surface as needs-you notices on the daemon's drain cadence.
- `stream_follow_repair` (agent lane): reconcile a follow whose durable binding row and local
  topic-follows record disagree on the subscription id — the `stream_unfollow_identity_conflict`
  refusal names it. An exact relay-store read under the owning account decides which id is
  actually registered and rewrites the losing record; local records only, nothing subscribed or
  released; refuses typed when the store cannot answer, holds both ids, or holds neither.
- `om install @scope/pack[#member]` lands members PAUSED with silent history import;
  `om fork <source>` copies one member into an owned watch with `lineage.forked_from` only.
- `om event-watch stats <ref> [--window <days>] [--format json]` is the receipts view. Label the
  numbers exactly: `relay_age` is publisher-claimed, uptime is heartbeat-sampled, follower counts
  are unknown, lanes are space-scoped. Author-side numbers are the author's own activity;
  follower-side receipts are relay-stamped. Never grade them as verified reality.
- `event_watch_show` prints the lane block (address, room, pending, BLOCKED state); a postcard
  failing 8 deliveries blocks its lane instead of skipping a sequence number, and
  `event_watch_lane_retry` clears the block.
- `om event-watch export <ref>` writes canonical stream-event JSONL (door-only keys and foreign
  relay rows never leave); `om event push <watch> --file <jsonl|csv>` imports files as silent
  history with idempotent dedupe. The two round-trip.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `event_journal_get`
  - `file` — default "overview.md"
- `event_journal_search`
  - `window_hours` — Omit for all-time (the default).
  - `limit` — Max story lines returned (default 20).
- `event_push`
  - `event.occurred_at` — ISO 8601 instant of the event's own clock; absent means the ingest instant.
  - `event.id` — Absent, a content hash dedupes honest retries anyway.
- `event_watch_backfill`
  - `adapter` — Source adapter id; defaults to stream_ref.adapter.
  - `latency` — Defaults to standard.
  - `max_llm_calls` — Per-run classifier LLM-call ceiling for THIS backfill run (default 500; 0 means no ceiling).
- `event_watch_backfill` · `event_watch_create`
  - `classifier.mode` — default "llm_every_event" — llm_every_event (default): the local classifier scores each item against the goal, keeps matches, drops the rest, under the daily budgets.
  - `classifier.provider` — LLM provider id for classification; falls back to the configured default when omitted.
  - `classifier.max_daily_classified_events` — llm_every_event only: max LIVE items classified per watch per UTC day (default 1000), a budget guard against a noisy feed.
  - `classifier.max_daily_llm_calls` — llm_every_event only: max LIVE classifier LLM calls per watch per UTC day (default 2000) — one call classifies a whole batch of events, so this is a DIFFERENT budget than max_daily_classified_events, not a per-event count.
- `event_watch_create`
  - `group` — Absent leaves the new watch standing alone.
  - `ingest.daily_cap` — Inbound watches only: max accepted pushed events per UTC day (default 2000).
- `event_watch_edit`
  - `group` — Absent keeps the current group; null leaves it, and the legs that stay keep theirs.
  - `classifier.mode` — llm_every_event (default): the local classifier scores each item against the goal, keeps matches, drops the rest, under the daily budgets.
  - `classifier.provider` — LLM provider id for classification; null clears it back to the configured default.
  - `classifier.max_daily_classified_events` — llm_every_event only: max LIVE items classified per watch per UTC day (default 1000).
  - `classifier.max_daily_llm_calls` — llm_every_event only: max LIVE classifier LLM calls per watch per UTC day (default 2000).
  - `brief_alert_fires` — false (the default posture) keeps them out.
- `event_watch_events`
  - `id_or_slug` — OMIT IT for the MERGED view: every watch's rows in one page, newest first on the SOURCE clock (when the story happened), which is what answers 'what fired recently?' across feeds — each row carries its own watch_id.
  - `include_raw_text` — Defaults to false.
  - `limit` — Defaults to 50, capped at 500.
- `event_watch_export`
  - `limit` — Defaults to 1000, capped at 5000 (one page is always a valid history file on its own); reach older rows with `before`.
- `event_watch_reclassify`
  - `limit` — Maximum error rows to re-judge in this call (default 50, max 200).
- `event_watch_remove`
  - `members` — The approval surfaces write this after the human saw the roster; omit it to act on the group's membership at dispatch time.
- `event_watch_stats`
  - `window_days` — Stats window in days (default 7).
- `event_watch_synthesize`
  - `rebuild` — Rebuild the backbone from scratch by clearing it and replaying every accepted event chronologically (instead of the default incremental refresh).
  - `page_size` — Events per synthesis pass (1-100; default 100).
- `stream_follow`
  - `slug` — Create the follow watch under this slug (default: <scope>-<name>[-<member>]-follow, the address's own identity).
  - `brief_alert_fires` — Default false: a price move is not news unless the user chose it.
- `stream_knocks`
  - `ref` — Omit to list every owned knock-door topic.
  - `status` — Omit for all (pending and decided).
- `stream_share`
  - `scope` — Defaults to the `registry_scope` setting; refused with missing_scope when neither is set.
  - `name` — Defaults to the watch slug (or a kebab form of the alert label).
  - `version` — Defaults to 0.1.0, or the last shared version with the patch bumped.
  - `history` — Ship the accepted past as history/<member>.jsonl (default true).
  - `door` — Default public.
  - `carrier` — Default: the stream_lane.default_carrier setting, else room_post.
- `watch_compose`
  - `group` — Composite group label for every committed member; defaults to the subject names.
  - `notify` — Whether the created watches ping the channel per live event (default true).

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om event` — (bespoke; see narrative above)
- `om event push` (action: `event_push`) — Push one event into an inbound event watch.

- `om event-journal` — (bespoke; see narrative above)
- `om event-journal get` (action: `event_journal_get`) — Return one local event journal Markdown file by slug.
- `om event-journal list` (action: `event_journal_list`) — List local event journals by slug, including the backing watch id/label when a watch spec still exists.
- `om event-journal search` (action: `event_journal_search`) — Free-text search over the user's WHOLE news/event fire history: accepted stories across all watches and followed feeds (FTS story lines grouped by watch, groups ordered by their top-ranked story, majors first then newest within each; all-time unless `window_hours` narrows it), plus substring matches from the journal Markdown itself (metadata/events/overview), which is what keeps a removed watch's preserved journal and raw-text-only entries reachable.

- `om event-watch` — (bespoke; see narrative above)
- `om event-watch amend` (action: `event_watch_amend`) — Correct an event this watch already streamed over its TOPIC lane.
- `om event-watch backfill` (action: `event_watch_backfill`) — Run a historical backfill for an existing (live or paused) or newly-created event watch.
- `om event-watch create` (action: `event_watch_create`) — Create a daemon-owned event watch from a natural-language goal and ONE structured stream reference the user named or a probe verified.
- `om event-watch edit` (action: `event_watch_edit`) — Update a watch's goal, filters, extra guidance, classifier, notify, overview, related-market tags, or the brief_alert_fires switch.
- `om event-watch events` (action: `event_watch_events`) — Query structured SQLite event rows by outcome, time, source, confidence, and notification state.
- `om event-watch export` (action: `event_watch_export`) — Export one watch's accepted event rows as canonical stream-event lines (JSONL), the shape a shared pack ships as history and `om event push --file` reads back.
- `om event-watch list` (action: `event_watch_list`) — List configured event watches with their daemon runtime status, optionally only one composite's members (`group: <label>`, exact trimmed case-insensitive match).
- `om event-watch pause` (action: `event_watch_pause`) — Disable one event watch by id or slug, several by exact id in ONE call (`ids`), or every watch in a composite (`group: <label>`); consuming strategies are NOT auto-paused, and journals are preserved.
- `om event-watch reclassify` (action: `event_watch_reclassify`) — Re-run the classifier over event rows this watch already stored with outcome `error` (a failed classification, e.g. a missing or expired LLM credential), using each row's retained raw text and source context.
- `om event-watch relay-door` (action: `event_watch_relay_door`) — Mint or rotate the relay mailbox for a watch that is live-shared over a relay topic, and print the drop URL exactly once.
- `om event-watch remove` (action: `event_watch_remove`) — Remove one event watch by id or slug, several by exact id in ONE call (`ids`), or a whole composite (`group: <label>`); consuming strategies auto-pause and each member's journal is preserved.
- `om event-watch resume` (action: `event_watch_resume`) — Re-enable one paused event watch by id or slug, several by exact id in ONE call (`ids`), or a whole composite (`group: <label>`); event flow returns and consuming strategies need no re-arm.
- `om event-watch rotate-token` (action: `event_watch_rotate_token`) — Mint a fresh ingest token for an inbound event watch and invalidate the old one immediately (rotation IS revocation: only the token's sha256 is stored, so the previous token stops authorizing the instant the new hash lands).
- `om event-watch show` (action: `event_watch_show`) — Show one event watch (spec, runtime status) by id or slug, or a composite's whole card (`group: <label>`), plus the signals and strategies that depend on it (the blast radius of a pause or remove).
- `om event-watch stats` (action: `event_watch_stats`) — Stream receipts for one event watch, computed on read from the local ledgers: window activity by arrival lane (live/relay/catchup/imported/backfill), and, for a followed stream, relay-stamp receipts (postcards by transport, relay_age labeled publisher-claimed, future-timestamp flags, heartbeat-sampled uptime) plus the author-side lane block for a live-shared one.
- `om event-watch synthesize` (action: `event_watch_synthesize`) — Refresh one event watch's overview.md from its accepted event history.

- `om follow` (action: `stream_follow`) — Follow a live-shared stream: create a PAUSED event watch fed by the author's fires over their relay lane.

- `om fork` — (bespoke; see narrative above)

- `om knocks` (action: `stream_knocks`) — Who is knocking on your knock-door topics, and where every knock stands (requested, approved, denied, revoked).
- `om knocks approve` (action: `stream_knock_resolve`) — Let a knocking account in (preapproval and re-admission included).
- `om knocks deny` (action: `stream_knock_resolve`) — Refuse a pending knock.
- `om knocks revoke` (action: `stream_knock_resolve`) — Cut off an approved follower.

- `om share` (action: `stream_share`) — Share an event watch, alert or schedule as a package under its stream address: publish it over its ref with its accepted history (a schedule ships future runs only, never earlier ones), and with live=true mint a relay lane so followers receive future postcards.

- `om unfollow` (action: `stream_unfollow`) — Stop following a stream: remove the follow watch (its stored events go with it; the journal is preserved, exactly the event_watch_remove contract) and drop the durable lane cursor so a later re-follow starts clean.

- `om watch` (action: `watch_compose`) — "Watch <subject> for me" as ONE verb: researches where each subject (a person, organization, product, or public issue) publishes and is covered, verifies sources with deterministic probes, creates the grouped event-watch set with notifications enabled, and opens with a dated, sourced read of where the subject stands right now.

<!-- AUTO: END COMMAND REFERENCE -->
