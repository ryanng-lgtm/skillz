---
name: be-deploy
description: >-
  Use when a backend MR (tsdb-gateway, tsdb-move, metadata-instrument,
  streamd and the other Go services) has to go from draft to a verified
  deploy, or an ArgoCD app on the Kiyotaka/OpenMarket platform has to be
  synced, checked, watched or rolled back. Trigger: /be-deploy [MR ...]
  [env], "merge and deploy !N", "land this MR on ore", "deploy X", "sync the
  app", "is X deployed", "what tag is running", "roll back X", or any
  OutOfSync/Degraded application question.
---

# be-deploy — from a draft MR to a verified deploy on the BE stack

## Overview

A personal copy of the work `argocd` skill (llm repo), extended for the
backend flow and Ryan's rules. The work skill stays as it is.

**Core principle: a deploy is done only when every app runs the expected image, is healthy, and the change's own check passes.**

## Ryan's rules

These sit on top of the consent gate below.

- Commits, plain pushes, and opening or updating MRs need no OK. Merges,
  force pushes and syncs happen only on Ryan's word in the current request;
  `/syncup` on named MRs counts as his word for their force pushes.
- Prod database reads after a deploy (index checks, watermark reads) need
  his go for that request: one short statement per psql, read-only
  `PGOPTIONS`, never holding IO. Never print credentials.
- Grafana reads use the token in `~/.grafana_token` (never print it), read
  paths only.
- After each rollout step, tell Ryan which step of his checklist to tick, in
  his numbering. Do not edit his message.
- Report times in UTC, links as plain URLs, and no AI watermark on commits
  or MRs.

## Scope

Driving and verifying deployments of ArgoCD-managed applications with the
`argocd` CLI, and the backend path from a draft MR to that deploy
(tsdb-gateway, tsdb-move, metadata-instrument, streamd and the other Go
services). The service's behavior after deploy is trace-debug; glab owns
the MR and pipeline commands; chart or infra changes belong in the
infrastructure repo (read its AGENTS.md first).

## Consent gate

