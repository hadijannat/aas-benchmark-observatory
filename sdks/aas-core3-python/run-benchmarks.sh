#!/usr/bin/env bash
set -euo pipefail

DATASETS_DIR="${1:?Usage: $0 <datasets_dir> <output_dir>}"
OUTPUT_DIR="${2:?Usage: $0 <datasets_dir> <output_dir>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$OUTPUT_DIR"

# Convert to absolute paths
DATASETS_DIR="$(cd "$DATASETS_DIR" && pwd)"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

# Install dependencies
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

# Temp file for pytest-benchmark JSON output
BENCH_JSON="$(mktemp)"
MEMORY_JSON="$(mktemp)"
trap 'rm -f "$BENCH_JSON" "$MEMORY_JSON"' EXIT

# Run pytest-benchmark, exporting JSON results
export DATASETS_DIR
export MEMORY_JSON
pytest "$SCRIPT_DIR/bench_pipeline.py" \
  --benchmark-json="$BENCH_JSON" \
  --benchmark-disable-gc \
  --benchmark-warmup=on \
  -v

# Convert pytest-benchmark JSON to report.json
python3 "$SCRIPT_DIR/emit_report.py" \
  "$BENCH_JSON" \
  "$MEMORY_JSON" \
  "$OUTPUT_DIR/report.json"

echo "Report written to $OUTPUT_DIR/report.json"
