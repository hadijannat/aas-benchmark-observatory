#!/usr/bin/env python3
"""Aggregate per-SDK results into a single results.json for the dashboard."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_OUTPUT = REPO_ROOT / "dashboard" / "data" / "results.json"


def read_json(path: Path):
    """Return parsed JSON or None if the file is missing / malformed."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def aggregate(results_dir: Path) -> list[dict]:
    sdks = []
    if not results_dir.is_dir():
        return sdks

    for entry in sorted(results_dir.iterdir()):
        if not entry.is_dir():
            continue
        sdk_id = entry.name
        sdk: dict = {"id": sdk_id}

        env = read_json(entry / "env.json")
        if env:
            sdk["name"] = env.get("sdk_name", sdk_id)
            sdk["env"] = env
        else:
            sdk["name"] = sdk_id

        conformance = read_json(entry / "conformance_summary.json")
        if conformance is not None:
            sdk["conformance"] = conformance

        scenarios = read_json(entry / f"k6_summary_{sdk_id}.json")
        crud = read_json(entry / f"k6_crud_{sdk_id}.json")
        if scenarios is not None or crud is not None:
            benchmarks: dict = {}
            if scenarios is not None:
                benchmarks["scenarios"] = scenarios
            if crud is not None:
                benchmarks["crud"] = crud
            sdk["benchmarks"] = benchmarks

        sdks.append(sdk)
    return sdks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir", type=Path, default=DEFAULT_RESULTS_DIR,
        help="Directory containing per-SDK result folders (default: results/)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Output path for aggregated JSON (default: dashboard/data/results.json)",
    )
    args = parser.parse_args()

    sdks = aggregate(args.results_dir)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sdks": sdks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Aggregated {len(sdks)} SDK(s) -> {args.output}")


if __name__ == "__main__":
    main()
