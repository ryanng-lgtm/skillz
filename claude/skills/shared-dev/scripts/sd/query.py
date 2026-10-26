"""Run SQL against the dev tsdb without a DB URL ever reaching argv or output.

As sd_guard (the default), unqualified names resolve to the run's scratch
copies first, then to the clones in public. As dev, the session is
read-only.

Usage:
  python -I run.py query --schema sd_x -c "SELECT ..." [--timeout 60s]
  python -I run.py query --as dev [--io-timing] -c "EXPLAIN (ANALYZE, BUFFERS) ..."
"""

import argparse

from sd import scratch


def _guard_password():
    return scratch._secret_path().read_text().strip()


def main(argv):
    ap = argparse.ArgumentParser(prog="query")
    ap.add_argument("-c", "--command", required=True)
    ap.add_argument("--schema", help="the run's scratch schema (required as sd_guard)")
    ap.add_argument("--as", dest="role", choices=["guard", "dev"], default="guard")
    ap.add_argument("--timeout", default="60s")
    ap.add_argument("--io-timing", action="store_true",
                    help="SET track_io_timing = on for this session (superuser-only, so --as dev)")
    args = ap.parse_args(argv)
    if args.io_timing and args.role != "dev":
        ap.error("--io-timing needs --as dev: track_io_timing is superuser-only")
    if args.role == "guard":
        if not args.schema:
            ap.error("--schema is required as sd_guard")
        conn = scratch.connect(scratch.guard_url(_guard_password(), [args.schema]))
    else:
        conn = scratch.connect()
        conn.execute("SET default_transaction_read_only = on")
        if args.io_timing:
            conn.execute("SET track_io_timing = on")  # this session only
    conn.execute(f"SET statement_timeout = '{args.timeout}'")
    cur = conn.execute(args.command)
    if cur.description is None:
        return
    print("\t".join(col.name for col in cur.description))
    for row in cur.fetchall():
        print("\t".join("" if v is None else str(v) for v in row))
