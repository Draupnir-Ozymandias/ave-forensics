import argparse
import json
from pathlib import Path

from recommendations.communities import (
    analyze_recommendation_drift,
    build_recommendation_communities,
    write_recommendation_communities,
    write_recommendation_drift,
)
from recommendations.graph import validate_recommendation_capture


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Discover recommendation communities and assess repeated-capture drift."
    )
    parser.add_argument(
        "--graph",
        type=Path,
        default=project_root / "recommendations" / "brainfm_recommendation_graph.json",
    )
    parser.add_argument(
        "--captures-dir",
        type=Path,
        default=project_root / "recommendations" / "captures",
    )
    parser.add_argument(
        "--corpus-index",
        type=Path,
        default=project_root / "artifacts" / "corpus" / "corpus_index.json",
    )
    parser.add_argument(
        "--clusters",
        type=Path,
        default=project_root / "artifacts" / "clustering" / "protocol_families.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "recommendations",
    )
    arguments = parser.parse_args()

    graph = json.loads(arguments.graph.read_text())
    index = json.loads(arguments.corpus_index.read_text())
    clustering = json.loads(arguments.clusters.read_text())
    communities = build_recommendation_communities(
        graph, index=index, clustering=clustering
    )
    community_path, csv_path = write_recommendation_communities(
        communities, arguments.output_dir
    )

    captures = []
    for path in sorted(arguments.captures_dir.glob("*.recommendation.json")):
        document = json.loads(path.read_text())
        validate_recommendation_capture(document)
        captures.append(document)
    drift = analyze_recommendation_drift(captures)
    drift_path = write_recommendation_drift(drift, arguments.output_dir)

    community_summary = communities["summary"]
    drift_summary = drift["summary"]
    print(f"Connected nodes:     {community_summary['connected_node_count']}")
    print(f"Isolated nodes:      {community_summary['isolated_node_count']}")
    print(f"Communities:         {community_summary['community_count']}")
    print(f"Modularity:          {community_summary['modularity']:.4f}")
    print(f"Local recordings:    {community_summary['local_recording_count']}")
    print(f"Repeated seeds:      {drift_summary['repeated_seed_count']}")
    print(f"Drift-assessed seeds:{drift_summary['assessed_seed_count']:>6}")
    print(
        f"Within-capture variants: {drift_summary['within_capture_variant_seed_count']}"
    )
    print(f"Communities JSON:    {community_path}")
    print(f"Assignments CSV:     {csv_path}")
    print(f"Drift JSON:          {drift_path}")


if __name__ == "__main__":
    main()
