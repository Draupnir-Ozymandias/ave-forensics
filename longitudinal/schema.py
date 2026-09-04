from __future__ import annotations

import hashlib
import json
import re
from typing import Any


SNAPSHOT_SCHEMA_VERSION = "1.0.0"
COMPARISON_SCHEMA_VERSION = "1.0.0"
SNAPSHOT_ID_PATTERN = re.compile(r"^ave_snapshot_[0-9a-f]{16}$")


def document_sha256(document: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_snapshot(document: dict[str, Any]) -> None:
    if document.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("unsupported snapshot_schema_version")
    snapshot_id = document.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_PATTERN.match(snapshot_id):
        raise ValueError("invalid snapshot_id")
    core = {
        key: value
        for key, value in document.items()
        if key not in {"snapshot_id", "captured_at"}
    }
    expected = f"ave_snapshot_{document_sha256(core)[:16]}"
    if snapshot_id != expected:
        raise ValueError("snapshot_id does not match snapshot content")
    recordings = document.get("recordings")
    if not isinstance(recordings, list):
        raise ValueError("recordings must be a list")
    digests = [item.get("input_sha256") for item in recordings]
    if len(digests) != len(set(digests)):
        raise ValueError("snapshot inputs must be unique")
    if document.get("summary", {}).get("unique_input_count") != len(recordings):
        raise ValueError("unique_input_count does not match recordings")


def validate_comparison(document: dict[str, Any]) -> None:
    if document.get("comparison_schema_version") != COMPARISON_SCHEMA_VERSION:
        raise ValueError("unsupported comparison_schema_version")
    for key in ("baseline_snapshot_id", "current_snapshot_id"):
        value = document.get(key)
        if not isinstance(value, str) or not SNAPSHOT_ID_PATTERN.match(value):
            raise ValueError(f"invalid {key}")
    if not isinstance(document.get("family_transitions"), list):
        raise ValueError("family_transitions must be a list")
