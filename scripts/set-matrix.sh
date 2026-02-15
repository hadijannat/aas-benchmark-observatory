#!/usr/bin/env bash
set -euo pipefail

KNOWN_SDKS="$(dirname "$0")/../known-sdks.json"
MATRIX_TYPE="${1:?Usage: set-matrix.sh <sdk|server>}"

if [ "$MATRIX_TYPE" = "sdk" ]; then
  jq -c '{include: [.sdk_benchmarks[] | select(.enabled == true) | {id, name, language, adapter_dir}]}' "$KNOWN_SDKS"
elif [ "$MATRIX_TYPE" = "server" ]; then
  jq -c '{include: [.server_benchmarks[] | select(.enabled == true) | {id, name, adapter_dir}]}' "$KNOWN_SDKS"
else
  echo "Error: MATRIX_TYPE must be 'sdk' or 'server'" >&2
  exit 1
fi
