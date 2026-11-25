#!/usr/bin/env bash
# @file runner.sh
# @brief Runs a backfill's units of work against one database, one psql per unit.
# @description
#   A unit is one line of a units file (tab separated):
#
#     group <TAB> unit <TAB> mode <TAB> statement
#
#   mode is `read` (read-only SQL), `write` (SQL that changes data) or `cmd`
#   (a shell command, e.g. a cjob or a vendor fetch; HOST is exported to it).
#   Units run in file order. A unit recorded as done in the state file is
#   skipped, so a rerun continues where the last run stopped.
#
#   Every SQL unit opens its own psql connection with application_name
#   `runner-<job>`. Before a write it waits until no other backend of the same
#   job still runs the same statement (pg_stat_activity), because a dropped
#   client can leave its backend running. A write is never retried by the
#   runner; a read that lost its connection (psql exit 2) is.
#
#   Per run: one log file under $RUNNER_LOG_DIR with one entry per unit (UTC
#   time, rc, seconds, statement, output). Per host and job: a state file
#   $RUNNER_STATE_DIR/<host>.<job>.json recording each finished unit. stdout
#   carries one `UNIT DONE` line per unit and one `GROUP DONE` line per
#   finished group, for a monitor to report.
#
#   The password comes from ~/.pgpass through psql only; this script never
#   reads it.
#
#   Environment (defaults in brackets):
#     RUNNER_PORT [5432]  RUNNER_DB [data]  RUNNER_USER [tsdb]
#     RUNNER_LOCK_TIMEOUT [10s]
#     RUNNER_WRITE_TIMEOUT [4h]       statement_timeout of writes
#     RUNNER_READ_TIMEOUT [10min]     statement_timeout of reads
#     RUNNER_WAIT_SECONDS [900]       longest wait for an earlier backend
#     RUNNER_READ_ATTEMPTS [30]       runs of a read whose connection drops
#     RUNNER_SLEEP [0]                pause between units, seconds
#     RUNNER_SEARCH_PATH []           search_path, e.g. a rehearsal schema
#     RUNNER_WRITE_ROLE []            role a write session switches to
#     RUNNER_STATE_DIR [./state]  RUNNER_LOG_DIR [./logs]
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
    runner.sh run    --host <host> --job <name> --units <file> [--only <group>] [--dry-run]
    runner.sh status --host <host> --job <name> --units <file>
    runner.sh -h | --help

Commands:
    run      Run every unit not yet recorded as done, in file order. Stops at
             the first failure.
    status   Print one line per group: group, done, total, UTC time of the
             last finished unit as HH:MM UTC YYYY-MM-DD (tab separated, for
             progress.sh).

Options:
    --host <host>    Database host.
    --job <name>     Job name: application_name suffix and state file name.
    --units <file>   Units file (group, unit, mode, statement; tab separated).
    --only <group>   Run one group only.
    --dry-run        Print the target and each statement; connect to nothing.
EOF
}

: "${RUNNER_PORT:=5432}" "${RUNNER_DB:=data}" "${RUNNER_USER:=tsdb}"
: "${RUNNER_LOCK_TIMEOUT:=10s}" "${RUNNER_WRITE_TIMEOUT:=4h}" "${RUNNER_READ_TIMEOUT:=10min}"
: "${RUNNER_WAIT_SECONDS:=900}" "${RUNNER_READ_ATTEMPTS:=30}" "${RUNNER_SLEEP:=0}"
: "${RUNNER_SEARCH_PATH:=}" "${RUNNER_WRITE_ROLE:=}"
: "${RUNNER_STATE_DIR:=./state}" "${RUNNER_LOG_DIR:=./logs}"

