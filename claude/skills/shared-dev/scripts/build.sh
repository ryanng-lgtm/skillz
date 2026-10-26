#!/usr/bin/env bash
#
# build.sh — build one linux/arm64 cgo binary from a Go source tree inside a
# golang container, the way shared-dev runs it.
#
# A host `go build` fails on confluent-kafka (`undefined: kafka.Event`) or
# yields a Mach-O binary, so the build runs in the container. Vendor is
# untracked in every backend repo, so `go mod vendor` runs on the host first.
#
# --replace MOD=DIR builds against a library worktree (kiyotaka-go,
# replayer) through a temporary modfile next to the output; the source tree's
# go.mod is never edited.
#
# Usage:
#   build.sh --src DIR --pkg ./cmd/X --out FILE [--image IMG] [--replace MOD=DIR ...]

set -euo pipefail

usage() {
	sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
	exit 2
}

src="" pkg="" out="" image="golang:1.27-alpine"
replaces=()
while [ $# -gt 0 ]; do
	case "$1" in
	--src) src="$2" && shift 2 ;;
	--pkg) pkg="$2" && shift 2 ;;
	--out) out="$2" && shift 2 ;;
	--image) image="$2" && shift 2 ;;
	--replace) replaces+=("$2") && shift 2 ;;
	-h | --help) usage ;;
	*) printf 'build.sh: unknown argument: %s\n' "$1" >&2 && exit 2 ;;
	esac
done
[ -n "$src" ] && [ -n "$pkg" ] && [ -n "$out" ] || usage

src="$(cd "$src" && pwd -P)"
out_dir="$(mkdir -p "$(dirname "$out")" && cd "$(dirname "$out")" && pwd -P)"
name="$(basename "$out")"

# A replace to a path outside the source tree would not exist in the
# container, and would build something other than the branch.
outside=0
while IFS= read -r line; do
	target="$(printf '%s\n' "$line" | sed -E 's/.*=>[[:space:]]*([^[:space:]]+).*/\1/')"
	case "$target" in
	/* | ./* | ../*) ;;
	*) continue ;;
	esac
	case "$target" in
	/*) resolved="$target" ;;
	*) resolved="$src/$target" ;;
	esac
	resolved="$(python3 -I -c 'import os, sys; print(os.path.normpath(sys.argv[1]))' "$resolved")"
	case "$resolved/" in
	"$src"/*) ;;
	*)
		printf 'build.sh: go.mod replaces a module with a path outside %s:\n  %s\n' "$src" "$line" >&2
		outside=1
		;;
	esac
done < <(grep -E '=>' "$src/go.mod" || true)
[ "$outside" -eq 0 ] || exit 1

modfile_flag=""
if [ "${#replaces[@]}" -gt 0 ]; then
	modfile="$out_dir/.$name.mod"
	cp "$src/go.mod" "$modfile"
	[ -f "$src/go.sum" ] && cp "$src/go.sum" "${modfile%.mod}.sum"
	for r in "${replaces[@]}"; do
		go mod edit -modfile="$modfile" -replace="$r"
	done
	(cd "$src" && go mod vendor -modfile="$modfile")
	modfile_flag="-modfile=/out/.$name.mod"
else
	(cd "$src" && go mod vendor)
fi

case "$image" in
*alpine*)
	prep='apk add --no-cache build-base >/dev/null'
	flags='-tags musl -ldflags "-linkmode external -extldflags -static"'
	;;
*)
	prep='true'
	flags=''
	;;
esac

gocache="$HOME/.cache/shared-dev/gocache"
mkdir -p "$gocache"
timeout 1800 docker run --rm --platform linux/arm64 \
	-v "$src:/ws" -v "$out_dir:/out" -v "$gocache:/root/.cache/go-build" -w /ws \
	-e CGO_ENABLED=1 -e GOFLAGS=-mod=vendor -e GOTOOLCHAIN=local \
	"$image" sh -c "$prep && go build -buildvcs=false $modfile_flag $flags -o /out/$name $pkg"

kind="$(file "$out")"
case "$kind" in
*"ELF 64-bit"*aarch64*) ;;
*)
	printf 'build.sh: %s is not a linux/arm64 ELF binary: %s\n' "$out" "$kind" >&2
	exit 1
	;;
esac
printf '%s\n' "$out"
