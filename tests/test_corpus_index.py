import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

from corpus.index import build_corpus_index, summarize_evidence_document, write_corpus_index
from corpus.manifests import build_recording_manifests, write_recording_manifests
from evidence.schema import SCHEMA_VERSION, create_evidence_object, measurement
from provider.brainfm import extract_brainfm_sidecars, write_provider_sidecars
from transcripts.sidecar import import_aws_transcribe, write_transcript_sidecar


def hypothesis_evidence() -> dict:
    return create_evidence_object(
        evidence_level="hypothesis",
        evidence_type="protocol_intent_hypothesis",
        source_module="analysis.protocol_hypothesis",
        summary="delta relaxation / sleep-depth candidate",
        measurements=[
            measurement("average_difference_frequency", 0.5, "Hz"),
            measurement("duration", 3600.0, "seconds"),
            measurement("brainwave_band", "delta", "classification"),
            measurement("hypothesis_score", 1.0821, "ranking_score"),
        ],
        confidence={
            "score": 0.8657,
            "method": "persistent_track_average_confidence",
        },
    )


def evidence_document(evidence: list[dict]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_count": len(evidence),
        "run_metadata": {"duration_seconds": 3600.0, "sample_rate": 44100},
        "evidence": evidence,
    }


def speech_context_evidence() -> dict:
    return create_evidence_object(
        evidence_level="association",
        evidence_type="speech_context_comparison",
        source_module="analysis.speech_context",
        summary="Speech-aware comparison",
        measurements=[
            measurement("buffered_speech_coverage", 0.38, "ratio"),
            measurement("speech_active_window_count", 72, "count"),
            measurement("speech_sparse_window_count", 106, "count"),
            measurement("direct_comparison_available", True, "boolean"),
            measurement("speech_active_candidate_rate", 1.0, "ratio"),
            measurement("speech_sparse_candidate_rate", 1.0, "ratio"),
            measurement("speech_active_median_difference", 1.25, "Hz"),
            measurement("speech_sparse_median_difference", 0.5, "Hz"),
            measurement("speech_active_persistent_difference", 0.8, "Hz"),
            measurement("speech_sparse_persistent_difference", 0.6, "Hz"),
            measurement("speech_active_persistent_score", 0.4, "ranking_score"),
            measurement("speech_sparse_persistent_score", 0.5, "ranking_score"),
        ],
        context={
            "entrainment_band_counts": {
                "speech_active": {"delta": 42, "gamma": 10},
                "speech_sparse": {"delta": 106},
            },
            "persistent_context": {
                "speech_active_band": "delta",
                "speech_sparse_band": "delta",
            },
        },
    )


def test_summarizes_speech_context_comparison():
    summary = summarize_evidence_document(
        evidence_document([hypothesis_evidence(), speech_context_evidence()])
    )

    comparison = summary["speech_context_comparison"]
    assert comparison["direct_comparison_available"] is True
    assert comparison["active_median_difference_hz"] == 1.25
    assert comparison["sparse_band_counts"] == {"delta": 106}
    assert comparison["sparse_persistent_difference_hz"] == 0.6


