import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
INSTALL = SCRIPTS / "install.py"
SAMPLE = SCRIPTS / "sample.json"
BEFORE = {"permissions": {"allow": ["Bash(git status)"]}}


class InstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.config = self.home / ".claude"
        self.config.mkdir()
        self.settings = self.config / "settings.json"
        self.script = self.config / "statusline.sh"
        self.env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
        self.env["HOME"] = str(self.home)
        self.env["CLAUDE_CONFIG_DIR"] = str(self.config)

    def run_install(self, *args):
        return subprocess.run([sys.executable, "-I", str(INSTALL), *args],
                              env=self.env, capture_output=True, text=True)

    def backups(self, name):
        return sorted(self.config.glob(f"{name}.bak-*"))

    def test_writes_script_and_only_status_line_key(self):
        self.settings.write_text(json.dumps(BEFORE))
        del self.env["CLAUDE_CONFIG_DIR"]

        result = self.run_install("--parts", "model,ctx")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = json.loads(self.settings.read_text())
        self.assertEqual(after["permissions"], BEFORE["permissions"])
        self.assertEqual(after["statusLine"],
                         {"type": "command", "command": "~/.claude/statusline.sh"})
        self.assertTrue(os.access(self.script, os.X_OK))
        self.assertIn('PARTS="model ctx"', self.script.read_text())

    def test_refuses_existing_status_line_without_force(self):
        before = {**BEFORE, "statusLine": {"type": "command", "command": "other"}}
        self.settings.write_text(json.dumps(before))
        original = self.settings.read_bytes()

        refused = self.run_install()

        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertFalse(self.script.exists())

        forced = self.run_install("--force")

        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        after = json.loads(self.settings.read_text())
        self.assertEqual(after["statusLine"]["command"], f"{self.config}/statusline.sh")
        self.assertEqual(after["permissions"], BEFORE["permissions"])
        self.assertEqual([json.loads(b.read_text()) for b in self.backups("settings.json")],
                         [before])

    def test_refuses_foreign_script_without_force(self):
        # A status line the user already points at <config>/statusline.sh.
        self.settings.write_text(json.dumps(
            {"statusLine": {"type": "command", "command": f"{self.config}/statusline.sh"}}))
        self.script.write_text("#!/bin/sh\necho mine\n")
        original = self.settings.read_bytes()

        refused = self.run_install()

        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertEqual(self.script.read_text(), "#!/bin/sh\necho mine\n")

        forced = self.run_install("--force")

        self.assertEqual(forced.returncode, 0, forced.stdout + forced.stderr)
        self.assertIn("PARTS=", self.script.read_text())
        self.assertEqual([b.read_text() for b in self.backups("statusline.sh")],
                         ["#!/bin/sh\necho mine\n"])
        self.assertEqual(self.settings.read_bytes(), original)

    def test_keeps_a_linked_private_settings_file(self):
        # settings.json linked from a dotfiles folder, readable by its owner only.
        target = self.home / "dotfiles" / "settings.json"
        target.parent.mkdir()
        target.write_text(json.dumps(BEFORE))
        target.chmod(0o600)
        self.settings.symlink_to(target)

        result = self.run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.settings.is_symlink())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertIn("statusLine", json.loads(target.read_text()))

    def test_quotes_a_config_path_with_spaces(self):
        config = self.home / "my config"
        config.mkdir()
        self.env["CLAUDE_CONFIG_DIR"] = str(config)
        script = f"{config}/statusline.sh"
        settings = config / "settings.json"
        # An earlier install stored the path unquoted; it is still this skill's.
        settings.write_text(json.dumps({"statusLine": {"type": "command", "command": script}}))

        result = self.run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        command = json.loads(settings.read_text())["statusLine"]["command"]
        # The shell Claude Code runs it in sees one word: the script's path.
        words = subprocess.run(["sh", "-c", f"printf '%s\\n' {command}"],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(words, f"{script}\n")

    def test_rerun_updates_script(self):
        self.settings.write_text(json.dumps(BEFORE))
        self.assertEqual(self.run_install("--parts", "model,ctx").returncode, 0)
        settings = self.settings.read_bytes()
        backups = self.backups("settings.json")

        result = self.run_install("--parts", "folder,branch")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PARTS="folder branch"', self.script.read_text())
        self.assertEqual(self.settings.read_bytes(), settings)
        self.assertEqual(self.backups("settings.json"), backups)

    @unittest.skipUnless(shutil.which("jq"), "statusline.sh needs jq")
    def test_prints_selected_parts_only(self):
        self.assertEqual(self.run_install("--parts", "model,ctx").returncode, 0)

        out = subprocess.run([str(self.script)], input=SAMPLE.read_text(),
                             capture_output=True, text=True, check=True).stdout

        self.assertIn("Opus 5.5", out)
        self.assertIn("ctx", out)
        self.assertNotIn("my-app", out)
        self.assertNotIn("5h", out)


if __name__ == "__main__":
    unittest.main()
