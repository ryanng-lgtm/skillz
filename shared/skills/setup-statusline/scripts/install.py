#!/usr/bin/env python3
"""Install a Claude Code status line that shows the parts you pick.

usage: python3 -I install.py [--parts model,folder,branch,ctx,limits,effort] [--force]

Writes statusline.sh into the Claude Code config directory ($CLAUDE_CONFIG_DIR,
default ~/.claude) with its PARTS line set to the chosen parts (default: all),
then points the statusLine key of settings.json at it after a timestamped
backup. No other setting changes. The script is a copy, so it keeps working
when this skill's folder moves; rerun to change the parts.

Exits 1 without writing anything when settings.json already has a different
statusLine, or when statusline.sh exists and was not written by this skill;
--force replaces either after backing it up. Exits 2 on an unknown part.
"""
import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import stat
import sys

PARTS = ("model", "folder", "branch", "ctx", "limits", "effort")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statusline.sh")
MARKER = "setup-statusline"


def parts(value):
    chosen = [p.strip() for p in value.split(",") if p.strip()]
    unknown = [p for p in chosen if p not in PARTS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown part {', '.join(unknown)}; choose from {','.join(PARTS)}")
    if not chosen:
        raise argparse.ArgumentTypeError("choose at least one part")
    return [p for p in PARTS if p in chosen]


def main(argv):
    ap = argparse.ArgumentParser(prog="install.py")
    ap.add_argument("--parts", type=parts, default=list(PARTS))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    config = os.environ.get("CLAUDE_CONFIG_DIR")
    folder = config or os.path.expanduser("~/.claude")
    script = os.path.join(folder, "statusline.sh")
    settings_path = os.path.join(folder, "settings.json")
    # ~ keeps the setting the same on every machine; Claude Code runs it in a shell,
    # so an explicit path is quoted.
    want = {"type": "command",
            "command": shlex.quote(script) if config else "~/.claude/statusline.sh"}
    # Earlier installs stored the explicit path unquoted; that setting is ours too.
    unquoted = {"type": "command", "command": script}

    settings = load(settings_path)
    current = settings.get("statusLine")
    if current and current not in (want, unquoted) and not args.force:
        print("settings.json has a different statusLine; rerun with --force to replace it:")
        print(json.dumps(current, indent=2))
        return 1
    foreign = os.path.exists(script) and MARKER not in read(script)
    if foreign and not args.force:
        print(f"{script} exists and was not written by {MARKER}; "
              "rerun with --force to replace it")
        return 1

    os.makedirs(folder, exist_ok=True)
    if foreign:
        backup(script)
    write_script(script, args.parts)
    print(f"wrote {script} (parts: {' '.join(args.parts)})")

    if current == want:
        print(f"statusLine already runs {want['command']}")
        return 0
    if os.path.exists(settings_path):
        backup(settings_path)
    settings["statusLine"] = want
    replace(settings_path, json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"statusLine now runs {want['command']}")
    return 0


def write_script(path, chosen):
    text, n = re.subn(r'^PARTS=".*"$', f'PARTS="{" ".join(chosen)}"', read(TEMPLATE),
                      count=1, flags=re.M)
    if n != 1:
        sys.exit(f"{TEMPLATE} has no PARTS line")
    replace(path, text, mode=0o755)


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        return json.load(fh)


def read(path):
    with open(path) as fh:
        return fh.read()


def backup(path):
    dest = f"{path}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(path, dest)
    print(f"backed up {os.path.basename(path)} to {dest}")


def replace(path, text, mode=None):
    # Write through a symlink, so a settings.json linked from elsewhere stays linked,
    # and keep the file's mode, since settings.json can hold tokens.
    path = os.path.realpath(path)
    if mode is None:
        mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else default_mode()
    tmp = path + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as fh:
        fh.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def default_mode():
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
