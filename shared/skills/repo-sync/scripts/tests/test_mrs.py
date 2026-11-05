import json
import os
import shutil
import stat
import tempfile
import unittest

from gitrepo import git, git_env, script

# Stands in for ssh: serves "<host>:<path>" from $FAKE_FORGE/<host>/<path>, so
# clones can keep real forge URLs and still fetch from local bare repos. For
# `ssh -G <host>` it prints the HostName that $FAKE_SSH_HOSTNAME ("from=to")
# gives that host, as an ssh config would.
FAKE_SSH = """#!/bin/sh
if [ "$1" = -G ]; then
	shift
	[ "$1" != -- ] || shift
	real="$1"
	case "$FAKE_SSH_HOSTNAME" in "$1="*) real="${FAKE_SSH_HOSTNAME#*=}" ;; esac
	echo "hostname $real"
	exit 0
fi
host="${1#*@}"
eval "set -- $2"
exec "$1" "$FAKE_FORGE/$host/$2"
"""


def mr(project, iid, source, target, host="gitlab.example.com", fork=False):
    """One GitLab MR as the merge_requests API returns it."""
    return {
        "references": {"full": f"{project}!{iid}"},
        "web_url": f"https://{host}/{project}/-/merge_requests/{iid}",
        "source_branch": source,
        "target_branch": target,
        "source_project_id": 2 if fork else 1,
        "target_project_id": 1,
        "detailed_merge_status": "mergeable",
    }


@unittest.skipUnless(shutil.which("jq"), "mrs.sh needs jq")
class MrsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.env = git_env(self.tmp)
        self.bin = os.path.join(self.tmp, "bin")
        os.mkdir(self.bin)
        self.stub("ssh", FAKE_SSH)
        self.stub("gh", "#!/bin/sh\necho '{\"data\":{\"search\":{\"nodes\":[]}}}'\n")
        self.env.update(
            PATH=f"{self.bin}{os.pathsep}{self.env['PATH']}",
            FAKE_FORGE=os.path.join(self.tmp, "forge"),
            GIT_SSH_COMMAND=os.path.join(self.bin, "ssh"),
            GIT_SSH_VARIANT="simple",
        )
        self.root = os.path.join(self.tmp, "repos")
        os.mkdir(self.root)

    def stub(self, name, text):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def glab_lists(self, *mrs):
        self.stub("glab", f"#!/bin/sh\ncat <<'EOF'\n{json.dumps(list(mrs))}\nEOF\n")

    def clone(self, name, host, project, branches):
        """A clone under the root whose origin is git@<host>:<project>.git.

        Every branch in branches is cut from main and is one commit behind it."""
        bare = os.path.join(self.tmp, "forge", host, f"{project}.git")
        seed = os.path.join(self.tmp, "seed-" + name)
        git(self.env, self.tmp, "init", "-q", "--bare", bare)
        git(self.env, self.tmp, "clone", "-q", bare, seed)
        git(self.env, seed, "commit", "-q", "--allow-empty", "-m", "base")
        for b in branches:
            git(self.env, seed, "branch", b)
        git(self.env, seed, "commit", "-q", "--allow-empty", "-m", "main moves on")
        git(self.env, seed, "push", "-q", "origin", "main", *branches)
        path = os.path.join(self.root, name)
        git(self.env, self.tmp, "clone", "-q", bare, path)
        git(self.env, path, "remote", "set-url", "origin", f"git@{host}:{project}.git")
        return path

    def rows(self):
        r = script(self.env, "mrs.sh", "--root", self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [line.split("\t") for line in r.stdout.splitlines()], r.stderr

    def test_mr_maps_only_to_clones_on_its_own_host(self):
        gitlab = self.clone("gitlab-api", "gitlab.example.com", "team/api", ["feat"])
        self.clone("github-api", "github.com", "team/api", ["feat"])
        self.glab_lists(mr("team/api", 5, "feat", "main"))

        rows, _ = self.rows()

        self.assertEqual([(row[0], row[1], row[5]) for row in rows],
                         [(gitlab, "team/api!5", "rebase")])

    def test_ssh_hostname_alias_still_maps_the_mr_to_its_clone(self):
        # The ssh config sends gitlab.example.com to altssh.gitlab.example.com.
        self.env["FAKE_SSH_HOSTNAME"] = "gitlab.example.com=altssh.gitlab.example.com"
        path = self.clone("api", "gitlab.example.com", "team/api", ["feat"])
        self.glab_lists(mr("team/api", 5, "feat", "main"))

        rows, _ = self.rows()

        self.assertEqual([(row[0], row[1], row[5]) for row in rows],
                         [(path, "team/api!5", "rebase")])

    def test_clone_on_a_separate_ssh_host_claims_the_branch_but_never_syncs_it(self):
        # The clone's origin names the forge's ssh host, which the MR's web URL never shows.
        path = self.clone("api", "altssh.gitlab.example.com", "team/api", ["feat"])
        self.glab_lists(mr("team/api", 5, "feat", "main"))

        rows, _ = self.rows()

        self.assertEqual([(row[0], row[1], row[5], row[9]) for row in rows],
                         [(path, "team/api!5", "?", "other-host")])

    def test_fork_mr_claims_its_branch_name_but_never_syncs_it(self):
        # origin has its own "topic", unrelated to the fork's branch of that name.
        path = self.clone("api", "gitlab.example.com", "team/api", ["topic"])
        self.glab_lists(mr("team/api", 6, "topic", "main", fork=True))

        rows, err = self.rows()

        self.assertEqual([(row[0], row[1], row[5], row[9]) for row in rows],
                         [(path, "team/api!6", "?", "fork")])
        self.assertIn("team/api!6 is from a fork, not handled", err)


if __name__ == "__main__":
    unittest.main()
