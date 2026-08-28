---
name: openmarket-connect-source
description: Turn a source the user owns or names (their inbox, their CI, a URL they point at, an internal webhook, a log pipe) into a first-class event feed through the daemon's inbound ingest door. Use when the information lives at the user's own place rather than in the world's public coverage ("watch my X", a URL plus watch intent, push/pipe/webhook/ingest language). Builds the watch and the glue, hands at most one paste, and is finished only when the first real event has arrived and classified.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Bash(curl *)
  - Read
  - Write
  - AskUserQuestion
---

# Connected sources: the user's own places as feeds

Vendors carry the world's news. This skill carries everything else: information that lives at a place the user owns or names, delivered through the daemon's inbound ingest door into an ordinary event-watch, so classification, journals, delivery, charts, backtests, and shares all work exactly as they do for a vendor feed.

**The discriminator is one rule: does the information live at a place the user owns or names?** "Watch my IBKR emails" does (their inbox). "Watch our CI" does (their pipeline). "Watch this URL" does (a page they pointed at). "Watch TSLA" does not: that is the world's news, and it stays in the vendor lanes (`news.md`: a Fast alert for a moment, a Topic for a subject, a Stream for a ready-made feed). Phrase cues ("watch my X", a URL plus watch intent, "pipe", "push", "webhook", "ingest") are hints only; test the discriminator, not the wording. Two traps the wording sets:

- **Possessives can lie.** "News about my portfolio companies" is world coverage OF things the user holds, not information AT a place they own, so it routes to the vendor lanes (one Topic per subject), not here.
- **A moment cue never overrides the place.** "Ping me the moment our CI goes red" is a connected source with an alerting goal, not a Fast alert: the vendor cannot see their pipeline, however alert-shaped the sentence is.

**Say the route back in one sentence before building anything.** ("Your inbox is the source here, so I will wire a mail rule into an inbound watch, not a news vendor.") A wrong lane must die in conversation, not in config.

Use this skill when:

- The user asks to watch, monitor, or be alerted on something of THEIRS: their emails, their CI or deploys, their server logs, their internal tools.
- The user names a specific URL, page, or endpoint and wants to know when it changes or posts.
- The user has something that can push (a webhook, a script, a forwarder) and wants it to land in a feed, on a chart, or in their pings.

## The spine every lane shares

One inbound watch is the destination for every lane. Create it first, with the goal distilled from the user's own sentence, because the goal IS the filter:

```bash
om event-watch create --inbound --goal "Fire on real CI failures on main. Do not fire on flaky reruns, scheduled jobs, or branch builds"
```

- `--inbound` means there is no vendor stream: the watch IS the endpoint. The create prints the door once: the `/ingest/v1/<watch>` endpoint plus a bearer token, shown exactly once (only its hash is stored). Losing or leaking the token has one answer, `om event-watch rotate-token <watch>`, and rotation is revocation.
- The default classifier (`llm_every_event`) judges every push against the goal under the watch's normal daily budgets, so a chatty source still yields a clean journal. `--classifier-mode accept_all` journals everything and is the user's explicit opt-out, same doctrine as `news.md`.
- Delivery, channels, muting, and noise tuning are ordinary watch mechanics (`event-watches.md`); the feed also appears in `om news list --provider inbound` like any other feed.

Then build the glue that feeds the door. Build everything you can reach yourself (the watch, the goal, the glue script, the test push); the user's hands are for the one thing only they can touch.

## The five lanes

1. **Vendor-covered.** Check before building: a named PUBLIC place a vendor already carries (government releases, agency feeds, big public accounts) is a vendor feed wearing a URL. `om news catalog` and a follow/add beat any glue, and the result is maintained by someone else. Glue for a covered source is waste; route it back to `news.md`.
2. **Public poller.** A public page or endpoint no vendor carries: first check the declared poller below (a well-formed RSS, Atom, or JSON feed needs no glue at all); otherwise write the poller yourself (a few lines that fetch, diff against the last seen marker, and push only what is new via `om event push <watch> --text ...`), and put it on a cadence with the machine's own scheduler (cron, a launchd or systemd timer) on a box that can reach both the page and the daemon. Pass `occurred_at` and a stable `id` per item so retries dedupe and history lands in source-time order.
3. **Webhook, one paste.** The source can already POST (CI systems, internal scanners, SaaS webhook settings): the door IS the webhook target. Hand one paste for their settings page: the endpoint URL and the `Authorization: Bearer <token>` header, complete, nothing to assemble.
4. **Email rule.** The information arrives in their inbox: hand one paste for their mail provider's rule or script box that turns a matching message into a door POST (subject or sender filter, body as `text`). A provider that can only forward, never POST, gets local glue below (a small fetcher on the user's side of the mailbox) instead of a rule.
5. **Local glue.** Anything already on their machine (a log, a folder, a process, a pipe): a few lines that tail or scan and push. Local glue needs no token at all: `om event push` authenticates as the operator, and with the daemon down an `accept_all` push is still written through the same store path.

