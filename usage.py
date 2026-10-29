#!/usr/bin/env python3
"""Measure what the skills in this repo cost in tokens.

usage: python3 -I usage.py [DAYS] [--calibrate]

Reads the Claude Code transcripts under ~/.claude/projects changed in the last
DAYS days (default 30), subagents included, and prints one row per skill:
  runs     times its text was loaded, from a Skill tool call or a /command
  tok/run  tokens each run loaded, on average
  total    tokens all its runs loaded
  now      tokens its SKILL.md loads today
  desc     tokens its description adds to every session, or "-" for a
           manual-only skill (disable-model-invocation: true), whose
           description is left out of the session

Tokens are characters / 2.76. That ratio was fitted against the API's own
usage numbers: tokens = 0.362 x chars + 115 over 225 runs, r = 0.98.
--calibrate refits it from the transcripts and prints the fit.

It counts only the text a run loads, not the reference files the skill reads
afterwards or the work it does.
"""
import json
import pathlib
import re
import statistics
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent
PROJECTS = pathlib.Path.home() / ".claude" / "projects"
CHARS_PER_TOKEN = 2.76
COMMAND = re.compile(r"<command-name>/?([\w:-]+)</command-name>")


def skill_files():
    return {
        p.parent.name: p
        for base in ("claude/skills", "setup")
        for p in sorted((REPO / base).glob("*/SKILL.md"))
    }


def frontmatter(path):
    text = path.read_text()
    return text.split("---", 2)[1] if text.startswith("---") else ""


def description(fm):
    lines = fm.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("description:"):
            value = line.split(":", 1)[1].strip()
            if value in (">", ">-", "|", "|-"):
                rest = []
                for more in lines[i + 1:]:
                    if more and not more.startswith(" "):
                        break
                    rest.append(more.strip())
                return " ".join(rest).strip()
            return value.strip("'\"")
    return ""


def texts(record):
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
    return []


def prompt_tokens(usage):
    return (usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0))


def runs_in(path, names):
    """Yield (skill, chars loaded, prompt growth or None) for each run in one transcript."""
    records = []
    for line in path.open(errors="replace"):
        try:
            records.append(json.loads(line))
        except ValueError:
            pass
    for i, record in enumerate(records):
        skill = None
        content = (record.get("message") or {}).get("content")
        if record.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Skill":
                    skill = (block.get("input") or {}).get("skill")
        elif record.get("type") == "user" and not record.get("isMeta"):
            for text in texts(record):
                if m := COMMAND.search(text):
                    skill = m.group(1)
                    break
        if skill not in names:
            continue
        # The skill's text arrives as the isMeta user messages before the next turn.
        chars, j = 0, i + 1
        while j < len(records) and records[j].get("type") != "assistant":
            if records[j].get("type") == "user" and records[j].get("isMeta"):
                chars += sum(len(t) for t in texts(records[j]))
            j += 1
        if not chars:
            continue  # denied or interrupted before the text loaded
        growth = None
        if record.get("type") == "assistant" and j < len(records):
            before = (record.get("message") or {}).get("usage") or {}
            after = (records[j].get("message") or {}).get("usage") or {}
            growth = prompt_tokens(after) - prompt_tokens(before) - before.get("output_tokens", 0)
        yield skill, chars, growth


def main():
    args = [a for a in sys.argv[1:] if a != "--calibrate"]
    days = int(args[0]) if args else 30
    cutoff = time.time() - days * 86400
    files = skill_files()
    loaded = {n: [] for n in files}
    pairs = []
    transcripts = [p for p in PROJECTS.rglob("*.jsonl") if p.stat().st_mtime >= cutoff]
    for path in transcripts:
        for skill, chars, growth in runs_in(path, files):
            loaded[skill].append(chars)
            if growth is not None and growth > 200 and chars > 800:
                pairs.append((chars, growth))

    if "--calibrate" in sys.argv and len(pairs) > 2:
        xs, ys = zip(*pairs)
        mx, my = statistics.mean(xs), statistics.mean(ys)
        slope = sum((x - mx) * (y - my) for x, y in pairs) / sum((x - mx) ** 2 for x in xs)
        print(f"fit over {len(pairs)} runs: tokens = {slope:.3f} x chars + {my - slope * mx:.0f}, "
              f"{1 / slope:.2f} chars per token, r = {statistics.correlation(xs, ys):.3f}\n")

    tok = lambda chars: round(chars / CHARS_PER_TOKEN)
    always = 0
    rows = []
    for name, path in files.items():
        fm = frontmatter(path)
        manual = re.search(r"^disable-model-invocation:\s*true\s*$", fm, re.M)
        desc = None if manual else tok(len(name) + len(description(fm)))
        always += desc or 0
        runs = loaded[name]
        rows.append((sum(runs), name, len(runs), tok(statistics.mean(runs)) if runs else 0,
                     tok(sum(runs)), tok(len(path.read_text())), desc))

    print(f"{len(transcripts)} transcripts from the last {days} days")
    print(f"descriptions in every session: ~{always} tokens\n")
    print(f"{'skill':20} {'runs':>5} {'tok/run':>8} {'total':>8} {'now':>7} {'desc':>5}")
    for _, name, runs, per, total, now, desc in sorted(rows, key=lambda r: (-r[0], r[1])):
        print(f"{name:20} {runs:5} {per:8} {total:8} {now:7} {desc if desc is not None else '-':>5}")


if __name__ == "__main__":
    main()
