/**
 * Benchmarks for aas-core3.0 TypeScript SDK using tinybench.
 *
 * Outputs JSON results to stdout for emit_report.js to consume.
 * Expects DATASETS_DIR env var pointing to directory with dataset JSON files.
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

function measureMemory(): number {
  return process.memoryUsage().rss;
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

  let rssBefore = measureMemory();
  await deserializeBench.run();
  let rssAfter = measureMemory();

  const deserializeTask = deserializeBench.tasks[0]!;
  results.push({
    dataset: dataset.name,
    operation: "deserialize",
    iterations: deserializeTask.result!.totalTime > 0
      ? Math.round(deserializeTask.result!.totalTime / deserializeTask.result!.mean)
      : 0,
    meanMs: deserializeTask.result!.mean,
    medianMs: deserializeTask.result!.p50 ?? null,
    stddevMs: deserializeTask.result!.sd ?? null,
    minMs: deserializeTask.result!.min,
    maxMs: deserializeTask.result!.max,
    p75Ms: deserializeTask.result!.p75 ?? null,
    p99Ms: deserializeTask.result!.p99 ?? null,
    memory: { rssBefore, rssAfter, peakRssBytes: rssAfter - rssBefore },
  });

  // --- Validate ---
  const validateBench = new Bench({ time: 5000, warmupTime: 1000 });
  validateBench.add("validate", () => {
    const errors: string[] = [];
    for (const error of aasVerification.verify(environment)) {
      errors.push(error.message);
    }
  });

  rssBefore = measureMemory();
  await validateBench.run();
  rssAfter = measureMemory();

  const validateTask = validateBench.tasks[0]!;
  results.push({
    dataset: dataset.name,
    operation: "validate",
    iterations: validateTask.result!.totalTime > 0
      ? Math.round(validateTask.result!.totalTime / validateTask.result!.mean)
      : 0,
    meanMs: validateTask.result!.mean,
    medianMs: validateTask.result!.p50 ?? null,
    stddevMs: validateTask.result!.sd ?? null,
    minMs: validateTask.result!.min,
    maxMs: validateTask.result!.max,
    p75Ms: validateTask.result!.p75 ?? null,
    p99Ms: validateTask.result!.p99 ?? null,
    memory: { rssBefore, rssAfter, peakRssBytes: rssAfter - rssBefore },
  });

  // --- Traverse ---
  const traverseBench = new Bench({ time: 5000, warmupTime: 1000 });
  traverseBench.add("traverse", () => {
    let count = 0;
    for (const _ of environment.descend()) {
      count++;
    }
  });

  rssBefore = measureMemory();
  await traverseBench.run();
  rssAfter = measureMemory();

  const traverseTask = traverseBench.tasks[0]!;
  results.push({
    dataset: dataset.name,
    operation: "traverse",
    iterations: traverseTask.result!.totalTime > 0
      ? Math.round(traverseTask.result!.totalTime / traverseTask.result!.mean)
      : 0,
    meanMs: traverseTask.result!.mean,
    medianMs: traverseTask.result!.p50 ?? null,
    stddevMs: traverseTask.result!.sd ?? null,
    minMs: traverseTask.result!.min,
    maxMs: traverseTask.result!.max,
    p75Ms: traverseTask.result!.p75 ?? null,
    p99Ms: traverseTask.result!.p99 ?? null,
    memory: { rssBefore, rssAfter, peakRssBytes: rssAfter - rssBefore },
  });

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

  rssBefore = measureMemory();
  await updateBench.run();
  rssAfter = measureMemory();

  const updateTask = updateBench.tasks[0]!;
  results.push({
    dataset: dataset.name,
    operation: "update",
    iterations: updateTask.result!.totalTime > 0
      ? Math.round(updateTask.result!.totalTime / updateTask.result!.mean)
      : 0,
    meanMs: updateTask.result!.mean,
    medianMs: updateTask.result!.p50 ?? null,
    stddevMs: updateTask.result!.sd ?? null,
    minMs: updateTask.result!.min,
    maxMs: updateTask.result!.max,
    p75Ms: updateTask.result!.p75 ?? null,
    p99Ms: updateTask.result!.p99 ?? null,
    memory: { rssBefore, rssAfter, peakRssBytes: rssAfter - rssBefore },
  });

  // --- Serialize ---
  const serializeBench = new Bench({ time: 5000, warmupTime: 1000 });
  serializeBench.add("serialize", () => {
    const jsonableOut = aasJsonization.toJsonable(environment);
    JSON.stringify(jsonableOut);
  });

  rssBefore = measureMemory();
  await serializeBench.run();
  rssAfter = measureMemory();

  const serializeTask = serializeBench.tasks[0]!;
  results.push({
    dataset: dataset.name,
    operation: "serialize",
    iterations: serializeTask.result!.totalTime > 0
      ? Math.round(serializeTask.result!.totalTime / serializeTask.result!.mean)
      : 0,
    meanMs: serializeTask.result!.mean,
    medianMs: serializeTask.result!.p50 ?? null,
    stddevMs: serializeTask.result!.sd ?? null,
    minMs: serializeTask.result!.min,
    maxMs: serializeTask.result!.max,
    p75Ms: serializeTask.result!.p75 ?? null,
    p99Ms: serializeTask.result!.p99 ?? null,
    memory: { rssBefore, rssAfter, peakRssBytes: rssAfter - rssBefore },
  });

  return results;
}

async function main(): Promise<void> {
  const datasets = discoverDatasets();
  const allResults: BenchTaskResult[] = [];

  for (const dataset of datasets) {
    process.stderr.write(`Benchmarking dataset: ${dataset.name}\n`);
    const results = await runBenchmarksForDataset(dataset);
    allResults.push(...results);
  }

  // Output all results as JSON to stdout
  process.stdout.write(JSON.stringify(allResults, null, 2) + "\n");
}

main().catch((err) => {
  process.stderr.write(`Error: ${err}\n`);
  process.exit(1);
});