## The declared poller: lane 2 without the glue

When the public place is already a well-formed feed (RSS, Atom, or a JSON list of records), do not write lane-2 glue: declare the feed on the watch itself and the daemon's own fixed fetcher polls it. Create the watch with a `poller` source instead of `--inbound`:

```json
{ "adapter": "poller", "stream_ref": { "adapter": "poller", "channel": "feed",
  "extra": { "url": "https://example.com/releases.atom", "format": "atom", "every_sec": "900" } } }
```

- `format` is one of `rss`, `atom`, `json`; `every_sec` is the cadence, an integer from 60 to 86400. When the feed's field names are nonstandard, add a field map: `title_key`, `time_key`, `id_key`, `body_key`, `items_key` (element names for RSS and Atom, dot paths into the document for JSON, for example `items_key: "data.rows"`).
- No script exists and none travels: a shared or installed pack that carries this source is run by the SAME fixed fetcher on every installer's daemon, which is why the consent card says it "fetches from your machine". Pass `occurred_at`-style timestamps through `time_key` so items land in source-time order; items older than the live window (six hours, or twice the cadence if longer) journal quietly as catch-up instead of pinging.
- The fetcher is deliberately narrow, and the limits route for you: https only, private and link-local hosts refused on every poll and every redirect, no cookies and no auth headers ever, one document per poll capped at 2 MiB. A feed behind a login is not a public source (lane 4 or 5); a page that is not one of the three formats needs lane-2 glue, because the declared poller never scrapes HTML.
- First open sweeps the feed's current items silently so a fresh watch does not ping on the backlog; history enters on request via `om event-watch backfill`.

## The one-paste contract

Hand at most ONE paste, and only when the source sits behind the user's own account (their CI's webhook settings, their mail provider's rule box): places only they can touch. The paste block is complete and final: destination, header, body shape, all filled in. The token appears exactly once, inside that paste block, and is never repeated in a later message (only its hash is stored, so there is nothing to reprint; a lost token is a rotate, not a search). If the plan needs a second paste, the lane is wrong: go back one step and pick again.

## Verified means the first event arrived

The word "configured" is banned as an endpoint. Nothing here is done because it is set up; it is done when the first real event arrived and classified as intended, and completion is reported as exactly that: "first event arrived, classified irrelevant, as intended." Wait for the first natural event when the cadence makes that reasonable; otherwise send a test push yourself (`om event push <watch> --text "test: ..."`), read it back (`om event-watch events <watch> --format json`), and say what the classifier did with it. A test event the goal rejects as `irrelevant` is the filter PASSING, not the pipe failing; say it that way.

## Failure modes, named out loud

- **The source cannot reach the daemon port.** The door lives on the daemon's HTTP bind, loopback by default: a CI webhook aimed at a laptop's localhost will simply never arrive. A remote sender needs a reachable door: the always-on VPS install, an SSH tunnel (`ssh -L`), or a TLS-terminating proxy in front of the daemon. Never a bare non-loopback bind: that sends the bearer token in cleartext.
- **No event within the expected cadence.** Recheck the glue, not the watch: is the poller actually running, did the rule match anything, what status did the sender log? 401 is the token (rotate and re-key the sender), 409 is a paused watch (`om event-watch resume`), 422 is a missing or oversized `text`.
- **The daily ingest cap.** Accepted pushes are bounded per watch per UTC day (default 2000, `--ingest-daily-cap`); past it the door answers 429 with `retry_at`. A source that hits it needs the cap raised or the glue made choosier; duplicates never spend the cap.
- **Daemon down.** `om status`, then `om service start` (or `om service install` if none exists): fires only flow while the daemon runs, and saying so beats letting the user wait on pings that cannot arrive.
