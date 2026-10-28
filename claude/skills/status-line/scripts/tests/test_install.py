import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "install.py"


class InstallTests(unittest.TestCase):
    def test_replaces_only_status_line_and_only_when_forced(self):
        with tempfile.TemporaryDirectory() as home:
            settings = Path(home) / "settings.json"
            before = {"permissions": {"allow": ["Bash(git status)"]},
                      "statusLine": {"type": "command", "command": "other"}}
            settings.write_text(json.dumps(before))
            env = {**os.environ, "CLAUDE_CONFIG_DIR": home}

            def run(*args):
                return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                                      env=env, capture_output=True, text=True)

            refused = run()
            self.assertEqual(refused.returncode, 1)
            self.assertEqual(json.loads(settings.read_text()), before)

            forced = run("--force")
            self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
            after = json.loads(settings.read_text())
            self.assertEqual(after["permissions"], before["permissions"])
            self.assertEqual(after["statusLine"]["command"],
                             f"{home}/skills/status-line/scripts/statusline.sh")
            backups = list(Path(home).glob("settings.json.bak-*"))
            self.assertEqual([json.loads(b.read_text()) for b in backups], [before])

            self.assertEqual(run().returncode, 0)


if __name__ == "__main__":
    unittest.main()
