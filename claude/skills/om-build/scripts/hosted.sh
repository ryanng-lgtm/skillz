#!/usr/bin/env bash
# om-build --hosted, end to end. See ../SKILL.md for why each step exists.
#
#   hosted.sh            build + install if the gate says to
#   hosted.sh --gate     run the skip gate only, print BUILD/SKIP, exit
#   hosted.sh --force    build even if the gate says SKIP
#   hosted.sh --no-gui   skip the GUI bundle (daemon only; /rooms serves the placeholder)
#
# Exit: 0 ok (including SKIP), 1 failure. Restores the GUI stubs on every path.

set -uo pipefail

die_early() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# Paths default to this box's layout; override to run it anywhere else.
MONO=${OM_MONO:-$HOME/github/openmarket-internal}
GUI=${OM_GUI:-$HOME/github/openmarket-chat}
SLOT="$MONO/packages/cli/assets/rooms-gui"
PLIST=${OM_PLIST:-$HOME/Library/LaunchAgents/xyz.openmarket.runner.plist}
[ -d "$MONO" ] || die_early "monorepo not at $MONO (set OM_MONO)"
[ -d "$GUI" ]  || die_early "GUI repo not at $GUI (set OM_GUI)"
HEALTH=http://127.0.0.1:31337/healthz
ROOMS=http://127.0.0.1:31337/rooms/

GATE_ONLY=0; FORCE=0; NO_GUI=0
for a in "$@"; do case "$a" in
  --gate) GATE_ONLY=1 ;; --force) FORCE=1 ;; --no-gui) NO_GUI=1 ;;
  --hosted) ;;   # accepted and ignored; this script is the hosted target
  *) echo "unknown flag: $a" >&2; exit 1 ;;
esac; done

say() { printf '%s\n' "$*"; }
die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

# Staged assets are a working-tree overwrite of committed stubs. Restore them on
# EVERY exit path -- failure and Ctrl-C included, which is where they used to leak.
STAGED=0
cleanup() {
  [ "$STAGED" = 1 ] || return 0
  git -C "$MONO" checkout -- packages/cli/assets/rooms-gui/ 2>/dev/null
  rm -f "$MONO"/packages/cli/.*.bun-build
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- provenance
say "== provenance =="
for R in "$MONO" "$GUI"; do
  git -C "$R" fetch --quiet origin 2>/dev/null
  BR=$(git -C "$R" rev-parse --abbrev-ref HEAD)
  [ "$BR" = HEAD ] && BR="detached@$(git -C "$R" rev-parse --short HEAD)"
  D=$(git -C "$R" status --porcelain | wc -l | tr -d ' ')
  WT=$(git -C "$R" rev-parse --git-common-dir); [ "$WT" = .git ] && WT="" || WT=" [linked worktree]"
  UP=$(git -C "$R" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo "no upstream")
  AB=$(git -C "$R" rev-list --left-right --count "$UP"...HEAD 2>/dev/null | awk '{print "behind "$1", ahead "$2}')
  printf '%-22s %s @ %s  %s  dirty=%s%s\n' "$(basename "$R")" "$BR" \
    "$(git -C "$R" rev-parse --short HEAD)" "${AB:-$UP}" "$D" "$WT"
done

# Where does the daemon actually live? Read it, never assume -- the plist has
# been repointed at the repo build tree before (openmarket-chat #603).
TARGET=$(sed -n '/ProgramArguments/,/<\/array>/p' "$PLIST" 2>/dev/null \
         | grep -o '<string>[^<]*om</string>' | head -1 | sed 's/<[^>]*>//g')
[ -n "$TARGET" ] || TARGET=/opt/homebrew/bin/om
[ -e "$TARGET" ] || die "cannot determine the daemon binary from $PLIST or PATH"
# Resolve it. The plist normally names /opt/homebrew/bin/om, which is a SYMLINK,
# and macOS `stat -f` is lstat -- it would report the link's own inode (size 49,
# the target path string) and check [1] could never match the running binary.
TARGET=$(realpath "$TARGET")
case "$TARGET" in *dist/om) MODE=repo ;; *) MODE=versioned ;; esac
say "daemon target:         $TARGET  [$MODE]"
case "$TARGET" in *"/Cellar/openmarket/"*) die "target is a Homebrew install -- see SKILL.md hard rules" ;; esac

