#!/usr/bin/env python3
"""Zip the skills the README marks Agnostic yes, to upload anywhere.

usage: python3 -I export.py [--out DIR]

Writes DIR/<name>.zip for each skill, with the skill's folder at the zip's
root (the layout Claude Desktop's skill upload takes), and DIR.zip with every
skill folder in one archive. DIR defaults to ~/Downloads/skillz-skills.

Runs check.py first and writes nothing while it fails, so a stale README
can't pick the wrong skills.
"""
import argparse
import glob
import os
import re
import sys
import zipfile

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)  # -I leaves the script's directory off sys.path
import check  # noqa: E402

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
    desc = fields.get("description", "")
    if not desc:
        yield f"{name}: description is empty"
    elif len(desc) > MAX_DESCRIPTION:
        yield f"{name}: description is {len(desc)} characters, over {MAX_DESCRIPTION}"


def add(zf, name, folder):
    for path in files(folder):
        zf.write(path, os.path.join(name, os.path.relpath(path, folder)))


def main():
    parser = argparse.ArgumentParser(description="Zip the agnostic skills.")
    parser.add_argument(
        "--out", default=os.path.expanduser("~/Downloads/skillz-skills"),
        help="directory for the per-skill zips (default: %(default)s)",
    )
    out = os.path.abspath(parser.parse_args().out)
    if os.path.commonpath([out, REPO]) == REPO:
        print(f"export: {out} is inside the repo, which sync publishes; pick a folder outside it")
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

    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*.zip")):
        os.remove(old)
    with zipfile.ZipFile(out + ".zip", "w", zipfile.ZIP_DEFLATED) as everything:
        for name, folder in skills.items():
            with zipfile.ZipFile(os.path.join(out, name + ".zip"), "w", zipfile.ZIP_DEFLATED) as zf:
                add(zf, name, folder)
            add(everything, name, folder)
            print(f"  {name}.zip")
    print(f"export: {len(skills)} skills in {out}/, all of them in {out}.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
