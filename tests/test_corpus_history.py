import json

from alignment.intent_alignment import build_intent_alignment
from clustering.protocol_families import build_protocol_families
from longitudinal.corpus_history import (
    build_corpus_snapshot,
    compare_corpus_snapshots,
    write_snapshot,
)
from longitudinal.schema import validate_comparison, validate_snapshot
from tests.test_intent_alignment import aligned_index


def build_snapshot(index: dict, timestamp: str) -> dict:
    clustering = build_protocol_families(index)
    alignment = build_intent_alignment(index, clustering)
    return build_corpus_snapshot(
        index, clustering, alignment, captured_at=timestamp
    )


def test_snapshot_preserves_cross_context_reuse_and_is_content_addressed(tmp_path):
    index = aligned_index()
    duplicate = next(
        record for record in index["recordings"]
        if record["relative_path"] == "renamed-low.wav"
    )
    duplicate["stated_intent"] = "alternate-context"
    snapshot = build_snapshot(index, "2026-09-04T12:00:00+00:00")

    validate_snapshot(snapshot)
    assert snapshot["snapshot_id"].startswith("ave_snapshot_")
    assert snapshot["summary"]["cross_context_reuse_count"] == 1
    reuse = next(
        item for item in snapshot["reuse_groups"]
        if item["reuse_classification"] == "cross_context_reuse"
    )
    assert reuse["stated_intents"] == ["alternate-context", "rest"]
    path, created = write_snapshot(snapshot, tmp_path)
    assert created is True
    assert json.loads(path.read_text())["snapshot_id"] == snapshot["snapshot_id"]
    _, created_again = write_snapshot(snapshot, tmp_path)
    assert created_again is False


def test_comparison_detects_growth_and_context_drift():
    baseline_index = aligned_index()
    baseline = build_snapshot(baseline_index, "2026-09-04T12:00:00+00:00")

    current_index = aligned_index()
    changed = next(
        record for record in current_index["recordings"]
        if record["relative_path"] == "low-1.wav"
    )
    changed["stated_intent"] = "new-context"
    new_record = dict(
        next(
            record for record in current_index["recordings"]
            if record["relative_path"] == "high-1.wav"
        )
    )
    new_record["relative_path"] = "high-new.wav"
    new_record["input_sha256"] = f"{500:064x}"
    current_index["recordings"].append(new_record)
    current = build_snapshot(current_index, "2026-09-05T12:00:00+00:00")
    comparison = compare_corpus_snapshots(baseline, current)

    validate_comparison(comparison)
    assert comparison["summary"]["added_input_count"] == 1
    assert comparison["summary"]["removed_input_count"] == 0
    assert comparison["summary"]["context_change_count"] == 1
    assert any(
        item["intent_change"]["added"] == ["new-context"]
        for item in comparison["context_changes"]
    )
