// emit_report.go converts Go test -json benchmark output to the report.json schema.
//
// Usage:
//
//	go run emit_report.go <bench_raw.json> <output_path> [memory_stats.json]
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

var (
	coreDatasets = map[string]bool{
		"wide":  true,
		"deep":  true,
		"mixed": true,
	}
	coreOperations = map[string]bool{
		"deserialize": true,
		"validate":    true,
		"traverse":    true,
		"update":      true,
		"serialize":   true,
	}
)

// GoTestEvent represents a single line from `go test -json` output.
type GoTestEvent struct {
	Time    string  `json:"Time"`
	Action  string  `json:"Action"`
	Package string  `json:"Package"`
	Test    string  `json:"Test"`
	Output  string  `json:"Output"`
	Elapsed float64 `json:"Elapsed"`
}

// BenchResult holds parsed benchmark results for a single sub-benchmark.
type BenchResult struct {
	Operation   string
	Dataset     string
	N           int
	NsPerOp     float64
	BytesPerOp  int64
	AllocsPerOp int64
	Runs        []float64 // NsPerOp across -count runs
}

// MemoryEntry holds memory metrics for report output.
type MemoryEntry struct {
	PeakRSSBytes    *int64   `json:"peak_rss_bytes"`
	AllocBytesPerOp *int64   `json:"alloc_bytes_per_op"`
	AllocCountPerOp *int64   `json:"alloc_count_per_op"`
	HeapUsedBytes   *int64   `json:"heap_used_bytes"`
	GcPauseMs       *float64 `json:"gc_pause_ms"`
	GcCount         *int64   `json:"gc_count"`
	TracedPeakBytes *int64   `json:"traced_peak_bytes"`
}

// OperationEntry is one operation in the report.
type OperationEntry struct {
	OperationID          string      `json:"operation_id"`
	OperationTrack       string      `json:"operation_track"`
	SampleCount          int         `json:"sample_count"`
	MeasurementSemantics string      `json:"measurement_semantics"`
	FailureState         string      `json:"failure_state"`
	Iterations           int         `json:"iterations"`
	MeanNs               int64       `json:"mean_ns"`
	MedianNs             int64       `json:"median_ns"`
	StddevNs             int64       `json:"stddev_ns"`
	MinNs                int64       `json:"min_ns"`
	MaxNs                int64       `json:"max_ns"`
	P75Ns                *int64      `json:"p75_ns"`
	P99Ns                *int64      `json:"p99_ns"`
	ThroughputOpsPerSec  float64     `json:"throughput_ops_per_sec"`
	Memory               MemoryEntry `json:"memory"`
}

// DatasetEntry holds all operations for one dataset.
type DatasetEntry struct {
	FileSizeBytes *int64                    `json:"file_size_bytes"`
	ElementCount  *int64                    `json:"element_count"`
	Operations    map[string]OperationEntry `json:"operations"`
}

// Report is the top-level output schema.
type Report struct {
	SchemaVersion int                     `json:"schema_version"`
	SDKID         string                  `json:"sdk_id"`
	Metadata      map[string]string       `json:"metadata"`
	Datasets      map[string]DatasetEntry `json:"datasets"`
}

// sideChannelMemSnapshot mirrors the snapshot struct written by bench_pipeline_test.go.
type sideChannelMemSnapshot struct {
	HeapAllocBytes  uint64 `json:"heap_alloc_bytes"`
	HeapSysBytes    uint64 `json:"heap_sys_bytes"`
	TotalAllocBytes uint64 `json:"total_alloc_bytes"`
	NumGC           uint32 `json:"num_gc"`
	PauseTotalNs    uint64 `json:"pause_total_ns"`
}

// sideChannelMemStats is the schema of the memory_stats.json file.
type sideChannelMemStats struct {
	Before sideChannelMemSnapshot            `json:"before"`
	After  sideChannelMemSnapshot            `json:"after"`
	Groups map[string]sideChannelMemSnapshot `json:"groups"`
}

