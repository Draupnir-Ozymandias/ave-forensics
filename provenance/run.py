from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from ave_version import __version__
from core.hashing import sha256_file
from corpus.manifests import (
    manifest_path_for,
    validate_recording_manifest,
)


RUN_PROVENANCE_SCHEMA_VERSION = "1.0.0"
RUN_ID_PATTERN = re.compile(r"^ave_run_[0-9a-f]{16}$")
SOURCE_DIRECTORIES = (
    "analysis",
    "batch",
    "core",
    "corpus",
    "evidence",
    "provenance",
    "reports",
)
SOURCE_FILES = ("requirements.txt",)
DEPENDENCIES = ("numpy", "scipy", "librosa", "soundfile", "matplotlib")


def _canonical_hash(value: Any) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_tree_sha256(project_root: Path) -> str:
    paths = []
    for directory in SOURCE_DIRECTORIES:
        root = project_root / directory
        if root.exists():
            paths.extend(root.rglob("*.py"))
    paths.extend(project_root.glob("*.py"))
    paths.extend(
        project_root / filename
        for filename in SOURCE_FILES
        if (project_root / filename).exists()
    )
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item.relative_to(project_root))):
        relative = str(path.relative_to(project_root))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _git_value(project_root: Path, *arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_identity(project_root: Path) -> dict[str, Any]:
    commit = _git_value(project_root, "rev-parse", "HEAD")
    branch = _git_value(project_root, "branch", "--show-current")
    status = _git_value(project_root, "status", "--porcelain")
    return {
        "commit": commit,
        "branch": branch or None,
        "dirty": bool(status) if status is not None else None,
    }


def _dependency_versions() -> dict[str, str | None]:
    versions = {}
    for dependency in DEPENDENCIES:
        try:
            versions[dependency] = importlib.metadata.version(dependency)
        except importlib.metadata.PackageNotFoundError:
            versions[dependency] = None
    return versions


def _relative_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path.resolve())


def build_run_provenance(
    *,
    input_path: Path,
    project_root: Path,
    analysis_configuration: dict[str, Any],
) -> dict[str, Any]:
    input_path = input_path.resolve()
    input_hash = sha256_file(input_path)
    configuration_snapshot = json.loads(
        json.dumps(analysis_configuration, sort_keys=True)
    )
    metadata_path = manifest_path_for(input_path)
    manifest_binding = None
    if metadata_path.exists():
        manifest = json.loads(metadata_path.read_text())
        validate_recording_manifest(manifest)
        if manifest["identity"]["sha256"] != input_hash:
            raise ValueError("recording manifest SHA-256 does not match input")
        manifest_binding = {
            "recording_id": manifest["recording_id"],
            "manifest_schema_version": manifest["manifest_schema_version"],
            "manifest_sha256": sha256_file(metadata_path),
            "relative_path": _relative_path(metadata_path, project_root),
        }

    payload = {
        "provenance_schema_version": RUN_PROVENANCE_SCHEMA_VERSION,
        "toolkit": {
            "name": "AVE Forensics Laboratory",
            "version": __version__,
            "source_tree_sha256": _source_tree_sha256(project_root),
        },
        "git": _git_identity(project_root),
        "runtime": {
            "python": sys.version.split()[0],
            "dependencies": _dependency_versions(),
        },
        "input": {
            "relative_path": _relative_path(input_path, project_root),
            "size_bytes": input_path.stat().st_size,
            "hash_algorithm": "sha256",
            "sha256": input_hash,
        },
        "recording_manifest": manifest_binding,
        "analysis_configuration": configuration_snapshot,
    }
    payload["run_id"] = f"ave_run_{_canonical_hash(payload)[:16]}"
    validate_run_provenance(payload)
    return payload


def validate_run_provenance(provenance: dict[str, Any]) -> None:
    required = {
        "provenance_schema_version",
        "run_id",
        "toolkit",
        "git",
        "runtime",
        "input",
        "recording_manifest",
        "analysis_configuration",
    }
    missing = required - provenance.keys()
    if missing:
        raise ValueError(f"missing provenance fields: {', '.join(sorted(missing))}")
    if provenance["provenance_schema_version"] != RUN_PROVENANCE_SCHEMA_VERSION:
        raise ValueError("unsupported provenance schema version")
    if not RUN_ID_PATTERN.match(provenance["run_id"]):
        raise ValueError("invalid run_id")
    input_identity = provenance["input"]
    if input_identity.get("hash_algorithm") != "sha256":
        raise ValueError("unsupported input hash algorithm")
    if not re.fullmatch(r"[0-9a-f]{64}", input_identity.get("sha256", "")):
        raise ValueError("invalid input SHA-256")
    source_hash = provenance["toolkit"].get("source_tree_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        raise ValueError("invalid source tree SHA-256")
    if not isinstance(provenance["analysis_configuration"], dict):
        raise ValueError("analysis_configuration must be an object")
    expected_payload = dict(provenance)
    run_id = expected_payload.pop("run_id")
    expected_run_id = f"ave_run_{_canonical_hash(expected_payload)[:16]}"
    if run_id != expected_run_id:
        raise ValueError("run_id does not match provenance payload")
