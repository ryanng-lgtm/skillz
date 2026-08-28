---
name: openmarket-schedules
description: Deliver artifacts on a wall clock with `om schedule` (recurring chart-workspace screenshots to a notification channel) and read the schedule-plane receipts (next fire, run ledger, reliability stats, stand-down recovery), which also cover the news-brief, strategy-digest and worklog-digest cadences managed by their own funnels. Read when the user wants something delivered at a set time ("every morning at 8", "daily chart to Telegram"), asks what is scheduled or when the next fire lands, or asks why a scheduled delivery stopped arriving.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om schedules

Guardrails that hold whichever section you read:

- A schedule fires on a wall clock, unconditionally. "When X happens" is never a schedule: a market condition is an alert (`skill_read("alerts")`), a standing news subject is a feed (`skill_read("news")`). Schedules carry artifacts at times the user names.
- `cron` is a 5-field expression (`m h dom mon dow`) and `tz` MUST be an IANA zone name, never a raw offset: map "UTC+8" to a city zone like Asia/Singapore (Etc/GMT-8 also works, but Etc zones invert the sign). "Every morning" with no time named is a question, not a default.
- Exactly four kinds exist: `workspace_screenshot`, `news_digest`, `strategy_digest`, `worklog_digest`. `schedule_create` mints ONLY `workspace_screenshot`; each digest is a singleton its own funnel manages (§"The four kinds"). Never invent another kind or promise one, and route a digest's cadence change to its funnel, never to a generic verb.
- State the cadence back in the user's words before creating ("a chart of your BTC workspace to Telegram daily at 07:30 Singapore time"), and verify after the create with `schedule_show`: relay the next fire instant and the destination, then stop.
- A schedule counts from creation: the first delivery is the next cron occurrence after now, never an immediate fire. The same rule holds on `schedule_resume`: slots that lapsed while paused or stood down are gone, not replayed.
- A failing schedule is reported as failing, from the receipts: `lastError` on the spec sticks until the next successful slot, `schedule_events` holds the per-slot ledger, and a stood-down schedule names its reason and is only revived by `om schedule resume <id>` (§"Receipts and recovery"). `lastFiredAt` is the consumed-slot cursor (stamped at create and resume, before anything has fired), never a delivery: the delivery clocks are `lastSuccessAt` and `lastAttemptAt`, and `om schedule list` prints `last=` from them.

Routing:

- A standing SUBJECT ("keep me posted on X", headlines, tweets) → the news lane: `om news catalog`, `skill_read("news")`. Its daily brief cadence is `om news brief --schedule <HH:MM|off>`, not a generic schedule verb.
- A market CONDITION ("when BTC crosses 100k") → `skill_read("alerts")`. A condition checked on a cadence is still an alert; the alert engine owns the checking clock.
- A wall-clock ARTIFACT ("chart screenshot every morning", "same chart to Discord at the close") → `schedule_create` (§"Create a screenshot schedule").
- Digest cadences → their funnels: `om news brief --schedule`, `om strategy digest schedule set`, and the work-ledger's own enable/disable verbs for the worklog digest. The generic surface still lists, shows, pauses, resumes and removes them (worklog excepted: its lifecycle verbs refuse and point at the ledger's, save `schedule_resume` clearing a stand-down).
- "What is scheduled", "when does it fire next", "why did nothing arrive", "how reliable is it" → `schedule_list`, then `schedule_show` / `schedule_events` / `schedule_stats` on the id (§"Receipts and recovery"). `schedule_list` shows `enabled` only; whether a disabled entry is paused or stood down comes from `schedule_show`.

Quick routing, the common asks, the call, and what to assume and disclose:

| Ask | Call | What to assume, disclose it, then stop |
| --- | --- | --- |
| "send my BTC chart to Telegram every morning at 8" | `schedule_create` | `kind: "workspace_screenshot"`, `cron: "0 8 * * *"`, `tz` = the user's IANA zone (ask when unknown), `channelName` from `om setup list`, `workspaceId` from `om chart list`; then `schedule_show` and relay its next fire |
| "what do I have scheduled?" | `schedule_list` | one line per schedule: id, kind, cron + tz, destination, enabled or not; `schedule_list` returns bare specs, so a disabled entry is named paused or stood down only after `schedule_show` on it (a stand-down fact lives outside the spec) |
| "when does schedule 3 fire next?" | `schedule_show` | quote `nextFireAt` with its `nextFireBasis` (scheduled / due / retry); paused, stood_down and cron_error have no next fire |
| "why didn't my chart arrive?" | `schedule_show`, then `schedule_events` | read `lastError` and the newest ledger rows before speculating; a stand-down names its reason and the resume command |
| "how reliable is schedule 3?" | `schedule_stats` | fires, errors, on-time rate, first fire, last success; counts are floors when `dataComplete` is false |
| "pause / resume / delete schedule 3" | `schedule_pause` / `schedule_resume` / `schedule_remove` | by id, report once; resume never replays missed slots |
| "change schedule 3 to 9am" | (no edit tool) | remove + re-create with the new cron, or hand the user `/screenshot edit <id> cron <expr>` for a terminal `om chat` |

