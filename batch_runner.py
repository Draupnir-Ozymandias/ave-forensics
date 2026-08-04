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
    arguments = parser.parse_args()

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
    )

    counts = {}
    for result in results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    print(f"Batch corpus entries: {len(results)}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
