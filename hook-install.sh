#!/usr/bin/env bash
#
# Register the auto-sync hooks in ~/.claude/settings.json.
#
# Stop runs sync.sh, so a session syncs once when it finishes answering. It
# ran on PostToolUse until it turned a thirteen-edit session into thirteen
# commits and pushes; sync.sh sweeps the whole repo with `git add -A`, so
# firing per edit bought nothing that firing per turn does not.
#
# SessionStart runs `sync.sh --pull`, so a session starts on what the other
# machines pushed. Stop alone never pulled on a machine that only reads the
# skills, and it kept running old versions.
#
# settings.json is deliberately NOT tracked by this repo (it accumulates
# machine-local permission entries), so the hook is injected per device
# instead of synced. Idempotent: re-running replaces the skillz entry and
# leaves every other hook and setting untouched.
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETTINGS="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"

[ -f "$SETTINGS" ] || echo '{}' >"$SETTINGS"

python3 - "$SETTINGS" "$REPO/sync.sh" <<'PY'
import json, shlex, sys, shutil, datetime

settings_path, hook_cmd = sys.argv[1], sys.argv[2]

with open(settings_path) as fh:
    settings = json.load(fh)

shutil.copy2(settings_path, settings_path + ".bak-" +
             datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

def entry(command, status, matcher=None):
    group = {
        "hooks": [{
            "type": "command",
            "command": command,
            "async": True,
            "timeout": 120,
            "statusMessage": status,
        }],
    }
    if matcher:
        group["matcher"] = matcher
    return group


hooks = settings.setdefault("hooks", {})


def is_skillz(group):
    return any(
        "skillz" in h.get("command", "")
        and ("/hook.sh" in h.get("command", "") or "/sync.sh" in h.get("command", ""))
        for h in group.get("hooks", [])
    )


# Drop every previous skillz registration before adding: the repo may have
# moved, and older installs registered this on PostToolUse, which committed
# once per edit rather than once per turn.
for event in ("PostToolUse", "Stop", "SessionStart"):
    groups = hooks.get(event)
    if groups is None:
        continue
    groups[:] = [group for group in groups if not is_skillz(group)]
    if not groups:
        del hooks[event]

hooks.setdefault("Stop", []).append(entry(shlex.quote(hook_cmd), "syncing skillz"))
# A compact carries on the same session, so it does not pull.
hooks.setdefault("SessionStart", []).append(
    entry(shlex.quote(hook_cmd) + " --pull", "pulling skillz", "startup|resume|clear"))

with open(settings_path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")

print(f"  hooks registered in {settings_path}")
PY

echo "  auto-sync: edits under $REPO commit and push once per turn, and each session starts with a pull"
