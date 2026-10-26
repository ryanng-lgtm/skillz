import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import yaml

from sd import compose

BASE = {
    "name": "kiyotaka-shared-dev",
    "services": {
        "metadata-instrument": {
            "image": "kiyotaka-local-metadata-instrument", "mem_limit": "2g",
            "volumes": ["./config/metadata-instrument.yaml:/config.yaml:ro",
                        "./bin/linux-arm64/metadata-instrument:/shared-dev/metadata-instrument:ro"],
            "ports": ["127.0.0.1:18092:8092", "127.0.0.1:8092:8092"],
        },
        "tsdb-read": {
            "image": "kiyotaka-local-tsdb-gateway", "mem_limit": "2g",
            "depends_on": {"metadata-instrument": {"condition": "service_healthy"}},
            "volumes": ["./config/tsdb-gateway-reader.yaml:/config.yaml:ro", "./schemas/gateway-reader.yaml:/schema.yaml:ro",
                        "./bin/linux-arm64/tsdb-gateway-bitget:/shared-dev/tsdb-gateway:ro"],
            "command": ["/shared-dev/tsdb-gateway", "-c", "/config.yaml", "-s", "/schema.yaml", "read"],
            "ports": ["127.0.0.1:18080:4080", "127.0.0.1:4080:4080"],
        },
        "tsdb-api": {
            "image": "kiyotaka-local-tsdb-gateway", "mem_limit": "2g",
            "depends_on": {"metadata-instrument": {"condition": "service_healthy"}},
            "volumes": ["./config/tsdb-gateway-reader.yaml:/config.yaml:ro", "./schemas/gateway-reader.yaml:/schema.yaml:ro",
                        "./bin/linux-arm64/tsdb-gateway-bitget:/shared-dev/tsdb-gateway:ro"],
            "command": ["/shared-dev/tsdb-gateway", "-c", "/config.yaml", "-s", "/schema.yaml", "api"],
            "ports": ["127.0.0.1:4084:4080"],
        },
        "tsdb-registry": {
            "image": "kiyotaka-local-tsdb-gateway", "mem_limit": "2g",
            "depends_on": {"metadata-instrument": {"condition": "service_healthy"}},
            "volumes": ["./config/tsdb-gateway-writer.yaml:/config.yaml:ro", "./schemas/gateway-writer.yaml:/schema.yaml:ro",
                        "./bin/linux-arm64/tsdb-gateway:/shared-dev/tsdb-gateway:ro"],
            "command": ["/shared-dev/tsdb-gateway", "-c", "/config.yaml", "-s", "/schema.yaml", "registry"],
        },
        "stream-deduplicated": {
            "image": "kiyotaka-local-stream-deduplicated", "mem_limit": "2g",
            "volumes": ["./config/stream-deduplicated.yaml:/config.yaml:ro"],
            "command": ["stream-deduplicated", "-c", "/config.yaml"],
        },
    },
}
URL = "postgres://dev:pw@100.82.235.54:25432/data?sslmode=disable"
READER = {"timescaledb": {k: {"url": URL + "&application_name=ryan-shared-reader&options=-c%20statement_timeout%3D15000"}
                          for k in ("primary", "secondary", "free_secondary")},
          "kafka": {"consumer": {"options": {"group.id": "dev.ryan.tsdb-registry", "bootstrap.servers": "100.82.235.54:19092"},
                                 "topics": ["dev.ryan.deduplicated"]}}}
META = {"postgresql": {"primary": {"url": "postgres://env_ryan:pw@100.82.235.54:5433/meta_ryan?sslmode=disable"}}}
DEDUP = {"kafka": {"consumer": {"options": {"group.id": "dev.ryan.dedup"}, "topics": ["dev.ryan.normalized"]}}}


