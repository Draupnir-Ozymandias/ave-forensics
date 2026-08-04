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

Run the test suite with:

```bash
.venv/bin/python -B -m pytest -q -p no:cacheprovider
```
