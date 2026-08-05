import argparse
from pathlib import Path

from batch.corpus_runner import run_corpus


def main() -> None:
    project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Analyze an AVE reference corpus with isolated outputs."
    )
    parser.add_argument(
        "--samples-root",
        type=Path,
        default=project_root / "samples",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=project_root / "samples" / "manifest.csv",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=project_root / "artifacts" / "batch",
    )
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Exclude matching corpus paths; may be supplied more than once.",
    )
    parser.add_argument(
        "--max-duration-minutes",
        type=float,
        default=60.0,
        help="Defer recordings longer than this limit; use 0 to disable.",
    )
    parser.add_argument(
        "--timeout-minutes",
        type=float,
        default=180.0,
        help="Stop one analysis after this limit; use 0 to disable.",
    )
    arguments = parser.parse_args()

    max_duration_seconds = (
        arguments.max_duration_minutes * 60.0
        if arguments.max_duration_minutes > 0
        else None
    )
    timeout_seconds = (
        arguments.timeout_minutes * 60.0
        if arguments.timeout_minutes > 0
        else None
    )

    results = run_corpus(
        project_root=project_root,
        samples_root=arguments.samples_root,
        manifest_path=arguments.manifest,
        output_root=arguments.output_root,
        include_discovered=not arguments.manifest_only,
        resume=not arguments.no_resume,
        dry_run=arguments.dry_run,
        limit=arguments.limit,
        progress=lambda message: print(message, flush=True),
        exclude_patterns=tuple(arguments.exclude),
        max_duration_seconds=max_duration_seconds,
        timeout_seconds=timeout_seconds,
    )

    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print(f"Batch corpus entries: {len(results)}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
