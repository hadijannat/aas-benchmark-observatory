#!/usr/bin/env bash
set -euo pipefail

SDK_YAML="${1:?Usage: run_aas_test_engines.sh <sdk.yaml> <output_dir>}"
OUTPUT_DIR="${2:?Usage: run_aas_test_engines.sh <sdk.yaml> <output_dir>}"

command -v yq >/dev/null 2>&1 || { echo "Error: yq is required but not installed." >&2; exit 1; }
command -v aas_test_engines >/dev/null 2>&1 || { echo "Error: aas-test-engines is required but not installed." >&2; exit 1; }

mkdir -p "$OUTPUT_DIR"

SDK_ID="$(yq -r '.id' "$SDK_YAML")"
API_BASE_URL="$(yq -r '.api_base_url' "$SDK_YAML")"
PROFILE_COUNT="$(yq -r '.conformance.profiles | length' "$SDK_YAML")"

PASSED=0
FAILED=0
RESULTS="["

for (( i=0; i<PROFILE_COUNT; i++ )); do
  PROFILE_NAME="$(yq -r ".conformance.profiles[$i].name" "$SDK_YAML")"
  PROFILE_DESC="$(yq -r ".conformance.profiles[$i].description" "$SDK_YAML")"
  OUTFILE="$OUTPUT_DIR/conformance_${i}.json"

  printf "Running conformance test %d/%d: %s (%s)\n" "$((i+1))" "$PROFILE_COUNT" "$PROFILE_NAME" "$PROFILE_DESC"

  if aas_test_engines check_server --server "$API_BASE_URL" --output "$OUTFILE" 2>&1; then
    STATUS="pass"
    PASSED=$((PASSED + 1))
  else
    STATUS="fail"
    FAILED=$((FAILED + 1))
  fi

  if [ "$i" -gt 0 ]; then
    RESULTS="${RESULTS},"
  fi
  RESULTS="${RESULTS}{\"index\":${i},\"profile\":\"${PROFILE_NAME}\",\"description\":\"${PROFILE_DESC}\",\"status\":\"${STATUS}\",\"output_file\":\"conformance_${i}.json\"}"
done

RESULTS="${RESULTS}]"

printf '{"sdk_id":"%s","total_profiles":%d,"passed":%d,"failed":%d,"results":%s}\n' \
  "$SDK_ID" "$PROFILE_COUNT" "$PASSED" "$FAILED" "$RESULTS" \
  > "$OUTPUT_DIR/conformance_summary.json"

echo "Conformance summary written to $OUTPUT_DIR/conformance_summary.json"

if [ "$FAILED" -gt 0 ]; then
  echo "WARNING: $FAILED/$PROFILE_COUNT profiles failed."
  exit 1
fi
