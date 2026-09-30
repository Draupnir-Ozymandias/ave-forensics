"""Pinned validation for AVE demo agreement reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


AGREEMENT_REPORT_SCHEMA_VERSION = "0.1.0"
AGREEMENT_REPORT_SCHEMA_SHA256 = (
    "f4a2ce98dc407b0aa7f40dcfc636de98e6c8d498feda84ecec9e5b3a36292315"
)
AGREEMENT_REPORT_SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "ave-demo-agreement-report-0.1.0.schema.json"
)


class AgreementReportSchemaError(ValueError):
    """Raised when the pinned contract drifts or a report violates it."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_agreement_report_schema(
    schema_path: Path = AGREEMENT_REPORT_SCHEMA_PATH,
) -> dict[str, Any]:
    path = schema_path.resolve()
    actual_hash = _sha256(path)
    if actual_hash != AGREEMENT_REPORT_SCHEMA_SHA256:
        raise AgreementReportSchemaError(
            "agreement-report schema SHA-256 drift: "
            f"expected {AGREEMENT_REPORT_SCHEMA_SHA256}, observed {actual_hash}"
        )
    schema = json.loads(path.read_text())
    Draft202012Validator.check_schema(schema)
    return schema


def validate_agreement_report(
    report: dict[str, Any],
    *,
    schema_path: Path = AGREEMENT_REPORT_SCHEMA_PATH,
) -> None:
    schema = load_agreement_report_schema(schema_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(report),
        key=lambda error: list(error.absolute_path),
    )
    if not errors:
        return
    details = "; ".join(
        f"{'.'.join(str(item) for item in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    )
    raise AgreementReportSchemaError(
        f"agreement report violates pinned schema {AGREEMENT_REPORT_SCHEMA_VERSION}: "
        f"{details}"
    )
