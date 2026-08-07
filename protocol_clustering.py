import argparse
import json
from pathlib import Path

from clustering.protocol_families import build_protocol_families, write_protocol_families


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Discover evidence-led protocol families in the AVE corpus."
    )
    parser.add_argument(
        "--corpus-index",
        type=Path,
        default=project_root / "artifacts" / "corpus" / "corpus_index.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "artifacts" / "clustering",
    )
    parser.add_argument(
        "--maximum-families",
        type=int,
        default=8,
        help="Maximum candidate family count considered during model selection.",
    )
    arguments = parser.parse_args()
    index = json.loads(arguments.corpus_index.read_text())
    document = build_protocol_families(
        index,
        maximum_families=arguments.maximum_families,
    )
    json_path, csv_path = write_protocol_families(document, arguments.output_dir)
    method = document["method"]
    print(f"Unique inputs clustered: {document['clustered_unique_input_count']}")
    print(f"Protocol families:       {method['selected_family_count']}")
    print(f"Silhouette score:        {method['overall_silhouette_score']:.4f}")
    for family in document["families"]:
        print(f"  {family['family_id']} ({family['member_count']}): {family['descriptor']}")
    print(f"JSON families:           {json_path}")
    print(f"CSV assignments:         {csv_path}")


if __name__ == "__main__":
    main()
