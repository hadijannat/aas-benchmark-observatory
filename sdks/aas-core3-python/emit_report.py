#!/usr/bin/env python3
"""Convert pytest-benchmark JSON output + memory measurements to report.json.

Usage:
    python3 emit_report.py <bench_json> <memory_json> <output_path>
"""

import argparse
import datetime
import importlib.metadata
import json
import platform
import sys


def parse_benchmark_name(name):
    """Parse test name like 'test_deserialize[wide]' into (operation, dataset).

    Returns (operation, dataset) tuple.
    """
    # Name format: test_<operation>[<dataset>]
    if "[" in name and name.endswith("]"):
        base, param = name.rsplit("[", 1)
        dataset = param.rstrip("]")
    else:
        base = name
        dataset = "unknown"

    # Strip 'test_' prefix
    operation = base
    if operation.startswith("test_"):
        operation = operation[len("test_"):]

    return operation, dataset


def seconds_to_ns(s):
    """Convert seconds to nanoseconds."""
    return int(round(s * 1e9))


def build_operation_entry(bench):
    """Build an operation dict from a single pytest-benchmark entry."""
    stats = bench.get("stats", {})
    iterations = stats.get("iterations", 0) * stats.get("rounds", 1)

    mean_ns = seconds_to_ns(stats.get("mean", 0))
    median_ns = seconds_to_ns(stats.get("median", 0))
    stddev_ns = seconds_to_ns(stats.get("stddev", 0))
    min_ns = seconds_to_ns(stats.get("min", 0))
    max_ns = seconds_to_ns(stats.get("max", 0))

    throughput = 0.0
    mean_s = stats.get("mean", 0)
    if mean_s > 0:
        throughput = 1.0 / mean_s

    return {
        "iterations": iterations,
        "mean_ns": mean_ns,
        "median_ns": median_ns,
        "stddev_ns": stddev_ns,
        "min_ns": min_ns,
        "max_ns": max_ns,
        "p75_ns": None,
        "p99_ns": None,
        "throughput_ops_per_sec": round(throughput, 2),
        "memory": {
            "peak_rss_bytes": None,
            "alloc_bytes_per_op": None,
            "alloc_count_per_op": None,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Convert pytest-benchmark JSON to report.json"
    )
    parser.add_argument("bench_json", help="Path to pytest-benchmark JSON output")
    parser.add_argument("memory_json", help="Path to memory measurements JSON")
    parser.add_argument("output", help="Path to write report.json")
    args = parser.parse_args()

    with open(args.bench_json, "r", encoding="utf-8") as f:
        bench_data = json.load(f)

    # Load memory measurements (may be empty if no data)
    memory_data = {}
    try:
        with open(args.memory_json, "r", encoding="utf-8") as f:
            memory_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Get SDK version info
    try:
        sdk_version = importlib.metadata.version("aas-core3.0")
    except importlib.metadata.PackageNotFoundError:
        sdk_version = "unknown"

    try:
        harness_version = importlib.metadata.version("pytest-benchmark")
    except importlib.metadata.PackageNotFoundError:
        harness_version = "unknown"

    python_version = platform.python_version()

    # Organize benchmarks by dataset
    datasets = {}
    for bench in bench_data.get("benchmarks", []):
        name = bench.get("name", "")
        operation, dataset = parse_benchmark_name(name)

        if dataset not in datasets:
            datasets[dataset] = {"operations": {}}

        op_entry = build_operation_entry(bench)

        # Attach memory data if available
        mem_key = f"{dataset}/{operation}"
        if mem_key in memory_data:
            mem = memory_data[mem_key]
            op_entry["memory"]["peak_rss_bytes"] = mem.get("peak_rss_bytes")

        datasets[dataset]["operations"][operation] = op_entry

    # Build dataset entries with file metadata
    datasets_output = {}
    for ds_name, ds_data in datasets.items():
        datasets_output[ds_name] = {
            "file_size_bytes": None,
            "element_count": None,
            "operations": ds_data["operations"],
        }

    report = {
        "schema_version": 1,
        "sdk_id": "aas-core3-python",
        "metadata": {
            "language": "python",
            "runtime_version": f"Python {python_version}",
            "sdk_package_version": sdk_version,
            "benchmark_harness": f"pytest-benchmark {harness_version}",
            "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "datasets": datasets_output,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Wrote report to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
