"""Observe demo artifacts first; compare declarations only in a later phase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reports.evidence_export import export_evidence_json
from verification.demo_observation import observe_demo_request
from verification.demo_agreement import compare_demo
from verification.observation_bundle import bundle_observations


def observe(arguments: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parent
    output_dir = Path(arguments.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    observation, evidence = observe_demo_request(
        Path(arguments.verification_request), project_root=project_root
    )
    observation_path = output_dir / "demo-observation.json"
    observation_path.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n")
    export_evidence_json(
        evidence,
        str(output_dir / "ave-evidence.json"),
        run_metadata={
            "demo_id": observation["demo_id"],
            "demo_version": observation["demo_version"],
            "artifact_sha256": observation["artifact"]["sha256"],
        },
        run_provenance=observation["run_provenance"],
    )
    print(
        f"Persisted {observation['demo_id']} blind observation: "
        f"{len(observation['metrics'])} metrics, "
        f"{len(observation['not_evaluated'])} not evaluated"
    )


def compare(arguments: argparse.Namespace) -> None:
    report = compare_demo(
        Path(arguments.declaration),
        Path(arguments.observation),
        Path(arguments.schema),
    )
    output_path = Path(arguments.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    counts = {}
    for item in report["claim_results"]:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    print(
        f"{report['demo_id']}: {report['evidence_label']} "
        f"({', '.join(f'{key}={value}' for key, value in sorted(counts.items()))})"
    )


def bundle(arguments: argparse.Namespace) -> None:
    project_root = Path(__file__).resolve().parent
    observation = bundle_observations(
        [Path(arguments.primary), *(Path(item) for item in arguments.additional)],
        project_root=project_root,
    )
    output_path = Path(arguments.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n")
    print(
        f"Bundled {len(observation['component_observations'])} persisted observations: "
        f"{len(observation['metrics'])} metrics, "
        f"{len(observation['not_evaluated'])} not evaluated"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    observe_parser = subparsers.add_parser("observe")
    observe_parser.add_argument("verification_request")
    observe_parser.add_argument("--output-dir", required=True)
    observe_parser.set_defaults(handler=observe)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("declaration")
    compare_parser.add_argument("observation")
    compare_parser.add_argument("--schema", required=True)
    compare_parser.add_argument("--output", required=True)
    compare_parser.set_defaults(handler=compare)
    bundle_parser = subparsers.add_parser("bundle")
    bundle_parser.add_argument("primary")
    bundle_parser.add_argument("additional", nargs="+")
    bundle_parser.add_argument("--output", required=True)
    bundle_parser.set_defaults(handler=bundle)
    arguments = parser.parse_args()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
