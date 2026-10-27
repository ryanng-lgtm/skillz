"""Regroup a branch's commits for review without changing its code.

Usage:
  python3 -I regroup.py stats [--base REF] [--max-lines N] [--json]
  python3 -I regroup.py apply PLAN.json [--base REF] [--max-lines N] [--dry-run]
  python3 -I regroup.py check [--base REF] [--max-lines N] [--against REF]
                              [--exec CMD [--link DIR ...] [--timeout S]]

Run from inside the repo. The base defaults to the merge base with origin/HEAD,
origin/main, origin/master, main or master, whichever exists first.

A plan is JSON: {"commits": [{"message": "...", "paths": ["a.go", "b.go@<sha>"]}],
"kinds": {"<glob>": "<kind>"}}. A path takes its version at the branch tip;
`path@<sha>` takes its version at that commit of the branch. `kinds` overrides
how paths are classified (code, test, testdata, docs, generated); stats and
check read it with --plan.

The layout the rules enforce: code commits grouped by concern, each within
the line cap, then one testdata commit, one tests commit and one docs commit,
whatever their size.
"""

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

MAX_LINES = 600
MAX_COMMITS = 9
MIN_TEST_LINES = 200
EMPTY = "0" * 40

KINDS = ("code", "test", "testdata", "docs", "generated")
ORDER = {"code": 0, "generated": 0, "testdata": 1, "test": 2, "docs": 3}
TESTDATA_DIRS = {"testdata", "fixtures", "__fixtures__"}
TESTDATA_NAMES = ["*.golden"]
TEST_DIRS = {"test", "tests", "__tests__", "spec"}
TEST_NAMES = ["test_*.py", "*_test.py", "*_test.go", "conftest.py", "*.test.*", "*.spec.*"]
DOCS_DIRS = {"docs", "doc"}
DOCS_NAMES = ["*.md", "*.mdx", "*.rst", "*.adoc"]
GENERATED_DIRS = {"vendor", "node_modules", "__snapshots__"}
GENERATED_NAMES = ["go.sum", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock",
                   "bun.lockb", "Cargo.lock", "uv.lock", "poetry.lock", "Gemfile.lock", "composer.lock",
                   "*.pb.go", "*_pb2.py", "*_pb2_grpc.py", "*_gen.go", "zz_generated*", "*.min.js", "*.min.css",
                   "*.snap"]


class Refused(Exception):
    pass


class Rules:
    """Each path's kind: code, test, testdata, docs, or generated (never counted toward a commit's size)."""

    def __init__(self, kinds=None):
        self.kinds = dict(kinds or {})
        bad = sorted(set(self.kinds.values()) - set(KINDS))
        if bad:
            raise Refused(f"unknown kind in the plan's kinds: {', '.join(bad)} (use {', '.join(KINDS)})")

    def kind(self, path):
        for glob, kind in self.kinds.items():
            if fnmatch.fnmatchcase(path, glob):
                return kind
        p = PurePosixPath(path)
        dirs, name = set(p.parts[:-1]), p.name
        if dirs & GENERATED_DIRS or _match(name, GENERATED_NAMES):
            return "generated"
        if dirs & TESTDATA_DIRS or _match(name, TESTDATA_NAMES):
            return "testdata"
        if dirs & TEST_DIRS or _match(name, TEST_NAMES):
            return "test"
        if dirs & DOCS_DIRS or _match(name, DOCS_NAMES):
            return "docs"
        return "code"


def _match(text, globs):
    return any(fnmatch.fnmatchcase(text, g) for g in globs)


def git(repo, *args, input=None, env=None):
    proc = subprocess.run(["git", *args], cwd=repo, input=input, capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    if proc.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def _rev(repo, ref):
    proc = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], cwd=repo,
                          capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else None


def resolve_base(repo, ref=None):
    for candidate in [ref] if ref else ["origin/HEAD", "origin/main", "origin/master", "main", "master"]:
        if _rev(repo, candidate):
            return git(repo, "merge-base", candidate, "HEAD").strip()
    raise Refused(f"cannot find the base {ref or '(origin/HEAD, origin/main, origin/master, main, master)'}; "
                  "pass --base")


