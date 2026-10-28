#!/usr/bin/env python3
"""Point Claude Code's statusLine setting at this skill's statusline.sh.

usage: python3 -I install.py [--force]

Changes only the statusLine key of settings.json in $CLAUDE_CONFIG_DIR
(default ~/.claude), after a timestamped backup. A different status line that
is already set is printed and left alone unless --force is given.
"""
import datetime
import json
import os
import shutil
import sys

SCRIPT = "skills/status-line/scripts/statusline.sh"


def main(argv):
    force = "--force" in argv
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    # ~ keeps the setting the same on every machine; Claude Code runs it in a shell.
    command = os.path.join(config, SCRIPT) if config else f"~/.claude/{SCRIPT}"
    path = os.path.join(config or os.path.expanduser("~/.claude"), "settings.json")

    settings = {}
    if os.path.exists(path):
        with open(path) as fh:
            settings = json.load(fh)
    want = {"type": "command", "command": command}
    current = settings.get("statusLine")
    if current == want:
        print(f"statusLine already runs {command}")
        return 0
    if current and not force:
        print("settings.json has a different statusLine; rerun with --force to replace it:")
        print(json.dumps(current, indent=2))
        return 1

    if os.path.exists(path):
        backup = f"{path}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(path, backup)
        print(f"backed up settings.json to {backup}")
    settings["statusLine"] = want
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    print(f"statusLine now runs {command}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
