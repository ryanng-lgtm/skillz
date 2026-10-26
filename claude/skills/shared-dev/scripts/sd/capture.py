"""A time-boxed live capture: streamd on one venue, a few symbols, minutes not hours.

The venue's block comes from the bare-metal streamd config in
streamd-cex-playbook; Kafka settings come from the bundle's rendered
streamd-bitget config. The capture stops itself after `seconds`.
"""

import json
import re
from pathlib import Path

import yaml

from sd import common
from sd.compose import _rewrite_prefix, _write_secret

DEFAULT_SECONDS = 180
PLAYBOOK = Path.home() / "Documents" / "GitLab" / "meta_repo" / "streamd-cex-playbook" / "configs" / "streamd.yaml.j2"
LOCAL_CONNECTIONS = 2
_HEADER = r"^\S+_exchange_config:(\s*&\S+)?\s*$"  # headers carry YAML anchors


def venue_block(venue, playbook=PLAYBOOK):
    """The venue's exchange config from the playbook's `<x>_exchange_config:` blocks."""
    lines = Path(playbook).read_text().splitlines()
    in_configs = False
    for i, line in enumerate(lines):
        if re.match(_HEADER, line):
            in_configs = True
            continue
        if in_configs and re.match(rf"^  {re.escape(venue)}:\s*$", line):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= 2:
                    break
                body.append(nxt[4:])
            text = re.sub(r"\{\{.*?\}\}", "templated", "\n".join(body))
            text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("{%"))
            return yaml.safe_load(text)
        if re.match(r"^\S", line):
            in_configs = bool(re.match(_HEADER, line))
    raise KeyError(f"no {venue} block in {playbook}")


def config(venue, symbols, prefix, run_dir, *, base=None, playbook=PLAYBOOK):
    """Write run_dir/config/streamd-<venue>.yaml: one venue, these symbols, the run's topic prefix."""
    base = base or common.SHARED_DEV / "config" / "streamd-bitget.yaml"
    cfg = json.loads(Path(base).read_text())
    block = venue_block(venue, playbook)
    for key in ("connection_limit", "connection_limit_total"):
        if key in block:
            block[key] = min(block[key], LOCAL_CONNECTIONS)
    block["symbol_filters"] = {t: {"whitelisted_symbols": list(symbols)} for t in block.get("needed_types", [])}
    cfg["cex"]["exchange_configs"] = {venue: block}
    cfg["cex"]["kafka"]["topic"] = "dev.ryan.normalized"
    cfg = _rewrite_prefix(cfg, prefix)
    path = Path(run_dir) / "config" / f"streamd-{venue}.yaml"
    _write_secret(path, cfg)
    return path


def service(venue, symbols, seconds, streamd_bin, config_path):
    """The compose service for the capture; it exits on its own after `seconds`."""
    return {
        "image": "kiyotaka-local-metadata-instrument",
        "platform": "linux/arm64",
        "restart": "no",
        "pull_policy": "never",
        "cpus": 2,
        "mem_limit": "2g",
        "depends_on": {"metadata-instrument": {"condition": "service_healthy"}},
        "volumes": [f"{streamd_bin}:/shared-dev/streamd:ro", f"{config_path}:/config.yaml:ro"],
        "command": ["timeout", "--signal=TERM", "--kill-after=15s", f"{seconds}s", "/shared-dev/streamd", "-c",
                    "/config.yaml", "cex"],
        "labels": {"shared-dev.capture.symbols": ",".join(symbols)},
    }


def writer_tables(needed_types):
    """Tables tsdb-write fills for streamd's needed types; the run copies them empty first.

    The guard role is the backstop: a write to a table not copied fails loudly
    in tsdb-write's log, and the skill copies it and captures again.
    """
    return [t.lower() for t in needed_types]


def plan_capture(venue, symbols, seconds, streamd_bin, prefix, run_dir, **kw):
    """The `capture` argument compose.render takes."""
    path = config(venue, symbols, prefix, run_dir, **kw)
    return {"service_name": f"streamd-{venue}", "service": service(venue, symbols, seconds, streamd_bin, path),
            "config": path}
