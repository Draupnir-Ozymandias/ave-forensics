import argparse
import json
from pathlib import Path

from alignment.context_drift import build_context_drift, write_context_drift


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Compare independently preserved provider and corpus context layers."
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
        "--recommendation-graph",
        type=Path,
        default=project_root / "recommendations" / "brainfm_recommendation_graph.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "artifacts" / "context",
    )
    arguments = parser.parse_args()
    index = json.loads(arguments.corpus_index.read_text())
    clustering = json.loads(arguments.clusters.read_text())
    graph = json.loads(arguments.recommendation_graph.read_text())
    document = build_context_drift(index, clustering, graph)
    json_path, csv_path = write_context_drift(document, arguments.output_dir)
    summary = document["summary"]
    print(f"Canonical recordings:       {summary['assessed_recording_count']}")
    print(f"Provider-linked recordings: {summary['provider_linked_recording_count']}")
    print(
        "Recommendation contexts:   "
        f"{summary['recommendation_context_recording_count']}"
    )
    for status, count in summary["context_status_counts"].items():
        print(f"  {status}: {count}")
    print(f"Context JSON: {json_path}")
    print(f"Context CSV:  {csv_path}")


if __name__ == "__main__":
    main()
