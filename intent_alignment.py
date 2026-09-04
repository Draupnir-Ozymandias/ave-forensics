import argparse
import json
from pathlib import Path

from alignment.intent_alignment import build_intent_alignment, write_intent_alignment


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Measure claimed-intent association with observed protocol families."
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
        default=project_root / "artifacts" / "alignment",
    )
    parser.add_argument("--minimum-cohort-size", type=int, default=3)
    arguments = parser.parse_args()
    index = json.loads(arguments.corpus_index.read_text())
    clustering = json.loads(arguments.clusters.read_text())
    document = build_intent_alignment(
        index, clustering, minimum_cohort_size=arguments.minimum_cohort_size
    )
    json_path, csv_path = write_intent_alignment(document, arguments.output_dir)
    association = document["global_association"]
    print(f"Eligible recordings: {document['eligible_recording_count']}")
    print(f"Scored recordings:   {document['scored_recording_count']}")
    print(f"Cramer's V:           {association['cramers_v']:.4f}")
    print(f"Normalized MI:        {association['normalized_mutual_information']:.4f}")
    for profile in document["intent_profiles"]:
        if profile["assessment_status"] == "scored":
            print(
                f"  {profile['stated_intent']} (n={profile['cohort_size']}): "
                f"{profile['dominant_family_label']} · "
                f"consistency {profile['family_consistency']:.3f}"
            )
        else:
            print(
                f"  {profile['stated_intent']} (n={profile['cohort_size']}): "
                "insufficient cohort"
            )
    print(f"JSON alignment:       {json_path}")
    print(f"CSV assessments:      {csv_path}")


if __name__ == "__main__":
    main()
