#!/usr/bin/env python3
"""Convert criterion benchmark results to report.json schema.

Usage:
    python3 emit_report.py <criterion_target_dir> <output_path>

Criterion stores results in target/criterion/<group>/<benchmark>/new/estimates.json
with times in nanoseconds.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 emit_report.py <criterion_dir> <output_path>", file=sys.stderr)
        sys.exit(1)

    criterion_dir = Path(sys.argv[1])
    output_path = sys.argv[2]

    datasets = {}

    # Criterion directory structure: <group>/<benchmark>/new/estimates.json
    # group = operation (deserialize, serialize)
    # benchmark = dataset name (wide, deep, mixed)
    if criterion_dir.exists():
        for group_dir in sorted(criterion_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            operation = group_dir.name
            if operation.startswith("report"):
                continue

            for bench_dir in sorted(group_dir.iterdir()):
                if not bench_dir.is_dir():
                    continue
                ds_name = bench_dir.name

                estimates_path = bench_dir / "new" / "estimates.json"
                if not estimates_path.exists():
                    continue

                with open(estimates_path) as f:
                    estimates = json.load(f)

                mean_ns = round(estimates.get("mean", {}).get("point_estimate", 0))
                median_ns = round(estimates.get("median", {}).get("point_estimate", 0))
                stddev_ns = round(estimates.get("std_dev", {}).get("point_estimate", 0))

                # Load sample data if available
                sample_path = bench_dir / "new" / "sample.json"
                min_ns = None
                max_ns = None
                iterations = 0
                if sample_path.exists():
                    with open(sample_path) as f:
                        sample = json.load(f)
                    times = sample.get("times", [])
                    iters = sample.get("iters", [])
                    if times and iters:
                        per_op = [t / i for t, i in zip(times, iters) if i > 0]
                        if per_op:
                            min_ns = round(min(per_op))
                            max_ns = round(max(per_op))
                        iterations = sum(int(i) for i in iters)

                throughput = 0
                if mean_ns > 0:
                    throughput = round(1e9 / mean_ns, 2)

                if ds_name not in datasets:
                    datasets[ds_name] = {
                        "file_size_bytes": None,
                        "element_count": None,
                        "operations": {},
                    }

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

    # Detect Rust version
    rust_version = "unknown"
    try:
        import subprocess
        result = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
        rust_version = result.stdout.strip()
    except Exception:
        pass

    # Get crate version from Cargo.toml
    sdk_version = "unknown"
    cargo_path = Path(__file__).parent / "Cargo.toml"
    if cargo_path.exists():
        for line in cargo_path.read_text().splitlines():
            if "basyx-rs" in line and "=" in line:
                sdk_version = line.split("=")[-1].strip().strip('"')
                break

    report = {
        "schema_version": 1,
        "sdk_id": "basyx-rust",
        "metadata": {
            "language": "rust",
            "runtime_version": rust_version,
            "sdk_package_version": sdk_version,
            "benchmark_harness": "criterion",
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
