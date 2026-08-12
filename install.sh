#!/usr/bin/env bash
#
# Wire this repo into ~/.claude and ~/.codex on the current machine.
#
# Fresh device:  git clone … && cd skillz && ./install.sh
# Existing box:  safe to re-run; refreshes links, never clobbers unrelated skills.
#
# Flags:
#   --force    replace a conflicting real directory (backed up first) with the repo link
#   --no-hook  skip installing the auto-sync hook into ~/.claude/settings.json
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
WORK_SKILLS="${WORK_SKILLS_DIR:-$HOME/repos/llm/skills}"
STAMP="$(date +%Y%m%d-%H%M%S)"

FORCE=0
INSTALL_HOOK=1
for arg in "$@"; do
  case "$arg" in
    --force)   FORCE=1 ;;
    --no-hook) INSTALL_HOOK=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

linked=0 skipped=0 adopted=0

# link SRC DEST — idempotent.
#
# A real (non-symlink) DEST is only replaced when its contents already match SRC,
# which is the normal case when migrating a machine whose files seeded this repo.
# A real DEST that differs is preserved and reported, unless --force moves it aside.
link() {
  local src="$1" dest="$2" name="${2##*/}"

  if [ -L "$dest" ]; then
    [ "$(readlink "$dest")" = "$src" ] && { linked=$((linked + 1)); return; }
    ln -sfn "$src" "$dest"; linked=$((linked + 1)); return
  fi

  if [ -e "$dest" ]; then
    if diff -rq "$src" "$dest" >/dev/null 2>&1; then
      rm -rf "$dest"; ln -sfn "$src" "$dest"
      adopted=$((adopted + 1)); return
    fi
    if [ "$FORCE" = 1 ]; then
      local bak="$dest.local-$STAMP"
      mv "$dest" "$bak"
      ln -sfn "$src" "$dest"
      echo "  ADOPTED $name — your version saved to ${bak##*/}"
      adopted=$((adopted + 1)); return
    fi
    echo "  SKIP $name — real file at $dest differs from the repo. Re-run with --force to replace it (a backup is kept)."
    skipped=$((skipped + 1)); return
  fi

  ln -sfn "$src" "$dest"; linked=$((linked + 1))
}

echo "skillz → $CLAUDE_HOME and $CODEX_HOME"
echo

# ---- Claude ----------------------------------------------------------------
mkdir -p "$CLAUDE_HOME/skills" "$CLAUDE_HOME/commands"

echo "Claude:"
link "$REPO/claude/CLAUDE.md" "$CLAUDE_HOME/CLAUDE.md"

for f in "$REPO"/claude/commands/*.md; do
  [ -e "$f" ] || continue
  link "$f" "$CLAUDE_HOME/commands/$(basename "$f")"
done

for d in "$REPO"/claude/skills/*/; do
  name="$(basename "$d")"
  [ -f "$d/SKILL.md" ] || continue
  link "$REPO/claude/skills/$name" "$CLAUDE_HOME/skills/$name"
done
echo "  $linked linked, $adopted adopted, $skipped skipped"

# ---- Codex -----------------------------------------------------------------
linked=0 skipped=0 adopted=0
mkdir -p "$CODEX_HOME/skills"

echo "Codex:"
link "$REPO/codex/AGENTS.md" "$CODEX_HOME/AGENTS.md"

for d in "$REPO"/codex/skills/*/; do
  name="$(basename "$d")"
  [ -f "$d/SKILL.md" ] || continue
  link "$REPO/codex/skills/$name" "$CODEX_HOME/skills/$name"
done
echo "  $linked linked, $adopted adopted, $skipped skipped"

# ---- Work skills (not carried by this repo; relinked when present) ---------
#
# ~/repos/llm has its own remote and stays the source of truth for these.
if [ -d "$WORK_SKILLS" ]; then
  linked=0 skipped=0 adopted=0
  echo "Work skills from $WORK_SKILLS:"
  for d in "$WORK_SKILLS"/*/; do
    name="$(basename "$d")"
    [ -f "$d/SKILL.md" ] || continue
    # A repo-owned skill of the same name wins; don't fight over it.
    [ -e "$REPO/claude/skills/$name" ] && continue
    link "$WORK_SKILLS/$name" "$CLAUDE_HOME/skills/$name"
    [ -e "$REPO/codex/skills/$name" ] || link "$WORK_SKILLS/$name" "$CODEX_HOME/skills/$name"
  done
  echo "  $linked linked, $adopted adopted, $skipped skipped"
else
  echo "Work skills: $WORK_SKILLS not present on this machine — skipped."
fi

# ---- Auto-sync hook --------------------------------------------------------
if [ "$INSTALL_HOOK" = 1 ]; then
  echo
  "$REPO/hook-install.sh"
fi

echo
echo "Done. Verify with:  ls -la $CLAUDE_HOME/skills | grep skillz"
