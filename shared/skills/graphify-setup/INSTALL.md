# graphify Local Setup — Agent Runbook (INSTALL.md)

**Audience: a coding agent** (Claude Code or similar) executing this autonomously. Self-contained and repo-agnostic — nothing here assumes a specific project, language, or hook manager; repo-specific decisions come from survey steps at run time. Read the whole file, then start at Step 0.

All CLI behavior, flags, file formats, and timings stated below were verified against graphify (package `graphifyy`) and real graph output on 2026-07-27. Treat them as fact; re-verify only if a command's output contradicts them.

## Modes

Step 0 picks one. Every later step branches on it.

- **SINGLE** — one repo, one graph at its root. The default.
- **CROSS** — N sibling repos under a workspace directory, extracted separately, then merged into one cross-repo graph. Pick this when questions span repos (e.g. a frontend plus the landing-page repo that documents it).

## Goal state (all verifiable in Step 8)

1. graphify installed and importable
2. `.graphifyignore` scoping scans — junk and media excluded; nested repos excluded in SINGLE, targeted in CROSS
3. Nothing graphify-related visible in `git status`, via `.git/info/exclude`
4. post-commit + post-checkout hooks auto-rebuilding each repo's code graph
5. SINGLE: fresh `graphify-out/graph.json` at the repo root. CROSS: fresh per-repo graphs, a merged graph at the workspace root, and a wrapper keeping the merge current.

## Invariants — hold these through every step

- Run every command from the repo root (SINGLE) or the workspace root (CROSS), unless a step says otherwise.
- Every step ends with a VERIFY gate. A gate fails → stop, diagnose, report. Do not continue.
- All steps are idempotent. Re-running the whole file is safe.
- graphify entries go in `.git/info/exclude`, never the tracked `.gitignore`. Commit nothing this runbook creates.
- **CROSS: `MERGED_OUT` never lives inside a repo that has hooks installed.** That repo's post-commit hook runs `graphify update .`, rebuilds the file from that repo alone, and every other repo's nodes vanish — Step 7's `--force` semantics (allow node-count shrink) let it land without complaint. Step 0 gates this; Step 6 re-checks it.
- CROSS: `query`, `explain`, and `path` default to `./graphify-out/graph.json`. Pass `--graph "$MERGED_OUT"` on every read, or you read the wrong graph or none.

---

## Step 0 — Mode and preconditions

Decide SINGLE vs CROSS. Ask the user if it is not already stated; do not infer CROSS merely because sibling directories exist.

**SINGLE:**

```bash
cd "$(git rev-parse --show-toplevel)" || { echo "NOT A GIT REPO — abort"; exit 1; }
git config core.hooksPath   # record output; ".husky/_" means husky-managed hooks
```

Record `REPOS` (this one path) and `HOOKS_PATH` (empty = plain git hooks; `.husky/_` = husky).

**CROSS:**

**Locate the workspace root first — it is not your cwd.** This file is often dropped *inside* one of the target repos, so the directory you start in is a repo, not the workspace. The workspace root is the directory that *contains* the repos as children:

```bash
# If cwd is inside a git repo, the workspace root is that repo's PARENT:
git rev-parse --show-toplevel 2>/dev/null && echo "cwd is a repo — workspace root is its parent"
cd "$(dirname "$(git rev-parse --show-toplevel)")" 2>/dev/null || cd <workspace-root>
pwd   # confirm with the user before continuing
```

Enumerating from inside a repo returns nothing and leaves `REPOS` empty, which poisons every later step — the gate below exists to catch exactly that.

```bash
# Enumerate candidate repos one level down. Strip the trailing slash: a merged graph's
# `repo` attribute is the bare directory name, and Step 8's gates compare against it.
for d in */; do [ -d "$d/.git" ] && echo "${d%/}"; done
```

Confirm with the user which of those belong in the graph. `REPOS` is that confirmed list, not the full enumeration.

**VERIFY before continuing — `REPOS` must hold at least two repos:**

```bash
set -- $REPOS
[ "$#" -ge 2 ] && echo "PASS: $# repos" || echo "FAIL: only $# repo(s) — wrong workspace root, or use SINGLE mode"
```

