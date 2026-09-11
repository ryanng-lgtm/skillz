---
name: openmarket
description: Use the `om` CLI for market data, watches (conditions, pages, feeds, timers and the actions that run on them), scalar metrics and indicators, research studies, runner/service control, and OpenMarket chart workspace actions. Always use `om` commands instead of calling exchange APIs directly.
user-invocable: true
allowed-tools:
  - Bash(om *)
  - Bash(curl *)
  - Bash(jq *)
  - Read
  - Write
  - AskUserQuestion
---

# om — agent playbook

<!-- chat-context: omit-start -->
This is the umbrella skill markdown for the OpenMarket CLI (`om`). Any shell-capable LLM client reads these files to learn how to drive the binary.

One binary, seven jobs:

- **Market data**: `om points`, `om markets`, `om symbols`, `om coins`, `om exchanges`, `om normalized-symbols`, `om block-sizes`, `om tenors`, `om enum`, `om usage`, `om subscribe`, `om polymarket`, `om metric`. Calls the OpenMarket Data API at `https://api.openmarket.xyz` via the bundled SDK. `om metric get` computes any registered scalar metric (price, volume, funding_rate, open_interest, plus indicators like RSI / MACD / EMA / BB / ATR / Stoch) for a symbol on-demand; same metric registry the alert engine uses, so values match what an alert would fire on.
- **WRUN packages**: `om wrun install` installs WRUN packages from local paths, GitHub repos, or registry tarballs; `om wrun ...` scaffolds, validates, builds, exports, installs, lists, removes, upgrades, and configures WRUN indicator packages. Installed outputs become metric ids like `wrun/@scope/name/output` that work with metric lookup, alerts, and chart adds (`om chart indicator add --type wrun/...`). See `marketplace.md` for the registry workflow (install, mount, bind, repoint, list, remove) and `wrun.md` for authoring one.
- **Watches**: `om watch ...` is the one noun for everything a person keeps an eye on and everything that runs when it moves: a market condition, a page, a feed, an X handle, a hosted search, a timer, another watch or an inbound door as the source, with screenshot, errand, verb, execute (an order or a strategy) and judge actions on each row. `om service install` registers the launchd/systemd daemon that evaluates them and delivers to configured channels. See `watch.md`.
- **News / text-event feeds**: `om news ...` manages three products behind one capability-gated surface — **Fast** alerts (name a trigger, get pinged when it happens), **Topics** (name a subject, get a few story cards a day), and **Streams** (ready-made feeds from Synoptic's marketplace). Acquiring any of them auto-attaches a per-feed event-watch, so what they carry reaches journals and notification channels. See `news.md`.
- **Research studies**: `om research study` runs strictly correlational event studies over accepted event-watch rows and one asset's candles. Use it to inspect event anchors and pre/post returns, never as a trade signal. `om research page <url>` reads one web page or document as plain text from this machine (private-network guard, per-origin grants). See `research.md`.
- **Charts**: `om chart ...` to inspect and mutate OpenMarket chart workspaces through a persistent WebSocket the daemon holds open to `collab-service`. Verbs sit directly under `om chart`, with `indicator` and `drawing` as grouped families. Reads: `om chart status`, `om chart list`, `om chart refresh --workspace <id>`. Mutations: `om chart create` (a new workspace — REST, no daemon needed), `om chart layout` (multi-chart grid — `3x1`/`2x2`/...), `om chart symbol` / `om chart interval` / `om chart plot-type` (per-pane), `om chart sync` (symbol/interval/crosshair sync), `om chart indicator add` (RSI/MACD/EMA/...), `om chart drawing add` (TrendLine, FibonacciRetracement), `om chart view` (set the visible time range — ephemeral). See `chart-actions.md` for the full workflow. A grid/layout request is an `om chart layout` change FIRST, then per-pane `om chart symbol`.
The same `om` binary owns all of these surfaces. There is no separate "data", "wrun", "runner", "research", or "collab" CLI.
<!-- chat-context: omit-end -->

Tool-call hygiene: when calling any create/edit tool, omit optional fields you have no user instruction for — never pass a field just to restate its default. Chat surfaces render what each call set versus defaulted, and explicitly passed defaults misreport as user choices.

<!-- chat-context: omit-start -->
Required environment:

| Var | Purpose |
| --- | --- |
| `OM_API_KEY` | OpenMarket Data API auth. Captured interactively by `om init` (stored in `~/.openmarket/om.sqlite`) or exported as an env var. |
| `OM_BASE_URL` (optional) | Override the REST base URL; defaults to `https://api.openmarket.xyz`. |
| `OM_BIND` (optional) | Daemon HTTP bind target; defaults to `127.0.0.1:31337`. Non-loopback binds require a token (auto-generated to `~/.openmarket/runner.token`). |

Channels (Telegram, Discord, …) are configured via `om init` or `om setup <channel>` and persisted in `~/.openmarket/om.sqlite` — no env vars needed.

## How to load this skill

- **Claude Code / Cursor / Aider** (shell agents): point the agent at the `skills/` directory or pipe `om skill show openmarket` / `om skill show openmarket-research` into context.
- **OpenClaw**: `om setup openclaw` writes the bundled skill (SKILL.md + supporting markdown) to `~/.openclaw/skills/openmarket/`, following the Agent Skills open standard.
- **Codex**: `om setup codex` writes the bundled skill to `~/.codex/skills/openmarket/`, same Agent Skills layout.
- **Anything else** (bash, cron, GitHub Actions): read the markdown directly. The skill is markdown-only — there's nothing client-specific in here.
<!-- chat-context: omit-end -->

## Files

- `SKILL.md` (this file) — umbrella index. Routes the agent to the right detail file for the user's question.
- `watch.md`: ONE noun for everything watched and everything that runs on it. Sources (§"Sources"): a market condition (§"Condition source"), a page (§"Page source"), a feed, an X handle, a hosted search, a timer (§"Timer source"), other watches and one watch with several sources (§"Upstream source"), an inbound door; steps (§"Actions"): ai (§"AI step"), tool (§"Tool step") and money (§"Money step", §"Strategy mode") in chains, delivery as a setting; arming one chain per card (§"Arming"), reads (§"Read a watch"), edits (§"Edit a watch"), lifecycle (§"Lifecycle"), budgets (§"Budgets and caps"), the share / publish (one watch or a set as one package) / follow / install / fork / mute / knock doors (§"Doors") and the typed refusals (§"Errors"); the build of one watch from a sentence, the section `watch_kit` serves with this home's facts (§"Build from a description"), trigger versus context roles on sources (§"Trigger and context roles"), `@{Name}` mentions (§"Mentions") and the sandbox preview (§"Preview before enable"). Read when the user wants to be told when a market crosses a level, a page changes, a subject posts or a cadence comes due; wants work or money to run on that moment; asks what is watched or armed, or why a watch is quiet; or wants to share, follow, install, publish or fork one (§"Doors").
- `watch-prompts.md`: what an ai step sees when it runs and how to write one: the header the daemon generates (verbatim), INPUT per source kind, every function on the leash with its return shape, the three answer shapes and their readers, the `definitions` fields for a decision or a word list, `@{Name}` mentions, worked prompts (a judge, a note, a screen) and the refusal-is-the-fix table. Read before writing or editing any ai step's prompt, `tools`, `output` or `definitions`, and whenever a create answers `watching_unknown_source`, `watching_unknown_tool`, `watching_reader_unsatisfied` or `watching_definitions_overlap`.
- `orders.md` — one-shot order placement via `om order place` on a paired execution venue (Hyperliquid and Polymarket CLOB). Read when the user wants to act *now* — limit-bid a level, open or close a position — rather than wire a condition-triggered alert. Covers the flag and JSON-stdin forms, sizing modes, venue account reads, and the preview/confirm safety contract.
- `marketplace.md`: discover, evaluate, install, and publish registry packages (`om search` / `om wrun install` / `om watch publish` / `om yank` / `om access`; strategy templates ride the try-before-install arc, `backtest_run` evaluates a tuned candidate and mints the install token), the WRUN marketplace (mount an installed indicator on a chart, bind an odds input to a market, repoint a pinned one, list, remove) and watch packs: one watch or a set of watches as one package with its sources, chains and dependency pins, installed paused, every chain armed on the installing machine (`marketplace.md §"Watch packs"`). Read when the user mentions the marketplace or registry, wants to install or publish a package, asks what is installed or published, wants a package updated, uninstalled or a version discontinued (`marketplace.md §"Installed packages"`), or wants an installed WRUN indicator on a chart or bound to a market; building one is `wrun.md`.
- `wrun.md` — build a custom sandboxed WRUN indicator from a plain description (`wrun_author` → `wrun_build` → preview → publish): the authoring loop, the metadata dialect, input pins, bindable odds inputs, chart styling. Read when the user asks for an indicator to be built, styled, or its metadata written; installing, mounting, binding, repointing or removing a WRUN package stays with `marketplace.md`.
- `metrics.md` — the VALUE of a metric: one symbol's scalar value (§"Compute"), a universe scan (§"Scan"), and the registry (`metric_list`). Covers every registered metric (price / delta_pct / volume / funding_rate / open_interest plus indicators: RSI / SMA / EMA / MACD / BB / ATR / Stoch) with canonical default params and prompting rules; CCI/MFI/OBV/VWAP/ADX/Ichimoku are chart overlays only, not metrics. Read when the user asks what a metric IS on a symbol ("what's RSI on BTC?", "what's the price of SOL?", "give me the 4h MACD for ETH", "is BTC overbought right now?", "what are the Bollinger Bands on SOL?") or wants to verify what an alert would fire on right now.
- `chart-actions.md` — the chart surface (the picture, never the value): agent commands for inspecting the orchestrator's WS connection (`om chart status`), listing workspaces (`om chart list`), reading live state (`om chart refresh`), and mutating charts (`om chart create`, `om chart layout`, `om chart symbol`, `om chart interval`, `om chart plot-type`, `om chart sync`, `om chart indicator add`, `om chart drawing add`, `om chart view`). Read when the user asks "is the orchestrator/bridge connected?", "what's on my chart workspace?", or asks to: **see / show anything on a chart** ("show me X", "put it on the chart", price action, a level, a comparison) / change the **layout / grid** (e.g. `3x1`, `1x3`, `2x2`, "three across", "split into two") / change a chart's symbol / interval / plot type / toggle multi-chart sync (symbol / interval / crosshair) / add a technical indicator (any metric, or chart-only overlays like Liquidations) / seek / zoom / pan the visible range. For **drawing** tools (trendlines, fibs, shapes, positions, annotations) see `chart-actions-tool-drawing.md`. **A grid dimension or "set up N charts with these symbols" is a `chart layout` change FIRST, then per-pane `chart symbol` — read this file before acting.**
- `chart-actions-tool-drawing.md` — the drawing-tool detail for `om chart drawing` (auto / add / schema / remove). Read when the user asks to draw, add, place, mark, pin, box, annotate, highlight a level / zone / trendline, plot a fib, set up a long/short position, or remove a tool on a chart (any "mark it / pin it / draw it on the chart" phrasing). Covers `chart_drawing_auto` (anchors computed from market data — preferred), `chart_drawing_add` (caller-supplied role-tagged anchors), `chart_drawing_schema` (discover a tool's anchor roles), and `chart_drawing_remove`.
- `news.md` — text-event news/social alerts via `om news`: vendor capabilities (Attention authoring vs Synoptic catalog), preview-before-create doctrine, publish/follow/fork etiquette, auto-attached event-watch verification, and noise/duplicate tuning. Read when the user mentions news, headlines, tweets, social posts, catalysts, or briefs, wants an alert on anything that arrives as text rather than a price, asks what news feeds they have, or complains about duplicate or noisy news pings.
- `connect-source.md`: turning a source the user owns or names (their inbox, their CI, a URL they point at, a webhook, a log pipe) into a first-class event feed through the inbound ingest door. Read when the information lives at the user's own place rather than in public coverage: "watch my X", a URL plus watch intent, or push/pipe/webhook/ingest language.
- `research.md` — backtests and event studies. Read FIRST for any backtest / "would it have worked" ask (§"Reach for backtest_run FIRST": `backtest_run` on a saved strategy or an unsaved candidate, sweeps via `backtest_sweep`), for correlational event studies (§"Event studies"), and for reading one named web page or document (§"Page read (the `page_read` tool)": origin card, untrusted text).
- `rooms-docs.md` — the living-docs layer of OM Rooms chat: Markdown and Excalidraw Canvas files, topic-scoped discovery, CAS revisions, om://doc pills, and the `doc_*` / `canvas_update` lane verbs. Read when working inside a chat room or topic with files: the user asks what files are here, wants a conversation captured, references an om://doc pill, or asks to edit, draw, rename, file, revert, share, archive, or restrict a doc.
- `secrets.md` — sealed (end-to-end encrypted) chat messages: `/secret`, recipient cards, recovery codes. Read for private/sealed sends or secret recovery.

## Routing

Ask-shape rules — pick the surface before reading any detail file:

- A question about a news event, a catalyst, or what someone said or posted ("did X happen?", "what did they say?", "what did @handle post?") → BOTH reads, in this turn, without asking: `event_journal_search` (passing the window the user named) for what your watches already caught, and `web_research` for the live world, plus the odds read (`polymarket_odds`, last-traded) when the subject trades. The live read always runs for these questions; the journal is context beside it, never a reason to skip it. Only an ask about the journal itself ("what did my watches catch", "what do you have on X") stays journal-only. `web_research` says how the X half was read (`x_mirror.route`: X's own API on the stored token, or the public FxTwitter mirror, for a named handle; `x_search: "on_home_grok_credential"`: Grok's live search on the credential this home holds, whatever the chat model) and, when no Grok credential could run it, carries `x_search_hint`: relay it as the last row, every time; never tell the user to switch models. A new watch covers the future, not this turn; nothing captured, nothing found, no market: say so in one line and offer a watch once.
- "Can I SEE it / show me" price action, a level, structure, or a comparison → open it on the chart now (`chart_create`, scratch and unnamed, for an ad-hoc look; `chart_symbol` only on a chart already on screen; depth in chart-actions.md); to draw, mark, or pin on it → chart-actions-tool-drawing.md.
- Anything to be told about LATER, or to have something RUN later ("tell me when", "alert me", "ping me", "watch <subject> for me", "keep tabs on", "every morning at 8", "when Y happens do Z", a URL or an X account to watch, a rule to trade, "build me a watch that ...", a change to a watch) → `watch_kit` FIRST, in the turn it was asked (watch.md §"Build from a description"): one read that carries the shapes and every recipe, this home's channels, providers, venues and watches, and attaches the build verbs. Then ONE `watch_create` draft (a subject through `watch_compose`, a URL through `watch_page_add`, first), its `card` shown verbatim, and the arm card in the same turn (a chain with a money step arms at the terminal, watch.md §"Arming"). A feed beside a price rule is context (watch.md §"Trigger and context roles"); an ai step's prompt is written by `watch-prompts.md`. "What is it doing / is it armed" → `watching_overview`.
- An unscoped "what's going on / catch me up / what did I miss" → `news_brief` first: `get_last`, then `generate` when that edition is stale or `not_found` (news.md §"The daily brief"); `watch_history` / `event_journal_search` drill down after it and stand in when it returns nothing. A systems audit belongs to an explicit status question.
- One metric across many symbols → a single `metric_screen` (metrics.md §"Scan"), never per-symbol `metric_get`s.
- Inside a chat room: "what happened in #x / catch me up" → `rooms_changes_since` (or `room_history` to page a window); "find what someone said" → `room_message_search` (one room) or `rooms_search_messages` (across rooms); file and doc work (what files are here, capture this to a doc, edit or share one) → the rooms doc verbs (rooms-docs.md §"The verbs").
- "Did a watched stream coincide with price?", event anchors, or pre/post returns on event-watch rows → `research_study` (research.md §"Event studies") — correlational, never a signal.

<!-- chat-context: omit-start -->
## Channels

`om setup <name>` pairs an outbound notification channel, and `/setup` in a terminal `om chat` runs that same guided connect inline — from a chat surface, name `/setup` first and the terminal verb second. Routing is **materialized** — a watch stores exactly its `notify.channel` (a channel id), and there is no read-time fan-out. A create with no `channels[]` is **seeded** to the configured **default channel** (set via `om setup default <name>`), or the lone channel when only one is configured; with several channels and no default set the create is **refused** (pass `--channel <name>` or set a default: `om setup default <name>`); with no channels configured it is card-only (no push, no agent take). Pairing the very first channel also routes any still-card-only watches onto it, so specs authored before a channel existed get a real destination (a later second channel re-homes nothing).

| Channel | Setup |
| --- | --- |
| `telegram` | `om setup telegram --token <bot-token> --chat-id <id>` (or interactive) |
| `discord` | `om setup discord --webhook-url <url>` (or interactive) |
| `slack` | `om setup slack --webhook-url <url>` (or interactive) |
| `webhook` | `om setup webhook --webhook-url <url> [--bearer-token <token>]` (generic JSON POST to any http(s) endpoint; watch fires carry a structured block) |

Interactive mode (no credential flags) prompts for the channel name first (defaulting to the adapter id, e.g. `telegram` / `discord`) before collecting credentials — same as `om init`. Pass `--name <name>` to skip that prompt and supply the name on the command line. Pass `--default` to mark the new channel as the default for watches without an explicit destination.

Default-channel management: `om setup default` (show current), `om setup default <name>` (promote), `om setup default --clear` (drop the marker; with several channels a no-`channels[]` create is then refused until you set a default or name channels). `om setup list` shows a `DEFAULT` column with `*` next to the default row.

Per-channel view and routing: `om channel <name>` (name, id, or `default`) shows one channel's bound conversation thread and every watch routed to it, and takes `--add <watch-slug>` / `--remove <watch-slug>` to route a watch on or off it, `--rename <new-name>` to rename the channel (its routes follow), and `--format json`. It flags a spec whose fire would post plainly here (this channel past the wake cap) and footnotes any other channel that shares the same chat.

System lifecycle messages (runner started / stopping, watch paused / resumed) always fan out to every configured channel — the default-channel preference only applies to watch fires.

`om setup openclaw` is a separate flow — it installs the OM skill into a local OpenClaw and registers OpenClaw's webhook as a passthrough target (raw receipt JSON, no rendering by the runner).

## The runner

`om service install` registers a launchd (macOS) or systemd `--user` (Linux) unit that runs the tick loop in the background. It re-reads `~/.openmarket/watches/*.json` each tick (default 10s, override via `--interval-ms`), evaluates every condition watch, fires whenever the condition is TRUE (recurring mode) or once-and-terminates (once mode), and dispatches to configured channels via direct HTTPS POST. Edge semantics live in the leaf operator (`crosses_above` / `crosses_below`) for typed conditions, and in the script body for custom-script conditions — the runner itself is dumb. Lifecycle: `om service [start|stop|restart|status|logs|uninstall]`. Foreground mode (`om run`, no `--service`) is the dev-loop variant — same evaluator, no daemonization. Native Windows uses foreground only (no Task Scheduler integration yet).

The per-tick log line in `runner.log` has the form `[tick] scanned=[ids] evaluated=[ids] fired=[ids] errors=[ids]`. Each bracketed list is the set of watch IDs in that bucket, not a numeric tuple — `scanned=[2,1]` means watches 2 and 1 were scanned, `fired=[2]` means watch 2 fired this tick.

Whenever the runner is up — foreground `om run` or background `om service install` — it also exposes a local HTTP surface on `:31337`: `/healthz`, `/rpc/v1/alert/*` (CRUD over HTTP), `/events/v1` (SSE stream — `alert_fired`, `event_watch_fired`, `channel_delivered`, `channel_failed`, `tick_completed`), `/api/v1/*` (REST proxy to upstream), `/ws/v1/*` (WebSocket proxy). Most `om watch *` CLI commands route through `/rpc/v1/alert/*` when the runner is reachable and fall back to direct filesystem writes when it isn't, so authoring works either way. `om watch history` is the one command that needs the runner (it consumes `/events/v1`).

## Bundling into the binary

The compiled `om` binary embeds these files via Bun's text-import, so `om skill show [name]` works without the repo on disk.

Every file in the `## Files` index above is text-imported into `OPENMARKET_SKILL.files` by `packages/cli/src/skills/package.ts`, with the rooms deep-dives (`rooms-docs.md`, `secrets.md`) riding its `./package-rooms` plane, which a build without the rooms cluster swaps for an empty one.

`om skill list` enumerates them; `om skill show [name]` prints one to stdout.

Installed copies omit the generated command reference below: with a shell available, `om --help` and `om <command> --help` are the live surface, always current with the installed binary.

<!-- chat-context: omit-end -->
