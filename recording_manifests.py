import argparse
from pathlib import Path

from corpus.manifests import build_recording_manifests, write_recording_manifests


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Generate deterministic metadata sidecars for AVE recordings."
    )
    parser.add_argument(
        "--samples-root",
        type=Path,
        default=project_root / "samples",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report manifests without writing sidecars.",
    )
    arguments = parser.parse_args()

    manifests = build_recording_manifests(arguments.samples_root)
    duplicate_count = sum(
        manifest["duplicates"]["is_duplicate"] for _, manifest in manifests
    )
    if not arguments.dry_run:
        write_recording_manifests(manifests)
    action = "Validated" if arguments.dry_run else "Wrote"
    print(f"{action} recording manifests: {len(manifests)}")
    print(f"Recordings with byte-identical aliases: {duplicate_count}")


if __name__ == "__main__":
    main()