Zero or one repo means you are standing in the wrong directory, or CROSS is the wrong mode. Stop and resolve it; do not continue with an empty `REPOS`. Record `HOOKS_PATH` **per repo** — they can differ, one repo on husky and another on plain hooks:

```bash
for r in $REPOS; do echo -n "$r "; (cd "$r" && git config core.hooksPath || echo "(plain)"); done
```

Record `MERGED_OUT`, where the cross-repo graph lands. Default `<workspace-root>/graphify-out/graph.json`.

**Shell gotcha — CROSS blocks expand `$REPOS` and rely on POSIX word splitting, which zsh does not do.** Under zsh, `for r in $REPOS` iterates once with the whole string: a two-repo setup silently processes a repo named `"repo1 repo2"` and Step 8's gates report a false FAIL. Pick one before running any CROSS block, and say which:

```bash
setopt shwordsplit          # zsh only, current shell only
```

```bash
bash -lc '<block>'          # or run CROSS blocks under bash
```

bash is unaffected. The Step 6 wrapper is `#!/bin/sh`, so it splits correctly whatever your interactive shell is.

**VERIFY (CROSS):** the workspace root is not a git repo, or is one that contains no repo from `REPOS` as a subdirectory. Otherwise `MERGED_OUT` sits inside a hooked repo — pick a location outside every repo in `REPOS` and record that instead.

## Step 1 — Install uv + graphify

Skip pieces already present.

```bash
command -v uv >/dev/null || brew install uv || curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install graphifyy   # package is "graphifyy", command is "graphify"; no-op if current
```

**VERIFY:** `graphify --help` prints a usage block. If `graphify` is not on PATH, resolve the interpreter via `uv tool run graphifyy python -c "import sys; print(sys.executable)"` and use it with `-m graphify` for every later command.

## Step 2 — Author `.graphifyignore` before any scan

**When `.graphifyignore` exists, graphify uses it INSTEAD of `.gitignore` — the two are not merged.** Every scan-relevant `.gitignore` rule must be duplicated here. Builtins already skip: `node_modules`, `.git`, `dist`, `build`, `out`, `target`, `coverage`, `__snapshots__`, `.next`/`.nuxt`/`.turbo`, lockfiles, `graphify-out`.

**CROSS: one `.graphifyignore` per repo, at that repo's root.** The scan unit is the repo, so a workspace-root file does nothing for `graphify extract ./repo/`. Run this whole step once per repo in `REPOS`, from inside that repo.

Survey first — this step needs judgment:

```bash
# 1. Nested repo clones:
find . -maxdepth 2 -name .git -not -path ./.git | sed 's|/.git||'
# 2. Video/audio (triggers Whisper transcription — expensive):
find . -not -path './node_modules/*' -not -path './.git/*' \( -name '*.mp4' -o -name '*.mp3' -o -name '*.mov' -o -name '*.wav' \) | head
# 3. Untracked junk dirs:
git status --porcelain | grep '^??'
# 4. Scan-irrelevant .gitignore rules to mirror (build output, logs, scratch dirs):
grep -v '^#' .gitignore | grep -v '^$'
```

**Survey #1 reads differently per mode:**

- **SINGLE** — every nested repo is graph poison; its symbols duplicate against the host repo's. Exclude all of them.
- **CROSS** — a nested repo that is in `REPOS` is a *target*, not an exclude: it gets its own extract pass in Step 4, and excluding it here drops it from the graph entirely. Exclude only nested repos **not** in `REPOS` — vendored dependencies, scratch checkouts, throwaway clones. In the sibling layout this survey usually returns empty inside each repo; a hit means a genuinely nested clone worth inspecting.

Write `.graphifyignore` at the repo root (gitignore syntax). **Adapt the ADAPT-marked sections to the survey results:**

