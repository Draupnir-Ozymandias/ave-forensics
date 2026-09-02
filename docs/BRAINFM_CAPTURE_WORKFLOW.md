# Brain.fm Favorites Metadata Capture

AVE can extract provider taxonomy from either concatenated JSON response bodies or
a browser HAR capture. Raw captures are treated as sensitive working material
because request headers and expiring audio URLs may be present. They must not be
committed.

## Capture many Favorites in one pass

1. Open the browser's developer tools and select **Network**.
2. Enable **Preserve log**, clear the existing log, and optionally filter to
   `Fetch/XHR` traffic.
3. Open Brain.fm Favorites.
4. Click each desired track and allow its player/metadata request to finish before
   moving to the next track. Download or otherwise preserve the matching original
   MP3 separately.
5. Export the network log as **HAR with content**.
6. Save the HAR beneath `captured/brainfm/`, which is ignored by Git.

Treat the HAR like a temporary credential even if the browser says it sanitized
the export. Do not edit it, publish it, or place it in a commit.

## Extract sanitized sidecars

For individual per-track captures stored beneath `captured/brainfm/`, first audit
the complete tree without writing anything:

```bash
.venv/bin/python provider_metadata.py --batch --dry-run
```

When the report contains no unexpected `invalid_capture`, `ambiguous_capture`, or
`unmatched_capture` entries, generate the sanitized sidecars:

```bash
.venv/bin/python provider_metadata.py --batch
```

The batch command pairs capture basenames to audio stems across the Brain.fm corpus,
then confirms the exact MP3 variation filename inside every payload. This allows a
capture directory such as `captured/brainfm/focus/` to feed recordings in more
specific sample directories without inferring taxonomy from folder placement.
`missing_capture` entries document older or intentionally incomplete recordings and
do not block valid packages. A repeated run reports current outputs as `unchanged`;
different existing sidecars are protected unless `--overwrite` is supplied.

For a single multi-recording capture, run the extractor against that file and the
directory containing its recordings:

```bash
.venv/bin/python provider_metadata.py \
  captured/brainfm/favorites.har \
  --recordings-dir samples/brainfm/meditate/guided
```

Use `--dry-run` first when checking a new capture. The extractor:

- reads JSON responses embedded in HAR files or concatenated raw JSON;
- joins provider records to local audio by exact variation filename;
- collapses repeated identical catalog and track-load records;
- rejects conflicting records or missing local matches;
- omits every provider URL and access token;
- hashes the original audio and capture; and
- writes one validated `<audio filename>.provider.json` sidecar.

The sanitized sidecar may be committed. It preserves provider labels as contextual
claims, separate from AVE's observed-signal evidence.
