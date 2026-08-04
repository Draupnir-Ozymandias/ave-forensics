from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}


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

        if resume and evidence_path.exists():
            if progress:
                progress(f"{label} — already complete")
            results.append(
                {
                    **record,
                    "path": str(audio_path),
                    "output_dir": str(recording_output),
                    "status": "skipped_complete",
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
            except OSError as exc:
                return_code = None
                error = str(exc)
                status = "failed"
                (recording_output / "console.log").write_text("")
                (recording_output / "errors.log").write_text(f"{error}\n")
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
                "command": command,
            }
        )
        _write_summary(summary_path, results)

    return results
