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
export OUTPUT_DIR

cd "$SCRIPT_DIR"

# Download pinned module dependencies from go.mod/go.sum
go mod download

# Run Go benchmarks with JSON output
# -count=5 for statistical significance, -benchmem for allocation stats
# OUTPUT_DIR is exported so TestMain can write memory_stats.json there
go test -bench=. -benchmem -count=5 -json -timeout=30m ./... > bench_raw.json

# Convert Go benchmark JSON to report.json
# Pass memory_stats.json as optional third arg for SRQ-2 memory enrichment
MEMORY_STATS="$OUTPUT_DIR/memory_stats.json"
if [ -f "$MEMORY_STATS" ]; then
    go run emit_report.go bench_raw.json "$OUTPUT_DIR/report.json" "$MEMORY_STATS"
else
    go run emit_report.go bench_raw.json "$OUTPUT_DIR/report.json"
fi

echo "Report written to $OUTPUT_DIR/report.json"
