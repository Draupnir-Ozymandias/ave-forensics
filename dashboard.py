import argparse
import json
from pathlib import Path

from dashboard.comparison import build_dashboard_data, write_dashboard


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate the AVE reference-library comparison dashboard."
    )
    parser.add_argument(
        "--corpus-index",
        type=Path,
        default=project_root / "artifacts" / "corpus" / "corpus_index.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "artifacts" / "dashboard",
    )
    parser.add_argument(
        "--clusters",
        type=Path,
        default=project_root / "artifacts" / "clustering" / "protocol_families.json",
        help="Optional protocol-family artifact; loaded when the file exists.",
    )
    parser.add_argument(
        "--intent-alignment",
        type=Path,
        default=project_root / "artifacts" / "alignment" / "intent_alignment.json",
        help="Optional claimed-intent alignment artifact; loaded when the file exists.",
    )
    arguments = parser.parse_args()
    index = json.loads(arguments.corpus_index.read_text())
    clustering = (
        json.loads(arguments.clusters.read_text())
        if arguments.clusters.exists()
        else None
    )
    alignment = (
        json.loads(arguments.intent_alignment.read_text())
        if arguments.intent_alignment.exists()
        else None
    )
    data = build_dashboard_data(index, clustering, alignment)
    output_path = write_dashboard(data, arguments.output_dir)
    overview = data["overview"]
    print(f"Recording aliases: {overview['recording_alias_count']}")
    print(f"Unique inputs:     {overview['unique_input_count']}")
    print(f"Unique analyzed:   {overview['unique_indexed_count']}")
    print(f"Protocol families: {overview['protocol_family_count']}")
    print(f"Intent assessments: {overview['scored_intent_alignment_count']}")
    print(f"Dashboard:         {output_path}")


if __name__ == "__main__":
    main()
