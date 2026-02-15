#!/usr/bin/env python3
"""Generate deterministic AAS v3.0 Environment JSON datasets for benchmarking.

Produces three dataset files:
  wide.json  -- 1 AAS, 1 Submodel, 100,000 Property elements        (~30 MB)
  deep.json  -- 1 AAS, 5 Submodels, nested collections 15 levels     (~200 KB)
  mixed.json -- 5 AAS, 20 Submodels, varied element types, 4 levels  (~500 KB)

Usage:
    python3 datasets/generate.py --output-dir <dir>
    python3 datasets/generate.py --output-dir <dir> --only mixed
"""

import argparse
import base64
import json
import os

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_property(id_short, value="benchmark-value"):
    """Create an AAS v3.0 Property element."""
    return {
        "modelType": "Property",
        "idShort": id_short,
        "valueType": "xs:string",
        "value": value,
    }


def make_collection(id_short, children):
    """Create an AAS v3.0 SubmodelElementCollection."""
    return {
        "modelType": "SubmodelElementCollection",
        "idShort": id_short,
        "value": children,
    }


def make_blob(id_short, content_bytes=b"benchmark-blob-payload"):
    """Create an AAS v3.0 Blob element."""
    return {
        "modelType": "Blob",
        "idShort": id_short,
        "contentType": "application/octet-stream",
        "value": base64.b64encode(content_bytes).decode("ascii"),
    }


def make_mlp(id_short, text="benchmark text"):
    """Create an AAS v3.0 MultiLanguageProperty element."""
    return {
        "modelType": "MultiLanguageProperty",
        "idShort": id_short,
        "value": [
            {"language": "en", "text": text},
            {"language": "de", "text": f"{text} (de)"},
        ],
    }


def make_range(id_short, min_val=0, max_val=100):
    """Create an AAS v3.0 Range element."""
    return {
        "modelType": "Range",
        "idShort": id_short,
        "valueType": "xs:int",
        "min": str(min_val),
        "max": str(max_val),
    }


def make_submodel(sm_id, id_short, elements):
    """Create an AAS v3.0 Submodel."""
    return {
        "modelType": "Submodel",
        "id": sm_id,
        "idShort": id_short,
        "submodelElements": elements,
    }


def make_aas(aas_id, id_short, asset_id, submodel_refs):
    """Create an AAS v3.0 AssetAdministrationShell."""
    return {
        "modelType": "AssetAdministrationShell",
        "id": aas_id,
        "idShort": id_short,
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": asset_id,
        },
        "submodels": [
            {"type": "ModelReference", "keys": [{"type": "Submodel", "value": ref}]}
            for ref in submodel_refs
        ],
    }


def make_environment(shells, submodels):
    """Wrap shells and submodels into an AAS v3.0 Environment envelope."""
    return {
        "assetAdministrationShells": shells,
        "submodels": submodels,
        "assets": [],
    }


# ---------------------------------------------------------------------------
# Dataset builders
# ---------------------------------------------------------------------------


def build_wide():
    """1 AAS -> 1 Submodel -> 100,000 Property elements."""
    sm_id = "urn:benchmark:submodel:wide:0"
    # Pad values to ~200 extra chars so total file reaches ~30 MB.
    # Each property JSON is ~100 bytes of structure + value length.
    elements = [
        make_property(
            f"Prop{i:06d}",
            f"val-{i}-" + f"benchmark-payload-{i:06d}-".ljust(200, "x"),
        )
        for i in range(100_000)
    ]
    submodel = make_submodel(sm_id, "WideSubmodel", elements)
    aas = make_aas(
        "urn:benchmark:aas:wide:0",
        "WideAAS",
        "urn:benchmark:asset:wide:0",
        [sm_id],
    )
    return make_environment([aas], [submodel])


def _build_nested_collection(depth, max_depth, prefix):
    """Recursively build nested SubmodelElementCollections.

    At each level: 5 Properties + 1 child collection (until max_depth).
    Property values are padded so the deep dataset reaches ~200 KB total.
    """
    props = [
        make_property(
            f"{prefix}_Prop{i}",
            f"depth{depth}-val{i}-" + ("d" * 380),
        )
        for i in range(5)
    ]
    if depth >= max_depth:
        return make_collection(f"{prefix}_Col", props)
    child = _build_nested_collection(depth + 1, max_depth, f"{prefix}_L{depth + 1}")
    return make_collection(f"{prefix}_Col", props + [child])


