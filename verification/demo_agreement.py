"""Field-level comparison for persisted AVE demo observations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator


AGREEMENT_REPORT_VERSION = "0.1.0"
RESULT_STATES = {
    "agree",
    "disagree",
    "unsupported",
    "not_evaluated",
    "invalid_declaration",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scope_matches(claim_scope: dict[str, Any], observed_scope: dict[str, Any]) -> bool:
    if claim_scope["modality"] != observed_scope["modality"]:
        return False
    if set(claim_scope["regions"]) != set(observed_scope["regions"]):
        return False
    claim_channels = set(claim_scope["channels"])
    observed_channels = set(observed_scope["channels"])
    if not observed_channels.issubset(claim_channels):
        return False
    claim_time = claim_scope["time_range_seconds"]
    observed_time = observed_scope["time_range_seconds"]
    if claim_time is None:
        return True
    if observed_time is None:
        return False
    return (
        abs(float(claim_time["start"]) - float(observed_time["start"])) <= 1e-9
        and abs(float(claim_time["end"]) - float(observed_time["end"])) <= 1e-9
    )


def _combine_observations(
    claim: dict[str, Any], candidates: list[dict[str, Any]]
) -> dict[str, Any] | None:
    claim_channels = set(claim["scope"]["channels"])
    exact = [
        item
        for item in candidates
        if set(item["scope"]["channels"]) == claim_channels
    ]
    if exact:
        target = claim.get("target", {})
        if target.get("kind") == "scalar" and len(exact) > 1:
            scalar_candidates = [
                item
                for item in exact
                if item.get("observed", {}).get("kind") == "scalar"
            ]
            if scalar_candidates:
                target_value = float(target["value"])
                return min(
                    scalar_candidates,
                    key=lambda item: abs(float(item["observed"]["value"]) - target_value),
                )
        return exact[0]
    if not claim_channels or not candidates:
        return None
    covered = set().union(*(set(item["scope"]["channels"]) for item in candidates))
    if covered != claim_channels:
        return None
    first = candidates[0]["observed"]
    if any(item["observed"] != first for item in candidates[1:]):
        return None
    return {
        "evidence_type": claim["evidence_type"],
        "metric": claim["metric"],
        "unit": claim["unit"],
        "scope": claim["scope"],
        "observed": first,
        "coverage_fraction": min(item["coverage_fraction"] for item in candidates),
        "confidence": min(item["confidence"] for item in candidates),
        "evidence_ids": sorted(
            {evidence_id for item in candidates for evidence_id in item["evidence_ids"]}
        ),
        "limitations": [
            limitation
            for item in candidates
            for limitation in item.get("limitations", [])
        ],
    }


def _find_observation(
    claim: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any] | None:
    candidates = [
        item
        for item in observation["metrics"]
        if item["evidence_type"] == claim["evidence_type"]
        and item["metric"] == claim["metric"]
        and item["unit"] == claim["unit"]
        and _scope_matches(claim["scope"], item["scope"])
    ]
    return _combine_observations(claim, candidates)


def _claim_validity_error(claim: dict[str, Any]) -> str | None:
    target_kind = claim["target"]["kind"]
    comparison = claim["tolerance"]["comparison"]
    allowed = {
        "exact": {"category", "boolean", "scalar"},
        "absolute": {"scalar"},
        "relative": {"scalar"},
        "absolute_or_relative": {"scalar"},
        "interval_containment": {"interval"},
        "curve_fit": {"linear_curve"},
    }
    if target_kind not in allowed.get(comparison, set()):
        return f"{comparison} is incompatible with {target_kind} target"
    if target_kind == "interval" and claim["target"]["minimum"] > claim["target"]["maximum"]:
        return "interval target minimum exceeds maximum"
    time_range = claim["scope"]["time_range_seconds"]
    if time_range is not None and time_range["end"] <= time_range["start"]:
        return "claim scope has a non-positive time range"
    return None


def _support_failure(
    tolerance: dict[str, Any], observed: dict[str, Any]
) -> str | None:
    minimum_coverage = tolerance.get("minimum_coverage_fraction")
    if minimum_coverage is not None and observed["coverage_fraction"] < minimum_coverage:
        return (
            f"coverage {observed['coverage_fraction']:.6f} is below "
            f"minimum {minimum_coverage:.6f}"
        )
    minimum_confidence = tolerance.get("minimum_confidence")
    if minimum_confidence is not None and observed["confidence"] < minimum_confidence:
        return (
            f"confidence {observed['confidence']:.6f} is below "
            f"minimum {minimum_confidence:.6f}"
        )
    return None


def _compare_curve(
    target: dict[str, Any], observed: dict[str, Any], tolerance: dict[str, Any]
) -> tuple[bool, dict[str, float], str]:
    start_target = target["start"]
    end_target = target["end"]
    start_observed = observed["start"]
    end_observed = observed["end"]
    target_duration = end_target["time_seconds"] - start_target["time_seconds"]
    if target_duration <= 0:
        return False, {}, "target curve has non-positive duration"

    def expected_at(time_seconds: float) -> float:
        fraction = (time_seconds - start_target["time_seconds"]) / target_duration
        return start_target["value"] + fraction * (
            end_target["value"] - start_target["value"]
        )

    points = observed.get("point_observations") or [start_observed, end_observed]
    errors = [abs(point["value"] - expected_at(point["time_seconds"])) for point in points]
    max_point_error = max(errors) if errors else float("inf")
    rmse = float(np.sqrt(np.mean(np.square(errors)))) if errors else float("inf")
    time_error = max(
        abs(start_observed["time_seconds"] - start_target["time_seconds"]),
        abs(end_observed["time_seconds"] - end_target["time_seconds"]),
    )
    calculated = {
        "max_point_error": round(max_point_error, 9),
        "rmse": round(rmse, 9),
        "time_error_seconds": round(time_error, 9),
    }
    passed = (
        max_point_error <= tolerance["max_point_error"]
        and rmse <= tolerance["max_rmse"]
        and time_error <= tolerance["max_time_error_seconds"]
    )
    return passed, calculated, (
        "Curve error and timing conditions passed."
        if passed
        else "One or more curve error or timing conditions failed."
    )


def _compare_value(
    target: dict[str, Any], observed: dict[str, Any], tolerance: dict[str, Any]
) -> tuple[bool, dict[str, Any], str]:
    comparison = tolerance["comparison"]
    if comparison == "curve_fit":
        if observed.get("kind") != "linear_curve":
            return False, {}, "Observed value is not a linear curve."
        return _compare_curve(target, observed, tolerance)
    if comparison == "exact":
        passed = observed.get("value") == target.get("value")
        return passed, {"exact_match": passed}, (
            "Exact comparison passed." if passed else "Exact comparison failed."
        )
    if observed.get("kind") != "scalar":
        return False, {}, "Observed value is not scalar."
    value = float(observed["value"])
    if target["kind"] == "interval":
        lower = float(target["minimum"]) - tolerance["boundary_margin"]
        upper = float(target["maximum"]) + tolerance["boundary_margin"]
        passed = lower <= value <= upper
        return passed, {"expanded_minimum": lower, "expanded_maximum": upper}, (
            "Interval containment passed." if passed else "Interval containment failed."
        )
    target_value = float(target["value"])
    absolute_error = abs(value - target_value)
    errors: dict[str, Any] = {"absolute_error": round(absolute_error, 12)}
    if comparison == "absolute":
        passed = absolute_error <= tolerance["max_absolute_error"]
    else:
        relative_error = absolute_error / max(
            abs(target_value), tolerance["relative_floor"]
        )
        errors["relative_error_fraction"] = round(relative_error, 12)
        if comparison == "relative":
            passed = relative_error <= tolerance["max_relative_error_fraction"]
        else:
            passed = (
                absolute_error <= tolerance["max_absolute_error"]
                or relative_error <= tolerance["max_relative_error_fraction"]
            )
    return passed, errors, (
        "Numeric tolerance passed." if passed else "Numeric tolerance failed."
    )


def _claim_result(
    claim: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    base = {
        "claim_id": claim["claim_id"],
        "required": claim["required"],
        "state": None,
        "observed": None,
        "errors": {},
        "coverage_fraction": None,
        "confidence": None,
        "evidence_ids": [],
        "reason": "",
        "limitations": [],
    }
    validity_error = _claim_validity_error(claim)
    if validity_error:
        base.update(state="invalid_declaration", reason=validity_error)
        return base
    observed = _find_observation(claim, observation)
    if observed is None:
        not_evaluated = next(
            (
                item
                for item in observation["not_evaluated"]
                if item["metric"] == claim["metric"]
            ),
            None,
        )
        if not_evaluated:
            base.update(state="not_evaluated", reason=not_evaluated["reason"])
        else:
            base.update(
                state="unsupported",
                reason="No compatible evidence type, metric, unit, and scope were observed.",
            )
        return base
    base.update(
        observed=observed["observed"],
        coverage_fraction=observed["coverage_fraction"],
        confidence=observed["confidence"],
        evidence_ids=observed["evidence_ids"],
        limitations=observed.get("limitations", []),
    )
    support_failure = _support_failure(claim["tolerance"], observed)
    if support_failure:
        base.update(state="unsupported", reason=support_failure)
        return base
    passed, errors, reason = _compare_value(
        claim["target"], observed["observed"], claim["tolerance"]
    )
    base.update(
        state="agree" if passed else "disagree",
        errors=errors,
        reason=reason,
    )
    return base


def _demo_label(results: list[dict[str, Any]]) -> str:
    required_states = [item["state"] for item in results if item["required"]]
    if required_states and all(state == "agree" for state in required_states):
        return "verified"
    if (
        "agree" in required_states
        and not ({"disagree", "invalid_declaration"} & set(required_states))
    ):
        return "partially_verified"
    return "exploratory"


def compare_demo(
    declaration_path: Path,
    observation_path: Path,
    schema_path: Path,
) -> dict[str, Any]:
    declaration_path = declaration_path.resolve()
    observation_path = observation_path.resolve()
    schema_path = schema_path.resolve()
    declaration = json.loads(declaration_path.read_text())
    observation = json.loads(observation_path.read_text())
    declaration_hash = _sha256(declaration_path)
    observation_hash = _sha256(observation_path)
    schema = json.loads(schema_path.read_text())
    schema_errors = sorted(
        Draft202012Validator(schema).iter_errors(declaration),
        key=lambda error: list(error.path),
    )
    global_errors = [
        f"{'.'.join(str(item) for item in error.path) or '<root>'}: {error.message}"
        for error in schema_errors
    ]
    if declaration_hash != observation["expected_declaration_sha256"]:
        global_errors.append("declaration SHA-256 does not match verification request")
    if declaration.get("demo_id") != observation["demo_id"]:
        global_errors.append("declaration demo_id does not match observation")
    if declaration.get("demo_version") != observation["demo_version"]:
        global_errors.append("declaration demo_version does not match observation")

    claims = declaration.get("claims", []) if isinstance(declaration, dict) else []
    claim_ids = [claim.get("claim_id") for claim in claims if isinstance(claim, dict)]
    if len(claim_ids) != len(set(claim_ids)):
        global_errors.append("claim_id values are not unique")

    if global_errors:
        results = [
            {
                "claim_id": claim.get("claim_id", "unknown"),
                "required": bool(claim.get("required", True)),
                "state": "invalid_declaration",
                "observed": None,
                "errors": {},
                "coverage_fraction": None,
                "confidence": None,
                "evidence_ids": [],
                "reason": "; ".join(global_errors),
                "limitations": [],
            }
            for claim in claims
        ]
    else:
        results = [_claim_result(claim, observation) for claim in claims]
    if any(item["state"] not in RESULT_STATES for item in results):
        raise ValueError("agreement report contains an unknown result state")

    provenance = observation["run_provenance"]
    return {
        "agreement_report_version": AGREEMENT_REPORT_VERSION,
        "declaration_contract": "ave-demo-declaration@0.1.0",
        "demo_id": observation["demo_id"],
        "demo_version": observation["demo_version"],
        "declaration_id": observation["declaration_id"],
        "declaration_sha256": declaration_hash,
        "declaration_schema_sha256": _sha256(schema_path),
        "observation_sha256": observation_hash,
        "artifact_sha256": observation["artifact"]["sha256"],
        "forensics": {
            "version": provenance["toolkit"]["version"],
            "source_tree_sha256": provenance["toolkit"]["source_tree_sha256"],
            "git": provenance["git"],
            "run_id": provenance["run_id"],
            "analysis_configuration": provenance["analysis_configuration"],
        },
        "ordering_attestation": observation["ordering_attestation"],
        "declaration_validation_errors": global_errors,
        "claim_results": results,
        "evidence_label": _demo_label(results),
        "limitations": [
            "Agreement applies only to compared engineering fields.",
            "No evidence label establishes neurological entrainment, efficacy, therapeutic benefit, or exposure safety.",
        ],
    }
