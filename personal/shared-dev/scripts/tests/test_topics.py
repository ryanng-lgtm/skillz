import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sd import claim, topics


class TopicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(claim, "STATE", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        claim.write("kiyotaka-shared-dev-x", session="s", branch="b", worktrees=[], schemas=[], run_dir="/r",
                    prefix="dev.ryan.x.")
        self.admin = MagicMock()
        self.admin.list_topics.return_value.topics = {"dev.ryan.normalized": MagicMock(partitions={0: 1, 1: 1, 2: 1})}
        p2 = patch.object(topics, "_admin", return_value=self.admin)
        p2.start()
        self.addCleanup(p2.stop)

    def test_create_records_topic_and_copies_partitions(self):
        topics.create("kiyotaka-shared-dev-x", "dev.ryan.x.dedup.long-ids.v1", like="dev.ryan.normalized",
                      config={"retention.ms": "777600000"})
        new = self.admin.create_topics.call_args.args[0][0]
        self.assertEqual((new.topic, new.num_partitions), ("dev.ryan.x.dedup.long-ids.v1", 3))
        self.assertEqual(claim.read("kiyotaka-shared-dev-x")["topics"], ["dev.ryan.x.dedup.long-ids.v1"])

    def test_create_refuses_outside_prefix_or_existing(self):
        with self.assertRaises(SystemExit):
            topics.create("kiyotaka-shared-dev-x", "dev.ryan.other.t", partitions=1)
        with self.assertRaises(SystemExit):
            topics.create("kiyotaka-shared-dev-x", "dev.ryan.normalized", partitions=1)

    def test_delete_only_recorded_topics(self):
        with self.assertRaises(SystemExit):
            topics.delete("kiyotaka-shared-dev-x", "dev.ryan.normalized")
        self.admin.delete_topics.assert_not_called()


if __name__ == "__main__":
    unittest.main()
