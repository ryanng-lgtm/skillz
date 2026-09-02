---
name: openmarket-news
description: Author, preview, follow, fork and manage Attention Fast alerts, follow curated Attention Topics, and add Synoptic streams — the three text-event feed lanes behind `om news` — and keep their auto-attached event watches honest. Use when the user wants to be alerted on news/social/text events, wants an ongoing topic feed ("keep me posted on X"), asks what news feeds or alerts they have, wants to backtest an alert idea before arming it, or complains about noisy or duplicate news pings.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om news

`om news` is the control plane for text-event feeds: news, social posts, government releases, anything that arrives as text rather than a number on a chart. Three vendors sit behind one capability-gated command set — the lanes live in §"Providers and ids".

Every acquired feed pairs with a local **event-watch** (the daemon-owned monitor that journals fires and sends notifications). This file covers the news side and the doctrine for keeping the pair healthy; watch mechanics live in `event-watches.md`.

### Guardrails

- Never refuse a news request on plan grounds — attempt it; only a typed backend error is a wall, and the wall is a menu (§"Wall phrasing").
- Buying, upgrading or cancelling is never yours — name the exact terminal command (`om news subscribe`, `om news add <id>`) and never state a price (§"Wall phrasing").
- `active_quota_exhausted` is cleared by freeing a slot the user picks — never answered with a purchase (§"Wall phrasing").
- Six `news_*` calls raise a card in every approval mode — `news_delete`, `news_remove`, `news_unfollow`, `news_resume`, `news_share`, `news_publish` unless `public: false` — as do five shapes: `news_edit` carrying `alertWhen`, `news_replay` starting or cancelling a sweep, `news_brief` scheduling or sending off-box, `chart_pins` onto a chart the user keeps, and `backtest_news` with `materialize: true` (§"Publish, follow, fork").
- Publishing is a disclosure — the alert's condition becomes world-readable; confirm intent in your own words before `news_publish`, ahead of the card it raises (§"Publish, follow, fork").
- Get an explicit yes before plotting onto a chart the user keeps: a named workspace, or `here:` when the active workspace is the user's, raises an approval card. The agent's own minted charts and the default day chart dispatch without one; if the minted ledger can't be read, the card appears (§"Plotting events on charts").
- "Stop pinging me about X" is a mute (`news_mute`), never a delete — the feed and its journal keep running (§"Noise and duplicates").
- "Kill the feed" is actual removal, which cards — confirm it is not a mute in disguise before destroying anything (§"Noise and duplicates").
- Never share a feed into a room without an explicit user instruction naming the room — sharing posts as the user (§"Sharing a feed into a room").
- Buying a Stream is never unattended — never offer `--yes` as a way to script a purchase (§"Paid Synoptic Streams").
- State the one-key-at-a-time consequence when offering the Synoptic connect: connecting here stops another machine's stream reads until it reconnects there (§"Account and linking gates").

**Streams with registry addresses are not news feeds:** `@scope/name` event streams are followed with `stream_follow` (`om follow <address>`), never `news_follow --provider om` (that refuses with this hint). Their relayed alert-fire rows (`source_kind: "om_alert"`) stay out of the brief, the news lookups and the catalyst lines by default (a price move is not news) unless the user switched that watch's `brief_alert_fires` on (`om follow --brief-alert-fires`, `om event-watch edit --brief-alert-fires`), which admits them labeled with the stream address.

### Routing

Name a moment and the user wants a Fast alert ("tell me WHEN X happens" — latency matters), which is authored; name a subject and they want a Topic ("keep me posted ON X" — coverage matters), which is followed from the curated catalog and never authored, AND the composed first-party set beside it (both, under one group, for now); want somebody else's ready-made feed and they want a stream. Name a THEME ("watch the US-Iran escalation") and it is a composite watch rather than any one feed: alerts.md §"Grouping legs under one named watch" carries the recipe. Name a SUBJECT to watch ("watch <person/org/product> for me") and `watch_compose` (event-watches.md) researches, probes, and creates the grouped set in one call; a published Topic already covering the subject is followed as well, into the composed group. Name a place the user owns or names ("watch my IBKR emails", "watch our CI", "watch this URL") and the request leaves the vendor lanes entirely: the information lives at their place, not in the world's coverage, so read `connect-source.md` and build the inbound pair there instead. Topics are never called alerts/triggers/fires in user-facing copy, never described with urgency language, and never advertised as screened or verified.

- A feed nothing consumes is repaired with `news_attach`, never `event_watch_create` (§"After any acquisition, verify the pair").
- Replaying a Fast alert's OWN history is `news_replay` (§"Replay a Fast alert's history"); backfill and budget questions on a feed's WATCH (`budget_paused`, caps, shed) live in `event-watches.md`, as do event paging and journal reads — read it (`skill_read("event-watches")`) before touching the watch, and pull only the relevant journal.
- "Why so many pings" is diagnosed before any remedy (§"Noise and duplicates").
- A one-off news answer earns at most one conversion offer (§"One-off answers convert once").
- Backtest a feed's fires before proposing any signal or strategy on them (§"Backtest before arming anything").
- "What am I watching?" is one `watching_overview` call, every warning surfaced (§"What am I watching").

## X coverage and the Grok hint

Live X search exists only on an xAI credential (a SuperGrok / X Premium subscription or an xAI API key); every other account covers X indirectly through news echoes and feeds.

- When a task plainly targets X (an @handle, x.com links, "tweets") and no xAI credential is connected, a created watch may carry a one-time `x_search_hint`: relay it verbatim, then never raise it again.
- Never block or delay a task on the missing credential; what exists still runs.

## Providers and ids

The three vendor lanes (Fast `attention` · Topics `attention-briefs` · Streams `synoptic`), vendor-scoped ids, preview vs delivered history, `unsupported_operation` as routing.

- **Fast** (vendor Attention, provider `attention`, the default): the user names the moment that matters, in plain English, and gets pinged the second a public post matches it. Authoring vendor: create / edit / pause / resume / delete / publish / follow / fork.
- **Topics** (vendor Attention, provider `attention-briefs`, same account link — nothing extra to set up): a SUBJECT ("AI model releases") whose story arrives as it develops, a few story cards a day. Not alerts: they do not fire, and nothing about them is urgent. CURATED: Attention publishes the catalog, so the way in is `news_catalog` then `news_follow` — free, unlimited, and no slot. There is no create and no fork here; either verb answers `briefs_topic_authoring_restricted`, which means "browse and follow", not "try again". A Topic the user already owns keeps edit / pause / resume / unpublish (`news_publish` with `public: false`) / delete / unfollow.
- **Streams** (vendor Synoptic, provider `synoptic`): ready-made event feeds from Synoptic's marketplace, published by Synoptic and by independent providers (government releases, tariff feeds, crypto trackers). Some are free, some are paid on Synoptic, and some are delayed — never promise a user that a stream is live or free. A stream carries everything its publisher posts, so an added stream is always filtered by its event-watch `goal`. Catalog vendor: browse / add / remove / packages.

**Previewing a feed the user ALREADY has:** pass its id (`om news preview <id> --provider <vendor>`) — do NOT re-type a condition or interest they already own. A Fast alert answers with what it has **actually fired**, taking the best evidence it has and saying in `verb` which it used: fires inside the window; else the older past fires it does have ("6 past fires … — nothing in the last 24h"); else, only while the server is still backfilling its past fires, a labelled estimate; else "0 past fires yet". Report the `verb` as given — a brand-new alert answered from its backfilled history has NOT fired in the last 24h, and an estimate is not history. A Topic answers with a SIMULATED sample of what its interest would have carried; a Synoptic stream with recent posts. Preview and history are different claims and are never reported as one: a preview says what an interest or a condition WOULD have caught, `news_show` returns the cards and fires a feed DELIVERED. An id beats a typed condition: naming a feed asks about that feed. Ids are vendor-scoped, so pass the matching `--provider` (a Topic id sent to Attention is not found).

**Reading ONE feed in depth:** `news_show` (`om news show <feed>`) resolves the catalog first and then the user's own feeds, so an unpublished alert they authored, or a followed feed addressed by its publisher id, answers here too. It returns the public `entry` (null when only their own row matched — not an error), their `owned` row when they hold one, `held` (do they already have it: for a `paid` Stream that is the whole question, and `held: true` means `news_add` works with no purchase involved), `entitled` (may they read its fired rows), and `fires` — up to 100 rows of what it has ACTUALLY fired, newest first, each with `at` and, when the vendor gave one, `sourceUrl`. `fires` defaults to 5; pass `0` to skip the history fetch when only the entry matters, and raise it when the user asks what a feed has been catching. `fires: []` (nothing yet) and `fires: null` (no history was read — gated, none available, or the fetch failed) are different answers: only `[]` is "quiet".

**A published Attention feed's history belongs to its publisher, and anyone may read it.** Pass a catalog id — a Topic or a Fast alert the user does not hold — and `news_show` answers with the PUBLISHER's delivered rows, which is what makes "should I follow this?" answerable from evidence instead of from a simulation. It is also the same history after the follow as before it: a follow subscribes to a feed, it does not fork one, so a fresh follower's page shows the whole record including everything from before they took it. Never offer a preview as a substitute for that history, and never describe a preview sample as cards the Topic delivered. Synoptic is the other way round — a Stream's posts are readable only once it is added (`entitled: false`, `fires: null`), which is a gate, not a quiet feed.

Asking a vendor for a verb it does not support returns a typed `unsupported_operation` error. Treat that as routing information, not failure: switch vendor or verb.

## One-off answers convert once

A one-off news read earns at most ONE entitlement-aware offer (from `news_billing`); a covered subject is cited instead, and a decline is remembered, never re-offered.

"What's happening with X?" answered from news or web data is a one-off read; a watch is the standing version of the same question. The conversion is offered, never pushed. The offer is always a CONVERSION (arm a watch, follow a feed, a paid backfill): never offer a read you can run yourself, with ONE exception: the live fetch (`web_research`) costs cents and walls the conversation, so when the journal answered the ask freshly it is named as available in one closing line rather than run; journal search, journal get, and the odds/market read run in the same turn, unasked, per the injected fence's depth doctrine:

