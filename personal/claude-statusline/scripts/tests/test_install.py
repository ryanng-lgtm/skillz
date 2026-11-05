import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "install.py"
# The skill's command under its old name. Split so check.py, which reports a
# ~/.claude/skills path that does not exist, passes over this deliberate one.
OLD_COMMAND = "~/.claude/skills/" + "status-line/scripts/statusline.sh"


def migrate(env):
    return subprocess.run([sys.executable, "-I", str(SCRIPT), "--migrate"],
                          env=env, capture_output=True, text=True)


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
                             f"{home}/skills/claude-statusline/scripts/statusline.sh")
            backups = list(Path(home).glob("settings.json.bak-*"))
            self.assertEqual([json.loads(b.read_text()) for b in backups], [before])

            self.assertEqual(run().returncode, 0)

    def test_migrate_repoints_old_path(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / ".claude"
            config.mkdir()
            env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CONFIG_DIR"}
            env["HOME"] = home
            want = "~/.claude/skills/claude-statusline/scripts/statusline.sh"
            settings = config / "settings.json"
            before = {"permissions": {"allow": ["Bash(git status)"]},
                      "statusLine": {"type": "command", "command": OLD_COMMAND}}
            settings.write_text(json.dumps(before))

            result = migrate(env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = json.loads(settings.read_text())
            self.assertEqual(after["statusLine"], {"type": "command", "command": want})
            self.assertEqual(after["permissions"], before["permissions"])
            backups = list(config.glob("settings.json.bak-*"))
            self.assertEqual([json.loads(b.read_text()) for b in backups], [before])

    def test_keeps_a_linked_private_settings_file(self):
        with tempfile.TemporaryDirectory() as home:
            # settings.json linked from a dotfiles folder, readable by its owner only.
            target = Path(home) / "dotfiles" / "settings.json"
            target.parent.mkdir()
            target.write_text(json.dumps({"permissions": {"allow": []}}))
            target.chmod(0o600)
            settings = Path(home) / "settings.json"
            settings.symlink_to(target)

            result = subprocess.run([sys.executable, "-I", str(SCRIPT)],
                                    env={**os.environ, "CLAUDE_CONFIG_DIR": home},
                                    capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(settings.is_symlink())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertIn("statusLine", json.loads(target.read_text()))

    def test_migrate_quotes_an_unquoted_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "my config"
            config.mkdir()
            env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config)}
            script = f"{config}/skills/claude-statusline/scripts/statusline.sh"
            settings = config / "settings.json"
            settings.write_text(json.dumps(
                {"statusLine": {"type": "command", "command": script}}))

            result = migrate(env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            command = json.loads(settings.read_text())["statusLine"]["command"]
            # The shell Claude Code runs it in sees one word: the script's path.
            words = subprocess.run(["sh", "-c", f"printf '%s\\n' {command}"],
                                   capture_output=True, text=True, check=True).stdout
            self.assertEqual(words, f"{script}\n")
            migrated = settings.read_bytes()

            again = migrate(env)

            self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
            self.assertEqual(settings.read_bytes(), migrated)
            self.assertEqual(len(list(config.glob("settings.json.bak-*"))), 1)

    def test_migrate_leaves_other_status_lines(self):
        with tempfile.TemporaryDirectory() as home:
            settings = Path(home) / "settings.json"
            settings.write_text(json.dumps(
                {"statusLine": {"type": "command", "command": "other"}}))
            original = settings.read_bytes()

            result = migrate({**os.environ, "CLAUDE_CONFIG_DIR": home})

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(settings.read_bytes(), original)
            self.assertEqual(list(Path(home).glob("settings.json.bak-*")), [])

    def test_migrate_without_status_line(self):
        with tempfile.TemporaryDirectory() as home:
            settings = Path(home) / "settings.json"
            settings.write_text(json.dumps({"permissions": {"allow": []}}))
            original = settings.read_bytes()

            result = migrate({**os.environ, "CLAUDE_CONFIG_DIR": home})

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(settings.read_bytes(), original)
            self.assertEqual(list(Path(home).glob("settings.json.bak-*")), [])


if __name__ == "__main__":
    unittest.main()
