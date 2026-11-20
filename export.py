#!/usr/bin/env python3
"""Pack the shared/ plugin into one zip to upload to Claude or ChatGPT.

usage: python3 -I export.py [--claude | --codex] [--out FILE]

--claude (the default) writes ~/Downloads/skillz-claude.zip for Claude Desktop
and claude.ai, which take it at Customize > Plugins > Add > Upload plugin.
--codex writes ~/Downloads/skillz-codex.zip in the Codex plugin format, for
ChatGPT's New Plugin upload.

Either zip holds shared/ as one plugin folder, skillz/: that target's manifest,
the assets, and skillz/skills/<name>/ for each skill. The other agent's
manifest stays out. The zipped manifest gets a dated version, so each upload
counts as newer than the last; the repo's manifests stay unversioned. The
skills/ folder also unzips into any skills directory.

Runs check.py first and writes nothing while it or the target's upload checks
fail, so a personal marker or a manifest the upload would reject can't ship.
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
# Each target's manifest folder; a zip carries only its own.
TARGETS = {"claude": ".claude-plugin", "codex": ".codex-plugin"}
SKIP_DIRS = {"__pycache__", "node_modules"}
SKIP_FILES = {".DS_Store"}
NAME = re.compile(r"^[a-z0-9-]{1,64}$")
MAX_DESCRIPTION = 1024
# ChatGPT's limits for a Codex package: the skill's `plugin:skill` identity,
# and the listing's one-line short description.
MAX_IDENTITY = 64
MAX_SHORT_DESCRIPTION = 240
# What ChatGPT requires in the Codex manifest's `interface`.
INTERFACE_TEXT = ("displayName", "shortDescription", "longDescription", "developerName")
INTERFACE_LISTS = ("capabilities", "defaultPrompt")
INTERFACE_IMAGES = ("logo", "composerIcon")
YAML_KEY = re.compile(r"^(\s*)([A-Za-z_]+):\s*(.*)$")


def files(folder, target):
    leave_out = {d for t, d in TARGETS.items() if t != target}
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(
            d for d in dirs
            if d not in SKIP_DIRS and not (root == folder and d in leave_out)
        )
        for f in sorted(names):
            if f not in SKIP_FILES and not f.endswith(".pyc"):
                yield os.path.join(root, f)


def manifest_path(target):
    return os.path.join(ROOT, TARGETS[target], "plugin.json")


def openai_yaml(folder):
    """Map each top-level key of agents/openai.yaml to its non-empty child keys."""
    path = os.path.join(folder, "agents", "openai.yaml")
    if not os.path.exists(path):
        return None
    keys, top = {}, None
    with open(path) as fh:
        for line in fh:
            if not (m := YAML_KEY.match(line)):
                continue
            indent, key, value = m.groups()
            if not indent:
                top = key
                keys[top] = set()
            elif top and value.strip().strip("\"'"):
                keys[top].add(key)
    return keys


def skill_problems(name, folder, target):
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
    if target == "claude" and ("<" in desc or ">" in desc):
        yield f"{name}: description has < or >, which the upload rejects as XML tags"
    if target == "codex":
        if len(f"{PLUGIN}:{name}") > MAX_IDENTITY:
            yield f"{name}: {PLUGIN}:{name} is over {MAX_IDENTITY} characters"
        yaml = openai_yaml(folder)
        if yaml is not None:
            missing = {"display_name", "short_description"} - yaml.get("interface", set())
            if missing:
                yield f"{name}: agents/openai.yaml needs interface {', '.join(sorted(missing))}"


def manifest_problems(target):
    rel = os.path.relpath(manifest_path(target), REPO)
    with open(manifest_path(target)) as fh:
        data = json.load(fh)
    if target != "codex":
        return
    if not data.get("description"):
        yield f"{rel}: description is required"
    elif len(data["description"]) > MAX_DESCRIPTION:
        yield f"{rel}: description is over {MAX_DESCRIPTION} characters"
    if not (data.get("author") or {}).get("name"):
        yield f"{rel}: author.name is required"
    ui = data.get("interface") or {}
    for key in INTERFACE_TEXT:
        if not str(ui.get(key, "")).strip():
            yield f"{rel}: interface.{key} is required"
    for key in INTERFACE_LISTS:
        value = ui.get(key)
        if not value or not isinstance(value, list) or not all(
            isinstance(v, str) and v.strip() for v in value
        ):
            yield f"{rel}: interface.{key} must be a non-empty list of strings"
    short = ui.get("shortDescription", "")
    if "\n" in short or len(short) > MAX_SHORT_DESCRIPTION:
        yield f"{rel}: interface.shortDescription must be one line of at most {MAX_SHORT_DESCRIPTION} characters"
    for key in INTERFACE_IMAGES:
        path = ui.get(key, "")
        if not path.startswith("./") or not os.path.isfile(os.path.join(ROOT, path)):
            yield f"{rel}: interface.{key} must be a ./ path to an image in {check.PLUGIN_ROOT}/"


def manifest(target):
    with open(manifest_path(target)) as fh:
        data = json.load(fh)
    # Date and time, so each export carries a higher version than the last.
    now = datetime.datetime.now()
    data["version"] = f"{now.year}.{now.month * 100 + now.day}.{now.hour * 100 + now.minute}"
    return json.dumps(data, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Pack the shared/ plugin into one zip.")
    which = parser.add_mutually_exclusive_group()
    which.add_argument(
        "--claude", dest="target", action="store_const", const="claude",
        help="zip for Claude Desktop and claude.ai (the default)",
    )
    which.add_argument(
        "--codex", dest="target", action="store_const", const="codex",
        help="zip in the Codex plugin format, for ChatGPT",
    )
    parser.set_defaults(target="claude")
    parser.add_argument(
        "--out", help=f"the zip to write (default: ~/Downloads/{PLUGIN}-<target>.zip)",
    )
    args = parser.parse_args()
    target = args.target
    out = os.path.abspath(os.path.expanduser(args.out or f"~/Downloads/{PLUGIN}-{target}.zip"))
    if not out.endswith(".zip"):
        out += ".zip"
    if os.path.commonpath([out, REPO]) == REPO:
        print(f"export: {out} is inside the repo, which sync publishes; pick a path outside it")
        return 1

    if check.main() != 0:
        print("export: fix what check.py reports first; nothing written")
        return 1

    skills = check.skills(os.path.join(check.PLUGIN_ROOT, "skills"))
    problems = list(manifest_problems(target)) + [
        p for n in skills
        for p in skill_problems(n, os.path.join(ROOT, "skills", n), target)
    ]
    if problems:
        print("\n".join(problems))
        print("export: nothing written")
        return 1

    own = os.path.join(TARGETS[target], "plugin.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files(ROOT, target):
            rel = os.path.relpath(path, ROOT)
            entry = f"{PLUGIN}/{rel}"
            if rel == own:
                info = zipfile.ZipInfo.from_file(path, entry)  # keeps mode and date
                zf.writestr(info, manifest(target), zipfile.ZIP_DEFLATED)
            else:
                zf.write(path, entry)
    print("\n".join(f"  {n}" for n in skills))
    print(f"export: {len(skills)} skills in {out}, for {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
