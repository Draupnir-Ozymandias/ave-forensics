# Independent single-square green/magenta validation

Date: 2026-10-10. Status: complete working-tree encoded-media audit.
Recommended label: **partially_verified**, subject to Platform assignment.
Generator's initial label remains `exploratory`.

## Artifact and ordering

Analyzed the entire
[single-square-green-magenta-300s.mp4](../ave_generator/output/single-square-green-magenta-300s/single-square-green-magenta-300s.mp4).
Final MP4 SHA-256:
`98c596729ff6c26a2fb9b28ff3557d6f8e90626bc505dc5081a37d0fe0ba3274`.
The actual file hash matches the final manifest output entry.

The detector consumed only the MP4, discovered one connected bright area, and
measured its RGB and four interior quadrant medians through the complete video.
Two dominant nonblack color clusters were inferred from decoded pixels. The
observation and full color/timestamp traces were persisted before loading the
base timing recipe or visual treatment. Comparison then integrated the source
frequency curves independently with rational arithmetic. No Generator compiler
or resolved-plan gate flags were used as observations.

## Results

| Field | Independent measurement | Comparison |
| --- | --- | --- |
| Duration | 300.000 seconds, 36,000 decoded frames | `agree` |
| Canvas | 640×640, one connected square spanning the analysis canvas; aspect ratio 1.0 | `agree` with single square/no gutters |
| Interior uniformity | Four quadrant medians match exactly on every frame; maximum RGB difference 0 | Supports no internal color divisions at the tested spatial resolution |
| CFR timing | 120 fps; PTS from 0 to 299.991667 s; zero non-increasing timestamps or cadence outliers | `agree`; maximum frame-period error 0.667 microseconds in rounded ffprobe timestamps |
| Green state | 8,467 frames; observed center and peak [0,254,0] | Matches declared [0,255,0] within codec error |
| Magenta state | 27,113 frames; observed center and peak [253,0,252] | Matches declared [255,0,255] within codec error |
| Source blackout | 420 frames, exactly 0–1.5 s and 298–300 s | `agree` |
| Active-period black frames | Zero | Active gate-OFF maps to magenta rather than blackout |
| Source timing in color states | Zero state mismatches across all 36,000 frames against the independent declared-curve model | `agree` under frame-sampled timing |
| Visible green runs | 3,090 rising edges; 71 source cycle IDs have no green sample | Narrow-gate visibility limitation persists |
| RGB model | Maximum region-median error 3 code levels; no frame exceeds 3 | Consistent with lossy H.264 color encoding |

The recovered source pulse frequency/duty is expressed through **green-state
occupancy and green/magenta transitions**. The active interval is continuously
colored. Its magenta state is not an optical off-state, so this rendering is a
synthetic complementary-color switching treatment rather than a reproduction
of Lumenate's physical on/off light pulses. A black/nonblack timing detector
would not recover these source gates.

Original instantaneous frequency, duty, and integrated phase remain consistent
with the decoded color-state schedule. A 120 fps frame can miss a narrow green
gate, yielding fewer visible transitions than analytic pulse cycles. This does
not justify describing every continuous source pulse as fully reproduced.
The mapping recovers 3,090 represented cycles out of 3,161 cycle IDs traversed
during active sample times; 71 have no green frame.

## Reproduction

```bash
.venv/bin/python single_square_video.py \
  /Users/eric/Projects/media/ave_generator/output/single-square-green-magenta-300s/single-square-green-magenta-300s.mp4 \
  --output-dir artifacts/single-square-green-magenta-300s

# Execute after the blind observation is persisted.
.venv/bin/python compare_single_square_video.py \
  artifacts/single-square-green-magenta-300s/observation.json \
  /Users/eric/Projects/media/ave_generator/output/single-square-green-magenta-300s/base-timing-recipe.json \
  /Users/eric/Projects/media/ave_generator/output/single-square-green-magenta-300s/visual-treatment.json \
  --output artifacts/single-square-green-magenta-300s/comparison.json
```

Saved evidence in `artifacts/single-square-green-magenta-300s/`:

- `observation.json`: color clusters, geometry, spatial uniformity, green-state
  edges/windows, black intervals, PTS audit, input identity and run provenance.
- `color-traces.npz`: all decoded median RGB values, inferred states, timestamps.
- `comparison.json`: state/RGB errors, expected state counts, missed cycle IDs,
  and observation/input/base-recipe/treatment hashes.

Final source timing recipe file SHA-256:
`ad17b27b1f70c5bc797ba517ac315497a8bea81db6f07c3eb7cd268226bd9508`.
Visual-treatment file SHA-256:
`c8d080bd08772ce947d39dc5f622260c20a6177ac86500a6afafff7c84cc0763`.

Full Forensics suite: **163 tests passed**. The new color observer test recovers
source pulse timing while active off-gates remain colored. No media was
autoplayed; previous grayscale and vibrant artifacts were preserved.

## Limits and release handoff

Spatial uniformity uses median measurements at 128×128 analysis resolution;
it cannot rule out every isolated full-resolution pixel artifact. RGB code
values establish neither calibrated luminance nor exposure safety. Physical
display timing, optical duty, Nova equivalence and therapeutic effects remain
unsupported. The green/magenta palette and full software intensity are
Generator choices and should remain identified as synthetic.

These are custom scoped audit records, not a stable-ID portfolio agreement
report. Both new workflows carry working-tree provenance. Public label
promotion requires Platform review, with clean-source provenance and a formal
declaration still outstanding. The complete encoded-media check supports the
requested square, colors and timing with the narrow-gate sampling limitation.
