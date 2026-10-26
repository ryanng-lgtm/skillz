import re
import unittest
from urllib.parse import parse_qs, urlsplit

from sd import common


class SlugTests(unittest.TestCase):
    def test_slug_long_and_odd_branches(self):
        self.assertRegex(common.slug("feat/ABC.def"), r"^[a-z0-9_]+$")
        long_a = "feat/" + "x" * 60 + "-alpha" + "y" * 50
        long_b = "feat/" + "x" * 60 + "-bravo" + "y" * 50
        self.assertLessEqual(len(common.slug(long_a)), 40)
        self.assertNotEqual(common.slug(long_a), common.slug(long_b))
        for branch in ("feat/ABC.def", long_a, "a" * 300):
            self.assertLessEqual(len(common.schema_name(branch).encode()), 63)
            self.assertTrue(common.schema_name(branch).startswith("sd_"))

    def test_slug_distinct_when_only_punctuation_differs(self):
        self.assertNotEqual(common.slug("feat/a-b"), common.slug("feat/a.b"))


class PgUrlTests(unittest.TestCase):
    def test_patch_pg_url_merges_options(self):
        url = "postgres://dev:pw@100.82.235.54:25432/data?sslmode=disable&options=-c+statement_timeout%3D15000"
        out = common.patch_pg_url(url, settings={"statement_timeout": "120000", "search_path": "sd_x,public"})
        query = parse_qs(urlsplit(out).query)
        self.assertEqual(query["sslmode"], ["disable"])
        options = query["options"][0]
        self.assertEqual(re.findall(r"statement_timeout=(\S+)", options), ["120000"])
        self.assertIn("-c search_path=sd_x,public", options)

    def test_patch_pg_url_encodes_spaces_for_libpq(self):
        # libpq does not decode "+" as a space in URI query values; Go does both.
        out = common.patch_pg_url("postgres://dev@h:5432/data?sslmode=disable", settings={"search_path": "a,public"})
        self.assertNotIn("+", urlsplit(out).query)
        self.assertIn("options=-c%20search_path%3Da%2Cpublic", out)

    def test_patch_pg_url_sets_user_and_password(self):
        out = common.patch_pg_url("postgres://dev:pw@h:5432/data?sslmode=disable", user="sd_guard", password="p@ss/1")
        parts = urlsplit(out)
        self.assertEqual(parts.username, "sd_guard")
        self.assertEqual(parts.hostname, "h")
        self.assertEqual(parts.port, 5432)
        self.assertNotIn("p@ss/1", out)  # percent-encoded


class RunTests(unittest.TestCase):
    def test_run_raises_stuck(self):
        with self.assertRaises(common.Stuck):
            common.run(["sleep", "5"], timeout=1)


if __name__ == "__main__":
    unittest.main()