```gitignore
# graphify scan excludes. Replaces .gitignore for graphify — mirror rules here.

# ADAPT: nested clones / scratch checkouts from survey #1 and #3.
# SINGLE: every survey-#1 hit. CROSS: only hits NOT in REPOS.
# <clone-dir>/

# ADAPT: build/tooling output from survey #4 not covered by builtins
logs/
*.log
*.tsbuildinfo

# this runbook, if it was copied into the repo. Markdown IS extracted — leaving it
# in puts "SINGLE", "CROSS", "MERGED_OUT" and the step titles into the graph as
# concept nodes, so install instructions surface as if they were architecture.
INSTALL.md

# editor / agent state
.claude/
.vscode/
.idea/
.husky/

# secrets
.env
.env.*

# media + generated bundles: no graph value, images/video cost tokens
# ADAPT: asset dirs, locale/i18n bundles, large fixtures found in surveys #2/#4
*.png
*.jpg
*.jpeg
*.gif
*.ico
*.svg
*.mp4
*.mp3
*.woff
*.woff2
```

**VERIFY:** file exists; every survey-#2 video/audio location is covered by a dir rule or glob; and for survey #1 — SINGLE: every nested clone appears. CROSS: every nested clone **not** in `REPOS` appears, and no path belonging to a repo in `REPOS` appears. CROSS repeats this gate per repo before moving on.

## Step 3 — Hide everything via `.git/info/exclude`

`.git/info/exclude` is per-repo. **CROSS: run this once inside each repo in `REPOS`.**

Idempotent append, guarded:

```bash
grep -q '^# graphify — local-only' .git/info/exclude 2>/dev/null || cat >> .git/info/exclude <<'EOF'
# graphify — local-only knowledge graph setup
graphify-out/
.graphifyignore
.husky/post-commit
.husky/post-checkout
INSTALL.md
EOF
```

The `.husky/` lines are harmless in repos without husky. The `INSTALL.md` line hides this runbook from `git status` in whichever repo holds it; it is a no-op in the others, so leaving it in every repo is fine. (Keeping it out of the *graph* is separate — that is the `.graphifyignore` entry from Step 2.) If Step 5 installs hooks elsewhere (custom `core.hooksPath`), add those paths then.

If the tracked `.gitignore` holds graphify patterns from an older setup, remove them and leave the edit uncommitted for the user to review.

**CROSS — the merged graph.** `MERGED_OUT` sits at the workspace root, outside every repo, so no repo's git sees it and no exclude entry can hide it.

- Workspace root is not a git repo (the common case): nothing to do; it is untracked by anything.
- Workspace root *is* a git repo: append `graphify-out/` to **its** `.git/info/exclude` using the same guarded block.

**VERIFY** (per repo in CROSS):

```bash
git check-ignore -v .graphifyignore          # must resolve to .git/info/exclude
git status --porcelain | grep -i graphify    # must print nothing (exit 1)
```

## Step 4 — Build the graph

### SINGLE

- **Inside Claude Code with the graphify skill available:** invoke `/graphify` — full pipeline including LLM semantic extraction of docs. Preferred.
- **Headless / no skill:** code-only graph, no LLM:

```bash
mkdir -p graphify-out
PYTHONHASHSEED=0 graphify update .
```

**VERIFY:** `graphify-out/graph.json` exists; `update` prints `Rebuilt: N nodes, M edges` with N > 0.

### CROSS

Two passes: extract each repo into its own `graphify-out/`, then merge.

**Pass 1 — per repo.** The scan unit is one repo; each ends up with its own `graphify-out/graph.json`.

- **With the graphify skill:** the skill pipeline writes all intermediates to `graphify-out/` **in the current working directory**. Run it once per repo with cwd inside that repo. Running it from the workspace root once per repo clobbers a single shared output dir, and you get one repo's graph wearing every repo's name.
- **Headless / no skill:** run the CLI from the workspace root — `extract` places `graphify-out/` *inside* the scanned path, so there is nothing to clobber:

```bash
for r in $REPOS; do
  PYTHONHASHSEED=0 graphify extract "./$r/"   # → ./$r/graphify-out/graph.json
done
# Add --backend gemini|kimi|claude|openai|deepseek|ollama if the auto-detected key is not the one you want
```

**Pass 2 — merge.** From the workspace root:

```bash
mkdir -p "$(dirname "$MERGED_OUT")"
graphify merge-graphs \
  ./<repo1>/graphify-out/graph.json \
  ./<repo2>/graphify-out/graph.json \
  --out "$MERGED_OUT"
```

