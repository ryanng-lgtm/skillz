#!/usr/bin/env python3
"""Regenerate the INDEX.md files of a docs knowledge base from doc frontmatter.

Root: --root PATH, else $DOCS_ROOT, else the parent of this script's dir
(i.e. drop it into <docs>/scripts/ and it finds <docs> by itself).

Layout:
  docs/INDEX.md               top-level: hand-written preamble + generated area table
  docs/<area>/INDEX.md        per area: hand-written frontmatter + generated doc table
                              (plus a sub-area table when the area has sub-areas)
  docs/<area>/<sub>/INDEX.md  optional sub-areas, same shape, any depth
  docs/<area>/NNN Title.md    each doc starts with YAML-ish frontmatter:
      ---
      description: "one or two sentences: what's in it, when to read it"
      tags: [a, b, c]
      status: current            # or: superseded by NNN
      updated: YYYY-MM-DD
      host: myhost (...)         # optional
      ---

Only the block between the GENERATED markers is rewritten; everything else in an
INDEX.md is left alone. Also checks: every doc has description/tags/status/updated,
every [ref] has a definition, every relative link resolves, and an area's optional
`improvement:` field is one of IMPROVEMENT_MODES (a typo must not silently disable it), and a
`continuous` area names a `tooling:` dir that is in git and has README.md, tests/ and BY-HAND.md.

Usage: python3 build-index.py [--root DOCS_DIR] [--check]   (--check: validate, write nothing)
Exit code 1 if any problem is found.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, unquote

def resolve_root(argv: list[str]) -> Path:
    if "--root" in argv:
        return Path(argv[argv.index("--root") + 1]).expanduser().resolve()
    if os.environ.get("DOCS_ROOT"):
        return Path(os.environ["DOCS_ROOT"]).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


DOCS = resolve_root(sys.argv)
BEGIN, END = "<!-- BEGIN GENERATED (scripts/build-index.py) -->", "<!-- END GENERATED -->"
DOC_RE = re.compile(r"^\d{3} .+\.md$")
REQUIRED = ("description", "tags", "status", "updated")
IMPROVEMENT_MODES = ("continuous", "off")  # area INDEX.md `improvement:`; absent = off. Rules: <docs>/CLAUDE.md
problems: list[str] = []


def frontmatter(path: Path) -> dict | None:
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    try:
        block = text[4 : text.index("\n---\n", 4)]
    except ValueError:
        return None
    out: dict = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            out[key.strip()] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            out[key.strip()] = val.strip("\"'")
    return out


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def replace_generated(index: Path, generated: str, check: bool) -> None:
    if not index.exists():
        problems.append(f"{index.relative_to(DOCS)}: missing (copy templates/INDEX.md)")
        return
    text = index.read_text()
    if BEGIN not in text or END not in text:
        problems.append(f"{index.relative_to(DOCS)}: missing GENERATED markers")
        return
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new = f"{head}{BEGIN}\n{generated.rstrip()}\n{END}{tail}"
    if new != text:
        if check:
            problems.append(f"{index.relative_to(DOCS)}: out of date (run build-index.py)")
        else:
            index.write_text(new)
            print(f"updated {index.relative_to(DOCS)}")


def check_links(path: Path) -> None:
    text = path.read_text()
    rel = path.relative_to(DOCS)
    # strip fenced code so YAML/TOML like [storage] isn't read as a ref
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    prose = re.sub(r"`[^`\n]*`", "", prose)  # inline code (examples) isn't a real ref
    defs = dict(re.findall(r"^\[([^\]]+)\]: (\S+)$", text, flags=re.M))
    for ref in set(re.findall(r"\[((?:[a-z0-9-]+/)*\d{3})\](?![:(])", prose)):
        if ref not in defs:
            problems.append(f"{rel}: [{ref}] used but not defined")
    targets = list(defs.values()) + re.findall(r"\]\((\.{1,2}/[^)\s]+)\)", prose)
    for t in targets:
        if t.startswith(("./", "../")) and not (path.parent / unquote(t.split("#")[0])).exists():
            problems.append(f"{rel}: broken link {t}")


def check_tooling(area: str, tooling: str | None) -> None:
    """A continuous area's tooling dir: exists, inside git, has README.md, tests/, BY-HAND.md."""
    where = f"{area}/INDEX.md"
    if not tooling:
        problems.append(f"{where}: improvement: continuous needs 'tooling: <dir>'")
        return
    path = Path(tooling).expanduser()
    if not path.is_dir():
        problems.append(f"{where}: tooling dir {tooling} does not exist")
        return
    in_git = subprocess.run(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
                            capture_output=True, text=True).stdout.strip() == "true"
    if not in_git:
        problems.append(f"{where}: tooling dir {tooling} is not inside a git repo")
    for need in ("README.md", "tests", "BY-HAND.md"):
        if not (path / need).exists():
            problems.append(f"{where}: tooling dir {tooling} has no {need}")


