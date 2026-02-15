# AAS Benchmark Observatory

Automated benchmarking of Asset Administration Shell (AAS) server implementations.

[![Nightly Benchmark](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml/badge.svg)](https://github.com/hadijannat/aas-benchmark-observatory/actions/workflows/nightly-benchmark.yml)

## Architecture

A **manifest-driven CI harness** that benchmarks AAS server implementations and publishes results to GitHub Pages.

```
known-sdks.json → GitHub Actions matrix → Docker Compose → conformance + k6 → aggregate → dashboard
```

### Components

| Component | Purpose |
|-----------|---------|
| `known-sdks.json` | Source of truth — lists all tracked SDK implementations |
| `sdks/<id>/` | Per-SDK adapter: `sdk.yaml` contract + `docker-compose.yml` |
| `harness/` | Shared test harness: health checks, conformance tests, k6 benchmarks |
| `scripts/` | CI helpers: matrix generation, SDK discovery, result aggregation |
| `.github/workflows/` | Nightly benchmarks, PR smoke tests, SDK version discovery |
| `dashboard/` | Single-page dashboard deployed to GitHub Pages |

### Workflow

1. **Nightly** (`03:00 UTC`): Runs full conformance + performance benchmarks for all enabled SDKs
2. **PR Smoke**: On pull requests touching `sdks/` or `harness/`, runs a quick smoke test
3. **Weekly Discovery**: Checks Docker Hub for new SDK versions, opens issues

## Adding an SDK

1. Add an entry to `known-sdks.json` with `"enabled": false`
2. Create `sdks/<id>/sdk.yaml` describing the API contract
3. Create `sdks/<id>/docker-compose.yml` to launch the server
4. Open a PR — the smoke test validates your adapter
5. After review, set `"enabled": true`

## Currently Tracked SDKs

| SDK | Docker Image |
|-----|-------------|
| Eclipse BaSyx Java v2 | `eclipsebasyx/aas-environment` |
| FA³ST Service | `fraunhoferiosb/faaast-service` |

## Dashboard

View the latest results at: https://hadijannat.github.io/aas-benchmark-observatory/

## License

MIT
