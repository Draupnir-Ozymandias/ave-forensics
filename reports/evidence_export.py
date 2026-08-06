import json
from typing import Any

from evidence.schema import SCHEMA_VERSION, validate_evidence_object
from provenance.run import validate_run_provenance


def export_evidence_json(
    evidence_objects: list[dict[str, Any]],
    output_path: str = "ave_evidence.json",
    run_metadata: dict[str, Any] | None = None,
    run_provenance: dict[str, Any] | None = None,
) -> None:
    for evidence in evidence_objects:
        validate_evidence_object(evidence)
    if run_provenance is not None:
        validate_run_provenance(run_provenance)

    document = {
        "schema_version": SCHEMA_VERSION,
        "evidence_count": len(evidence_objects),
        "run_metadata": run_metadata or {},
        "run_provenance": run_provenance,
        "evidence": evidence_objects,
    }

    with open(output_path, "w") as output_file:
        json.dump(document, output_file, indent=2, sort_keys=True)
        output_file.write("\n")
