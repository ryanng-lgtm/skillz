import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "build-index.py"
CONTENTS = "## Contents\n"


def doc(body, tags="[svc, deploy]"):
    return (
        f'---\ndescription: "A doc."\ntags: {tags}\n'
        f"status: current\nupdated: 2026-10-28\n---\n\n# Doc\n\n{body}\n"
    )


class ObsidianVaultTests(unittest.TestCase):
    """A docs dir inside an Obsidian vault, checked the way Obsidian resolves links."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)
        self.docs = self.vault / "GO Backend"
        files = {
            ".obsidian/app.json": "{}",
            "assets/diagram.png": "",
            "bin/Runbook": "",  # a binary named like a note: not a match for [[Runbook]]
            "Other/Runbook.md": "# Runbook\n",
            "GO Backend/INDEX.md": "# Docs\n\n" + CONTENTS,
            "GO Backend/svc/INDEX.md": '---\ndescription: "Services."\ntags: [svc]\n---\n\n' + CONTENTS,
            "GO Backend/svc/001 Overview.md": doc("Service overview."),
            "GO Backend/db/INDEX.md": '---\ndescription: "Databases."\ntags: [db]\n---\n\n' + CONTENTS,
            "GO Backend/db/001 Overview.md": doc("Database overview.", "[db]"),
        }
        for rel, text in files.items():
            path = self.vault / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, body, tags="[svc, deploy]"):
        (self.docs / "svc" / "002 Deploy.md").write_text(doc(body, tags))
        result = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--root", str(self.docs)],
            capture_output=True, text=True,
        )
        return result.returncode, result.stdout

    def test_links_obsidian_resolves_pass(self):
        code, out = self.run_script(
            "\n".join([
                "[[svc/001 Overview|overview]] and [[db/001 Overview#Tables]].",
                "[[Runbook]], [[Other/Runbook]], [[#Rollback]], ![[diagram.png]].",
                "| table | [[Runbook\\|runbook]] |",
                "[same folder](001%20Overview.md), [vault path](Other/Runbook.md),",
                "[shortest](Runbook.md), [relative](../db/001%20Overview.md#Tables).",
            ]),
            tags="\n  - svc\n  - deploy",
        )
        self.assertEqual(code, 0, out)

    def test_broken_links_and_empty_properties_reported(self):
        # Obsidian writes an empty property as a bare key.
        (self.docs / "svc" / "003 Empty.md").write_text(
            "---\ndescription:\ntags:\n  - svc\nstatus: current\nupdated: 2026-10-28\n---\n"
        )
        code, out = self.run_script(
            "[[Missing Note]], [[001 Overview]], [gone](Gone.md), ![[nope.png]]."
        )
        self.assertEqual(code, 1)
        problems = [l for l in out.splitlines() if l.startswith("PROBLEM:")]
        self.assertEqual(len(problems), 5, out)
        for needle in (
            "[[Missing Note]]", "001 Overview matches 2 files", "Gone.md", "[[nope.png]]",
            "003 Empty.md: frontmatter missing 'description'",
        ):
            self.assertIn(needle, out)

    def test_contents_table_is_set_off_and_prose_after_it_kept(self):
        index = self.docs / "svc" / "INDEX.md"
        index.write_text(index.read_text() + "## Later\n\nHand-written notes.\n")
        code, out = self.run_script("Deploy steps.")
        self.assertEqual(code, 0, out)
        text = index.read_text()
        # Obsidian renders a table only when blank lines separate it from its neighbours.
        section = text.split("## Contents\n", 1)[1]
        self.assertTrue(section.startswith("\n|"), section)
        table, after = section[1:].split("\n\n", 1)
        self.assertIn("002 Deploy", table)
        self.assertTrue(all(line.startswith("|") for line in table.splitlines()), table)
        self.assertEqual(after, "## Later\n\nHand-written notes.\n")
        check = subprocess.run([sys.executable, "-I", str(SCRIPT), "--root", str(self.docs), "--check"],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout)

    def test_plain_docs_dir_resolves_markdown_links_relatively(self):
        (self.vault / ".obsidian" / "app.json").unlink()
        (self.vault / ".obsidian").rmdir()
        (self.docs / "db" / "schema.sql").write_text("")
        code, out = self.run_script("[same folder](001%20Overview.md) and [other area](schema.sql).")
        self.assertEqual(code, 1)
        problems = [l for l in out.splitlines() if l.startswith("PROBLEM:")]
        self.assertEqual(problems, ["PROBLEM: svc/002 Deploy.md: broken link schema.sql"], out)


if __name__ == "__main__":
    unittest.main()
