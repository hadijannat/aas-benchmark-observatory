#!/usr/bin/env python3
"""Generate deterministic AAS v3.0 Environment datasets for benchmarking.

Default mode produces three JSON dataset files:
  wide.json  -- 1 AAS, 1 Submodel, 100,000 Property elements        (~30 MB)
  deep.json  -- 1 AAS, 5 Submodels, nested collections 15 levels     (~200 KB)
  mixed.json -- 5 AAS, 20 Submodels, varied element types, 4 levels  (~500 KB)

Additional modes:
  --xml                Generate XML equivalents (wide.xml, deep.xml, mixed.xml)
  --validation-targets Generate targeted validation datasets (val_regex, val_cardinality, val_referential)
  --aasx               Generate AASX packages (aasx_small.aasx, aasx_medium.aasx)

Usage:
    python3 datasets/generate.py --output-dir <dir>
    python3 datasets/generate.py --output-dir <dir> --xml
    python3 datasets/generate.py --output-dir <dir> --validation-targets
    python3 datasets/generate.py --output-dir <dir> --aasx
    python3 datasets/generate.py --output-dir <dir> --only mixed
"""

import argparse
import base64
import json
import os
import xml.etree.ElementTree as ET
import zipfile

AAS_NS = "https://admin-shell.io/aas/3/0"

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


def make_reference_element(id_short, ref_type, ref_value):
    """Create an AAS v3.0 ReferenceElement."""
    return {
        "modelType": "ReferenceElement",
        "idShort": id_short,
        "value": {
            "type": "ModelReference",
            "keys": [{"type": ref_type, "value": ref_value}],
        },
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
    }


# ---------------------------------------------------------------------------
# Dataset builders (JSON)
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


DATASETS = {
    "wide": build_wide,
    "deep": build_deep,
    "mixed": build_mixed,
}


# ---------------------------------------------------------------------------
# XML generation (SRQ-1)
# ---------------------------------------------------------------------------


def _add_xml_text_child(parent, tag, text):
    """Add a child element with text content."""
    child = ET.SubElement(parent, tag)
    child.text = str(text)
    return child


def _element_to_xml(parent, elem):
    """Convert a JSON AAS element dict to XML sub-elements under *parent*."""
    model_type = elem.get("modelType", "")

    if model_type == "Property":
        prop_el = ET.SubElement(parent, "property")
        _add_xml_text_child(prop_el, "idShort", elem["idShort"])
        _add_xml_text_child(prop_el, "valueType", elem.get("valueType", "xs:string"))
        if elem.get("value") is not None:
            _add_xml_text_child(prop_el, "value", elem["value"])
        if elem.get("semanticId"):
            _semantic_id_to_xml(prop_el, elem["semanticId"])

    elif model_type == "SubmodelElementCollection":
        col_el = ET.SubElement(parent, "submodelElementCollection")
        _add_xml_text_child(col_el, "idShort", elem["idShort"])
        value_el = ET.SubElement(col_el, "value")
        for child in elem.get("value", []):
            _element_to_xml(value_el, child)

    elif model_type == "Blob":
        blob_el = ET.SubElement(parent, "blob")
        _add_xml_text_child(blob_el, "idShort", elem["idShort"])
        _add_xml_text_child(blob_el, "contentType", elem.get("contentType", "application/octet-stream"))
        if elem.get("value") is not None:
            _add_xml_text_child(blob_el, "value", elem["value"])

    elif model_type == "MultiLanguageProperty":
        mlp_el = ET.SubElement(parent, "multiLanguageProperty")
        _add_xml_text_child(mlp_el, "idShort", elem["idShort"])
        value_el = ET.SubElement(mlp_el, "value")
        for lang_entry in elem.get("value", []):
            ls_el = ET.SubElement(value_el, "langStringTextType")
            _add_xml_text_child(ls_el, "language", lang_entry["language"])
            _add_xml_text_child(ls_el, "text", lang_entry["text"])

    elif model_type == "Range":
        range_el = ET.SubElement(parent, "range")
        _add_xml_text_child(range_el, "idShort", elem["idShort"])
        _add_xml_text_child(range_el, "valueType", elem.get("valueType", "xs:int"))
        if elem.get("min") is not None:
            _add_xml_text_child(range_el, "min", elem["min"])
        if elem.get("max") is not None:
            _add_xml_text_child(range_el, "max", elem["max"])

    elif model_type == "ReferenceElement":
        ref_el = ET.SubElement(parent, "referenceElement")
        _add_xml_text_child(ref_el, "idShort", elem["idShort"])
        if elem.get("value"):
            _reference_to_xml(ref_el, "value", elem["value"])


