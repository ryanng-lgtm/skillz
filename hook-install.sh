#!/usr/bin/env bash
#
# Register the auto-sync hook in ~/.claude/settings.json.
#
# The hook runs on Stop, so a session syncs once when it finishes answering.
# It ran on PostToolUse until it turned a thirteen-edit session into thirteen
# commits and pushes; sync.sh sweeps the whole repo with `git add -A`, so
# firing per edit bought nothing that firing per turn does not.
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
import json, sys, shutil, datetime

settings_path, hook_cmd = sys.argv[1], sys.argv[2]

with open(settings_path) as fh:
    settings = json.load(fh)

shutil.copy2(settings_path, settings_path + ".bak-" +
             datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

entry = {
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "async": True,
        "timeout": 120,
        "statusMessage": "syncing skillz",
    }],
}

hooks = settings.setdefault("hooks", {})


def is_skillz(group):
    return any(
        "skillz" in h.get("command", "")
        and h.get("command", "").endswith(("hook.sh", "sync.sh"))
        for h in group.get("hooks", [])
    )


# Drop every previous skillz registration before adding: the repo may have
# moved, and older installs registered this on PostToolUse, which committed
# once per edit rather than once per turn.
for event in ("PostToolUse", "Stop"):
    groups = hooks.get(event)
    if groups is None:
        continue
    groups[:] = [group for group in groups if not is_skillz(group)]
    if not groups:
        del hooks[event]

hooks.setdefault("Stop", []).append(entry)

with open(settings_path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")

print(f"  hook registered in {settings_path}")
PY

echo "  auto-sync: edits under $REPO commit and push once per turn"
