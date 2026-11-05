#!/usr/bin/env python3
"""Pack the shared/ plugin into one zip for Claude Desktop and claude.ai.

usage: python3 -I export.py [--out FILE]

Writes FILE (default ~/Downloads/skillz.zip) holding shared/ as one plugin
folder, skillz/: the manifests plus skillz/skills/<name>/ for each skill. The
zipped .claude-plugin/plugin.json gets a dated version, so each upload counts
as newer than the last; the repo's manifest stays unversioned. Claude Desktop
and claude.ai take the zip at Customize > Plugins > Add > Upload plugin; the
skills/ folder also unzips into any skills directory.

Runs check.py first and writes nothing while it fails, so a personal marker
can't ship in the zip.
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
ROOT = os.path.join(REPO, check.PLUGIN_ROOT)
MANIFEST = ".claude-plugin/plugin.json"
SKIP_DIRS = {"__pycache__", "node_modules"}
SKIP_FILES = {".DS_Store"}
NAME = re.compile(r"^[a-z0-9-]{1,64}$")
MAX_DESCRIPTION = 1024


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
    if "<" in desc or ">" in desc:
        yield f"{name}: description has < or >, which the upload rejects as XML tags"


def manifest():
    with open(os.path.join(ROOT, MANIFEST)) as fh:
        data = json.load(fh)
    # Date and time, so each export carries a higher version than the last.
    now = datetime.datetime.now()
    data["version"] = f"{now.year}.{now.month * 100 + now.day}.{now.hour * 100 + now.minute}"
    return json.dumps(data, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Pack the shared/ plugin into one zip.")
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

    skills = check.skills(os.path.join(check.PLUGIN_ROOT, "skills"))
    problems = [
        p for n in skills
        for p in upload_problems(n, os.path.join(ROOT, "skills", n))
    ]
    if problems:
        print("\n".join(problems))
        print("export: nothing written")
        return 1

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files(ROOT):
            rel = os.path.relpath(path, ROOT)
            entry = f"{PLUGIN}/{rel}"
            if rel == os.path.normpath(MANIFEST):
                info = zipfile.ZipInfo.from_file(path, entry)  # keeps mode and date
                zf.writestr(info, manifest(), zipfile.ZIP_DEFLATED)
            else:
                zf.write(path, entry)
    print("\n".join(f"  {n}" for n in skills))
    print(f"export: {len(skills)} skills in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