// benchLineRegex matches Go benchmark output lines like:
// BenchmarkDeserialize/wide-8   1000   1234567 ns/op   8192 B/op   100 allocs/op
var benchLineRegex = regexp.MustCompile(
	`^Benchmark(\w+)/(\w+)(?:-\d+)?\s+(\d+)\s+([\d.]+)\s+ns/op(?:\s+(\d+)\s+B/op)?(?:\s+(\d+)\s+allocs/op)?`,
)

func canonicalOperationID(raw string) string {
	switch strings.ToLower(raw) {
	case "deserializexml":
		return "deserialize_xml"
	case "serializexml":
		return "serialize_xml"
	case "aasxextract":
		return "aasx_extract"
	case "aasxrepackage":
		return "aasx_repackage"
	default:
		return strings.ToLower(raw)
	}
}

func inferOperationTrack(dataset, operationID string) string {
	switch operationID {
	case "deserialize_xml", "serialize_xml":
		return "xml"
	case "aasx_extract", "aasx_repackage":
		return "aasx"
	}
	if strings.HasPrefix(dataset, "val_") && operationID == "validate" {
		return "validation"
	}
	if coreDatasets[dataset] && coreOperations[operationID] {
		return "core"
	}
	return "capability"
}

func parseBenchResults(path string) (map[string]*BenchResult, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("open %s: %w", path, err)
	}
	defer f.Close()

	results := make(map[string]*BenchResult)
	scanner := bufio.NewScanner(f)
	// Increase buffer for potentially long lines
	scanner.Buffer(make([]byte, 0, 1024*1024), 1024*1024)

	for scanner.Scan() {
		line := scanner.Text()

		// Each line of `go test -json` is a JSON object
		var event GoTestEvent
		if err := json.Unmarshal([]byte(line), &event); err != nil {
			// Skip non-JSON lines
			continue
		}

		if event.Action != "output" {
			continue
		}

		output := strings.TrimSpace(event.Output)
		matches := benchLineRegex.FindStringSubmatch(output)
		if matches == nil {
			continue
		}

		operation := canonicalOperationID(matches[1])
		dataset := matches[2] // e.g., "wide"
		n, _ := strconv.Atoi(matches[3])
		nsPerOp, _ := strconv.ParseFloat(matches[4], 64)

		var bytesPerOp, allocsPerOp int64
		if matches[5] != "" {
			bytesPerOp, _ = strconv.ParseInt(matches[5], 10, 64)
		}
		if matches[6] != "" {
			allocsPerOp, _ = strconv.ParseInt(matches[6], 10, 64)
		}

		key := fmt.Sprintf("%s/%s", dataset, operation)
		if _, exists := results[key]; !exists {
			results[key] = &BenchResult{
				Operation: operation,
				Dataset:   dataset,
			}
		}
		r := results[key]
		r.N += n
		r.BytesPerOp = bytesPerOp
		r.AllocsPerOp = allocsPerOp
		r.Runs = append(r.Runs, nsPerOp)
	}

	return results, scanner.Err()
}

// loadMemoryStats reads the side-channel memory_stats.json file if it exists.
func loadMemoryStats(path string) (*sideChannelMemStats, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var stats sideChannelMemStats
	if err := json.Unmarshal(data, &stats); err != nil {
		return nil, fmt.Errorf("parse memory_stats.json: %w", err)
	}
	return &stats, nil
}

func computeStats(runs []float64) (mean, median, stddev, min, max float64) {
	if len(runs) == 0 {
		return
	}

	// Sort for median
	sorted := make([]float64, len(runs))
	copy(sorted, runs)
	for i := 0; i < len(sorted); i++ {
		for j := i + 1; j < len(sorted); j++ {
			if sorted[j] < sorted[i] {
				sorted[i], sorted[j] = sorted[j], sorted[i]
			}
		}
	}

	min = sorted[0]
	max = sorted[len(sorted)-1]

	// Mean
	sum := 0.0
	for _, v := range sorted {
		sum += v
	}
	mean = sum / float64(len(sorted))

	// Median
	mid := len(sorted) / 2
	if len(sorted)%2 == 0 {
		median = (sorted[mid-1] + sorted[mid]) / 2
	} else {
		median = sorted[mid]
	}

	// Stddev
	if len(sorted) > 1 {
		sumSq := 0.0
		for _, v := range sorted {
			diff := v - mean
			sumSq += diff * diff
		}
		stddev = math.Sqrt(sumSq / float64(len(sorted)-1))
	}

	return
}

