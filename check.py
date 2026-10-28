#!/usr/bin/env python3
"""Check that the skills, the README tables and the skill paths agree.

usage: python3 -I check.py

Prints one line per problem and exits 1 when there is any:
  layout   each skill follows templates/skill-template.md
  links    each Codex symlink points at the Claude skill of the same name
  readme   the skill tables and the Claude-only list match the skill dirs
  paths    each ~/.claude/skills/... or ~/.codex/skills/... path a doc or
           script names exists in this repo, or in the work skills checkout
           when that is present
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
WORK_SKILLS = os.environ.get(
    "WORK_SKILLS_DIR", os.path.expanduser("~/repos/llm/skills")
)
# Shipped by other tools and synced in as-is, so they keep their own layout.
VENDORED = {"openmarket", "om-chat", "graphify"}
# Vendored and deliberately left out of the README.
UNLISTED = {"openmarket", "om-chat"}
SKILL_PATH = re.compile(r"~/\.(claude|codex)/skills/([A-Za-z0-9][A-Za-z0-9_.-]*)(/[A-Za-z0-9_./-]*)?")

problems = []


def report(where, problem):
    problems.append(f"{where}: {problem}")


def skills(agent):
    base = os.path.join(REPO, agent, "skills")
    return sorted(
        n for n in os.listdir(base)
        if os.path.isfile(os.path.join(base, n, "SKILL.md"))
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


def check_skills(claude, codex):
    codex_dir = os.path.join(REPO, "codex", "skills")
    linked = {n for n in codex if os.path.islink(os.path.join(codex_dir, n))}
    for name in sorted(linked):
        rel = f"codex/skills/{name}"
        target = os.readlink(os.path.join(REPO, rel))
        if target != f"../../claude/skills/{name}":
            report(rel, f"links to {target}, not ../../claude/skills/{name}")
    for name in claude:
        if name not in VENDORED:
            both = name in linked
            check_layout(
                f"claude/skills/{name}/SKILL.md", name,
                [f"/{name}", f"${name}"] if both else [f"/{name}"],
            )
    for name in sorted(set(codex) - linked - VENDORED):
        check_layout(f"codex/skills/{name}/SKILL.md", name, [f"${name}"])
    return linked


def section(lines, heading, stop):
    start = lines.index(heading) + 1
    for i in range(start, len(lines)):
        if lines[i].startswith(stop):
            return lines[start:i]
    return lines[start:]


def table_names(lines):
    return [
        m.group(1) for l in lines
        if (m := re.match(r"\| `([^`]+)` \|", l))
    ]


def check_readme(claude, codex, linked):
    with open(os.path.join(REPO, "README.md")) as fh:
        lines = fh.read().splitlines()
    claude_rows = table_names(
        section(lines, "### Claude (`claude/skills/` → `~/.claude/skills/`)", "### ")
    )
    want = [n for n in claude if n not in UNLISTED]
    for n in sorted(set(want) - set(claude_rows)):
        report("README.md", f"Claude table is missing {n}")
    for n in sorted(set(claude_rows) - set(want)):
        report("README.md", f"Claude table lists {n}, which claude/skills does not have")
    if claude_rows != sorted(claude_rows):
        report("README.md", "Claude table is not in alphabetical order")

    codex_lines = section(
        lines, "### Codex (`codex/skills/` → `~/.codex/skills/`)", "#### "
    )
    copies = sorted(set(codex) - linked)
    if sorted(table_names(codex_lines)) != copies:
        report("README.md", f"Codex table should list exactly {', '.join(copies)}")
    prose = " ".join(l for l in codex_lines if not l.startswith("|"))
    named = set(re.findall(r"`([a-z0-9-]+)`", prose)) & set(claude)
    claude_only = set(claude) - set(codex)
    if named != claude_only:
        report(
            "README.md",
            "Codex section should name the Claude-only skills "
            + ", ".join(sorted(claude_only)),
        )


def text_files():
    yield from ("README.md", "CLAUDE.md", "claude/CLAUDE.md", "codex/AGENTS.md")
    for agent in ("claude", "codex"):
        base = os.path.join(REPO, agent, "skills")
        for name in sorted(os.listdir(base)):
            top = os.path.join(base, name)
            if name in VENDORED or os.path.islink(top) or not os.path.isdir(top):
                continue
            for root, dirs, files in os.walk(top):
                dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__")]
                for f in sorted(files):
                    yield os.path.relpath(os.path.join(root, f), REPO)


def check_paths(claude, codex):
    for rel in text_files():
        try:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        for mention in sorted(set(m.group(0) for m in SKILL_PATH.finditer(text))):
            agent, name, rest = SKILL_PATH.match(mention).groups()
            rest = (rest or "").rstrip("./")
            if name in (claude if agent == "claude" else codex):
                path = os.path.join(REPO, agent, "skills", name + rest)
            elif os.path.isdir(WORK_SKILLS):
                path = os.path.join(WORK_SKILLS, name + rest)
            else:
                continue
            if not os.path.exists(path):
                report(rel, f"names {mention}, which does not exist")


def main():
    claude, codex = skills("claude"), skills("codex")
    linked = check_skills(claude, codex)
    check_readme(claude, codex, linked)
    check_paths(claude, codex)
    for p in problems:
        print(p)
    if problems:
        return 1
    print(f"check: {len(claude)} Claude and {len(codex)} Codex skills in step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
