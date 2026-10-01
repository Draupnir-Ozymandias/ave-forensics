# Stage-Classification Robustness

A detector confidence that differs from a support threshold by only a few
decimal places can imply more precision than the measurement procedure earns.
AVE Forensics therefore keeps robustness analysis separate from primary blind
observation and declaration comparison.

## Two-phase method

First, analyze one independently bounded stage without loading a confidence
threshold, expected construction class, or expected rate:

```bash
.venv/bin/python stage_robustness.py analyze \
  /path/to/stereo.wav \
  --start-seconds 5 \
  --end-seconds 10 \
  --output artifacts/stage-robustness-analysis.json
```

The fixed perturbation suite applies symmetric circular time shifts, ±5% gain,
16/20/24-bit quantization, deterministic low-level noise, and 32/48 kHz sample
rate round trips. Every variant is reclassified with the same stage detector.
The analysis records classification stability, confidence range and spread,
per-family variation, rate, duty cycle, configuration, artifact identity, and
run provenance.

Only after the analysis is persisted, compare an external threshold:

```bash
.venv/bin/python stage_robustness.py compare \
  artifacts/stage-robustness-analysis.json \
  --threshold 0.75 \
  --threshold-source "declaration minimum_confidence" \
  --output artifacts/stage-robustness-comparison.json
```

This second phase can label the boundary
`borderline_within_observed_variation`, but it never changes the primary
agreement state automatically.

## Demo 005 result

For the independently detected 5–10 second smooth-AM stage:

- baseline classification is `smooth_amplitude_modulation` at confidence
  `0.749983`;
- all 19 perturbations retain the smooth-AM classification;
- confidence spans `0.749320`–`0.758564`;
- maximum absolute movement from baseline is `0.008581`;
- observed pulse rate spans only `10.022727`–`10.028867` Hz; and
- three of 20 observations, counting baseline plus variants, are at or above
  `0.75`.

The original threshold gap is `0.000017`. Observed confidence movement is over
500 times larger and crosses the threshold, so treating the original decimal
shortfall as a scientifically sharp distinction would be false precision.
Nevertheless, the robustness audit was performed after the primary observation
and does not rewrite it: the two fields remain `unsupported`, not `agree`, and
Demo 005 remains `partially_verified` for the present release.

## Limits

- These are deterministic transformations of one rendered artifact, not
  independent Generator rerenders.
- Circular shifts can introduce one wrap seam, although Demo 005's selected
  stage contains whole modulation and carrier cycles.
- The empirical spread is specific to this detector, artifact, stage, and
  perturbation suite; it is not a universal confidence tolerance.
- Robustness describes measurement stability, not neurological entrainment,
  therapeutic efficacy, subjective benefit, or safety.