func main() {
	if len(os.Args) < 3 || len(os.Args) > 4 {
		fmt.Fprintf(os.Stderr, "Usage: go run emit_report.go <bench_raw.json> <output_path> [memory_stats.json]\n")
		os.Exit(1)
	}

	inputPath := os.Args[1]
	outputPath := os.Args[2]

	// Optionally load side-channel memory stats
	var memStats *sideChannelMemStats
	if len(os.Args) == 4 {
		memStatsPath := os.Args[3]
		ms, err := loadMemoryStats(memStatsPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: could not load memory stats from %s: %v\n", memStatsPath, err)
		} else {
			memStats = ms
			fmt.Fprintf(os.Stderr, "Loaded memory stats from %s\n", memStatsPath)
		}
	}

	results, err := parseBenchResults(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing benchmark results: %v\n", err)
		os.Exit(1)
	}

	// Organize by dataset
	datasets := make(map[string]DatasetEntry)
	for _, r := range results {
		if _, exists := datasets[r.Dataset]; !exists {
			datasets[r.Dataset] = DatasetEntry{
				Operations: make(map[string]OperationEntry),
			}
		}
		ds := datasets[r.Dataset]

		meanNs, medianNs, stddevNs, minNs, maxNs := computeStats(r.Runs)

		throughput := 0.0
		if meanNs > 0 {
			throughput = 1e9 / meanNs
		}

		bytesPerOp := r.BytesPerOp
		allocsPerOp := r.AllocsPerOp

		mem := MemoryEntry{
			AllocBytesPerOp: &bytesPerOp,
			AllocCountPerOp: &allocsPerOp,
		}

		// Populate heap/GC data from side-channel memory stats if available
		if memStats != nil {
			// Look up the group snapshot for this operation
			if groupSnap, ok := memStats.Groups[r.Operation]; ok {
				heapUsed := int64(groupSnap.HeapAllocBytes)
				mem.HeapUsedBytes = &heapUsed

				// GC pause: convert nanoseconds to milliseconds
				gcPauseMs := float64(groupSnap.PauseTotalNs) / 1e6
				mem.GcPauseMs = &gcPauseMs

				gcCount := int64(groupSnap.NumGC)
				mem.GcCount = &gcCount

				// TracedPeakBytes: use HeapSys as a proxy for peak traced memory
				tracedPeak := int64(groupSnap.HeapSysBytes)
				mem.TracedPeakBytes = &tracedPeak
			}

			// Also use the overall "after" snapshot for heap data if no group match
			if mem.HeapUsedBytes == nil {
				heapUsed := int64(memStats.After.HeapAllocBytes)
				mem.HeapUsedBytes = &heapUsed
			}
		}

		op := OperationEntry{
			OperationID:          r.Operation,
			OperationTrack:       inferOperationTrack(r.Dataset, r.Operation),
			SampleCount:          len(r.Runs),
			MeasurementSemantics: "mean_ns_per_operation",
			FailureState:         "ok",
			Iterations:           r.N,
			MeanNs:               int64(math.Round(meanNs)),
			MedianNs:             int64(math.Round(medianNs)),
			StddevNs:             int64(math.Round(stddevNs)),
			MinNs:                int64(math.Round(minNs)),
			MaxNs:                int64(math.Round(maxNs)),
			ThroughputOpsPerSec:  math.Round(throughput*100) / 100,
			Memory:               mem,
		}

		ds.Operations[r.Operation] = op
		datasets[r.Dataset] = ds
	}

	report := Report{
		SchemaVersion: 2,
		SDKID:         "aas-core3-golang",
		Metadata: map[string]string{
			"language":            "go",
			"runtime_version":     runtime.Version(),
			"sdk_package_version": "latest",
			"benchmark_harness":   "testing.B (go test -bench)",
			"timestamp":           time.Now().UTC().Format(time.RFC3339),
		},
		Datasets: datasets,
	}

	out, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling report: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(outputPath, out, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing report: %v\n", err)
		os.Exit(1)
	}

	fmt.Fprintf(os.Stderr, "Wrote report to %s\n", outputPath)
}
