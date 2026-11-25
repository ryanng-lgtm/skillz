#!/usr/bin/env bash
# @file progress.sh
# @brief Renders the OM Chat progress message of a backfill.
# @description
#   Reads rows from stdin, tab separated:
#
#     name <TAB> done <TAB> total <TAB> note
#
#   (runner.sh status prints group, done, total, last UTC time; prefix or
#   rename the first column per database before piping it here) and prints
#   the message text: the title line, then a ```progress block with one line
#   per row, `name: done/total | note`. Post the output unchanged.
#
#   Usage: progress.sh "<title>" < rows
set -euo pipefail

title=${1:?usage: progress.sh "<title>" < rows}
printf '%s\n```progress\n' "$title"
while IFS=$'\t' read -r name finished total note; do
    [[ -z $name ]] && continue
    if [[ -n $note ]]; then
        printf '%s: %s/%s | %s\n' "$name" "$finished" "$total" "$note"
    else
        printf '%s: %s/%s\n' "$name" "$finished" "$total"
    fi
done
printf '```\n'
