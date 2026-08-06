# AVE Forensics Laboratory

AVE analyzes audio-visual entrainment recordings and exports measurement reports,
timelines, reconstructed protocol hypotheses, and canonical evidence objects.

## Analyze one recording

```bash
.venv/bin/python main.py "/path/to/recording.mp3" --output-dir artifacts/single-run
```

## Analyze the reference corpus

Preview the corpus without performing analysis:

```bash
.venv/bin/python batch_runner.py --dry-run
```

Run every recording found under `samples/`:

```bash
.venv/bin/python batch_runner.py
```

Each recording receives an isolated directory under `artifacts/batch/`. The runner
writes `batch_summary.json` after every recording, captures `console.log` and
`errors.log`, and skips directories containing `ave_evidence.json` when resumed.

Useful controls:

- `--limit N` analyzes only the first N corpus entries.
- `--no-resume` reruns recordings that already have evidence output.
- `--manifest-only` excludes recordings not represented in `samples/manifest.csv`.
- `--samples-root`, `--manifest`, and `--output-root` override default paths.
- `--exclude '*pattern*'` explicitly excludes matching corpus paths and records them.
- `--max-duration-minutes N` defers longer recordings (default: 60 minutes).
- `--timeout-minutes N` stops one slow analysis and continues (default: 180 minutes).

Deferred and excluded recordings remain visible in `batch_summary.json`. Use `0` for
either time limit to disable it deliberately.

Run the test suite with:

```bash
.venv/bin/python -B -m pytest -q -p no:cacheprovider
```

## Build the Corpus Evidence Index

After a batch run, consolidate every recording and validated evidence document:

```bash
.venv/bin/python corpus_index.py
```

The command writes `artifacts/corpus/corpus_index.json` for complete structured
analysis and `artifacts/corpus/corpus_index.csv` for comparison, filtering, and
dashboard work. Each row preserves batch status, source metadata, duration,
SHA-256 input identity, evidence counts, dominant signal relationships, phase
behavior, and the top protocol hypothesis. Deferred and invalid recordings remain
visible rather than disappearing from the corpus.

Use `--no-hash` only for a provisional index when input hashing is unnecessary.
