#!/usr/bin/env python3
"""Point Claude Code's statusLine setting at this skill's statusline.sh.

usage: python3 -I install.py [--force | --migrate]

Changes only the statusLine key of settings.json in $CLAUDE_CONFIG_DIR
(default ~/.claude), after a timestamped backup. A different status line that
is already set is printed and left alone unless --force is given.

--migrate repoints a statusLine that still runs this skill under its old name,
status-line, and leaves any other setting alone. It always exits 0, so
install.sh can run it on every machine.
"""
import datetime
import json
import os
import shutil
import sys

SCRIPT = "skills/claude-statusline/scripts/statusline.sh"
OLD_SCRIPT = "skills/status-line/scripts/statusline.sh"


def main(argv):
    force = "--force" in argv
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    # ~ keeps the setting the same on every machine; Claude Code runs it in a shell.
    command = os.path.join(config, SCRIPT) if config else f"~/.claude/{SCRIPT}"
    path = os.path.join(config or os.path.expanduser("~/.claude"), "settings.json")
    want = {"type": "command", "command": command}

    if "--migrate" in argv:
        migrate(path, want)
        return 0

    settings = load(path)
    current = settings.get("statusLine")
    if current == want:
        print(f"statusLine already runs {command}")
        return 0
    if current and not force:
        print("settings.json has a different statusLine; rerun with --force to replace it:")
        print(json.dumps(current, indent=2))
        return 1

    save(path, settings, want)
    print(f"statusLine now runs {command}")
    return 0


def migrate(path, want):
    try:
        settings = load(path)
        current = settings.get("statusLine")
        if not isinstance(current, dict) or OLD_SCRIPT not in str(current.get("command", "")):
            return
        save(path, settings, want)
    except (OSError, ValueError) as err:
        print(f"statusLine not migrated: {path}: {err}", file=sys.stderr)
        return
    print(f"statusLine moved from status-line to {want['command']}")


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def save(path, settings, status_line):
    if os.path.exists(path):
        backup = f"{path}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(path, backup)
        print(f"backed up settings.json to {backup}")
    settings["statusLine"] = status_line
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
