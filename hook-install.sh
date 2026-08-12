#!/usr/bin/env bash
#
# Register the auto-sync hook in ~/.claude/settings.json.
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

python3 - "$SETTINGS" "$REPO/hook.sh" <<'PY'
import json, sys, shutil, datetime

settings_path, hook_cmd = sys.argv[1], sys.argv[2]

with open(settings_path) as fh:
    settings = json.load(fh)

shutil.copy2(settings_path, settings_path + ".bak-" +
             datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

entry = {
    "matcher": "Write|Edit|NotebookEdit",
    "hooks": [{
        "type": "command",
        "command": hook_cmd,
        "async": True,
        "timeout": 120,
        "statusMessage": "syncing skillz",
    }],
}

hooks = settings.setdefault("hooks", {})
post = hooks.setdefault("PostToolUse", [])

# Drop any previous skillz registration (the repo may have moved) before adding.
post[:] = [
    group for group in post
    if not any("skillz" in h.get("command", "") and h.get("command", "").endswith("hook.sh")
               for h in group.get("hooks", []))
]
post.append(entry)

with open(settings_path, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")

print(f"  hook registered in {settings_path}")
PY

echo "  auto-sync: edits under $REPO now commit and push automatically"