COMMAND=${1:-}
shift || true
HOST='' JOB='' UNITS='' ONLY='' DRY_RUN=0
while (($#)); do
    case $1 in
    --host) HOST=$2 && shift 2 ;;
    --job) JOB=$2 && shift 2 ;;
    --units) UNITS=$2 && shift 2 ;;
    --only) ONLY=$2 && shift 2 ;;
    --dry-run) DRY_RUN=1 && shift ;;
    -h | --help) usage && exit 0 ;;
    *) echo "unknown option: $1" >&2 && usage >&2 && exit 2 ;;
    esac
done
case $COMMAND in
run | status) ;;
-h | --help) usage && exit 0 ;;
*) usage >&2 && exit 2 ;;
esac
[[ -n $HOST && -n $JOB && -f $UNITS ]] || {
    echo '--host, --job and an existing --units file are required' >&2
    exit 2
}

APP_NAME=runner-$JOB
STATE=$RUNNER_STATE_DIR/$HOST.$JOB.json
export HOST

utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

conninfo() {
    printf 'host=%s port=%s dbname=%s user=%s connect_timeout=15' \
        "$HOST" "$RUNNER_PORT" "$RUNNER_DB" "$RUNNER_USER"
}

pgoptions() {
    local extra=''
    [[ -n $RUNNER_SEARCH_PATH ]] && extra+=" -c search_path=$RUNNER_SEARCH_PATH"
    if [[ $1 == read ]]; then
        printf -- '-c timezone=UTC -c default_transaction_read_only=on -c lock_timeout=%s -c statement_timeout=%s%s' \
            "$RUNNER_LOCK_TIMEOUT" "$RUNNER_READ_TIMEOUT" "$extra"
    else
        [[ -n $RUNNER_WRITE_ROLE ]] && extra+=" -c role=$RUNNER_WRITE_ROLE"
        printf -- '-c timezone=UTC -c lock_timeout=%s -c statement_timeout=%s%s' \
            "$RUNNER_LOCK_TIMEOUT" "$RUNNER_WRITE_TIMEOUT" "$extra"
    fi
}

# Runs one SQL statement in its own connection; output in OUT, returns psql's rc.
psql_once() {
    local rc=0
    OUT=$(PGAPPNAME=$APP_NAME PGOPTIONS=$(pgoptions "$1") \
        psql --no-password -X -v ON_ERROR_STOP=1 -At "$(conninfo)" -c "$2" 2>&1 </dev/null) || rc=$?
    return "$rc"
}

log() { printf '%s\n' "$*" >>"$LOG"; }

# Waits until no other backend of this job runs the same statement text.
guard_wait() {
    local statement=$1 waited=0 guard
    # shellcheck disable=SC2016 # $runner$ is an SQL dollar quote
    guard="SELECT count(*) FROM pg_stat_activity WHERE application_name = '$APP_NAME' AND pid <> pg_backend_pid() AND state IS DISTINCT FROM 'idle' AND query = \$runner\$$statement\$runner\$;"
    while true; do
        psql_once read "$guard" || {
            log "$(utc) guard read failed: $OUT"
            return 1
        }
        [[ $OUT == 0 ]] && return 0
        ((waited >= RUNNER_WAIT_SECONDS)) && {
            log "$(utc) an earlier backend still runs this statement after ${waited}s"
            return 1
        }
        log "$(utc) waiting 30s: an earlier backend still runs this statement"
        sleep 30
        waited=$((waited + 30))
    done
}

state_done() {
    [[ -f $STATE ]] && jq -e --arg u "$1" '.done[$u] != null' "$STATE" >/dev/null
}

state_mark() {
    local tmp
    mkdir -p "$RUNNER_STATE_DIR"
    [[ -f $STATE ]] || echo '{"done":{}}' >"$STATE"
    tmp=$(mktemp "$STATE.XXXXXX")
    jq --arg u "$1" --arg at "$(utc)" --argjson s "$2" '.done[$u] = {at: $at, seconds: $s}' "$STATE" >"$tmp"
    mv "$tmp" "$STATE"
}

