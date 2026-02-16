# Benchmark Validation Report

Date: 2026-02-16

## Checks Executed

1. Python syntax validation
- Command:
  - `python3 -m py_compile scripts/aggregate.py scripts/validate_report.py scripts/test_aggregate.py datasets/generate.py sdks/aas-core3-python/emit_report.py sdks/aas-core3-java/emit_report.py sdks/aas-core3-csharp/emit_report.py sdks/basyx-rust/emit_report.py`
- Result: pass

2. Aggregation unit tests
- Command:
  - `python3 scripts/test_aggregate.py`
- Result: pass (`Ran 3 tests ... OK`)

3. Go adapter compile/test check
- Command:
  - `go test ./...` (in `sdks/aas-core3-golang`)
- Result: pass

4. TypeScript lockfile/install determinism check
- Command:
  - `npm ci` (in `sdks/aas-core3-typescript`)
- Result: pass

5. Rust lockfile build check
- Command:
  - `cargo check --locked` (in `sdks/basyx-rust`)
- Result: pass

6. Dashboard script syntax check
- Method:
  - Extract inline JS from `dashboard/index.html` and run `node --check`.
- Result: pass

7. Workflow YAML parse check
- Method:
  - Parse `.github/workflows/nightly-benchmark.yml` and `.github/workflows/pr-smoke.yml` with PyYAML.
- Result: pass

8. Report validator smoke check
- Command:
  - `python3 scripts/validate_report.py /tmp/report_validate_smoke.json`
- Result: pass

9. Python adapter end-to-end smoke (mixed-only dataset)
- Command:
  - `python3 datasets/generate.py --output-dir /tmp/aas-datasets-mixed --only mixed`
  - `bash sdks/aas-core3-python/run-benchmarks.sh /tmp/aas-datasets-mixed /tmp/aas-py-results`
  - `python3 scripts/validate_report.py /tmp/aas-py-results/report.json`
- Result: pass (`5 passed, 4 skipped`)

## Residual Notes

- `dashboard-regressions-tab.png` and `dashboard-timing-tab.png` remain untracked (pre-existing workspace artifacts).
- No destructive cleanup commands were run against tracked files.
