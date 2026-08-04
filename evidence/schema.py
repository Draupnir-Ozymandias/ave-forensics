from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


SCHEMA_VERSION = "1.0.0"
EVIDENCE_LEVELS = {
    "measurement",
    "detection",
    "association",
    "reconstruction",
    "hypothesis",
}
EVIDENCE_ID_PATTERN = re.compile(r"^ave_[0-9a-f]{16}$")


class EvidenceValidationError(ValueError):
    """Raised when an object violates the AVE evidence contract."""


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvidenceValidationError("evidence values must be finite")
        return value

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    if hasattr(value, "item"):
        return _json_safe(value.item())

    raise EvidenceValidationError(
        f"value of type {type(value).__name__} is not JSON serializable"
    )


def measurement(name: str, value: Any, unit: str) -> dict[str, Any]:
    if not name.strip():
        raise EvidenceValidationError("measurement name cannot be empty")
    if not unit.strip():
        raise EvidenceValidationError("measurement unit cannot be empty")

    return {
        "name": name,
        "value": _json_safe(value),
        "unit": unit,
    }


def _evidence_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"ave_{digest}"


def create_evidence_object(
    *,
    evidence_level: str,
    evidence_type: str,
    source_module: str,
    summary: str,
    measurements: list[dict[str, Any]],
    channels: list[str] | None = None,
    time_range_seconds: dict[str, float] | None = None,
    context: dict[str, Any] | None = None,
    confidence: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    supporting_evidence_ids: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "evidence_level": evidence_level,
        "evidence_type": evidence_type,
        "source_module": source_module,
        "summary": summary,
        "scope": {
            "channels": channels or [],
            "time_range_seconds": time_range_seconds,
        },
        "measurements": measurements,
        "context": context or {},
        "confidence": confidence,
        "provenance": provenance or {},
        "supporting_evidence_ids": supporting_evidence_ids or [],
        "limitations": limitations or [],
    }
    payload = _json_safe(payload)
    validate_evidence_object(payload, require_id=False)
    payload["evidence_id"] = _evidence_id(payload)
    validate_evidence_object(payload)
    return payload


def validate_evidence_object(
    evidence: dict[str, Any],
    *,
    require_id: bool = True,
) -> None:
    required = {
        "schema_version",
        "evidence_level",
        "evidence_type",
        "source_module",
        "summary",
        "scope",
        "measurements",
        "context",
        "confidence",
        "provenance",
        "supporting_evidence_ids",
        "limitations",
    }
    if require_id:
        required.add("evidence_id")

    missing = required - evidence.keys()
    if missing:
        raise EvidenceValidationError(
            f"missing required fields: {', '.join(sorted(missing))}"
        )

    if evidence["schema_version"] != SCHEMA_VERSION:
        raise EvidenceValidationError("unsupported schema_version")
    if evidence["evidence_level"] not in EVIDENCE_LEVELS:
        raise EvidenceValidationError("invalid evidence_level")
    for field in ("evidence_type", "source_module", "summary"):
        if not isinstance(evidence[field], str) or not evidence[field].strip():
            raise EvidenceValidationError(f"{field} must be a non-empty string")

    if require_id and not EVIDENCE_ID_PATTERN.match(evidence["evidence_id"]):
        raise EvidenceValidationError("invalid evidence_id")

    scope = evidence["scope"]
    if not isinstance(scope, dict) or not isinstance(scope.get("channels"), list):
        raise EvidenceValidationError("scope.channels must be a list")
    time_range = scope.get("time_range_seconds")
    if time_range is not None:
        start = time_range.get("start")
        end = time_range.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise EvidenceValidationError("time range must contain numeric start/end")
        if start < 0 or end < start:
            raise EvidenceValidationError("invalid time range")

    measurements = evidence["measurements"]
    if not isinstance(measurements, list) or not measurements:
        raise EvidenceValidationError("measurements must be a non-empty list")
    for item in measurements:
        if set(item) != {"name", "value", "unit"}:
            raise EvidenceValidationError("invalid measurement structure")
        if not item["name"] or not item["unit"]:
            raise EvidenceValidationError("measurement name/unit cannot be empty")

    confidence = evidence["confidence"]
    if confidence is not None:
        score = confidence.get("score")
        method = confidence.get("method")
        if not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
            raise EvidenceValidationError("confidence score must be within 0-1")
        if not isinstance(method, str) or not method.strip():
            raise EvidenceValidationError("confidence method is required")

    for field in ("context", "provenance"):
        if not isinstance(evidence[field], dict):
            raise EvidenceValidationError(f"{field} must be an object")
    for field in ("supporting_evidence_ids", "limitations"):
        if not isinstance(evidence[field], list):
            raise EvidenceValidationError(f"{field} must be a list")

    _json_safe(evidence)
