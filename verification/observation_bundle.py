"""Bundle already-persisted blind observations for one demo comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.hashing import sha256_file
from provenance.run import build_run_provenance


class ObservationBundleError(ValueError):
    """Raised when persisted observations cannot be safely combined."""


def _unique(items: list[Any]) -> list[Any]:
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def bundle_observations(
    paths: list[Path],
    *,
    project_root: Path,
) -> dict[str, Any]:
    if len(paths) < 2:
        raise ObservationBundleError("at least two persisted observations are required")
    resolved = [path.resolve() for path in paths]
    observations = [json.loads(path.read_text()) for path in resolved]
    primary = observations[0]
    identity_fields = (
        "demo_id",
        "demo_version",
        "declaration_id",
        "expected_declaration_sha256",
    )
    for observation in observations:
        for field in identity_fields:
            if observation.get(field) != primary.get(field):
                raise ObservationBundleError(f"observation {field} values do not match")
        attestation = observation.get("ordering_attestation", {})
        if set(attestation.values()) != {False}:
            raise ObservationBundleError("every observation must retain blind ordering")
        artifact_path = Path(observation["artifact"]["path"])
        if not artifact_path.exists():
            raise ObservationBundleError("observation artifact is unavailable")
        if sha256_file(artifact_path) != observation["artifact"]["sha256"]:
            raise ObservationBundleError("observation artifact SHA-256 does not match")

    metrics = _unique(
        [metric for observation in observations for metric in observation["metrics"]]
    )
    observed_names = {item["metric"] for item in metrics}
    not_evaluated = _unique(
        [
            item
            for observation in observations
            for item in observation["not_evaluated"]
            if item["metric"] not in observed_names
        ]
    )
    component_records = [
        {
            "observation_path": str(path),
            "observation_sha256": sha256_file(path),
            "verification_request_sha256": observation[
                "verification_request_sha256"
            ],
            "artifact": observation["artifact"],
            "run_id": observation["run_provenance"]["run_id"],
        }
        for path, observation in zip(resolved, observations)
    ]
    configuration = {
        "configuration_schema_version": "demo-observation-bundle-0.1.0",
        "component_observations": [
            {
                "observation_sha256": record["observation_sha256"],
                "run_id": observation["run_provenance"]["run_id"],
                "analysis_configuration": observation["run_provenance"][
                    "analysis_configuration"
                ],
            }
            for record, observation in zip(component_records, observations)
        ],
    }
    provenance = build_run_provenance(
        input_path=Path(primary["artifact"]["path"]),
        project_root=project_root,
        analysis_configuration=configuration,
    )
    limitations = _unique(
        [
            *(
                limitation
                for observation in observations
                for limitation in observation.get("limitations", [])
            ),
            "This comparison bundle combines separately persisted blind observations; each evidence object retains its own artifact hash and run provenance.",
        ]
    )
    return {
        "observation_schema_version": "0.2.0",
        "demo_id": primary["demo_id"],
        "demo_version": primary["demo_version"],
        "declaration_id": primary["declaration_id"],
        "verification_request_sha256": primary["verification_request_sha256"],
        "expected_declaration_sha256": primary["expected_declaration_sha256"],
        "artifact": primary["artifact"],
        "supporting_artifacts": [item["artifact"] for item in component_records[1:]],
        "component_observations": component_records,
        "ordering_attestation": {
            "declaration_loaded_during_detection": False,
            "targets_loaded_during_detection": False,
            "tolerances_loaded_during_detection": False,
        },
        "run_provenance": provenance,
        "metrics": metrics,
        "not_evaluated": not_evaluated,
        "evidence_ids": sorted(
            {
                evidence_id
                for observation in observations
                for evidence_id in observation["evidence_ids"]
            }
        ),
        "limitations": limitations,
    }
