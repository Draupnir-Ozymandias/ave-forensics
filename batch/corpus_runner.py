from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import soundfile as sf

from provenance.run import validate_run_provenance
from core.media import AUDIO_EXTENSIONS


def read_evidence_provenance(evidence_path: Path) -> dict[str, Any]:
    try:
        document = json.loads(evidence_path.read_text())
        provenance = document.get("run_provenance")
        if provenance is None:
            return {
                "provenance_status": "legacy_missing",
                "run_id": None,
                "input_sha256": None,
            }
        validate_run_provenance(provenance)
        return {
            "provenance_status": "validated",
            "run_id": provenance["run_id"],
            "input_sha256": provenance["input"]["sha256"],
        }
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {
            "provenance_status": "invalid",
            "run_id": None,
            "input_sha256": None,
            "provenance_error": str(exc),
        }


def probe_duration_seconds(path: Path) -> float | None:
    """Read duration from the media header without decoding the recording."""
    try:
        return float(sf.info(path).duration)
    except (RuntimeError, TypeError, ValueError):
        return None


def _slug(relative_path: Path) -> str:
    readable = re.sub(
        r"[^a-z0-9]+",
        "-",
        str(relative_path.with_suffix("")).lower(),
    ).strip("-")
    digest = hashlib.sha256(str(relative_path).encode("utf-8")).hexdigest()[:8]
    return f"{readable[:80]}-{digest}"


