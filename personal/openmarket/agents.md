---
name: openmarket-agents
description: Create an agent from one sentence, put it on a clock, and reach it afterwards. An agent is an installed helper with one job, the few tools it was granted and three sample asks; it answers when mentioned in a room, handed an ask or run by a watch, and its room replies wait for the owner's OK. Read when the user wants an agent made ("make me an agent that ...", "an agent that runs daily ..."), asks which agents they have, or wants one handed an ask.
user-invocable: false
allowed-tools:
  - Bash(om *)
  - Read
  - AskUserQuestion
---

# om agents

An agent is an installed helper with one job: it calls only the tools it was granted and answers when mentioned, handed an ask or run by a watch.

### Guardrails

- An agent calls only its granted `tools`: reads, plus web search (a sealed number of searches a run) and om's browser when granted. It cannot write, post without the owner's OK or trade. Say so.
- A clock or a condition is a watch, never instructions; when an agent was asked for, build the agent first, then the watch that names it (§"Clocks and conditions").
- `agent_list` before every create; never reuse a name.
- The card is the ask: never ask "OK to create?" in prose first.

### Routing

- "Make me an agent that ..." → §"Build an agent", tools from §"Pick tools", text from §"Write the instructions".
- A new agent asked for, even on a clock or a condition ("an agent that runs daily ...") → §"Build an agent", then §"Clocks and conditions".
- A clock or a condition with no agent asked for ("tell me when ...", "every morning ...", "a watch, not an agent") → `watch_kit` (watch.md §"Build from a description").
- An agent that trades → one line: agents never trade; a trade rule is a watch with a money step, armed at the terminal.
- "The agent" or "ask the agent" with no name is om itself, not a new agent.
- An installed agent's name, "what agents do I have", "ask <agent> to ..." → §"Reach an installed agent"; on a clock, §"Clocks and conditions" with no new agent.
- "Publish my agent", "put it on the registry" → §"Publish an agent".
- A create refused → §"Refusals".

### Reply shape

After the install: the agent's name, the fit line (`Fit: 3/3 asks pass`), its sample ask with the answer, and how to reach it (`@name` in a room, or ask om to hand it something).

## Build an agent

One `agent_create` call from the user's sentence, built to the rubric: one job, one voice, explicit anti-jobs, no leftover tools.

- **One job.** `job` is one line; a second job is a second agent.
- **One voice.** One line of `instructions` says how it talks: `Answer in one plain line, then the source.`
- **Explicit anti-jobs.** `antiJobs` names what a user might expect it to do that it must not: `post without your OK`, `give trade advice`, `answer outside #macro`.
- **No leftover tools.** The fewest tools every sample ask needs (§"Pick tools").

1. `agent_list`, then pick a `name` not on it: lowercase `a-z`, `0-9` and `-`, never `om`, short and drawn from the job (`macro-checker`).
2. Ask up to three preference questions in ONE message: its voice, what it must never do, where it lives (the room it answers in). Skip any the sentence already answers; ask none when it answers all three. Never a second round: fill what is left from the sentence.
3. Fill the fields below, fit the draft (§"Fit before the card"), then call `agent_create` with the last draft fitted. The card shows the job, what it won't do, the tools, the fit, the brain and that replies are held; the yes installs the agent in shadow mode and runs the first sample ask as a try.

| Field | What goes in |
| --- | --- |
| `name` | step 1 |
| `job` | one line, what it does: `fact-checks claims in #macro against the research library` |
| `antiJobs` | 1 to 5 lines, what it never does; the card shows them as `Won't` |
| `whenToUse` | one or more short lines naming the asks it takes |
| `tools` | 1 to 8 names from §"Pick tools" |
| `instructions` | the agent's prompt with its voice line; with the anti-jobs, up to 4096 bytes (§"Write the instructions") |
| `sampleAsks` | exactly 3, one line each; the first runs as the try |
| `knowledge` | optional: standing facts the job needs (a glossary, the house sources) |
| `template` | optional start: `explain`, `fact-check`, `argue`, `debugger`, `feature` or `blank` |
| `checks` | optional reply checks (§"Write the instructions") |
| `work` | coding agents only: `{projectId, brain}`, brain `claude` or `codex` |
| `listing` | optional registry card: `displayName` (40), one-line `tagline` (200), up to 8 `tags`, one emoji `avatar`, up to 5 `jobs` |

A coding agent ("an agent that fixes failing tests in <project>") takes `work`, template `debugger` (finds and fixes a bug) or `feature` (builds a change), reads its project's repo on top of its tools, and carries no `checks`. No project in the sentence: ask for it in the same message.

```json
{
  "name": "macro-checker",
  "job": "fact-checks claims in #macro against the research library",
  "antiJobs": ["give trade advice", "answer outside #macro", "guess when the library is silent"],
  "whenToUse": ["someone in #macro states a number or a record as fact"],
  "tools": ["room_thread", "doc_search", "doc_read"],
  "template": "fact-check",
  "instructions": "You fact-check claims posted in #macro. Answer in one plain line, then the source. Read the claim's thread, then search the library for the source. Answer true, false or unverified, then the source link. When the library holds nothing on it, say unverified and what would settle it.",
  "sampleAsks": ["is BTC ETF outflow at a record?", "did the Fed cut in September?", "check the last claim in #macro"],
  "checks": ["cites-source", "no-bare-ack"]
}
```

