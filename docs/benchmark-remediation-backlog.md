# Benchmark Remediation Backlog

## P0-1 Canonical Report Contract
- Scope: Enforce canonical operation IDs and required operation metadata in every SDK report.
- Implemented:
  - `scripts/validate_report.py`
  - CI integration in `.github/workflows/nightly-benchmark.yml` and `.github/workflows/pr-smoke.yml`
- Acceptance criteria:
  - Non-canonical operation keys fail CI.
  - Missing `operation_id|operation_track|sample_count|measurement_semantics|failure_state` fails CI.

## P0-2 Regression Statistical Correctness
- Scope: Use independent sample counts for significance testing.
- Implemented:
  - `scripts/aggregate.py` (`sample_count` precedence over `iterations`).
- Acceptance criteria:
  - Synthetic high-variance + low-sample scenarios do not produce false alerts.
  - Backward compatibility maintained for legacy reports without `sample_count`.

## P0-3 Update Benchmark Isolation
- Scope: Ensure update benchmarks restore baseline state each timed iteration.
- Implemented across language adapters:
  - Python, Go, TypeScript, Java, C# benchmark files.
- Acceptance criteria:
  - Update timings are no longer affected by cumulative mutation from prior iterations.

## P1-1 Two-Track Dashboard
- Scope: Strict core-track leaderboard + capability-specific tabs.
- Implemented:
  - `dashboard/index.html`
  - Core track only includes `core_track_eligible` SDKs.
  - Capability views for Validation, XML, and AASX.
- Acceptance criteria:
  - Capability-only SDKs are excluded from core ranking and still visible in capability tabs.

## P1-2 Runtime Provenance
- Scope: Improve environment comparability across runs.
- Implemented:
  - `harness/collect-env.sh` adds `runner_fingerprint`, CPU model, runner metadata.
  - Dashboard shows the additional provenance fields.
- Acceptance criteria:
  - Every result card surfaces runner fingerprint and hardware context.

## P2-1 Adapter Onboarding Governance
- Scope: Add a reusable quality gate checklist for new adapters.
- Implemented:
  - `docs/benchmark-validity-checklist.md`
  - README reference.
- Acceptance criteria:
  - New adapter PRs can be reviewed against one explicit checklist.