def test_summarizes_all_retained_hypothesis_bands_and_best_candidates():
    gamma_low = create_evidence_object(
        evidence_level="hypothesis",
        evidence_type="protocol_intent_hypothesis",
        source_module="analysis.protocol_hypothesis",
        summary="low-gamma candidate",
        measurements=[
            measurement("average_difference_frequency", 34.0, "Hz"),
            measurement("duration", 120.0, "seconds"),
            measurement("brainwave_band", "gamma", "classification"),
            measurement("hypothesis_score", 0.2, "ranking_score"),
        ],
        confidence={"score": 0.4, "method": "persistent_track_average_confidence"},
    )
    gamma_high = create_evidence_object(
        evidence_level="hypothesis",
        evidence_type="protocol_intent_hypothesis",
        source_module="analysis.protocol_hypothesis",
        summary="low-gamma candidate",
        measurements=[
            measurement("average_difference_frequency", 38.0, "Hz"),
            measurement("duration", 120.0, "seconds"),
            measurement("brainwave_band", "gamma", "classification"),
            measurement("hypothesis_score", 0.3, "ranking_score"),
        ],
        confidence={"score": 0.5, "method": "persistent_track_average_confidence"},
    )

    summary = summarize_evidence_document(
        evidence_document([hypothesis_evidence(), gamma_low, gamma_high])
    )

    bands = summary["hypothesis_band_summary"]
    assert bands["candidate_count"] == 3
    assert bands["counts"] == {"delta": 1, "gamma": 2}
    assert bands["best_by_band"]["gamma"]["difference_hz"] == 38.0
    assert bands["best_by_band"]["gamma"]["ranking_score"] == 0.3
    assert summary["top_hypothesis"]["brainwave_band"] == "delta"


def test_builds_index_with_hashes_statuses_and_invalid_evidence(tmp_path):
    project = tmp_path / "project"
    audio = project / "samples" / "complete.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"known audio bytes")
    complete_output = project / "artifacts" / "complete"
    complete_output.mkdir(parents=True)
    (complete_output / "ave_evidence.json").write_text(
        json.dumps(evidence_document([hypothesis_evidence()]))
    )

    invalid_audio = project / "samples" / "invalid.wav"
    invalid_audio.write_bytes(b"invalid evidence audio")
    invalid_output = project / "artifacts" / "invalid"
    invalid_output.mkdir(parents=True)
    (invalid_output / "ave_evidence.json").write_text("not json")

    deferred_audio = project / "samples" / "deferred.wav"
    deferred_audio.write_bytes(b"deferred audio")
    batch = {
        "recording_count": 3,
        "status_counts": {"completed": 1, "deferred": 1, "failed": 1},
        "recordings": [
            {
                "relative_path": "complete.wav",
                "path": str(audio),
                "output_dir": str(complete_output),
                "source": "synthetic",
                "category": "control",
                "stated_intent": "test",
                "notes": "valid",
                "status": "completed",
            },
            {
                "relative_path": "deferred.wav",
                "path": str(deferred_audio),
                "output_dir": str(project / "artifacts" / "deferred"),
                "source": "synthetic",
                "category": "control",
                "stated_intent": "test",
                "notes": "long",
                "status": "deferred",
                "duration_seconds": 6812.1,
            },
            {
                "relative_path": "invalid.wav",
                "path": str(invalid_audio),
                "output_dir": str(invalid_output),
                "source": "synthetic",
                "category": "control",
                "stated_intent": "test",
                "notes": "bad evidence",
                "status": "failed",
            },
        ],
    }
    summary_path = project / "artifacts" / "batch_summary.json"
    summary_path.write_text(json.dumps(batch))

    index = build_corpus_index(summary_path, project)

    assert index["recording_count"] == 3
    assert index["indexed_recording_count"] == 1
    assert index["indexed_evidence_count"] == 1
    assert index["index_status_counts"] == {
        "deferred": 1,
        "indexed": 1,
        "invalid_evidence": 1,
    }
    complete = next(
        item for item in index["recordings"] if item["relative_path"] == "complete.wav"
    )
    assert complete["input_sha256"] == hashlib.sha256(b"known audio bytes").hexdigest()
    assert complete["evidence_summary"]["top_hypothesis"]["ranking_score"] == 1.0821
    assert complete["evidence_summary"]["top_hypothesis"]["confidence"] == 0.8657
    assert index["duplicate_input_groups"] == []
    assert index["analysis_configuration_version_counts"] == {}


