"""Benchmarks for aas-core3.0 Python SDK using pytest-benchmark."""

import io
import json
import zipfile

import aas_core3.jsonization as aas_jsonization
import aas_core3.types as aas_types
import aas_core3.verification as aas_verification
import aas_core3.xmlization as aas_xmlization


# ---------------------------------------------------------------------------
# Helper for memory tracking
# ---------------------------------------------------------------------------

def _track(memory_tracker, dataset_name, operation, fn, benchmark):
    """Run a benchmark function with both RSS and tracemalloc measurement."""
    peak_before = memory_tracker.measure_peak_rss()
    memory_tracker.reset_tracemalloc_peak()
    result = benchmark(fn)
    peak_after = memory_tracker.measure_peak_rss()
    traced_peak = memory_tracker.measure_tracemalloc_peak()
    memory_tracker.record(
        dataset_name, operation,
        peak_rss_bytes=peak_after - peak_before,
        traced_peak_bytes=traced_peak,
    )
    return result


# ---------------------------------------------------------------------------
# JSON Deserialize
# ---------------------------------------------------------------------------

def test_deserialize(benchmark, dataset_raw, dataset_path, memory_tracker):
    """Benchmark: JSON string -> AAS Environment object."""
    dataset_name = dataset_path.stem

    def _deserialize():
        jsonable = json.loads(dataset_raw)
        return aas_jsonization.environment_from_jsonable(jsonable)

    result = _track(memory_tracker, dataset_name, "deserialize", _deserialize, benchmark)
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

    result = _track(memory_tracker, dataset_name, "validate", _validate, benchmark)
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

    result = _track(memory_tracker, dataset_name, "traverse", _traverse, benchmark)
    assert result > 0


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: find all Property instances and append '_updated' to value."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)
    baseline = []
    for node in env.descend():
        if isinstance(node, aas_types.Property) and node.value is not None:
            baseline.append((node, node.value))

    def _update():
        # Mutate, then restore baseline so each timing iteration starts from
        # identical state.
        for prop, original in baseline:
            prop.value = original + "_updated"
        for prop, original in baseline:
            prop.value = original
        return len(baseline)

    result = _track(memory_tracker, dataset_name, "update", _update, benchmark)
    assert isinstance(result, int)


# ---------------------------------------------------------------------------
# JSON Serialize
# ---------------------------------------------------------------------------

def test_serialize(benchmark, dataset_jsonable, dataset_path, memory_tracker):
    """Benchmark: AAS Environment -> JSON string."""
    dataset_name = dataset_path.stem
    env = aas_jsonization.environment_from_jsonable(dataset_jsonable)

    def _serialize():
        jsonable = aas_jsonization.to_jsonable(env)
        return json.dumps(jsonable)

    result = _track(memory_tracker, dataset_name, "serialize", _serialize, benchmark)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# XML Deserialize (SRQ-1)
# ---------------------------------------------------------------------------

def test_deserialize_xml(benchmark, xml_dataset_raw, xml_dataset_path, memory_tracker):
    """Benchmark: XML bytes -> AAS Environment object."""
    dataset_name = xml_dataset_path.stem

    def _deserialize_xml():
        return aas_xmlization.environment_from_str(xml_dataset_raw.decode("utf-8"))

    result = _track(memory_tracker, dataset_name, "deserialize_xml", _deserialize_xml, benchmark)
    assert result is not None


# ---------------------------------------------------------------------------
# XML Serialize (SRQ-1)
# ---------------------------------------------------------------------------

def test_serialize_xml(benchmark, xml_dataset_raw, xml_dataset_path, memory_tracker):
    """Benchmark: AAS Environment -> XML string."""
    dataset_name = xml_dataset_path.stem
    env = aas_xmlization.environment_from_str(xml_dataset_raw.decode("utf-8"))

    def _serialize_xml():
        buf = io.StringIO()
        aas_xmlization.write(env, buf)
        return buf.getvalue()

    result = _track(memory_tracker, dataset_name, "serialize_xml", _serialize_xml, benchmark)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# AASX Extract (SRQ-4)
# ---------------------------------------------------------------------------

def test_aasx_extract(benchmark, aasx_path, memory_tracker):
    """Benchmark: read JSON environment from AASX ZIP package."""
    dataset_name = aasx_path.stem

    def _aasx_extract():
        with zipfile.ZipFile(aasx_path, "r") as zf:
            env_json = zf.read("aasx/environment.json")
            jsonable = json.loads(env_json)
            return aas_jsonization.environment_from_jsonable(jsonable)

    result = _track(memory_tracker, dataset_name, "aasx_extract", _aasx_extract, benchmark)
    assert result is not None


# ---------------------------------------------------------------------------
# AASX Repackage (SRQ-4)
# ---------------------------------------------------------------------------

def test_aasx_repackage(benchmark, aasx_path, memory_tracker):
    """Benchmark: read AASX, serialize environment back, write new AASX to memory."""
    dataset_name = aasx_path.stem

    # Pre-extract source data
    with zipfile.ZipFile(aasx_path, "r") as zf:
        env_json = zf.read("aasx/environment.json")
        supplementary = {
            name: zf.read(name)
            for name in zf.namelist()
            if name.startswith("aasx/supplementary/")
        }
    jsonable = json.loads(env_json)
    env = aas_jsonization.environment_from_jsonable(jsonable)

    def _aasx_repackage():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            out_jsonable = aas_jsonization.to_jsonable(env)
            zf.writestr("aasx/environment.json", json.dumps(out_jsonable))
            for name, data in supplementary.items():
                zf.writestr(name, data)
        return buf.getvalue()

    result = _track(memory_tracker, dataset_name, "aasx_repackage", _aasx_repackage, benchmark)
    assert len(result) > 0
