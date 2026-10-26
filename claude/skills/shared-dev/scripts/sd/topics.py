"""Kafka topics a run needs (a dedup IDs topic, say): created under the run's
prefix, recorded in its claim, deleted by teardown. Topics the run did not
create are never deleted.

Usage:
  python -I run.py topics create --project P NAME (--partitions N | --like TOPIC) [--config k=v ...]
  python -I run.py topics delete --project P NAME
"""

import argparse

from sd import claim
from sd.common import load_env


def _admin():
    from confluent_kafka.admin import AdminClient

    env = load_env()
    return AdminClient({
        "bootstrap.servers": env["KAFKA_BOOTSTRAP_SERVERS"],
        "security.protocol": env["KAFKA_SECURITY_PROTOCOL"],
        "sasl.mechanism": env["KAFKA_SASL_MECHANISM"],
        "sasl.username": env["KAFKA_SASL_USERNAME"],
        "sasl.password": env["KAFKA_SASL_PASSWORD"],
    })


def create(project, name, *, partitions=None, like=None, config=None):
    from confluent_kafka.admin import NewTopic

    record = claim.read(project) or {}
    prefix = record.get("prefix", "dev.ryan.")
    if not name.startswith(prefix):
        raise SystemExit(f"{name} is outside this run's prefix {prefix}")
    admin = _admin()
    existing = admin.list_topics(timeout=10).topics
    if name in existing:
        raise SystemExit(f"{name} already exists; a run only creates (and later deletes) its own topics")
    if like:
        partitions = len(existing[like].partitions)
    futures = admin.create_topics([NewTopic(name, partitions, -1, config=config or {})])
    futures[name].result(timeout=30)
    claim.update(project, topics=sorted(set(record.get("topics", [])) | {name}))


def delete(project, name):
    if name not in (claim.read(project) or {}).get("topics", []):
        raise SystemExit(f"{name} was not created by this run; not deleting it")
    _admin().delete_topics([name])[name].result(timeout=30)
    record = claim.read(project)
    claim.update(project, topics=[t for t in record.get("topics", []) if t != name])


def main(argv):
    ap = argparse.ArgumentParser(prog="topics")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--project", required=True)
    c.add_argument("name")
    size = c.add_mutually_exclusive_group(required=True)
    size.add_argument("--partitions", type=int)
    size.add_argument("--like", help="copy the partition count of this topic")
    c.add_argument("--config", action="append", default=[], metavar="KEY=VALUE")
    d = sub.add_parser("delete")
    d.add_argument("--project", required=True)
    d.add_argument("name")
    args = ap.parse_args(argv)
    if args.cmd == "create":
        create(args.project, args.name, partitions=args.partitions, like=args.like,
               config=dict(item.split("=", 1) for item in args.config))
        print(f"created {args.name}")
    else:
        delete(args.project, args.name)
        print(f"deleted {args.name}")