- **Journal first, then the live world, in that order.** A named subject (an @handle, a person, a ticker) whose journal search comes back empty, or whose newest hit is older than the window the user named, gets `web_research` in the same turn, unasked: an empty journal is not "nothing happened", it is "no watch covers this". When the journal HAS fresh hits and the ask is not plainly about the live world, show what the journal holds and offer the live fetch in one line; never run research silently over a fresh journal answer (it costs cents and walls the conversation). Words that name the live world (search, look up, live, latest, right now, a pasted URL) run research first, whatever the journal holds.
- **No covering watch: answer, then append ONE entitlement-aware offer line.** One line at the end of the answer, at most one offer per subject per session. Entitlement-aware means the line names a lane this account can take today: read it from `news_billing` (`can_author` for an authored Fast alert, `can_follow` for another publisher's, and the free follow of a curated feed or a Topic otherwise) rather than guessing, and never state a price. The offer is part of the answer, never a precondition for it.
- **A covered subject is cited, never offered.** When an existing watch or feed already covers the subject, point at it and what it caught ("your Iran watch caught this 2h ago", read from `event_watch_events`) instead of offering a duplicate. A second watch on a covered subject is next week's duplicate-pings complaint.
- **A decline is remembered.** When the user declines the offer (or waves it off), save it with `memory_save` keyed to the subject (search first with `memory_search`), and never re-offer that subject unprompted, this session or later ones. A remembered decline is lifted only by the user's own ask.
- **Repetition earns receipts, once.** The same subject asked again within a week is the one escalation: offer once more WITH receipts ("third time this week; a watch would have caught 6 events"), taking the count from a real read (`om news preview` for a would-have-fired count, or the covering journal), never invented. Declined again, the subject returns to remembered silence.

## Classifier defaults

Auto-attached watches default to `llm_every_event` under daily live budgets; `accept_all` is an explicit opt-out; a backfill spends its own ceiling, `budget_paused` is a choice.

Every auto-attached watch — Attention or Synoptic — defaults to `llm_every_event`: the local classifier checks each incoming item against the watch's goal, keeps what matches, and drops the rest, under per-watch daily LIVE budgets (default 1000 classified items, 2000 LLM calls per UTC day — leave both alone unless the user asks; event-watches.md §"Budgets and caps" carries the confirm-back rule on lowering one). Explicit `om event-watch backfill` never spends these live budgets; it runs on its own per-run LLM-call ceiling and, when that ceiling binds, returns `status: budget_paused`, a choice to relay (continue from the resume command, raise the ceiling, or stop), never a completed backfill (event-watches.md §"Backfill"). Goal quality is the product: a vague goal wastes budget on noise, a sharp one keeps the journal clean.

`accept_all` — journal and notify every delivered item with no local classifier — is an explicit opt-out, not a default. Only switch a watch to it on the user's ask (`om event-watch edit <id> --classifier-mode accept_all`, or `om config set news.auto_watch.classifier.<vendor> accept_all` for future auto-watches).

## Account and linking gates

Sign-in and vendor links — `guest_not_allowed` fixes with `om login`; Attention links lazily, Synoptic needs `om news setup synoptic` (one key at a time), fires need the daemon up.

- All news verbs need a signed-in OpenMarket account. A guest session gets a typed `guest_not_allowed` error; the fix is `om login`.
- **Attention** needs no key and links lazily on the first Attention verb. `om news setup attention` links up front. If the account has no verified email (Twitter-only login), the first authoring action requires a one-time email verification: drive it with the `account_set_email` / `account_verify_email` actions, relaying the emailed code from the user.
- **Synoptic** needs a reader API key, and `om news setup synoptic` gets one: it links the user's OpenMarket account to Synoptic and stores the key that comes back (interactive only). A failed link (Synoptic not wired up server-side, an upstream error, an account with no verified email) ends the command on that error and stores nothing — relay the error and its fix rather than promising a paste prompt, which only appears when the link succeeds but returns no key. `OM_SYNOPTIC_API_KEY` is the env alternative, and shadows the stored key while it is set.
- There is no `news_setup` action: vendor linking beyond Attention's lazy link is interactive-only. When Synoptic linking is missing, name the nearest door rather than the terminal by reflex — four doors open the SAME guided link: `n` on the news home's `SYNOPTIC: STREAMS` lane, Enter on the news console's locked Streams tab, Enter on the `/setup` panel's news-vendor row, and `om news setup synoptic` in a terminal. From `om chat`, name the first: an unconnected lane's action row IS the connect, so `/news`, `→`, `n` does it in place.
- **State the one-key-at-a-time consequence when you offer that connect.** Synoptic reads for an account through ONE key at a time, so connecting here is also what takes the key away from wherever it was minted last: another machine reading Synoptic streams stops receiving them until it connects again there. What the user bought and what they follow stay theirs — only where they read moves. The three keystroke doors ask this before anything is minted and a decline reaches no vendor at all; the typed command states it instead, because typing it is already the consent.
- Fires only flow while the daemon runs. If `om status` shows the service down, say so with the fix (`om service install`) before the user waits on pings that cannot arrive.

## Author a Fast alert

`news_preview` before `news_create`, always — one `alertWhen` sentence with a closing DO-NOT-fire clause; report `approx` as an estimate and `atLeast` as a floor, never as exact.

Never create an authored Fast alert without previewing the condition first, unless the user explicitly declines:

```bash
om news preview \
  --alert-when "Fire only when a major exchange announces a new BTC perpetual listing. Do not fire on rumors, roadmap posts, or delistings" \
  --window-hours 48 --format json
```

Authoring answers a MOMENT, so a standing-coverage ask reaches the catalog before it reaches this section: "keep me posted on AI model launches" names a subject, and the published Topic for it is followed from `news_catalog` (provider `attention-briefs`) — free, no slot, story cards rather than a ping per headline. Author only what no published Topic covers.

One field authors a Fast alert: `--alert-when`, the moment that matters, in plain English. Write it as "Fire only when …": one kind of event, the specific companies, people or sources involved, and then what should NOT fire ("Do not fire on rumors, speculation…"). The closing exclusion is what separates an alert from a news feed — without it the condition names a subject, and everything that mentions the subject becomes a notification. That one field is the whole alert: the subject Attention retrieves on is derived from the trigger sentence, so the `news_create` action takes no subject at all and none may be invented for one (the terminal takes an advanced, optional `om news create --query` for a user who names a subject their trigger does not). `preview` accepts the same optional `--query`, and leaving it out there means the trigger sentence stands in as the subject for that one back-test — retrieval keys off the subject, so a preview shows the SHAPE of the alert (roughly how often it fires, and on what kind of story), not the exact fires the created alert will produce; say it that way when you report the count.

`--window-hours` accepts 1..168, and the 24h default is a same-day sample. A would-have-fired count quoted to justify a NEW alert runs the full week — `--window-hours 168` (`windowHours: 168`) — and is spoken as one: "last week that would have been 6 pings". State it in the confirmation too, against the condition it was run on: an armed feed whose rate the user never heard is a preview spent for nothing. A day's worth of evidence for a condition meant to run for months reads as thin, and a quiet Tuesday reads as a dead idea. Report the count the way it comes back: two marks, two different claims about a number, and neither is a tally. `approx` (rendered with a `~`) means the count is an ESTIMATE — the vendor sampled rather than exhausted what it counted, so the real figure could be either side of it, and a "likely more" verb means the condition is broader than the number suggests. `atLeast` (rendered as a trailing `+`, "`50+ times it fired`") means the count is a FLOOR — every one of them happened and there were more we did not read, so it can only be under; say "at least 50", never "about 50", which would tell the user their alert might have fired FEWER times than the fires you are showing them. NEVER present either as exact, and never explain how the vendor arrived at it. Calibrate with the user: too many fires means tighten `--alert-when` (it respects explicit "DO NOT fire on ..." clauses); zero fires on a visibly live topic means loosen it. (`om news preview --tracked-entities` calibrates that one back-test only: an authored alert carries its trigger alone, so a count run with entities describes an alert nothing can create.) A `hint` in the result is that judgement already made for you — a trigger that would fire more than ten times a day is a feed, not an alert — so relay it and offer to narrow the trigger before you create anything. Then create with the agreed condition:

```bash
om news create \
  --alert-when "..." \
  --label "New perp listings" --format json
```

Always name what you author: `--label "<short name>"` on the CLI, `title` on the actions. The name is what every surface shows and what the feed's watch is addressed by; without one a Fast alert is named after the subject it watches (the one derived from the trigger), clipped to 60 characters — not a name a person would have chosen. An interactive create (the console's `n` dialog, or `om news create` on a terminal) offers a name for the trigger in an editable box, and the box says whether it holds a written name (Enter stores it) or a clipped copy of the trigger (Enter stores nothing, and the feed keeps the derived name); an empty box leaves it unnamed too.

Edit later with `om news edit <id>` (`--alert-when` to change what fires, `--label` to rename); pause/resume/delete manage lifecycle. Changes are live against the vendor immediately, and a rewritten `--alert-when` discards the alert's replayed history (§"Replay a Fast alert's history") — the edit's own row carries `deletedReplayFires`, the count of what went, so report it and offer to replay the new trigger.

Before creating, check `om news list --format json` and `om event-watch list --format json`: the user may already own, follow, or be covered for the topic. Prefer editing an existing Fast alert, or forking a published one, over creating a near-duplicate.

## Replay a Fast alert's history

`news_replay` sweeps an authored Fast alert's CURRENT trigger back over history it never saw and writes the matches onto its feed; run it after a create and after any trigger edit.

Not `om event-watch backfill`, which imports events into a watch's journal — this one sweeps a Fast alert's trigger over a news corpus and produces fires. A preview counts what a trigger WOULD have caught; a replay writes the rows, and a swept row is a fire like any other: `news_show` returns it with no mark on it, and only the terminal console labels it `replayed` on its history cards. Never claim which of a feed's fires a sweep wrote.

```bash
om news replay <feed> --lookback 1d
```

`--lookback` takes 1h, 4h, 12h, 1d, 3d or 7d, whose 160h is a ceiling set INSIDE the corpus's own seven-day retention so the deepest sweep stays clear of the edge history falls off, and the run reports the span it actually covers. The sweep takes minutes, and longer at 3d and 7d; the terminal command watches it and prints matches as they land (bare `om news replay <feed>`, with no `--lookback`, attaches to the run already going or prints the standing), while `news_replay` answers with a snapshot, so an agent calls it again with no `lookback` until `done` is true — every 30-60s, or once between other work. Read progress as `cursor_at` within `window` — the run's OWN span, swept oldest-first — never within `coverage`, which is wider. Carry `job_id` between polls: coverage outlives any one run, so a reading with a different id is a different sweep and its counts are not the last one's. An alert nothing has ever swept — a fresh one, or one whose trigger was just rewritten — answers `status: never_run` with `done: true` and no window: that is a standing, not an error, and the answer to it is a `lookback`. Esc detaches the terminal watcher without stopping the run; only `--cancel` (`cancel: true`) stops one, and what it swept is kept. Starting a sweep and cancelling one each raise a card; a poll carrying neither reads free.

Two shapes answer without a run to poll. `covered: true` means the span asked for is already swept, so nothing was queued: report the ground that is there and the counts of the run that earned it. `attached: true` means a run was already going ON THIS ALERT and this reading is ITS progress — one replay runs at a time per ACCOUNT, so a run on another alert comes back as a refusal naming that alert, never as a reading of the wrong sweep. And where `coverage_windows` is present it is the real ground: several pieces means gaps, so quote those and never the `coverage` envelope as one continuous span. `cancel: true` conflicts with `lookback` — a stop and a start name different runs — and the pair is refused on both surfaces.

