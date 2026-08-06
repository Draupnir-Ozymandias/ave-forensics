from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import soundfile as sf

from core.hashing import sha256_file
from core.media import AUDIO_EXTENSIONS


MANIFEST_SCHEMA_VERSION = "1.0.0"
RECORDING_ID_PATTERN = re.compile(r"^ave_recording_[0-9a-f]{16}$")


class RecordingManifestError(ValueError):
    """Raised when a recording metadata manifest is invalid."""


def manifest_path_for(recording_path: Path) -> Path:
    return recording_path.with_name(f"{recording_path.name}.metadata.json")


def _inferred_labels(relative_path: Path) -> dict[str, str]:
    parts = relative_path.parts
    return {
        "source": parts[0] if parts else "unknown",
        "category": parts[1] if len(parts) > 1 else "unknown",
        "claimed_intent": parts[2] if len(parts) > 2 else "unknown",
        "basis": "corpus_directory_structure",
    }


def _media_properties(path: Path) -> dict[str, Any]:
    info = sf.info(path)
    return {
        "container_extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(float(info.duration), 6),
        "sample_rate": int(info.samplerate),
        "channels": int(info.channels),
        "frame_count": int(info.frames),
        "codec_subtype": info.subtype,
    }


def validate_recording_manifest(manifest: dict[str, Any]) -> None:
    required = {
        "manifest_schema_version",
        "recording_id",
        "relative_path",
        "identity",
        "media",
        "inferred_labels",
        "curation",
        "duplicates",
        "provenance",
    }
    missing = required - manifest.keys()
    if missing:
        raise RecordingManifestError(
            f"missing required fields: {', '.join(sorted(missing))}"
        )
    if manifest["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise RecordingManifestError("unsupported manifest_schema_version")
    if not RECORDING_ID_PATTERN.match(manifest["recording_id"]):
        raise RecordingManifestError("invalid recording_id")

    identity = manifest["identity"]
    input_hash = identity.get("sha256") if isinstance(identity, dict) else None
    if not isinstance(input_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", input_hash):
        raise RecordingManifestError("identity.sha256 must be a SHA-256 digest")
    if identity.get("hash_algorithm") != "sha256":
        raise RecordingManifestError("unsupported hash algorithm")

    media = manifest["media"]
    for field in ("size_bytes", "duration_seconds", "sample_rate", "channels"):
        if not isinstance(media.get(field), (int, float)) or media[field] <= 0:
            raise RecordingManifestError(f"media.{field} must be positive")

    labels = manifest["inferred_labels"]
    for field in ("source", "category", "claimed_intent", "basis"):
        if not isinstance(labels.get(field), str) or not labels[field]:
            raise RecordingManifestError(f"inferred_labels.{field} is required")

    curation = manifest["curation"]
    if curation.get("review_status") not in {"unreviewed", "reviewed"}:
        raise RecordingManifestError("invalid curation.review_status")
    for field in ("source_override", "category_override", "claimed_intent_override"):
        value = curation.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise RecordingManifestError(f"curation.{field} must be null or text")

    duplicates = manifest["duplicates"]
    if not isinstance(duplicates.get("matching_relative_paths"), list):
        raise RecordingManifestError(
            "duplicates.matching_relative_paths must be a list"
        )


def resolved_labels(manifest: dict[str, Any]) -> dict[str, str]:
    inferred = manifest["inferred_labels"]
    curation = manifest["curation"]
    return {
        "source": curation.get("source_override") or inferred["source"],
        "category": curation.get("category_override") or inferred["category"],
        "claimed_intent": (
            curation.get("claimed_intent_override")
            or inferred["claimed_intent"]
        ),
        "label_source": (
            "curated_override"
            if any(
                curation.get(field)
                for field in (
                    "source_override",
                    "category_override",
                    "claimed_intent_override",
                )
            )
            else inferred["basis"]
        ),
    }


def build_recording_manifests(samples_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    recordings = sorted(
        path
        for path in samples_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    hashes = {path: sha256_file(path) for path in recordings}
    paths_by_hash: dict[str, list[Path]] = defaultdict(list)
    for path, input_hash in hashes.items():
        paths_by_hash[input_hash].append(path)

    manifests = []
    for recording_path in recordings:
        relative_path = recording_path.relative_to(samples_root)
        input_hash = hashes[recording_path]
        output_path = manifest_path_for(recording_path)
        existing_curation = None
        if output_path.exists():
            try:
                existing = json.loads(output_path.read_text())
                existing_curation = existing.get("curation")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                existing_curation = None

        curation = {
            "review_status": "unreviewed",
            "source_override": None,
            "category_override": None,
            "claimed_intent_override": None,
            "notes": "",
        }
        if isinstance(existing_curation, dict):
            curation.update(existing_curation)
        matching_paths = sorted(
            str(path.relative_to(samples_root))
            for path in paths_by_hash[input_hash]
            if path != recording_path
        )
        manifest = {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "recording_id": f"ave_recording_{input_hash[:16]}",
            "relative_path": str(relative_path),
            "identity": {
                "hash_algorithm": "sha256",
                "sha256": input_hash,
            },
            "media": _media_properties(recording_path),
            "inferred_labels": _inferred_labels(relative_path),
            "curation": curation,
            "duplicates": {
                "is_duplicate": bool(matching_paths),
                "matching_relative_paths": matching_paths,
            },
            "provenance": {
                "generator": "corpus.manifests",
                "generator_version": MANIFEST_SCHEMA_VERSION,
                "source": "local_corpus_file",
            },
        }
        validate_recording_manifest(manifest)
        manifests.append((output_path, manifest))
    return manifests


def write_recording_manifests(
    manifests: list[tuple[Path, dict[str, Any]]],
) -> list[Path]:
    output_paths = []
    for output_path, manifest in manifests:
        output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        output_paths.append(output_path)
    return output_paths