def _semantic_id_to_xml(parent, semantic_id):
    """Convert a semanticId reference to XML."""
    sem_el = ET.SubElement(parent, "semanticId")
    _add_xml_text_child(sem_el, "type", semantic_id.get("type", "ExternalReference"))
    keys_el = ET.SubElement(sem_el, "keys")
    for key in semantic_id.get("keys", []):
        key_el = ET.SubElement(keys_el, "key")
        _add_xml_text_child(key_el, "type", key["type"])
        _add_xml_text_child(key_el, "value", key["value"])


def _reference_to_xml(parent, tag, ref):
    """Convert a reference dict to XML."""
    ref_el = ET.SubElement(parent, tag)
    _add_xml_text_child(ref_el, "type", ref.get("type", "ModelReference"))
    keys_el = ET.SubElement(ref_el, "keys")
    for key in ref.get("keys", []):
        key_el = ET.SubElement(keys_el, "key")
        _add_xml_text_child(key_el, "type", key["type"])
        _add_xml_text_child(key_el, "value", key["value"])


def env_to_xml(env_dict):
    """Convert an AAS Environment dict to an XML ElementTree."""
    root = ET.Element("environment")
    root.set("xmlns", AAS_NS)

    # Asset Administration Shells
    shells_el = ET.SubElement(root, "assetAdministrationShells")
    for shell in env_dict.get("assetAdministrationShells", []):
        aas_el = ET.SubElement(shells_el, "assetAdministrationShell")
        _add_xml_text_child(aas_el, "id", shell["id"])
        _add_xml_text_child(aas_el, "idShort", shell.get("idShort", ""))

        # Asset information
        asset_info = shell.get("assetInformation", {})
        ai_el = ET.SubElement(aas_el, "assetInformation")
        _add_xml_text_child(ai_el, "assetKind", asset_info.get("assetKind", "Instance"))
        if asset_info.get("globalAssetId"):
            _add_xml_text_child(ai_el, "globalAssetId", asset_info["globalAssetId"])

        # Submodel references
        if shell.get("submodels"):
            sms_el = ET.SubElement(aas_el, "submodels")
            for ref in shell["submodels"]:
                _reference_to_xml(sms_el, "reference", ref)

    # Submodels
    submodels_el = ET.SubElement(root, "submodels")
    for sm in env_dict.get("submodels", []):
        sm_el = ET.SubElement(submodels_el, "submodel")
        _add_xml_text_child(sm_el, "id", sm["id"])
        _add_xml_text_child(sm_el, "idShort", sm.get("idShort", ""))

        if sm.get("semanticId"):
            _semantic_id_to_xml(sm_el, sm["semanticId"])

        elements_el = ET.SubElement(sm_el, "submodelElements")
        for elem in sm.get("submodelElements", []):
            _element_to_xml(elements_el, elem)

    return ET.ElementTree(root)


def generate_xml_datasets(output_dir):
    """Generate XML versions of the standard datasets."""
    for name, builder in DATASETS.items():
        path = os.path.join(output_dir, f"{name}.xml")
        print(f"Generating {name}.xml ...", end=" ", flush=True)
        env = builder()
        tree = env_to_xml(env)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="unicode", xml_declaration=True)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"done ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Targeted validation datasets (SRQ-3)