def build_deep():
    """1 AAS -> 5 Submodels -> nested collections 15 levels deep, 5 props/level."""
    submodels = []
    sm_ids = []
    for s in range(5):
        sm_id = f"urn:benchmark:submodel:deep:{s}"
        sm_ids.append(sm_id)
        root = _build_nested_collection(1, 15, f"SM{s}_L1")
        submodels.append(make_submodel(sm_id, f"DeepSubmodel{s}", [root]))
    aas = make_aas(
        "urn:benchmark:aas:deep:0",
        "DeepAAS",
        "urn:benchmark:asset:deep:0",
        sm_ids,
    )
    return make_environment([aas], submodels)


def _build_mixed_collection(depth, max_depth, prefix):
    """Build a mixed-type collection tree up to 4 levels.

    Each level has multiple element types with padded payloads to reach
    ~500 KB total for the mixed dataset.
    """
    children = []
    # 4 properties per level with padded values
    for j in range(4):
        children.append(
            make_property(f"{prefix}_Prop{j}", f"mixed-depth{depth}-{j}-" + ("m" * 140))
        )
    # 3 blobs per level with larger payloads
    for j in range(3):
        children.append(
            make_blob(f"{prefix}_Blob{j}", (f"blob-d{depth}-{j}-" + "B" * 180).encode())
        )
    # 2 MLPs per level
    for j in range(2):
        children.append(
            make_mlp(f"{prefix}_MLP{j}", f"multilang text depth {depth} item {j} " + "t" * 100)
        )
    # 2 ranges per level
    for j in range(2):
        children.append(make_range(f"{prefix}_Range{j}", depth * 10 + j, depth * 10 + 100 + j))
    if depth < max_depth:
        child_col = _build_mixed_collection(depth + 1, max_depth, f"{prefix}_L{depth + 1}")
        children.append(child_col)
    return make_collection(f"{prefix}_Col", children)


def build_mixed():
    """5 AAS -> 20 Submodels -> varied elements with 4-level nesting."""
    all_shells = []
    all_submodels = []
    for a in range(5):
        sm_ids = []
        for s in range(4):
            sm_id = f"urn:benchmark:submodel:mixed:{a}:{s}"
            sm_ids.append(sm_id)
            # Build a mix of top-level elements and nested collection trees
            elements = []
            # 5 top-level properties with padded values
            for p in range(5):
                elements.append(
                    make_property(
                        f"TopProp{s}_{p}",
                        f"aas{a}-sm{s}-prop{p}-" + ("p" * 120),
                    )
                )
            # 3 top-level blobs
            for b in range(3):
                elements.append(
                    make_blob(
                        f"TopBlob{s}_{b}",
                        (f"aas{a}-sm{s}-blob{b}-" + "B" * 160).encode(),
                    )
                )
            # 2 top-level MLPs
            for m in range(2):
                elements.append(
                    make_mlp(f"TopMLP{s}_{m}", f"aas{a} sm{s} mlp{m} " + "t" * 80)
                )
            # 1 top-level range
            elements.append(make_range(f"TopRange{s}", s, s + 1000))
            # 2 nested collection trees for more volume
            for c in range(2):
                elements.append(
                    _build_mixed_collection(1, 4, f"A{a}S{s}_C{c}_L1")
                )
            all_submodels.append(
                make_submodel(sm_id, f"MixedSubmodel_A{a}_S{s}", elements)
            )
        aas = make_aas(
            f"urn:benchmark:aas:mixed:{a}",
            f"MixedAAS{a}",
            f"urn:benchmark:asset:mixed:{a}",
            sm_ids,
        )
        all_shells.append(aas)
    return make_environment(all_shells, all_submodels)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DATASETS = {
    "wide": build_wide,
    "deep": build_deep,
    "mixed": build_mixed,
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic AAS v3.0 benchmark datasets."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the JSON files into.",
    )
    parser.add_argument(
        "--only",
        choices=list(DATASETS.keys()),
        default=None,
        help="Generate only this dataset (useful for quick smoke tests).",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    targets = {args.only: DATASETS[args.only]} if args.only else DATASETS

    for name, builder in targets.items():
        path = os.path.join(args.output_dir, f"{name}.json")
        print(f"Generating {name}.json ...", end=" ", flush=True)
        env = builder()
        with open(path, "w") as f:
            json.dump(env, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"done ({size_mb:.1f} MB)")

    print("All datasets written to", args.output_dir)


if __name__ == "__main__":
    main()
