import argparse
from pathlib import Path

from corpus.index import build_corpus_index, write_corpus_index


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Build a searchable index from AVE batch evidence."
    )
    parser.add_argument(
        "--batch-summary",
        type=Path,
        default=project_root / "artifacts" / "batch" / "batch_summary.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "artifacts" / "corpus",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA-256 input hashing for a faster provisional index.",
    )
    arguments = parser.parse_args()

    index = build_corpus_index(
        arguments.batch_summary,
        project_root,
        hash_inputs=not arguments.no_hash,
    )
    json_path, csv_path = write_corpus_index(index, arguments.output_dir)
    print(f"Corpus recordings: {index['recording_count']}")
    print(f"Indexed recordings: {index['indexed_recording_count']}")
    print(f"Indexed evidence objects: {index['indexed_evidence_count']}")
    for status, count in index["index_status_counts"].items():
        print(f"  {status}: {count}")
    print(f"JSON index: {json_path}")
    print(f"CSV index:  {csv_path}")


if __name__ == "__main__":
    main()
