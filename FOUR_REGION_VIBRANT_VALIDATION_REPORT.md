# Independent vibrant four-region video validation

Date: 2026-10-10. Status: completed independent pixel audit of the final MP4.
Recommended label: **partially_verified**, subject to Platform assignment and
release provenance requirements. Generator's initial label is `exploratory`.

## Media identity and observation ordering

Media: [four-region-vibrant-300s.mp4](../ave_generator/output/four-region-vibrant-300s/four-region-vibrant-300s.mp4)
under `/Users/eric/Projects/media/ave_generator/output/four-region-vibrant-300s`.
SHA-256:
`579cfb266f88c7ee4eb3e83bb95a3d89d44a44cb8b230c6abb29a33af6b305e5`.
The actual file hash matches the final manifest output entry after rendering.

The full video was decoded twice at 128×128 analysis resolution to discover
spatial areas and extract per-region RGB traces. All timestamps were inspected.
The detector accepted only the MP4; it loaded no recipe, palette, sweep order,
or target schedule. It persisted `observation.json` and `rgb-traces.npz` before
the recipe and visual-treatment declarations were read for comparison.
Region emphasis was independently inferred using RGB energy relative to each
region's 25th-percentile active energy, with a 5% separation requirement.

## Measurements and comparisons

| Property | Actual decoded result | Engineering result |
| --- | --- | --- |
| Duration/cadence | 300.000 s, 36,000 frames, 120 fps | `agree` |
| Timestamps | 0 to 299.991667 s frame starts; no non-increasing PTS or cadence outliers | `agree`; maximum frame-period deviation 0.667 microseconds in rounded ffprobe timestamps |
| Spatial layout | Four separated bright components in a 2×2 arrangement | `agree` |
| Shared gates | Zero frames with gate differences among quadrants | `agree` at encoded-frame resolution |
| Gate curves | Independent analytic integration of declared constant/linear frequency curves reproduces all observed gates | Zero mismatches across all four region traces |
| Visible pulses | 3,090 rising edges per region at each of three fixed thresholds | Robust over thresholds 0.01, 0.02, and 0.05 of RGB maximum-channel strength |
| Sweep | Every one of 3,090 inferred visible pulse highlights matches declared analytic-cycle modulo four | `agree`: top-left → top-right → bottom-right → bottom-left |
| Color | Maximum median-region RGB error 3 code levels; mean absolute error 0.303741 | Compatible with declared palette/white-mix under lossy H.264; no frames exceed the 3-code diagnostic threshold |
| Narrow pulses | 69 analytic cycles are absent between visible pulse observations; final visible cycle is 3158 | Continuous pulse visibility remains incomplete |
| Physical replication | No optical measurements of playback | Physical brightness, phase, duty, exposure safety, and Nova equivalence remain `unsupported` |

The source program contains 3,161 analytic gate starts (cycles 0–3160).
There are 69 unseen cycles between visible pulses and two after the last visible
pulse, retaining the 71 missed-gate limitation of the original frame-sampled
replication. Highlight advancement follows analytic cycle IDs even when a
pulse has no on-frame. Consequently some consecutive visible highlights skip
one or more quadrants; all observed skips agree with the declared pulse cycle,
and do not establish a sweep error. One full clockwise lap spans four pulses,
not a rotation hidden within a single pulse's on-window.

## Color evidence

The table separates declared base RGB from decoded typical and peak values.
Peaks include the synthetic 45% white-mix highlight. No calibrated luminance
claim follows from these RGB measurements.

| Region | Declared base RGB | Decoded typical RGB (active 25th percentile) | Decoded per-channel peak RGB |
| --- | --- | --- | --- |
| Top-left | [255, 80, 20] | [253, 80, 19] | [254, 158, 124] |
| Top-right | [40, 160, 255] | [39, 158, 254] | [134, 201, 254] |
| Bottom-right | [220, 80, 255] | [218, 80, 253] | [235, 158, 254] |
| Bottom-left | [120, 255, 80] | [118, 254, 79] | [179, 254, 159] |

The visual treatment increases software intensity to 1.0 relative to the
earlier 0.25 grayscale preview. The decoded colors support the vibrant palette
and pulse-linked white-mix emphasis. They do not reproduce captured Lumenate
color, brightness, or independent-region behavior: those are Generator choices.

## Reproduction and saved evidence

```bash
.venv/bin/python vibrant_video.py \
  /Users/eric/Projects/media/ave_generator/output/four-region-vibrant-300s/four-region-vibrant-300s.mp4 \
  --output-dir artifacts/four-region-vibrant-300s

# Execute only after observations above have persisted.
.venv/bin/python compare_vibrant_video.py \
  artifacts/four-region-vibrant-300s/observation.json \
  /Users/eric/Projects/media/ave_generator/output/four-region-vibrant-300s/recipe.json \
  /Users/eric/Projects/media/ave_generator/output/four-region-vibrant-300s/visual-treatment.json \
  --output artifacts/four-region-vibrant-300s/comparison.json
```

Saved evidence under `artifacts/four-region-vibrant-300s/`:

- `observation.json`: geometry, color summaries, edge traces, blind emphasis,
  complete PTS audit, media hash, detector configuration, and run provenance.
- `rgb-traces.npz`: all 36,000 RGB samples for four regions and timestamps.
- `comparison.json`: independent gate and analytic sweep comparison, declared
  palette comparison, artifact/recipe/treatment/observation hashes.

Recipe SHA-256:
`03116d99be9ff99f45dd1c350baf6be998fa9d34051b2dad31db137a69096425`.
Treatment SHA-256:
`ad91d5c9eb0bc4071a0cc80f0a7014b8d445fa41bb7136e65401cff823cb9559`.

The independent comparison uses rational integration of recipe curves and a
separate RGB model. It does not import Generator's renderer/compiler or treat
the resolved plan as a pixel observation. These custom reports are scoped audit
records, not a stable-ID `ave-demo-agreement-report@0.1.0` release declaration.

Validation: the full Forensics suite passes **162 tests**, including matched
color-gate/clockwise-highlight recovery and integrated-ramp phase checks.
New Forensics sources and Generator workflow currently carry working-tree
changes. Clean provenance and a formal declaration remain release dependencies.

## Recommendation

The brighter render and clockwise pulse highlight pass encoded-media validation
under the declared frame-sampling model. Retain the narrow-gate visibility limit
and existing warnings. Platform may review the final hashed media and assign a
scoped `partially_verified` label; no claim of physical equivalence, entrainment,
therapeutic efficacy, or exposure safety is supported. The original grayscale
render and accepted demo portfolio were preserved.