def discover_recordings(samples_root: Path) -> list[dict[str, Any]]:
    recordings = []
    for path in sorted(samples_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        relative = path.relative_to(samples_root)
        parts = relative.parts
        recordings.append(
            {
                "path": path.resolve(),
                "relative_path": str(relative),
                "source": parts[0] if parts else "unknown",
                "category": parts[1] if len(parts) > 1 else "unknown",
                "stated_intent": parts[2] if len(parts) > 2 else "",
                "notes": "discovered from corpus",
            }
        )
    return recordings


def load_manifest_recordings(
    manifest_path: Path,
    samples_root: Path,
) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        return []

    by_name: dict[str, list[Path]] = {}
    for path in samples_root.rglob("*"):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            by_name.setdefault(path.name, []).append(path)

    recordings = []
    with manifest_path.open(newline="") as manifest_file:
        for row in csv.DictReader(manifest_file):
            declared = samples_root / row["filename"]
            resolved = declared if declared.exists() else None
            matches = by_name.get(Path(row["filename"]).name, [])
            if resolved is None and len(matches) == 1:
                resolved = matches[0]

            recordings.append(
                {
                    "path": resolved.resolve() if resolved else None,
                    "relative_path": row["filename"],
                    "source": row.get("source", ""),
                    "category": row.get("category", ""),
                    "stated_intent": row.get("stated_intent", ""),
                    "notes": row.get("notes", ""),
                    "manifest_missing": resolved is None,
                }
            )
    return recordings


def build_corpus(
    samples_root: Path,
    manifest_path: Path,
    include_discovered: bool = True,
) -> list[dict[str, Any]]:
    manifest_records = load_manifest_recordings(manifest_path, samples_root)
    records_by_path = {
        str(record["path"]): record
        for record in manifest_records
        if record["path"] is not None
    }
    missing_records = [
        record for record in manifest_records if record["path"] is None
    ]

    if include_discovered:
        for record in discover_recordings(samples_root):
            records_by_path.setdefault(str(record["path"]), record)

    records = list(records_by_path.values()) + missing_records
    return sorted(records, key=lambda item: item["relative_path"])


def _write_summary(path: Path, results: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    path.write_text(
        json.dumps(
            {
                "recording_count": len(results),
                "status_counts": counts,
                "recordings": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def run_corpus(
    *,
    project_root: Path,
    samples_root: Path,
    manifest_path: Path,
    output_root: Path,
    include_discovered: bool = True,
    resume: bool = True,
    dry_run: bool = False,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
    exclude_patterns: tuple[str, ...] = (),
    max_duration_seconds: float | None = None,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    corpus = build_corpus(samples_root, manifest_path, include_discovered)
    if limit is not None:
        corpus = corpus[:limit]

    output_root.mkdir(parents=True, exist_ok=True)
    results = []
    summary_path = output_root / "batch_summary.json"

    for index, record in enumerate(corpus, start=1):
        audio_path = record["path"]
        label = f"[{index}/{len(corpus)}] {record['relative_path']}"
        if audio_path is None:
            if progress:
                progress(f"{label} — missing")
            result = {**record, "path": None, "status": "missing"}
            results.append(result)
            _write_summary(summary_path, results)
            continue

        relative_path = Path(record["relative_path"])
        recording_output = output_root / _slug(relative_path)
        evidence_path = recording_output / "ave_evidence.json"

        if any(
            fnmatch.fnmatch(record["relative_path"], pattern)
            for pattern in exclude_patterns
        ):
            if progress:
                progress(f"{label} — excluded")
            results.append(
                {
                    **record,
                    "path": str(audio_path),
                    "output_dir": str(recording_output),
                    "status": "excluded",
                    "reason": "matched an exclusion pattern",
                }
            )
            _write_summary(summary_path, results)
            continue

        if resume and evidence_path.exists():
            provenance_summary = read_evidence_provenance(evidence_path)
            if progress:
                progress(f"{label} — already complete")
            results.append(
                {
                    **record,
                    "path": str(audio_path),
                    "output_dir": str(recording_output),
                    "status": "skipped_complete",
                    **provenance_summary,
                }
            )
            _write_summary(summary_path, results)
            continue

        duration_seconds = probe_duration_seconds(audio_path)
        if (
            max_duration_seconds is not None
            and duration_seconds is not None
            and duration_seconds > max_duration_seconds
        ):
            reason = (
                f"duration {duration_seconds:.1f}s exceeds limit "
                f"{max_duration_seconds:.1f}s"
            )
            if progress:
                progress(f"{label} — deferred ({reason})")
            results.append(
                {
                    **record,
                    "path": str(audio_path),
                    "output_dir": str(recording_output),
                    "duration_seconds": round(duration_seconds, 3),
                    "status": "deferred",
                    "reason": reason,
                }
            )
            _write_summary(summary_path, results)
            continue

        command = [
            sys.executable,
            str(project_root / "main.py"),
            str(audio_path),
            "--output-dir",
            str(recording_output),
        ]

        if dry_run:
            status = "planned"
            return_code = None
            error = None
            if progress:
                progress(f"{label} — planned")
        else:
            if progress:
                progress(f"{label} — analyzing")
            recording_output.mkdir(parents=True, exist_ok=True)
            environment = os.environ.copy()
            environment.setdefault(
                "MPLCONFIGDIR",
                str(output_root / ".matplotlib_cache"),
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    check=False,
                    env=environment,
                    timeout=timeout_seconds,
                )
                (recording_output / "console.log").write_text(completed.stdout)
                (recording_output / "errors.log").write_text(completed.stderr)
                return_code = completed.returncode
                error = None
                status = (
                    "completed"
                    if return_code == 0 and evidence_path.exists()
                    else "failed"
                )
                provenance_summary = (
                    read_evidence_provenance(evidence_path)
                    if evidence_path.exists()
                    else {
                        "provenance_status": "not_available",
                        "run_id": None,
                        "input_sha256": None,
                    }
                )
                if status == "completed" and provenance_summary[
                    "provenance_status"
                ] != "validated":
                    status = "failed"
            except OSError as exc:
                return_code = None
                error = str(exc)
                status = "failed"
                (recording_output / "console.log").write_text("")
                (recording_output / "errors.log").write_text(f"{error}\n")
                provenance_summary = {
                    "provenance_status": "not_available",
                    "run_id": None,
                    "input_sha256": None,
                }
            except subprocess.TimeoutExpired as exc:
                return_code = None
                error = f"analysis exceeded timeout of {timeout_seconds:.1f}s"
                status = "timed_out"
                stdout = exc.stdout or ""
                stderr = exc.stderr or ""
                if isinstance(stdout, bytes):
                    stdout = stdout.decode(errors="replace")
                if isinstance(stderr, bytes):
                    stderr = stderr.decode(errors="replace")
                (recording_output / "console.log").write_text(stdout)
                (recording_output / "errors.log").write_text(
                    f"{stderr}\n{error}\n"
                )
                provenance_summary = {
                    "provenance_status": "not_available",
                    "run_id": None,
                    "input_sha256": None,
                }
            if progress:
                progress(f"{label} — {status}")

        results.append(
            {
                **record,
                "path": str(audio_path),
                "output_dir": str(recording_output),
                "status": status,
                "return_code": return_code,
                "error": error,
                "duration_seconds": (
                    round(duration_seconds, 3)
                    if duration_seconds is not None
                    else None
                ),
                "command": command,
                **(
                    provenance_summary
                    if not dry_run
                    else {
                        "provenance_status": "planned",
                        "run_id": None,
                        "input_sha256": None,
                    }
                ),
            }
        )
        _write_summary(summary_path, results)

    return results
