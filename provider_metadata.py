import argparse
from pathlib import Path

from provider.brainfm import extract_brainfm_sidecars, write_provider_sidecars


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Extract safe Brain.fm provider metadata sidecars from a capture."
    )
    parser.add_argument("capture", type=Path)
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        default=project_root / "samples" / "brainfm" / "meditate" / "guided",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report matches without writing sidecars.",
    )
    arguments = parser.parse_args()
    sidecars = extract_brainfm_sidecars(arguments.capture, arguments.recordings_dir)
    paths = [] if arguments.dry_run else write_provider_sidecars(sidecars)
    print(f"Provider records matched: {len(sidecars)}")
    for output_path, sidecar in sidecars:
        track = sidecar["provider_track"]
        measurements = sidecar["provider_measurements"]
        action = "validated" if arguments.dry_run else "written"
        print(
            f"  {track['title']} — {measurements['neural_effect_level']} NEL "
            f"— {action}: {output_path}"
        )
    if paths:
        print(f"Provider sidecars written: {len(paths)}")


if __name__ == "__main__":
    main()
