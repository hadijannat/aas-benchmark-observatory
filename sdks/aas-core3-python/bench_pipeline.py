"""Benchmarks for aas-core3.0 Python SDK using pytest-benchmark."""

import json

import aas_core3.jsonization as aas_jsonization
import aas_core3.types as aas_types
import aas_core3.verification as aas_verification


# ---------------------------------------------------------------------------
# Deserialize
# ---------------------------------------------------------------------------

def test_deserialize(benchmark, dataset_raw, dataset_path, memory_tracker):
    """Benchmark: JSON string -> AAS Environment object."""
    dataset_name = dataset_path.stem

    def _deserialize():
        jsonable = json.loads(dataset_raw)
        return aas_jsonization.environment_from_jsonable(jsonable)

    peak_before = memory_tracker.measure_peak_rss()
    result = benchmark(_deserialize)
    peak_after = memory_tracker.measure_peak_rss()
    memory_tracker.record(dataset_name, "deserialize", peak_after - peak_before)
    assert result is not None


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def test_validate(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: verify an AAS Environment, collecting all errors."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)

    def _validate():
        errors = list(aas_verification.verify(env))
        return errors

    peak_before = memory_tracker.measure_peak_rss()
    result = benchmark(_validate)
    peak_after = memory_tracker.measure_peak_rss()
    memory_tracker.record(dataset_name, "validate", peak_after - peak_before)
    # result is a list of errors; we just need it to complete
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Traverse
# ---------------------------------------------------------------------------

def test_traverse(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: descend through all nodes, counting them."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)

    def _traverse():
        count = 0
        for _ in env.descend():
            count += 1
        return count

    peak_before = memory_tracker.measure_peak_rss()
    result = benchmark(_traverse)
    peak_after = memory_tracker.measure_peak_rss()
    memory_tracker.record(dataset_name, "traverse", peak_after - peak_before)
    assert result > 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: find all Property instances and append '_updated' to value."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)

    def _update():
        count = 0
        for node in env.descend():
            if isinstance(node, aas_types.Property):
                if node.value is not None:
                    node.value = node.value + "_updated"
                    count += 1
        return count

    peak_before = memory_tracker.measure_peak_rss()
    result = benchmark(_update)
    peak_after = memory_tracker.measure_peak_rss()
    memory_tracker.record(dataset_name, "update", peak_after - peak_before)
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# Serialize
# ---------------------------------------------------------------------------

def test_serialize(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: AAS Environment -> JSON string."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)

    def _serialize():
        jsonable = aas_jsonization.to_jsonable(env)
        return json.dumps(jsonable)

    peak_before = memory_tracker.measure_peak_rss()
    result = benchmark(_serialize)
    peak_after = memory_tracker.measure_peak_rss()
    memory_tracker.record(dataset_name, "serialize", peak_after - peak_before)
    assert len(result) > 0
