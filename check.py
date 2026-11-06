#!/usr/bin/env python3
"""Check that the skills, the README skill index and the skill paths agree.

usage: python3 -I check.py

Prints one line per problem and exits 1 when there is any:
  layout   each skill follows templates/skill-template.md
  links    each Codex symlink points at the shared or personal skill of the
           same name
  readme   the Shared skills table in README.md and the Personal skills table
           in personal/README.md list every skill, in order, with its SKILL.md
           link and the agents that have it
  paths    each ~/.claude/skills/... or ~/.codex/skills/... path a doc or
           script names exists in this repo, or in the work skills checkout
           when that is present
  leaks    shared/, the plugin every install copies, holds no symlink and no
           personal marker, and the plugin manifests and marketplaces exist
           and name the same plugin
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
WORK_SKILLS = os.environ.get(
    "WORK_SKILLS_DIR", os.path.expanduser("~/repos/llm/skills")
)
# Shipped by other tools and synced in as-is, so they keep their own layout.
VENDORED = {"openmarket", "om-chat", "graphify", "desloppify"}
# Vendored and deliberately left out of the README.
UNLISTED = {"openmarket", "om-chat"}
# Where skills live: the shared plugin's skills, then Ryan's own.
HOMES = ("shared/skills", "personal")
# The file and table heading that list the skills of each home.
TABLES = {
    "shared/skills": ("README.md", "## Shared skills"),
    "personal": ("personal/README.md", "## Personal skills"),
}
SKILL_PATH = re.compile(r"~/\.(claude|codex)/skills/([A-Za-z0-9][A-Za-z0-9_.-]*)(/[A-Za-z0-9_./-]*)?")
# The plugin root: Claude Code and Codex copy this folder, and nothing else, into
# every install.
PLUGIN_ROOT = "shared"
PLUGIN_MANIFESTS = ("shared/.claude-plugin/plugin.json", "shared/.codex-plugin/plugin.json")
MARKETPLACES = (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json")
# Personal data that must never reach the plugin, matched case-insensitively.
# Words match whole, so the GitHub handle ryanng-lgtm in the manifests is not
# "Ryan"; path fragments match anywhere.
LEAK_WORDS = ("Ryan", "OM Chat", "openmarket", "kiyotaka")
LEAK_PATHS = ("/Users/", "~/Documents", "Mobile Documents", "~/.claude/skills/", "~/.codex/skills/")
LEAK_MARKERS = [
    *((m, re.compile(rf"\b{re.escape(m)}\b", re.IGNORECASE)) for m in LEAK_WORDS),
    *((m, re.compile(re.escape(m), re.IGNORECASE)) for m in LEAK_PATHS),
]

problems = []


def report(where, problem):
    problems.append(f"{where}: {problem}")


def skills(base):
    path = os.path.join(REPO, base)
    return sorted(
        n for n in os.listdir(path)
        if os.path.isfile(os.path.join(path, n, "SKILL.md"))
    )


def frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return {}, lines
    end = lines.index("---", 1)
    front, fields = lines[1:end], {}
    for i, line in enumerate(front):
        key, sep, value = line.partition(":")
        if not sep or line[0].isspace():
            continue
        value = value.strip()
        if value in (">", ">-", "|", "|-"):
            parts = []
            for nxt in front[i + 1:]:
                if nxt and not nxt[0].isspace():
                    break
                parts.append(nxt.strip())
            value = " ".join(p for p in parts if p)
        fields[key] = value.strip("\"'")
    return fields, lines[end + 1:]


def outside_fences(lines):
    fenced = False
    for line in lines:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced:
            yield line


def check_layout(rel, name, triggers):
    with open(os.path.join(REPO, rel)) as fh:
        fields, body = frontmatter(fh.read().splitlines())
    if fields.get("name") != name:
        report(rel, f"frontmatter name is {fields.get('name')!r}, not {name!r}")
    desc = fields.get("description", "")
    if not desc.startswith("Use when"):
        report(rel, "description does not start with 'Use when'")
    if "Trigger:" not in desc:
        report(rel, "description has no 'Trigger:'")
    for t in triggers:
        if t not in desc.partition("Trigger:")[2]:
            report(rel, f"description trigger does not name {t}")
    body = list(outside_fences(body))
    title = next((l for l in body if l.startswith("# ")), "")
    if not title.startswith(f"# {name} — "):
        report(rel, f"title {title!r} is not '# {name} — <purpose>'")
    sections = [l.strip() for l in body if l.startswith("## ")]
    if not sections or sections[0] != "## Overview":
        report(rel, "first section is not '## Overview'")
    if not any(l.startswith("**Core principle:") for l in body):
        report(rel, "no '**Core principle:' line")


def check_skills(home, codex):
    codex_dir = os.path.join(REPO, "codex", "skills")
    linked = {n for n in codex if os.path.islink(os.path.join(codex_dir, n))}
    for name in sorted(linked):
        rel = f"codex/skills/{name}"
        target = os.readlink(os.path.join(REPO, rel))
        want = f"../../{home[name]}/{name}" if name in home else "a shared or personal skill"
        if target != want:
            report(rel, f"links to {target}, not {want}")
    for name, base in sorted(home.items()):
        if name not in VENDORED:
            both = name in linked
            check_layout(
                f"{base}/{name}/SKILL.md", name,
                [f"/{name}", f"${name}"] if both else [f"/{name}"],
            )
    for name in sorted(set(codex) - linked - VENDORED):
        check_layout(f"codex/skills/{name}/SKILL.md", name, [f"${name}"])
    return linked


def agents(name, home, codex, linked):
    if name not in codex:
        return "Claude"
    if name not in home:
        return "Codex"
    return "Claude, Codex" if name in linked else "Claude, Codex (own copy)"


def table_rows(doc, lines, heading):
    """Map each skill row under heading to (link, agents)."""
    if heading not in lines:
        report(doc, f"no {heading!r} section")
        return {}
    rows, where = {}, heading.lstrip("# ")
    for line in lines[lines.index(heading) + 1:]:
        if line.startswith("## "):
            break
        if m := re.match(r"\| \[`([^`]+)`\]\(([^)]+)\) \| ([^|]+) \|", line):
            cells = re.split(r"(?<!\\)\|", line.strip())[1:-1]
            if len(cells) != 3:
                report(doc, f"{where} row for {m.group(1)} has {len(cells)} columns, not 3")
            rows[m.group(1)] = (m.group(2), m.group(3).strip())
    return rows


def check_readme(home, codex, linked):
    for base, (doc, heading) in TABLES.items():
        with open(os.path.join(REPO, doc)) as fh:
            lines = fh.read().splitlines()
        want = {n for n, b in home.items() if b == base} - UNLISTED
        if base == "personal":
            # A Codex-only skill has no home; it is listed with Ryan's own.
            want |= set(codex) - set(home) - UNLISTED
        rows, where = table_rows(doc, lines, heading), heading.lstrip("# ")
        for n in sorted(want - set(rows)):
            report(doc, f"{where} is missing {n}")
        for n in sorted(set(rows) - want):
            report(doc, f"{where} lists {n}, which belongs elsewhere or does not exist")
        if list(rows) != sorted(rows):
            report(doc, f"{where} is not in alphabetical order")
        for n in sorted(want & set(rows)):
            link, cell = rows[n]
            path = os.path.relpath(f"{home.get(n, 'codex/skills')}/{n}/SKILL.md", os.path.dirname(doc))
            if link != path:
                report(doc, f"{n} links to {link}, not {path}")
            expected = agents(n, home, codex, linked)
            if cell != expected:
                report(doc, f"{n} lists agents {cell!r}, not {expected!r}")


def text_files():
    yield from ("README.md", "personal/README.md", "CLAUDE.md", "claude/CLAUDE.md", "codex/AGENTS.md")
    for base in (*HOMES, "codex/skills"):
        base = os.path.join(REPO, base)
        for name in sorted(os.listdir(base)):
            top = os.path.join(base, name)
            if name in VENDORED or os.path.islink(top) or not os.path.isdir(top):
                continue
            for root, dirs, files in os.walk(top):
                dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__")]
                for f in sorted(files):
                    yield os.path.relpath(os.path.join(root, f), REPO)


def check_paths(home, codex):
    for rel in text_files():
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        for mention in sorted(set(m.group(0) for m in SKILL_PATH.finditer(text))):
            agent, name, rest = SKILL_PATH.match(mention).groups()
            rest = (rest or "").rstrip("./")
            if agent == "claude" and name in home:
                path = os.path.join(REPO, home[name], name + rest)
            elif agent == "codex" and name in codex:
                path = os.path.join(REPO, "codex", "skills", name + rest)
            elif os.path.isdir(WORK_SKILLS):
                path = os.path.join(WORK_SKILLS, name + rest)
            else:
                continue
            if not os.path.exists(path):
                report(rel, f"names {mention}, which does not exist")


def load_json(rel):
    try:
        with open(os.path.join(REPO, rel)) as fh:
            return json.load(fh)
    except FileNotFoundError:
        report(rel, "missing")
    except (OSError, ValueError) as err:
        report(rel, f"is not valid JSON: {err}")
    return None


def check_manifests():
    names = {}
    for rel in PLUGIN_MANIFESTS:
        if (data := load_json(rel)) is not None:
            names[rel] = data.get("name")
    for rel in MARKETPLACES:
        if (data := load_json(rel)) is not None:
            for i, entry in enumerate(data.get("plugins", [])):
                names[f"{rel} plugins[{i}]"] = entry.get("name")
    if len(set(names.values())) > 1:
        listed = ", ".join(f"{where} = {name!r}" for where, name in names.items())
        report(PLUGIN_ROOT, f"manifests and marketplaces name different plugins: {listed}")


def plugin_files():
    """Yield each file under the plugin root, reporting each symlink instead."""
    for root, dirs, files in os.walk(os.path.join(REPO, PLUGIN_ROOT)):
        for name in sorted(dirs + files):
            path = os.path.join(root, name)
            if os.path.islink(path):
                report(os.path.relpath(path, REPO), "is a symlink; the plugin must hold real files")
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
        for name in sorted(files):
            path = os.path.join(root, name)
            if not os.path.islink(path):
                yield path


def leaks():
    """Report symlinks and personal markers anywhere in the plugin root."""
    check_manifests()
    for path in plugin_files():
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            if b"\0" in data:
                continue  # binary, such as a .pyc
            lines = data.decode("utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        rel = os.path.relpath(path, REPO)
        for n, line in enumerate(lines, 1):
            for marker, pattern in LEAK_MARKERS:
                if pattern.search(line):
                    report(f"{rel}:{n}", f"personal marker '{marker}'")


def homes():
    """Where each Claude skill lives: shared/skills or personal."""
    home = {}
    for base in HOMES:
        for n in skills(base):
            if n in home:
                report(f"{base}/{n}", f"a skill of the same name is in {home[n]}")
            else:
                home[n] = base
    return home


def main():
    home = homes()
    codex = skills("codex/skills")
    linked = check_skills(home, codex)
    check_readme(home, codex, linked)
    check_paths(home, codex)
    leaks()
    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"check: {len(home)} Claude and {len(codex)} Codex skills in step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
