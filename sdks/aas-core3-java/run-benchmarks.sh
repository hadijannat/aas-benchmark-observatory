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

# Build the JMH uber-jar
mvn -q package -DskipTests

# Run JMH benchmarks
export JMH_OUTPUT="$OUTPUT_DIR/jmh_results.json"
java -jar target/aas-benchmark-java-1.0.0.jar

# Convert JMH JSON to report.json
python3 "$SCRIPT_DIR/emit_report.py" \
  "$JMH_OUTPUT" \
  "$OUTPUT_DIR/report.json"

echo "Report written to $OUTPUT_DIR/report.json"
