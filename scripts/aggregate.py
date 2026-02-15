#!/usr/bin/env python3
"""Aggregate per-SDK and per-server results into a single results.json for the dashboard.

Tiered detection:
  - report.json present       -> SDK (library) benchmark result
  - conformance_summary.json  -> Server benchmark result
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_OUTPUT = REPO_ROOT / "dashboard" / "data" / "results.json"
DEFAULT_KNOWN_SDKS = REPO_ROOT / "known-sdks.json"


def read_json(path: Path):
    """Return parsed JSON or None if the file is missing / malformed."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ── SDK (library) benchmarks ────────────────────────────────────────────


def _build_sdk_entry(entry: Path, names: dict[str, str]) -> dict | None:
    """Build an SDK benchmark entry from a directory containing report.json."""
    report = read_json(entry / "report.json")
    if report is None:
        return None

    sdk_id = report.get("sdk_id", entry.name)
    name = names.get(sdk_id, report.get("metadata", {}).get("name", sdk_id))

    result: dict = {"id": sdk_id, "name": name}

    env = read_json(entry / "env.json")
    if env:
        result["env"] = env

    # Store the full report (including metadata + datasets) so the dashboard
    # can display language, runtime version, harness, and package version.
    result["pipeline"] = report

    return result


# ── Server benchmarks ───────────────────────────────────────────────────


def _build_server_entry(entry: Path, names: dict[str, str]) -> dict | None:
    """Build a server benchmark entry from a directory containing conformance_summary.json."""
    sdk_id = entry.name
    result: dict = {"id": sdk_id}

    env = read_json(entry / "env.json")
    if env:
        result["name"] = names.get(sdk_id, env.get("sdk_name", sdk_id))
        result["env"] = env
    else:
        result["name"] = names.get(sdk_id, sdk_id)

    conformance = read_json(entry / "conformance_summary.json")
    if conformance is not None:
        result["conformance"] = conformance

    scenarios = read_json(entry / f"k6_summary_{sdk_id}.json")
    crud = read_json(entry / f"k6_crud_{sdk_id}.json")
    if scenarios is not None or crud is not None:
        benchmarks: dict = {}
        if scenarios is not None:
            benchmarks["scenarios"] = scenarios
        if crud is not None:
            benchmarks["crud"] = crud
        result["benchmarks"] = benchmarks

    return result


# ── Aggregation ─────────────────────────────────────────────────────────


def _load_names(known_sdks: Path) -> dict[str, str]:
    """Load id→name mapping from known-sdks.json."""
    names: dict[str, str] = {}
    try:
        with open(known_sdks) as f:
            ks = json.load(f)
        for entry in ks.get("sdk_benchmarks", []) + ks.get("server_benchmarks", []):
            names[entry["id"]] = entry.get("name", entry["id"])
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return names


def aggregate(results_dir: Path, known_sdks: Path) -> tuple[list[dict], list[dict]]:
    """Walk *results_dir* and classify each sub-directory as SDK or server.

    Returns (sdk_benchmarks, server_benchmarks).
    """
    sdk_benchmarks: list[dict] = []
    server_benchmarks: list[dict] = []

    if not results_dir.is_dir():
        return sdk_benchmarks, server_benchmarks

    names = _load_names(known_sdks)

    for entry in sorted(results_dir.iterdir()):
        if not entry.is_dir():
            continue

        # Detection: report.json → SDK benchmark, conformance_summary.json → server
        if (entry / "report.json").exists():
            sdk_entry = _build_sdk_entry(entry, names)
            if sdk_entry is not None:
                sdk_benchmarks.append(sdk_entry)
        elif (entry / "conformance_summary.json").exists():
            server_entry = _build_server_entry(entry, names)
            if server_entry is not None:
                server_benchmarks.append(server_entry)
        else:
            # Fallback: treat directories with k6 or env data as server results
            server_entry = _build_server_entry(entry, names)
            if server_entry is not None:
                server_benchmarks.append(server_entry)

    return sdk_benchmarks, server_benchmarks


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
    parser.add_argument(
        "--known-sdks", type=Path, default=DEFAULT_KNOWN_SDKS,
        help="Path to known-sdks.json for name lookup (default: known-sdks.json)",
    )
    args = parser.parse_args()

    sdk_benchmarks, server_benchmarks = aggregate(args.results_dir, args.known_sdks)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sdk_benchmarks": sdk_benchmarks,
        "server_benchmarks": server_benchmarks,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    total = len(sdk_benchmarks) + len(server_benchmarks)
    print(
        f"Aggregated {total} result(s) "
        f"({len(sdk_benchmarks)} SDK, {len(server_benchmarks)} server) "
        f"-> {args.output}"
    )


if __name__ == "__main__":
    main()