## Pick tools

Call `agent_tools` with the job's words, then name the fewest tools every sample ask needs, at most 8; a tool no sample ask calls is a leftover.

- `query` takes words from the job and the sample asks (`funding btc price`); each row is a tool's name, pitch and weight, what it costs the agent on every step.
- Walk the three sample asks: name the tool each one calls, nothing more. Of two tools that answer the same ask, take the lighter.
- A refused name comes back with the nearest names it may hold; pick from those.
- `web_research` is grantable: set `searchesPerRun` (default 3, at most 16). The card's `Web` row names the cap and, beside a room, doc or browser read, that a search quoting what the run read is refused.
- `watch_roster` answers "which watches exist", one slim row per watch.

Nothing grants a write, a trade, the owner's accounts or positions. A job that needs one: say in one line what the agent cannot reach, then offer the nearest that works (a watch for alerts and runs, `orders.md` for a trade now).

## Fit before the card

Run `agent_fit` on the draft before `agent_create`: all three sample asks run with only its tools, and each reports what it called and what it was refused.

- Drop every tool in `unusedTools`: no ask called it.
- A name in `refusedTools` is a tool an ask reached for: add it when `agent_tools` lists it, else rewrite that ask.
- An ask with `passed: false`: rewrite the ask, or the instructions its failed check exposed.
- Changed the draft: `agent_fit` again. At most two fit rounds, then `agent_create` with the last draft fitted.
- The card's `Fit` row is the daemon's run for that exact draft; a change after the fit reads `not run for this draft`.
- Coding agents have no fit: go straight to `agent_create`.

## Write the instructions

How to write the agent's prompt and voice, its anti-jobs, three sample asks, knowledge and checks; read before filling those fields.

- `instructions` speak to the agent in the second person ("You fact-check ..."), scoped to its job: one voice line, what to read first, what to answer, what to say when it cannot tell, and the answer's shape. No schedule, no trigger, no promise of a write.
- `antiJobs` are short and concrete, one line each; they close the instructions as a `You never:` list, so never repeat them in `instructions`.
- `sampleAsks` are three asks a user would really send, concrete and different from each other: the common case first (it runs as the try), then a harder one, then a different angle on the job.
- `knowledge` holds what holds for every ask; anything that changes belongs in a room or the library the agent reads.
- `checks` are tests a reply must pass before the owner sees it. Pick the ones the job implies:

| Check | The reply |
| --- | --- |
| `cites-source` | carries an `om://msg` or `om://doc` link, or says unverified |
| `grounded-links` | links only to what it read in this run |
| `no-bare-ack` | is more than a bare "ok" or "got it" |
| `no-narrative-mention` | tags only people (`@handle`) and roles (`om://role/<id>`) the run saw |
| `stays-in-thread` | lands in the thread it was asked in |
| `max-chars:<n>` | is at most `n` characters |

## Clocks and conditions

A clock or a condition is a watch; for an agent asked for, build the agent first, then the watch whose `ai` step names it. Never write a schedule into instructions.

1. An agent asked for: `agent_list`, then `agent_create` (§"Build an agent"); its card is the ask.
2. After the yes, `watch_kit` with the person's whole request. The composer hands the clock off as a timer, and the `watch_create` takes an `ai` step `{label, agent: "<name>", ask?}` naming the agent (watch.md §"AI step").
3. The arm card is the consent for every run; each run's answer goes to the watch's destination, not held.

- An installed agent on a clock ("have macro-checker run daily"): no new agent; step 2 with its name.
- No agent asked for ("every morning summarize #macro", "tell me when funding flips"): `watch_kit` (watch.md §"Build from a description").

## Reach an installed agent

List what is installed, hand an agent an ask, mention it in a room, or wake it from a watch.

- `agent_list`: each agent's brain, model, state and runs today; with `agent`, its fields, what it may reach and the watches that run it.
- `agent_run` hands an installed agent one ask in full; its answer comes back here.
- When the ask depends on something om read (a page, a doc, a thread, a file), attach verbatim excerpts in `context`, each item opening with one line naming its source.
- When the ask continues an earlier exchange with the same agent, attach that exchange as one `context` item.
- A result proposal with action `om_request` names something the agent could not read. Fetch it with your own tool, under that tool's card, then hand the agent the same ask again with the material and the earlier exchange in `context`.
- When you cannot fetch it, tell the person what the agent asked for.
- `@name` in a room message asks it there; held replies wait as drafts until the owner posts them.
- From a watch: §"Clocks and conditions".

## Publish an agent

`agent_publish` puts an agent made here on the registry as `@<username>/<name>`, with its card.

- `dry_run: true` first: it returns the coordinate, the next version and the listing, uploading nothing.
- `listing` changes the card for this publish only; the agent's own folder never changes.
- The real call raises one card: Package, Version, Name, Tagline, Tags, Cover. A first version takes `cover_words` or a file where the home can draw.
- `not_local`: the agent came from elsewhere. `package_deleted`: pick a new name.

## Refusals

What an `agent_create` refusal means and its one fix.

| Refusal | Fix |
| --- | --- |
| `agents_unavailable` | agents are off on this home: say so, and offer a watch when the job fits one |
| `name_taken` | pick a name not on the listed installed names; never overwrite one |
| `bad_request` | the message names the field: fix it and call once more |

A sample whose checks failed is not a refused create: the agent is installed. Reply with the answer and the failed check.