Coverage belongs to the trigger the alert carries right now and is INCREMENTAL, so going 1d then 7d costs the same ground as 7d alone. Two things reset it. Editing the trigger discards the history replayed for the sentence that was replaced (a run in flight ends `superseded`) — so replay AFTER the edit settles, never before. `om news edit --alert-when` and the console's edit dialog ask the user to confirm that loss where a sweep has written something or is writing some (`--yes` is how a script answers), and a `news_edit` carrying `alertWhen` raises an approval card for the same reason — state what the edit costs in your own words before calling it. And the day's replay budget is finite: a run that exhausts it ends `failed` with `error_code: budget_exhausted` — branch on that code, never on the prose in `error` beside it — keeps every fire it wrote, and the allowance is spent OR unavailable, which is what `error` beside the code says; ordinarily it comes back at 00:00 UTC.

Every other ending has its own account too. `error_code` is the class and `error` is the vendor's own sentence about this run: relay it. Causes the sweep cannot get past — `no_keywords`, `no_query_embedding` — end every later run identically, so the answer is rewording what fires the alert, not a retry. A `superseded` ending carries `superseded_reason`, and the three mean different things about the feed: `edit` discarded the rows that run wrote, `paused` stopped the sweep and LEFT them (resume, then replay to carry on), `deleted` leaves no alert at all. An absent reason is not a licence to claim a discard — say the run stopped and nothing more.

Only an alert the user AUTHORED can be replayed; a followed one carries its publisher's own history, and the refusal is `attention_not_authored`. Fork it (`news_fork`) for a copy they author, then replay that. A paused alert has no running trigger to sweep and is refused (`attention_alert_paused`) — resume first. Where the account's deployment carries no replay route at all the refusal says exactly that (`replay_unsupported`): nothing is wrong with the alert, and its other verbs answer as usual.

## Paid Synoptic Streams

Paid catalog Streams — `paid: true` with no amount on the agent surface; non-interactive adds return `purchase_required`; a per-target rate is never simplified into a price.

Some Streams in the Synoptic catalog are sold by the vendor. `om news catalog` and `om news show` carry the price the vendor publishes; on the agent surface a catalog entry carries only `paid: true`, with no amount.

A Stream priced **per target** shows a rate against its step ("US$20 per 200 targets / month"), never a flat price, because the amount buys one step of targets rather than the Stream. What it bills is that rate times the number of steps bought. Repeat that shape if you quote it from a terminal transcript; do not simplify a rate into a price. Amounts carry a `US$` prefix: no Synoptic endpoint returns a currency field, so om labels every amount from one place rather than reading a unit off each price.

On an interactive terminal, `om news add <id>` for a paid Stream offers the purchase: pick a billing option, a hosted checkout page opens in the browser, and om waits for the Stream to unlock and then adds it as usual. Non-interactive and `--format json` runs never prompt — they return `purchase_required`.