# ---------------------------------------------------------------------------


def build_val_regex():
    """10,000 elements with diverse identifier formats to stress regex matching."""
    elements = []
    patterns = [
        "urn:example:aas:benchmark:id:{i:06d}",
        "https://example.org/aas/ids/{i:06d}",
        "0173-1#01-ABD123#{i:03d}",
        "urn:ietf:rfc:2141:benchmark-{i:06d}",
        "https://admin-shell.io/zvei/nameplate/1/0/ContactInformations/id{i:06d}",
    ]
    for i in range(10_000):
        pattern = patterns[i % len(patterns)]
        id_val = pattern.format(i=i)
        elements.append(make_property(
            f"RegexProp{i:06d}",
            id_val,
        ))

    sm_id = "urn:benchmark:submodel:val_regex:0"
    submodel = make_submodel(sm_id, "ValRegexSubmodel", elements)
    aas = make_aas(
        "urn:benchmark:aas:val_regex:0",
        "ValRegexAAS",
        "urn:benchmark:asset:val_regex:0",
        [sm_id],
    )
    return make_environment([aas], [submodel])


def build_val_cardinality():
    """Edge-case multiplicities: empty submodels, max-children collections."""
    submodels = []
    sm_ids = []

    # 5 empty submodels (0-element edge case)
    for i in range(5):
        sm_id = f"urn:benchmark:submodel:val_card:empty:{i}"
        sm_ids.append(sm_id)
        submodels.append(make_submodel(sm_id, f"EmptySubmodel{i}", []))

    # 3 max-children collections (500 elements each)
    for i in range(3):
        sm_id = f"urn:benchmark:submodel:val_card:maxchild:{i}"
        sm_ids.append(sm_id)
        children = [
            make_property(f"CardProp{i}_{j:04d}", f"card-val-{j}")
            for j in range(500)
        ]
        submodels.append(make_submodel(sm_id, f"MaxChildSubmodel{i}", children))

    # 2 deeply nested single-child chains (30 levels)
    for i in range(2):
        sm_id = f"urn:benchmark:submodel:val_card:chain:{i}"
        sm_ids.append(sm_id)
        inner = make_property(f"ChainLeaf{i}", "leaf-value")
        for d in range(30, 0, -1):
            inner = make_collection(f"Chain{i}_L{d}", [inner])
        submodels.append(make_submodel(sm_id, f"ChainSubmodel{i}", [inner]))

    aas = make_aas(
        "urn:benchmark:aas:val_cardinality:0",
        "ValCardinalityAAS",
        "urn:benchmark:asset:val_cardinality:0",
        sm_ids,
    )
    return make_environment([aas], submodels)


def build_val_referential():
    """5 AAS, 50 submodels, extensive cross-referencing."""
    all_shells = []
    all_submodels = []
    sm_ids_flat = []

    for a in range(5):
        sm_ids = []
        for s in range(10):
            sm_id = f"urn:benchmark:submodel:val_ref:{a}:{s}"
            sm_ids.append(sm_id)
            sm_ids_flat.append(sm_id)

            elements = []
            # Properties with semanticId references
            for p in range(5):
                prop = make_property(f"RefProp{a}_{s}_{p}", f"ref-val-{a}-{s}-{p}")
                prop["semanticId"] = {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": f"urn:benchmark:semantic:{a}:{s}:{p}"}],
                }
                elements.append(prop)

            # ReferenceElements pointing to other submodels
            for r in range(3):
                target_idx = (a * 10 + s + r + 1) % 50
                target_sm_id = f"urn:benchmark:submodel:val_ref:{target_idx // 10}:{target_idx % 10}"
                elements.append(make_reference_element(
                    f"SubmodelRef{a}_{s}_{r}",
                    "Submodel",
                    target_sm_id,
                ))

            all_submodels.append(make_submodel(sm_id, f"RefSubmodel_A{a}_S{s}", elements))

        # derivedFrom reference to previous AAS
        shell = make_aas(
            f"urn:benchmark:aas:val_ref:{a}",
            f"ValRefAAS{a}",
            f"urn:benchmark:asset:val_ref:{a}",
            sm_ids,
        )
        if a > 0:
            shell["derivedFrom"] = {
                "type": "ModelReference",
                "keys": [{"type": "AssetAdministrationShell", "value": f"urn:benchmark:aas:val_ref:{a - 1}"}],
            }
        all_shells.append(shell)

    return make_environment(all_shells, all_submodels)


