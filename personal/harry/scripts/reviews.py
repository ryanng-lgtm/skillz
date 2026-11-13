"""Collect Harry's past reviews into one markdown file for the reviewer.

    python3 -I reviews.py OUT.md [--days 180] [--max-age-days 7]

GitLab: every thread harry208 wrote in, on openmarketxyz MRs updated in the
last --days days that he was asked to review or that Ryan opened. OM Chat:
his posts in #go-tasks of more than 120 characters from the same window,
read with `om room history`.

OUT is left alone when it is younger than --max-age-days. It carries
teammates' names and internal links: keep it out of the skillz repo, which
is public.
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time

GROUP = "openmarketxyz"
REVIEWER = "harry208"
AUTHOR = "ryan_ng"
ROOM_TITLE = "#go-tasks"
HANDLE = "harrychiew"


def room_id():
    """Return the canonical name of the room titled ROOM_TITLE."""
    out = subprocess.run(
        ["om", "room", "ls", "--format", "json", "--limit", "500"],
        capture_output=True, text=True, check=True,
    ).stdout
    for room in json.loads(out):
        if room.get("title") == ROOM_TITLE:
            return room["name"]
    sys.exit(f"no room titled {ROOM_TITLE} in `om room ls`")


def glab(path):
    """Return every page of a GitLab API list endpoint."""
    out = subprocess.run(
        ["glab", "api", "--paginate", path], capture_output=True, text=True, check=True
    ).stdout
    items, dec, rest = [], json.JSONDecoder(), out.strip()
    while rest:
        page, end = dec.raw_decode(rest)
        items += page
        rest = rest[end:].lstrip()
    return items


def render(disc):
    """Return a thread's human notes as markdown, or None when Harry wrote none."""
    notes = [n for n in disc.get("notes", []) if not n.get("system")]
    if not any(n["author"]["username"] == REVIEWER for n in notes):
        return None
    lines = []
    for n in notes:
        pos = n.get("position") or {}
        line = pos.get("new_line") or pos.get("old_line")
        loc = f" {pos.get('new_path') or pos.get('old_path', '')}:{line}" if pos else ""
        lines.append(f"--- @{n['author']['username']}{loc}\n{n['body']}")
    return "\n".join(lines)


def gitlab_threads(since):
    mrs = {}
    for who in (f"reviewer_username={REVIEWER}", f"author_username={AUTHOR}"):
        for mr in glab(
            f"groups/{GROUP}/merge_requests?{who}&state=all&scope=all"
            f"&updated_after={since.isoformat()}&per_page=100"
        ):
            mrs[mr["id"]] = mr
    out = []
    for mr in sorted(mrs.values(), key=lambda m: m["updated_at"]):
        if mr["user_notes_count"] == 0:
            continue
        threads = glab(f"projects/{mr['project_id']}/merge_requests/{mr['iid']}/discussions?per_page=100")
        rendered = [t for t in map(render, threads) if t]
        if rendered:
            out.append(f"### {mr['references']['full']} — {mr['title']}\n\n" + "\n\n".join(rendered))
    return out


def room_page(room, before):
    cmd = ["om", "room", "history", room, "--format", "json", "--limit", "200"]
    if before:
        cmd += ["--before-seq", str(before)]
    for _ in range(5):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.stdout.strip():
            return json.loads(r.stdout).get("entries", [])
        time.sleep(6)  # the relay refuses reads that come too fast
    sys.exit(f"om room history failed: {r.stderr.strip()[-300:]}")


def chat_posts(since):
    since_ms = since.timestamp() * 1000
    room, posts, before = room_id(), [], None
    while True:
        entries = room_page(room, before)
        if not entries:
            break
        posts += [e for e in entries if e.get("handle") == HANDLE and e.get("type") == "post"
                  and len(e.get("text", "")) > 120 and e["ts"] >= since_ms]
        oldest = min(entries, key=lambda e: e["seq"])
        if oldest["ts"] < since_ms or oldest["seq"] <= 1:
            break
        before = oldest["seq"]
    posts.sort(key=lambda e: e["seq"])
    return [f"--- [{p['seq']}] topic {p.get('topicId')}\n{p['text']}" for p in posts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--max-age-days", type=float, default=7)
    args = ap.parse_args()

    if os.path.exists(args.out):
        age = (time.time() - os.path.getmtime(args.out)) / 86400
        if age < args.max_age_days:
            print(f"{args.out} is {age:.1f} days old; reusing it")
            return
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    threads = gitlab_threads(since)
    posts = chat_posts(since)
    body = ["# Your past reviews", "", "## GitLab threads you wrote in", ""]
    body += threads or ["none"]
    body += ["", "## Your posts in OM Chat #go-tasks, oldest first", ""]
    body += posts or ["none"]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write("\n\n".join(body) + "\n")
    print(f"{len(threads)} GitLab MRs, {len(posts)} chat posts -> {args.out}")


if __name__ == "__main__":
    main()
