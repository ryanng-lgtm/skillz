"""Throwaway git repos for the repo-sync script tests.

Every repo lives in a temporary folder, uses its own git config, and talks
only to local bare repos, so the tests never read the user's git setup or
reach a real forge.
"""

import os
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
# macOS /bin/bash is 3.2, the oldest bash the scripts must run under.
BASH = "/bin/bash" if os.path.exists("/bin/bash") else "bash"


def git_env(tmp):
    """An environment whose git ignores the user's and the system's config."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.pop("REPO_SYNC_ROOT", None)
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    config = os.path.join(tmp, "gitconfig")
    with open(config, "w") as f:
        f.write(
            "[user]\n\tname = Test\n\temail = test@example.com\n"
            "[init]\n\tdefaultBranch = main\n"
            "[commit]\n\tgpgsign = false\n"
            "[advice]\n\tdetachedHead = false\n"
        )
    env.update(
        HOME=home,
        GIT_CONFIG_GLOBAL=config,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_EDITOR="true",
    )
    return env


def git(env, cwd, *args, check=True):
    """Run git in cwd and return its stdout as bytes."""
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True)
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr.decode()}")
    return r.stdout


def script(env, name, *args):
    """Run scripts/<name> under BASH; stdout and stderr come back as text."""
    return subprocess.run(
        [BASH, str(SCRIPTS / name), *args], env=env, capture_output=True, text=True
    )
