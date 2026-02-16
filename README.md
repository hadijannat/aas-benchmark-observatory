# AAS Benchmark Observatory

Automated, validity-focused benchmarking for Asset Administration Shell (AAS) implementations across two tiers:
- SDK in-process pipeline benchmarks
- Server API conformance and performance benchmarks

[![Nightly Benchmark](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml/badge.svg)](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml)

## What This Repository Does

This repository standardizes AAS benchmarking so results remain comparable over time and across implementations.

Key goals:
- Measurement correctness: timing loops benchmark isolated state.
- Reproducibility: adapter dependencies are pinned and CI is deterministic.
- Longitudinal comparability: canonical operation IDs and backward-compatible aggregation.

High-level pipeline:

```text
known-sdks.json
  -> CI matrix (enabled SDK/server adapters)
  -> adapter run-benchmarks.sh
  -> per-adapter artifacts (report.json, conformance, k6)
  -> scripts/aggregate.py
  -> dashboard/data/results.json
  -> GitHub Pages dashboard
```

## Repository Map

| Path | Purpose |
|---|---|
| `known-sdks.json` | Source-of-truth manifest for `sdk_benchmarks[]` and `server_benchmarks[]` |
| `sdks/<id>/` | Per-SDK adapters and emitters producing `report.json` |
| `servers/<id>/` | Per-server adapters (`sdk.yaml`, `docker-compose.yml`) |
| `datasets/` | Deterministic AAS dataset generation (`wide`, `deep`, `mixed`, XML, validation targets, AASX) |
| `harness/` | Shared scripts for conformance, health checks, data seeding, and k6 runs |
| `scripts/` | CI helpers for matrix generation, aggregation, report validation, and discovery |
| `.github/workflows/` | Nightly run, PR smoke, weekly discovery |
| `dashboard/` | Static dashboard UI and `dashboard/data/results.json` consumer |
| `docs/` | Benchmark validity governance/checklists/reports |

## Benchmark Model

### SDK Tier

Canonical core operations:
- `deserialize`
- `validate`
- `traverse`
- `update`
- `serialize`

Capability operations:
- `deserialize_xml`
- `serialize_xml`
- `aasx_extract`
- `aasx_repackage`

Standard datasets:
- Core datasets: `wide`, `deep`, `mixed`
- Validation targets: `val_cardinality`, `val_referential`, `val_regex`

### Server Tier

Server adapters run:
- Conformance tests (`aas-test-engines`)
- k6 scenarios / CRUD load tests

## Requirements (Local)

For full multi-SDK local benchmarking:
- Python 3.11+ (`python3`, `pip`)
- Go 1.22+
- Node.js 20+ and npm
- Java (Temurin/OpenJDK) + Maven
- Rust toolchain (`cargo`, `rustc`)

For server-tier local benchmarking:
- Docker + Docker Compose
- `yq`
- `aas-test-engines`
- `k6`

## Quick Start (Single SDK)

```bash
git clone https://github.com/hadijannat/aas-benchmark-observatory.git
cd aas-benchmark-observatory

mkdir -p /tmp/aas-datasets /tmp/aas-results/python
python3 datasets/generate.py --output-dir /tmp/aas-datasets
python3 datasets/generate.py --output-dir /tmp/aas-datasets --xml
python3 datasets/generate.py --output-dir /tmp/aas-datasets --validation-targets

bash sdks/aas-core3-python/run-benchmarks.sh /tmp/aas-datasets /tmp/aas-results/python
python3 scripts/validate_report.py /tmp/aas-results/python/report.json
```

## Full Local Multi-SDK Run

The following mirrors CI-style SDK execution and aggregation:

```bash
TS="$(date +%Y%m%d-%H%M%S)"
DATA="/tmp/aas-bench-datasets-$TS"
OUT="/tmp/aas-bench-results-$TS"
mkdir -p "$DATA" "$OUT"

python3 datasets/generate.py --output-dir "$DATA"
python3 datasets/generate.py --output-dir "$DATA" --xml
python3 datasets/generate.py --output-dir "$DATA" --validation-targets

for sdk in aas-core3-python aas-core3-golang aas-core3-typescript aas-core3-java basyx-rust; do
  mkdir -p "$OUT/$sdk"
  bash "sdks/$sdk/run-benchmarks.sh" "$DATA" "$OUT/$sdk"
  python3 scripts/validate_report.py "$OUT/$sdk/report.json"
done

python3 scripts/aggregate.py \
  --results-dir "$OUT" \
  --output "$OUT/aggregated_results.json"

echo "DATASETS_DIR=$DATA"
echo "RESULTS_DIR=$OUT"
```

Notes:
- `aas-core3-csharp` is currently disabled in `known-sdks.json`.
- `basyx-rust` currently skips `mixed` if parser support is missing; run logs make this explicit.

## Output Contracts

SDK adapters must emit:
- `<results>/<sdk_id>/report.json`

Server adapters typically emit:
- `<results>/<server_id>/conformance_summary.json`
- `<results>/<server_id>/k6_summary_<server_id>.json`
- `<results>/<server_id>/k6_crud_<server_id>.json`

Aggregated output:
- `scripts/aggregate.py` writes a merged JSON with `sdk_benchmarks[]` and `server_benchmarks[]`.

Report schema (backward-compatible additions in use):
- `operation_id`
- `operation_track`
- `sample_count`
- `measurement_semantics`
- `failure_state`

## Validity Guardrails

Enforced by adapter/report tooling:
- Canonical operation normalization to snake_case IDs.
- Adapter report validation via `scripts/validate_report.py`.
- Hard-fail behavior for benchmark runner errors in CI.
- Aggregation logic prefers independent `sample_count` over loop `iterations`.
- Core-track eligibility is derived from full core dataset + operation coverage.

Governance docs:
- `docs/benchmark-validity-checklist.md`
- `docs/benchmark-validity-findings.md`
- `docs/benchmark-remediation-backlog.md`
- `docs/benchmark-validation-report.md`

## CI Workflows

- `nightly-benchmark.yml`
  - Schedule: daily at `03:00 UTC`
  - Also supports manual `workflow_dispatch` with optional `sdk_filter`
- `pr-smoke.yml`
  - Runs smoke checks for changed enabled adapters and shared harness changes
- `sdk-discovery.yml`
  - Schedule: weekly on Monday at `09:00 UTC`
  - Opens issues for newly discovered server Docker image tags

## Adding a New Adapter

### SDK Adapter
1. Add entry under `sdk_benchmarks[]` in `known-sdks.json` with `"enabled": false`.
2. Create `sdks/<id>/run-benchmarks.sh` and adapter benchmark code.
3. Ensure `run-benchmarks.sh <datasets_dir> <output_dir>` emits valid `report.json`.
4. Run `python3 scripts/validate_report.py <report.json>`.
5. Enable after PR validation.

### Server Adapter
1. Add entry under `server_benchmarks[]` in `known-sdks.json` with `"enabled": false`.
2. Create `servers/<id>/sdk.yaml` and `servers/<id>/docker-compose.yml`.
3. Validate conformance/k6 flow locally or in PR smoke.
4. Enable after PR validation.

## Dashboard

Latest dashboard:
- [https://hadijannat.github.io/aas-benchmark-observatory/](https://hadijannat.github.io/aas-benchmark-observatory/)

Main views:
- SDK pipeline comparisons and per-operation timing tables
- Core/capability track interpretation
- Server conformance and k6 performance summaries

## License

MIT