**What the merge produces.** Every node gains a `repo` attribute (the repo's directory name), its id is namespaced to `<repo>::<label>`, and the original id is kept as `local_id`. Because ids are namespaced, **the merged graph has no edges crossing repo boundaries** — it is a union of per-repo graphs in one file, not a stitched graph. Cross-repo connections surface as *shared labels*: the same function, package, or concept present in both repos, which a query sees side by side. Step 8 check 6 measures that. Do not hunt for cross-repo edges; there are none by construction.

The merge is a union of already-built graphs — ~0.25s for two mid-size repos (1,880 nodes). Cheap enough to re-run on every commit, which is what Step 6 does.

**Graph file format** (needed to edit any script in this runbook): graphify writes networkx node-link JSON. Edges live under `g['links']`, **not** `g['edges']`, keyed `source`/`target`. Merged nodes carry `repo`, `local_id`, and the namespaced `id`.

**VERIFY:**

```bash
# 1. every repo produced a non-empty graph
for r in $REPOS; do echo -n "$r: "; python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['nodes']),'nodes')" "./$r/graphify-out/graph.json"; done
# 2. merged graph exists and every repo is represented
python3 -c "
import json,collections,sys
g=json.load(open(sys.argv[1]))
c=collections.Counter(n.get('repo','<none>') for n in g['nodes'])
print(c)
" "$MERGED_OUT"
```

Gate: check #2 lists every repo in `REPOS` with a count > 0. A repo missing or at zero was excluded by its own `.graphifyignore` (re-read Step 2's CROSS rule) or its extract pass failed. A `<none>` bucket means origins were not tagged — the file was produced by something other than `merge-graphs`.

## Step 5 — Install auto-rebuild hooks

Hooks are per-repo. **CROSS: run this once inside each repo in `REPOS`.**

```bash
graphify hook install
graphify hook status   # expect: post-commit: installed / post-checkout: installed
```

The installer is husky-aware: with `core.hooksPath=.husky/_` it writes `.husky/post-commit` and `.husky/post-checkout` (user level, not the `_` shim dir). It appends between markers when a hook file already exists.

Hook behavior: post-commit re-extracts only committed-changed code files, runs detached so the commit returns instantly, and skips during rebase/merge/cherry-pick. post-checkout does a full code rebuild on branch switch. Bypass once with `GRAPHIFY_SKIP_HOOK=1`. Hooks are AST-only — doc changes need a manual `/graphify --update`.

**VERIFY:** hook files exist at the location matching that repo's `HOOKS_PATH` from Step 0 — `.husky/` when husky, else `.git/hooks/`. If husky is active but the files landed in `.git/hooks/`, they are dead code: report the mismatch. If hooks landed anywhere not covered by Step 3's exclude block (custom hooksPath), add those paths to `.git/info/exclude` now.

## Step 6 — CROSS only: keep the merged graph current

Install this by default, not on request. Skip the entire step in SINGLE.

A hook rebuilds **only its own repo's** `graphify-out/graph.json`. Nothing re-runs `merge-graphs`, so out of the box `MERGED_OUT` holds the pre-commit picture after any commit in any repo, and nothing warns you. The wrapper below fixes that. Manual fallback is Pass 2 of Step 4.

**Design constraint:** graphify's post-commit hook spawns its rebuild detached (`Popen(start_new_session=True)`). A `merge-graphs` line appended straight after it runs *before* the per-repo graph is rebuilt and merges pre-commit data. The wrapper waits until the repo's `graph.json` mtime reaches the commit timestamp.

Write `<workspace-root>/graphify-remerge.sh`, filling in `WORKSPACE` and `REPOS`:

```sh
#!/bin/sh
# Refresh the cross-repo merged graph after a per-repo graphify rebuild.
# Called from each repo's post-commit/post-checkout hook with the repo name as $1.
set -eu

WORKSPACE="<workspace-root>"          # absolute path
REPOS="<repo1> <repo2>"               # directory names under WORKSPACE
MERGED_OUT="$WORKSPACE/graphify-out/graph.json"
TRIGGER="${1:-}"

mtime() {  # BSD (macOS) and GNU stat
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# Wait for the detached rebuild to land: the repo's graph.json must be at least
# as new as the commit that triggered us. Bounded, so a failed rebuild cannot hang.
if [ -n "$TRIGGER" ]; then
  GRAPH="$WORKSPACE/$TRIGGER/graphify-out/graph.json"
  WANT=$(git -C "$WORKSPACE/$TRIGGER" log -1 --format=%ct 2>/dev/null || echo 0)
  i=0
  while [ "$i" -lt 180 ]; do
    [ "$(mtime "$GRAPH")" -ge "$WANT" ] && break
    sleep 1
    i=$((i + 1))
  done
  [ "$i" -ge 180 ] && echo "[remerge] timed out waiting on $TRIGGER; merging anyway"
fi

set --
for r in $REPOS; do set -- "$@" "$WORKSPACE/$r/graphify-out/graph.json"; done
mkdir -p "$(dirname "$MERGED_OUT")"
graphify merge-graphs "$@" --out "$MERGED_OUT"
```

```bash
chmod +x <workspace-root>/graphify-remerge.sh
```

Append this to **each repo's** `post-commit` and `post-checkout`, after the `# graphify-hook-end` marker. Guard on `graphify-remerge-start` so it stays idempotent:

```sh
# graphify-remerge-start
( sh "<workspace-root>/graphify-remerge.sh" "<this-repo-name>" \
    >> "$HOME/.cache/graphify-remerge.log" 2>&1 & ) >/dev/null 2>&1
# graphify-remerge-end
```

`( … & )` keeps the commit instant — the waiter runs detached, like graphify's own rebuild. Simultaneous commits in two repos are safe: each wrapper merges the full `REPOS` set, so the later writer wins with equally complete data.

The wrapper lives at the workspace root, outside every repo. If your layout puts it inside a repo, add it to that repo's Step 3 exclude block — and re-check the invariant that `MERGED_OUT` is not inside a hooked repo.

**VERIFY:**

```bash
# 1. runs standalone and produces a merged graph
sh <workspace-root>/graphify-remerge.sh && echo PASS
# 2. hook wiring present in every repo
for r in $REPOS; do echo -n "$r: "; grep -l graphify-remerge "$r/.git/hooks/post-commit" "$r/.husky/post-commit" 2>/dev/null || echo MISSING; done
# 3. end-to-end: commit a trivial change in one repo, then confirm the merged
#    graph's mtime advances past the commit (allow the rebuild ~10-60s)
tail -5 "$HOME/.cache/graphify-remerge.log"
```

## Step 7 — Force-refresh baseline

Only when a graph predates the ignore rules. Fresh builds from Step 4 skip this step.

If `graphify-out/graph.json` existed before Step 2 (pre-existing setup), rebuild it so excluded content drops out:

```bash
rm -f graphify-out/.graphify_chunk_*.json graphify-out/.graphify_chunklist_*.txt \
      graphify-out/.graphify_detect.json graphify-out/.graphify_incremental.json \
      graphify-out/.graphify_uncached.txt graphify-out/.graphify_ast.json   # stale temp artifacts
PYTHONHASHSEED=0 graphify update . --force   # --force: allow node-count shrink from new excludes
```

**CROSS:** run the block inside each repo whose graph predates its `.graphifyignore`, then re-run Step 4 Pass 2 to rebuild `MERGED_OUT` from the refreshed per-repo graphs. Never point `graphify update` or `--force` at `MERGED_OUT` — `update` rebuilds from a single scan path and collapses a merged graph down to one repo.

## Step 8 — Final verification checklist

**Checks 1–4 are per repo.** SINGLE runs them once; CROSS runs them inside each repo in `REPOS`. All must pass:

```bash
# 1. git is clean of graphify
git status --porcelain | grep -iE 'graphify|\.husky/post-' && echo FAIL || echo PASS
# 2. exclude resolves from .git/info/exclude, not .gitignore
git check-ignore -v graphify-out/graph.json .graphifyignore
# 3. see below — the expected result differs by mode
# 4. hooks live
graphify hook status
```

**Check 3 — excluded content contributed zero nodes.** The assertion inverts between modes. Running the SINGLE form against a cross-repo graph fails a correct setup.

```bash
# SINGLE: every survey-#1 dir was excluded, so it contributed nothing
grep -c '<clone-dir>/' graphify-out/graph.json    # expect 0
```

```bash
# CROSS: assert the opposite — each repo in REPOS is PRESENT with nodes > 0,
# and only genuinely-excluded paths are absent. Run at the workspace root.
python3 -c "
import json,collections,sys
g=json.load(open(sys.argv[1]))
c=collections.Counter(n.get('repo','<none>') for n in g['nodes'])
expected=set(sys.argv[2:])
print('counts:',dict(c))
if not expected:
    print('FAIL: REPOS expanded to nothing — empty gate proves nothing.')
    print('      zsh does not word-split; see Step 0. Re-run under bash or with setopt shwordsplit.')
    sys.exit(1)
missing=[r for r in expected if c[r]==0]
print('FAIL missing/empty:',missing) if missing else print('PASS all repos present')
print('FAIL untagged nodes:',c['<none>']) if c['<none>'] else None
" "$MERGED_OUT" $REPOS
# plus, per repo: any path you DID exclude still contributes nothing
grep -c '<excluded-dir>/' "$MERGED_OUT"    # expect 0
```

**Check 5 — graph queryable.** Run at the repo root (SINGLE) or workspace root (CROSS):

```bash
# SINGLE
graphify explain "$(git rev-parse --show-toplevel | xargs basename)" >/dev/null 2>&1 || graphify query "what are the main components?" | head -5
# CROSS
graphify query "what are the main components?" --graph "$MERGED_OUT" | head -5
```

**Check 6 — CROSS only: the merge earned its keep.** Measure shared labels; cross-repo edges are always zero (Step 4), so counting them proves nothing. A merged graph with no shared labels is two unrelated graphs in one file, and cross-repo questions will not resolve.

```bash
python3 -c "
import json,collections,sys
g=json.load(open(sys.argv[1]))
by=collections.defaultdict(set)
for n in g['nodes']: by[n.get('repo')].add(n.get('norm_label') or n['label'])
repos=sorted(by)
for i,a in enumerate(repos):
    for b in repos[i+1:]:
        shared=by[a]&by[b]
        print(f'{a} <-> {b}: {len(shared)} shared labels', sorted(shared)[:8])
" "$MERGED_OUT"
```

Zero shared labels is not automatically a failure — repos with genuinely no common symbols, packages, or concepts show zero. Report the count and a sample either way and let the user judge. Shared generic method names (`.start()`, `.stop()`) are weak evidence; a shared package name or domain type is strong evidence.

## Rollback

**SINGLE** — from the repo root:

```bash
graphify hook uninstall
rm -rf graphify-out .graphifyignore
# then delete the '# graphify — local-only' block from .git/info/exclude
```

**CROSS** — the same per repo, plus the workspace-root artifacts:

```bash
for r in $REPOS; do (cd "$r" && graphify hook uninstall && rm -rf graphify-out .graphifyignore); done
rm -f "$MERGED_OUT" <workspace-root>/graphify-remerge.sh
# then, in each repo, delete the '# graphify — local-only' block from .git/info/exclude
# and delete the graphify-remerge-start/end block from post-commit and post-checkout
```

## Report back to the user

State plainly: which mode was used and why; what was installed and where; the exact `.graphifyignore` exclusions chosen and why, especially nested clones and media; that everything is local-only via `.git/info/exclude`; and graph size (nodes/edges/communities).

Name these limitations every time:

- Hooks are AST-only. Doc changes need a manual `/graphify --update` — per repo in CROSS, and the merged graph inherits it.
- **CROSS:** graphify's own hooks maintain per-repo graphs, not the merged one. Say whether the Step 6 wrapper was installed. If it was, the merged graph refreshes on every commit and branch switch, a few seconds behind the per-repo rebuild it waits on. If it was not, `MERGED_OUT` is a snapshot as of the last manual merge — give the user the `merge-graphs` command and say plainly that nothing warns them when it is stale.
- **CROSS:** the merged graph is a union with namespaced ids, so no edges cross repo boundaries; cross-repo insight comes from shared labels. Report the Step 8 check 6 count so the user knows how much the merge actually connects.
- **CROSS:** every read command needs `--graph "$MERGED_OUT"`.
