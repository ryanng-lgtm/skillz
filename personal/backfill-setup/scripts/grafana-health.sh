#!/usr/bin/env bash
# @file grafana-health.sh
# @brief Reads database host health from Prometheus through Grafana, read-only.
# @description
#   For each --instance (an instance_name label, e.g. timescaledb-3) prints one
#   line: memory available, deadlocks in the last hour, free space on the
#   largest filesystem, busiest disk's IO time, then OK or the flags that
#   tripped. With --every it repeats until killed; memory only flags after
#   three low readings in a row, since a host can dip for a minute by itself.
#
#   The token is read from --token-file and only ever sent as a header; it is
#   never printed. Only the datasource proxy's query path is called.
#
#   Labels as on the ore cluster in 2026-11: node metrics under
#   job="timescaledb", Postgres metrics under job="timescaledb-postgresql-metric",
#   both with instance_name. Check them with one manual query on another
#   cluster before relying on the flags.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
    grafana-health.sh --instance <name> [--instance <name>...] [options]

Options:
    --datasource <uid>   Prometheus datasource uid [PACDA894871293EDF, prometheus-ore]
    --token-file <path>  Grafana token file [~/.grafana_token]
    --every <seconds>    Repeat every N seconds; 0 runs once [0]
    --mem-min <pct>      Flag memory available under this [12]
    --deadlocks-max <n>  Flag more deadlocks than this in 1 h [2]
    --disk-min <pct>     Flag free space under this on the largest filesystem [8]
    --io-max <pct>       Flag the busiest disk's IO time over this [90]
EOF
}

INSTANCES=() DS=PACDA894871293EDF TOKEN_FILE=~/.grafana_token EVERY=0
MEM_MIN=12 DEAD_MAX=2 DISK_MIN=8 IO_MAX=90
while (($#)); do
    case $1 in
    --instance) INSTANCES+=("$2") && shift 2 ;;
    --datasource) DS=$2 && shift 2 ;;
    --token-file) TOKEN_FILE=$2 && shift 2 ;;
    --every) EVERY=$2 && shift 2 ;;
    --mem-min) MEM_MIN=$2 && shift 2 ;;
    --deadlocks-max) DEAD_MAX=$2 && shift 2 ;;
    --disk-min) DISK_MIN=$2 && shift 2 ;;
    --io-max) IO_MAX=$2 && shift 2 ;;
    -h | --help) usage && exit 0 ;;
    *) echo "unknown option: $1" >&2 && usage >&2 && exit 2 ;;
    esac
done
((${#INSTANCES[@]})) || {
    usage >&2
    exit 2
}

TOKEN=$(grep -v '^#' "$TOKEN_FILE" | head -1)
API=https://grafana.occ.kiyotaka.dev/api/datasources/proxy/uid/$DS/api/v1/query

# One instant query; prints the first value or nothing.
q() {
    curl -s -m 20 -H "Authorization: Bearer $TOKEN" "$API" --data-urlencode "query=$1" |
        jq -r '.data.result[0].value[1] // empty' 2>/dev/null
}

lt() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a < b) }'; }
round() { awk -v a="$1" 'BEGIN { printf "%.1f", a }'; }

declare -A LOW=()
while true; do
    for i in "${INSTANCES[@]}"; do
        node="job=\"timescaledb\",instance_name=\"$i\""
        fs="$node,fstype!~\"tmpfs|overlay|squashfs|ramfs\""
        mem=$(q "100 * max(node_memory_MemAvailable_bytes{$node} / node_memory_MemTotal_bytes{$node})")
        dead=$(q "sum(increase(pg_stat_database_deadlocks{job=\"timescaledb-postgresql-metric\",instance_name=\"$i\"}[1h]))")
        size=$(q "max(node_filesystem_size_bytes{$fs})")
        free=$(q "max(node_filesystem_avail_bytes{$fs} and on(mountpoint) (node_filesystem_size_bytes{$fs} == scalar(max(node_filesystem_size_bytes{$fs}))))")
        io=$(q "100 * max(rate(node_disk_io_time_seconds_total{$node}[5m]))")
        flags=()
        if [[ -n $mem ]] && lt "$mem" "$MEM_MIN"; then
            LOW[$i]=$((${LOW[$i]:-0} + 1))
            ((LOW[$i] >= 3 || EVERY == 0)) && flags+=("memory under ${MEM_MIN}%")
        else
            LOW[$i]=0
        fi
        [[ -n $dead ]] && lt "$DEAD_MAX" "$dead" && flags+=("deadlocks over $DEAD_MAX/h")
        pct=''
        if [[ -n $free && -n $size ]]; then
            pct=$(awk -v f="$free" -v s="$size" 'BEGIN { printf "%.0f", 100 * f / s }')
            lt "$pct" "$DISK_MIN" && flags+=("disk free under ${DISK_MIN}%")
        fi
        [[ -n $io ]] && lt "$IO_MAX" "$io" && flags+=("IO over ${IO_MAX}%")
        line="$(date -u +%H:%MZ) $i mem=${mem:+$(round "$mem")%} deadlocks_1h=${dead:+$(round "$dead")}"
        line+=" disk_free=${free:+$(awk -v f="$free" 'BEGIN { printf "%.2fTB", f / 1e12 }')}${pct:+ (${pct}%)}"
        line+=" io=${io:+$(round "$io")%}"
        if ((${#flags[@]})); then
            printf '%s | FLAG: %s\n' "$line" "$(
                IFS=,
                echo "${flags[*]}"
            )"
        else
            printf '%s | OK\n' "$line"
        fi
    done
    ((EVERY > 0)) || exit 0
    sleep "$EVERY"
done
