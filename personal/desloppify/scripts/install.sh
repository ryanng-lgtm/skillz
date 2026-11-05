#!/bin/bash
# Installs the desloppify CLI from PyPI as a uv tool, on Python 3.11 or later,
# which uv downloads when the machine has none.
#
# Usage: install.sh [--upgrade]
#
# It installs the CLI only. It never runs `desloppify setup` or
# `desloppify update-skill`: the skill files come from the skillz repo, and
# setup writes into ~/.claude/skills and ~/.codex/AGENTS.md, which are links
# into that repo.
set -euo pipefail

pkg='desloppify[full]>=1.0'
upgrade=false
case "${1:-}" in
'') ;;
--upgrade) upgrade=true ;;
*)
	echo "usage: install.sh [--upgrade]" >&2
	exit 2
	;;
esac

if command -v desloppify >/dev/null 2>&1 && ! $upgrade; then
	echo "desloppify: installed at $(command -v desloppify)"
	exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
	echo "desloppify needs uv to install: https://docs.astral.sh/uv/getting-started/installation/" >&2
	exit 1
fi
flags=(--python '>=3.11')
if $upgrade; then
	flags+=(--upgrade)
fi
uv tool install "${flags[@]}" "$pkg"
bin_dir=$(uv tool dir --bin)

if ! command -v desloppify >/dev/null 2>&1; then
	echo "desloppify: installed in $bin_dir, which is not on PATH" >&2
	exit 1
fi
echo "desloppify: installed at $(command -v desloppify)"
