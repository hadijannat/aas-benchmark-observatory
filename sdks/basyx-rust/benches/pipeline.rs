use basyx_rs::Environment;
use criterion::{criterion_group, criterion_main, Criterion};
use std::fs;
use std::path::PathBuf;

fn get_datasets_dir() -> PathBuf {
    let dir = std::env::var("DATASETS_DIR").expect("DATASETS_DIR not set");
    PathBuf::from(dir)
}

fn get_dataset_files() -> Vec<(String, String)> {
    let dir = get_datasets_dir();
    let mut datasets = Vec::new();
    for entry in fs::read_dir(&dir).expect("Failed to read DATASETS_DIR") {
        let entry = entry.expect("Failed to read dir entry");
        let path = entry.path();
        if path.extension().map_or(false, |e| e == "json") {
            let name = path.file_stem().unwrap().to_string_lossy().to_string();
            let content = fs::read_to_string(&path).expect("Failed to read dataset");
            datasets.push((name, content));
        }
    }
    datasets.sort_by(|a, b| a.0.cmp(&b.0));
    datasets
}

fn bench_deserialize(c: &mut Criterion) {
    let datasets = get_dataset_files();
    let mut group = c.benchmark_group("deserialize");
    for (name, json_str) in &datasets {
        group.bench_function(name, |b| {
            b.iter(|| {
                let env: Environment = serde_json::from_str(json_str).unwrap();
                std::hint::black_box(env);
            });
        });
    }
    group.finish();
}

fn bench_serialize(c: &mut Criterion) {
    let datasets = get_dataset_files();
    let mut group = c.benchmark_group("serialize");
    for (name, json_str) in &datasets {
        let env: Environment = serde_json::from_str(json_str).unwrap();
        group.bench_function(name, |b| {
            b.iter(|| {
                let output = serde_json::to_string(&env).unwrap();
                std::hint::black_box(output);
            });
        });
    }
    group.finish();
}

criterion_group!(benches, bench_deserialize, bench_serialize);
criterion_main!(benches);