def commits(repo, base, head):
    out = []
    for line in git(repo, "rev-list", "--reverse", "--parents", f"{base}..{head}").splitlines():
        sha, *parents = line.split()
        if len(parents) > 1:
            raise Refused(f"the branch has a merge commit ({sha[:8]}); rebase it onto its target first")
        out.append(sha)
    return out


def _numstat(repo, a, b):
    fields = git(repo, "diff", "--numstat", "-z", "--no-renames", a, b).split("\0")
    out = []
    for field in fields:
        if not field:
            continue
        added, deleted, path = field.split("\t", 2)
        binary = added == "-"
        out.append((path, 0 if binary else int(added), 0 if binary else int(deleted), binary))
    return out


def _attr_generated(repo, paths):
    if not paths:
        return set()
    out = git(repo, "check-attr", "-z", "--stdin", "linguist-generated", input="\0".join(paths) + "\0")
    parts = out.split("\0")
    return {parts[i] for i in range(0, len(parts) - 2, 3) if parts[i + 2] in ("set", "true")}


def _files(repo, a, b, rules):
    rows = _numstat(repo, a, b)
    attr = _attr_generated(repo, [r[0] for r in rows])
    out = []
    for path, added, deleted, binary in rows:
        kind = "generated" if path in attr else rules.kind(path)
        out.append({"path": path, "kind": kind, "added": added, "deleted": deleted, "binary": binary})
    return out


def review(repo, base, head, max_lines, rules):
    """Per-commit size, kind and rule problems for base..head."""
    report = []
    for sha in commits(repo, base, head):
        files = _files(repo, f"{sha}^", sha, rules)
        counted_files = [f for f in files if f["kind"] not in ("generated", "testdata") and not f["binary"]]
        counted = sum(f["added"] + f["deleted"] for f in counted_files)
        excluded = sum(f["added"] + f["deleted"] for f in files if f not in counted_files)
        kinds = {f["kind"] for f in files if f["kind"] != "generated"}
        kind = "mixed" if len(kinds) > 1 else (kinds.pop() if kinds else "generated")
        problems, notes = [], []
        if kind == "mixed":
            mixed = sorted({f["kind"] for f in files} - {"generated"})
            problems.append(f"mixes kinds ({', '.join(mixed)}); each kind goes in its own commit")
        code_files = [f for f in counted_files if f["kind"] == "code"]
        code_lines = sum(f["added"] + f["deleted"] for f in code_files)
        oversize = code_lines > max_lines and len(code_files) > 1
        if oversize:
            problems.append(f"{code_lines} changed lines > {max_lines}")
        elif code_lines > max_lines:
            notes.append(f"single file over {max_lines} changed lines ({code_lines}); cannot split by path")
        report.append({"sha": sha, "subject": git(repo, "log", "-1", "--format=%s", sha).strip(),
                       "counted": counted, "excluded": excluded, "kind": kind, "oversize": oversize,
                       "files": files, "problems": problems, "notes": notes})
    return report


def layout_problems(report):
    """Problems with how the kinds spread over the commits and in what order."""
    out = []
    for kind, label in (("testdata", "testdata"), ("test", "tests"), ("docs", "docs")):
        n = sum(1 for c in report if c["kind"] == kind)
        if n > 1:
            out.append(f"{label} are spread over {n} commits; they go in one")
    highest, after = -1, None
    for c in report:
        if c["kind"] == "mixed":
            continue
        rank = ORDER[c["kind"]]
        if rank < highest:
            out.append(f"{c['sha'][:8]} {c['subject']}: {c['kind']} comes after a {after} commit; "
                       "the order is code, testdata, tests, docs")
        elif rank > highest:
            highest, after = rank, c["kind"]
    return out


def offer_reasons(report, files, max_lines):
    """Why to offer /regroup: too many commits, an oversize commit, or tests that outweigh the code."""
    reasons = []
    if len(report) > MAX_COMMITS:
        reasons.append(f"{len(report)} commits > {MAX_COMMITS}")
    over = sum(1 for c in report if c["oversize"])
    if over:
        reasons.append(f"{over} commit{'s' if over > 1 else ''} over {max_lines} changed lines")
    tests = sum(f["added"] for f in files if f["kind"] == "test" and not f["binary"])
    code = sum(f["added"] + f["deleted"] for f in files if f["kind"] == "code" and not f["binary"])
    if tests >= MIN_TEST_LINES and tests > code:
        reasons.append(f"tests add {tests} lines against {code} changed lines of code")
    return reasons


