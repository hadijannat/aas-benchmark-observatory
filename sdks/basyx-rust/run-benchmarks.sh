#!/usr/bin/env bash
set -euo pipefail

DATASETS_DIR="${1:?Usage: $0 <datasets_dir> <output_dir>}"
OUTPUT_DIR="${2:?Usage: $0 <datasets_dir> <output_dir>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$OUTPUT_DIR"

# Convert to absolute paths before cd
DATASETS_DIR="$(cd "$DATASETS_DIR" && pwd)"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
export DATASETS_DIR

cd "$SCRIPT_DIR"

# Run criterion benchmarks with JSON output
cargo bench --bench pipeline -- --output-format=json 2>/dev/null | tee "$OUTPUT_DIR/criterion_raw.json" || true

# Convert criterion output to report.json
python3 "$SCRIPT_DIR/emit_report.py" \
  "$SCRIPT_DIR/target/criterion" \
  "$OUTPUT_DIR/report.json"

echo "Report written to $OUTPUT_DIR/report.json"