run_unit() {
    local mode=$1 statement=$2 rc=0 attempt=1
    case $mode in
    cmd)
        OUT=$(bash -c "$statement" 2>&1 </dev/null) || rc=$?
        ;;
    write)
        guard_wait "$statement" || return 1
        psql_once write "$statement" || rc=$?
        ;;
    read)
        while true; do
            rc=0
            psql_once read "$statement" || rc=$?
            ((rc == 2 && attempt < RUNNER_READ_ATTEMPTS)) || break
            log "$(utc) connection lost on a read, attempt $attempt, next in 60s"
            sleep 60
            attempt=$((attempt + 1))
        done
        ;;
    *)
        OUT="unknown mode: $mode"
        rc=2
        ;;
    esac
    return "$rc"
}

status() {
    awk -F'\t' '!/^#/ && NF >= 4 {print $1 "\t" $2}' "$UNITS" | while IFS=$'\t' read -r group unit; do
        if state_done "$unit"; then
            printf '%s\t1\t%s\n' "$group" "$(jq -r --arg u "$unit" '.done[$u].at' "$STATE")"
        else
            printf '%s\t0\t\n' "$group"
        fi
    done | awk -F'\t' '
        { if (!($1 in total)) order[n++] = $1; total[$1]++; done[$1] += $2; if ($3 > last[$1]) last[$1] = $3 }
        END { for (i = 0; i < n; i++) { g = order[i]; t = last[g]; if (t != "") t = substr(t, 12, 5) " UTC " substr(t, 1, 10); printf "%s\t%d\t%d\t%s\n", g, done[g], total[g], t } }'
}

if [[ $COMMAND == status ]]; then
    status
    exit 0
fi

if ((DRY_RUN)); then
    printf 'target: %s\napplication_name: %s\nstate: %s\n' "$(conninfo)" "$APP_NAME" "$STATE"
    printf 'read options: %s\nwrite options: %s\n' "$(pgoptions read)" "$(pgoptions write)"
fi

mkdir -p "$RUNNER_LOG_DIR"
LOG=$RUNNER_LOG_DIR/$HOST-$JOB-$(date -u +%Y%m%dT%H%M%SZ).log
((DRY_RUN)) && LOG=/dev/null
log "$(utc) START $JOB on $HOST (units: $UNITS)"

declare -A left=()
while IFS=$'\t' read -r group unit _ _; do
    [[ -z $group || $group == \#* ]] && continue
    state_done "$unit" || left[$group]=$((${left[$group]:-0} + 1))
done <"$UNITS"

while IFS=$'\t' read -r group unit mode statement <&3; do
    [[ -z $group || $group == \#* ]] && continue
    [[ -n $ONLY && $group != "$ONLY" ]] && continue
    state_done "$unit" && continue
    if ((DRY_RUN)); then
        printf -- '-- %s %s (%s)\n%s\n' "$group" "$unit" "$mode" "$statement"
        continue
    fi
    started=$SECONDS
    rc=0
    run_unit "$mode" "$statement" || rc=$?
    seconds=$((SECONDS - started))
    log "$(utc) $group $unit rc=$rc ${seconds}s $mode: $statement"
    [[ -n ${OUT:-} ]] && printf '%s\n' "$OUT" | sed 's/^/    /' >>"$LOG"
    if ((rc != 0)); then
        log "$(utc) STOPPED at $unit"
        echo "UNIT FAILED $group $unit rc=$rc $(utc) log=$LOG"
        exit 1
    fi
    state_mark "$unit" "$seconds"
    left[$group]=$((left[$group] - 1))
    echo "UNIT DONE $group $unit ${seconds}s $(utc)"
    ((left[$group] == 0)) && echo "GROUP DONE $group $(utc)"
    ((RUNNER_SLEEP > 0)) && sleep "$RUNNER_SLEEP"
done 3<"$UNITS"

log "$(utc) DONE"
((DRY_RUN)) || echo "RUN DONE $JOB $HOST $(utc) log=$LOG"
