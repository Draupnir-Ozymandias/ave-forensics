import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import provenance.run as run_module
from analysis.config import ANALYSIS_CONFIGURATION
from corpus.manifests import build_recording_manifests, write_recording_manifests
from provenance.run import build_run_provenance, validate_run_provenance


def prepare_recording(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    recording = (
        project
        / "samples"
        / "synthetic"
        / "control"
        / "known_intent"
        / "tone.wav"
    )
    recording.parent.mkdir(parents=True)
    sf.write(recording, np.zeros(8000, dtype=np.float32), 8000)
    write_recording_manifests(
        build_recording_manifests(project / "samples")
    )
    return project, recording


def stabilize_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        run_module,
        "_git_identity",
        lambda root: {"commit": "a" * 40, "branch": "main", "dirty": False},
    )
    monkeypatch.setattr(
        run_module,
        "_dependency_versions",
        lambda: {"numpy": "1.0"},
    )
    monkeypatch.setattr(run_module, "_source_tree_sha256", lambda root: "b" * 64)


def test_run_id_binds_input_manifest_code_and_configuration(tmp_path, monkeypatch):
    project, recording = prepare_recording(tmp_path)
    stabilize_environment(monkeypatch)

    first = build_run_provenance(
        input_path=recording,
        project_root=project,
        analysis_configuration=ANALYSIS_CONFIGURATION,
    )
    second = build_run_provenance(
        input_path=recording,
        project_root=project,
        analysis_configuration=ANALYSIS_CONFIGURATION,
    )

    assert first == second
    validate_run_provenance(first)
    assert first["input"]["sha256"] == first["recording_manifest"][
        "recording_id"
    ].removeprefix("ave_recording_") + first["input"]["sha256"][16:]
    assert first["recording_manifest"]["manifest_sha256"]

    changed_configuration = json.loads(json.dumps(ANALYSIS_CONFIGURATION))
    changed_configuration["timeline"]["hop_seconds"] = 2.5
    changed = build_run_provenance(
        input_path=recording,
        project_root=project,
        analysis_configuration=changed_configuration,
    )
    assert changed["run_id"] != first["run_id"]


def test_rejects_input_that_no_longer_matches_manifest(tmp_path, monkeypatch):
    project, recording = prepare_recording(tmp_path)
    stabilize_environment(monkeypatch)
    recording.write_bytes(recording.read_bytes() + b"changed")

    with pytest.raises(ValueError, match="manifest SHA-256 does not match"):
        build_run_provenance(
            input_path=recording,
            project_root=project,
            analysis_configuration=ANALYSIS_CONFIGURATION,
        )


def test_rejects_tampered_run_fingerprint(tmp_path, monkeypatch):
    project, recording = prepare_recording(tmp_path)
    stabilize_environment(monkeypatch)
    provenance = build_run_provenance(
        input_path=recording,
        project_root=project,
        analysis_configuration=ANALYSIS_CONFIGURATION,
    )
    provenance["analysis_configuration"]["timeline"]["hop_seconds"] = 99

    with pytest.raises(ValueError, match="run_id does not match"):
        validate_run_provenance(provenance)


def test_formal_provenance_schema_matches_runtime_version():
    schema_path = (
        Path(__file__).parents[1]
        / "provenance"
        / "run-provenance.schema.json"
    )
    schema = json.loads(schema_path.read_text())

    assert schema["properties"]["provenance_schema_version"]["const"] == "1.0.0"
    assert "analysis_configuration" in schema["required"]
