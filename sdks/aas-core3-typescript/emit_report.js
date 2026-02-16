#!/usr/bin/env node
/**
 * Convert tinybench JSON output to report.json schema.
 *
 * Usage:
 *   node emit_report.js <bench_raw.json> <output_path>
 *
 * tinybench results have `mean` in milliseconds — we convert to nanoseconds.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function msToNs(ms) {
  if (ms === null || ms === undefined) {
    return null;
  }
  return Math.round(ms * 1e6);
}

function main() {
  if (process.argv.length !== 4) {
    process.stderr.write(
      "Usage: node emit_report.js <bench_raw.json> <output_path>\n"
    );
    process.exit(1);
  }

  const inputPath = process.argv[2];
  const outputPath = process.argv[3];

  const rawData = fs.readFileSync(inputPath, "utf-8");
  const benchResults = JSON.parse(rawData);

  // Organize by dataset
  const datasets = {};

  for (const result of benchResults) {
    const dsName = result.dataset;
    if (!(dsName in datasets)) {
      datasets[dsName] = {
        file_size_bytes: null,
        element_count: null,
        operations: {},
      };
    }

    const meanNs = msToNs(result.meanMs);
    let throughput = 0;
    if (result.meanMs > 0) {
      throughput = Math.round((1000 / result.meanMs) * 100) / 100;
    }

    const memoryEntry = {
      peak_rss_bytes: null,
      heap_used_bytes: null,
      alloc_bytes_per_op: null,
      alloc_count_per_op: null,
      gc_pause_ms: null,
      gc_count: null,
      traced_peak_bytes: null,
    };

    if (result.memory) {
      memoryEntry.peak_rss_bytes =
        result.memory.peakRssBytes > 0 ? result.memory.peakRssBytes : null;
      memoryEntry.heap_used_bytes =
        result.memory.heapUsedBytes != null && result.memory.heapUsedBytes !== 0
          ? result.memory.heapUsedBytes
          : null;
    }

    datasets[dsName].operations[result.operation] = {
      iterations: result.iterations || 0,
      mean_ns: meanNs,
      median_ns: msToNs(result.medianMs),
      stddev_ns: msToNs(result.stddevMs),
      min_ns: msToNs(result.minMs),
      max_ns: msToNs(result.maxMs),
      p75_ns: msToNs(result.p75Ms),
      p99_ns: msToNs(result.p99Ms),
      throughput_ops_per_sec: throughput,
      memory: memoryEntry,
    };
  }

  // Detect Node.js version
  const nodeVersion = process.version;

  // Try to get SDK package version
  let sdkVersion = "unknown";
  try {
    const pkgPath = path.join(
      __dirname,
      "node_modules",
      "@aas-core-works",
      "aas-core3.0-typescript",
      "package.json"
    );
    if (fs.existsSync(pkgPath)) {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
      sdkVersion = pkg.version || "unknown";
    }
  } catch {
    // ignore
  }

  const report = {
    schema_version: 2,
    sdk_id: "aas-core3-typescript",
    metadata: {
      language: "typescript",
      runtime_version: `Node.js ${nodeVersion}`,
      sdk_package_version: sdkVersion,
      benchmark_harness: "tinybench",
      timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    },
    datasets,
  };

  // Ensure output directory exists
  const outDir = path.dirname(outputPath);
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + "\n", "utf-8");
  process.stderr.write(`Wrote report to ${outputPath}\n`);
}

main();
