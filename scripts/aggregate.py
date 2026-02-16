#!/usr/bin/env python3
"""Aggregate per-SDK and per-server results into a single results.json for the dashboard.

Tiered detection:
  - report.json present       -> SDK (library) benchmark result
  - conformance_summary.json  -> Server benchmark result

Regression detection (SRQ-5):
  --previous-results <path>   -> Compare against previous results.json,
                                  flag regressions/improvements with 95% CI.
"""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_DIR = REPO_ROOT / "results"
DEFAULT_OUTPUT = REPO_ROOT / "dashboard" / "data" / "results.json"
DEFAULT_KNOWN_SDKS = REPO_ROOT / "known-sdks.json"

REGRESSION_THRESHOLD_PCT = 5.0
Z_95 = 1.96


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


# ── Regression detection (SRQ-5) ──────────────────────────────────────


def _compute_regressions(
    current_sdk: dict, previous_sdks: dict[str, dict]
) -> list[dict]:
    """Compare current SDK results against previous, return flagged regressions."""
    sdk_id = current_sdk.get("id", "")
    prev_sdk = previous_sdks.get(sdk_id)
    if prev_sdk is None:
        return []

    curr_datasets = current_sdk.get("pipeline", {}).get("datasets", {})
    prev_datasets = prev_sdk.get("pipeline", {}).get("datasets", {})

    regressions = []

    for ds_name, curr_ds in curr_datasets.items():
        prev_ds = prev_datasets.get(ds_name)
        if prev_ds is None:
            continue

        curr_ops = curr_ds.get("operations", {})
        prev_ops = prev_ds.get("operations", {})

        for op_name, curr_op in curr_ops.items():
            prev_op = prev_ops.get(op_name)
            if prev_op is None:
                continue

            curr_mean = curr_op.get("mean_ns")
            prev_mean = prev_op.get("mean_ns")
            curr_stddev = curr_op.get("stddev_ns")
            prev_stddev = prev_op.get("stddev_ns")
            curr_n = curr_op.get("iterations", 0)
            prev_n = prev_op.get("iterations", 0)

            if (
                curr_mean is None or prev_mean is None
                or prev_mean == 0
                or curr_n <= 1 or prev_n <= 1
            ):
                continue

            # Welch's approximation for comparing two means
            change_pct = (curr_mean - prev_mean) / prev_mean * 100.0

            # Standard error of the difference
            curr_var = (curr_stddev or 0) ** 2
            prev_var = (prev_stddev or 0) ** 2
            se_diff = math.sqrt(curr_var / curr_n + prev_var / prev_n)

            # 95% CI of the change percentage
            se_pct = (se_diff / prev_mean) * 100.0 if prev_mean > 0 else 0.0
            ci_lower = change_pct - Z_95 * se_pct
            ci_upper = change_pct + Z_95 * se_pct

            # Determine significance and direction
            if ci_lower > REGRESSION_THRESHOLD_PCT:
                significant = True
                direction = "regression"
            elif ci_upper < -REGRESSION_THRESHOLD_PCT:
                significant = True
                direction = "improvement"
            else:
                significant = False
                direction = "unchanged"

            if significant:
                regressions.append({
                    "dataset": ds_name,
                    "operation": op_name,
                    "previous_mean_ns": prev_mean,
                    "current_mean_ns": curr_mean,
                    "change_pct": round(change_pct, 2),
                    "ci_lower_pct": round(ci_lower, 2),
                    "ci_upper_pct": round(ci_upper, 2),
                    "significant": True,
                    "direction": direction,
                })

    return regressions


def _build_previous_index(previous_data: dict) -> dict[str, dict]:
    """Build sdk_id -> SDK entry map from previous results.json."""
    index: dict[str, dict] = {}
    for sdk in previous_data.get("sdk_benchmarks", []):
        sdk_id = sdk.get("id", "")
        if sdk_id:
            index[sdk_id] = sdk
    return index


# ── Aggregation ─────────────────────────────────────────────────────────


def _load_names(known_sdks: Path) -> dict[str, str]:
    """Load id->name mapping from known-sdks.json."""
    names: dict[str, str] = {}
    try:
        with open(known_sdks) as f:
            ks = json.load(f)
        for entry in ks.get("sdk_benchmarks", []) + ks.get("server_benchmarks", []):
            names[entry["id"]] = entry.get("name", entry["id"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
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

        # Detection: report.json -> SDK benchmark, conformance_summary.json -> server
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
    parser.add_argument(
        "--previous-results", type=Path, default=None,
        help="Path to previous results.json for regression detection (SRQ-5).",
    )
    args = parser.parse_args()

    sdk_benchmarks, server_benchmarks = aggregate(args.results_dir, args.known_sdks)

    # Regression detection (SRQ-5)
    if args.previous_results:
        previous_data = read_json(args.previous_results)
        if previous_data and previous_data.get("sdk_benchmarks"):
            prev_index = _build_previous_index(previous_data)
            regression_count = 0
            for sdk_entry in sdk_benchmarks:
                regs = _compute_regressions(sdk_entry, prev_index)
                if regs:
                    sdk_entry["regressions"] = regs
                    regression_count += len(regs)
            if regression_count > 0:
                print(f"Detected {regression_count} regression(s)/improvement(s)")
            else:
                print("No significant regressions detected")

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
