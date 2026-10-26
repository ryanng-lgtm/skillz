"""Render GitLab review threads as markdown.

Two modes:

    python3 -I threads.py OUT.md [--reviewer pan26] [--author ryan_ng]
                                 [--group openmarketxyz/go-backend]
        Every thread the reviewer took part in, across all of the author's MRs
        in the group. Used to refresh references/panos.md.

    python3 -I threads.py OUT.md --mr PROJECT_ID IID
        Every human thread on one MR, marked resolved or open. Used as the
        reviewer's "existing threads" input.
"""

import argparse
import json
import subprocess
import urllib.parse


def glab(path):
    """Return every page of a GitLab API list endpoint."""
    out = subprocess.run(
        ["glab", "api", "--paginate", path], capture_output=True, text=True, check=True
    ).stdout
    # --paginate concatenates one JSON array per page.
    items, dec, rest = [], json.JSONDecoder(), out.strip()
    while rest:
        page, end = dec.raw_decode(rest)
        items += page
        rest = rest[end:].lstrip()
    return items


def render(disc):
    """Return a thread's human notes as markdown lines, or [] when it has none."""
    notes = [n for n in disc.get("notes", []) if not n.get("system")]
    if not notes:
        return []
    resolvable = [n for n in notes if n.get("resolvable")]
    state = ""
    if resolvable:
        state = " [resolved]" if all(n.get("resolved") for n in resolvable) else " [open]"
    lines = []
    for i, n in enumerate(notes):
        pos = n.get("position") or {}
        line = pos.get("new_line") or pos.get("old_line")
        loc = f" {pos.get('new_path') or pos.get('old_path', '')}:{line}" if pos else ""
        tag = state if i == 0 else ""
        lines.append(f"--- @{n['author']['username']}{loc}{tag}\n{n['body']}")
    return lines


def discussions(project_id, iid):
    return glab(f"projects/{project_id}/merge_requests/{iid}/discussions?per_page=100")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--mr", nargs=2, metavar=("PROJECT_ID", "IID"))
    ap.add_argument("--reviewer", default="pan26")
    ap.add_argument("--author", default="ryan_ng")
    ap.add_argument("--group", default="openmarketxyz/go-backend")
    args = ap.parse_args()

    out, threads = [], 0
    if args.mr:
        for disc in discussions(*args.mr):
            lines = render(disc)
            if lines:
                threads += 1
                out += ["", *lines]
        source = f"MR {args.mr[0]}!{args.mr[1]}"
    else:
        group = urllib.parse.quote(args.group, safe="")
        mrs = glab(
            f"groups/{group}/merge_requests?author_username={args.author}&state=all&scope=all&per_page=100"
        )
        for mr in mrs:
            if mr["user_notes_count"] == 0:
                continue
            for disc in discussions(mr["project_id"], mr["iid"]):
                if not any(n["author"]["username"] == args.reviewer for n in disc.get("notes", [])):
                    continue
                threads += 1
                out.append(f"\n===== {mr['references']['full']} — {mr['title']}")
                out += render(disc)
        source = f"{len(mrs)} MRs"

    with open(args.out, "w") as fh:
        fh.write(("\n".join(out) if out else "No threads.") + "\n")
    print(f"{threads} threads from {source} -> {args.out}")


if __name__ == "__main__":
    main()
