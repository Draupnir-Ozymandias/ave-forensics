import argparse
import json
from pathlib import Path

from recommendations.graph import (
    aggregate_recommendation_captures,
    extract_recommendation_capture,
    validate_recommendation_capture,
    write_recommendation_capture,
    write_recommendation_graph,
)


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Extract sanitized Brain.fm recommendation observations and build a graph."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Sanitize one or more raw captures.")
    extract.add_argument("captures", type=Path, nargs="+")
    extract.add_argument("--visible-category")
    extract.add_argument("--visible-intent")
    extract.add_argument("--seed-track-id")
    extract.add_argument("--captured-at")
    extract.add_argument(
        "--context-method",
        default="not_recorded",
        choices=["not_recorded", "user_recorded", "capture_metadata"],
    )
    extract.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "recommendations" / "captures",
    )

    build = subparsers.add_parser("build", help="Aggregate sanitized observations.")
    build.add_argument(
        "--captures-dir",
        type=Path,
        default=project_root / "recommendations" / "captures",
    )
    build.add_argument(
        "--output",
        type=Path,
        default=project_root / "recommendations" / "brainfm_recommendation_graph.json",
    )

    arguments = parser.parse_args()
    if arguments.command == "extract":
        for capture_path in arguments.captures:
            document = extract_recommendation_capture(
                capture_path,
                visible_category=arguments.visible_category,
                visible_intent=arguments.visible_intent,
                seed_track_id=arguments.seed_track_id,
                captured_at=arguments.captured_at,
                context_method=arguments.context_method,
            )
            path = write_recommendation_capture(document, arguments.output_dir)
            summary = document["summary"]
            print(f"Capture: {capture_path}")
            print(f"  Observation: {document['observation_id']}")
            print(
                f"  Seeds: {summary['observed_seed_count']} · "
                f"edges: {summary['unique_edge_count']} · "
                f"varying lists: {summary['seed_with_multiple_list_variants_count']}"
            )
            print(f"  Sidecar: {path}")
        return

    paths = sorted(arguments.captures_dir.glob("*.recommendation.json"))
    captures = []
    for path in paths:
        document = json.loads(path.read_text())
        validate_recommendation_capture(document)
        captures.append(document)
    graph = aggregate_recommendation_captures(captures)
    output = write_recommendation_graph(graph, arguments.output)
    summary = graph["summary"]
    print(f"Capture observations: {summary['observation_count']}")
    print(f"Recommendation seeds: {summary['seed_count']}")
    print(f"Graph nodes:          {summary['node_count']}")
    print(f"Graph edges:          {summary['edge_count']}")
    print(f"Varying seed lists:   {summary['seed_with_multiple_list_variants_count']}")
    print(f"Graph:                {output}")


if __name__ == "__main__":
    main()
