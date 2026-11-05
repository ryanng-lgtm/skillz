#!/usr/bin/env bash
#
# Claude Code status line, written by setup-statusline. Rerun /setup-statusline
# to change which parts it shows, or edit PARTS below.
#
# Claude Code pipes a JSON status to stdin and shows what this prints. The parts
# named in PARTS print in the order model | folder | branch | ctx % |
# 5h % 7d % | effort; any part Claude Code doesn't report is skipped.

PARTS="model folder branch ctx limits effort"

input=$(cat)
j() { printf '%s' "$input" | jq -r "$1 // empty"; }
on() { case " $PARTS " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

model=$(j .model.display_name)
dir=$(j '.workspace.current_dir // .cwd')
ctx=$(j .context_window.used_percentage)
five=$(j .rate_limits.five_hour.used_percentage)
week=$(j .rate_limits.seven_day.used_percentage)
effort=$(j .effort.level)
branch=''
on branch && branch=$(git -C "$dir" --no-optional-locks branch --show-current 2>/dev/null)

E=$(printf '\033')
c() { printf '%s[%sm%s%s[0m' "$E" "$1" "$2" "$E"; }

# A percentage: green under 50, yellow from 50, red from 80.
pc() {
  local n k
  n=$(printf '%.0f' "$1")
  if [ "$n" -ge 80 ]; then k=31; elif [ "$n" -ge 50 ]; then k=33; else k=32; fi
  printf '%s[%sm%s%%%s[0m' "$E" "$k" "$n" "$E"
}

sep=$(c 2 ' | ')
out=''
add() { [ -n "$1" ] && out="${out:+$out$sep}$1"; }

on model && [ -n "$model" ] && add "$(c '1;36' "$model")"
on folder && [ -n "$dir" ] && add "$(c 34 "$(basename "$dir")")"
on branch && [ -n "$branch" ] && add "$(c 35 "$branch")"
on ctx && [ -n "$ctx" ] && add "ctx $(pc "$ctx")"
if on limits; then
  r=''
  [ -n "$five" ] && r="5h $(pc "$five")"
  [ -n "$week" ] && r="${r:+$r }7d $(pc "$week")"
  add "$r"
fi
on effort && [ -n "$effort" ] && add "$(c 90 "$effort")"
printf '%s' "$out"