`app sync`, `app rollback`, `glab mr merge`, and anything else that mutates
cluster state or a default branch runs only when the current request
explicitly names that action ("deploy X", "sync it", "roll back", "merge
!N"). A request to sync is not a request to merge, and the reverse. Consent
does not carry forward to later requests. A request that stops short of
naming the mutation ("is the new build up?", "get !N ready") gets inspection
and preparation only: execute up to the gate and report the MR ready to
merge or the app ready to sync — that is the complete, correct outcome, not
an unfinished task. Read-only inspection (list, get, diff, history,
`glab mr view`) is always fine; so is a manifest refresh (`app get
--refresh`), which changes no workload. Never `app delete`: Applications are
generated (see below), and deleting one neither cleans up its workloads nor
stays gone.

## Access

Server `argocd.occ.kiyotaka.dev`, SSO via Dex. Every command needs
`--grpc-web` (the server is behind nginx; without it, calls fail or warn).

Two lifetimes, and conflating them causes surprise. The stored `auth-token` is
a Dex-issued **ID token valid 24h** (read its `exp` claim rather than assuming
— that is Dex's default, and nothing in the infra repo overrides it), while
`argocd login --sso` also stores a **refresh token** the CLI redeems silently
when the ID token expires. So a seat goes weeks without an interactive login
even though its token rotates daily.

The refresh token has **no configured expiry** — `expiry.refreshTokens` is set
nowhere in `aws-occ/ansible/k3s/charts/03-argocd`, so Dex's default (no
time-based expiry) applies. It ends when it is revoked, when you log out, or
when Dex loses it — bundled Dex commonly keeps refresh tokens in memory, so a
Dex pod restart can invalidate every seat at once. An auth error a day or more
after last use means the silent refresh failed; re-run the login rather than
suspecting the platform.

The `30d` often quoted is `users.session.duration` in argocd-cm, which governs
ArgoCD's **own** session tokens (local accounts and API keys), not the Dex
refresh token. Do not use it to reason about SSO lifetimes.

```bash
argocd account get-user-info --grpc-web                # is the session alive
argocd login argocd.occ.kiyotaka.dev --sso --grpc-web  # interactive; the user runs it

# hours left on the current ID token, when a long unattended run depends on it
python3 -c 'import json,base64,re,pathlib,time;t=re.search(r"auth-token:\s*(\S+)",(pathlib.Path.home()/".config/argocd/config").read_text()).group(1);p=t.split(".")[1];p+="="*(-len(p)%4);print(round((json.loads(base64.urlsafe_b64decode(p))["exp"]-time.time())/3600,1),"h")'
```

RBAC maps emails to role patterns (infrastructure repo,
`aws-occ/ansible/k3s/charts/03-argocd/values.yaml`). "permission denied"
means the app is outside your role's patterns, not that it is missing.

The CLI (v3.x) is newer than the server (v2.12); list/get/diff/history are
verified to work across the skew. If some other subcommand misbehaves,
suspect the skew before the platform.

## Deployment model

Nobody writes Application manifests. Reflectful (a GitLab scanner) discovers
repos carrying the `reflectful` topic, reads their `reflectful.yaml` and
`charts/<chart>/values.<env>.yaml`, and feeds an ApplicationSet that
generates the apps.

- Names are `<env>-<namespace>-<release>-<branch>`, e.g.
  `ore-cache-tsdb-gateway-read-dev-main`. ArgoCD project = env:
  `production`, `staging`, `ore`, `cme`. `app list -o name` prints
  `argocd/<name>`; use that full form in commands.
- A chart gets an app in env X only if it has `values.X.yaml`. Open MRs
  automatically become `staging-<ns>-<release>-mr-<iid>` preview apps.
- CI builds `harbor.kiyotaka.dev/kiyotakadev/<service>:<build>-<shortsha>`;
  Reflectful injects it as Helm parameters `image.repository` and
  `image.tag` on the Application. The chart's own `image.tag` is empty on
  purpose — the repo's values files never carry the deployed tag.
- **No auto-sync anywhere.** A new build makes the app OutOfSync; deploying
  is a manual sync.
- Removed charts and closed MRs do not delete their apps or workloads
  (`preserveResourcesOnDeletion`); stale `mr-*` apps are normal, leave them.

## Deploy a new build

```bash
A=argocd/<env>-<ns>-<release>-<branch>

argocd app list --grpc-web -o name | grep <service>   # find the app
argocd app get "$A" --grpc-web                        # sync/health, values files, resources
argocd app get "$A" --grpc-web -o json |
  jq -r '.spec.source.helm.parameters[] | select(.name=="image.tag").value'
argocd app get "$A" --grpc-web --refresh >/dev/null   # re-render from the current revision
argocd app diff "$A" --grpc-web                       # what sync will apply; empty = none
# ---- consent gate ----
argocd app sync "$A" --grpc-web
argocd app wait "$A" --health --timeout 300 --grpc-web
```

Refresh before every diff. Without it, `app diff` and the OutOfSync status
compare against the manifests ArgoCD rendered at its last poll: the diff can
show the previous build's tag as the target although the injected parameter
already names the new one. `.status.sync.revision` after the refresh must be
the commit being deployed.

Before syncing, confirm the injected `image.tag` is the build being
deployed. If CI finished but the parameter still shows the old tag,
Reflectful has not rescanned yet — re-check shortly instead of syncing the
old tag. If it never updates, check the Reflectful server logs (`devops`
namespace on the OCC cluster) — it silently skips a project, branch, or MR
after a generation error.

Verify after: `app get` shows Healthy and the new tag appears under the
app's images (`.status.summary.images` in the JSON). Brief edge 502s during
a sync are expected (see trace-debug).

## From a draft MR to a verified deploy (backend repos)

The stages in order. Each ends with something you can check; stop at the
first stage that does not pass and report it. Stages 4 and 8 are behind the
consent gate. The tsdb-gateway and tsdb-move specifics (shards, the migrate
hook, index checks) are in `references/backend.md`; read it before stage 6
for those two repos.

1. **Read the MR and its project.** `glab api projects/<id>/merge_requests/<iid>`:
   `draft`, `has_conflicts`, `diverged_commits_count`, `head_pipeline.status`,
   `target_branch` (not the default branch means it is stacked on another
   MR), `sha`. Project: `merge_method`, `squash_option`,
   `remove_source_branch_after_merge`, `only_allow_merge_if_pipeline_succeeds`;
   `.../approvals` for `approvals_left`. Done when you can say what blocks the
   merge, if anything.
2. **Bring it up to date.** REQUIRED SUB-SKILL: syncup, when it is installed.
   Otherwise: record `origin/<source>` and, for a stacked MR, `origin/<target>`;
   rebase onto `origin/<target>`; resolve; regenerate generated files from
   their sources instead of hand-merging them (tsdb-gateway:
   `bash scripts/generate-schema.bash` after a `schema.*.yaml` conflict, then
   check that it leaves the tree clean). Two MRs that each change one key of
   the same anchor block in `schema.<plane>.yaml` conflict: keep both keys.
   Push with
   `--force-with-lease=<source>:<recorded sha>`. A stacked MR goes after its
   base: `git rebase --onto origin/<base> <old base sha>`. A force push to an
   existing MR does not always start a pipeline: start one with
   `glab api -X POST projects/<id>/merge_requests/<iid>/pipelines`.
3. **Get the pipeline green, inside the MR's own change.** Read the failed
   job's trace (`glab api projects/<id>/jobs/<job>/trace`, strip ANSI) before
   touching code. Reproduce locally only what the MR touched, and read exit
   codes, not the tail of the output (`cmd | tail` returns tail's status):
   - `GOFLAGS=-mod=mod go build ./... && go vet <pkgs> && go test <pkgs>` when
     the worktree's `vendor/` is out of step with `go.mod`.
   - `golangci-lint run --new-from-rev=origin/<target> <pkgs>` without
     `--fix`: `task lint` passes `--fix` and rewrites files.
     `golangci-lint fmt <file>` applies the formatters (golines, gci) to one
     file.
   - Packages whose tests start Docker containers fail locally without a
     Docker socket. Say which were not run; CI runs them.

   A fix outside the MR's change, or an infrastructure failure (runners,
   registry, image pull), is reported, not patched. Commit a fix as its own
   commit, push, restart the pipeline if none started, wait for a terminal
   state.
4. **Merge** (consent gate: the request names the merge). `glab mr update
   <iid> --ready`, then `glab mr merge <iid> --yes --sha <head sha>`, plus
   `--squash` when the project's `squash_option` is `always` or `default_on`.
   `--sha` refuses the merge if the branch moved since you read it. Record
   the commit that landed: `squash_commit_sha` when squashed, else
   `merge_commit_sha`, else the head sha on a fast-forward. When the source
   branch is removed on merge, GitLab retargets every MR stacked on it to the
   default branch, and those MRs still carry the base's pre-squash commits:
   rebase each onto the default branch (stage 2) before its own merge.
   A merged change reaches an environment with the next sync of its apps,
   whoever runs it. So an MR that is one step of a staged rollout stays a
   draft until its gate has passed, and its merge and sync happen in one
   sitting.
5. **Main pipeline, then the tag.** The expected tag is
   `<pipeline build>-<first 8 chars of the landed commit>`. Wait until every
   target app's injected `image.tag` equals it (see Deploy a new build).
6. **Read what the sync picks up.** For each app, take the running tag from
   `.status.summary.images`, its commit from the tag's suffix, and list
   `git log --first-parent <running>..<landed>`. Flag anything added under
   `migrations/`, any change to the app's chart or its `values.<env>.yaml`,
   and any `schema.*.yaml` change. Commits from other MRs ship too; name
   them in the report. More than one tag in `.status.summary.images` means
   someone synced part of the app: compare per Deployment. Then refresh and
   diff (Deploy a new build) and summarize the diff by resource kind: image
   changes only, or config too.
7. **Plan the order.** Per repo rules in `references/backend.md`. Default:
   one app first when the deploy runs a hook that changes the database
   (migrations, index builds), the rest after it passes; read and write sets
   of one service never in the same step; never `--prune`. A tsdb-move app
   is never synced whole: one Job at a time with `--resource`.
8. **Sync** (consent gate: the request names the sync). Start it with
   `--async` and poll the app (the sync call blocks through hooks, and the
   CLI exits 20 when its own wait times out while the app goes on to
   Synced). Time each hook from the app's `operationState`.
9. **Verify** per app: Healthy, Synced, `.status.summary.images` holds the
   expected tag, and the change's own check passes (the MR or its plan names
   it: an index valid on every chunk, a job's log line, a query result). A
   deploy is not verified on health and image alone when the change has its
   own check.
10. **Report** once: MR → landed commit, per app before → after tag, hook
    durations, the other MRs' commits that shipped, and what is left (stacked
    MRs to rebase, apps deliberately not synced, checks still to run).

## Rollback

```bash
argocd app history "$A" --grpc-web
# ---- consent gate ----
argocd app rollback "$A" <id> --grpc-web
```

The ApplicationSet still owns the spec, so the app will show OutOfSync
against the newest build again — rollback is a stopgap until a fixed build
lands, not a pin.

## App missing entirely

The repo needs the `reflectful` topic and a `reflectful.yaml` (its absence
is a hard error for the whole repo), and the chart needs a values file for
the target env. If all that holds, check the Reflectful logs as above.
