package main

import (
	"bytes"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	aas "github.com/aas-core-works/aas-core3.0-golang/jsonization"
	aastypes "github.com/aas-core-works/aas-core3.0-golang/types"
	aasverification "github.com/aas-core-works/aas-core3.0-golang/verification"
	aasxml "github.com/aas-core-works/aas-core3.0-golang/xmlization"
)

// memorySnapshot captures a single ReadMemStats measurement.
type memorySnapshot struct {
	HeapAllocBytes uint64 `json:"heap_alloc_bytes"`
	HeapSysBytes   uint64 `json:"heap_sys_bytes"`
	TotalAllocBytes uint64 `json:"total_alloc_bytes"`
	NumGC          uint32 `json:"num_gc"`
	PauseTotalNs   uint64 `json:"pause_total_ns"`
}

// memoryStatsFile is the schema written to memory_stats.json.
type memoryStatsFile struct {
	Before memorySnapshot            `json:"before"`
	After  memorySnapshot            `json:"after"`
	Groups map[string]memorySnapshot `json:"groups"`
}

// captureMemSnapshot reads runtime.MemStats and returns a snapshot.
func captureMemSnapshot() memorySnapshot {
	runtime.GC() // force GC so HeapAlloc is more accurate
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return memorySnapshot{
		HeapAllocBytes:  m.HeapAlloc,
		HeapSysBytes:    m.HeapSys,
		TotalAllocBytes: m.TotalAlloc,
		NumGC:           m.NumGC,
		PauseTotalNs:    m.PauseTotalNs,
	}
}

// globalMemStats accumulates per-group snapshots written at the end.
var globalMemStats = memoryStatsFile{
	Groups: make(map[string]memorySnapshot),
}

// datasetFiles returns the list of JSON dataset files from DATASETS_DIR.
func datasetFiles(b *testing.B) []string {
	b.Helper()
	dir := os.Getenv("DATASETS_DIR")
	if dir == "" {
		b.Skip("DATASETS_DIR not set")
	}
	matches, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		b.Fatalf("Failed to glob datasets: %v", err)
	}
	if len(matches) == 0 {
		b.Skipf("No JSON files found in %s", dir)
	}
	return matches
}

// datasetXmlFiles returns the list of XML dataset files from DATASETS_DIR.
func datasetXmlFiles(b *testing.B) []string {
	b.Helper()
	dir := os.Getenv("DATASETS_DIR")
	if dir == "" {
		b.Skip("DATASETS_DIR not set")
	}
	matches, err := filepath.Glob(filepath.Join(dir, "*.xml"))
	if err != nil {
		b.Fatalf("Failed to glob XML datasets: %v", err)
	}
	if len(matches) == 0 {
		b.Skipf("No XML files found in %s", dir)
	}
	return matches
}

// datasetName extracts the dataset name from a file path (e.g. "wide" from "/path/wide.json").
func datasetName(path string) string {
	base := filepath.Base(path)
	return strings.TrimSuffix(base, filepath.Ext(base))
}

// loadRawJSON reads a dataset file and returns its raw bytes.
func loadRawJSON(b *testing.B, path string) []byte {
	b.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		b.Fatalf("Failed to read %s: %v", path, err)
	}
	return data
}

// loadRawXML reads an XML dataset file and returns its raw bytes.
func loadRawXML(b *testing.B, path string) []byte {
	b.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		b.Fatalf("Failed to read XML %s: %v", path, err)
	}
	return data
}

// deserializeEnv unmarshals raw JSON into an AAS Environment.
func deserializeEnv(raw []byte) (aastypes.IEnvironment, error) {
	var jsonable interface{}
	if err := json.Unmarshal(raw, &jsonable); err != nil {
		return nil, fmt.Errorf("json unmarshal: %w", err)
	}
	env, deserErr := aas.EnvironmentFromJsonable(jsonable)
	if deserErr != nil {
		return nil, fmt.Errorf("environment_from_jsonable: %s", deserErr.Error())
	}
	return env, nil
}

// deserializeXmlEnv unmarshals raw XML bytes into an AAS Environment.
func deserializeXmlEnv(raw []byte) (aastypes.IEnvironment, error) {
	reader := bytes.NewReader(raw)
	decoder := xml.NewDecoder(reader)
	instance, err := aasxml.Unmarshal(decoder)
	if err != nil {
		return nil, fmt.Errorf("xml unmarshal: %w", err)
	}
	env, ok := instance.(aastypes.IEnvironment)
	if !ok {
		return nil, fmt.Errorf("xml unmarshal: expected IEnvironment, got %T", instance)
	}
	return env, nil
}

// BenchmarkDeserialize benchmarks JSON -> AAS Environment deserialization.
func BenchmarkDeserialize(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawJSON(b, f)
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				env, err := deserializeEnv(raw)
				if err != nil {
					b.Fatal(err)
				}
				_ = env
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["deserialize"] = after
	_ = before
}

