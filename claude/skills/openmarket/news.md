---
name: openmarket-news
description: Discover Attention Fast alerts, curated Topics and Synoptic Streams; preview a feed, inspect subscriptions and billing, read the daily brief, and set the news voice. Feed authoring and management use the watch skill.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om news

The news store discovers text feeds and manages vendor links, subscriptions, previews, briefs and voice. Each acquired feed is a source on a local watch.

### Guardrails

- Attempt an authorized request; only a typed backend error establishes a plan restriction. Read the account's actual entitlement with `news_billing` (§"Wall phrasing").
- Buying, upgrading and cancelling require the person's terminal. Name `om news subscribe`, `om news upgrade` or `om news billing`; paid Streams are acquired from the news store (§"Paid Synoptic Streams").
- **Zero `news_*` calls raise a card** on their bare name. `news_brief` scheduling or sending to a channel raises one; a local read or generation follows the approval mode.
- A vendor feed id is not a local watch id or a registry address. Discover the feed in the store, then use its saved watch for changes. `watch_follow` follows an OpenMarket `@scope/name` stream.
- State the one-key-at-a-time consequence when offering Synoptic linking (§"Account and linking gates").

### Routing

A moment to detect is an OpenFeed on a watch; a subject to follow is a curated Topic; a ready-made stream comes from the catalog. Topics are never described as alerts, triggers or urgent events.

- Discover or inspect a vendor feed: §"Providers and ids". Acquire it through the `/news` store.
- Watch for a moment: watch.md §"Sources" for `watch_create` with one OpenFeed listener. Author a Fast alert only when the person asks for one: preview its complete trigger with `news_preview`, then the same section.
- Read a feed's saved watch: watch.md §"Read a watch". Change its trigger, name or delivery: watch.md §"Edit a watch". Replay history, pause or remove it: watch.md §"Lifecycle".
- Share, follow or fork an OpenMarket watch: watch.md §"Doors". Plot its rows: chart-actions.md §"Pins".
- Watch a person, organization or subject: watch.md §"Watch a subject". A source the user owns or names lives in `connect-source.md`.
- A one-off answer: §"One-off answers convert once". A catch-up across feeds: §"The daily brief". What the user is watching: `watching_overview`, then watch.md §"Read a watch".

| Ask | Call | What to preserve |
| --- | --- | --- |
| "preview this alert condition" | `news_preview` | The complete previewed trigger becomes the listener's `alert_when`; an existing feed is previewed by its vendor id |
| "find a published feed" | `news_catalog` | Its provider and feed id; the store handles acquisition |
| "show this feed" | `news_catalog` with `feed` | Delivered history differs from a simulated preview; inspect a saved watch with `watch_show` |

## X coverage and the Grok hint

Live X search exists only on a Grok credential (a SuperGrok / X Premium subscription or an xAI API key); a home without one covers X indirectly through news echoes and feeds.

