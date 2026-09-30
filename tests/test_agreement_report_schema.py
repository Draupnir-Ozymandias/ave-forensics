import copy
import json
from pathlib import Path

import pytest

from verification.report_schema import (
    AGREEMENT_REPORT_SCHEMA_PATH,
    AGREEMENT_REPORT_SCHEMA_SHA256,
    AgreementReportSchemaError,
    load_agreement_report_schema,
    validate_agreement_report,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "demo-agreement-reports"
CANONICAL_REPORT_PATHS = sorted(FIXTURE_ROOT.glob("*-agreement-report.json"))


def test_pinned_schema_has_platform_hash():
    schema = load_agreement_report_schema()

    assert AGREEMENT_REPORT_SCHEMA_PATH.name == (
        "ave-demo-agreement-report-0.1.0.schema.json"
    )
    assert AGREEMENT_REPORT_SCHEMA_SHA256 == (
        "f4a2ce98dc407b0aa7f40dcfc636de98e6c8d498feda84ecec9e5b3a36292315"
    )
    assert schema["properties"]["agreement_report_version"]["const"] == "0.1.0"


def test_rejects_pinned_schema_drift(tmp_path):
    drifted_path = tmp_path / AGREEMENT_REPORT_SCHEMA_PATH.name
    schema = json.loads(AGREEMENT_REPORT_SCHEMA_PATH.read_text())
    schema["title"] = "drifted contract"
    drifted_path.write_text(json.dumps(schema))

    with pytest.raises(AgreementReportSchemaError, match="SHA-256 drift"):
        load_agreement_report_schema(drifted_path)


def test_rejects_report_contract_drift():
    report = json.loads(
        (FIXTURE_ROOT / "ave-demo-001-agreement-report.json").read_text()
    )
    drifted_report = copy.deepcopy(report)
    drifted_report["agreement_report_version"] = "0.2.0"

    with pytest.raises(AgreementReportSchemaError, match="violates pinned schema"):
        validate_agreement_report(drifted_report)


def test_all_five_canonical_report_snapshots_are_pinned():
    assert [path.name for path in CANONICAL_REPORT_PATHS] == [
        f"ave-demo-{index:03d}-agreement-report.json" for index in range(1, 6)
    ]


@pytest.mark.parametrize("report_path", CANONICAL_REPORT_PATHS)
def test_canonical_portfolio_report_snapshot_validates(report_path):
    validate_agreement_report(json.loads(report_path.read_text()))
