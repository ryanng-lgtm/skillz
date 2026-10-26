"""Call a local gateway endpoint with the dev API key, without printing the key.

Usage: python -I run.py api [--port 4084] PATH
"""

import argparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sd.common import load_env


def main(argv):
    ap = argparse.ArgumentParser(prog="api")
    ap.add_argument("--port", type=int, default=4084)
    ap.add_argument("path")
    args = ap.parse_args(argv)
    key = load_env()["DEV_API_KEY"]
    url = f"http://127.0.0.1:{args.port}/{args.path.lstrip('/')}"
    request = Request(url, headers={"Authorization": key, "x-kiyotaka-key": key})
    try:
        with urlopen(request, timeout=30) as response:
            status, body = response.status, response.read()
    except HTTPError as exc:
        status, body = exc.code, exc.read()
    print(f"HTTP {status}")
    print(body.decode(errors="replace").replace(key, "<key>"))
