#!/usr/bin/env python3
"""Parse a GitLab user-activity .atom export into categorized work items.

GitLab exposes a per-user feed at https://<host>/<username>.atom — download it
and pass the file here. The feed surfaces review/MR activity (approvals, MR
opens/merges, comments, branch create/delete) that local `git log` never shows,
but it is capped to a recent window of entries, so it will not backfill old work.

Usage:
  parse-atom.py FEED.atom                 # all entries
  parse-atom.py FEED.atom --date 2026-06-18   # only that calendar day (UTC)
  parse-atom.py FEED.atom --since 2026-06-15  # that day onward
  parse-atom.py FEED.atom --json          # machine-readable

Output groups entries by action and pulls out the MR number (!NNNN) and title so
log entries can reference `(!NNNN)` instead of a bare commit hash.
"""
import sys, re, html, json, argparse

ACTIONS = [
    ("approval",      r"approved merge request"),
    ("mr_merged",     r"accepted merge request"),
    ("mr_opened",     r"opened merge request"),
    ("comment",       r"commented on"),
    ("branch_new",    r"pushed new project branch"),
    ("branch_delete", r"deleted project branch"),
    ("push",          r"pushed to project branch"),
]


def classify(title):
    for name, pat in ACTIONS:
        if re.search(pat, title):
            return name
    return "other"


def parse(path):
    raw = open(path, encoding="utf-8").read()
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", raw, re.S):
        tm = re.search(r"<title>(.*?)</title>", e, re.S)
        um = re.search(r"<updated>(.*?)</updated>", e, re.S)
        lm = re.search(r'<link href="(.*?)"', e, re.S)
        if not (tm and um):
            continue
        title = html.unescape(html.unescape(tm.group(1))).replace("\U0001f3e0", "").strip()
        title = re.sub(r"\s+at\s+.*$", "", title)  # drop " at <project>" tail
        date = um.group(1)[:10]
        mr = re.search(r"merge request !(\d+):\s*(.*)", title)
        out.append({
            "date": date,
            "action": classify(title),
            "mr": mr.group(1) if mr else None,
            "mr_title": mr.group(2).strip() if mr else None,
            "title": title,
            "link": html.unescape(lm.group(1)) if lm else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("feed")
    ap.add_argument("--date", help="keep only this YYYY-MM-DD")
    ap.add_argument("--since", help="keep this YYYY-MM-DD onward")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rows = parse(a.feed)
    if a.date:
        rows = [r for r in rows if r["date"] == a.date]
    if a.since:
        rows = [r for r in rows if r["date"] >= a.since]

    if a.json:
        print(json.dumps(rows, indent=2))
        return

    dates = sorted({r["date"] for r in rows})
    span = f"{dates[0]} → {dates[-1]}" if dates else "none"
    print(f"{len(rows)} entries  |  window: {span}")
    order = ["approval", "mr_opened", "mr_merged", "comment",
             "push", "branch_new", "branch_delete", "other"]
    for act in order:
        group = [r for r in rows if r["action"] == act]
        if not group:
            continue
        print(f"\n=== {act} ({len(group)}) ===")
        for r in group:
            ref = f"!{r['mr']} " if r["mr"] else ""
            label = r["mr_title"] or r["title"]
            print(f"  {r['date']}  {ref}{label}")


if __name__ == "__main__":
    main()
