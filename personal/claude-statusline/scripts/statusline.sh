#!/usr/bin/env bash
#
# Claude Code status line: model | folder | branch | ctx % | 5h % 7d % | effort.
# Claude Code pipes a JSON status to stdin and shows what this prints. Any part
# it doesn't report is skipped.

input=$(cat)
j() { printf '%s' "$input" | jq -r "$1 // empty"; }

model=$(j .model.display_name)
dir=$(j '.workspace.current_dir // .cwd')
ctx=$(j .context_window.used_percentage)
five=$(j .rate_limits.five_hour.used_percentage)
week=$(j .rate_limits.seven_day.used_percentage)
effort=$(j .effort.level)
branch=$(git -C "$dir" --no-optional-locks branch --show-current 2>/dev/null)

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

[ -n "$model" ] && add "$(c '1;36' "$model")"
[ -n "$dir" ] && add "$(c 34 "$(basename "$dir")")"
[ -n "$branch" ] && add "$(c 35 "$branch")"
[ -n "$ctx" ] && add "ctx $(pc "$ctx")"
r=''
[ -n "$five" ] && r="5h $(pc "$five")"
[ -n "$week" ] && r="${r:+$r }7d $(pc "$week")"
add "$r"
[ -n "$effort" ] && add "$(c 90 "$effort")"
printf '%s' "$out"
