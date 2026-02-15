package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	aas "github.com/aas-core-works/aas-core3.0-golang/jsonization"
	aastypes "github.com/aas-core-works/aas-core3.0-golang/types"
	aasverification "github.com/aas-core-works/aas-core3.0-golang/verification"
)

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

// BenchmarkDeserialize benchmarks JSON -> AAS Environment deserialization.
func BenchmarkDeserialize(b *testing.B) {
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
}

// BenchmarkValidate benchmarks verification of a deserialized AAS Environment.
func BenchmarkValidate(b *testing.B) {
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
				errors := make([]string, 0)
				for verErr := range aasverification.Verify(env) {
					errors = append(errors, verErr.Error())
				}
				_ = errors
			}
		})
	}
}

// BenchmarkTraverse benchmarks descending through all nodes in an AAS Environment.
func BenchmarkTraverse(b *testing.B) {
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
				for range env.Descend() {
					count++
				}
				_ = count
			}
		})
	}
}

// BenchmarkUpdate benchmarks finding all Property instances and updating their values.
func BenchmarkUpdate(b *testing.B) {
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
				for node := range env.Descend() {
					if prop, ok := node.(aastypes.IProperty); ok {
						val := prop.Value()
						if val != nil {
							updated := *val + "_updated"
							prop.SetValue(&updated)
							count++
						}
					}
				}
				_ = count
			}
		})
	}
}

// BenchmarkSerialize benchmarks AAS Environment -> JSON serialization.
func BenchmarkSerialize(b *testing.B) {
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
				jsonable := aas.ToJsonable(env)
				data, marshalErr := json.Marshal(jsonable)
				if marshalErr != nil {
					b.Fatal(marshalErr)
				}
				_ = data
			}
		})
	}
}
