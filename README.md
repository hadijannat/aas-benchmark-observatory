# AAS Benchmark Observatory

Automated benchmarking of Asset Administration Shell (AAS) implementations — both in-process SDK pipelines and server APIs.

[![Nightly Benchmark](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml/badge.svg)](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml)

## Architecture

A **manifest-driven CI harness** that benchmarks AAS implementations across two tiers and publishes results to GitHub Pages.

```
known-sdks.json → GitHub Actions matrix
  ├─ SDK benchmarks:    language setup → generate datasets → run pipeline → report.json
  └─ Server benchmarks: Docker Compose → seed data → conformance + k6 → results
Both → aggregate.py → dashboard/data/results.json → GitHub Pages
```

### Components

| Component | Purpose |
|-----------|---------|
| `known-sdks.json` | Source of truth — two-tier schema with `sdk_benchmarks[]` and `server_benchmarks[]` |
| `sdks/<id>/` | Per-SDK adapter: pipeline benchmarks using native language harnesses |
| `servers/<id>/` | Per-server adapter: `sdk.yaml` contract + `docker-compose.yml` |
| `datasets/` | Deterministic AAS v3.0 dataset generator (wide/deep/mixed) for SDK benchmarks |
| `harness/` | Shared test harness: seed data, conformance tests, k6 load benchmarks |
| `scripts/` | CI helpers: matrix generation (`sdk`/`server`), SDK discovery, result aggregation |
| `.github/workflows/` | Monthly benchmarks, PR smoke tests, SDK version discovery |
| `dashboard/` | Zero-dependency tabbed SPA deployed to GitHub Pages |

### Benchmark Tiers

**Tier A — SDK Pipeline Benchmarks**: In-process benchmarks comparing AAS library performance across languages on a canonical Read → Validate → Traverse → Update → Write pipeline using generated datasets (wide, deep, mixed).

**Tier B — Server API Benchmarks**: Docker-based benchmarks testing AAS server conformance and HTTP API performance via k6.

### Workflow

1. **Nightly (daily @ 03:00 UTC)**: Runs full SDK pipeline + server API benchmarks for all enabled implementations
2. **PR Smoke**: On pull requests touching `sdks/`, `servers/`, or `harness/`, runs quick smoke tests
3. **Weekly Discovery**: Checks Docker Hub for new server versions, opens issues

## Adding a Server

1. Add an entry to `known-sdks.json` under `server_benchmarks` with `"enabled": false`
2. Create `servers/<id>/sdk.yaml` describing the API contract
3. Create `servers/<id>/docker-compose.yml` to launch the server
4. Open a PR — the smoke test validates your adapter
5. After review, set `"enabled": true`

## Benchmark Validity Checklist

Before enabling a new adapter, run through:
- `docs/benchmark-validity-checklist.md`

Related governance docs:
- `docs/benchmark-validity-findings.md`
- `docs/benchmark-remediation-backlog.md`
- `docs/benchmark-validation-report.md`

## Adding an SDK

1. Add an entry to `known-sdks.json` under `sdk_benchmarks` with `"enabled": false`
2. Create `sdks/<id>/` with `run-benchmarks.sh` and language-specific benchmark files
3. Ensure `run-benchmarks.sh <datasets_dir> <output_dir>` produces a valid `report.json`
4. Open a PR — the smoke test validates your adapter
5. After review, set `"enabled": true`

## Currently Tracked

### SDK Libraries

| SDK | Language | Harness | Package |
|-----|----------|---------|---------|
| aas-core3.0 Python | Python | pytest-benchmark | `aas-core3.0` |
| aas-core3.0 Go | Go | testing.B | `github.com/aas-core-works/aas-core3.0-golang` |
| aas-core3.0 Java | Java | JMH | `io.github.aas-core-works:aas-core3.0-java` |
| aas-core3.0 TypeScript | TypeScript | tinybench | `@aas-core-works/aas-core3.0-typescript` |
| BaSyx Rust SDK | Rust | criterion | `basyx-rs` |
| aas-core3.0 C# | C# | BenchmarkDotNet | `AasCore.Aas3_0` (disabled) |

### Server Implementations

| Server | Docker Image |
|--------|-------------|
| Eclipse BaSyx Java v2 | `eclipsebasyx/aas-environment` |
| FA³ST Service | `fraunhoferiosb/faaast-service` |

## Dashboard

View the latest results at: https://hadijannat.github.io/aas-benchmark-observatory/

The dashboard is a tabbed SPA:
- **SDK Pipeline**: Comparison tables per dataset with operation timings, plus per-SDK detail cards showing metadata
- **Server API**: Conformance pass/fail cards and k6 performance results

## License

MIT
