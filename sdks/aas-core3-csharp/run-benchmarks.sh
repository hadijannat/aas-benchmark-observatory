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

# Restore NuGet packages
dotnet restore

# Run BenchmarkDotNet with JSON exporter
# --filter '*' runs all benchmarks, --exporters json produces machine-readable output
dotnet run -c Release -- --filter '*' --exporters json

# Convert BenchmarkDotNet JSON export to report.json
# BenchmarkDotNet writes results to BenchmarkDotNet.Artifacts/results/
python3 "$SCRIPT_DIR/emit_report.py" \
  BenchmarkDotNet.Artifacts/results/*.json \
  "$OUTPUT_DIR/report.json"

echo "Report written to $OUTPUT_DIR/report.json"