A Stream sold **per target** is bought the same way, with a sizing step in the middle. After the billing option, om asks how many targets the purchase should cover (the vendor's `min`/`max` bound the answer), rounds that up to whole steps of the vendor's step size, and prints the arithmetic above the confirmation:

```
Priced at US$20 per 200 targets / month. You chose 250 targets (min 200, max 13,000).
250 targets = 2 steps of 200. 2 steps × US$20 = US$40 / month.
Check that total against Synoptic's checkout page before you pay.
```

The step count is what rides on the checkout. The total is om's own arithmetic on the published rate, and no Synoptic endpoint reads a purchased quantity or its charge back afterwards — which is why the user is told to compare it against the hosted page before paying rather than to reconcile it after. Once the Stream unlocks, om asks for the target list and writes it, capped at the target slots just bought.

Buying a Stream is never unattended. `--yes` answers the purchase confirmation and the target question after it, but the price picker, the target-count question and the target list all still block for an answer, and the checkout itself happens in a browser — so do not offer `--yes` as a way to script one.

Two limits of this flow:

- **A per-target Stream whose envelope names no usable step size is refused before anything is posted.** With no step size there is no step count to send for any target count, so om buys nothing and points at synoptic.com; after buying there, `om news add <id>` adds it normally.
- **Cancelling, changing a plan, seeing a renewal date, or reading an invoice all live at synoptic.com.** Synoptic exposes none of it to om, so om never shows a status or a renewal for a Stream, and neither should you. Users reach that page with the login Synoptic emailed them when their account was set up.

A Stream sold per target delivers nothing until targets are set on it — `om news follow <target> --feed <id>`. An add of one says so; the wording is conditional because whether a list is already in place is not readable per user.

## After any acquisition, verify the pair

Every acquisition auto-attaches a per-feed watch — relay feed + watch + delivery + daemon in one message; `news_attach` repairs `eventWatchLinked: false` / `feed_unwatched`.

`create`, `follow`, `add`, and `fork` auto-attach a per-feed event-watch. The action result reports the attach outcome. Always relay the full picture in one message:

- the feed (vendor, id, label) and the attached watch id;
- whether fires reach a channel. A notify-enabled watch with NO channel is NOT off: fires still show as inline cards in an open `om chat` session; a channel only adds pings for when chat is closed. Frame a channel-less home as "add a channel for closed-session pings" (`/setup` in a terminal `om chat` runs the guided connect inline; `om setup telegram` is the terminal verb) — never as "notifications are off". Only an explicit opt-out is truly off. A watch card-only under `notify_unavailable: "no_default"` takes a `routing_choices` answer through `event_watch_edit`, or a channel named at acquisition; `om setup default` never reaches it. Slack wakes need a verified owner member id: `om setup slack` prompts for it (`--user-id` alone does not persist it); without it, reactive chat works but wakes stay off;
- whether the daemon is running (`om status`), because a stored watch with no daemon fires nothing.

If the attach reports the stream as already covered by an existing watch, say which one. Covered is not the same as firing: when the covering watch is paused, resume it yourself with `event_watch_resume` (which raises a card, like every watch-lifecycle verb this skill reaches; over the plain CLI, `om event-watch resume <id>`) — do not hand the user a command for a tool you hold. Every feed has its own watch — a vendor-wide watch (no per-feed id) cannot be created, and a legacy one never counts as a feed's watch. If an attach reports `broad_watch_id`, that legacy watch also consumes the feed, so its events now arrive twice: tell the user what it is, and offer to clear it with `event_watch_remove` (removing a watch is destructive, so ask first: the call raises an approval card, and `om event-watch remove <id>` is the terminal equivalent, confirming there). To notify on everything from a vendor, don't reach for a vendor-wide watch — set `om config set news.auto_watch.classifier.<vendor> accept_all` so each feed's own watch accepts every event.

Deleting or unfollowing a feed retires its auto-attached watch (`removedWatch` in the result; the journal is kept and its slug stays reserved, so a re-attached watch starts empty, and any room shares bound to that watch are revoked with it). A hand-built watch on the same stream is never auto-removed: it comes back as `keptWatch`: report its id and offer the cleanup with `event_watch_remove`, so the user decides. Editing a Fast alert's trigger re-points the attached watch's goal when it is still the attach-derived default (`watchGoal.status: "realigned"`); a goal the user wrote is reported (`customized`), never overwritten; offer the goal edit instead.

**A feed nothing consumes is repaired in one call.** A `news_list` row with `eventWatchLinked: false` (or `delivery.state: "not_delivering"`, or a `feed_unwatched` warning from `watching_overview`) is a feed the user still holds at the vendor whose matches reach nothing locally. Call `news_attach` with its provider + id: it attaches exactly what an acquisition would have — the per-feed consumer, its goal derived from the feed, the user's classifier and routing settings — and the result's `eventWatch` block says where fires will land. It is non-destructive and idempotent (`status: "exists"` writes nothing), so it is safe to try before diagnosing. Prefer it over hand-building a stream ref through `event_watch_create`: that route fills a missing `channel` and claims the watch for news when the feed is demonstrably the user's, but the claim needs the vendor's owned list to be readable right then, and a create that cannot confirm ownership leaves a hand-built watch `news_delete` will not retire. `status: "disabled"` means the auto-watch bridge itself is off — `om config set news.auto_watch on` in a terminal (there is no config action), then `news_attach` again. Over the plain CLI the same repair is `om news attach <id>` for one feed, and `om news attach --every-feed` for every feed that has none (it picks only feeds with no watch, so muted and card-only feeds are untouched; it also RETIRES watches whose feed the vendor flags source-deleted — permanent, journal kept with its slug reserved, asked in a terminal — so hand over the bare form, never `--yes`).

Auto-attach behavior is user-configurable (`om config set news.auto_watch off`, `news.auto_watch.classifier.attention`, `news.auto_watch.classifier.attention-briefs`, `news.auto_watch.classifier.synoptic`, `news.auto_watch.overview`). If a listed feed shows `not delivering` in the text table (`eventWatchLinked: false` in `--format json`), that config is the first suspect; when the bridge is on, `news_attach` (`om news attach <id>`) repairs the row directly.

"Notify me here" in a chat session is not a channel to configure; never refuse it as unsupported. Explain the split instead: fires already render inline in this chat automatically whenever the session is open, and a notification channel covers the hours the session is closed — connect one with `/setup` in a terminal `om chat` (the nearest door from chat) or with `om setup telegram` / discord / slack / webhook, then `--notify` on the watch. Offer to set up the channel when none exists.

**Routing a feed's alerts.** A destination the user names rides the call's own `channel` field — `news_create`, `news_follow`, `news_fork`, `news_add` and `news_attach` each take one, and it outranks the automatic ladder — so hold the answer there rather than acquiring first and repairing after. The token is a configured channel's name or id, `default` for the user's default, or `none` for card-only (inline cards in om chat, no pings), and it resolves BEFORE the vendor call, so a token naming nothing refuses with the configured names instead of leaving an acquired feed to unwind. Omit it and the feed routes to the channel this conversation posts to, else the default, else the lone channel. On a home with several channels and none of them the default, nothing is picked for the user: the watch stays card-only and the result's `eventWatch` block carries `notify_unavailable: "no_default"` with the destinations to offer in `routing_choices` — ASK which one, then route their choice through `event_watch_edit` (`{id_or_slug: <watch_slug>, notify: {add_channels: [<chosen id>]}}`), which raises its own card carrying the destination they picked; `om setup default` never reaches a watch already marked as routed nowhere. Read `eventWatch.routed_explicit` (`channel` / `no-route` / `conversation`) and `eventWatch.routed_channel_name` and STATE where alerts land — a decided destination is a fact to report, never a nudge about a missing default. On `news_attach` the field sets the destination of the watch that call attaches; a feed that already has one keeps its watch's destination (`status: "exists"`), and re-pointing that is `event_watch_edit` with `{notify: {channel: <id>}}`.

**In the terminal the same decision is a flag.** `om news create`, `om news follow`, `om news add`, `om news fork` and `om news attach` each take `--channel <name|id|default>` (deliver this feed's alerts to that channel) or `--no-route` (keep them card-only in om chat — no delivery; `--channel none` says the same thing). On an interactive terminal with at least one channel configured and neither flag, `follow`, `fork`, `add` and `attach` open a destination **picker** (the same rows as the alert picker: channels most-recently-routed first with their bound thread, and a card-only row below a divider); the news console runs it too, and with a single channel the picker still opens with the cursor on that channel, the card-only row still below the divider. `om news add` opens it only once the stream itself resolves: against a vendor with no managed feeds, or a feed id that looks up to nothing, it asks nothing and fails with its own typed error. `om news create` takes the automatic routing when neither flag is given, and asks only where that routing has no answer — several channels with none of them the default — where it offers the destinations once (after the trigger, so a create that authors nothing settles nothing) and can promote the answer to this machine's default; a `--feed` follow (a Synoptic custom target) attaches no watch of its own and refuses a destination. Whichever surface decides, the choice materializes the feed's auto-attached watch destination and is stated back (*"New matches land in om chat and ping trading-group."* / *"...stay in om chat only, card only, no push."*), and it holds only while auto-watch is on — with `news.auto_watch off` nothing is watched, so no destination is set up: `eventWatch` comes back `status: "disabled"`. A non-interactive/piped run with neither flag skips the picker and takes the same automatic routing.

## Noise and duplicates

Similar pings around one story are expected — map the phrase: "stop pinging" = `news_mute`, "too noisy" = cooldown, "wrong stuff" = tighten, "kill it" = carded removal.

Differently-worded posts about the same development each fire separately; vendors collapse only near-identical wording within a short window. Several similar pings around one hot story is expected behavior, not a bug. When the user complains, diagnose first (`om event-watch events <id> --format json` shows the near-identical titles), explain the behavior, then offer remedies in this order:

1. **Notification cooldown** (keeps the journal complete, quiets the phone): `om event-watch edit <id> --notify-min-interval-sec 1800`. Major updates bypass the cooldown by design, so genuinely big developments still ping immediately.
2. **Confidence floor**: `om event-watch edit <id> --notify-min-confidence 0.8`.
3. **Tighten the condition** (Attention): add "DO NOT fire on ..." clauses to `--alert-when` via `om news edit` — the trigger is the one lever, and the subject retrieval reads follows it.
4. **Sharpen the goal / enable the classifier**: a default watch already runs the local classifier, so `om event-watch edit <id> --goal "..."` with a goal spelling out what counts as genuinely new makes it label repeats as duplicates and notify only on real updates. If the watch was set to `accept_all`, switching it back with `--classifier-mode llm_every_event` restores that filter.

What the user SAYS picks the lever; map the phrase before reaching for any of them:

- "stop pinging me about X": a **mute** (`news_mute`, reversed by `news_unmute`), never a delete. The feed and its journal keep running; only the pings stop. Several feeds = ONE `news_mute` / `news_unmute` call with `ids` (one approval covers the set; neither verb raises a card, so the call dispatches in auto mode with one receipt block and takes one ticket in ask).
- "too noisy" / "five pings about the same story": the **cooldown**, remedy 1 (`--notify-min-interval-sec`). The journal stays complete and major updates still break through.
- "wrong stuff is firing" / "only real announcements, not rumors": **tighten the predicate**, remedies 2-4 (a confidence floor, "DO NOT fire on ..." clauses via `om news edit`, a sharper watch goal).
- "kill the feed" / "delete it": actual removal, which cards (§"Publish, follow, fork"). Confirm it is not a mute in disguise before destroying anything.

## Publish, follow, fork

Publishing is a disclosure and cards; the carded `news_*` set and its exceptions live here — follow is read-only, `news_fork` copies to an owned alert, a declined card answers.

- **Publishing is a disclosure.** It makes the Fast alert's `alert_when`, `query`, and tracked entities world-readable in the catalog. Confirm intent in your own words before calling `news_publish`, and expect the surface to confirm too: on chat surfaces a publish (`public` true, which is also the default when the flag is omitted) raises an approval card naming what goes public. **Six `news_*` calls raise a card**: `news_publish` when it resolves public — on every vendor, because who may list a feed is answered per account and the card follows the direction of the call (a Topic publish is refused for most callers with `briefs_topic_authoring_restricted`, and discloses the Topic for one of Attention's curators) — `news_delete` (permanent, and it retires the feed's event-watch), `news_remove` (it unfollows the stream vendor-side — gated by name, so every removal cards, including the free ones), `news_unfollow` (it retires that feed's watch the same way: the follow is re-added from the catalog at any time, the watch's stored events, backbone, snapshots and room shares are not; two shapes retire nothing: a Synoptic target drop (an unfollow carrying `feed`, which leaves the feed and its watch standing), and a feed with no watch of its own to retire), `news_share` (one call authorizes an open-ended stream of cards into a room under the user's name), and `news_resume` (it re-opens a standing delivery and claims one of the account's active slots). Five more shapes card while the rest of their verb does not: `news_edit` when it carries `alertWhen` (a trigger rewrite permanently discards the history a replay swept for the sentence it replaces, and no later run brings those rows back — §"Replay a Fast alert's history"), `news_replay` when it starts a sweep (a `lookback`) or cancels one (the progress poll starts and stops nothing, so it reads free — §"Replay a Fast alert's history"), `news_brief` with `mode: "schedule_set"` or a `generate` naming a channel (each stands or sends a briefing off-box — §"The daily brief"), `chart_pins` when it targets a chart the user keeps — an explicit `workspace`, or `here: true` for the one they are looking at (either re-points that chart and leaves pins on it that only `chart_delete` removes; the agent's own minted charts and the default day workspace dispatch without a card — §"Plotting events on charts"), and `backtest_news` when it carries `materialize: true` (the paid timeline synthesis runs outside the run's own call cap and persists reconstructed snapshots — §"Backtest before arming anything"). Every other `news_*` call follows the one approvals mode — it dispatches in auto and takes a one-line ticket in ask — taking a feed back down (`public: false`, `om news unpublish <id>`), a `news_edit` that only renames a feed or retunes a Topic's `interest` (neither touches what a sweep wrote), `news_pause`, and `news_unshare` included. Three more cards this skill raises from outside the family, all on the watch side: `event_watch_remove`, the legacy-watch cleanup (§"After any acquisition, verify the pair"; permanent destruction of paid output, so it cards like the removals do), and `event_watch_resume` and `event_watch_edit`, which re-open and re-point a watch's delivery. No approval mode and no session allowance answers any of these — the card appears in every mode — so make the disclosure it will name in your own words before calling. A declined card is the user's answer: do not re-ask or route around it.
- **Several feeds are ONE call, one approval.** Every lifecycle verb here (`news_delete`, `news_remove`, `news_unfollow`, `news_follow`, `news_pause`, `news_resume`, `news_mute`, `news_unmute`, `news_share`, `news_unshare`) takes `ids` beside its single selector, with one `provider` per call (and one `room` for the share pair); one approval covers the set, and where the verb raises a card that card lists every member with its fate (which watch a removal retires, which it keeps; the slot a resume claims; the share state a room binding has); ids the vendor does not know are skipped rows and never dispatched, and a member that fails mid-batch never voids the others. The vendor round-trip verbs (delete, remove, unfollow, follow, pause, resume) cap at 50 per call and stop at the first rate limit with the rest reported `failed: rate_limited` (never retried; re-run the rest later); the local verbs (mute, unmute, share, unshare) cap at 200. Never loop single-id calls for a set: on the verbs that card that is one card per feed, and on the rest one dispatch per feed. The CLI mirrors it: `om news delete|pause|resume <id...>`, `om news remove|mute|unmute <feed...>`, `om news follow|unfollow <target...>`, `om news share|unshare <feed...> --room <room>`.
- **Follow is read-only.** The user receives fires but cannot edit the condition. To customize a Fast alert, `om news fork <id>` copies it into an authored one they own (which holds a slot). The canonical flow: `catalog`, then `show <id>` to read the condition, then `fork`, then `edit`, then optionally `publish`. A Topic has no such flow: the catalog is curated, so following IS the way to hold one, and the interest stays as its publisher wrote it.
- Never print another publisher's raw payload text into chat; relay the same sanitized fields the CLI shows (labels, conditions from `show`, counts).

## Pair watches with markets

`related_markets` tags put a watch's freshest event beside a tagged market's price-alert fires as a "Possible catalyst" line — correlational wording; tag on the user's motive.

A watch can carry market tags (`related_markets`, normalized `EXCHANGE:SYMBOL`). When a price alert fires on a tagged market, the fire notification automatically appends the watch's freshest accepted event from the last few hours as one line: `Possible catalyst (42m ago): <title> [update, 91%]`. The wording is deliberately correlational; never present it as causation.

Doctrine:

- When the user creates a news watch *because of* a market conversation (an alert they just made, a chart they are discussing), tag it: `event_watch_create` with `related_markets`, or `om event-watch edit <id> --market BINANCE:BTCUSDT` for an existing watch (repeat `--market` per ref; `--clear-markets` removes them). Auto-attached news watches are not tagged automatically, because only the conversation knows which market motivated them.
- When the user creates a price alert on a market and no news watch covers it, offer the pairing once ("want to know *why* it moves? I can watch the news on BTC too"), not naggingly.
- Tags are plain metadata: they never affect what the watch matches or fires on, only what price-alert notifications can borrow from it.

## Backtest before arming anything

`backtest_news` answers "would trading this feed's fires have paid?" before any signal — the study lane is free, `--classify` spends (cached).

`om backtest news <feed>` (action `backtest_news`) answers "would trading this feed's fires have made money?" with zero authoring: a free correlational study first (does price move after fires?), then a P&L replay of a synthesized hold-after-fire strategy. Run it before proposing any signal or strategy on a feed's fires; the printed breadcrumb at the end names the exact `om signal create` + `om strategy create` commands. The study lane and `--side` replays cost no LLM calls; `--classify` spends real ones (durably cached, so reruns are free) and classifies each fire with the signal's default prior context, rebuilt as of that fire (`--context-replay normal|advanced` selects how; refused with `--study-only`). An advanced replay over spans with no qualifying snapshot needs `materialize` (`--materialize`): without it the run refuses with the projected call count, and with it the paid timeline synthesis runs outside the run's own call cap and persists reconstructed snapshots — the one shape of this verb that saves anything, and the reason it raises a card in every approval mode. The asset defaults from the watch's single `related_markets` tag: tag first, backtest second.

## Plotting events on charts

`chart_pins` plots any event sources onto a live chart in one call — default silently to the day workspace, one question max, a user-chosen chart cards, filters ride the query.

`om chart pins` (action `chart_pins`) is the plotting verb: ANY event sources onto a live price chart in ONE call. News feeds (Fast alerts, Streams), custom inbound watches, and price alerts (their fires) mix freely. A chart's event lane is a live query over the one event store, and the call writes the query (sources + filter + window + depth + market + workspace); the daemon keeps it true. The result carries the live-view URL to share plus one structured summary. Doctrine:

- **Default silently and act: one call, zero questions.** "Show X on a chart", "plot @scope/name on NQ" or "see the fires on the chart" is one `chart_pins` call with the sources named. A stream address (`@scope/name`, `#member` allowed) is itself a source ref: pass it straight through and the verb resolves every bound role (own, followed, installed) as its own labeled source. Plotting NEVER starts with `chart_show`, `chart_create` or `chart_status`: `chart_pins` finds or mints the workspace itself, so those calls before it are wasted turns (typed refs `{kind: "watch"|"feed"|"alert", ref}` beat bare strings; a bare string works when it is unique across all three namespaces). No sources at all plots every chartable owned source, and a home with none gets a catalog preview. Market defaults from the active chart pane, else the sources' sole market tag; the workspace defaults to the view's own titled day workspace (same view, same day: same chart; `fresh: true` when the user asks for a NEW chart). Never pre-ask what a default resolves, and never hand-build pins from `event_watch_events` plus drawing tools: the verb owns selection, framing, caps, dedup, and live updates.
- **A market named in human form resolves first, never guesses.** "NQ", "Apple", "EURUSD" are not `EXCHANGE:SYMBOL` yet: one `symbol_resolve` call turns the phrase into the chart plane's exact ref (`CME:NQ1!`), TradFi venues included, and a `bound` answer's `market` pastes straight into this verb (a colon-less `market` also self-resolves inside the verb when the directory answers). Ambiguity comes back as named candidates: pick with the user, never guess, and never substitute a crypto proxy for a market the chart plane carries. Candle-backed verbs (backtests, price alerts) work on the TradFi venues the data transport serves (Polygon equities today; `om exchanges` is the coverage answer); a resolved market on a venue outside that set (CME, FX) still refuses with the boundary named, while plotting pins needs no candles at all.
- **ONE question max, and only at a true fork.** Three forks qualify: nothing resolves the market (no active chart AND no sole source tag: the typed `asset_required` names supported venues, so run `symbol_resolve` on the user's phrase first — a bound ref usually dissolves the fork — and otherwise ask which market); a multi-market source with nothing on screen (the same error lists the candidate tags: ask which one); the user names a stream they do not hold (`feed_unwatched`: adding it is an acquisition, so ask before `news_add` / `news_follow`). Everything else defaults and is stated after acting.
- **Echo after acting, one line from the summary.** The result's `disclosure` IS that line, precomposed ("47 events: Fast 12, Streams 29, Custom 5, Alert 1, last 30d, following live"): relay it verbatim, never re-derive the counts, then add depth requested/satisfied and the one narrow-it `hint` when something was cut. Relay every `disclosures` line and each `dropped` entry (layers: window, depth, filter_budget, fill_budget, unrecorded_sources; each names what was cut and the remedy). Auto-fill rides the same line: a journal thinner than the asked depth fills by native vendor replay where the source supports it, `filled` counts what arrived that way, and the shared per-plot fill budget binding is disclosed as a `fill_budget` drop, never silently. A source whose recording began after the asked reach cannot fill; the disclosure says so once. Never present a young journal as "no news happened".
- **Refusals teach; relay the lesson, not the error string.** Topics do not fire (`feed_not_chartable`): offer a Fast alert or Stream on the subject instead. An ambiguous bare ref (`ambiguous_source`) returns cross-namespace candidates: send a typed ref or pick with the user. Alert shadow watches are alert-managed (`event_watch_alert_managed`): route to the alert verbs (`alert_pause` / `alert_resume` / `alert_remove`), never around the refusal.
- **A chart the USER chose gets the confirm language BEFORE targeting.** `workspace: <id>` puts up to 500 events onto a chart the user keeps, and `here: true` does the same to the chart they are looking at; both re-point the sources' live follows there, and the pins stay until `chart_delete` removes the whole workspace. A chat surface raises an approval card for both in every approval mode — neither auto-approval nor a session allowance answers it (the CLI confirms `--workspace`, where `--here` is a human keystroke rather than a target the model picked) — and over MCP nothing gates either call, so this doctrine is the gate: get the user's explicit yes before passing `workspace` or `here: true`. The card is for a chart the user KEEPS: the agent's own minted charts (and the default day workspace, which exists for these pins) dispatch without a card, and an unreadable minted ledger fails closed to the card.
- **Filters are chart-time predicates.** "Only actual strikes, not threats" is `filter`: one plain-English sentence judged per event on the user's own model, fail-closed (an unjudgeable sentence refuses the plot rather than plotting unfiltered), with receipts in the summary's `filter` block and the judge budget disclosed. NEVER create a new alert or feed just to see a filtered view: the journal already holds the events, and the filter is part of the query.
- **Depth beats the window, and arrival is invisible.** Default: the newest 100 matching events (cap 500), split across sources by global recency, over the WHOLE journal; only an explicit `from`/`until` clips, and an asked depth wins over any window a source would default to. Selection is arrival-agnostic (`selection: "any"`): live, backfilled, and caught-up rows all qualify, so a followed chart never freezes in a backfill mode.
- **Alert fires chart like any source.** `sources: [{kind: "alert", ref: <id-or-label>}]` (CLI `om chart pins --alert <id>`) pins the alert's fire history as diamond `alert_fire` pins and follows new fires as they land. Authoring lives in `alerts.md`; the mirror behind it is alert-managed, per the refusal above.
- **Follow is ON everywhere; control ops are separate calls.** A plotted view stays live by default (`follow: false` skips arming and removes nothing). `unfollow: true` stops the live view on a workspace (pins stay; `source` scopes one member); `rearm: true` resets a degraded view's delivery health in place. Never re-arm by re-plotting: a re-plot re-projects and can widen the filter frozen into the binding. Relay the result's `follow` block when the user asks why a chart went quiet.
- **`om news chart` is deprecated and CLI-only; no agent surface carries it.** It stays one release with its old semantics intact (the live-vs-backfill `history` split, follow OFF on explicit-workspace targets, the 30-day default window). Hand the user `om news chart <feed> --rearm` / `--unfollow` only to drive a follow row that verb armed; everything new is `chart_pins`.
- **Offer once, not naggingly.** When the conversation is about a market one of the user's sources covers (its price alert, its backtest, its chart), offer the pin chart ONE time ("want the fires on the chart next to it?"), and never re-offer after a decline. Tagging once (`om event-watch edit <id> --market EXCHANGE:SYMBOL`) makes every later plot and backtest flag-free.

## The daily brief

"Catch me up" on the day's headlines = `news_brief` `get_last` first, `generate` when stale (`fallback` disclosed); schedules: `schedule_set` writes, `schedule_list` reads.

An unscoped catch-up ("what happened today", "what did I miss?", "catch me up", "anything new on my feeds?") opens with `news_brief`, never with a rollup assembled by hand.

`om news brief` (action `news_brief`) rolls everything the user's feeds produced into ONE synthesized, deduplicated briefing: stories merged across feeds, major developments first, a quiet note for feeds with nothing new, nothing repeated from the previous brief unless it advanced. In `om chat` the `/brief` slash renders the same edition as a transcript block. The call sequence:

- Call `news_brief` with mode `get_last` first. If the returned brief is recent (its `window_to` covers the question), relay `body_md` as-is: it is already the answer, do not re-summarize it thinner.
- The body's relative ages ("1m ago", "2h ago") are FROZEN at `body_ages_at` (`created_at` on older records), not measured now. Relaying the body verbatim is fine; repeating one of its ages as your own claim is not — date it against that instant, or say the brief covers `window_from`..`window_to`.
- If it is stale or missing (`not_found`), call mode `generate` (one LLM call when the user has one configured; the fallback is an honest raw fire list and says so via `generator: "fallback"`, which you should mention). A generated edition is relayed the same way: its lead bullets already carry each story's source and age, and re-narrating them as prose drops both.
- Older briefs stay on disk. "What did yesterday's brief say?" is mode `list` (stored briefs newest-first, bodies omitted, `total` for how many exist) then mode `get` with that `id` — a stored brief costs nothing and reads exactly as it did the day it was written, so replay one instead of regenerating the past. An `id` nothing matches comes back as `not_found` carrying the candidates in `details`; pick from those rather than guessing another id.
- Do not fan out over `event_watch_events` / journals to hand-build a rollup when `news_brief` answers the question in one call; the per-watch reads are for drill-down follow-ups ("why did X fire?").
- If the user asks for a catch-up repeatedly across sessions, offer the schedule ONCE: "want this every morning? `om news brief --schedule 08:00`" (mode `schedule_set`, HH:MM local or a 5-field cron; `schedule_off` removes it; one schedule per install, setting again updates it). Never nag about it again after a decline.
- **A scheduled brief lands in ONE destination, so name it in the offer and state it after the call.** Pass `channel` when the user named where the brief should go; after the call, read `schedule.channels` back and SAY where it lands. The token is a channel's name or id, or `default`; `schedule_set` also takes `none`. Where several channels could carry it and none of them is the default, `schedule_set` refuses with `no_default`, writes nothing, and the error names the candidates — ASK which one and schedule with their reply. `channel: "none"` is the third choice: it binds the brief to deliver nowhere, which `schedule_list` reads back as `delivery: "none"`. A schedule the result reports as `destination_unavailable` exists and runs; its brief just has nowhere to land yet, so relay the state and the remedy that gap names.
- **`news_brief` has no schedule READ — `schedule_list` is the read.** "Is my morning brief still on / what time / where does it go?" is answered by `schedule_list` and its `kind: "news_digest"` row: `cron`, `tz`, `enabled`, `lastFiredAt`, and `channelName` (absent means it resolves at fire time, to the default channel else the lone one; where neither answers nothing is picked and delivery waits for a name, and a channel created by adding the agent to a chat is never picked unnamed). `delivery: "none"` is the deliberate local-only binding — the brief is generated and stored daily and pushed nowhere, so read it with mode `get_last` and never offer a remedy for it. Check it before calling `schedule_set`, which replaces the existing schedule rather than reporting a conflict.
- **The brief's destination is its own binding, not the feeds'.** Muting every feed, or leaving every watch card-only, quiets the pings and not the brief: their matches still land in the journal it rolls up. Binding the brief re-points no watch, and routing a feed moves no brief. Both answer "where does my news go?" and are set separately, so say which one you changed.
- `generate` spends an LLM call and `schedule_set`/`schedule_off` mutate durable state; prefer `get_last` whenever freshness allows. `schedule_set`, and a `generate` naming a channel, each raise a card; a local `generate` and `schedule_off` follow the approvals mode.

## Your news voice

"Too chatty / just numbers" → `news_voice` shapes agent-written fire messages and the brief (global or per-feed), never claims; plain alert-style sends stay raw.

- When a user complains about the TONE or FORMAT of their news pings or brief ("too chatty", "just give me numbers", "drop the emoji"), offer `om news voice "<style>"` (action `news_voice`) ONCE; it shapes agent-written fire messages and the daily brief, never what they may claim. Plain alert-style sends are raw by design and are never restyled.
- A per-feed voice (`om news voice <feed> "<style>"`, mode `set_feed`) overrides the global one for that feed's fire messages only.
- Clearing (`--clear`, modes `clear_global`/`clear_feed`) returns to the default persona; a cleared feed falls back to the global voice first.

## Sharing a feed into a room

`news_share` posts fire cards into a room AS THE USER — the instruction must name the room, confirm both ends, `room_not_joined` means join first; `news_unshare` reports counts.

`om news share <feed> --room <room>` (action `news_share`) binds a feed to an OM Chat room: every fire that passes the feed's own notification gates then posts a compact card into the room, at most one per 10 minutes (major updates always post). Doctrine:

- **Sharing is posting as the user.** The cards carry their identity and the room's moderation applies to them, exactly as if they typed each one. Frame it that way when offering or confirming.
- **Never share without an explicit user instruction that names the room.** "Share my Fed feed into #macro" qualifies; "make my feed more visible" does not. Never bind a feed to a room on your own initiative.
- **Confirm both ends before creating**: repeat back which feed and which room ("share 'Fed watch' into #macro?") unless the user's instruction already named both unambiguously. Chat surfaces raise an approval card too; over MCP that card does not exist, so the user's explicit yes has to come first. The user must be a member of the room; a `room_not_joined` error means they join it first (`om room join <room>`), not that you find another room.
- **`--room` takes the room's canonical name or its exact title** — `om room ls` prints both, and `room_search`/`room_list` return the name. A near miss is refused with the rooms it nearly matched (`details.candidates`); an archived room refuses as archived, and nothing can post into one.
- A muted or suppressed fire never reaches a room: shares ride the same gates as the user's private delivery, so quieting a feed quiets its shares too. Say so when a user asks why a muted feed stopped posting. `news_share`'s own result carries `delivery`, `daemon_running` and `vendor_paused` — read them before telling the user cards are on their way.
- A `degraded` share (see `news_shares` / `om news shares`) stopped posting after repeated failures; re-running `news_share` for the same feed and room re-arms it. A `blocker` on a row is the other silence: nobody is signed in, the feed is muted, its watch is paused or gone, or another account on this install owns the binding, and each has its own fix — re-arming clears none of them.
- **`news_unshare` removes every binding of that feed to that room**, and `removed_count` says how many. Re-sharing afterwards starts a new share with zeroed delivered/suppressed counters, so report the count rather than "stopped the share".
- **Posting the daily brief into a room is not a share** and needs no new tool: fetch it with `news_brief` mode `get_last` and post `body_md` with `room_message_send`, only when the user asks for that room by name (the send is itself name-gated and cards).

## What am I watching

`watching_overview` is the one-call answer with `attention_needed` warnings; `delivery.state` and `muted` are reads (absent means unknown), and an unhealthy feed is said so.

In `om chat` (action-capable surfaces), call the `watching_overview` action: one call merges price alerts, event watches with runtime status, news feeds with attach state, and daemon health, and returns an `attention_needed` list of honesty warnings. Surface every warning; each carries its own fix (`feed_muted` → `news_unmute`, `feed_unwatched` → `news_attach`, or `om news attach <id>` over the plain CLI). Over the plain CLI, compose the same answer from three reads: `om news list --format json` (feeds across vendors, with `eventWatchLinked`), `om event-watch list --format json` (watch status, classifier mode, enabled state), and `om status --format json` (daemon up, channel configured). Either way the honesty rule is the same: a feed whose watch is missing, paused, muted, or running under a downed daemon is not really being watched, and the answer must say so.

**"Where do this feed's alerts land?" is a read, not a mutation.** Owned rows from `news_list` (and `news_overview` / `watching_overview` / `news_show`'s `owned`) carry `delivery` — the same resolved answer the CLI's DELIVERY column prints — plus `muted`:

- `delivery.state`: `delivering` (pings reach `delivery.channels`, which name the destinations), `chat_only` (notify is on but no channel receives it, so matches render inline in an open `om chat` only), `muted`, `not_delivering` (nothing consumes the feed — see `delivery.reason`, and repair with `news_attach`, or `om news attach <id>` / `om news attach --every-feed` over the plain CLI), `syncing` (configured to deliver, but the service is down — `om service start`).
- `delivery.state` describes CONFIGURATION and daemon liveness; per-channel TRANSPORT health is a separate system that lives in `om status` / `om doctor` and rides here as `delivery.failing_channels` when the delivery log can be read — so a feed reads `delivering` into a channel that bounces every message, and the honest answer names both ("delivering to telegram, which is failing its deliveries — `om setup deliveries telegram`"). Absent `failing_channels` is unknown, never a clean bill of health.
- `muted: true` means the feed runs and nothing pings; matches keep landing in the journal and the `/news` panel. `news_unmute` reverses it.
- Both fields are OPTIONAL, and **absent means unknown** — the local stores could not be read, or the feed's stream is unknown locally. Never read an absent field as "not muted" or "delivering"; say the state could not be resolved.

`news_overview` also carries `listErrors`: a non-empty array means at least one vendor's feed list failed and the answer is TRUNCATED. Say which vendor is missing rather than presenting a short list as complete.

For what a watch has seen, use `event_watch_events` (`om event-watch events <id>`) or `om event-journal get <slug>` (rolling overview). `event_watch_events` takes the watch id as OPTIONAL: omit it for a merged, source-time-ordered page across every watch — the honest "what fired recently, in order" read — and pass one for a single watch's page. Either way the page is bounded (50 rows by default, 500 at most): counts come from `total_matching`, never from how many rows arrived, and `next_cursor` goes back as `before` for the next page. event-watches.md §"Read journals" carries the rest of the paging contract. Pull only the journal relevant to the question; do not bulk-load journals into context. Correlation against price action belongs to `research.md`; wiring fires to automated trading belongs to `strategy.md`.

## Wall phrasing

A wall is a menu, never a refusal — typed walls only: `active_quota_exhausted` clears by freeing a slot; `authoring_requires_plan` / `follow_requires_plan` are terminal for you.

Two vendors charge, and they wall differently. Both share one rule: never refuse a news request on plan grounds yourself. Attempt the action; only a typed error from the backend is a wall.

**Fast alerts (Attention)** — popular curated channels are free because everyone shares them; specific Fast alerts are paid because they run just for you.

- When a wall arrives on authoring or a niche follow: run the preview first if you have not already (the backtest is the demonstration of what paying buys), report the would-have-fired count, say plainly that specific Fast alerts are the paid lane, and keep the user's condition as a draft in the conversation.
- Always offer the free exit: the curated channel that covers the topic most broadly ("the geopolitics channel catches most export-control headlines, follow it free meanwhile?").
- For guests, the pitch is that the curated channels are free after `om login`; never oversell what a free account gets.

### Reading the plan, and the three walls

**Read it with `news_billing`, before guessing.** `news_billing` (`om news billing`) answers "what plan am I on / how many slots are left / when does it renew" without touching money: `plan_name` (say **Slots**, or the name an earlier plan carries — never the wire ids `fast_slots`/`fast_5`/`fast_30`), `slots_used` / `quota` / `slots_free`, `active` (alerts they authored) and `paused`, `past_due`, `exempt`, `can_author`, `can_follow`, `interval`, `renews_at`, a `scheduled_change` (a cancel, or a drop to fewer slots) with its date, an optional `free_beta` (below), and any Synoptic Streams held (billed separately, and `unchecked > 0` means that list is incomplete). Its `notes[]` are ready-to-relay sentences in the order the CLI prints them — prefer relaying them to writing your own. It carries no price, no URL and no checkout, and it changes nothing. Do not learn the plan by tripping a wall when one call answers.

**One slot, one active alert.** A slot is held by each Fast alert the user authored and by each Fast alert they follow from ANOTHER publisher. Following a **curated** feed costs nothing on any plan — catalog entries and owned rows carry `curated: true` for exactly that, and an entry WITHOUT the mark is another publisher's — and Topics are free to follow always. An owned row marked `sourceGone: true` is the other free row: its publisher deleted the alert it binds to, so it delivers nothing, holds no slot, and unfollowing it frees nothing. So every wall below has the same free exit, and it is the first thing to offer. An ACTIVE row marked `sourcePaused: true` is the opposite case, and worth raising unprompted: the source exists but its publisher holds it paused, so the follow keeps the slot it is billed for and delivers nothing meanwhile (a row the user paused holds none whatever its source is doing). The resume is the publisher's, so `news_unfollow` is the only move the user has — say what the row costs and let them decide, because the publisher can start the feed again at any time and delivery may be set up for it meanwhile.

**The Free Beta — every account holds slots until it ends.** While it runs, any account holds a stated number of slots with no plan at all. `news_billing` reports it as `free_beta: { active, ends_at }` plus `slots` and `granted_slots` while it is open, and `can_author` / `can_follow` answer whether THIS account may act right now, whatever pays for it — read those fields rather than inferring them from the window, and never refuse a request on plan grounds while one says true. Four things to say, and only these:

- Say the beta is open only when `free_beta.active` is **true**. Call it a launch state; never a sale, an offer, a trial, a promotion or something to "claim".
- Say `ends_at` when the beta comes up — read the date off the field, never from memory — and that when it ends, holding slots needs a plan again and alerts over the entitlement are paused, not deleted. `active: false` with an `ends_at` in the past means the beta ENDED — say that, and read the plan from `plan_name`.
- `slots` inside `free_beta` is **the whole cap in force** while the window is open — the bought `quota` plus `granted_slots` — with `slots_free` already counting against it. `granted_slots` is the half that ends on `ends_at`; the rest is what the account bought and outlives the window, so a subscriber asked "what do I lose when it ends?" is told `granted_slots`, never `slots`. Both are ABSENT once `active` is false: never substitute the top-level `quota` for the cap then, and never state a number for it. Holding every slot in the cap answers `active_quota_exhausted` — Wall 1 below, cleared the same way: free one, retry. Never answer a full cap by suggesting a purchase.
- Say following curated feeds is free with or without the beta, every time the end date comes up.

`free_beta` ABSENT means there is no such window: do not mention one, and do not infer it from anything else. It is also absent when `exempt` is true — that account holds alerts without limit, so never quote it a cap. Never state a price for the beta: the agent surface carries no prices at all.

**Wall 1 — `active_quota_exhausted` (they hold slots; every one is in use).** You can clear this yourself, and the interactive console's own resolver does exactly these steps:

1. `news_list` — the active rows are the candidates: an alert they authored, or one they follow from another publisher (a row marked `curated: true` or `sourceGone: true` holds no slot, and a paused row already costs nothing; an ACTIVE row marked `sourcePaused: true` holds a slot and delivers nothing, so offer it first). Run the same steps whether the slots were bought or granted by the Free Beta; under the beta, skip the money paragraph below.
2. Ask WHICH one goes quiet. It is the user's call, never yours, and it is a real tradeoff — a paused alert stops firing.
3. `news_pause` that id (or `news_unfollow` a follow they no longer want), then retry the original `news_create` / `news_fork` / `news_follow` / `news_resume`.

Only reach for money when there is nothing worth freeing, or the user says the wall is wrong for them: then name `om news upgrade` for them to run in a terminal, and use `news_billing` to show what they hold today. Never relay the error string alone — it is written for both audiences, and the half addressed to you is the part the user should not have to read.

**Wall 2 — `authoring_requires_plan` (no slots at all).** There is no self-service exit: authoring takes a slot. Name `om news subscribe` for the account owner to run in a terminal, keep the drafted condition in the conversation so nothing is lost, and offer a curated follow meanwhile. If this wall arrives while a `free_beta` window is open, relay it as a real wall anyway and do not argue the beta at the user.

**Wall 3 — `follow_requires_plan` (no slots, and the feed belongs to another publisher).** The free exit is already in hand: offer a `curated` entry from `news_catalog` that covers the same subject, or a Topic, and follow that instead. Money is the second answer, not the first — `om news subscribe`, for the account owner to run in a terminal.

**All three walls are terminal for you, and buying is never yours.** There is no subscribe, upgrade, checkout or cancel action, and there will not be one: `om news subscribe`, `om news upgrade` and `om news billing` (renewal, fewer packs, cancel, payment method) are hosted Stripe flows a person runs. Name the exact command instead of saying "you'll need to upgrade" — an unnamed handoff is the failure it looks like. Never state a price: the agent surface carries none.

**Synoptic Streams** — the vendor sells a specific Stream, not a plan that covers the catalog. It bills on the interval published with its price and recurs until it is cancelled at synoptic.com. None of the Fast-alerts doctrine above transfers: there is no preview that demonstrates it, no pack to add, and no free curated Stream that substitutes for a specific one. Offering any of those describes a menu that does not exist here.

- A catalog entry carries `paid: true` when the vendor sells it. `news_add` on one fails with `purchase_required`. That error is terminal for you.
- **You cannot buy, and neither can any chat surface.** The purchase runs in a terminal, where a person picks a billing option, sizes a per-target Stream against its bounds, and completes a hosted checkout in a browser. Say that the Stream is paid and that adding it means running `om news add <id>` there. Do not describe it as blocked, and do not offer to retry.
- **Never state a price.** Amounts are not exposed on the agent surface at all, and a Stream priced per target has no single price to state even where they are — its rate buys one step of targets, and what it bills depends on how many steps the buyer takes at checkout.
- Some Streams are sold only inside a package; those are marked `packageOnly`. The package is bought the same way, from the console.

## Injected news context

The fenced `<news_context>` injection is awareness, not coverage — cite `evt_<id>` receipts, run the depth reads in the same turn unasked, and never present the fence as a fetch.

Chat turns may arrive with a `news:` badge on the turn-context line (unread counts plus the loudest headlines) and, when the user's message names something their watches track (or asks to catch up), a fenced `<news_context>` block of story lines with `evt_<id>` ids. Both are deterministic local injections; no tool ran and no vendor was called.

- The injection is awareness, not coverage: answer from its rows when they already answer the question, and never present the fence as something you fetched.
- Cite ids for receipts: write a cited story's id in brackets, e.g. `[evt_12]`, on its own paragraph. In `om chat` that marker renders as the real fire card; on other surfaces it stays a compact reference.
- Depth runs in the same turn, unasked: `event_journal_get` with the slug the line carries for one story's journal; `event_journal_search` for older or broader history (the block says "showing K of N" when its 72h window holds more than it shows); and the market read (`markets` with `exchanges: ["POLYMARKET"]` and a keyword `symbolFilter`, or `polymarket_odds`; both quote LAST-TRADED probability, cite it as that and read the order book before sizing any order) when the subject trades anywhere, folded into the same answer. Do not hand-build a multi-journal rollup when `news_brief` answers in one call.
- No fence means the message matched nothing the vocabulary tracks. Still not a dead end, and still not a permission question: run `event_journal_search` anyway (the vocabulary only speaks for followed subjects; the journal may hold older rows), and the market read when the subject trades. When both miss and the vendor is linked, `news_preview` with a candidate `alertWhen` (Fast alert) or `interest` (Topic) samples what a feed on that subject WOULD have carried, without creating anything: the vendor-search fallback, and the receipts for the one-line watch offer. Only after all of that, say plainly what is not tracked.

**The response contract (cards tell the stories, prose connects them):**

- Never re-describe a story whose id you cite: the rendered card carries it. At most one short note line of NEW context may follow a citation (a position it touches, a thread it advances).
- Catch-up shape, fixed — the shape for answering from the fence's own rows, never for a catch-up a `news_brief` edition answers, which is relayed as the bullets it comes in: one opener line with the counts, then per thread ONE short connective sentence plus its story citations, then a quiet line and one tail hint (`/news`, or `/brief` for the daily edition). Nothing else.
- Question shape, fixed: a 2-3 sentence answer in plain prose, then the cited receipts, then the market line when one exists. An offer line appears only when the offer doctrine (§"One-off answers convert once") grants one (a conversion, never a read).
- Two indent levels only (flush prose and the cards); no nested bullets, no italic asides.
- Broken tools, keys, pairing gaps, and daemon health never interrupt a news answer: they live in `watching_overview`, `om status`, and `om doctor`.

## In-chat news surfaces

`/news` is the single news entry point (HOT TODAY, the three lanes, ON WATCH, `$` billing); `/news fires`, `/brief`, tips and countdown toggles — retired forms are never offered.

In `om chat`, fires render inline as cards, the header's news slot carries the latest headline (or `N new` while fires are unread), and an arrival greeting lists what landed while the user was away. Six commands:

- `/news` — the news home, and the only news surface: a HOT TODAY section over three lanes (`FAST`, `TOPICS`, `SYNOPTIC: STREAMS`) over an ON WATCH card that lists the most recently active feeds with their delivery and age, plus a dim plan line under the masthead. `↑`/`↓` rows, `←`/`→` panes, Enter opens the row (a feed's detail, a catalog row to follow or add), `n` takes the focused pane's action, `s` or `/` searches the lanes in place (Esc clears), `f` jumps to the fires panel, `r` refreshes, `$` opens the billing pane, Esc returns to chat. Enter on ON WATCH opens the watchlist: every feed the user owns or follows — Inbound included — with its delivery state, tabbed All/Fast/Topics/Streams, `m` mutes a row in place, `r` re-reads the page, `q`/Esc goes back to the home. Every screen is the same console `om news list` opens, so a follow, an add, a create or a delivery change behaves identically and keeps its confirmations.
  - **HOT TODAY** is the day's stories, one row each, and it sits above the lanes: whenever it has rows it is the first `←`/`→` stop and where the cursor opens. A row carries the story, how many feeds stand behind it (the day's ranking plus the user's own feeds about it, counted as one list), and the gap line where there are none; the vendor is the authority on both the order and the coverage verdict — om renders the order it was sent and never re-ranks. A row with no feed under it says which gap it is: `nothing covers it yet` (nothing published stands behind the story) or `covered, out of reach here` (published feeds do cover it and this machine can reach none of them — a vendor with no linked credential, so the fix is linking, not authoring). Enter opens the theme's page — the feeds themselves, filled marker = already held, hollow = a follow or an add away, the same chips the `om news list` hot block prints — and the theme's own digit key (`1`, `2`, `3`) opens it from anywhere on the home. `n` on the section writes a Fast alert seeded with the story on exactly the themes that offer that act (nothing published covers it and this machine can author); on every other theme `n` is the FAST lane's own create. Up to three themes show. When the vendor answers nothing, or its answer is too old to stand, the section is simply absent — a missing HOT TODAY is never a claim that the day was quiet.
- `/news fires` — the recent-fires panel: Enter drills into a watch's story, `a` hands the fire to you as a question, `b` opens the news home.
- `/news side` names no surface: the terminal keeps its native scrollback, so there is no docked rail. Fire cards in the transcript and the header ticker carry arrivals, `/news` opens the home, and any `/news side` form answers with a one-line notice.
- `/news tips on` / `/news tips off` — keep or drop the daily brief's footer tip line. Explicit forms only, and the choice persists for every surface the brief reaches — the same switch as `om config set news.tips`, which works from a shell without opening chat.
- `/news countdown on` / `/news countdown off` — keep or drop the Free Beta end date wherever a surface counts down to it (banner, hint line, brief footer, chat cards, channel pings, status row). Off leaves the date on the plan line and in `--format json`, so nothing is hidden that a user asked for. Same explicit-form rule and the same switch as `om config set news.beta_countdown`. This is the answer when the user says the beta is being counted at them.
- `/brief`: the latest daily brief edition as a transcript block, generating today's on demand when none exists yet (the same edition `om news brief` prints and the schedule delivers).

When a user asks where their news went, point at `/news`; when they ask to see recent fires, `/news fires`; when they ask what is hot today, `/news` and its HOT TODAY section. `/news` is the single news entry point — there is no `/news browse`, so never offer it, and the forms above are the whole grammar. On non-TUI surfaces answer the same questions directly from `event_watch_events` and the journals.

## Console handoff

Bare `om news list` opens the full-screen console for hands-on browsing; agents always force flat output with `--format json` or `--provider`.

On an interactive terminal, bare `om news list` opens that same full-screen console on its home screen (browse, follow, fork, publish, watch settings, past fires day by day, all confirmation-gated). "Preview" is the name of the design-time back-test (`om news preview`) and nothing else: what the console shows is a feed's real past fires, never a simulation. Agents always force flat output with `--format json` or `--provider`. When the user wants to browse hands-on rather than through chat, point them at `om news list` in a terminal, or `/news` if they are already in `om chat`.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `backtest_news` · `news_add` · `news_attach` · `news_catalog` · `news_create` · `news_delete` · `news_edit` · `news_follow` · `news_fork` · `news_list` · `news_mute` · `news_package_streams` · `news_packages` · `news_pause` · `news_preview` · `news_publish` · `news_remove` · `news_replay` · `news_resume` · `news_share` · `news_show` · `news_unfollow` · `news_unmute` · `news_unshare` · `news_voice`
  - `provider` — Vendor: 'attention' (default) = FAST, alerts that fire the moment a named condition happens
- `backtest_news`
  - `asset` — Optional when the feed's history carries exactly one market tag; it then defaults to that tag and the result discloses it.
  - `hold` — Default 4h.
  - `from` — Default: 30 days ago.
  - `side` — Fixed side to trade on every fire (default long).
  - `classify` — Each fire classifies WITH the signal's default prior context, rebuilt as of that fire (context_replay selects the mode); the result discloses it.
  - `context_replay` — With classify: how the default prior context is rebuilt per fire — normal (default; the watch's durable development timeline as of the fire) or advanced (as-of overview snapshots where history survives).
  - `materialize_page_size` — Materialization page size, 1..100 (default 100).
  - `history` — live (default): rows the daemon observed in real time (quiet catch-up recovery rows are excluded; their observed_at is the catch-up moment, not live-actionable).
  - `fee_bps` — Default 0.
  - `slippage_bps` — Default 0.
  - `latency_bars` — Default 0.
  - `max_llm_calls` — Default: 200 — a classify run always carries a ceiling, and reaching it refuses with the spend so far, every verdict already paid for durably cached.
- `backtest_news` · `chart_pins`
  - `until` — Default: now.
- `chart_pins`
  - `sources` — OMIT for every chartable owned source (feeds with journals, custom watches, price alerts); a home with none previews a free catalog stream on the chart `here`/`workspace` names.
  - `depth` — Newest N matching events (default 100, wire cap 500), split across sources by global recency.
  - `from` — Only given windows clip; the default is the whole journal, newest-depth.
  - `outcomes` — Subset of accepted journal outcomes to plot (default: all).
  - `market` — Default: the chart pane's market, else the sources' sole market tag, else a typed asset_required refusal naming supported venues.
  - `workspace` — The default (no workspace) is the view's own titled day workspace and needs no confirmation.
  - `fresh` — Default is fresh-or-same-view: the same view re-plotted the same day reuses its workspace.
  - `live` — Default TRUE everywhere (a plotted view stays live).
  - `follow` — Honored when `live` is absent; passing both with different values is refused.
  - `unfollow` — Control op: stop the live view on the target workspace (default: the whole view; pass `source` to drop one member).
- `news_add` · `news_attach` · `news_create` · `news_follow` · `news_fork`
  - `channel` — Omit it and they route to the channel this conversation posts to, else the default; pass it when the user has named a destination.
- `news_attach`
  - `goal` — Omit it and the feed's own trigger/interest becomes the goal, which is what an acquisition does — only pass one when the user asked for something narrower.
- `news_brief`
  - `limit` — list only: how many of the newest stored briefs to return, 1..60 (default: all stored).
  - `window` — Default: since the last brief, else 24h.
  - `channel` — A configured channel's name or id, or 'default' for the user's default.
- `news_create`
  - `title` — A Fast alert defaults to the subject it watches (the one Attention derives from alertWhen), clipped to 60 characters — pass a real name when you author one for a user.
- `news_preview`
  - `feed` — Omit it to try out a new condition/interest.
  - `query` — Omit it unless the user names a subject the trigger doesn't; sending a guess of your own narrows what the alert can ever see.
  - `windowHours` — Lookback window, 1-168h; default 24 (attention/synoptic); Topics default to their full 7-day corpus window
- `news_replay`
  - `lookback` — Omit to read the run already going without starting one.
- `news_show`
  - `fires` — How many fired rows to include, 0..100 (default 5).

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `backtest_news`
  - discloses `disclosures[]` — The run's honesty notes: asset defaulting, the classify lane's context-replay mode, sparse-corpus warnings.
- `news_attach`
  - discloses `eventWatch.notify_style` — The created watch's delivery style: agent (the agent's take, the default) or alert (one-way, the opt-down)
  - discloses `eventWatch.classifier_llm_unavailable` — The watch filters every event through an LLM and none resolves on this host — the reason why. Nothing reaches the user while this is set: events arrive, classification fails, and each one is stored as an error row. Say so plainly and send them to `om init` in a terminal (no action connects an LLM). It is not a failed attach — the watch exists and starts working the moment a credential does.
  - discloses `eventWatch.brief_auto_scheduled` — Creating this watch also switched the daily brief ON (their first feed's default-on): a news_digest schedule now exists. The brief lands at brief_time_label each day, quiet days skip, and news_brief mode=schedule_off (or `om news brief --schedule off`) stops it for good.
  - discloses `eventWatch.brief_time_label` — When the auto-created daily brief lands ("08:00", machine-local time).
  - discloses `eventWatch.brief_auto_declined` — The daily brief was not switched on with this first feed: several channels are configured and none is the default, so a destination would have to be guessed. Say so in one line and offer to schedule it — news_brief mode=schedule_set with `channel` (a name, id, or 'none' to keep it local).
  - discloses `eventWatch.agent_undeliverable` — The watch is agent-style (the default) but this host has no live agent chat. With a channel bound, fires fall back to plain alerts; when notify_unavailable is ALSO set there is no fallback — fires render only as inline cards in om chat. Tell the user `om setup telegram` (then a daemon restart) enables the agent's take
- `news_brief`
  - discloses `brief.body_md` — The briefing markdown: story-grouped items deduplicated across feeds, major developments first, with a quiet note for feeds with nothing new. Relay it to the user as-is; do not re-summarize away detail. When generator=fallback it is a labeled raw per-feed fire list instead, whose '(raw rollup: ...)' first line states what THAT run did and carries no setup advice — what to do about it depends on what is configured now, so read llm_error and the user's current state before advising anything. The body's relative ages are frozen at body_ages_at (created_at on older briefs): never repeat one as though it were measured now.
  - on `not_found` — No stored brief matched: follow the error's own hint (list or re-select a stored one, or mode 'generate' when none exists); if nothing exists at all, the events live in event_watch_events / event_journal_search — and in alert_events on a home whose watches all shadow alerts.

<!-- AUTO: END RESULT CONTRACT -->

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om backtest news` (action: `backtest_news`) — one shot, zero authoring.

- `om chart pins` (action: `chart_pins`) — plot ANY event sources on a chart in ONE call: news feeds, custom inbound watches, and price alerts (their fires), mixed freely.

- `om news` (action: `news_overview`) — Show each news vendor's credential status and the user's own feeds across vendors (Fast alerts, Topics, Streams), each row with where its matches land.
- `om news add` (action: `news_add`) — Add a catalog stream to the user's feeds (Synoptic).
- `om news attach` (action: `news_attach`) — Set up local delivery for a feed the user ALREADY HAS but nothing consumes — the repair behind the `w` key on `om news`'s feed page, and the fix for a `feed_unwatched` warning from watching_overview, or for a `news_list` row with eventWatchLinked:false.
- `om news billing` (action: `news_billing`) — READ the user's Fast-alerts plan: plan name, slots used of the balance and how many are free, paused alerts, payment-failed state, a scheduled cancel or slot drop with its date, the renewal date, exempt status, and any Synoptic Streams held (billed separately).
- `om news brief` (action: `news_brief`) — the daily brief.
- `om news brief list` (action: `news_brief`) — List the stored daily briefs, newest first, without their bodies.
- `om news brief show` (action: `news_brief`) — Replay one stored daily brief by id.
- `om news catalog` (action: `news_catalog`) — Discover browsable feeds you can subscribe to: Synoptic streams, or Fast alerts other users have published (with follower counts) that can be followed without authoring your own.
- `om news create` (action: `news_create`) — Author and create a Fast alert from alertWhen (Attention), the one field it takes.
- `om news delete` (action: `news_delete`) — Permanently delete owned Fast alerts (Attention) or Topics (provider 'attention-briefs'): `id` for one, or `ids` for several in ONE call under one approval card.
- `om news edit` (action: `news_edit`) — Edit an owned Fast alert's fire condition or its name.
- `om news follow` (action: `news_follow`) — Attention: follow a published catalog Fast alert by id, a read-only binding to the publisher's alert, which holds a slot while it runs unless the entry is `curated` (those are free).
- `om news fork` (action: `news_fork`) — Attention: fork (copy-to-own) a published catalog Fast alert by id into a NEW Fast alert you author and own, which you can then edit/pause/publish.
- `om news list` (action: `news_list`) — List the user's own feeds for a vendor (default attention) with configured state: kind (authored/followed/managed), status, whether published to the catalog, whether an event-watch consumes it, and `delivery` — the resolved answer to 'where do this feed's alerts land?' (state + destination channel names) plus `muted`.
- `om news mute` (action: `news_mute`) — Stop a feed's pings WITHOUT stopping the feed: `id` for one, or `ids` for several in ONE call (a member already muted is reported unchanged).
- `om news package` (action: `news_package_streams`) — List the member streams of a Synoptic stream package by id.
- `om news packages` (action: `news_packages`) — Browse curated Synoptic stream packages (bundles).
- `om news pause` (action: `news_pause`) — Pause an owned Fast alert (stops it firing without deleting it): `id` for one, or `ids` for several in ONE call (one approval covers the set; a member already paused is reported unchanged).
- `om news preview` (action: `news_preview`) — See what a feed gives you, WITHOUT creating anything.
- `om news publish` (action: `news_publish`) — Set an owned feed's catalog visibility.
- `om news remove` (action: `news_remove`) — Remove locally managed feeds (Synoptic): `feed` for one, or `ids` for several in ONE call (one vendor for the set; one approval card covers it; never a loop of single calls).
- `om news replay` (action: `news_replay`) — Run an authored Fast alert's CURRENT trigger back over history it never saw, so a freshly written alert has a record instead of an empty page.
- `om news resume` (action: `news_resume`) — Resume a paused Fast alert (Attention) or a paused Topic (provider 'attention-briefs'): `id` for one, or `ids` for several in ONE call (one approval card covers the set; the members compete for the same slot pool, in order, and one refused at `active_quota_exhausted` lands in `failed` while its siblings proceed).
- `om news setup` — (bespoke; see narrative above)
- `om news share` (action: `news_share`) — share feeds' fires into an OM Chat room: `feed` for one, or `ids` for several in ONE call into the one `room` (one approval card covers the set; never a loop of single calls).
- `om news shares` (action: `news_shares`) — list the user's room shares: which feed posts into which room, delivered/suppressed/owed counts, and health (`at_risk` is failing but still trying; `degraded` stopped posting after repeated failures, re-arm it with news_share).
- `om news show` (action: `news_show`) — Show ONE feed in depth: a catalog entry, or one of the user's own (an unpublished alert they authored resolves here too — catalog first, then their own feeds).
- `om news subscribe` — TERMINAL ONLY — buy Fast alerts slots (hosted Stripe checkout). No action exists and none will: name the command for the account owner to run, never offer to buy. Read the plan with `news_billing`.
- `om news unfollow` (action: `news_unfollow`) — Attention: unfollow public Fast alerts by id, `target` for one or `ids` for several in ONE call under one approval card; unfollowing another publisher's frees the slot it held.
- `om news unmute` (action: `news_unmute`) — Resume a muted feed's pings: `id` for one, or `ids` for several in ONE call (a member already unmuted is reported unchanged).
- `om news unpublish` (action: `news_publish`) — Remove an owned alert (Attention) or brief (provider 'attention-briefs') from the discovery catalog; the inverse of `om news publish`, equivalent to publishing with public=false.
- `om news unshare` (action: `news_unshare`) — stop sharing feeds' fires into a room: `feed` for one, or `ids` for several in ONE call out of the one `room` (a member not shared there is reported unchanged).
- `om news upgrade` — TERMINAL ONLY — add a pack of Fast alerts slots to what the account already holds (hosted Stripe confirm page). Same rule as `om news subscribe`: relay the command, never attempt the purchase.
- `om news voice` (action: `news_voice`) — the user's news voice, controlling HOW news is written to them.

<!-- AUTO: END COMMAND REFERENCE -->
