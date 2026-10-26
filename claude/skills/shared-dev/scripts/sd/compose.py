"""A standalone compose file and configs for one run.

Each run gets its own compose.json built from the bundle's compose.yaml,
holding only the planned services, with the run's binaries, schemas and
configs mounted. Nothing is written into ~/.config/shared-dev.
"""

import copy
import json
from pathlib import Path

import yaml

from sd import common
from sd.common import patch_pg_url
from sd.plan import MAP

SHARED_DEV = common.SHARED_DEV
GUARD_ROLE = "sd_guard"
MAIN_READER_PORTS = 100


def _abs(mount):
    host, sep, rest = mount.partition(":")
    if host.startswith("./"):
        host = str(SHARED_DEV / host[2:])
    return f"{host}{sep}{rest}"


def _target(mount):
    return mount.split(":")[1]


def _set_mount(volumes, target, host, mode="ro"):
    kept = [v for v in volumes if _target(v) != target]
    return [*kept, f"{host}:{target}:{mode}"]


def _shift(port, offset):
    parts = port.split(":")
    parts[-2] = str(int(parts[-2]) + offset)
    return ":".join(parts)


def _rewrite_prefix(node, prefix):
    if isinstance(node, dict):
        return {k: _rewrite_prefix(v, prefix) for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite_prefix(v, prefix) for v in node]
    if isinstance(node, str) and node.startswith("dev.ryan."):
        return prefix + node[len("dev.ryan."):]
    return node


def _merge(base, extra):
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value)
        else:
            base[key] = value
    return base


def _config(base_mount, *, search_path, password, prefix, patch=None):
    """The base rendered config with the run's DB role, search_path, Kafka prefix and patch."""
    cfg = json.loads(Path(_abs(base_mount).split(":")[0]).read_text())
    if patch:
        _merge(cfg, patch)
    for key in ("primary", "secondary", "free_secondary"):
        entry = cfg.get("timescaledb", {}).get(key)
        if entry and "url" in entry:
            entry["url"] = patch_pg_url(entry["url"], user=GUARD_ROLE, password=password,
                                        settings={"search_path": search_path})
    meta = cfg.get("postgresql", {}).get("primary")
    if meta and "url" in meta:
        meta["url"] = patch_pg_url(meta["url"], settings={"statement_timeout": "120000"})
    if prefix != "dev.ryan.":
        cfg = _rewrite_prefix(cfg, prefix)
    return cfg


def _write_secret(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)
    path.chmod(0o600)
    path.write_text(json.dumps(doc, indent=2))


def render(plan, binaries, *, project, offset, prefix, schema, password, run_dir, schemas=None, main_reader=None,
           capture=None, exposed=None, patches=None):
    """Write run_dir/compose.json and run_dir/config/<service>.yaml; return the compose path.

    main_reader is (binary, search schema, schema yaml) for a tsdb-read-main
    service on host ports +100, built from main, for side-by-side probes.
    capture is {"service": dict, "config": Path} from capture.service().
    exposed is the run's exposure schema (views over new prod clones); both
    readers search it, so main and branch probes read the same data.
    patches maps a service to non-secret config keys merged into its config
    (a branch's new settings); topic names in them follow the run's prefix.
    """
    patches = patches or {}
    base = yaml.safe_load((SHARED_DEV / "compose.yaml").read_text())["services"]
    run_dir = Path(run_dir)
    schemas = schemas or {}
    # streamd has no bundle service: the capture service runs it.
    wanted = [s for s in dict.fromkeys([*plan["services"], *plan.get("builds", {})]) if s in base]
    services = {}

    def build(name, source, *, binary, schema_yaml, search_path, port_shift):
        svc = copy.deepcopy(base[source])
        volumes = [_abs(v) for v in svc.get("volumes", [])]
        config_mount = next(v for v in base[source]["volumes"] if _target(v) == "/config.yaml")
        cfg_path = run_dir / "config" / f"{name}.yaml"
        _write_secret(cfg_path, _config(config_mount, search_path=search_path, password=password, prefix=prefix,
                                        patch=patches.get(name)))
        volumes = _set_mount(volumes, "/config.yaml", cfg_path)
        bin_name = MAP["binaries"][source]["name"]
        if binary:
            volumes = _set_mount(volumes, f"/shared-dev/{bin_name}", binary)
            if source == "stream-deduplicated":
                svc["command"] = [f"/shared-dev/{bin_name}", "-c", "/config.yaml"]
        if schema_yaml:
            volumes = _set_mount(volumes, "/schema.yaml", schema_yaml)
        svc["volumes"] = volumes
        svc["ports"] = [_shift(p, port_shift) for p in svc.get("ports", [])]
        if name == "tsdb-registry":
            svc["mem_limit"] = "4g"
        if "depends_on" in svc:
            svc["depends_on"] = {d: c for d, c in svc["depends_on"].items() if d in wanted}
        services[name] = svc

    for name in wanted:
        build(name, name, binary=binaries.get(name), schema_yaml=schemas.get(name),
              search_path=",".join([schema, *([exposed] if exposed else []), "public"]), port_shift=offset)
    if main_reader:
        binary, search, schema_yaml = main_reader
        build("tsdb-read-main", "tsdb-read", binary=binary, schema_yaml=schema_yaml,
              search_path=",".join([*([] if search == "public" else [search]), *([exposed] if exposed else []),
                                    "public"]), port_shift=offset + MAIN_READER_PORTS)
    if capture:
        services[capture["service_name"]] = capture["service"]

    path = run_dir / "compose.json"
    path.write_text(json.dumps({"name": project, "services": services}, indent=2))
    return path
