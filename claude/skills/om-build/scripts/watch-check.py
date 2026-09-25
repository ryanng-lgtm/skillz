#!/usr/bin/env python3
"""Read-only watch continuity checks around an om-hosted installation.

Receipts contain definition hashes, status codes and paths, never watch prompts
or credentials. This does not arm, resume, repair, replay or execute a watch.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


def read_json_command(binary, home, *args):
    path = Path(home)
    if path.parent.name != "accounts":
        raise ValueError("daemon home does not use the account layout")
    result = subprocess.run(
        [binary, *args, "--format", "json"],
        env={**os.environ, "OM_HOME": str(path.parent.parent), "OM_ACCOUNT": path.name},
        capture_output=True, text=True, timeout=45, check=True,
    )
    return json.loads(result.stdout)


def snapshot(binary, health_url):
    with urllib.request.urlopen(health_url, timeout=10) as response:
        health = json.load(response)
    home = health["om_home"]
    if not isinstance(home, str) or not Path(home).is_absolute():
        raise ValueError("daemon did not report an absolute OM home")
    listing = read_json_command(binary, home, "watch", "list")
    if any(listing.get(k) for k in ("unreadable", "skipped_specs", "syncing")):
        raise ValueError("watch inventory is unreadable or still syncing")
    watches = {}
    for watch in listing["watches"]:
        watch_id = watch["id"]
        spec = read_json_command(binary, home, "watch", "show", watch_id)["spec"]
        # Timestamps may change during a compatible migration; behavior must not.
        definition = {k: v for k, v in spec.items() if k not in ("updated_at", "spec_version")}
        digest = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        status = watch["status"]
        watches[watch_id] = {
            "enabled": watch["enabled"], "definition": digest,
            "parts": {key: value.get("state") for key, value in status.items()
                      if key in ("source", "steps", "channel", "share") and value},
            "faults": status.get("faults", []),
        }
    return {"home": home, "version": health["version"], "pid": health["pid"],
            "watches": watches, "lanes": health.get("lanes", {}),
            "channels": {c["surface"]: c["state"] for c in health.get("channels", [])}}


def differences(before, after, version=None, restarted=False):
    errors = []
    if before["home"] != after["home"]:
        errors.append("daemon changed OM home")
    if version and after["version"] != version:
        errors.append(f"daemon version is {after['version']}; expected {version}")
    if restarted and before["pid"] == after["pid"]:
        errors.append("daemon still has its pre-install PID")
    if before["watches"].keys() != after["watches"].keys():
        errors.append("watch inventory changed")
    for watch_id, old in before["watches"].items():
        new = after["watches"].get(watch_id)
        if new is None:
            errors.append(f"{watch_id}: missing")
            continue
        if old["definition"] != new["definition"]:
            errors.append(f"{watch_id}: definition changed")
        if old["enabled"] != new["enabled"]:
            errors.append(f"{watch_id}: enabled/paused state changed")
        if not old["enabled"]:
            continue
        for part, state in old["parts"].items():
            if state == "working" and new["parts"].get(part) != "working":
                errors.append(f"{watch_id}: {part} stopped working")
        if any(fault not in old["faults"] for fault in new["faults"]):
            errors.append(f"{watch_id}: new watch fault; run om watch show {watch_id}")
    for name in ("alerts", "schedules", "stream-polls"):
        if name in before["lanes"]:
            lane = after["lanes"].get(name, {})
            if not lane.get("last_pass_at") or lane.get("last_error"):
                errors.append(f"daemon lane {name} has not completed a healthy pass")
    for channel, state in before["channels"].items():
        if state == "healthy" and after["channels"].get(channel) != "healthy":
            errors.append(f"{channel}: bot connection did not recover")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "verify", "home"))
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--binary", default="om")
    parser.add_argument("--health", default="http://127.0.0.1:31337/healthz")
    parser.add_argument("--version")
    parser.add_argument("--restarted", action="store_true")
    args = parser.parse_args()
    if args.mode == "home":
        print(json.loads(args.receipt.read_text())["home"])
        return
    current = snapshot(args.binary, args.health)
    if args.mode == "capture":
        # The enclosing receipt directory is private; enforce file mode too.
        with os.fdopen(os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
            json.dump(current, file, indent=2)
    else:
        errors = differences(json.loads(args.receipt.read_text()), current, args.version, args.restarted)
        if errors:
            for error in errors:
                print(f"watch check: {error}", file=sys.stderr)
            raise SystemExit(1)
    enabled = sum(w["enabled"] for w in current["watches"].values())
    print(f"watches: {enabled} enabled, {len(current['watches']) - enabled} paused; {args.mode} passed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        # A failed CLI may emit private data on stderr: never echo its output.
        print(f"watch check unavailable: {type(error).__name__}", file=sys.stderr)
        sys.exit(1)
