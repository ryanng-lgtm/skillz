---
name: openmarket
description: Use the `om` CLI for market data, alerts, scalar metrics and indicators, event-watch journals, research studies, runner/service control, and OpenMarket chart workspace actions. Always use `om` commands instead of calling exchange APIs directly.
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

One binary, eight jobs:

- **Market data**: `om points`, `om markets`, `om symbols`, `om coins`, `om exchanges`, `om normalized-symbols`, `om block-sizes`, `om tenors`, `om enum`, `om usage`, `om subscribe`, `om polymarket`, `om metric`. Calls the OpenMarket Data API at `https://api.openmarket.xyz` via the bundled SDK. `om metric get` computes any registered scalar metric (price, volume, funding_rate, open_interest, plus indicators like RSI / MACD / EMA / BB / ATR / Stoch) for a symbol on-demand; same metric registry the alert engine uses, so values match what an alert would fire on.
- **WRUN packages**: `om install` installs WRUN packages from local paths, GitHub repos, or registry tarballs; `om wrun ...` scaffolds, validates, builds, exports, installs, lists, removes, upgrades, and configures WRUN indicator packages. Installed outputs become metric ids like `wrun/@scope/name/output` that work with metric lookup, alerts, and chart adds (`om chart indicator add --type wrun/...`). See `marketplace.md` for the registry workflow (install, mount, bind, repoint, list, remove) and `wrun.md` for authoring one.
- **Alert engine**: `om alert ...` to author alerts as JSON files under `~/.openmarket/alerts/` (typed conditions OR custom-script conditions backed by files under `~/.openmarket/scripts/`), optional Hyperliquid or Polymarket auto-execution via `on_fire.execute`, `om service install` to install a launchd/systemd daemon that watches them, `om alert watch` to tail fire events in real time.
- **News / text-event feeds**: `om news ...` manages three products behind one capability-gated surface — **Fast** alerts (name a trigger, get pinged when it happens), **Topics** (name a subject, get a few story cards a day), and **Streams** (ready-made feeds from Synoptic's marketplace). Acquiring any of them auto-attaches a per-feed event-watch, so what they carry reaches journals and notification channels. See `news.md`.
- **Event watches**: `om event-watch ...` manages persistent event-stream monitors; `om event-journal ...` retrieves their local Markdown event journals on demand. See `event-watches.md`.
- **Research studies**: `om research study` runs strictly correlational event studies over accepted event-watch rows and one asset's candles. Use it to inspect event anchors and pre/post returns, never as a trade signal. `om research page <url>` reads one web page or document as plain text from this machine (private-network guard, per-origin grants). See `research.md`.
- **Charts**: `om chart ...` to inspect and mutate OpenMarket chart workspaces through a persistent WebSocket the daemon holds open to `collab-service`. Verbs sit directly under `om chart`, with `indicator` and `drawing` as grouped families. Reads: `om chart status`, `om chart list`, `om chart refresh --workspace <id>`. Mutations: `om chart create` (a new workspace — REST, no daemon needed), `om chart layout` (multi-chart grid — `3x1`/`2x2`/...), `om chart symbol` / `om chart interval` / `om chart plot-type` (per-pane), `om chart sync` (symbol/interval/crosshair sync), `om chart indicator add` (RSI/MACD/EMA/...), `om chart drawing add` (TrendLine, FibonacciRetracement), `om chart view` (set the visible time range — ephemeral). See `chart-actions.md` for the full workflow. A grid/layout request is an `om chart layout` change FIRST, then per-pane `om chart symbol`.
- **Strategies**: `om signal` + `om strategy` wire a signal (over a watched event stream or a market metric) to automated trading on Polymarket or Hyperliquid — a signal emits a direction/conviction view, a strategy binds it to a pinned market + sizer, and the daemon evaluates enabled strategies each tick (observe / paper / dry_run / live). Author, then `om strategy resume`; the daemon acts (no foreground strategy-run command). See `strategy.md`.

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
- `alerts.md` — alert anatomy, §"Condition tree" and §"Alert fields and defaults", the create workflow (§"Create an alert"), error recovery (§"Errors"). Read when the user mentions alerts, conditions, thresholds, `om alert ...`, or wants to be notified about a market. Also covers the optional `on_fire.execute` block — independent of the condition, so a `kind: script` condition can auto-execute too (a stateful strategy can place orders, not just notify).
- `orders.md` — one-shot order placement via `om order place` on a paired execution venue (Hyperliquid and Polymarket CLOB). Read when the user wants to act *now* — limit-bid a level, open or close a position — rather than wire a condition-triggered alert. Covers the flag and JSON-stdin forms, sizing modes, venue account reads, and the preview/confirm safety contract.
- `marketplace.md`: discover, evaluate, install, and publish registry packages (`om search` / `om install` / `om publish` / `om yank` / `om access`; strategy templates ride the try-before-install arc — `package_try` evaluates a tuned candidate and mints the install token), and the WRUN marketplace — mount an installed indicator on a chart, bind an odds input to a market, repoint a pinned one, list, remove. Read when the user mentions the marketplace or registry, wants to install or publish a package, or wants an installed WRUN indicator on a chart or bound to a market; building one is `wrun.md`.
- `wrun.md` — build a custom sandboxed WRUN indicator from a plain description (`wrun_author` → `wrun_build` → preview → publish): the authoring loop, the metadata dialect, input pins, bindable odds inputs, chart styling. Read when the user asks for an indicator to be built, styled, or its metadata written; installing, mounting, binding, repointing or removing a WRUN package stays with `marketplace.md`.
- `metrics.md` — the VALUE of a metric: one symbol's scalar value (§"Compute"), a universe scan (§"Scan"), and the registry (`metric_list`). Covers every registered metric (price / delta_pct / volume / funding_rate / open_interest plus indicators: RSI / SMA / EMA / MACD / BB / ATR / Stoch) with canonical default params and prompting rules; CCI/MFI/OBV/VWAP/ADX/Ichimoku are chart overlays only, not metrics. Read when the user asks what a metric IS on a symbol ("what's RSI on BTC?", "what's the price of SOL?", "give me the 4h MACD for ETH", "is BTC overbought right now?", "what are the Bollinger Bands on SOL?") or wants to verify what an alert would fire on right now.
- `chart-actions.md` — the chart surface (the picture, never the value): agent commands for inspecting the orchestrator's WS connection (`om chart status`), listing workspaces (`om chart list`), reading live state (`om chart refresh`), and mutating charts (`om chart create`, `om chart layout`, `om chart symbol`, `om chart interval`, `om chart plot-type`, `om chart sync`, `om chart indicator add`, `om chart drawing add`, `om chart view`). Read when the user asks "is the orchestrator/bridge connected?", "what's on my chart workspace?", or asks to: **see / show anything on a chart** ("show me X", "put it on the chart", price action, a level, a comparison) / change the **layout / grid** (e.g. `3x1`, `1x3`, `2x2`, "three across", "split into two") / change a chart's symbol / interval / plot type / toggle multi-chart sync (symbol / interval / crosshair) / add a technical indicator (any metric, or chart-only overlays like Liquidations) / seek / zoom / pan the visible range. For **drawing** tools (trendlines, fibs, shapes, positions, annotations) see `chart-actions-tool-drawing.md`. **A grid dimension or "set up N charts with these symbols" is a `chart layout` change FIRST, then per-pane `chart symbol` — read this file before acting.**
- `chart-actions-tool-drawing.md` — the drawing-tool detail for `om chart drawing` (auto / add / schema / remove). Read when the user asks to draw, add, place, mark, pin, box, annotate, highlight a level / zone / trendline, plot a fib, set up a long/short position, or remove a tool on a chart (any "mark it / pin it / draw it on the chart" phrasing). Covers `chart_drawing_auto` (anchors computed from market data — preferred), `chart_drawing_add` (caller-supplied role-tagged anchors), `chart_drawing_schema` (discover a tool's anchor roles), and `chart_drawing_remove`.
- `news.md` — text-event news/social alerts via `om news`: vendor capabilities (Attention authoring vs Synoptic catalog), preview-before-create doctrine, publish/follow/fork etiquette, auto-attached event-watch verification, and noise/duplicate tuning. Read when the user mentions news, headlines, tweets, social posts, catalysts, or briefs, wants an alert on anything that arrives as text rather than a price, asks what news feeds they have, or complains about duplicate or noisy news pings.
- `connect-source.md`: turning a source the user owns or names (their inbox, their CI, a URL they point at, a webhook, a log pipe) into a first-class event feed through the inbound ingest door. Read when the information lives at the user's own place rather than in public coverage: "watch my X", a URL plus watch intent, or push/pipe/webhook/ingest language.
- `event-watches.md` — creation, discovery, lifecycle, and on-demand journal retrieval for watched event streams.
- `research.md` — backtests and event studies. Read FIRST for any backtest / "would it have worked" ask (§"Reach for backtest_run FIRST": `backtest_run` on a saved strategy or an unsaved candidate, sweeps via `backtest_sweep`), for correlational event studies (§"Event studies": whether a watched event stream coincided with market moves, event anchors, pre/post returns), and for reading one named web page or document (§"Page read (the `page_read` tool)": origin card, untrusted text).
- `signal.md` — the `om signal` producer surface: the three signal kinds (`text_long_short`, `metric_level_rule`, `metric_band_rule`) and their tunables — topic-as-policy, context/memory, model pins, the decision cache, bar/tick evaluation + cooldown, and the identity-change (`force`) guard. Read when the user asks what signal kinds or signal settings exist, wants to create or tune a signal on its own, or asks why a signal edit was refused. For binding a signal to a market and trading it, `strategy.md` is the continuation.
- `strategy.md` — author and operate daemon-native, signal-driven strategies end to end (an `om signal` — over an event-watch or a market metric — bound to a pinned market as an `om strategy`, armed with `om strategy resume`, verified under the running daemon; executes on the Polymarket CLOB or Hyperliquid). Read when the user wants to wire an event/news or metric signal to automated trading, asks how a strategy runs, or asks why one is not trading.
- `schedules.md`: wall-clock delivery via `om schedule` (chart screenshots on a cron today; digest cadences live in their own funnels). Read when the user wants something delivered at a set time, asks what is scheduled or when it fires next, or asks why a scheduled delivery stopped (`om schedule show` / `events` / `stats`, stand-down recovery).
- `rooms-docs.md` — the living-docs layer of OM Rooms chat: Markdown and Excalidraw Canvas files, topic-scoped discovery, CAS revisions, om://doc pills, and the `doc_*` / `canvas_update` lane verbs. Read when working inside a chat room or topic with files: the user asks what files are here, wants a conversation captured, references an om://doc pill, or asks to edit, draw, rename, file, revert, share, archive, or restrict a doc.
- `secrets.md` — sealed (end-to-end encrypted) chat messages: `/secret`, recipient cards, recovery codes. Read for private/sealed sends or secret recovery.

## Routing

Ask-shape rules — pick the surface before reading any detail file:

- A question about a news event or catalyst ("did X happen?", "what did they say?") → answer from what is already captured (`event_journal_search`, `event_watch_events`; event-watches.md §"Read journals"), plus the odds read (`polymarket_odds`, last-traded) when the subject trades, all in this turn without asking — a new watch covers the future, it is not this turn's answer; nothing captured and no market: say so in one line and offer a watch once.
- "Can I SEE it / show me" price action, a level, structure, or a comparison → open it on the chart now (`chart_create`, scratch and unnamed, for an ad-hoc look; `chart_symbol` only on a chart already on screen; depth in chart-actions.md); to draw, mark, or pin on it → chart-actions-tool-drawing.md.
- "Keep me posted on <subject>" → follow the subject as a news Topic (news.md); author a Fast alert (news.md §"Author a Fast alert") only when no published Topic covers it.
- An unscoped "what's going on / catch me up / what did I miss" → `news_brief` first: `get_last`, then `generate` when that edition is stale or `not_found` (news.md §"The daily brief"); `event_watch_events` / `event_journal_search` drill down after it and stand in when it returns nothing, as does `alert_events` on a home whose watches all shadow alerts. A systems audit belongs to an explicit status question.
- One metric across many symbols → a single `metric_screen` (metrics.md §"Scan"), never per-symbol `metric_get`s.
- Inside a chat room: "what happened in #x / catch me up" → `rooms_changes_since` (or `room_history` to page a window); "find what someone said" → `room_message_search` (one room) or `rooms_search_messages` (across rooms); file and doc work (what files are here, capture this to a doc, edit or share one) → the rooms doc verbs (rooms-docs.md §"The verbs").
- "Do X when Y happens" → an alert with an `on_fire.execute` block (alerts.md), single-shot unless the user wants every occurrence (`fire_mode: "recurring"`); a standing signal-driven position to manage → a signal/strategy pair (strategy.md §"When to use this skill vs `openmarket-alerts`"), not a hand-rolled script alert.

<!-- chat-context: omit-start -->
## Channels

`om setup <name>` pairs an outbound notification channel, and `/setup` in a terminal `om chat` runs that same guided connect inline — from a chat surface, name `/setup` first and the terminal verb second. Routing is **materialized** — an alert stores exactly its top-level `channels: string[]` (channel ids), and there is no read-time fan-out. A create with no `channels[]` is **seeded** to the configured **default channel** (set via `om setup default <name>`), or the lone channel when only one is configured; with several channels and no default set the create is **refused** (pass `--channel <name>` or set a default: `om setup default <name>`); with no channels configured it is card-only (no push, no agent take). Pairing the very first channel also routes any still-card-only alerts and watches onto it, so specs authored before a channel existed get a real destination (a later second channel re-homes nothing).

| Channel | Setup |
| --- | --- |
| `telegram` | `om setup telegram --token <bot-token> --chat-id <id>` (or interactive) |
| `discord` | `om setup discord --webhook-url <url>` (or interactive) |
| `slack` | `om setup slack --webhook-url <url>` (or interactive) |
| `webhook` | `om setup webhook --webhook-url <url> [--bearer-token <token>]` (generic JSON POST to any http(s) endpoint; alert fires carry a structured `alert` block) |

Interactive mode (no credential flags) prompts for the channel name first (defaulting to the adapter id, e.g. `telegram` / `discord`) before collecting credentials — same as `om init`. Pass `--name <name>` to skip that prompt and supply the name on the command line. Pass `--default` to mark the new channel as the default for alerts without an explicit `channels[]` field.

Default-channel management: `om setup default` (show current), `om setup default <name>` (promote), `om setup default --clear` (drop the marker; with several channels a no-`channels[]` create is then refused until you set a default or name channels). `om setup list` shows a `DEFAULT` column with `*` next to the default row.

Per-channel view and routing: `om channel <name>` (name, id, or `default`) shows one channel's bound conversation thread and every alert and watch routed to it, and takes `--add <alert-id|watch-slug>` / `--remove <alert-id|watch-slug>` to route a spec on or off it, `--rename <new-name>` to rename the channel (its routes follow), and `--format json`. It flags a spec whose fire would post plainly here (this channel past the wake cap) and footnotes any other channel that shares the same chat.

System lifecycle messages (runner started / stopping, alert paused / resumed) always fan out to every configured channel — the default-channel preference only applies to alert fires.

`om setup openclaw` is a separate flow — it installs the OM skill into a local OpenClaw and registers OpenClaw's webhook as a passthrough target (raw receipt JSON, no rendering by the runner).

## The runner

`om service install` registers a launchd (macOS) or systemd `--user` (Linux) unit that runs the tick loop in the background. It re-reads `~/.openmarket/alerts/*.json` each tick (default 10s, override via `--interval-ms`), evaluates every alert, fires whenever the condition is TRUE (recurring mode) or once-and-terminates (once mode), and dispatches to configured channels via direct HTTPS POST. Edge semantics live in the leaf operator (`crosses_above` / `crosses_below`) for typed conditions, and in the script body for custom-script conditions — the runner itself is dumb. Lifecycle: `om service [start|stop|restart|status|logs|uninstall]`. Foreground mode (`om run`, no `--service`) is the dev-loop variant — same evaluator, no daemonization. Native Windows uses foreground only (no Task Scheduler integration yet).

The per-tick log line in `runner.log` has the form `[tick] scanned=[ids] evaluated=[ids] fired=[ids] errors=[ids]`. Each bracketed list is the set of alert IDs in that bucket, not a numeric tuple — `scanned=[2,1]` means alerts 2 and 1 were scanned, `fired=[2]` means alert 2 fired this tick.

Whenever the runner is up — foreground `om run` or background `om service install` — it also exposes a local HTTP surface on `:31337`: `/healthz`, `/rpc/v1/alert/*` (CRUD over HTTP), `/events/v1` (SSE stream — `alert_fired`, `event_watch_fired`, `channel_delivered`, `channel_failed`, `tick_completed`), `/api/v1/*` (REST proxy to upstream), `/ws/v1/*` (WebSocket proxy). Most `om alert *` CLI commands route through `/rpc/v1/alert/*` when the runner is reachable and fall back to direct filesystem writes when it isn't, so authoring works either way. `om alert watch` is the one command that needs the runner (it consumes `/events/v1`).

## Bundling into the binary

The compiled `om` binary embeds these files via Bun's text-import, so `om skill show [name]` works without the repo on disk.

Every file in the `## Files` index above is text-imported into `OPENMARKET_SKILL.files` by `packages/cli/src/skills/package.ts`, with the rooms deep-dives (`rooms-docs.md`, `secrets.md`) riding its `./package-rooms` plane, which a build without the rooms cluster swaps for an empty one.

`om skill list` enumerates them; `om skill show [name]` prints one to stdout.

Installed copies omit the generated command reference below: with a shell available, `om --help` and `om <command> --help` are the live surface, always current with the installed binary.

<!-- chat-context: omit-end -->
