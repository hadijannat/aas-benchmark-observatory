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
RESULTS="["

for (( i=0; i<PROFILE_COUNT; i++ )); do
  SUITE="$(yq -r ".conformance.profiles[$i].suite" "$SDK_YAML")"
  PROFILE_DESC="$(yq -r ".conformance.profiles[$i].description" "$SDK_YAML")"
  OUTFILE="$OUTPUT_DIR/conformance_${i}.json"

  printf "Running conformance test %d/%d: %s (%s)\n" "$((i+1))" "$PROFILE_COUNT" "$SUITE" "$PROFILE_DESC"

  aas_test_engines check_server \
    --output json \
    "$API_BASE_URL" "$SUITE" \
    > "$OUTFILE" 2>&1 || true

  # Parse actual check counts from output
  read -r CHECKS_PASSED CHECKS_FAILED <<< "$(count_checks "$OUTFILE")"
  TOTAL_CHECKS_PASSED=$((TOTAL_CHECKS_PASSED + CHECKS_PASSED))
  TOTAL_CHECKS_FAILED=$((TOTAL_CHECKS_FAILED + CHECKS_FAILED))
  TOTAL=$((CHECKS_PASSED + CHECKS_FAILED))

  printf "  Profile result: %d/%d checks passed\n" "$CHECKS_PASSED" "$TOTAL"

  if [ "$i" -gt 0 ]; then
    RESULTS="${RESULTS},"
  fi
  RESULTS="${RESULTS}{\"index\":${i},\"suite\":\"${SUITE}\",\"description\":\"${PROFILE_DESC}\",\"checks_passed\":${CHECKS_PASSED},\"checks_failed\":${CHECKS_FAILED},\"checks_total\":${TOTAL},\"output_file\":\"conformance_${i}.json\"}"
done

RESULTS="${RESULTS}]"
GRAND_TOTAL=$((TOTAL_CHECKS_PASSED + TOTAL_CHECKS_FAILED))

printf '{"sdk_id":"%s","total_profiles":%d,"checks_passed":%d,"checks_failed":%d,"checks_total":%d,"results":%s}\n' \
  "$SDK_ID" "$PROFILE_COUNT" "$TOTAL_CHECKS_PASSED" "$TOTAL_CHECKS_FAILED" "$GRAND_TOTAL" "$RESULTS" \
  > "$OUTPUT_DIR/conformance_summary.json"

echo "Conformance summary written to $OUTPUT_DIR/conformance_summary.json"
printf "Overall: %d/%d checks passed across %d profiles\n" "$TOTAL_CHECKS_PASSED" "$GRAND_TOTAL" "$PROFILE_COUNT"
