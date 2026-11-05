#!/usr/bin/env python3
"""Digest a day's Claude Code sessions for war-diary context.

Claude Code stores one .jsonl transcript per session under
~/.claude/projects/<project-slug>/<session-id>.jsonl . This surfaces work that
never reaches GitLab — analysis, planning, doc authoring done in-session (e.g.
Obsidian notes) — so it complements parse-atom.py + `git log`.

Usage:
  scan-sessions.py                      # today, all projects
  scan-sessions.py --date 2026-06-15
  scan-sessions.py --grep Obsidian      # only sessions touching paths matching grep
  scan-sessions.py --base ~/.claude/projects

Per session it prints: the project, the user's prompts (intent), files
written/edited, and notable Bash commands (commits, etc.). Read the digest, then
ask the user to confirm/flesh out — do not log it verbatim.
"""
import sys, os, json, glob, argparse, datetime

EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def text_blocks(content):
    if isinstance(content, str):
        return [content]
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text", ""))
    return out


def scan_file(path, date):
    prompts, files, cmds = [], [], []
    hit = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("timestamp", "")[:10] != date:
                continue
            hit = True
            msg = e.get("message") or {}
            role = msg.get("role") or e.get("type")
            content = msg.get("content")
            if role == "user":
                for t in text_blocks(content):
                    t = t.strip()
                    if not t or t.startswith("<") or "tool_result" in t:
                        continue
                    if "system-reminder" in t or "hook" in t.lower()[:40]:
                        continue
                    if t.startswith(("Base directory for this skill:", "Launching skill", "Caveman", "CAVEMAN")):
                        continue
                    prompts.append(t.replace("\n", " ")[:140])
            elif role == "assistant" and isinstance(content, list):
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    name, inp = b.get("name"), b.get("input") or {}
                    if name in EDIT_TOOLS and inp.get("file_path"):
                        files.append(inp["file_path"])
                    elif name == "Bash" and inp.get("command"):
                        c = inp["command"]
                        if any(k in c for k in ("git commit", "git push", "git tag")):
                            cmds.append(c.replace("\n", " ")[:120])
    return hit, prompts, files, cmds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--base", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--grep", help="only sessions where a touched path matches this")
    a = ap.parse_args()

    sessions = sorted(glob.glob(os.path.join(a.base, "*", "*.jsonl")))
    shown = 0
    for path in sessions:
        hit, prompts, files, cmds = scan_file(path, a.date)
        if not hit:
            continue
        uniq_files = list(dict.fromkeys(files))
        if a.grep and not any(a.grep.lower() in f.lower() for f in uniq_files):
            continue
        shown += 1
        project = os.path.basename(os.path.dirname(path))
        print(f"\n=== {project}  ({os.path.basename(path)[:8]})  {a.date} ===")
        if prompts:
            print("  intent:")
            for p in dict.fromkeys(prompts):
                print(f"    • {p}")
        if uniq_files:
            print("  files touched:")
            for f in uniq_files:
                print(f"    - {f}")
        if cmds:
            print("  git:")
            for c in dict.fromkeys(cmds):
                print(f"    $ {c}")
    print(f"\n{shown} session(s) on {a.date}")


if __name__ == "__main__":
    main()
