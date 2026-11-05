#!/usr/bin/env python3
"""Point Claude Code's statusLine setting at this skill's statusline.sh.

usage: python3 -I install.py [--force | --migrate]

Changes only the statusLine key of settings.json in $CLAUDE_CONFIG_DIR
(default ~/.claude), after a timestamped backup. A different status line that
is already set is printed and left alone unless --force is given.

--migrate repoints a statusLine that still runs this skill under its old name,
status-line, or by an unquoted path, and leaves any other setting alone. It
always exits 0, so install.sh can run it on every machine.
"""
import datetime
import json
import os
import shlex
import shutil
import stat
import sys

SCRIPT = "skills/claude-statusline/scripts/statusline.sh"
OLD_SCRIPT = "skills/status-line/scripts/statusline.sh"


def main(argv):
    force = "--force" in argv
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    # ~ keeps the setting the same on every machine; Claude Code runs it in a shell,
    # so an explicit path is quoted.
    script = os.path.join(config, SCRIPT) if config else f"~/.claude/{SCRIPT}"
    command = shlex.quote(script) if config else script
    path = os.path.join(config or os.path.expanduser("~/.claude"), "settings.json")
    want = {"type": "command", "command": command}
    # Earlier installs stored the explicit path unquoted; that setting is ours too.
    unquoted = {"type": "command", "command": script}

    if "--migrate" in argv:
        migrate(path, want, unquoted)
        return 0

    settings = load(path)
    current = settings.get("statusLine")
    if current == want:
        print(f"statusLine already runs {command}")
        return 0
    if current and current != unquoted and not force:
        print("settings.json has a different statusLine; rerun with --force to replace it:")
        print(json.dumps(current, indent=2))
        return 1

    save(path, settings, want)
    print(f"statusLine now runs {command}")
    return 0


def migrate(path, want, unquoted):
    try:
        settings = load(path)
        current = settings.get("statusLine")
        if current == want or not isinstance(current, dict):
            return
        if current != unquoted and OLD_SCRIPT not in str(current.get("command", "")):
            return
        save(path, settings, want)
    except (OSError, ValueError) as err:
        print(f"statusLine not migrated: {path}: {err}", file=sys.stderr)
        return
    print(f"statusLine now runs {want['command']}")


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
    # Write through a symlink, so a settings.json linked from elsewhere stays linked,
    # and keep the file's mode, since settings.json can hold tokens.
    path = os.path.realpath(path)
    if os.path.exists(path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    tmp = path + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as fh:
        json.dump(settings, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(tmp, mode)
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
