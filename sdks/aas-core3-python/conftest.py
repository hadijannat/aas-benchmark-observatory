"""Pytest fixtures for AAS Core 3.0 Python benchmarks."""

import json
import os
import pathlib
import tracemalloc

import psutil
import pytest


def _find_dataset_files():
    """Discover dataset JSON files from DATASETS_DIR."""
    datasets_dir = os.environ.get("DATASETS_DIR", "")
    if not datasets_dir:
        pytest.skip("DATASETS_DIR not set")
    p = pathlib.Path(datasets_dir)
    if not p.is_dir():
        pytest.skip(f"DATASETS_DIR does not exist: {datasets_dir}")
    files = sorted(p.glob("*.json"))
    if not files:
        pytest.skip(f"No JSON files found in {datasets_dir}")
    return files


def _find_xml_files():
    """Discover dataset XML files from DATASETS_DIR."""
    datasets_dir = os.environ.get("DATASETS_DIR", "")
    if not datasets_dir:
        pytest.skip("DATASETS_DIR not set")
    p = pathlib.Path(datasets_dir)
    if not p.is_dir():
        pytest.skip(f"DATASETS_DIR does not exist: {datasets_dir}")
    files = sorted(p.glob("*.xml"))
    if not files:
        pytest.skip(f"No XML files found in {datasets_dir}")
    return files


def _find_aasx_files():
    """Discover AASX package files from DATASETS_DIR."""
    datasets_dir = os.environ.get("DATASETS_DIR", "")
    if not datasets_dir:
        pytest.skip("DATASETS_DIR not set")
    p = pathlib.Path(datasets_dir)
    if not p.is_dir():
        pytest.skip(f"DATASETS_DIR does not exist: {datasets_dir}")
    files = sorted(p.glob("*.aasx"))
    if not files:
        pytest.skip(f"No AASX files found in {datasets_dir}")
    return files


def _dataset_id(path):
    """Extract dataset ID from filename, e.g. 'wide.json' -> 'wide'."""
    return path.stem


@pytest.fixture(params=_find_dataset_files(), ids=_dataset_id)
def dataset_path(request):
    """Parametrized fixture yielding each dataset file path."""
    return request.param


@pytest.fixture
def dataset_raw(dataset_path):
    """Read raw bytes of a dataset file."""
    return dataset_path.read_text(encoding="utf-8")


@pytest.fixture
def dataset_jsonable(dataset_raw):
    """Parse dataset JSON into a Python dict."""
    return json.loads(dataset_raw)


@pytest.fixture(params=_find_xml_files(), ids=_dataset_id)
def xml_dataset_path(request):
    """Parametrized fixture yielding each XML dataset file path."""
    return request.param


@pytest.fixture
def xml_dataset_raw(xml_dataset_path):
    """Read raw bytes of an XML dataset file."""
    return xml_dataset_path.read_bytes()


@pytest.fixture(params=_find_aasx_files(), ids=_dataset_id)
def aasx_path(request):
    """Parametrized fixture yielding each AASX file path."""
    return request.param


class MemoryTracker:
    """Track peak RSS and tracemalloc memory usage around operations."""

    def __init__(self):
        self._process = psutil.Process()
        self.records = {}

    def measure_peak_rss(self):
        """Return current RSS in bytes."""
        return self._process.memory_info().rss

    def measure_tracemalloc_peak(self):
        """Return tracemalloc peak traced memory in bytes, or None if not started."""
        if tracemalloc.is_tracing():
            _current, peak = tracemalloc.get_traced_memory()
            return peak
        return None

    def reset_tracemalloc_peak(self):
        """Reset tracemalloc peak to allow per-operation measurement."""
        if tracemalloc.is_tracing():
            tracemalloc.reset_peak()

    def record(self, dataset_name, operation, peak_rss_bytes, traced_peak_bytes=None):
        """Store a memory measurement."""
        key = f"{dataset_name}/{operation}"
        self.records[key] = {
            "peak_rss_bytes": peak_rss_bytes,
            "traced_peak_bytes": traced_peak_bytes,
        }


# Module-level memory tracker shared across all tests
_memory_tracker = MemoryTracker()


@pytest.fixture
def memory_tracker():
    """Provide the shared memory tracker instance."""
    return _memory_tracker


def pytest_configure(config):
    """Start tracemalloc at session start for Python-specific memory tracking."""
    tracemalloc.start()


def pytest_sessionfinish(session, exitstatus):
    """Write memory measurements to a JSON file at session end."""
    if tracemalloc.is_tracing():
        tracemalloc.stop()

    memory_json = os.environ.get("MEMORY_JSON", "")
    if memory_json and _memory_tracker.records:
        with open(memory_json, "w", encoding="utf-8") as f:
            json.dump(_memory_tracker.records, f, indent=2)