def tree_diff(repo, a, b):
    return [p for p in git(repo, "diff", "--name-only", "-z", "--no-renames", a, b).split("\0") if p]


_REV = re.compile(r"^[0-9a-f]{4,40}$")


def _entry(repo, entry, originals):
    path, _, rev = entry.rpartition("@")
    if not path or not _REV.match(rev):
        return entry, None
    full = _rev(repo, rev)
    if full not in originals:
        raise Refused(f"{entry}: {rev} is not a commit on this branch")
    return path, full


def build(repo, base, head, plan):
    """Commit the plan's groups on top of base and return the new tip. Never moves a ref."""
    originals = set(commits(repo, base, head))
    changed = set(tree_diff(repo, base, head))
    groups, assigned = [], set()
    for i, c in enumerate(plan["commits"], 1):
        message = c.get("message", "").strip()
        if not message:
            raise Refused(f"commit {i} has no message")
        entries = [_entry(repo, e, originals) for e in c["paths"]]
        for path, _ in entries:
            if path not in changed:
                raise Refused(f"{path} is not changed on this branch")
            assigned.add(path)
        groups.append((message, entries))
    if changed - assigned:
        raise Refused("no commit takes: " + ", ".join(sorted(changed - assigned)))

    with tempfile.TemporaryDirectory() as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git(repo, "read-tree", base, env=env)
        parent = base
        for i, (message, entries) in enumerate(groups, 1):
            lines = []
            for path, rev in entries:
                listed = git(repo, "ls-tree", "-z", rev or head, "--", path).rstrip("\0")
                if listed:
                    meta, _ = listed.split("\t", 1)
                    mode, _, sha = meta.split()
                    lines.append(f"{mode} {sha}\t{path}")
                else:
                    lines.append(f"0 {EMPTY}\t{path}")
            git(repo, "update-index", "-z", "--index-info", input="\0".join(lines) + "\0", env=env)
            tree = git(repo, "write-tree", env=env).strip()
            if tree == git(repo, "rev-parse", f"{parent}^{{tree}}").strip():
                raise Refused(f"commit {i} ({message.splitlines()[0]}) changes nothing")
            parent = git(repo, "commit-tree", tree, "-p", parent, "-F", "-", input=message + "\n").strip()
    differs = tree_diff(repo, parent, head)
    if differs:
        raise Refused("the regrouped tip differs from the branch: " + ", ".join(differs))
    return parent


def _problems(report):
    return [f"{c['sha'][:8]} {c['subject']}: {p}" for c in report for p in c["problems"]]


def apply(repo, plan_path, base_ref=None, max_lines=MAX_LINES, dry_run=False):
    branch = subprocess.run(["git", "symbolic-ref", "-q", "--short", "HEAD"], cwd=repo, capture_output=True,
                            text=True).stdout.strip()
    if not branch:
        raise Refused("HEAD is detached; check out the branch to regroup")
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise Refused("the worktree has uncommitted changes; commit them or set them aside first")
    plan = json.loads(Path(plan_path).read_text())
    rules = Rules(plan.get("kinds"))
    base = resolve_base(repo, base_ref)
    head = git(repo, "rev-parse", "HEAD").strip()
    tip = build(repo, base, head, plan)
    report = review(repo, base, tip, max_lines, rules)
    problems = _problems(report) + layout_problems(report)
    if problems:
        raise Refused("the regrouped commits break the rules; the branch is unchanged:\n  " + "\n  ".join(problems))
    backup = None
    if not dry_run:
        backup = f"refs/regroup/{branch}/{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        git(repo, "update-ref", backup, head, "")
        git(repo, "update-ref", "-m", "regroup", f"refs/heads/{branch}", tip, head)
    return {"branch": branch, "base": base, "old": head, "new": tip, "backup": backup, "review": report}


