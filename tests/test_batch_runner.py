import json
import subprocess
from pathlib import Path

from batch.corpus_runner import build_corpus, run_corpus


def write_manifest(path: Path, filename: str) -> None:
    path.write_text(
        "filename,source,stated_intent,category,duration_minutes,notes\n"
        f"{filename},synthetic,focus,control,1,test\n"
    )


def test_build_corpus_merges_manifest_and_discovery(tmp_path):
    samples = tmp_path / "samples"
    audio = samples / "synthetic" / "focus" / "tone.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    manifest = samples / "manifest.csv"
    write_manifest(manifest, "synthetic/focus/tone.wav")

    corpus = build_corpus(samples, manifest)

    assert len(corpus) == 1
    assert corpus[0]["path"] == audio.resolve()
    assert corpus[0]["stated_intent"] == "focus"


def test_manifest_resolves_unique_moved_filename(tmp_path):
    samples = tmp_path / "samples"
    audio = samples / "new" / "location" / "tone.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    manifest = samples / "manifest.csv"
    write_manifest(manifest, "old/location/tone.wav")

    corpus = build_corpus(samples, manifest, include_discovered=False)

    assert corpus[0]["path"] == audio.resolve()


def test_dry_run_creates_plan_without_analysis(tmp_path):
    project = tmp_path / "project"
    samples = project / "samples"
    audio = samples / "control.wav"
    samples.mkdir(parents=True)
    audio.write_bytes(b"audio")
    manifest = samples / "manifest.csv"
    write_manifest(manifest, "control.wav")
    output = project / "artifacts" / "batch"

    results = run_corpus(
        project_root=project,
        samples_root=samples,
        manifest_path=manifest,
        output_root=output,
        dry_run=True,
    )

    assert results[0]["status"] == "planned"
    summary = json.loads((output / "batch_summary.json").read_text())
    assert summary["status_counts"] == {"planned": 1}


def test_resume_skips_existing_evidence(tmp_path):
    project = tmp_path / "project"
    samples = project / "samples"
    audio = samples / "control.wav"
    samples.mkdir(parents=True)
    audio.write_bytes(b"audio")
    manifest = samples / "manifest.csv"
    write_manifest(manifest, "control.wav")
    output = project / "batch"

    planned = run_corpus(
        project_root=project,
        samples_root=samples,
        manifest_path=manifest,
        output_root=output,
        dry_run=True,
    )
    recording_output = Path(planned[0]["output_dir"])
    recording_output.mkdir(parents=True)
    (recording_output / "ave_evidence.json").write_text("{}")

    resumed = run_corpus(
        project_root=project,
        samples_root=samples,
        manifest_path=manifest,
        output_root=output,
    )

    assert resumed[0]["status"] == "skipped_complete"


def test_subprocess_launch_failure_is_recorded(tmp_path, monkeypatch):
    project = tmp_path / "project"
    samples = project / "samples"
    audio = samples / "control.wav"
    samples.mkdir(parents=True)
    audio.write_bytes(b"audio")
    manifest = samples / "manifest.csv"
    write_manifest(manifest, "control.wav")

    def fail_to_launch(*args, **kwargs):
        raise OSError("synthetic launch failure")

    monkeypatch.setattr(subprocess, "run", fail_to_launch)
    results = run_corpus(
        project_root=project,
        samples_root=samples,
        manifest_path=manifest,
        output_root=project / "batch",
    )

    assert results[0]["status"] == "failed"
    assert results[0]["error"] == "synthetic launch failure"
    error_log = Path(results[0]["output_dir"]) / "errors.log"
    assert error_log.read_text() == "synthetic launch failure\n"