def plan(*services):
    return {"services": list(services), "builds": {s: {} for s in services}, "cjob": False}


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.sd = root / "shared-dev"
        (self.sd / "config").mkdir(parents=True)
        (self.sd / "compose.yaml").write_text(yaml.safe_dump(BASE))
        (self.sd / "config" / "tsdb-gateway-reader.yaml").write_text(json.dumps(READER))
        (self.sd / "config" / "tsdb-gateway-writer.yaml").write_text(json.dumps(READER))
        (self.sd / "config" / "metadata-instrument.yaml").write_text(json.dumps(META))
        (self.sd / "config" / "stream-deduplicated.yaml").write_text(json.dumps(DEDUP))
        self.run_dir = root / "run"
        patcher = patch.object(compose, "SHARED_DEV", self.sd)
        patcher.start()
        self.addCleanup(patcher.stop)

    def render(self, p, binaries=None, **kw):
        args = dict(project="kiyotaka-shared-dev", offset=0, prefix="dev.ryan.", schema="sd_b", password="guardpw",
                    run_dir=self.run_dir)
        args.update(kw)
        out = compose.render(p, binaries or {}, **args)
        return json.loads(out.read_text())

    def test_render_only_planned_services(self):
        doc = self.render(plan("metadata-instrument", "tsdb-read", "tsdb-api"))
        self.assertEqual(sorted(doc["services"]), ["metadata-instrument", "tsdb-api", "tsdb-read"])
        self.assertEqual(doc["name"], "kiyotaka-shared-dev")

    def test_render_absolute_paths_and_registry_4g(self):
        binary = Path("/run/bin/tsdb-gateway")
        doc = self.render(plan("metadata-instrument", "tsdb-registry"), {"tsdb-registry": binary})
        reg = doc["services"]["tsdb-registry"]
        self.assertEqual(reg["mem_limit"], "4g")
        self.assertIn(f"{binary}:/shared-dev/tsdb-gateway:ro", reg["volumes"])
        self.assertIn(f"{self.run_dir / 'config' / 'tsdb-registry.yaml'}:/config.yaml:ro", reg["volumes"])
        meta_mounts = doc["services"]["metadata-instrument"]["volumes"]
        self.assertIn(f"{self.sd}/bin/linux-arm64/metadata-instrument:/shared-dev/metadata-instrument:ro", meta_mounts)

    def test_render_offsets_ports(self):
        doc = self.render(plan("metadata-instrument", "tsdb-read"), offset=1000)
        self.assertIn("127.0.0.1:5080:4080", doc["services"]["tsdb-read"]["ports"])
        self.assertIn("127.0.0.1:19080:4080", doc["services"]["tsdb-read"]["ports"])

    def test_render_prefix_rewrites_kafka(self):
        self.render(plan("metadata-instrument", "tsdb-read", "stream-deduplicated"), prefix="dev.ryan.x.")
        reader = json.loads((self.run_dir / "config" / "tsdb-read.yaml").read_text())
        opts = reader["kafka"]["consumer"]["options"]
        self.assertEqual(opts["group.id"], "dev.ryan.x.tsdb-registry")
        self.assertEqual(opts["bootstrap.servers"], "100.82.235.54:19092")
        self.assertEqual(reader["kafka"]["consumer"]["topics"], ["dev.ryan.x.deduplicated"])

    def test_render_config_url_guarded(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.render(plan("metadata-instrument", "tsdb-read"))
        self.assertEqual(buf.getvalue(), "")
        path = self.run_dir / "config" / "tsdb-read.yaml"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        url = json.loads(path.read_text())["timescaledb"]["primary"]["url"]
        parts = urlsplit(url)
        self.assertEqual(parts.username, "sd_guard")
        query = parse_qs(parts.query)
        self.assertIn("-c search_path=sd_b,public", query["options"][0])
        self.assertIn("statement_timeout=15000", query["options"][0])
        self.assertEqual(query["application_name"], ["ryan-shared-reader"])

    def test_render_metadata_statement_timeout(self):
        self.render(plan("metadata-instrument"))
        url = json.loads((self.run_dir / "config" / "metadata-instrument.yaml").read_text())["postgresql"]["primary"]["url"]
        self.assertIn("statement_timeout=120000", parse_qs(urlsplit(url).query)["options"][0])
        self.assertEqual(urlsplit(url).username, "env_ryan")

    def test_render_dedup_runs_mounted_binary(self):
        binary = Path("/run/bin/stream-deduplicated")
        doc = self.render(plan("stream-deduplicated"), {"stream-deduplicated": binary})
        dedup = doc["services"]["stream-deduplicated"]
        self.assertEqual(dedup["command"][0], "/shared-dev/stream-deduplicated")
        self.assertIn(f"{binary}:/shared-dev/stream-deduplicated:ro", dedup["volumes"])

    def test_render_main_reader(self):
        doc = self.render(plan("metadata-instrument", "tsdb-read"),
                          main_reader=(Path("/bin/main/tsdb-gateway"), "public", Path("/bin/main/schema.yaml")))
        main = doc["services"]["tsdb-read-main"]
        self.assertIn("127.0.0.1:4180:4080", main["ports"])
        self.assertIn("/bin/main/tsdb-gateway:/shared-dev/tsdb-gateway:ro", main["volumes"])
        url = json.loads((self.run_dir / "config" / "tsdb-read-main.yaml").read_text())["timescaledb"]["primary"]["url"]
        self.assertIn("search_path=public", parse_qs(urlsplit(url).query)["options"][0])


if __name__ == "__main__":
    unittest.main()
