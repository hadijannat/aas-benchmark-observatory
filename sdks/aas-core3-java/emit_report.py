#!/usr/bin/env python3
"""Convert JMH JSON output to report.json schema.

Usage:
    python3 emit_report.py <jmh_results.json> <output_path>

JMH results have times in nanoseconds when OutputTimeUnit is NANOSECONDS.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 emit_report.py <jmh_json> <output_path>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path) as f:
        jmh_results = json.load(f)

    datasets = {}

    for result in jmh_results:
        # JMH benchmark name format: com.aas.benchmark.PipelineBenchmarks.operation
        benchmark_name = result["benchmark"]
        operation = benchmark_name.rsplit(".", 1)[-1]

        # Dataset from params
        ds_name = result.get("params", {}).get("dataset", "unknown")

        if ds_name not in datasets:
            datasets[ds_name] = {
                "file_size_bytes": None,
                "element_count": None,
                "operations": {},
            }

        primary = result.get("primaryMetric", {})
        score = primary.get("score", 0)
        score_error = primary.get("scoreError", 0)
        raw_data = primary.get("rawData", [[]])

        # Flatten raw iterations
        all_values = [v for run in raw_data for v in run]
        iterations = len(all_values)

        mean_ns = round(score)
        median_ns = None
        min_ns = None
        max_ns = None
        stddev_ns = None

        if all_values:
            sorted_vals = sorted(all_values)
            min_ns = round(sorted_vals[0])
            max_ns = round(sorted_vals[-1])
            mid = len(sorted_vals) // 2
            if len(sorted_vals) % 2 == 0:
                median_ns = round((sorted_vals[mid - 1] + sorted_vals[mid]) / 2)
            else:
                median_ns = round(sorted_vals[mid])
            if len(sorted_vals) > 1:
                mean_val = sum(sorted_vals) / len(sorted_vals)
                variance = sum((x - mean_val) ** 2 for x in sorted_vals) / (len(sorted_vals) - 1)
                stddev_ns = round(variance ** 0.5)

        throughput = 0
        if score > 0:
            throughput = round(1e9 / score, 2)

        datasets[ds_name]["operations"][operation] = {
            "iterations": iterations,
            "mean_ns": mean_ns,
            "median_ns": median_ns,
            "stddev_ns": stddev_ns,
            "min_ns": min_ns,
            "max_ns": max_ns,
            "p75_ns": None,
            "p99_ns": None,
            "throughput_ops_per_sec": throughput,
            "memory": {
                "peak_rss_bytes": None,
                "alloc_bytes_per_op": None,
                "alloc_count_per_op": None,
            },
        }

    # Detect Java version
    java_version = os.popen("java -version 2>&1").read().strip().split("\n")[0]

    # Try to get SDK version from pom.xml
    sdk_version = "unknown"
    pom_path = Path(__file__).parent / "pom.xml"
    if pom_path.exists():
        content = pom_path.read_text()
        m = re.search(r"aas-core3\.0-java</artifactId>\s*<version>([^<]+)", content)
        if m:
            sdk_version = m.group(1)

    report = {
        "schema_version": 1,
        "sdk_id": "aas-core3-java",
        "metadata": {
            "language": "java",
            "runtime_version": java_version,
            "sdk_package_version": sdk_version,
            "benchmark_harness": "JMH",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "datasets": datasets,
    }

    out_dir = Path(output_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    print(f"Wrote report to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
