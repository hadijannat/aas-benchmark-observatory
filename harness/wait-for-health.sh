#!/usr/bin/env bash
set -euo pipefail

URL="${1:?Usage: wait-for-health.sh <url> [timeout_seconds]}"
TIMEOUT="${2:-120}"
INTERVAL=5
ELAPSED=0

printf "Waiting for %s (timeout %ss)" "$URL" "$TIMEOUT"

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
  if curl -sf "$URL" > /dev/null 2>&1; then
    printf "\nHealth check passed after %ss\n" "$ELAPSED"
    exit 0
  fi
  printf "."
  sleep "$INTERVAL"
  ELAPSED=$((ELAPSED + INTERVAL))
done

printf "\nTimeout after %ss waiting for %s\n" "$TIMEOUT" "$URL" >&2
exit 1
