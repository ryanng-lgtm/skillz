#!/usr/bin/env bash
#
# preflight.sh — check the machine before a shared-dev run.
#
# Prints one line per check, "ok <check>" or "FAIL <check>: <detail>", and
# exits 1 when any check fails. Every external call has a timeout: Docker
# Desktop has hung in past sessions.
#
#   docker     Docker answers within 20 s
#   forbidden  no zmeta_local or local TimescaleDB container is running
#   backing    Sean's PC answers (check_connections.py --backing-only)
#   tailscale  only when backing fails: has sean-trontal's IP moved?
#   memory     Docker has at least --need-mib MiB
#   vpn        with --prod: the prod database names resolve
#
# Usage:
#   preflight.sh [--need-mib N] [--prod]

set -uo pipefail

SD="${SHARED_DEV:-$HOME/.config/shared-dev}"
need_mib=0
prod=0
while [ $# -gt 0 ]; do
	case "$1" in
	--need-mib) need_mib="$2" && shift 2 ;;
	--prod) prod=1 && shift ;;
	-h | --help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//' && exit 0 ;;
	*) printf 'preflight.sh: unknown argument: %s\n' "$1" >&2 && exit 2 ;;
	esac
done

failed=0
ok() { printf 'ok %s\n' "$*"; }
fail() {
	printf 'FAIL %s\n' "$*"
	failed=1
}

mem_bytes="$(timeout 20 docker info --format '{{.MemTotal}}' 2>&1)"
case $? in
0)
	ok docker
	ps_out="$(timeout 20 docker ps --format '{{.Names}}	{{.Label "com.docker.compose.project"}}' 2>&1)"
	forbidden="$(printf '%s\n' "$ps_out" | grep -iE 'zmeta|timescale' | tr '\t\n' ' ')"
	if [ -n "$forbidden" ]; then
		fail "forbidden: local TimescaleDB stack running: $forbidden"
	else
		ok forbidden
	fi
	if [ "$need_mib" -gt 0 ]; then
		have_mib=$((mem_bytes / 1024 / 1024))
		if [ "$have_mib" -ge "$need_mib" ]; then
			ok memory
		else
			fail "memory: Docker has $have_mib MiB, the run needs $need_mib MiB"
		fi
	fi
	;;
124) fail "docker: no answer in 20 s (Docker Desktop hung?)" ;;
*) fail "docker: $(printf '%s\n' "$mem_bytes" | head -1)" ;;
esac

backing="$(timeout 60 "$SD/.venv/bin/python" "$SD/check_connections.py" --backing-only 2>&1)"
backing_rc=$?
if [ "$backing_rc" -eq 0 ] && ! printf '%s\n' "$backing" | grep -q '^FAIL'; then
	ok backing
else
	fail "backing: $(printf '%s\n' "$backing" | grep '^FAIL' | tr '\n' ' ')"
	cfg_ip="$(python3 -I -c '
import json, sys
c = json.load(open(sys.argv[1]))
print(c["registry"]["kafka"]["bootstrap_servers"].split(":")[0])
' "$SD/config/tsdb-gateway-reader.yaml" 2>/dev/null)"
	ts_ip="$(timeout 10 tailscale status --json 2>/dev/null | python3 -I -c '
import json, sys
for peer in json.load(sys.stdin).get("Peer", {}).values():
    if peer.get("HostName") == "sean-trontal":
        print(peer["TailscaleIPs"][0] if peer.get("Online", True) else "offline")
' 2>/dev/null)"
	if [ -z "$ts_ip" ]; then
		fail "tailscale: sean-trontal not found in tailscale status"
	elif [ "$ts_ip" = offline ]; then
		fail "tailscale: sean-trontal is offline"
	elif [ "$ts_ip" != "$cfg_ip" ]; then
		fail "tailscale: sean-trontal moved to $ts_ip (configs use $cfg_ip)"
	else
		ok "tailscale: sean-trontal at $ts_ip, same as the configs"
	fi
fi

if [ "$prod" -eq 1 ]; then
	host=timescaledb-2.int.ore.kiyotaka.ai
	if timeout 5 python3 -I -c 'import socket, sys; socket.getaddrinfo(sys.argv[1], 5432)' "$host" >/dev/null 2>&1; then
		ok vpn
	else
		fail "vpn: $host does not resolve (connect the org VPN)"
	fi
fi

exit "$failed"
