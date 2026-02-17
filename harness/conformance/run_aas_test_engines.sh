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

# Extract pass/fail counts from aas_test_engines JSON output
# Level 0 = ok, level 2 = warning, level 3 = error
count_checks() {
  python3 -c "
import json, sys
def count(node):
    p, f = 0, 0
    subs = node.get('s', [])
    if not subs:
        return (0, 1) if node.get('l', 0) >= 3 else (1, 0)
    for s in subs:
        sp, sf = count(s)
        p += sp; f += sf
    return p, f
try:
    data = json.load(open(sys.argv[1]))
    p, f = count(data)
    print(f'{p} {f}')
except: print('0 0')
" "$1"
}

TOTAL_CHECKS_PASSED=0
TOTAL_CHECKS_FAILED=0
EXECUTION_FAILURES=0
RESULTS="["

for (( i=0; i<PROFILE_COUNT; i++ )); do
  SUITE="$(yq -r ".conformance.profiles[$i].suite" "$SDK_YAML")"
  PROFILE_DESC="$(yq -r ".conformance.profiles[$i].description" "$SDK_YAML")"
  OUTFILE="$OUTPUT_DIR/conformance_${i}.json"

  printf "Running conformance test %d/%d: %s (%s)\n" "$((i+1))" "$PROFILE_COUNT" "$SUITE" "$PROFILE_DESC"

  CMD_STATUS=0
  aas_test_engines check_server \
    --output json \
    "$API_BASE_URL" "$SUITE" \
    > "$OUTFILE" 2>&1 || CMD_STATUS=$?

  JSON_PARSE_OK=0
  if python3 - "$OUTFILE" <<'PY'
import json
import sys
try:
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        json.load(f)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
  then
    JSON_PARSE_OK=1
  fi

  # Parse actual check counts from output
  CHECKS_PASSED=0
  CHECKS_FAILED=0
  if [ "$JSON_PARSE_OK" -eq 1 ]; then
    read -r CHECKS_PASSED CHECKS_FAILED <<< "$(count_checks "$OUTFILE")"
  fi

  PROFILE_FAILURE_STATE="ok"
  if [ "$JSON_PARSE_OK" -ne 1 ]; then
    PROFILE_FAILURE_STATE="parse_failed"
    EXECUTION_FAILURES=$((EXECUTION_FAILURES + 1))
  elif [ "$CMD_STATUS" -ne 0 ] && [ "$CHECKS_PASSED" -eq 0 ] && [ "$CHECKS_FAILED" -eq 0 ]; then
    # Treat non-zero exit as execution failure only if we could not derive any check result.
    # aas_test_engines may return non-zero for conformance findings while still emitting valid JSON.
    PROFILE_FAILURE_STATE="execution_failed"
    EXECUTION_FAILURES=$((EXECUTION_FAILURES + 1))
  elif [ "$CHECKS_FAILED" -gt 0 ]; then
    PROFILE_FAILURE_STATE="checks_failed"
  fi

  TOTAL_CHECKS_PASSED=$((TOTAL_CHECKS_PASSED + CHECKS_PASSED))
  TOTAL_CHECKS_FAILED=$((TOTAL_CHECKS_FAILED + CHECKS_FAILED))
  TOTAL=$((CHECKS_PASSED + CHECKS_FAILED))

  printf "  Profile result: %d/%d checks passed (state=%s)\n" "$CHECKS_PASSED" "$TOTAL" "$PROFILE_FAILURE_STATE"

  if [ "$i" -gt 0 ]; then
    RESULTS="${RESULTS},"
  fi
  RESULTS="${RESULTS}{\"index\":${i},\"suite\":\"${SUITE}\",\"description\":\"${PROFILE_DESC}\",\"checks_passed\":${CHECKS_PASSED},\"checks_failed\":${CHECKS_FAILED},\"checks_total\":${TOTAL},\"failure_state\":\"${PROFILE_FAILURE_STATE}\",\"output_file\":\"conformance_${i}.json\"}"
done

RESULTS="${RESULTS}]"
GRAND_TOTAL=$((TOTAL_CHECKS_PASSED + TOTAL_CHECKS_FAILED))
SUMMARY_FAILURE_STATE="ok"
if [ "$EXECUTION_FAILURES" -gt 0 ]; then
  SUMMARY_FAILURE_STATE="execution_failed"
elif [ "$TOTAL_CHECKS_FAILED" -gt 0 ]; then
  SUMMARY_FAILURE_STATE="checks_failed"
fi

printf '{"sdk_id":"%s","total_profiles":%d,"checks_passed":%d,"checks_failed":%d,"checks_total":%d,"execution_failures":%d,"failure_state":"%s","results":%s}\n' \
  "$SDK_ID" "$PROFILE_COUNT" "$TOTAL_CHECKS_PASSED" "$TOTAL_CHECKS_FAILED" "$GRAND_TOTAL" "$EXECUTION_FAILURES" "$SUMMARY_FAILURE_STATE" "$RESULTS" \
  > "$OUTPUT_DIR/conformance_summary.json"

echo "Conformance summary written to $OUTPUT_DIR/conformance_summary.json"
printf "Overall: %d/%d checks passed across %d profiles\n" "$TOTAL_CHECKS_PASSED" "$GRAND_TOTAL" "$PROFILE_COUNT"

if [ "$EXECUTION_FAILURES" -gt 0 ]; then
  echo "Conformance execution failures detected: $EXECUTION_FAILURES" >&2
  exit 2
fi
