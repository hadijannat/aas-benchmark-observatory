#!/usr/bin/env bash
set -euo pipefail

DATASETS_DIR="${1:?Usage: $0 <datasets_dir> <output_dir>}"
OUTPUT_DIR="${2:?Usage: $0 <datasets_dir> <output_dir>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$OUTPUT_DIR"

export DATASETS_DIR

cd "$SCRIPT_DIR"

# Install dependencies
npm install

# Run benchmarks via tsx, outputs JSON to stdout
npx tsx bench_pipeline.ts > bench_raw.json

# Convert tinybench JSON output to report.json
node emit_report.js bench_raw.json "$OUTPUT_DIR/report.json"

echo "Report written to $OUTPUT_DIR/report.json"
