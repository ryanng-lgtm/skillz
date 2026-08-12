---
name: bump-rc
description: Release a new @openmarket/rooms-client version — pick the bump from what actually changed, run the repo's release script, then update both GUI consumers' pins. Trigger: /bump-rc [version]
---

# bump-rc — release rooms-client and repin its consumers

`@openmarket/rooms-client` lives in `openmarket-internal` and is consumed by two
forks that pin it exactly: `openmarket-chat` (bun) and `openmarket-chat-cloud`
(pnpm). Publishing without repinning leaves both forks on the old version;
repinning without publishing leaves them unresolvable. This skill does the whole
sequence.

**Announce at start:** "Using bump-rc to release rooms-client."

## Hard rules

- **Publishing is irreversible.** A version number can never be reused, even
  after `npm unpublish`. Confirm the version with Ryan before step 4 unless he
  named it in the invocation.
- **Never invent an npm token.** If auth fails, stop and ask — do not try other
  registries, other accounts, or `--force`.
- Commit the version bump via the `/commit` skill, never raw `git commit`.
- No pushing unless Ryan says so; the release script itself does not push.

## Steps

### 1. Read the current state

```bash
cd ~/Documents/GitLab/openmarket-internal
git status --short                       # must be clean; the script refuses otherwise
git branch --show-current                # publish expects main
grep '"version"' packages/rooms-client/package.json
```

Also read the consumers' current pins, so step 6 has a before/after:

```bash
grep '"@openmarket/rooms-client"' ~/Documents/GitLab/openmarket-chat/package.json \
  ~/Documents/GitLab/openmarket-chat-cloud/package.json
```

### 2. Decide the bump from what actually changed

List what landed in the package since the last version bump:

```bash
git log --oneline "$(git log -1 --format=%H --grep='chore(rooms-client):' -- packages/rooms-client/package.json)"..HEAD -- packages/rooms-client/
```

Then pick by the strongest change present:

| Change | Bump |
|---|---|
| A removed or renamed export; a changed function signature, return shape, or wire type that existing callers must adapt to | **major** |
| A new module or export entry, a new optional field or parameter, new behavior behind a default that preserves today's semantics | **minor** |
| Bug fix or internal change with no surface movement | patch |

New modules with new `exports` entries are additive — that is a **minor**, not a
major. When a change looks major, say which caller breaks and how before
proposing the number.

State the proposed version and the one-line reason, then confirm with Ryan
unless he already named it.

### 3. Prepare (optional but preferred)

`prepare` writes the version and runs the package gates without committing,
tagging, or publishing — it fails loudly if the gates are red:

```bash
bun run rooms-client:release prepare 0.X.0
```

Then commit the version change (stage `packages/rooms-client/package.json`, plus
a CHANGELOG entry if the repo's recent releases carry one — check
`git log --oneline -5 -- CHANGELOG.md`), using the `/commit` skill with the
repo's convention: `chore(rooms-client): 0.X.0 (<what it adds>)`.

### 4. Publish

```bash
bun run rooms-client:release publish 0.X.0
```

The script asserts a clean worktree on `main`, that `package.json` already reads
the target version, runs `npm whoami`, runs the package gates, publishes, then
polls the registry until the version is readable (about a minute).

### 5. If auth fails

`npm whoami` failing, `ENEEDAUTH`, `E401`, or `E403` all mean the same thing:
the token is missing, expired, or lacks publish rights on the `@openmarket`
scope. Stop and ask Ryan for a token — quote the exact npm error, and offer him
the two ways to supply it:

- `npm login --scope=@openmarket` in his own terminal (interactive; the `!`
  prefix runs it in-session), or
- an automation token exported as `NPM_TOKEN` / written to `~/.npmrc`.

Never print a token back, never write one into a repo file, and never retry
publishing until he confirms.

If the script instead reports the version is already published, **do not bump
past it silently** — the release may have half-landed. Verify with
`npm view @openmarket/rooms-client@0.X.0 version` and report what you find.

### 6. Update both GUI consumers

Once npm reports the new version:

```bash
cd ~/Documents/GitLab/openmarket-chat
bun add @openmarket/rooms-client@0.X.0 --exact

cd ~/Documents/GitLab/openmarket-chat-cloud
pnpm add @openmarket/rooms-client@0.X.0 --save-exact
```

Two traps, both real:

- `openmarket-chat` may have rooms-client **symlinked** to a local monorepo
  checkout (`tools/link-rooms-client.ts`). `bun add` replaces the link. Check
  `readlink node_modules/@openmarket/rooms-client` first; if it was linked and
  the session still needs the link, relink after the pin lands:
  `bun tools/link-rooms-client.ts --unlink && OM_REPO=<checkout> bun tools/link-rooms-client.ts`.
- Pre-public-launch, the registry may not serve the package at all. If the add
  fails to resolve, report it and fall back to the local tarball flow rather
  than editing the pin by hand:
  `cd <monorepo>/packages/rooms-client && bun run build && npm pack`, then
  install that tarball in the consumer.

### 7. Verify and report

```bash
grep '"@openmarket/rooms-client"' ~/Documents/GitLab/openmarket-chat/package.json \
  ~/Documents/GitLab/openmarket-chat-cloud/package.json
cd ~/Documents/GitLab/openmarket-chat && bun run typecheck
cd ~/Documents/GitLab/openmarket-chat-cloud && pnpm run typecheck
```

Commit each consumer's pin change (`package.json` + its lockfile) via the
`/commit` skill: `chore: rooms-client 0.X.0`.

Report: the version published, why that bump, both consumer pins before/after,
typecheck results, and anything left for Ryan (a relink, an unpushed commit, a
failed resolve).