An X API token (developer.x.com; pay-per-use, X bills each post read) is stored with `om setup x-api` or the `/setup` X row, checked by one read, and shown by `om status` (`x_api`, with the month's reads). With a token stored, an X handle watch polls X's own API (coverage `api`, official; the mirror covers a poll the API refuses and the reason says so), an X search leg runs on the token with no model request, and a named @handle in research is read through the API (`x_mirror.route: "x_api"`). The lane is never a per-watch setting: `watch_show`'s `x_coverage.next` and the show line name the door (or the fix when the API refused a poll), and the save receipt names the X watches the key moved.

A home that holds a Grok credential reaches live X whatever the chat model: for a question that plainly targets X (an @handle, an x.com link, tweets, posts on X), or when `web_research` is called with `sources: ["x"]`, the call moves to Grok by itself and says so (`x_search: "on_home_grok_credential"`). A question that only implies X (sentiment "on X", chatter) stays on the chat model unless you pass `sources: ["x"]`; the result then says `x_search: "skipped_not_x_targeted"`.

- When a task plainly targets X (an @handle, x.com links, "tweets") and no xAI credential is connected, a created watch may carry a one-time `x_search_hint`: relay it once as its own row, then never raise it again.
- Never block or delay a task on the missing credential; what exists still runs.

## Providers and ids

Fast, Topics and Streams have vendor-scoped ids; inspect a catalog feed before acquiring it and distinguish delivered history from a simulated preview.

- **Fast**, provider `attention`: an authored condition that matches public posts. Preview it with `news_preview`; create the listener through `watch_create`.
- **Topics**, provider `attention-briefs`: Attention's curated subjects, free to follow and sharing the Attention account link. `briefs_topic_authoring_restricted` means browse the catalog, not retry authoring.
- **Streams**, provider `synoptic`: ready-made marketplace feeds. Some are free, some paid, some delayed; never promise that a Stream is live or free.

`news_catalog` lists entries; pass `feed` and its `provider` to inspect one. The CLI equivalent is `om news catalog <feed> --provider <vendor>`. The detail can include the public `entry`, the user's `owned` row, `held`, `entitled` and recent `fires`. `fires: []` means no rows; `fires: null` means history was not read, which can be a gate or a failed fetch. Never call a gated feed quiet.

A published Attention feed's history belongs to its publisher and can be read before following it. A Synoptic Stream's posts require entitlement. A Topic preview is a simulated sample of its interest, not the cards it delivered. For a feed already held, preview its id rather than retyping its condition; relay the returned evidence label and window.

`unsupported_operation` names a vendor boundary. Follow the supported route it returns.

## One-off answers convert once

A one-off news read earns at most ONE entitlement-aware offer (from `news_billing`); a covered subject is cited instead, and a decline is remembered, never re-offered.

"What's happening with X?" answered from news or web data is a one-off read; a watch is the standing version of the same question. The conversion is offered, never pushed. The offer is always a CONVERSION (arm a watch, follow a feed, a paid backfill): never offer a read you can run yourself, and the live read (`web_research`) is no offer either: for any question about what someone posted or said it runs in the same turn, the journal beside it; journal search, journal get, and the odds/market read run in the same turn, unasked, per the injected fence's depth doctrine:

- **A question about what someone posted or said always gets the live read.** `web_research` runs in the same turn, unasked, whatever the journal holds; the journal read runs beside it as context (what your watches already caught, with dates). An empty journal is not "nothing happened", it is "no watch covers this", and a full one is not a reason to skip the live world. Only an ask about the journal itself ("what did my watches catch this week") stays journal-only. Without any Grok credential a named @handle is read through the public FxTwitter mirror (real dated posts) and the reply ends with the Grok how-to line `web_research` returns; a broad X search without Grok is coverage, labeled as coverage, with the same last line.
- **No covering watch: answer, then append ONE entitlement-aware offer line.** One line at the end of the answer, at most one offer per subject per session. Entitlement-aware means the line names a lane this account can take today: a moment to catch is a watch with an OpenFeed; for a subject, read it from `news_billing` (`can_follow` for another publisher's Fast alert, the free follow of a curated feed or a Topic otherwise, and an authored Fast alert only when the person asks for one) rather than guessing, and never state a price. The offer is part of the answer, never a precondition for it.
- **A covered subject is cited, never offered.** When an existing watch or feed already covers the subject, point at it and what it caught ("your Iran watch caught this 2h ago", read from `watch_history`) instead of offering a duplicate. A second watch on a covered subject is next week's duplicate-pings complaint.
- **A decline is remembered.** When the user declines the offer (or waves it off), save it with `memory_save` keyed to the subject (search first with `memory_search`), and never re-offer that subject unprompted, this session or later ones. A remembered decline is lifted only by the user's own ask.
- **Repetition earns receipts, once.** The same subject asked again within a week is the one escalation: offer once more WITH receipts ("third time this week; a watch would have caught 6 events"), taking the count from a real read (`om news preview` for a would-have-fired count, or the covering journal), never invented. Declined again, the subject returns to remembered silence.

## Account and linking gates

Sign-in and vendor links — `guest_not_allowed` fixes with `om login`; Attention links lazily, Synoptic needs `om news setup synoptic` (one key at a time), fires need the daemon up.

- All news verbs need a signed-in OpenMarket account. A guest session gets a typed `guest_not_allowed` error; the fix is `om login`.
- **Attention** needs no key and links lazily on the first Attention verb. `om news setup attention` links up front. If the account has no verified email (Twitter-only login), the first authoring action requires a one-time email verification: drive it with the `account_set_email` / `account_verify_email` actions, relaying the emailed code from the user.
- **Synoptic** needs a reader API key, and `om news setup synoptic` gets one: it links the user's OpenMarket account to Synoptic and stores the key that comes back (interactive only). A failed link (Synoptic not wired up server-side, an upstream error, an account with no verified email) ends the command on that error and stores nothing — relay the error and its fix rather than promising a paste prompt, which only appears when the link succeeds but returns no key. `OM_SYNOPTIC_API_KEY` is the env alternative, and shadows the stored key while it is set.
- There is no `news_setup` action: vendor linking beyond Attention's lazy link is interactive-only. When Synoptic linking is missing, name the nearest door rather than the terminal by reflex — four doors open the SAME guided link: `n` on the news home's `SYNOPTIC: STREAMS` lane, Enter on the news console's locked Streams tab, Enter on the `/setup` panel's news-vendor row, and `om news setup synoptic` in a terminal. From `om chat`, name the first: an unconnected lane's action row IS the connect, so `/news`, `→`, `n` does it in place.
- **State the one-key-at-a-time consequence when you offer that connect.** Synoptic reads for an account through ONE key at a time, so connecting here is also what takes the key away from wherever it was minted last: another machine reading Synoptic streams stops receiving them until it connects again there. What the user bought and what they follow stay theirs — only where they read moves. The three keystroke doors ask this before anything is minted and a decline reaches no vendor at all; the typed command states it instead, because typing it is already the consent.
- Fires only flow while the daemon runs. If `om status` shows the service down, say so with the fix (`om service install`) before the user waits on pings that cannot arrive.

## Paid Synoptic Streams

A paid Stream is acquired in the news store by a person; the agent catalog exposes `paid: true`, never an amount or checkout authority.

Open `/news`, browse `SYNOPTIC: STREAMS`, and choose the catalog entry. The terminal purchase flow offers the vendor's billing options, opens hosted checkout, waits for entitlement, then adds the Stream. An entry marked `packageOnly` is bought through its package.

A per-target rate buys one step of targets. The store asks for the target count, rounds up to whole vendor steps, and shows the calculation before confirmation. The person compares that total with the hosted checkout page; the vendor does not provide a purchased quantity to reconcile afterwards. When entitlement is ready, the store asks for targets. A Stream with no usable step size is refused before purchase.

Never state a price from the agent catalog, offer an unattended purchase, or treat `purchase_required` as permission to buy. Cancellation, plan changes, renewal dates and invoices live at synoptic.com.

## Backtest before arming anything

`backtest_news` answers "would trading this feed's fires have paid?" before any signal — the study lane is free, `--classify` spends (cached).

`om backtest news <feed>` (action `backtest_news`) answers "would trading this feed's fires have made money?" with zero authoring: a free correlational study first (does price move after fires?), then a P&L replay of a synthesized hold-after-fire strategy. Run it before proposing any signal or strategy on a feed's fires; the printed breadcrumb at the end names the exact `om watch action add <feed> --ai <prompt> --output verdict` and strategy-step commands. It answers the same envelope every backtest door does — `choices` (what the run resolved: asset, window, hold, costs), `study`, `report` for the replay half, and ONE `warnings` list carrying the lane's disclosures and the replay's together — so read a disclosure off `warnings`, never out of `report`, and quote `choices` when saying what was actually replayed. A study-only run has no replay and saves no report; a replayed one names its file, which `backtest_report` reads back a section at a time. The study lane and `--side` replays cost no LLM calls; `--classify` grades the feed's own ai verdict step over its fires, the producer a promoted watch runs: the step's model is asked once per fire the verdict memo cannot answer (`max_llm_calls` caps the model requests, and a turn that reads history is two; reruns ask nothing), and the step reads the feed's earlier fires as of each fire through `watch_history`. The asset defaults from the watch's single `related_markets` tag: tag first, backtest second. The window is `--window` (a lookback ending at `--until`) or `--from`/`--until`; `--data-mode live|backfill` picks the corpus (`--history` still works); the cost knobs are `--fee-bps`, `--slippage-bps`, `--latency-bars`, as on every backtest door.

## The daily brief

"Catch me up" on the day's headlines = `news_brief` `get_last` first, `generate` when stale (`fallback` disclosed); a recurring brief uses a timer-source watch.

An unscoped catch-up ("what happened today", "what did I miss?", "catch me up", "anything new on my feeds?") opens with `news_brief`, never with a rollup assembled by hand.

`om news brief` (action `news_brief`) rolls everything the user's feeds produced into ONE synthesized, deduplicated briefing: stories merged across feeds, major developments first, a quiet note for feeds with nothing new, nothing repeated from the previous brief unless it advanced. In `om chat` the `/brief` slash renders the same edition as a transcript block. The call sequence:

- Call `news_brief` with mode `get_last` first. If the returned brief is recent (its `window_to` covers the question), relay `body_md` as-is: it is already the answer, do not re-summarize it thinner.
- The body's relative ages ("1m ago", "2h ago") are FROZEN at `body_ages_at` (`created_at` on older records), not measured now. Relaying the body verbatim is fine; repeating one of its ages as your own claim is not — date it against that instant, or say the brief covers `window_from`..`window_to`.
- If it is stale or missing (`not_found`), call mode `generate` (one LLM call when the user has one configured; the fallback is an honest raw fire list and says so via `generator: "fallback"`, which you should mention). A generated edition is relayed the same way: its lead bullets already carry each story's source and age, and re-narrating them as prose drops both.
- Older briefs stay on disk. "What did yesterday's brief say?" is mode `list` (stored briefs newest-first, bodies omitted, `total` for how many exist) then mode `get` with that `id` — a stored brief costs nothing and reads exactly as it did the day it was written, so replay one instead of regenerating the past. An `id` nothing matches comes back as `not_found` carrying the candidates in `details`; pick from those rather than guessing another id.
- Do not fan out over `watch_history` / journals to hand-build a rollup when `news_brief` answers the question in one call; the per-watch reads are for drill-down follow-ups ("why did X fire?").
- If the user asks for a catch-up repeatedly across sessions, offer a timer-source watch ONCE; `skill_read("watch", section = "Timer source")` carries the cadence and step shape. The terminal also exposes "want this every morning? `om news brief --schedule 08:00`": HH:MM local or a 5-field cron; `om news brief --schedule off` removes that daily brief. This shortcut owns one brief per install, and setting it again updates it. Never nag about it again after a decline.
- **A scheduled brief lands in ONE destination, so name it in the offer and state it after the call.** A timer-source watch uses its `notify` setting; read the saved destination with `watch_show`. The `om news brief --schedule` shortcut takes `--channel` (name, id, `default`, or `none`); read `channels` in its receipt (`schedule.channels` on the `news_brief` action). With several channels and no default it refuses `no_default`, writes nothing and names the candidates: ASK which one, then use their reply. `none` keeps the brief local. A `destination_unavailable` result means the brief runs but has nowhere to land; relay the state and its remedy.
- **Read a timer-source watch with `watch_list` and `watch_show`.** "Is my morning brief still on / what time / where does it go?" needs its timer source, enabled state, steps and destination; never create it again to inspect it. For the `om news brief --schedule` shortcut, `om news --format json` returns `daily_brief` with `cron`, `tz`, `time_label`, `channels`, `last_brief_at` and any destination gap. A paused brief is named separately in `daily_brief_paused`, with its destination and fix. `delivery: "none"` is deliberate: the brief is generated and stored daily and pushed nowhere, so read it with `news_brief` mode `get_last` and never offer a remedy for it.
- **The brief's destination is its own binding, not the feeds'.** Muting every feed, or leaving every watch card-only, quiets the pings and not the brief: their matches still land in the journal it rolls up. Binding the brief re-points no watch, and routing a feed moves no brief. Both answer "where does my news go?" and are set separately, so say which one you changed.
- `generate` spends an LLM call; prefer `get_last` whenever freshness allows. A timer-source watch is authored with `watch_create`, its steps started through `watch_arm`, and its lifecycle read or changed through the watch verbs. The `news_brief` scheduling operation, and a generate naming a channel, each raise a card; a local generate and switching that brief off follow the approvals mode.

## Your news voice

"Too chatty / just numbers" → `news_voice` shapes the normal updates and the brief (global or per-feed), never claims; full updates stay raw.

- When a user complains about the TONE or FORMAT of their news pings or brief ("too chatty", "just give me numbers", "drop the emoji"), offer `om news voice "<style>"` (action `news_voice`) ONCE; it shapes the normal updates and the daily brief, never what they may claim. Full updates are raw by design and are never restyled.
- A per-feed voice (`om news voice <feed> "<style>"`, mode `set_feed`) overrides the global one for that feed's normal updates only.
- Clearing (`--clear`, modes `clear_global`/`clear_feed`) returns to the default persona; a cleared feed falls back to the global voice first.

## Wall phrasing

Read the entitlement with `news_billing`; offer the account's supported next action when a typed vendor refusal arrives.

`news_billing` reports `plan_name`, `slots_used`, `quota`, `slots_free`, `active`, `paused`, `past_due`, `exempt`, `can_author`, `can_follow`, `interval`, `renews_at`, `scheduled_change` and any `free_beta`. Its `notes[]` are ready to relay. Say the plan's display name, not a wire id. Synoptic purchases are separate; `unchecked > 0` makes that list incomplete.

One active authored Fast alert or followed non-curated Fast alert holds one slot. Curated feeds and Topics are free. `sourceGone: true` holds no slot and delivers nothing. An active `sourcePaused: true` follow still holds a slot while its publisher has it paused; report both facts.

For `free_beta`, `active: true` means the window is open and `ends_at` gives its end date. `slots` is the whole cap in force, bought `quota` plus `granted_slots`; only `granted_slots` ends with the window. Those two fields are absent after it closes. Read `can_author` and `can_follow` for what this account may do now. An absent `free_beta` is no window to announce; `exempt: true` is not a cap. When the date comes up, say curated follows remain free. Never describe the beta as a sale or an offer to claim.

- `active_quota_exhausted`: read `news_overview` for the account's active feeds and the saved watches through `watch_list`. Let the user choose which alert to pause before retrying. A source another active watch needs stays running; check the receipt and balance before claiming a freed slot. Never pause one on their behalf without that choice or answer a full cap with a purchase.
- `authoring_requires_plan`: keep the complete drafted condition, name `om news subscribe`, and offer a covering curated feed.
- `follow_requires_plan`: offer a covering curated feed or Topic from `news_catalog`; a paid subscription is the person's terminal choice.
- `purchase_required`: a Synoptic purchase belongs to §"Paid Synoptic Streams".

The reads carry no checkout authority. `om news subscribe`, `om news upgrade` and the money-changing flags of `om news billing` run in the terminal. Relay a typed refusal even during a beta window; do not overrule it from a remembered plan.

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

`/news` opens the store and its ON WATCH list; Enter on a saved feed opens its watch page, while briefs, recent fires and display toggles keep their own forms.

- `/news`: HOT TODAY, `FAST`, `TOPICS`, `SYNOPTIC: STREAMS` and ON WATCH. The home keeps its existing rows and keys: arrows navigate, Enter opens the selection, `n` takes the lane's action, `v` changes the voice, `s` or `/` searches, `r` refreshes, `$` opens billing, and Esc returns to chat.
- Enter on a saved feed opens its watch with LATEST / SOURCES / ACTIONS / SHARING. LATEST shows its fires; SOURCES shows the feed as source 1 with its rule and slot; ACTIONS shows delivery.
- `/news fires`: recent fires. Enter opens the selected watch's story; `a` asks about it and `b` returns to the news home.
- `/news tips on` / `/news tips off`: the brief footer's tip line, also set through `om config set news.tips`.
- `/news countdown on` / `/news countdown off`: the beta countdown, also set through `om config set news.beta_countdown`. Off keeps the date on the plan line and in JSON.
- `/news side` names no surface and returns a notice; there is no docked news rail. `/brief` opens the daily edition, generating it when needed.

HOT TODAY keeps the vendor's ordering and coverage. A missing section says nothing about how quiet the day was. Fire cards in the transcript and the footer count carry arrivals. There is no `/news browse` form.

## Console handoff

Use `/news` in `om chat` for browsing; scripts read `news_overview` or `om news --format json`, and saved feeds are managed through their watch.

A catalog row is a store entry; a saved feed opens its watch page. Preview means `om news preview`, a design-time read whose evidence label is preserved. The watch's LATEST tab holds recorded fires.

<!-- AUTO: ARGUMENT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Argument contract

What each tool here fills in when a field is omitted — the defaults and omit-rules its schema states on top-level fields and one object level down; prose never restates them.

- `backtest_news` · `news_catalog` · `news_package_streams` · `news_packages` · `news_preview` · `news_voice`
  - `provider` — Vendor: 'attention' (default) = FAST, alerts that fire the moment a named condition happens
- `backtest_news`
  - `asset` — Optional when the feed's history carries exactly one market tag; it then defaults to that tag and the result discloses it.
  - `hold` — Default 24h.
  - `from` — Default: 90 days before `until`.
  - `window` — Lookback as `<int><ms|s|m|h|d|w>` ending at `until` (default: now), e.g. '30d'; conflicts with an explicit `from`.
  - `side` — Fixed side to trade on every fire (default long).
  - `data_mode` — live (default): rows the daemon observed in real time (quiet catch-up recovery rows are excluded; their observed_at is the catch-up moment, not live-actionable).
  - `fee_bps` — Default: the traded venue's taker fee.
  - `slippage_bps` — Default: the traded venue's slippage floor.
  - `latency_bars` — Default 1.
  - `max_llm_calls` — Default: 400, two per fire the run reads by default — a classify run always carries a ceiling, and reaching it refuses with the spend so far, every verdict already answered kept in the memo.
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
  - `unfollow` — Control op: stop the live view on the target workspace (default: the whole view; pass `source` to drop one member).
- `news_brief`
  - `limit` — list only: how many of the newest stored briefs to return, 1..60 (default: all stored).
  - `window` — Default: since the last brief, else 24h.
  - `channel` — A configured channel's name or id, or 'default' for the user's default.
- `news_catalog`
  - `fires` — Recent fired rows when inspecting a feed; default 5, 0 skips history.
- `news_preview`
  - `feed` — Omit it to try out a new condition/interest.
  - `query` — Omit it unless the user names a subject the trigger doesn't; sending a guess of your own narrows what the alert can ever see.
  - `windowHours` — Lookback window, 1-168h; default 24 (attention/synoptic); Topics default to their full 7-day corpus window

<!-- AUTO: END ARGUMENT CONTRACT -->

<!-- AUTO: RESULT CONTRACT — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Result contract

What a reply must carry from each result-bearing action here; the per-branch guidance itself rides on the tool result.

- `backtest_news`
  - discloses `warnings[]` — The one honesty channel: every warning the run raised, the report's and the tool's.
- `news_brief`
  - discloses `brief.body_md` — The briefing markdown: story-grouped items deduplicated across feeds, major developments first, with a quiet note for feeds with nothing new. Relay it to the user as-is; do not re-summarize away detail. When generator=fallback it is a labeled raw per-feed fire list instead, whose '(raw rollup: ...)' first line states what THAT run did and carries no setup advice — what to do about it depends on what is configured now, so read llm_error and the user's current state before advising anything. The body's relative ages are frozen at body_ages_at (created_at on older briefs): never repeat one as though it were measured now.
  - on `not_found` — No stored brief matched: follow the error's own hint (list or re-select a stored one, or mode 'generate' when none exists); if nothing exists at all, the events live in watch_history / event_journal_search — and in alert_events on a home whose watches all shadow alerts.

<!-- AUTO: END RESULT CONTRACT -->

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om backtest news` (action: `backtest_news`) — one shot, zero authoring.

- `om chart pins` (action: `chart_pins`) — plot ANY event sources on a chart in ONE call: news feeds, custom inbound watches, and price alerts (their fires), mixed freely.

- `om news` (action: `news_overview`) — Show each news vendor's credential status and the user's own feeds across vendors (Fast alerts, Topics, Streams), each row with where its matches land.
- `om news billing` (action: `news_billing`) — READ the user's Fast-alerts plan: plan name, slots used of the balance and how many are free, paused alerts, payment-failed state, a scheduled cancel or slot drop with its date, the renewal date, exempt status, and any Synoptic Streams held (billed separately).
- `om news brief` (action: `news_brief`) — the daily brief.
- `om news brief list` (action: `news_brief`) — List the stored daily briefs, newest first, without their bodies.
- `om news brief show` (action: `news_brief`) — Replay one stored daily brief by id.
- `om news catalog` (action: `news_catalog`) — Browse available Synoptic streams, Fast alerts and Topics.
- `om news package` (action: `news_package_streams`) — List a Synoptic package's member streams.
- `om news packages` (action: `news_packages`) — Browse curated Synoptic stream packages.
- `om news preview` (action: `news_preview`) — inspect a held feed or test a new Fast trigger without creating anything.
- `om news setup` — (bespoke; see narrative above)
- `om news subscribe` — TERMINAL ONLY — buy Fast alerts slots (hosted Stripe checkout). No action exists and none will: name the command for the account owner to run, never offer to buy. Read the plan with `news_billing`.
- `om news upgrade` — TERMINAL ONLY — add a pack of Fast alerts slots to what the account already holds (hosted Stripe confirm page). Same rule as `om news subscribe`: relay the command, never attempt the purchase.
- `om news voice` (action: `news_voice`) — the user's news voice, controlling HOW news is written to them.

<!-- AUTO: END COMMAND REFERENCE -->
