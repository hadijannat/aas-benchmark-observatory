/**
 * Benchmarks for aas-core3.0 TypeScript SDK using tinybench.
 *
 * Outputs JSON results to stdout for emit_report.js to consume.
 * Expects DATASETS_DIR env var pointing to directory with dataset JSON/XML files.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { Bench } from "tinybench";
import * as aasJsonization from "@aas-core-works/aas-core3.0-typescript/jsonization";
import * as aasVerification from "@aas-core-works/aas-core3.0-typescript/verification";
import * as aasTypes from "@aas-core-works/aas-core3.0-typescript/types";

interface DatasetInfo {
  name: string;
  filePath: string;
  raw: string;
  fileSizeBytes: number;
}

interface MemorySnapshot {
  rssBefore: number;
  rssAfter: number;
  peakRssBytes: number;
  heapUsedBytes: number;
}

interface BenchTaskResult {
  dataset: string;
  operation: string;
  iterations: number;
  meanMs: number;
  medianMs: number | null;
  stddevMs: number | null;
  minMs: number;
  maxMs: number;
  p75Ms: number | null;
  p99Ms: number | null;
  memory: MemorySnapshot | null;
}

function discoverDatasets(): DatasetInfo[] {
  const datasetsDir = process.env.DATASETS_DIR;
  if (!datasetsDir) {
    throw new Error("DATASETS_DIR environment variable not set");
  }

  if (!fs.existsSync(datasetsDir)) {
    throw new Error(`DATASETS_DIR does not exist: ${datasetsDir}`);
  }

  const files = fs.readdirSync(datasetsDir).filter((f) => f.endsWith(".json")).sort();

  if (files.length === 0) {
    throw new Error(`No JSON files found in ${datasetsDir}`);
  }

  return files.map((f) => {
    const filePath = path.join(datasetsDir, f);
    const raw = fs.readFileSync(filePath, "utf-8");
    const stat = fs.statSync(filePath);
    return {
      name: path.basename(f, ".json"),
      filePath,
      raw,
      fileSizeBytes: stat.size,
    };
  });
}

function captureMemory(): { rss: number; heapUsed: number } {
  const mem = process.memoryUsage();
  return { rss: mem.rss, heapUsed: mem.heapUsed };
}

function buildMemorySnapshot(
  before: { rss: number; heapUsed: number },
  after: { rss: number; heapUsed: number },
): MemorySnapshot {
  return {
    rssBefore: before.rss,
    rssAfter: after.rss,
    peakRssBytes: after.rss - before.rss,
    heapUsedBytes: after.heapUsed - before.heapUsed,
  };
}

function buildResult(
  dataset: string,
  operation: string,
  task: { result: NonNullable<(typeof Bench.prototype.tasks)[0]["result"]> },
  memory: MemorySnapshot,
): BenchTaskResult {
  const r = task.result;
  return {
    dataset,
    operation,
    iterations: r.totalTime > 0 ? Math.round(r.totalTime / r.mean) : 0,
    meanMs: r.mean,
    medianMs: r.p50 ?? null,
    stddevMs: r.sd ?? null,
    minMs: r.min,
    maxMs: r.max,
    p75Ms: r.p75 ?? null,
    p99Ms: r.p99 ?? null,
    memory,
  };
}

async function runBenchmarksForDataset(dataset: DatasetInfo): Promise<BenchTaskResult[]> {
  const results: BenchTaskResult[] = [];

  // Pre-deserialize for benchmarks that need a loaded environment
  const jsonable = JSON.parse(dataset.raw);
  const env = aasJsonization.environmentFromJsonable(jsonable);
  if (env.error !== null) {
    throw new Error(`Failed to deserialize ${dataset.name}: ${env.error.message}`);
  }
  const environment = env.mustValue();

  // --- Deserialize ---
  const deserializeBench = new Bench({ time: 5000, warmupTime: 1000 });
  deserializeBench.add("deserialize", () => {
    const parsed = JSON.parse(dataset.raw);
    const result = aasJsonization.environmentFromJsonable(parsed);
    if (result.error !== null) {
      throw new Error(result.error.message);
    }
  });

  let memBefore = captureMemory();
  await deserializeBench.run();
  let memAfter = captureMemory();

  results.push(buildResult(
    dataset.name, "deserialize", deserializeBench.tasks[0]! as any,
    buildMemorySnapshot(memBefore, memAfter),
  ));

  // --- Validate ---
  const validateBench = new Bench({ time: 5000, warmupTime: 1000 });
  validateBench.add("validate", () => {
    const errors: string[] = [];
    for (const error of aasVerification.verify(environment)) {
      errors.push(error.message);
    }
  });

  memBefore = captureMemory();
  await validateBench.run();
  memAfter = captureMemory();

  results.push(buildResult(
    dataset.name, "validate", validateBench.tasks[0]! as any,
    buildMemorySnapshot(memBefore, memAfter),
  ));

  // --- Traverse ---
  const traverseBench = new Bench({ time: 5000, warmupTime: 1000 });
  traverseBench.add("traverse", () => {
    let count = 0;
    for (const _ of environment.descend()) {
      count++;
    }
  });

  memBefore = captureMemory();
  await traverseBench.run();
  memAfter = captureMemory();

  results.push(buildResult(
    dataset.name, "traverse", traverseBench.tasks[0]! as any,
    buildMemorySnapshot(memBefore, memAfter),
  ));

  // --- Update ---
  const updateBench = new Bench({ time: 5000, warmupTime: 1000 });
  updateBench.add("update", () => {
    for (const node of environment.descend()) {
      if (node instanceof aasTypes.Property) {
        if (node.value !== null) {
          node.value = node.value + "_updated";
        }
      }
    }
  });

  memBefore = captureMemory();
  await updateBench.run();
  memAfter = captureMemory();

  results.push(buildResult(
    dataset.name, "update", updateBench.tasks[0]! as any,
    buildMemorySnapshot(memBefore, memAfter),
  ));

  // --- Serialize ---
  const serializeBench = new Bench({ time: 5000, warmupTime: 1000 });
  serializeBench.add("serialize", () => {
    const jsonableOut = aasJsonization.toJsonable(environment);
    JSON.stringify(jsonableOut);
  });

  memBefore = captureMemory();
  await serializeBench.run();
  memAfter = captureMemory();

  results.push(buildResult(
    dataset.name, "serialize", serializeBench.tasks[0]! as any,
    buildMemorySnapshot(memBefore, memAfter),
  ));

  return results;
}

async function main(): Promise<void> {
  const datasets = discoverDatasets();
  const allResults: BenchTaskResult[] = [];

  // JSON pipeline benchmarks
  for (const dataset of datasets) {
    process.stderr.write(`Benchmarking JSON dataset: ${dataset.name}\n`);
    const results = await runBenchmarksForDataset(dataset);
    allResults.push(...results);
  }

  // Note: XML benchmarks skipped — TS SDK does not export xmlization module

  // Output all results as JSON to stdout
  process.stdout.write(JSON.stringify(allResults, null, 2) + "\n");
}

main().catch((err) => {
  process.stderr.write(`Error: ${err}\n`);
  process.exit(1);
});