def is_area(d: Path) -> bool:
    """A folder with numbered docs, or with sub-areas that have them."""
    if not d.is_dir() or d.name.startswith((".", "_")) or d.name == "scripts":
        return False
    return any(DOC_RE.match(p.name) for p in d.iterdir()) or any(is_area(c) for c in d.iterdir())


def build_area(area: Path, check: bool) -> dict | None:
    name = str(area.relative_to(DOCS))
    index = area / "INDEX.md"
    if not index.exists():
        problems.append(f"{name}/: has docs but no INDEX.md")
        return None
    meta = frontmatter(index) or {}
    for k in ("description", "tags"):
        if not meta.get(k):
            problems.append(f"{name}/INDEX.md: frontmatter missing '{k}'")
    mode = meta.get("improvement", "off")
    if mode not in IMPROVEMENT_MODES:
        problems.append(f"{name}/INDEX.md: improvement '{mode}' not one of {IMPROVEMENT_MODES}")
    if mode == "continuous":
        check_tooling(name, meta.get("tooling"))
    for doc in (p for p in area.iterdir() if DOC_RE.match(p.name)):
        if "improvement" in (frontmatter(doc) or {}):
            problems.append(f"{name}/{doc.name}: 'improvement' belongs in the area INDEX.md, not a doc")
    rows = ["| Doc | Description | Tags | Status |", "| --- | --- | --- | --- |"]
    latest, count = "", 0
    for doc in sorted(p for p in area.iterdir() if DOC_RE.match(p.name)):
        fm = frontmatter(doc)
        if fm is None:
            problems.append(f"{name}/{doc.name}: no frontmatter")
            continue
        for k in REQUIRED:
            if not fm.get(k):
                problems.append(f"{name}/{doc.name}: frontmatter missing '{k}'")
        latest = max(latest, fm.get("updated", ""))
        count += 1
        link = f"[{doc.stem}](./{quote(doc.name)})"
        tags = ", ".join(fm.get("tags", []))
        rows.append(f"| {link} | {cell(fm.get('description', '—'))} | {cell(tags)} | {fm.get('status', '?')} |")
        check_links(doc)
    if count == 0:
        rows = []
    subs = [i for i in (build_area(d, check) for d in sorted(area.iterdir()) if is_area(d)) if i]
    if subs:
        if rows:
            rows.append("")
        rows += ["| Sub-area | What's in it | Tags | Docs |", "| --- | --- | --- | --- |"]
        for sub in subs:
            short = sub["name"].split("/")[-1]
            rows.append(f"| [{short}/](./{quote(short)}/INDEX.md) | {cell(sub.get('description', '—'))} "
                        f"| {cell(', '.join(sub.get('tags', [])))} | {sub['count']} (updated {sub['updated'] or '?'}) |")
            count += sub["count"]
            latest = max(latest, sub["updated"])
    replace_generated(index, "\n".join(rows), check)
    check_links(index)
    return {**meta, "name": name, "count": count, "updated": latest}


def main() -> int:
    check = "--check" in sys.argv
    if not DOCS.is_dir():
        print(f"PROBLEM: docs root {DOCS} is not a directory")
        return 1
    areas = []
    for area in sorted(p for p in DOCS.iterdir() if is_area(p)):
        info = build_area(area, check)
        if info:
            areas.append(info)
    for stray in (p for p in DOCS.iterdir() if p.is_file() and DOC_RE.match(p.name)):
        problems.append(f"{stray.name}: numbered doc at top level; move it into an area folder")

    rows = ["| Area | What's in it | Tags | Docs | Skills / jobs | Improvement |",
            "| --- | --- | --- | --- | --- | --- |"]
    for a in areas:
        rows.append(
            f"| [{a['name']}/](./{quote(a['name'])}/INDEX.md) | {cell(a.get('description', '—'))} "
            f"| {cell(', '.join(a.get('tags', [])))} | {a['count']} (updated {a['updated'] or '?'}) "
            f"| {cell(a.get('related', '—') or '—')} | {a.get('improvement', 'off')} |"
        )
    replace_generated(DOCS / "INDEX.md", "\n".join(rows), check)
    for top in ("INDEX.md", "ABOUT.md", "CLAUDE.md"):
        if (DOCS / top).exists():
            check_links(DOCS / top)

    for p in problems:
        print("PROBLEM:", p)
    if not problems:
        print("ok:", ", ".join(f"{a['name']} ({a['count']})" for a in areas))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
