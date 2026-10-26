"""Paths and helpers shared by the shared-dev scripts."""

import hashlib
import re
import shlex
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

SHARED_DEV = Path.home() / ".config" / "shared-dev"
STATE = SHARED_DEV / "state"
PLANS = Path.home() / ".claude" / "plans"

SLUG_MAX = 40


class Stuck(Exception):
    """A command ran past its timeout."""

    def __init__(self, cmd, timeout):
        super().__init__(f"timed out after {timeout}s: {' '.join(map(str, cmd))}")
        self.cmd = cmd
        self.timeout = timeout


def slug(branch):
    """Return an identifier-safe name for a branch, unique per branch.

    Whenever the branch had to change to fit (case, punctuation, length), a
    hash of the original is appended so two branches never share a slug.
    """
    clean = re.sub(r"[^a-z0-9]+", "_", branch.lower()).strip("_")
    if clean == branch and len(clean) <= SLUG_MAX:
        return clean
    digest = hashlib.sha1(branch.encode()).hexdigest()[:6]
    return clean[: SLUG_MAX - 7].rstrip("_") + "_" + digest


def schema_name(branch):
    return "sd_" + slug(branch)


def load_env(path=SHARED_DEV / "connections.env"):
    """Parse a KEY=VALUE env file into a dict. Never print the result."""
    env = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, sep, value = line.partition("=")
        if not sep:
            continue
        parts = shlex.split(value, comments=True)
        env[key.strip()] = parts[0] if parts else ""
    return env


def patch_pg_url(url, *, user=None, password=None, settings=None):
    """Return url with user, password and `-c key=value` options replaced."""
    parts = urlsplit(url)
    userinfo, _, hostport = parts.netloc.rpartition("@")
    old_user, _, old_password = userinfo.partition(":")
    new_user = quote(user, safe="") if user is not None else old_user
    new_password = quote(password, safe="") if password is not None else old_password
    netloc = hostport
    if new_user:
        netloc = f"{new_user}:{new_password}@{hostport}" if new_password else f"{new_user}@{hostport}"

    query = parse_qsl(parts.query, keep_blank_values=True)
    if settings:
        options = {}
        for key, value in query:
            if key == "options":
                options.update(re.findall(r"-c\s*([^=\s]+)=(\S*)", value))
        options.update(settings)
        query = [(k, v) for k, v in query if k != "options"]
        query.append(("options", " ".join(f"-c {k}={v}" for k, v in options.items())))
    return urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), parts.fragment))


def run(cmd, *, timeout, check=True, **kw):
    """subprocess.run with text output captured and a mandatory timeout."""
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    try:
        return subprocess.run(cmd, timeout=timeout, check=check, **kw)
    except subprocess.TimeoutExpired as exc:
        raise Stuck(cmd, timeout) from exc


def evidence_dir(branch, plans=PLANS):
    """Return the evidence dir of the newest plan that mentions branch, if any."""
    found = run(["grep", "-rlF", "--include=*.md", branch, str(plans)], timeout=60, check=False)
    candidates = [
        Path(p) for p in found.stdout.splitlines() if p and not any(part.endswith("-evidence") for part in Path(p).parts)
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    return newest.with_name(newest.stem + "-evidence")
