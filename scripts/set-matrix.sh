#!/usr/bin/env bash
set -euo pipefail

KNOWN_SDKS="$(dirname "$0")/../known-sdks.json"

jq -c '{include: [.[] | select(.enabled == true) | {id, name, adapter_dir}]}' "$KNOWN_SDKS"
