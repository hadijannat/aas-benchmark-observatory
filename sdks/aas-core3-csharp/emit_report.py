#!/usr/bin/env python3
"""Convert BenchmarkDotNet JSON export to report.json (schema v2).

Usage:
    python3 emit_report.py <benchmarkdotnet_json> <output_path>

Schema v2 additions:
  - memory.heap_used_bytes, gc_pause_ms, gc_count, traced_peak_bytes
  - gc_count derived from Gen0Collections + Gen1Collections + Gen2Collections
"""

import argparse
import json
import sys
from datetime import datetime, timezone


# Map BenchmarkDotNet method names to our operation names
OPERATION_MAP = {
    "Deserialize": "deserialize",
    "Validate": "validate",
    "Traverse": "traverse",
    "Update": "update",
    "Serialize": "serialize",
}


def extract_dataset_from_params(benchmark):
    """Extract dataset name from BenchmarkDotNet benchmark parameters."""
    params = benchmark.get("Parameters", "")
    # Parameters looks like "Dataset=wide"
    if "=" in params:
        for part in params.split(","):
            part = part.strip()
            if part.startswith("Dataset="):
                return part.split("=", 1)[1]
    return "unknown"


def extract_operation(benchmark):
    """Extract operation name from BenchmarkDotNet method name."""
    method = benchmark.get("Method", "")
    return OPERATION_MAP.get(method, method.lower())


def build_operation_entry(benchmark):
    """Build an operation entry from a BenchmarkDotNet benchmark result."""
    stats = benchmark.get("Statistics", {})

    # BenchmarkDotNet Statistics.Mean is in nanoseconds
    mean_ns = int(round(stats.get("Mean", 0)))
    median_ns = int(round(stats.get("Median", 0)))
    stddev_ns = int(round(stats.get("StandardDeviation", 0)))
    min_ns = int(round(stats.get("Min", 0)))
    max_ns = int(round(stats.get("Max", 0)))

    # Percentiles
    percentiles = stats.get("Percentiles", {})
    p75_ns = None
    p99_ns = None
    if "P75" in percentiles:
        p75_ns = int(round(percentiles["P75"]))
    if "P99" in percentiles:
        p99_ns = int(round(percentiles["P99"]))

    iterations = stats.get("N", 0)

    throughput = 0.0
    if mean_ns > 0:
        throughput = 1e9 / mean_ns

    # Memory from MemoryDiagnoser
    memory = benchmark.get("Memory", {})
    alloc_bytes = memory.get("BytesAllocatedPerOperation")
    gen0 = memory.get("Gen0Collections")
    gen1 = memory.get("Gen1Collections")
    gen2 = memory.get("Gen2Collections")

    # Convert Gen0Collections to alloc_count_per_op if available
    alloc_count = None
    if gen0 is not None:
        alloc_count = int(gen0)

    # Sum all GC generation collections for gc_count
    gc_count = None
    gc_parts = [v for v in (gen0, gen1, gen2) if v is not None]
    if gc_parts:
        gc_count = sum(int(v) for v in gc_parts)

    return {
        "iterations": iterations,
        "mean_ns": mean_ns,
        "median_ns": median_ns,
        "stddev_ns": stddev_ns,
        "min_ns": min_ns,
        "max_ns": max_ns,
        "p75_ns": p75_ns,
        "p99_ns": p99_ns,
        "throughput_ops_per_sec": round(throughput, 2),
        "memory": {
            "peak_rss_bytes": None,
            "alloc_bytes_per_op": int(alloc_bytes) if alloc_bytes is not None else None,
            "alloc_count_per_op": alloc_count,
            "heap_used_bytes": None,
            "gc_pause_ms": None,
            "gc_count": gc_count,
            "traced_peak_bytes": None,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert BenchmarkDotNet JSON export to report.json"
    )
    parser.add_argument(
        "benchmarkdotnet_json",
        help="Path to BenchmarkDotNet JSON export file",
    )
    parser.add_argument("output", help="Path to write report.json")
    args = parser.parse_args()

    with open(args.benchmarkdotnet_json, "r", encoding="utf-8") as f:
        bdn_data = json.load(f)

    # Extract runtime info from BenchmarkDotNet host info
    host_info = bdn_data.get("HostEnvironmentInfo", {})
    runtime_version = host_info.get("DotNetCliVersion", "unknown")
    os_desc = host_info.get("OsVersion", "")

    benchmarks = bdn_data.get("Benchmarks", [])

    # Organize by dataset
    datasets = {}
    for bench in benchmarks:
        dataset = extract_dataset_from_params(bench)
        operation = extract_operation(bench)

        if dataset not in datasets:
            datasets[dataset] = {
                "file_size_bytes": None,
                "element_count": None,
                "operations": {},
            }

        op_entry = build_operation_entry(bench)
        datasets[dataset]["operations"][operation] = op_entry

    report = {
        "schema_version": 2,
        "sdk_id": "aas-core3-csharp",
        "metadata": {
            "language": "csharp",
            "runtime_version": f".NET {runtime_version}",
            "sdk_package_version": "latest",
            "benchmark_harness": "BenchmarkDotNet",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "datasets": datasets,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote report to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
