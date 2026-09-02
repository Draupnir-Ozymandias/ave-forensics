import argparse
from collections import Counter
from pathlib import Path

from provider.brainfm import (
    ProviderMetadataError,
    extract_brainfm_capture_tree,
    extract_brainfm_sidecars,
    write_brainfm_capture_tree,
    write_provider_sidecars,
)


def _print_sidecar(output_path, sidecar, action: str) -> None:
    track = sidecar["provider_track"]
    measurements = sidecar["provider_measurements"]
    print(
        f"  {track['title']} — {measurements['neural_effect_level']} NEL "
        f"— {action}: {output_path}"
    )


def _run_batch(arguments: argparse.Namespace, project_root: Path) -> None:
    captures_root = arguments.captures_root or project_root / "captured" / "brainfm"
    recordings_root = arguments.recordings_dir or project_root / "samples" / "brainfm"
    entries = extract_brainfm_capture_tree(captures_root, recordings_root)
    counts = Counter(entry.status for entry in entries)
    paths = (
        []
        if arguments.dry_run
        else write_brainfm_capture_tree(entries, overwrite=arguments.overwrite)
    )
    print(f"Brain.fm batch entries: {len(entries)}")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")
    for entry in entries:
        if entry.status not in {
            "ambiguous_capture",
            "invalid_capture",
            "stale_sidecar",
            "unmatched_capture",
        }:
            continue
        subject = entry.capture_path or entry.recording_path
        print(f"  {entry.status}: {subject} — {entry.message}")
    action = "validated" if arguments.dry_run else "written"
    for entry in entries:
        if entry.status == "ready" and entry.output_path and entry.sidecar:
            _print_sidecar(entry.output_path, entry.sidecar, action)
        elif (
            arguments.overwrite
            and entry.status == "stale_sidecar"
            and entry.output_path
            and entry.sidecar
        ):
            _print_sidecar(entry.output_path, entry.sidecar, action)
    if not arguments.dry_run:
        print(f"Provider sidecars written: {len(paths)}")


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Extract safe Brain.fm provider metadata sidecars from a capture."
    )
    parser.add_argument(
        "capture",
        type=Path,
        nargs="?",
        help="One JSON/HAR capture (omit when using --batch).",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Recursively pair a capture tree with the Brain.fm recording corpus.",
    )
    parser.add_argument(
        "--captures-root",
        type=Path,
        help="Batch capture tree (default: captured/brainfm).",
    )
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        help=(
            "Single-capture recording directory, or batch corpus root "
            "(defaults depend on mode)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report matches without writing sidecars.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Batch mode only: replace stale or invalid existing sidecars.",
    )
    arguments = parser.parse_args()
    if arguments.batch:
        if arguments.capture is not None:
            parser.error("capture cannot be combined with --batch")
        _run_batch(arguments, project_root)
        return
    if arguments.capture is None:
        parser.error("capture is required unless --batch is used")
    if arguments.captures_root is not None:
        parser.error("--captures-root requires --batch")
    if arguments.overwrite:
        parser.error("--overwrite requires --batch")
    recordings_directory = (
        arguments.recordings_dir
        or project_root / "samples" / "brainfm" / "meditate" / "guided"
    )
    sidecars = extract_brainfm_sidecars(arguments.capture, recordings_directory)
    paths = [] if arguments.dry_run else write_provider_sidecars(sidecars)
    print(f"Provider records matched: {len(sidecars)}")
    for output_path, sidecar in sidecars:
        action = "validated" if arguments.dry_run else "written"
        _print_sidecar(output_path, sidecar, action)
    if paths:
        print(f"Provider sidecars written: {len(paths)}")


if __name__ == "__main__":
    try:
        main()
    except ProviderMetadataError as error:
        raise SystemExit(f"Provider metadata error: {error}") from error