def test_writes_deterministic_json_and_flat_csv(tmp_path):
    index = {
        "index_schema_version": "1.0.0",
        "evidence_schema_version": "1.0.0",
        "recording_count": 1,
        "indexed_recording_count": 0,
        "indexed_evidence_count": 0,
        "input_hash_algorithm": "sha256",
        "batch_status_counts": {"deferred": 1},
        "index_status_counts": {"deferred": 1},
        "source_counts": {"synthetic": 1},
        "category_counts": {"control": 1},
        "stated_intent_counts": {"test": 1},
        "duplicate_input_groups": [],
        "recordings": [
            {
                "relative_path": "long.wav",
                "source": "synthetic",
                "category": "control",
                "stated_intent": "test",
                "notes": "long",
                "batch_status": "deferred",
                "index_status": "deferred",
                "input_size_bytes": 10,
                "input_sha256": "abc",
                "duplicate_input_paths": [],
                "duration_seconds": 6812.1,
                "evidence_path": None,
                "evidence_summary": None,
                "index_error": None,
            }
        ],
    }

    json_path, csv_path = write_corpus_index(index, tmp_path)

    assert json.loads(json_path.read_text()) == index
    with csv_path.open(newline="") as input_file:
        rows = list(csv.DictReader(input_file))
    assert rows[0]["relative_path"] == "long.wav"
    assert rows[0]["index_status"] == "deferred"


def test_identifies_byte_identical_inputs(tmp_path):
    project = tmp_path / "project"
    samples = project / "samples"
    samples.mkdir(parents=True)
    first = samples / "first.wav"
    second = samples / "renamed-copy.wav"
    first.write_bytes(b"identical")
    second.write_bytes(b"identical")
    records = []
    for path in (first, second):
        records.append(
            {
                "relative_path": path.name,
                "path": str(path),
                "output_dir": str(project / "artifacts" / path.stem),
                "source": "synthetic",
                "category": "control",
                "stated_intent": "test",
                "notes": "duplicate test",
                "status": "deferred",
            }
        )
    summary_path = project / "batch_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "recording_count": 2,
                "status_counts": {"deferred": 2},
                "recordings": records,
            }
        )
    )

    index = build_corpus_index(summary_path, project)

    assert len(index["duplicate_input_groups"]) == 1
    assert index["duplicate_input_groups"][0]["relative_paths"] == [
        "first.wav",
        "renamed-copy.wav",
    ]
    assert index["recordings"][0]["duplicate_input_paths"] == [
        "renamed-copy.wav"
    ]


def test_index_uses_validated_manifest_instead_of_stale_batch_labels(tmp_path):
    project = tmp_path / "project"
    samples = project / "samples"
    audio = samples / "brainfm" / "meditate" / "unguided" / "session.wav"
    audio.parent.mkdir(parents=True)
    sf.write(audio, np.zeros(8000, dtype=np.float32), 8000)
    write_recording_manifests(build_recording_manifests(samples))
    batch = {
        "recording_count": 1,
        "status_counts": {"deferred": 1},
        "recordings": [
            {
                "relative_path": "brainfm/meditation/session.wav",
                "path": str(audio),
                "output_dir": str(project / "artifacts" / "session"),
                "source": "brain.fm",
                "category": "meditation",
                "stated_intent": "meditation",
                "notes": "stale",
                "status": "deferred",
            }
        ],
    }
    summary_path = project / "batch_summary.json"
    summary_path.write_text(json.dumps(batch))

    index = build_corpus_index(summary_path, project)
    record = index["recordings"][0]

    assert record["relative_path"] == "brainfm/meditate/unguided/session.wav"
    assert record["source"] == "brainfm"
    assert record["category"] == "meditate"
    assert record["stated_intent"] == "unguided"
    assert record["metadata_status"] == "validated"
    assert record["batch_metadata"]["category"] == "meditation"


