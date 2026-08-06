import json
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from corpus.manifests import (
    MANIFEST_SCHEMA_VERSION,
    build_recording_manifests,
    resolved_labels,
    validate_recording_manifest,
    write_recording_manifests,
)


def write_tone(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    tone = np.sin(2 * np.pi * 100 * time)
    sf.write(path, tone, sample_rate)


def test_generates_valid_manifests_and_duplicate_aliases(tmp_path):
    samples = tmp_path / "samples"
    first = samples / "brainfm" / "focus" / "deep_work" / "tone.wav"
    second = first.with_name("renamed-tone.wav")
    write_tone(first)
    shutil.copyfile(first, second)

    manifests = build_recording_manifests(samples)

    assert len(manifests) == 2
    first_manifest = next(
        manifest for path, manifest in manifests if path.name == "tone.wav.metadata.json"
    )
    validate_recording_manifest(first_manifest)
    assert first_manifest["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
    assert first_manifest["inferred_labels"] == {
        "source": "brainfm",
        "category": "focus",
        "claimed_intent": "deep_work",
        "basis": "corpus_directory_structure",
    }
    assert first_manifest["duplicates"]["is_duplicate"] is True
    assert first_manifest["duplicates"]["matching_relative_paths"] == [
        "brainfm/focus/deep_work/renamed-tone.wav"
    ]
    assert manifests[0][1]["recording_id"] == manifests[1][1]["recording_id"]


def test_regeneration_preserves_human_curation(tmp_path):
    samples = tmp_path / "samples"
    recording = samples / "brainfm" / "focus" / "deep_work" / "tone.wav"
    write_tone(recording)
    paths = write_recording_manifests(build_recording_manifests(samples))
    manifest = json.loads(paths[0].read_text())
    manifest["curation"] = {
        "review_status": "reviewed",
        "source_override": None,
        "category_override": None,
        "claimed_intent_override": "sustained_attention",
        "notes": "Reviewed against provider labeling.",
    }
    paths[0].write_text(json.dumps(manifest))

    regenerated = build_recording_manifests(samples)[0][1]

    assert regenerated["curation"] == manifest["curation"]
    assert resolved_labels(regenerated) == {
        "source": "brainfm",
        "category": "focus",
        "claimed_intent": "sustained_attention",
        "label_source": "curated_override",
    }


def test_formal_manifest_schema_has_runtime_version(tmp_path):
    schema_path = (
        Path(__file__).parents[1]
        / "corpus"
        / "recording-manifest.schema.json"
    )
    schema = json.loads(schema_path.read_text())

    assert schema["properties"]["manifest_schema_version"]["const"] == (
        MANIFEST_SCHEMA_VERSION
    )
