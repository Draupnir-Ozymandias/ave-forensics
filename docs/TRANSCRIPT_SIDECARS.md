# Transcript Sidecars

AVE treats speech as contextual evidence. Verbatim commercial transcripts remain
private capture material and never enter the committed corpus, clustering features,
or observed-signal evidence.

## Storage boundary

- Original audio remains under `samples/` and is ignored as commercial media.
- Raw transcription responses belong under `captured/transcripts/` and are ignored
  because they contain verbatim text and may contain cloud account identifiers,
  job names, or storage locations.
- A sanitized `<audio filename>.transcript.json` sidecar lives beside its recording
  and may be committed.

The sanitized sidecar binds the original recording, complete raw response, and
verbatim transcript content to separate SHA-256 digests. It retains the engine,
region, language, model declaration, job settings, text-free speech intervals,
pronunciation timing and confidence, and aggregate coverage statistics. It omits
every recognized word, sentence, provider account identifier, job name, and cloud
storage location.

## Import an AWS Transcribe response

Validate a completed response before writing:

```bash
.venv/bin/python transcript_metadata.py \
  captured/transcripts/brainfm/meditate/guided/recording.json \
  samples/brainfm/meditate/guided/recording.mp3 \
  --region us-east-2 \
  --language-code en-US \
  --media-format mp3 \
  --media-sample-rate-hz 48000 \
  --dry-run
```

Remove `--dry-run` to write the sanitized sidecar. Existing identical outputs are
reported as `unchanged`; a different existing sidecar is protected unless
`--overwrite` is explicit. Optional `--model-name`, job timestamps, and
`--timestamp-timezone` arguments preserve additional provenance when known.

The importer verifies that the response completed, item identifiers are unique,
segment references resolve, time ranges are ordered and bounded by the recording,
confidence values are within 0–1, and declared media format and sample rate match
the original file.

## Interpretation

Speech coverage is based on transcription-provider audio segments. It is not yet a
voice-activity detector and must not be treated as sample-accurate isolation. The
next speech-aware analysis milestone will derive buffered speech-active and
speech-sparse regions while retaining the complete-program analysis as primary
evidence.
