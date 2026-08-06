from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
AVE_SCHEMA_SHA256 = "7edee601724e13ceb2308482a9f1135acbdb850360de149f1ac009374f26ce18"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_pinned_ave_schema_has_not_drifted() -> None:
    schema_path = CONTRACTS / "ave-evidence-object-1.0.0.schema.json"
    digest = hashlib.sha256(schema_path.read_bytes()).hexdigest()
    assert digest == AVE_SCHEMA_SHA256
    assert load_json(schema_path)["properties"]["schema_version"]["const"] == "1.0.0"


def test_minimal_export_validates() -> None:
    protocol_schema = load_json(CONTRACTS / "lumenate-protocol-export.schema.json")
    ave_schema = load_json(CONTRACTS / "ave-evidence-object-1.0.0.schema.json")
    fixture = load_json(CONTRACTS / "examples" / "minimal-export.json")

    resolved_ave_uri = (
        "https://example.invalid/lumenate-nova/contracts/"
        "ave-evidence-object-1.0.0.schema.json"
    )
    registry = Registry().with_resource(
        resolved_ave_uri,
        Resource.from_contents(ave_schema),
    )
    validator = jsonschema.validators.Draft202012Validator(protocol_schema, registry=registry)
    validator.validate(fixture)


def test_segment_ranges_are_ordered() -> None:
    fixture = load_json(CONTRACTS / "examples" / "minimal-export.json")
    assert all(segment["end_ms"] >= segment["start_ms"] for segment in fixture["segments"])