// BenchmarkDeserializeXml benchmarks XML -> AAS Environment deserialization.
func BenchmarkDeserializeXml(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetXmlFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawXML(b, f)
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				env, err := deserializeXmlEnv(raw)
				if err != nil {
					b.Fatal(err)
				}
				_ = env
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["deserialize_xml"] = after
	_ = before
}

// BenchmarkValidate benchmarks verification of a deserialized AAS Environment.
func BenchmarkValidate(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawJSON(b, f)
		env, err := deserializeEnv(raw)
		if err != nil {
			b.Fatalf("Setup failed for %s: %v", name, err)
		}
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				errorCount := 0
				aasverification.Verify(env, func(_ *aasverification.VerificationError) bool {
					errorCount++
					return false // continue verification
				})
				_ = errorCount
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["validate"] = after
	_ = before
}

// BenchmarkTraverse benchmarks descending through all nodes in an AAS Environment.
func BenchmarkTraverse(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawJSON(b, f)
		env, err := deserializeEnv(raw)
		if err != nil {
			b.Fatalf("Setup failed for %s: %v", name, err)
		}
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				count := 0
				env.Descend(func(_ aastypes.IClass) bool {
					count++
					return false // continue descending
				})
				_ = count
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["traverse"] = after
	_ = before
}

// BenchmarkUpdate benchmarks finding all Property instances and updating their values.
func BenchmarkUpdate(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawJSON(b, f)
		env, err := deserializeEnv(raw)
		if err != nil {
			b.Fatalf("Setup failed for %s: %v", name, err)
		}
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				count := 0
				env.Descend(func(node aastypes.IClass) bool {
					if prop, ok := node.(aastypes.IProperty); ok {
						val := prop.Value()
						if val != nil {
							updated := *val + "_updated"
							prop.SetValue(&updated)
							count++
						}
					}
					return false // continue descending
				})
				_ = count
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["update"] = after
	_ = before
}

// BenchmarkSerialize benchmarks AAS Environment -> JSON serialization.
func BenchmarkSerialize(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetFiles(b)
	for _, f := range files {
		name := datasetName(f)
		raw := loadRawJSON(b, f)
		env, err := deserializeEnv(raw)
		if err != nil {
			b.Fatalf("Setup failed for %s: %v", name, err)
		}
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				jsonable, serErr := aas.ToJsonable(env)
				if serErr != nil {
					b.Fatal(serErr)
				}
				data, marshalErr := json.Marshal(jsonable)
				if marshalErr != nil {
					b.Fatal(marshalErr)
				}
				_ = data
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["serialize"] = after
	_ = before
}

// BenchmarkSerializeXml benchmarks AAS Environment -> XML serialization.
func BenchmarkSerializeXml(b *testing.B) {
	before := captureMemSnapshot()
	files := datasetXmlFiles(b)
	for _, f := range files {
		name := datasetName(f)
		// Load XML, deserialize to env, then re-serialize to XML
		raw := loadRawXML(b, f)
		env, err := deserializeXmlEnv(raw)
		if err != nil {
			b.Fatalf("Setup failed for XML %s: %v", name, err)
		}
		b.Run(name, func(b *testing.B) {
			b.ResetTimer()
			for i := 0; i < b.N; i++ {
				var buf bytes.Buffer
				encoder := xml.NewEncoder(&buf)
				marshalErr := aasxml.Marshal(encoder, env, true)
				if marshalErr != nil {
					b.Fatal(marshalErr)
				}
				_ = buf.Bytes()
			}
		})
	}
	after := captureMemSnapshot()
	globalMemStats.Groups["serialize_xml"] = after
	_ = before
}

// TestMain runs after all benchmarks and writes memory_stats.json.
func TestMain(m *testing.M) {
	// Capture overall "before" snapshot
	globalMemStats.Before = captureMemSnapshot()

	// Run all tests and benchmarks
	exitCode := m.Run()

	// Capture overall "after" snapshot
	globalMemStats.After = captureMemSnapshot()

	// Write memory_stats.json to OUTPUT_DIR if set
	outputDir := os.Getenv("OUTPUT_DIR")
	if outputDir != "" {
		memPath := filepath.Join(outputDir, "memory_stats.json")
		data, err := json.MarshalIndent(globalMemStats, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "Warning: failed to marshal memory stats: %v\n", err)
		} else {
			if err := os.MkdirAll(outputDir, 0755); err != nil {
				fmt.Fprintf(os.Stderr, "Warning: failed to create output dir: %v\n", err)
			} else if err := os.WriteFile(memPath, data, 0644); err != nil {
				fmt.Fprintf(os.Stderr, "Warning: failed to write memory stats: %v\n", err)
			} else {
				fmt.Fprintf(os.Stderr, "Wrote memory stats to %s\n", memPath)
			}
		}
	}

	os.Exit(exitCode)
}
