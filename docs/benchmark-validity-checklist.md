# Benchmark Validity Checklist

Use this checklist when adding or updating SDK/server adapters.

## Measurement Correctness

- [ ] No benchmark mutates shared state across timed iterations without restoring baseline state.
- [ ] Operation IDs in `report.json` are canonical snake_case:
  - `deserialize`, `validate`, `traverse`, `update`, `serialize`
  - `deserialize_xml`, `serialize_xml`
  - `aasx_extract`, `aasx_repackage`
- [ ] Each operation entry includes:
  - `operation_id`
  - `operation_track`
  - `sample_count`
  - `measurement_semantics`
  - `failure_state`

## Reproducibility

- [ ] Dependencies are pinned.
- [ ] Lockfiles are committed when applicable (`go.sum`, `package-lock.json`, `Cargo.lock`).
- [ ] CI install commands are deterministic (`npm ci`, `go mod download`, etc.).

## Report Integrity

- [ ] Adapter produces non-empty `report.json` with datasets and operations.
- [ ] `python3 scripts/validate_report.py <report.json>` passes.
- [ ] No mixed legacy/canonical operation keys are emitted.

## CI and Runtime Provenance

- [ ] `harness/collect-env.sh` metadata is captured in `env.json`.
- [ ] `runner_fingerprint` is present for comparability.
- [ ] Conformance execution failures are surfaced in `conformance_summary.json` with `failure_state`.

## Dashboard Compatibility

- [ ] Core track comparisons include only core-eligible SDKs.
- [ ] Capability tracks are used for XML, AASX, and targeted validation datasets.
- [ ] Legacy reports still render via normalization fallback.
