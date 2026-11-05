"""Read-only continuity contracts; no live daemon or external services."""

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("watch_check", Path(__file__).parents[1] / "watch-check.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "home": "/om/accounts/ryan", "version": "1", "pid": 10,
            "channels": {"discord": "healthy"},
            "lanes": {"schedules": {"last_pass_at": "now", "last_error": None}},
            "watches": {
                "active": {"enabled": True, "definition": "abc", "faults": [],
                           "parts": {"source": "working", "steps": "working", "channel": "working"}},
                "paused": {"enabled": False, "definition": "xyz", "faults": [],
                           "parts": {"source": "paused"}},
            },
        }
        self.after = copy.deepcopy(self.before)
        self.after.update(version="2", pid=11)

    def test_clean_restart_preserves_pauses(self):
        self.assertEqual(CHECK.differences(self.before, self.after, "2", True), [])

    def test_missing_watch(self):
        del self.after["watches"]["active"]
        self.assertIn("active: missing", CHECK.differences(self.before, self.after))

    def test_lost_authority(self):
        self.after["watches"]["active"]["parts"]["steps"] = "needs_approval"
        self.assertIn("active: steps stopped working", CHECK.differences(self.before, self.after))

    def test_paused_watch_must_not_resume(self):
        self.after["watches"]["paused"]["enabled"] = True
        self.assertIn("paused: enabled/paused state changed", CHECK.differences(self.before, self.after))

    def test_definition_change(self):
        self.after["watches"]["active"]["definition"] = "changed"
        self.assertIn("active: definition changed", CHECK.differences(self.before, self.after))

    def test_wrong_account_binary_or_no_restart(self):
        self.after.update(home="/other/accounts/guest", version="1", pid=10)
        self.assertEqual(len(CHECK.differences(self.before, self.after, "2", True)), 3)

    def test_lost_discord_connection(self):
        for state in ("disconnected", "starting", None):
            with self.subTest(state=state):
                self.after["channels"] = {"discord": state} if state else {}
                self.assertIn("discord: bot connection did not recover",
                              CHECK.differences(self.before, self.after))

    def test_new_fault_and_unstarted_scheduler(self):
        self.after["watches"]["active"]["faults"] = [{"code": "missing_file"}]
        self.after["lanes"] = {}
        self.assertEqual(len(CHECK.differences(self.before, self.after)), 2)

    def test_existing_fault_is_not_a_restart_regression(self):
        self.before["watches"]["active"]["faults"] = [{"code": "old"}]
        self.after["watches"]["active"]["faults"] = [{"code": "old"}]
        self.assertEqual(CHECK.differences(self.before, self.after), [])

    @patch.object(CHECK.subprocess, "run")
    def test_account_home_is_split_into_root_and_account(self, run):
        run.return_value.stdout = "{}"
        CHECK.read_json_command("/new/om", "/om/accounts/ryan", "watch", "list")
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["OM_HOME"], "/om")
        self.assertEqual(env["OM_ACCOUNT"], "ryan")
        self.assertEqual(run.call_args.args[0][0], "/new/om")


if __name__ == "__main__":
    unittest.main()
