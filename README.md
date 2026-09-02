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

## Generate Per-Recording Metadata Manifests

Create one versioned JSON sidecar beside every supported corpus recording:

```bash
.venv/bin/python recording_manifests.py
.venv/bin/python corpus_index.py
```

Each `<recording>.<extension>.metadata.json` sidecar records SHA-256 identity,
media properties, directory-derived source/category/intent labels, duplicate-file
aliases, and generation provenance. Machine-inferred labels remain separate from
the `curation` block so reviewed human overrides survive later regeneration.

The Corpus Evidence Index automatically validates available sidecars and prefers
their resolved labels while retaining the original batch metadata for auditability.

## Input Hashing and Run Provenance

Every new `main.py` or `batch_runner.py` analysis embeds a validated
`run_provenance` object in `ave_evidence.json`. It binds the evidence to:

- the input file's SHA-256 digest and size;
- the recording manifest ID, schema version, and manifest SHA-256;
- the AVE toolkit version and deterministic source-tree hash;
- the active Git commit, branch, and dirty-worktree state;
- Python and analysis dependency versions; and
- the complete versioned analysis configuration.

The deterministic `ave_run_<digest>` identifier changes whenever any bound input,
manifest, source, dependency, Git state, or analysis parameter changes. The Corpus
Evidence Index reports provenance as `validated`, `legacy_missing`, or `invalid`.
Evidence created before this feature remains explicitly marked as legacy rather
than receiving reconstructed historical provenance.

## Discover Protocol Families

After building the Corpus Evidence Index, discover recurring signal families:

```bash
.venv/bin/python protocol_clustering.py
```

The command writes a validated JSON family document and a flat assignment CSV to
`artifacts/clustering/`. It uses robust-standardized carrier, envelope, shared
modulation, phase, and hypothesis measurements. Provider, category, claimed-intent,
notes, and transcript fields are explicitly excluded. Byte-identical inputs receive
one canonical assignment, and model selection reports silhouette quality so weak
boundaries remain visible. Hypothesis ranking strength is also excluded because its
legacy and current score sources are not directly comparable.

See `docs/CORPUS_CONTEXT_LAYERS.md` for the policy governing provider taxonomy,
guided speech, transcripts, outcome claims, and future generator integration.

## Extract Brain.fm Provider Metadata

Sanitize a raw Brain.fm JSON or HAR capture into one validated provider sidecar per
local recording:

```bash
.venv/bin/python provider_metadata.py /path/to/capture.har \
  --recordings-dir samples/brainfm/meditate/guided
```

For the normal one-capture-per-recording archive, validate and ingest the entire
tree recursively:

```bash
.venv/bin/python provider_metadata.py --batch --dry-run
.venv/bin/python provider_metadata.py --batch
```

The extractor matches exact MP3 variation filenames, deduplicates repeated response
records, rejects conflicts and ambiguous capture basenames, binds outputs to
recording and capture SHA-256 digests, and omits all provider URLs and tokens.
Batch matching works across differing capture/corpus category depths and reports
missing or unmatched packages without blocking valid ones. Existing sidecars are
never replaced unless `--overwrite` is explicit. Raw captures belong under ignored
`captured/` storage; only sanitized `*.provider.json` sidecars should be committed.
See `docs/BRAINFM_CAPTURE_WORKFLOW.md` for the Favorites collection workflow.

## Generate the Reference-Library Comparison Dashboard

Build the Corpus Evidence Index, then generate the local dashboard:

```bash
.venv/bin/python corpus_index.py
.venv/bin/python protocol_clustering.py
.venv/bin/python dashboard.py
```

Open `artifacts/dashboard/index.html` in a browser. The self-contained dashboard
requires no server or network connection. It provides corpus filters, carrier and
modulation distributions, phase and hypothesis comparisons, recording drill-down,
protocol-family profiles, contextual provider-taxonomy filters and summaries, and
filtered CSV/JSON exports. Provider labels remain visibly separate from measured
evidence and are excluded from clustering. When a current clustering artifact
exists, the dashboard validates that it was produced from the exact same Corpus
Evidence Index before displaying any assignment.

Comparison statistics use one canonical recording per SHA-256 input by default so
byte-identical aliases cannot bias the results. Uncheck **Unique inputs** to inspect
every corpus path. Deferred, invalid, duplicate, and legacy-provenance conditions
remain visible as forensic warnings. Dashboard results describe measured signal
relationships; they do not establish physiological effect or vendor intent.
