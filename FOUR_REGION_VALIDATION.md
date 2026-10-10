# Five-minute four-region video: Forensics validation plan

Prepared 2026-10-10. The initial specification below is now accompanied by
completed independent measurements in
[FOUR_REGION_VALIDATION_REPORT.md](FOUR_REGION_VALIDATION_REPORT.md).
The final Generator MP4 has been decoded in full and its hash checked against
the final manifest after the packaging rerender.

## Evidence available

The reviewed [Lumenate motif catalog](../lumenate_nova_forensics/contracts/examples/lumenate-light-motif-catalog-0.1.0.json)
has SHA-256 `30be884b53cc48087500bcefca4721898f78357e99d246ec66bbaf4b76ab4f8c`.
Its [evidence report](../lumenate_nova_forensics/reports/lumenate_nova/DEMO_LIGHT_MOTIF_CATALOG.md)
and [Generator handoff](../lumenate_nova_forensics/handoffs/ave_generator_four_region_screen_emulator/HANDOFF.md)
support these practical inputs:

| Property | Evidence | Rendering implication |
| --- | --- | --- |
| Constant gated pulse | Vitality 37–56 s declares/commands 10.5 Hz and 0.20 duty; camera estimate approximately 10.4644 Hz | Use declared 10.5 Hz if reconstructing command intent; keep camera measurement separate |
| Gated ramp | Vitality 5–15 s declares linear 7.5→13.5 Hz and 0.20→0.15 duty | Use the reviewed curve-bearing catalog; record any repetition or time scaling |
| Four-region relationship | Matched compact commands; camera regions synchronous within approximately 8.33 ms | Matched four-region timing is the evidence-supported starting point |
| Independent regions | Extended command capability statically supported; divergent use unobserved | Any divergence or phase offset is a synthetic Generator choice |

The catalog supplies motifs rather than an entire 300-second program. A motif
montage expanded to five minutes is an evidence-inspired composition. To claim
reconstruction of the full captured Vitality program, Generator needs a reviewed
complete schedule from Lumenate, including transitions and terminal blackout.
The underlying [Vitality export](../lumenate_nova_forensics/reports/lumenate_nova/exports/vitality-5min-empirical-0.2.0.json)
is evidence interchange; its null interpolated fields must not be filled by
parsing explanatory prose. Lumenate owns any additional schedule normalization.

## Handoff required from Generator

Provide an unlabeled detector MP4, SHA-256, and a request listing measurable
field names without target values, tolerances, region schedules, or labels.
Keep the public presentation, recipe, resolved plan, source provenance, and
field declarations in separate files. Declare:

- whether 300 seconds includes opening/closing blackout and explanatory cards;
- constant frame rate, dimensions, exact region layout and gutters;
- frequency/duty curves and active intervals per region;
- phase origin, reset versus continuous phase policy, and frame sampling rule;
- RGB intensity/color choices, transition policy, and synthetic extensions;
- source catalog/export identities and hashes.

Forensics first hashes the detector input, decodes pixels, and persists evidence
with detector configuration and source revision. Only then compare declarations.
The phase integration and frame sampling rule are needed for post-observation
quantization analysis, never as detector targets.

## Practical acceptance checks

Use constant frame rate. Prefer a 120 fps analysis master when practical;
validate any 60 fps delivery separately. Frame rate improves encoded sampling
but does not guarantee a matching physical display refresh rate.

| Field | Independent measurement | Acceptance approach |
| --- | --- | --- |
| Duration | Decoded frame count and frame timestamps, checked against stream/container metadata | 300 s total as declared; at 60 fps expect 18,000 frames, at 120 fps 36,000; first-to-last frame-end coverage within one frame |
| Cadence | Actual frame PTS differences, timestamp continuity, decoded count | Match declared CFR; flag missing/duplicate timestamps and variable cadence; metadata alone is insufficient |
| Four spatial regions | Pixel geometry and four spatial ROI traces | Find four separately bounded active areas or explicitly report prescribed quadrant sampling; do not equate four sampled ROIs with four discovered components |
| On/off waveform | Per-region RGB-derived intensity trace, on/off runs, threshold sensitivity | Explicit off intervals support gated light pulses; a continuously varying envelope needs a different classification |
| Frequency | Rising-edge count, inter-edge intervals, windowed rate and missed-pulse checks | Report measured estimates and sampling uncertainty for plateaus; ramps require time-resolved measurements, not a single file-wide mean |
| Duty | On-frame count / valid active-interval frames, plus per-pulse on durations | Report encoded duty and quantization envelope; distinguish opening/closing blackout from pulse off-state |
| Relative timing | Matched region edge timestamps and pairwise differences | Report same-frame edges as agreement within frame resolution; bound offsets in seconds before expressing phase |
| Transitions | Independently detected changes in local rate/duty and activity | Compare scoped transitions after observation; retain unsupported intervals and coverage |
| Blackout | Beginning/end frames and off intervals | Check declared black startup/shutdown; a static MP4 cannot demonstrate an interactive stop control |