def test_index_validates_and_flattens_provider_metadata(tmp_path):
    project = tmp_path / "project"
    samples = project / "samples"
    audio = samples / "brainfm" / "meditate" / "guided" / "session.wav"
    audio.parent.mkdir(parents=True)
    sf.write(audio, np.zeros(8000, dtype=np.float32), 8000)
    provider_track = {
        "id": "track-1",
        "name": "Calm Session",
        "beatsPerMinute": 120,
        "brightnessLevel": 0.25,
        "complexityLevel": 0.5,
        "createdAt": "2026-08-12T00:00:00Z",
        "releaseStatus": "published",
        "hasMultipleNELs": False,
        "mentalState": {"displayValue": "Meditate"},
        "mobileActivity": {"displayValue": "Guided"},
        "tags": [{"type": "mood", "value": "Calm"}],
        "variations": [
            {
                "id": "variation-1",
                "url": audio.name,
                "lengthInSeconds": 1,
                "neuralEffectLevel": 0.9,
                "style": "guided",
            }
        ],
    }
    capture = project / "captured-response"
    capture.write_text(json.dumps({"result": {"track": provider_track}}))
    write_provider_sidecars(extract_brainfm_sidecars(capture, audio.parent))
    batch = {
        "recording_count": 1,
        "status_counts": {"deferred": 1},
        "recordings": [
            {
                "relative_path": "brainfm/meditate/guided/session.wav",
                "path": str(audio),
                "output_dir": str(project / "artifacts" / "session"),
                "source": "brainfm",
                "category": "meditate",
                "stated_intent": "guided",
                "status": "deferred",
            }
        ],
    }
    summary_path = project / "batch_summary.json"
    summary_path.write_text(json.dumps(batch))

    index = build_corpus_index(summary_path, project)
    record = index["recordings"][0]

    assert index["provider_metadata_status_counts"] == {"validated": 1}
    assert record["provider_metadata_status"] == "validated"
    assert record["provider_metadata"]["provider_track"]["title"] == "Calm Session"
    _, csv_path = write_corpus_index(index, project / "corpus")
    with csv_path.open(newline="") as input_file:
        row = next(csv.DictReader(input_file))
    assert row["provider_activity"] == "Guided"
    assert row["provider_neural_effect_level"] == "0.9"


def test_index_validates_and_flattens_transcript_sidecar(tmp_path):
    from tests.test_transcript_metadata import aws_response

    project = tmp_path / "project"
    audio = project / "samples" / "brainfm" / "meditate" / "guided" / "session.wav"
    audio.parent.mkdir(parents=True)
    sf.write(audio, np.zeros(80_000, dtype=np.float32), 8_000)
    raw = project / "captured" / "session.json"
    raw.parent.mkdir()
    raw.write_text(json.dumps(aws_response()))
    sidecar = import_aws_transcribe(
        raw,
        audio,
        region="us-east-2",
        language_code="en-US",
        media_format="wav",
        media_sample_rate_hz=8_000,
    )
    write_transcript_sidecar(sidecar, audio)
    batch = {
        "recording_count": 1,
        "status_counts": {"deferred": 1},
        "recordings": [
            {
                "relative_path": "brainfm/meditate/guided/session.wav",
                "path": str(audio),
                "output_dir": str(project / "artifacts" / "session"),
                "source": "brainfm",
                "category": "meditate",
                "stated_intent": "guided",
                "status": "deferred",
            }
        ],
    }
    summary_path = project / "batch_summary.json"
    summary_path.write_text(json.dumps(batch))

    index = build_corpus_index(summary_path, project)
    record = index["recordings"][0]

    assert index["transcript_status_counts"] == {"validated": 1}
    assert record["transcript_status"] == "validated"
    assert record["transcript_sidecar"]["content_policy"][
        "sidecar_contains_verbatim_text"
    ] is False
    _, csv_path = write_corpus_index(index, project / "corpus")
    with csv_path.open(newline="") as input_file:
        row = next(csv.DictReader(input_file))
    assert row["transcript_provider"] == "aws"
    assert row["transcript_language_code"] == "en-US"
    assert row["transcript_speech_coverage_ratio"] == "0.2"
