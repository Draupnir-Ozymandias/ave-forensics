# Independent four-region Vitality render validation

Date: 2026-10-10. Status: complete working-tree engineering validation.
Recommended evidence label: **partially_verified**, subject to Platform label
assignment. Generator's initial package label remains `exploratory`.

## Input and ordering

Analyzed the complete
[/Users/eric/Projects/media/ave_generator/output/four-region-replication-300s/four-region-300s.mp4](../ave_generator/output/four-region-replication-300s/four-region-300s.mp4).
MP4 SHA-256:
`ec3bcf1ffbf79250cdf407f9c88b7d91a352cba5171e7f09d91a4f16f711091e`.
This matches both the final Generator manifest and verification request after
Generator's packaging rerender. No recipe, resolved plan, or schedule target
was loaded by the detector. The observation and compressed pixel traces were
persisted before loading the recipe for comparison.

The first 64-pixel decode confirmed cadence but blurred gutters into one spatial
component. The retained final observation uses 128-pixel analysis and a
half-observed-peak geometry threshold with a 0.02 floor. The correction concerns
pixel geometry; it introduces no schedule targets. Both earlier and final
observations are preserved under `artifacts/four-region-replication-300s/`.

## Observed result

| Field | Measurement | Result and scope |
| --- | --- | --- |
| Duration | 300.000 seconds, 36,000 decoded frames | `agree` with declared duration |
| Cadence | 120 fps; PTS begins at 0, last frame begins at 299.991667 s | `agree`; no non-increasing timestamps or cadence outliers; maximum deviation from one frame period is 0.667 microseconds in rounded ffprobe timestamps |
| Geometry | Four separated bright components named top-left/right and bottom-left/right | `agree` with four-region layout; detected from pixels |
| Matched gates | Zero frames with region disagreement | `agree` at frame resolution; four timing traces match on every frame |
| Threshold robustness | Rising/falling edge lists identical at 10%, 25%, and 50% of each trace's observed peak | Edges stable over the tested thresholds |
| Rectangular gates | 3,090 illuminated runs/rising edges per region | `agree` with a frame-sampled gated-light program |
| Opening blackout | Entire 0–1.5 s interval is dark | `agree` |
| Closing blackout | Entire declared 298–300 s interval is dark | `agree`; the last illuminated frame ends at 297.8 s, which is compatible with narrow terminal gates |
| Declared sampled schedule | Analytic integration of recipe curves compared with saved decoded gates | All 136 region intervals (34 × 4) `agree`; zero gate-state mismatches |
| Continuous duty/frequency replication | 71 of 3,161 analytic gate starts have no illuminated sample | `unsupported` as an exact continuous waveform replication claim; supported only as the declared 120 fps sampling |
| Physical/subframe phase, optical duty/luminance, Nova equivalence | No physical output measurements | `unsupported` |

The schedule comparison independently integrates constant/linear frequency
curves using rational arithmetic, applies declared phase policy and duty at
frame sample times, then compares with the already persisted pixel traces.
It does not call Generator's compiler or use the resolved plan as an observer.
This is a comparison against a declaration, not blind recovery of all 34
boundaries from pixels. Five-second sliding rate/duty measurements were also
persisted during detection; very short or undersampled intervals cannot support
high-precision instantaneous reconstruction.

For the declared constant 10.5 Hz / 0.20-duty interval at 37–56 s, the decoded
edge estimate is approximately 10.499337 Hz and encoded duty is 0.199561. Narrow
gates elsewhere distort observable edge counts: for example, the 171–177 s
interval yields about 9.830508 Hz, despite agreement with the correctly sampled
declared gate. Frequency and duty should therefore be reported with their
sampling and interval scope, not asserted as uniformly recovered at high
precision throughout the program.

The independently computed 71 gate starts without on frames agree with
Generator's separately read quantization diagnostic. That agreement does not
remove the sampling limitation. A higher frame rate or a different declared
frame-exposure model would require a new render and independent validation.

## Reproduction and artifacts

```bash
.venv/bin/python streaming_video.py \
  /Users/eric/Projects/media/ave_generator/output/four-region-replication-300s/four-region-300s.mp4 \
  --output-dir artifacts/four-region-replication-300s/observation-v2

# Run only after the observation above has persisted.
.venv/bin/python compare_streaming_video.py \
  artifacts/four-region-replication-300s/observation-v2/observation.json \
  /Users/eric/Projects/media/ave_generator/output/four-region-replication-300s/recipe.json \
  --output artifacts/four-region-replication-300s/observation-v2/comparison.json
```

- Observation: `artifacts/four-region-replication-300s/observation-v2/observation.json`
- Traces and all frame timestamps: sibling `pixel-traces.npz`
- Post-observation per-interval results: sibling `comparison.json`
- Recipe file SHA-256:
  `ad17b27b1f70c5bc797ba517ac315497a8bea81db6f07c3eb7cd268226bd9508`

These custom audit records are not an `ave-demo-agreement-report@0.1.0` portfolio
report: this new render has no stable portfolio declaration identity or
schema-normalized claim set. Platform can consume this scoped engineering audit
now; a formal portfolio release needs Generator's declaration handoff and a
clean-source rerun. Both Generator and the new Forensics implementation are
currently recorded with working-tree changes; the media is hash-verified but
has not earned clean release provenance.

## Capture limits and next action

The full schedule comes from Lumenate's reviewed 34-interval replication brief.
Matched-region timing is evidence-supported within camera resolution. Generator
owns the selected phase continuity, screen layout/color/intensity, and refresh
rate. Screen pixels do not establish the captured device's subframe phase,
optical duty, calibrated intensity, latency, exposure safety, or therapeutic
effects. Keep the warnings and blackout/player-stop instructions with the
package.

Platform can now review or copy the final hashed MP4 and this report. Forensics
recommends `partially_verified` with the explicit narrow-pulse sampling limit;
exact physical replication remains unsupported. Any public promotion should
retain those limits and resolve source-provenance/declaration requirements.