Use plateau windows of at least 10 seconds where the schedule permits, with
cycle/edge coverage reported. Edge-count resolution is roughly one cycle per
window (0.1 Hz over 10 s); timing estimates also carry frame uncertainty. For
rapid ramps use shorter windows and report the increased uncertainty. Do not
adopt a blanket ±0.01 Hz or decimal-duty tolerance without sampling analysis.

At 60 fps one frame is 16.67 ms. A 10.5 Hz pulse at 0.20 duty lasts about
19.05 ms (1.14 frames); a 13.5 Hz pulse at 0.15 duty lasts about 11.11 ms
(0.67 frames). Point-sampled 60 fps rendering can omit pulses in the latter
case. At 120 fps these are approximately 2.29 and 1.33 frames, respectively,
still subject to quantization. A one-frame edge uncertainty corresponds to duty
uncertainty on the order of frequency/frame-rate; window averaging can reduce
aggregate error but cannot establish subframe pulse shape. Integrating exposure
within a frame produces intermediate intensities and requires its own declared
sampling semantics and validation.

For matched schedules require framewise agreement of the four traces within
the measured threshold/compression uncertainty. At differing frequencies, a
single phase offset is generally insufficient: compare edge differences over
time. Relative phase below one frame remains unsupported. Threshold robustness
should be measured across several fixed intensity thresholds; compression
artifacts near boundaries must not silently become extra spatial regions.

## Current Forensics implementation and required adaptation

[`analysis/video_regions.py`](analysis/video_regions.py) already decodes video,
finds connected pixel timing components, and reports transitions, geometry,
off intervals, frame count, and cadence metadata. It does not yet provide the
complete frequency/duty/phase and PTS audit described above.

Identically flashing quadrants that touch can form one connected component.
Generator can render black gutters for visibly separate regions. If a full
continuous surface is required, Forensics should sample four geometric ROIs and
report that prescribed geometry separately from blind region discovery.
Distinct regions do not require distinct timing schedules; matched timing is
the expected source relationship.

The earlier implementation loads every frame into memory, including float64
RGB arrays. For a five-minute 120 fps master, streaming reduced-resolution
frames into four scalar traces is preferable. Preserve timing and thresholds;
compute transitions and window statistics from those traces. Chunking must
retain state across chunk boundaries. This is an implementation prerequisite
for full long-video validation. It has now been implemented in
`analysis/streaming_video.py` and run on the actual 36,000-frame MP4. The
streaming command persists pixel evidence; `compare_streaming_video.py` performs
the separate post-observation schedule comparison.

## Replication limits and release decision

The camera evidence is bounded by approximately 120 fps sampling and rolling
shutter. Optical duty, calibrated luminance/intensity, subframe phase,
packet-to-photon timing, physical emitter topology, and observed independent
region control remain unresolved. Screen RGB and encoded timing do not resolve
these capture uncertainties. No audio/light relationship should be introduced
from this catalog; none was established session-wide.

Begin with `exploratory`. After independent observation, field results retain
`agree`, `disagree`, `unsupported`, `not_evaluated`, and `invalid_declaration`.
Platform assigns `verified`, `partially_verified`, or `exploratory` under the
existing contract. Verification can establish agreement with a synthetic
render declaration while capture-equivalence limitations remain explicit.
Keep visible photosensitivity/exposure warnings and player stop/blackout
instructions in the public package. Engineering agreement establishes neither
exposure safety nor therapeutic efficacy.

Next owners: Generator supplies media and separate declarations; Lumenate
confirms whether the selected source is a full-session reconstruction or motif
composition; Forensics performs the streaming trace and timing audit when the
output arrives. The companion report records the completed output validation,
including the limitations of 120 fps sampling for narrow gates.
