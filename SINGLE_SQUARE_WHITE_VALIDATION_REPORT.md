# Independent white/black single-square validation

Date: 2026-10-10. Status: completed independent full-video audit.
Recommended label: **partially_verified**, subject to Platform assignment.
Generator's initial label remains `exploratory`.

## Final media identity

Analyzed the entire
[single-square-white-300s.mp4](../ave_generator/output/single-square-white-300s/single-square-white-300s.mp4)
in `/Users/eric/Projects/media/ave_generator/output/single-square-white-300s`.
Actual MP4 SHA-256:
`5e3f6732715194039bec1176e0fedbf8309fca1ceb293068c1e120139657919a`.
This matches the final Generator manifest output entry after rendering.

The detector consumed only the MP4, discovered spatial geometry, and measured
RGB, brightness-state transitions, quadrant medians and every frame timestamp.
It persisted observations and traces before the base timing recipe and visual
treatment were read. The subsequent comparison independently integrated the
declared frequency/duty curves; it used neither Generator compiler output nor
resolved-plan gate flags as observations. No video was autoplayed.

## Measurements and comparison

| Field | Decoded observation | Result |
| --- | --- | --- |
| Duration/count | 300.000 seconds, 36,000 frames | `agree` |
| Cadence | 120 fps; frame PTS 0 to 299.991667 s | `agree`; no non-increasing timestamps or cadence outliers |
| Timestamp precision | Maximum frame-period deviation 0.667 microseconds in rounded ffprobe timestamps | Encoded CFR supported; physical display cadence unmeasured |
| Canvas/layout | 640×640; one connected square spanning the analysis canvas; aspect ratio 1.0 | Single square/no gutters supported |
| Interior uniformity | Four quadrant medians equal on every frame; maximum difference 0 RGB codes | No internal quadrant color pattern at tested resolution |
| White | 8,467 frames; observed RGB center/peak [253,253,253] | Matches declared [255,255,255] within codec error |
| Black | 27,533 frames; observed RGB [0,0,0] | Matches declared pulse-OFF black |
| Color neutrality | Maximum channel spread 0 in measured RGB medians | Achromatic output supported |
| Gate timing | Zero black/nonblack mismatches over all 36,000 frames against independently integrated original Vitality curves | `agree` under the declared frame sampling |
| Pulse visibility | 3,090 white runs; 71 of 3,161 analytic cycle IDs have no white sample | Continuous pulse visibility remains incomplete |
| RGB model | Maximum error 2 codes from declared white/black; no frames exceed 3-code diagnostic threshold | Consistent with lossy H.264 |

The source opening 0–1.5 s and closing 298–300 s intervals are entirely black.
During the active program, each sampled gate-OFF frame is also black. Thus this
output restores an encoded white-on/black-off gated-light structure, replacing
the earlier complementary-color switching treatment. The original frequency,
duty and accumulated phase agree with recovered state timing at sample times.

The 120 fps frame interval is 8.333 ms. Narrow analytic on-windows can fall
between samples; the 71 missed gates were measured from the independent
declared-curve comparison. This limits claims of continuous frequency/duty
replication, even though every represented frame matches the sampled schedule.
Full-rate physical playback and optical timing were not measured.

## Saved evidence and reproduction

```bash
.venv/bin/python single_square_white_video.py observe \
  /Users/eric/Projects/media/ave_generator/output/single-square-white-300s/single-square-white-300s.mp4 \
  --output-dir artifacts/single-square-white-300s

# Run only after observation has persisted.
.venv/bin/python single_square_white_video.py compare \
  artifacts/single-square-white-300s/observation.json \
  /Users/eric/Projects/media/ave_generator/output/single-square-white-300s/base-timing-recipe.json \
  --output artifacts/single-square-white-300s/comparison.json
```

Evidence under `artifacts/single-square-white-300s/`:

- `observation.json`: discovered geometry, RGB summaries, spatial uniformity,
  black/nonblack transitions/windows, timestamps, artifact identity, detector
  configuration and run provenance.
- `traces.npz`: full median RGB, state sequence and PTS.
- `comparison.json`: independent frame-gate and RGB comparison, missed cycle
  IDs, and observation/artifact/base-recipe hashes.

Base timing recipe SHA-256:
`ad17b27b1f70c5bc797ba517ac315497a8bea81db6f07c3eb7cd268226bd9508`.
The full Forensics suite passes **164 tests**, including independent monochrome
gate recovery and spatial/channel neutrality checks.

## Limits and release handoff

Spatial checks use median samples at 128×128 analysis resolution; isolated
full-resolution pixel defects remain outside that measurement. White RGB and
software intensity are not calibrated luminance, optical duty or exposure
safety measurements. Screen timing does not establish Nova equivalence,
subframe phase, neurological entrainment or therapeutic efficacy.

These custom reports are scoped audits rather than a stable-ID portfolio
agreement report. New Generator and Forensics workflows carry working-tree
provenance. Clean-source provenance, formal declaration and Platform review
remain release dependencies. The final hashed MP4 is ready for that review with
its narrow-pulse limit and existing warning package retained. Previous
grayscale, vibrant and green/magenta variants were preserved.