def run_each(repo, shas, cmd, links, timeout):
    """Run cmd at each commit in a temporary worktree; [(sha, ok, output tail)]."""
    if not shas:
        return []
    tmp = Path(tempfile.mkdtemp(prefix="regroup-"))
    wt = tmp / "wt"
    results = []
    try:
        git(repo, "worktree", "add", "-q", "--detach", str(wt), shas[0])
        for name in links:
            src = Path(repo, name).resolve()
            if src.exists() and not (wt / name).exists():
                (wt / name).parent.mkdir(parents=True, exist_ok=True)
                os.symlink(src, wt / name)
        for sha in shas:
            git(wt, "checkout", "-q", "--detach", sha)
            try:
                proc = subprocess.run(cmd, shell=True, cwd=wt, capture_output=True, text=True, timeout=timeout)
                ok, out = proc.returncode == 0, proc.stdout + proc.stderr
            except subprocess.TimeoutExpired:
                ok, out = False, f"timed out after {timeout}s"
            results.append((sha, ok, "\n".join(out.strip().splitlines()[-20:])))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo, capture_output=True)
        subprocess.run(["git", "worktree", "prune"], cwd=repo, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return results


def _print_review(report):
    for c in report:
        print(f"  {c['sha'][:8]}  {c['kind']:<9} {c['counted']:>5}  {c['subject']}"
              + (f"  (+{c['excluded']} not counted)" if c["excluded"] else ""))
        for p in c["problems"]:
            print(f"            ! {p}")
        for n in c["notes"]:
            print(f"            ~ {n}")


def main(argv):
    ap = argparse.ArgumentParser(prog="regroup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("stats", "apply", "check"):
        p = sub.add_parser(name)
        p.add_argument("--base")
        p.add_argument("--max-lines", type=int, default=MAX_LINES)
        if name != "apply":
            p.add_argument("--plan", help="read the plan's kinds")
        if name == "stats":
            p.add_argument("--json", action="store_true")
        if name == "apply":
            p.add_argument("plan")
            p.add_argument("--dry-run", action="store_true")
        if name == "check":
            p.add_argument("--against", help="a ref whose tree HEAD must match (the backup)")
            p.add_argument("--exec", dest="exec_cmd", help="command that must pass at every commit")
            p.add_argument("--link", action="append", default=[], help="ignored dir to link into the temp worktree")
            p.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args(argv)
    repo = git(os.getcwd(), "rev-parse", "--show-toplevel").strip()
    try:
        if args.cmd == "apply":
            out = apply(repo, args.plan, args.base, args.max_lines, args.dry_run)
            print(f"{'dry run: ' if args.dry_run else ''}{out['branch']} {out['old'][:8]} -> {out['new'][:8]}"
                  + (f", backup {out['backup']}" if out["backup"] else ""))
            _print_review(out["review"])
            return 0
        rules = Rules(json.loads(Path(args.plan).read_text()).get("kinds") if args.plan else None)
        base = resolve_base(repo, args.base)
        report = review(repo, base, "HEAD", args.max_lines, rules)
        layout = layout_problems(report)
        if args.cmd == "stats":
            branch_files = _files(repo, base, "HEAD", rules)
            files = [{"path": f["path"], "kind": f["kind"], "lines": f["added"] + f["deleted"]}
                     for f in branch_files]
            reasons = offer_reasons(report, branch_files, args.max_lines)
            if args.json:
                print(json.dumps({"base": base, "commits": report, "offer": reasons, "layout": layout,
                                  "files": files}, indent=2))
                return 0
            print(f"base {base[:8]}, {len(report)} commits, offer /regroup: "
                  + ("; ".join(reasons) if reasons else "no"))
            _print_review(report)
            for problem in layout:
                print(f"  layout ! {problem}")
            print("files (whole branch):")
            for f in files:
                print(f"  {f['kind']:<9} {f['lines']:>5}  {f['path']}")
            return 0
        failed = bool(_problems(report) or layout)
        _print_review(report)
        for problem in layout:
            print(f"  layout ! {problem}")
        if args.against:
            differs = tree_diff(repo, args.against, "HEAD")
            print(f"tree vs {args.against}: " + ("identical" if not differs else "DIFFERS: " + ", ".join(differs)))
            failed |= bool(differs)
        if args.exec_cmd:
            for sha, ok, tail in run_each(repo, [c["sha"] for c in report], args.exec_cmd, args.link, args.timeout):
                print(f"  {sha[:8]} {'pass' if ok else 'FAIL'}")
                if not ok:
                    print("\n".join("      " + line for line in tail.splitlines()))
                failed |= not ok
        return 1 if failed else 0
    except Refused as e:
        print(f"regroup: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
