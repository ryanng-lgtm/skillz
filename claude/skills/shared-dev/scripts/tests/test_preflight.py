import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

PREFLIGHT = Path(__file__).parents[1] / "preflight.sh"


def setup(root, *, docker="ok", ps="", backing="PASS TimescaleDB", ts_ip="100.82.235.54", cfg_ip="100.82.235.54"):
    sd = root / "shared-dev"
    (sd / ".venv" / "bin").mkdir(parents=True)
    (sd / "config").mkdir()
    (sd / "config" / "tsdb-gateway-reader.yaml").write_text(
        json.dumps({"registry": {"kafka": {"bootstrap_servers": f"{cfg_ip}:19092"}}})
    )
    (sd / "check_connections.py").write_text("")
    py = sd / ".venv" / "bin" / "python"
    py.write_text(f"#!/bin/sh\nprintf '%s\\n' '{backing}'\n")
    bin_dir = root / "stubbin"
    bin_dir.mkdir()
    docker_body = {
        "ok": 'case "$1" in info) echo 8319238144 ;; ps) printf "%s" "$STUB_PS" ;; esac',
        "hang": "sleep 60",
    }[docker]
    (bin_dir / "docker").write_text(f"#!/bin/sh\n{docker_body}\n")
    peers = {"p": {"HostName": "sean-trontal", "TailscaleIPs": [ts_ip], "Online": True}}
    (bin_dir / "tailscale").write_text(f"#!/bin/sh\necho '{json.dumps({'Peer': peers})}'\n")
    for f in [py, *bin_dir.iterdir()]:
        f.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "SHARED_DEV": str(sd), "STUB_PS": ps}
    return env


def run(env, *args):
    return subprocess.run(["bash", str(PREFLIGHT), *args], env=env, capture_output=True, text=True, timeout=90)


class PreflightTests(unittest.TestCase):
    def test_preflight_all_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(setup(Path(tmp)), "--need-mib", "6000")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            for check in ("docker", "forbidden", "backing", "memory"):
                self.assertIn(f"ok {check}", proc.stdout)

    def test_preflight_docker_hang_fails_fast(self):
        with tempfile.TemporaryDirectory() as tmp:
            start = time.monotonic()
            proc = run(setup(Path(tmp), docker="hang"))
            self.assertLess(time.monotonic() - start, 25)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("FAIL docker", proc.stdout)

    def test_preflight_forbidden_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(setup(Path(tmp), ps="timescaledb-1\tzmeta_local\n"))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("FAIL forbidden", proc.stdout)
            self.assertIn("zmeta_local", proc.stdout)

    def test_preflight_ip_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(setup(Path(tmp), backing="FAIL TimescaleDB: OperationalError", ts_ip="100.1.2.3"))
            self.assertEqual(proc.returncode, 1)
            self.assertIn("FAIL tailscale", proc.stdout)
            self.assertIn("100.1.2.3", proc.stdout)
            self.assertIn("100.82.235.54", proc.stdout)

    def test_preflight_memory_short(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run(setup(Path(tmp)), "--need-mib", "9000")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("FAIL memory", proc.stdout)


if __name__ == "__main__":
    unittest.main()