Reply shape: one line saying what is armed, in the user's words, naming the cadence, the zone, the destination and the next fire; ids are handles, never the headline.

## The four kinds

The kinds a schedule can carry, who creates each, and where it delivers; read this before naming a kind or routing a digest cadence.

| Kind | What fires | Created by | Destination |
| --- | --- | --- | --- |
| `workspace_screenshot` | a chart-workspace PNG | `schedule_create` (`om schedule screenshot create`) | a named alert channel, required |
| `news_digest` | the cross-feed daily brief | `om news brief --schedule` | bound channel, the default at fire time, or local-only |
| `strategy_digest` | the strategy fleet briefing | `om strategy digest schedule set` | its funnel's binding; unbound means local by design |
| `worklog_digest` | the work-ledger digest | the ledger's enable verb (`worklog_enable`) | an OM Rooms ledger channel, in its payload |

## Create a screenshot schedule

The `schedule_create` call for a recurring chart-workspace PNG; read this when the user wants a chart delivered at a set time.

`schedule_create` takes `kind: "workspace_screenshot"`, `cron`, `tz`, `channelName`, and `payload: {workspaceId, caption?}`. The channel must already be configured (`om setup list`; pair one with `om setup <channel>`), the workspace id comes from `om chart list` or a share link, and screenshot fires are rate limited to 1 per minute per user. `enabled: false` (`--paused` on the CLI) creates it dormant for a later `schedule_resume`.

Stagger: on periods of an hour or longer a fire lands up to five minutes after the nominal cron instant (a deterministic per-home offset that keeps fleets off one synchronized wave); `schedule_show` reports the effective instant with the offset. Sub-hourly cadences fire on the nominal clock.

## Receipts and recovery

The read verbs (`schedule_show`, `schedule_events`, `schedule_stats`) and what a stand-down means; read this when asked what fires next or why nothing arrived.

- `schedule_show` is the verification read: the spec, the destination, the next fire with its basis, the last recorded run, and any stand-down fact. `nextFireBasis` is `scheduled` (nominal + stagger, ahead of now), `due` (its instant passed and the daemon runs it on its next pass, so a `due` that persists means the daemon is down: `om service status`), `retry` (a live same-slot retry with its attempt clock), or names why there is none: `paused`, `stood_down`, `cron_error`.
- `schedule_events` is the per-slot run ledger, newest first: one row per slot with `ok` / `error` / `stood_down` and the error text. Use it before speculating about why a delivery did not arrive.
- `schedule_stats` aggregates the retained ledger: fires, errors, on-time rate, first fire, last success, stand-downs. When `dataComplete` is false the counts are floors (retention pruned history), never totals.
- A slot is consumed when it fires or terminally fails; slots missed during an outage collapse into the latest one. Transient screenshot failures (network, timeout, 5xx, rate limit) retry the SAME slot on a backoff ladder until the next natural slot approaches; digest kinds record the failure and move on.
- Repeated failures stand a schedule down (10 straight failed runs for screenshots, 3 straight cron evaluation failures for any kind): it flips to `enabled: false` (the worklog digest excepted: its flag belongs to the ledger's verbs, so only `schedule_show` reveals its stand-down), keeps the reason in the sidecar (`schedule_show` reports it; `schedule_list` shows no more than the flag), and sends a notice carrying the literal `om schedule resume <id>`. Resume clears the streaks and arms the next occurrence after now; report a stand-down as "stood down after N failures: reason", never as "paused". A stood-down worklog digest is re-armed the same way: `schedule_resume` clears its stand-down and leaves its enabled flag as the ledger's verbs set it (a plainly disabled one takes `om worklog enable`, not resume).

<!-- AUTO: COMMAND REFERENCE — do not edit by hand. Regenerate with `bun packages/cli/scripts/gen-skills.ts` -->

## Command reference

Every `om` command this skill covers, one line each with its action name — check exact verbs and spellings here.

- `om schedule` — (bespoke; see narrative above)
- `om schedule events` (action: `schedule_events`) — The per-slot run ledger for one schedule by id, newest first, each row a slot's latest attempt (ok, error, stood_down) with its start and finish clocks and error text.
- `om schedule list` (action: `schedule_list`) — List every configured recurring schedule (enabled and paused).
- `om schedule pause` (action: `schedule_pause`) — Stop a schedule from firing until it is resumed.
- `om schedule remove` (action: `schedule_remove`) — Delete a recurring schedule by id.
- `om schedule resume` (action: `schedule_resume`) — Re-enable a paused or stood-down schedule by id.
- `om schedule screenshot` — (bespoke; see narrative above)
- `om schedule screenshot create` (action: `schedule_create`) — Register a recurring wall-clock job.
- `om schedule show` (action: `schedule_show`) — One schedule by id: its spec, the next effective fire (cron occurrence plus this home's stagger, or a live retry's attempt clock), error streaks, any stand-down fact, and the last run.
- `om schedule stats` (action: `schedule_stats`) — Reliability receipts for one schedule by id, aggregated from its retained run ledger (fires, errors, on-time rate, first fire, last success, stand-downs).

<!-- AUTO: END COMMAND REFERENCE -->
