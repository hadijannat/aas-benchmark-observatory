# Benchmark Validity Findings

Date: 2026-02-16

## P0

1. Stateful mutation during timed update benchmarks skewed iteration comparability.
- Impact: Later iterations measured different object state than earlier iterations.
- Fixed in:
  - `sdks/aas-core3-python/bench_pipeline.py`
  - `sdks/aas-core3-golang/bench_pipeline_test.go`
  - `sdks/aas-core3-typescript/bench_pipeline.ts`
  - `sdks/aas-core3-java/src/main/java/com/aas/benchmark/PipelineBenchmarks.java`
  - `sdks/aas-core3-csharp/PipelineBenchmarks.cs`

2. Silent failure paths allowed benchmark/conformance execution errors to appear successful.
- Impact: Invalid or partial results could be published.
- Fixed in:
  - `sdks/basyx-rust/run-benchmarks.sh` (removed failure swallowing)
  - `harness/conformance/run_aas_test_engines.sh` (explicit execution/parsing failure states)
  - `.github/workflows/nightly-benchmark.yml` (conformance execution validation step)
  - `.github/workflows/pr-smoke.yml` (conformance execution validation step)

3. Cross-SDK operation naming was inconsistent (camelCase vs snake_case).
- Impact: Broken comparisons and regression matching across adapters.
- Fixed in:
  - `scripts/aggregate.py` (canonical normalization + compatibility mapping)
  - `sdks/aas-core3-java/emit_report.py`
  - `sdks/aas-core3-golang/emit_report.go`
  - `dashboard/index.html` (legacy fallback normalization)

## P1

4. Reproducibility controls were weak due to mutable dependency resolution.
- Impact: Drift across runs and reduced longitudinal confidence.
- Fixed in:
  - `sdks/aas-core3-python/requirements.txt` + `sdks/aas-core3-python/constraints.txt`
  - `sdks/aas-core3-typescript/package.json` + `sdks/aas-core3-typescript/package-lock.json`
  - `sdks/aas-core3-golang/go.sum` + `sdks/aas-core3-golang/run-benchmarks.sh`
  - `sdks/basyx-rust/Cargo.lock` + `sdks/basyx-rust/run-benchmarks.sh`

5. Schedule/documentation mismatch created operational ambiguity.
- Impact: Docs claimed monthly cadence while workflow ran daily.
- Fixed in:
  - `README.md`
