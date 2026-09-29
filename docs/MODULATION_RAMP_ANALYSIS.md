# Continuous Modulation-Ramp Analysis

This analyzer tracks a changing amplitude-envelope rate in a selected carrier
band. It is the AVE Forensics P2B measurement layer for the
demo portfolio. It does not read a Generator recipe, resolved protocol, or
expected curve while detecting the ridge.

## Method

1. Isolate a caller-specified carrier band with a zero-phase band-pass filter.
2. Extract its analytic amplitude envelope.
3. Resample the envelope above twice the highest permitted modulation rate.
4. Measure a spectral peak in short overlapping windows.
5. Preserve unsupported windows and their failure reasons.
6. Accept a linear ridge only when total coverage, contiguous coverage, and
   goodness-of-fit thresholds are met.

The result records the fitted start and end rates at the first and last
supported window centers, slope, direction, coverage, residual error,
per-window confidence, unsupported intervals, and complete extraction
configuration. A stable modulation is labeled separately from a ramp.

## Command

```bash
.venv/bin/python modulation_ramp.py rendered.wav \
  --carrier-hz 528 \
  --carrier-bandwidth-hz 64 \
  --min-rate-hz 4 \
  --max-rate-hz 20 \
  --envelope-sample-rate 200 \
  --channel left \
  --start-seconds 0 \
  --end-seconds 12 \
  --output-dir artifacts/demo-verification
```

The command writes:

- `ave_modulation_ramp.json` — detailed blind observation and run provenance;
- `ave_modulation_ramp_evidence.json` — canonical AVE evidence document.

Choose a carrier bandwidth wide enough to retain the modulation sidebands. The
analyzer intentionally does not infer the band from a Generator declaration.
For a published demo, document how the carrier was independently selected or
analyze an isolated, declared stem while retaining that scope limitation.
The optional time bounds retain original source timestamps in every window and
in the canonical evidence scope, which permits bounded stage analysis without
creating an identity-ambiguous excerpt.

## Evidence boundary

This module does **not** decide whether the tracked envelope is sinusoidal,
otherwise smooth, or hard-gated. A continuous rate ridge describes continuity
of the measured rate track, not waveform shape. Duty cycle and isochronic-pulse
classification remain the responsibility of `analysis.pulse`. A later
agreement report may compare this observation with a
Generator declaration by hash and tolerance, but the declaration is never
embedded as detector input.

Signal agreement does not establish neural entrainment, efficacy, therapeutic
benefit, subjective outcome, or exposure safety.
