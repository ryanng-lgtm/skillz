#!/usr/bin/env python3
"""Pack the skills the README marks Agnostic yes into one plugin zip.

usage: python3 -I export.py [--out FILE]

Writes FILE (default ~/Downloads/skillz.zip) holding one plugin folder:
skillz/.claude-plugin/plugin.json and skillz/skills/<name>/ for each skill.
Claude Desktop and claude.ai take it at Customize > Plugins > Add > Upload
plugin; the skills/ folder also unzips into any skills directory.

Runs check.py first and writes nothing while it fails, so a stale README
can't pick the wrong skills.
"""
import argparse
import datetime
import json
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)  # -I leaves the script's directory off sys.path
import check  # noqa: E402

PLUGIN = "skillz"
SKIP_DIRS = {"__pycache__", "node_modules"}
SKIP_FILES = {".DS_Store"}
NAME = re.compile(r"^[a-z0-9-]{1,64}$")
MAX_DESCRIPTION = 1024


def agnostic():
    with open(os.path.join(REPO, "README.md")) as fh:
        lines = fh.read().splitlines()
    names = []
    for heading in ("## Skill index", "## One-time setup"):
        rows = check.table_rows(lines, heading)
        names += [n for n, (_, _, a) in rows.items() if a == "yes"]
    return sorted(names)


def files(folder):
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(names):
            if f not in SKIP_FILES and not f.endswith(".pyc"):
                yield os.path.join(root, f)


def upload_problems(name, folder):
    with open(os.path.join(folder, "SKILL.md")) as fh:
        fields, _ = check.frontmatter(fh.read().splitlines())
    if not NAME.match(name):
        yield f"{name}: name must be 1-64 lowercase letters, digits or hyphens"
    if fields.get("name") != name:
        yield f"{name}: frontmatter name is {fields.get('name')!r}, not the folder name"
    desc = fields.get("description", "")
    if not desc:
        yield f"{name}: description is empty"
    elif len(desc) > MAX_DESCRIPTION:
        yield f"{name}: description is {len(desc)} characters, over {MAX_DESCRIPTION}"


def manifest():
    # Date and time, so each export carries a higher version than the last.
    now = datetime.datetime.now()
    version = f"{now.year}.{now.month * 100 + now.day}.{now.hour * 100 + now.minute}"
    return json.dumps({
        "name": PLUGIN,
        "version": version,
        "description": "Ryan's codebase-agnostic skills, exported from the skillz repo.",
    }, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Pack the agnostic skills into one plugin zip.")
    parser.add_argument(
        "--out", default=os.path.expanduser("~/Downloads/skillz.zip"),
        help="the zip to write (default: %(default)s)",
    )
    out = os.path.abspath(parser.parse_args().out)
    if not out.endswith(".zip"):
        out += ".zip"
    if os.path.commonpath([out, REPO]) == REPO:
        print(f"export: {out} is inside the repo, which sync publishes; pick a path outside it")
        return 1

    if check.main() != 0:
        print("export: fix what check.py reports first; nothing written")
        return 1

    home = check.homes()
    skills = {n: os.path.join(REPO, home[n], n) for n in agnostic()}
    problems = [p for n, f in skills.items() for p in upload_problems(n, f)]
    if problems:
        print("\n".join(problems))
        print("export: nothing written")
        return 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{PLUGIN}/.claude-plugin/plugin.json", manifest())
        for name, folder in skills.items():
            for path in files(folder):
                zf.write(path, os.path.join(PLUGIN, "skills", name, os.path.relpath(path, folder)))
            print(f"  {name}")
    print(f"export: {len(skills)} skills in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
