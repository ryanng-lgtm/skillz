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

Only the `## Contents` section (up to the next # or ## heading) is rewritten; everything
else in an INDEX.md is left alone. Also checks: every doc has description/tags/status/updated,
every [ref] has a definition, every markdown link and wikilink resolves (inside an
Obsidian vault, the way Obsidian resolves it), and an area's optional
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
CONTENTS = "## Contents"  # heading of the generated section; a plain heading, so Obsidian shows no markers
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
    key = ""
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"\s*-\s+(.*)$", line)
        if item and isinstance(out.get(key), list):
            out[key].append(item.group(1).strip().strip("\"'"))
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if not val:
            out[key] = []  # a block list, as Obsidian's Properties editor writes one
        elif val.startswith("[") and val.endswith("]"):
            out[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            out[key] = val.strip("\"'")
    # A key with no value and no items is an empty property, not a list.
    return {k: "" if v == [] else v for k, v in out.items()}


def cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def replace_generated(index: Path, generated: str, check: bool) -> None:
    if not index.exists():
        problems.append(f"{index.relative_to(DOCS)}: missing (copy templates/INDEX.md)")
        return
    text = index.read_text()
    start = re.search(rf"^{re.escape(CONTENTS)}[ \t]*$", text, flags=re.M)
    if not start:
        problems.append(f"{index.relative_to(DOCS)}: missing '{CONTENTS}' heading")
        return
    nxt = re.search(r"^#{1,2} ", text[start.end():], flags=re.M)
    tail = text[start.end() + nxt.start():] if nxt else ""
    # Blank lines around the table: Obsidian won't render a table that touches its neighbours.
    body = f"\n\n{generated.strip()}\n" if generated.strip() else "\n"
    new = f"{text[:start.end()]}{body}{chr(10) if tail else ''}{tail}"
    if new != text:
        if check:
            problems.append(f"{index.relative_to(DOCS)}: out of date (run build-index.py)")
        else:
            index.write_text(new)
            print(f"updated {index.relative_to(DOCS)}")


def find_vault(docs: Path) -> Path:
    """The Obsidian vault holding the docs dir (nearest .obsidian/), else the docs dir."""
    for d in (docs, *docs.parents):
        if (d / ".obsidian").is_dir():
            return d
    return docs


VAULT = find_vault(DOCS)
OBSIDIAN = (VAULT / ".obsidian").is_dir()
_vault_files: list[str] = []


def vault_files() -> list[str]:
    """Every file in the vault, as a lowercase vault-relative path, skipping dot dirs."""
    if not _vault_files:
        for root, dirs, files in os.walk(VAULT):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                _vault_files.append((Path(root) / f).relative_to(VAULT).as_posix().lower())
    return _vault_files


def resolve(target: str, src: Path, wikilink: bool) -> str | None:
    """None when the target resolves, else "broken" or why it is ambiguous.

    A markdown link resolves against the linking file's folder. A wikilink, or
    any link inside an Obsidian vault, also resolves the way Obsidian does:
    against the vault root, then as the tail of exactly one vault path (the
    shortest-path form). A wikilink names a note (`.md`) unless it ends in a
    file extension, as `[[diagram.png]]` does.
    """
    relative = not wikilink or target.startswith(("./", "../"))
    vault_wide = wikilink or OBSIDIAN
    if not wikilink or target.lower().endswith(".md"):
        names = [target]
    elif re.search(r"\.[A-Za-z0-9]{1,5}$", target):
        names = [target, target + ".md"]
    else:
        names = [target + ".md"]
    for name in names:
        if relative and (src.parent / name).exists():
            return None
        if vault_wide and (VAULT / name).exists():
            return None
    if not vault_wide:
        return "broken"
    tails = [n.lower().lstrip("./") for n in names]
    hits = {f for f in vault_files() for t in tails if f == t or f.endswith("/" + t)}
    if len(hits) == 1:
        return None
    return f"{target} matches {len(hits)} files; give its path" if hits else "broken"


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
    # Markdown links: skip URLs (any scheme) and same-file anchors.
    targets = list(defs.values()) + [
        t.strip("<>") for t in re.findall(r"\]\(\s*(<[^>]+>|[^)\s]+)", prose)
    ]
    for t in targets:
        t = unquote(t.split("#")[0])
        if t and not re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", t):
            problem = resolve(t, path, wikilink=False)
            if problem:
                problems.append(f"{rel}: {'broken link ' + t if problem == 'broken' else problem}")
    # Wikilinks and embeds: [[target#anchor|alias]], with `\|` inside tables.
    for t in re.findall(r"!?\[\[([^\[\]|#]*)[^\[\]]*\]\]", prose):
        t = t.rstrip("\\").strip()
        if t:
            problem = resolve(t, path, wikilink=True)
            if problem:
                problems.append(f"{rel}: {'broken wikilink [[' + t + ']]' if problem == 'broken' else problem}")


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

    # The Improvement column appears only once some area opts in.
    modes = any(a.get("improvement", "off") != "off" for a in areas)
    rows = ["| Area | What's in it | Tags | Docs | Skills / jobs |" + (" Improvement |" if modes else ""),
            "| --- | --- | --- | --- | --- |" + (" --- |" if modes else "")]
    for a in areas:
        rows.append(
            f"| [{a['name']}/](./{quote(a['name'])}/INDEX.md) | {cell(a.get('description', '—'))} "
            f"| {cell(', '.join(a.get('tags', [])))} | {a['count']} (updated {a['updated'] or '?'}) "
            f"| {cell(a.get('related', '—') or '—')} |" + (f" {a.get('improvement', 'off')} |" if modes else "")
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
