"""Where a run keeps its files: the evidence dir of the newest plan that names
the branch, else the session's scratchpad. Creates it and prints the path.

Usage: python -I run.py rundir --branch BRANCH --scratchpad DIR
"""

import argparse
from datetime import datetime
from pathlib import Path

from sd.common import PLANS, evidence_dir


def run_dir(branch, *, scratchpad, plans=PLANS, stamp=None):
    stamp = stamp or datetime.now().strftime("%Y-%m-%d-%H%M")
    base = evidence_dir(branch, plans) or Path(scratchpad)
    out = Path(base).resolve() / "shared-dev" / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def main(argv):
    ap = argparse.ArgumentParser(prog="rundir")
    ap.add_argument("--branch", required=True)
    ap.add_argument("--scratchpad", required=True, help="this session's scratchpad directory")
    ap.add_argument("--plans", default=str(PLANS))
    args = ap.parse_args(argv)
    print(run_dir(args.branch, scratchpad=Path(args.scratchpad), plans=Path(args.plans)))