# ---------------------------------------------------------------- skip gate
say ""; say "== gate =="
need=0; why=""
flag() { need=1; why="${why:+$why; }$1"; }
health=$(curl -s --max-time 5 "$HEALTH")
pid=$(printf '%s' "$health" | sed -n 's/.*"pid":\([0-9]*\).*/\1/p')

if [ -z "$pid" ]; then
  flag "daemon not answering on 31337"
else
  disk=$(stat -f '%i' "$TARGET" 2>/dev/null)
  # match /om$, NOT /bin\/om/ -- the narrow pattern silently misses a repo-tree
  # daemon and reports an empty inode as if the daemon were sick.
  live=$(lsof -p "$pid" 2>/dev/null | awk '$4=="txt" && $NF ~ /\/om$/ {print $(NF-1); exit}')
  say "  [1] inode disk=$disk live=$live"
  [ "$disk" = "$live" ] || flag "daemon runs inode ${live:-<none>}, disk has $disk"
fi

src_ver=$(grep -m1 '"version"' "$MONO/packages/cli/package.json" | grep -o '[0-9][0-9.]*')
run_ver=$(printf '%s' "$health" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')
say "  [2] source=$src_ver daemon=${run_ver:-<none>}"
[ "$src_ver" = "$run_ver" ] || flag "daemon ${run_ver:-down}, source $src_ver"

built=$(grep -o 'rooms\.js?v=[a-f0-9]*' "$GUI/dist/index.html" 2>/dev/null | head -1)
served=$(curl -s --max-time 5 "$ROOMS" | grep -o 'rooms\.js?v=[a-f0-9]*' | head -1)
say "  [3] built=${built:-<none>} served=${served:-<none>}"
{ [ -n "$built" ] && [ "$built" = "$served" ]; } || flag "served ${served:-none}, built ${built:-none}"

newer() { find "$1" -type f -newer "$2" 2>/dev/null | wc -l | tr -d ' '; }
n=$(newer "$GUI/src" "$GUI/dist/index.html")
say "  [4] GUI src newer: $n";          [ "$n" = 0 ] || flag "$n GUI src file(s) newer than dist"
n=$(newer "$MONO/packages/rooms-client/src" "$MONO/packages/rooms-client/dist/version.js")
say "  [5] rooms-client src newer: $n"; [ "$n" = 0 ] || flag "$n rooms-client src file(s) newer than dist"
RC_STALE=$n
n=$(newer "$MONO/packages/cli/src" "$TARGET")
say "  [6] cli src newer: $n";          [ "$n" = 0 ] || flag "$n packages/cli src file(s) newer than the daemon binary"

# [7] protocol era. Direction matters: linked NEWER than the GUI's pin is a
# benign superset; linked OLDER is the skew that breaks sign-in.
pin=$(grep '"@openmarket/rooms-client"' "$GUI/package.json" | grep -o '[0-9][0-9.]*')
pkg=$(grep -m1 '"version"' "$MONO/packages/rooms-client/package.json" | grep -o '[0-9][0-9.]*')
printf '  [7] protocol: GUI pins %s, linked %s -> ' "$pin" "$pkg"
if [ "$pin" = "$pkg" ]; then say "match"
elif [ "$(printf '%s\n%s' "$pin" "$pkg" | sort -V | head -1)" = "$pin" ]; then say "linked newer (superset), benign"
else say "SKEW"; flag "PROTOCOL SKEW: GUI pins $pin, linked is OLDER at $pkg"; fi

say ""
if [ "$need" -eq 0 ]; then
  say "SKIP -- nothing to build (daemon $run_ver, pid $pid, stamp ${served#rooms.js?v=})"
  [ "$FORCE" = 1 ] || exit 0
  say "(--force given, building anyway)"
else
  say "BUILD -- $why"
fi
[ "$GATE_ONLY" = 1 ] && exit 0

# ---------------------------------------------------------------- build
if [ "$NO_GUI" = 0 ]; then
  say ""; say "== build =="
  ( cd "$MONO" && bun install ) >/dev/null 2>&1 || die "monorepo bun install"
  if [ "${RC_STALE:-0}" != 0 ] || [ "$src_ver" != "$run_ver" ]; then
    # tsc exits 2 on three known TS2835 imports but still emits -- don't gate on it
    ( cd "$MONO/packages/rooms-client" && bun run build ) >/dev/null 2>&1
    grep -q 'VERSION' "$MONO/packages/rooms-client/dist/version.js" || die "rooms-client build emitted nothing"
    say "rooms-client:          $(grep -o '"[0-9][0-9.]*"' "$MONO/packages/rooms-client/dist/version.js" | head -1 | tr -d '"')"
  fi

  ( cd "$GUI" && bun install ) >/dev/null 2>&1 || die "GUI bun install"
  STAMPLINE=$( cd "$GUI" && bun run build 2>&1 | grep 'stamp-asset-versions OK' )
  [ -n "$STAMPLINE" ] || die "GUI build produced no stamp line"
  STAMP=$(printf '%s' "$STAMPLINE" | grep -o '?v=[a-f0-9]*' | cut -d= -f2)
  say "stamp:                 $STAMP"
  for f in dist/assets/rooms.js dist/assets/rooms.css dist/index.html dist/sw.js dist/manifest.webmanifest; do
    [ -f "$GUI/$f" ] || die "GUI build incomplete: missing $f"
  done

  # A rebuild that reproduces the live stamp is nothing to install. Common after
  # a checkout that only moved mtimes, or a squash-merge of the branch you built.
  if [ "$FORCE" = 0 ] && [ "rooms.js?v=$STAMP" = "$served" ] && [ "$src_ver" = "$run_ver" ] && [ -n "$pid" ]; then
    say ""; say "NOTHING TO INSTALL -- rebuild reproduced the live stamp $STAMP"
    exit 0
  fi

  say ""; say "== stage =="
  cp "$GUI/dist/assets/rooms.js"  "$SLOT/rooms.js"  || die "stage rooms.js"
  cp "$GUI/dist/assets/rooms.css" "$SLOT/rooms.css" || die "stage rooms.css"
  cp "$GUI/dist/index.html"       "$SLOT/index.html.txt" || die "stage index.html"
  STAGED=1
  ( cd "$MONO" && bun packages/cli/scripts/pack-rooms-gui-extra.ts "$GUI/dist" "$SLOT/extra.json.txt" ) >/dev/null 2>&1 \
    || die "pack-rooms-gui-extra"
  grep -l "__OM_ROOMS_GUI_STUB__" "$SLOT/rooms.js" "$SLOT/extra.json.txt" >/dev/null 2>&1 \
    && die "stub marker still present -- the embed would serve the placeholder"
  say "staged"
fi

# ---------------------------------------------------------------- compile
say ""; say "== compile =="
OUT="$MONO/packages/cli/dist/om"
# In repo mode the compile output IS the running binary. bun would write over a
# file launchd is executing, so stop the service first (mv-not-cp, same reason).
STOPPED=0
if [ "$MODE" = repo ] && [ -n "$pid" ]; then
  om service stop >/dev/null 2>&1 && STOPPED=1
  sleep 3
  curl -s -o /dev/null -m 3 "$HEALTH" && die "service still answering after stop; refusing to overwrite a running binary"
fi
( cd "$MONO" && bun install && bun run build ) >/dev/null 2>&1 || die "monorepo compile"
[ -x "$OUT" ] || die "no binary at $OUT"
NEWVER=$("$OUT" --version) || die "compiled binary will not run"
SIZE=$(ls -lh "$OUT" | awk '{print $5}')
say "binary:                $SIZE, $NEWVER"
if [ "$NO_GUI" = 0 ]; then
  EMB=$(grep -o 'rooms\.js?v=[a-f0-9]*' "$SLOT/index.html.txt" | head -1)
  [ "$EMB" = "rooms.js?v=$STAMP" ] || die "embedded stamp $EMB != built $STAMP"
fi

# ---------------------------------------------------------------- install
say ""; say "== install =="
if [ "$MODE" = repo ]; then
  say "in place at $OUT (launchd runs it directly)"
  [ "$STOPPED" = 1 ] && { om service start >/dev/null 2>&1 || die "service start"; } \
                     || { om service restart >/dev/null 2>&1 || die "service restart"; }
else
  DEST=~/.local/opt/openmarket/"$NEWVER"/bin/om
  [ -e "$DEST" ] && say "NOTE: overwriting $NEWVER in place -- the outgoing binary is gone, rollback reverts the version"
  mkdir -p "$(dirname "$DEST")"
  mv "$OUT" "$DEST" || die "mv into $DEST"      # mv, never cp
  chmod +x "$DEST"
  ln -sfn "$DEST" /opt/homebrew/bin/om || die "symlink repoint"
  say "installed:             $DEST"
  om service restart >/dev/null 2>&1 || die "service restart"
fi
sleep 15

cleanup; STAGED=0
say "monorepo dirty:        $(git -C "$MONO" status --short | wc -l | tr -d ' ')"
say "GUI repo dirty:        $(git -C "$GUI" status --short | wc -l | tr -d ' ')"

# ---------------------------------------------------------------- verify
say ""; say "== verify =="
h=$(curl -s --max-time 10 "$HEALTH")
NPID=$(printf '%s' "$h" | sed -n 's/.*"pid":\([0-9]*\).*/\1/p')
[ -n "$NPID" ] || die "daemon not answering after restart"
say "daemon:                $(printf '%s' "$h" | sed -n 's/.*"version":"\([^"]*\)".*/\1/p') pid $NPID"
if curl -s --max-time 10 "$ROOMS" | grep -q OM_ROOMS_GUI_DIR; then
  [ "$NO_GUI" = 1 ] && say "GUI:                   placeholder (--no-gui, expected)" \
                    || die "live daemon is serving the PLACEHOLDER"
else
  LIVE=$(curl -s --max-time 10 "$ROOMS" | grep -o 'rooms\.js?v=[a-f0-9]*')
  say "GUI:                   real, $LIVE"
  [ "$NO_GUI" = 1 ] || [ "$LIVE" = "rooms.js?v=$STAMP" ] || die "live stamp $LIVE != built $STAMP"
fi

J=$(mktemp); curl -s -c "$J" -o /dev/null --max-time 5 "$ROOMS"
AUTH=$(curl -s --max-time 9 -b "$J" -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  "http://127.0.0.1:31337/ws/rooms" 2>/dev/null | strings | grep -oE '"type":"[A-Z_]+"|"username":"[^"]*"' | head -2 | tr '\n' ' ')
rm -f "$J"
say "auth:                  ${AUTH:-NO HANDSHAKE}"
case "$AUTH" in *AUTH_SUCCESS*) ;; *) say "  ^^ sign-in did not complete -- check the protocol pin" ;; esac

BIND=$(lsof -nP -iTCP:31337 -sTCP:LISTEN | awk 'NR==2{print $9}')
say "listener:              ${BIND:-none}"
case "$BIND" in 127.0.0.1:*) ;; *) say "  ^^ not IPv4 loopback -- the MacBook tunnel cannot reach it" ;; esac

LE=$(printf '%s' "$h" | sed -n 's/.*"last_error":"\([^"]*\)".*/\1/p' | head -c 110)
[ -n "$LE" ] && say "last error:            $LE"
say "pending consents:      $(om agent grants requests --status pending 2>/dev/null | head -1)"
say ""
say "OPEN: http://localhost:31337/rooms#/"
