import argparse
import json
from pathlib import Path

from longitudinal.corpus_history import (
    build_corpus_snapshot,
    compare_corpus_snapshots,
    write_comparison,
    write_snapshot,
)
from longitudinal.schema import validate_snapshot


def _load_snapshots(directory: Path) -> list[dict]:
    snapshots = []
    for path in sorted(directory.glob("ave_snapshot_*.json")) if directory.exists() else []:
        document = json.loads(path.read_text())
        validate_snapshot(document)
        snapshots.append(document)
    return sorted(snapshots, key=lambda item: (item["captured_at"], item["snapshot_id"]))


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Save a durable corpus snapshot and compare it with the prior state."
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
        "--intent-alignment",
        type=Path,
        default=project_root / "artifacts" / "alignment" / "intent_alignment.json",
    )
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=project_root / "history" / "corpus_snapshots",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=project_root / "artifacts" / "longitudinal",
    )
    arguments = parser.parse_args()

    index = json.loads(arguments.corpus_index.read_text())
    clustering = json.loads(arguments.clusters.read_text())
    alignment = json.loads(arguments.intent_alignment.read_text())
    current = build_corpus_snapshot(index, clustering, alignment)
    existing = _load_snapshots(arguments.snapshot_dir)
    prior = next(
        (
            snapshot
            for snapshot in reversed(existing)
            if snapshot["snapshot_id"] != current["snapshot_id"]
        ),
        None,
    )
    snapshot_path, created = write_snapshot(current, arguments.snapshot_dir)

    print(f"Corpus snapshot: {current['snapshot_id']}")
    print(f"Unique inputs:   {current['summary']['unique_input_count']}")
    print(f"Cross-context:   {current['summary']['cross_context_reuse_count']}")
    print(f"Snapshot file:   {snapshot_path} ({'created' if created else 'already current'})")
    if prior is None:
        print("Comparison:      baseline established; no earlier distinct snapshot")
        return

    comparison = compare_corpus_snapshots(prior, current)
    comparison_path = write_comparison(comparison, arguments.output_dir)
    summary = comparison["summary"]
    print(f"Compared with:   {prior['snapshot_id']}")
    print(
        "Changes:         "
        f"+{summary['added_input_count']} / -{summary['removed_input_count']} inputs, "
        f"{summary['family_transition_count']} family transitions, "
        f"{summary['context_change_count']} context changes"
    )
    print(f"Comparison file: {comparison_path}")


if __name__ == "__main__":
    main()
