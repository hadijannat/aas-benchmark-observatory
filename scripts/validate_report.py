#!/usr/bin/env python3
"""Validate report.json integrity and canonical operation naming.

Checks:
  - report has at least one dataset and one operation
  - no dataset has an empty operations object
  - operation keys are canonical snake_case IDs
  - operation_id field (if present) matches canonical key
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def canonical_operation_id(raw_op: str) -> str:
    explicit = {
        "deserializeXml": "deserialize_xml",
        "serializeXml": "serialize_xml",
        "deserializexml": "deserialize_xml",
        "serializexml": "serialize_xml",
        "aasxExtract": "aasx_extract",
        "aasxRepackage": "aasx_repackage",
        "aasxextract": "aasx_extract",
        "aasxrepackage": "aasx_repackage",
    }
    if raw_op in explicit:
        return explicit[raw_op]

    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw_op)
    snake = snake.replace("-", "_").lower()
    dense_map = {
        "deserializexml": "deserialize_xml",
        "serializexml": "serialize_xml",
        "aasxextract": "aasx_extract",
        "aasxrepackage": "aasx_repackage",
    }
    return dense_map.get(snake, snake)


def validate_report(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"failed to parse JSON: {exc}"]

    datasets = report.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        return ["report must contain at least one dataset"]

    op_count = 0
    for dataset_name, dataset_entry in datasets.items():
        if not isinstance(dataset_entry, dict):
            errors.append(f"dataset {dataset_name!r} is not an object")
            continue
        operations = dataset_entry.get("operations")
        if not isinstance(operations, dict) or not operations:
            errors.append(f"dataset {dataset_name!r} has no operations")
            continue

        for op_key, op_entry in operations.items():
            op_count += 1
            canonical = canonical_operation_id(op_key)
            if op_key != canonical:
                errors.append(
                    f"dataset {dataset_name!r} contains non-canonical operation key "
                    f"{op_key!r} (canonical: {canonical!r})"
                )
            if isinstance(op_entry, dict):
                op_id = op_entry.get("operation_id")
                if op_id is not None and op_id != canonical:
                    errors.append(
                        f"dataset {dataset_name!r} operation {op_key!r} has mismatched "
                        f"operation_id={op_id!r} (expected {canonical!r})"
                    )
                required = [
                    "operation_id",
                    "operation_track",
                    "sample_count",
                    "measurement_semantics",
                    "failure_state",
                    "mean_ns",
                ]
                missing = [k for k in required if k not in op_entry]
                if missing:
                    errors.append(
                        f"dataset {dataset_name!r} operation {op_key!r} missing required fields: "
                        + ", ".join(missing)
                    )
            else:
                errors.append(f"dataset {dataset_name!r} operation {op_key!r} is not an object")

    if op_count == 0:
        errors.append("report must contain at least one operation")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to report.json")
    args = parser.parse_args()

    problems = validate_report(args.report)
    if problems:
        print(f"Invalid report: {args.report}", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"Report valid: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