VALIDATION_DATASETS = {
    "val_regex": build_val_regex,
    "val_cardinality": build_val_cardinality,
    "val_referential": build_val_referential,
}


def generate_validation_datasets(output_dir):
    """Generate targeted validation stress-test datasets."""
    for name, builder in VALIDATION_DATASETS.items():
        path = os.path.join(output_dir, f"{name}.json")
        print(f"Generating {name}.json ...", end=" ", flush=True)
        env = builder()
        with open(path, "w") as f:
            json.dump(env, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"done ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# AASX generation (SRQ-4)
# ---------------------------------------------------------------------------

CONTENT_TYPES_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json"/>
  <Default Extension="bin" ContentType="application/octet-stream"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
</Types>"""

RELS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://www.admin-shell.io/aasx/relationships/aas-spec"
                Target="/aasx/environment.json"/>
</Relationships>"""


def generate_aasx_datasets(output_dir):
    """Generate AASX packages with embedded environment JSON and supplementary files."""
    # aasx_small: mixed.json + 5 synthetic 1KB binary files
    _generate_aasx(
        output_dir,
        "aasx_small",
        build_mixed,
        num_binaries=5,
        binary_size=1024,
    )
    # aasx_medium: wide.json + 20 synthetic 100KB binary files
    _generate_aasx(
        output_dir,
        "aasx_medium",
        build_wide,
        num_binaries=20,
        binary_size=100 * 1024,
    )


def _generate_aasx(output_dir, name, env_builder, num_binaries, binary_size):
    """Create a single AASX package."""
    path = os.path.join(output_dir, f"{name}.aasx")
    print(f"Generating {name}.aasx ...", end=" ", flush=True)

    env = env_builder()
    env_json = json.dumps(env)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("aasx/environment.json", env_json)

        # Deterministic binary supplementary files
        for i in range(num_binaries):
            # Deterministic content: repeating pattern based on index
            chunk = f"binary-payload-{i:04d}-".encode("ascii")
            data = (chunk * ((binary_size // len(chunk)) + 1))[:binary_size]
            zf.writestr(f"aasx/supplementary/binary_{i:04d}.bin", data)

    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"done ({size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Generate deterministic AAS v3.0 benchmark datasets."
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write the dataset files into.",
    )
    parser.add_argument(
        "--only",
        choices=list(DATASETS.keys()),
        default=None,
        help="Generate only this JSON dataset (useful for quick smoke tests).",
    )
    parser.add_argument(
        "--xml",
        action="store_true",
        help="Generate XML equivalents of the standard datasets.",
    )
    parser.add_argument(
        "--validation-targets",
        action="store_true",
        help="Generate targeted validation stress-test datasets.",
    )
    parser.add_argument(
        "--aasx",
        action="store_true",
        help="Generate AASX package datasets.",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # If no special flag is set, generate standard JSON datasets
    if not args.xml and not args.validation_targets and not args.aasx:
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
        return

    if args.xml:
        generate_xml_datasets(args.output_dir)
        print("XML datasets written to", args.output_dir)

    if args.validation_targets:
        generate_validation_datasets(args.output_dir)
        print("Validation datasets written to", args.output_dir)

    if args.aasx:
        generate_aasx_datasets(args.output_dir)
        print("AASX datasets written to", args.output_dir)


if __name__ == "__main__":
    main()
