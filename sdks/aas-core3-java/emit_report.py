#!/usr/bin/env python3
"""Convert JMH JSON output to report.json schema v2.

Usage:
    python3 emit_report.py <jmh_results.json> <output_path>

JMH results have times in nanoseconds when OutputTimeUnit is NANOSECONDS.

Schema v2 additions (SRQ-2):
  - memory.heap_used_bytes, memory.gc_pause_ms, memory.gc_count,
    memory.traced_peak_bytes (all nullable)
  - Parses JMH secondaryMetrics for GC profiler data:
      gc.alloc.rate.norm -> alloc_bytes_per_op
      gc.count           -> gc_count
      gc.time            -> gc_pause_ms
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _extract_gc_metrics(result):
    """Extract GC profiler metrics from JMH secondaryMetrics.

    Returns a dict with keys:
      alloc_bytes_per_op, gc_count, gc_pause_ms
    Values are None when not present.
    """
    secondary = result.get("secondaryMetrics", {})

    alloc_bytes_per_op = None
    gc_count = None
    gc_pause_ms = None

    # gc.alloc.rate.norm gives bytes allocated per operation (score is the value)
    gc_alloc_norm = secondary.get("gc.alloc.rate.norm")
    if gc_alloc_norm is not None:
        score = gc_alloc_norm.get("score")
        if score is not None:
            alloc_bytes_per_op = round(score)

    # gc.count gives total number of GC pauses during the measurement
    gc_count_metric = secondary.get("gc.count")
    if gc_count_metric is not None:
        score = gc_count_metric.get("score")
        if score is not None:
            gc_count = round(score)

    # gc.time gives total GC pause time in milliseconds
    gc_time_metric = secondary.get("gc.time")
    if gc_time_metric is not None:
        score = gc_time_metric.get("score")
        if score is not None:
            gc_pause_ms = round(score, 3)

    return {
        "alloc_bytes_per_op": alloc_bytes_per_op,
        "gc_count": gc_count,
        "gc_pause_ms": gc_pause_ms,
    }


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

        params = result.get("params", {})

        # Determine which dataset param this result belongs to.
        # XML benchmarks use the xmlDataset param; JSON benchmarks use dataset.
        is_xml_op = operation in ("deserializeXml", "serializeXml")
        if is_xml_op:
            ds_name = params.get("xmlDataset", "unknown")
        else:
            ds_name = params.get("dataset", "unknown")

        # Skip placeholder entries (dataset="__none__")
        if ds_name == "__none__":
            continue

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

        # Extract GC profiler metrics (SRQ-2)
        gc_metrics = _extract_gc_metrics(result)

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
                "alloc_bytes_per_op": gc_metrics["alloc_bytes_per_op"],
                "alloc_count_per_op": None,
                "heap_used_bytes": None,
                "gc_pause_ms": gc_metrics["gc_pause_ms"],
                "gc_count": gc_metrics["gc_count"],
                "traced_peak_bytes": None,
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
        "schema_version": 2,
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
