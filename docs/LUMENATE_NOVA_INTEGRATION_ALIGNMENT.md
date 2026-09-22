# AVE–Lumenate Nova Integration Alignment

**Status:** Shared working agreement  
**Date:** 2026-09-16  
**Participating repositories:** `ave_forensics` and `lumenate_nova_forensics`

## Shared objective

Reconstruct at least one Lumenate Nova session as a reproducible light-event
timeline, preserve the evidence and uncertainty behind that reconstruction, and
compare it with the associated audio timeline in AVE Forensics.

The combined work should answer:

> What light and audio timing relationships are measurably present, how do they
> change over the session, and which engineering interpretations are justified by
> the available evidence?

Neither repository should interpret signal alignment as proof of brain entrainment,
therapeutic efficacy, safety, subjective outcome, or physiological response.

## Current position

### AVE Forensics

AVE currently provides:

- input hashing, run provenance, and canonical evidence objects;
- carrier, envelope, modulation-spectrum, phase, and protocol-hypothesis analysis;
- broadband pulse and isochronic-pattern analysis;
- pulse rate, duty cycle, onset regularity, hard-versus-smooth shape, stereo timing,
  and time-resolved transition measurements;
- corpus indexing, longitudinal comparison, clustering, intent alignment, and a
  local evidence dashboard.

The pulse analyzer produces `ave_pulse_analysis.json` and a
`broadband_pulse_pattern` evidence object. It supplies the audio-side timing
vocabulary needed for future light/audio comparison.

### Lumenate Nova Forensics

The Lumenate project currently provides:

- an evidence-first, independently versioned device-forensics repository;
- an APK 7.0.0 / versionCode 380 reconnaissance baseline;
- identified Java/JNI strobe-engine and Nova BLE investigation targets;
- milestone gates N0 through N6;
- released `lumenate-protocol-export` schema version `0.2.0`;
- a pinned AVE evidence schema version `1.0.0`; and
- a sanitized synthetic contract fixture.

N1 and N2 now establish the bounded control path and BLE semantics used by the
published empirical Vitality timeline. Open native and firmware questions remain
separate from the released interchange contract.

## Repository ownership boundary

| Lumenate Nova Forensics owns | AVE Forensics owns |
|---|---|
| APK, DEX, Smali, JNI, and native-code analysis | Audio and general signal analysis |
| BLE services, characteristics, commands, and device state | Pulse, carrier, envelope, phase, and modulation measurements |
| Session/segment reconstruction | Multimodal alignment and comparison |
| App, transport, firmware, and device responsibility boundaries | Corpus indexing, dashboards, clustering, and longitudinal analysis |
| Declared and commanded light parameters | Import validation and downstream evidence relationships |
| Physical optical validation | Cross-modal hypotheses with explicit uncertainty |

The repositories remain separate. There is no source-tree or Git-history merge.
Integration occurs only through versioned, sanitized JSON artifacts and golden
contract fixtures.

## Authoritative interchange contract

The authoritative producer contract remains:

`lumenate_nova_forensics/contracts/lumenate-protocol-export-0.2.0.schema.json`

Lumenate owns and versions this schema. The unversioned schema follows the current
release; the versioned file is immutable. AVE vendors the released schema for
consumer validation and rejects unsupported versions. A released schema must
never be changed silently.

The released `0.2.0` contract establishes the essential structure and resolves
the clock, audio-identity, transition, execution-layer, and evidence-linkage
questions identified during alignment:

- device and app version identity;
- session identity and duration;
- ordered light segments;
- intensity, RGB color, pulse frequency, duty cycle, and on/off timing;
- BLE commands and evidence links;
- synchronization anchors with uncertainty;
- source hashes and acquisition notes;
- bounded confidence and limitations; and
- AVE-compatible evidence objects.

Raw APKs, packet captures, copyrighted media, credentials, account identifiers,
device identifiers, and reusable tokens must not cross this boundary.

## Questions to resolve before the first empirical handoff

Every empirical export must make the following relationships unambiguous. Contract
`0.2.0` represents them explicitly; any future requirement that changes validation
or semantics must use a deliberately versioned successor rather than a prose-only
convention.

1. **Audio identity** — identify the exact associated audio asset with SHA-256,
   duration, sample rate when known, and a non-sensitive role or source identifier.
2. **Clock definitions** — name every source clock and state whether timestamps are
   monotonic, wall-clock, media-position, BLE-capture, app-callback, or optical
   measurement time.
3. **Session origin** — define the zero point for both the light timeline and audio
   timeline.
4. **Synchronization anchors** — include at least two anchors when drift is to be
   estimated; every anchor carries uncertainty and supporting evidence IDs.
5. **Pulse shape** — preserve waveform or gating form when supported: square,
   smoothed, ramped, interpolated, unknown, or another evidence-backed class.
6. **Transitions** — distinguish steps, ramps, interpolation, pauses, resumptions,
   and discontinuities rather than reducing every change to adjacent segments.
7. **Execution layer** — identify whether each reconstructed behavior is declared by
   the session, calculated by the app/native engine, transported over BLE, executed
   by firmware, or physically measured.
8. **Missing knowledge** — use `null`, confidence, and limitations for unknown values;
   never substitute assumptions merely to complete an export.

## First empirical handoff package

The minimum useful handoff is one complete session containing:

1. A contract-valid `lumenate-protocol-export` JSON document.
2. A stable session identifier and total duration.
3. Ordered, non-overlapping or explicitly overlapping light segments.
4. Frequency, duty cycle, intensity, color, and transition values where supported.
5. Command-to-segment relationships and supporting evidence IDs.
6. The associated audio hash or an explicit statement that audio identity is not yet
   available.
7. At least one synchronization anchor; two or more are required for drift analysis.
8. App, firmware, and acquisition-version metadata.
9. Source hashes, confidence method, limitations, and unresolved alternatives.
10. A sanitized golden fixture safe to store in both repositories.

An export may contain unknown fields and still be useful. It must not present a
synthetic fixture or inferred values as observed empirical evidence.

## AVE import and comparison responsibilities

After receiving the first empirical export, AVE will:

1. validate the contract version and pinned AVE evidence-schema version;
2. validate IDs, temporal bounds, segment ordering, evidence references, and source
   hashes;
3. preserve the Lumenate export and evidence provenance without rewriting its
   conclusions;
4. associate the export with an audio analysis only through verified identity or
   explicit synchronization evidence;
5. convert light segments into a normalized time-resolved light-event timeline;
6. compare light pulse rate, duty cycle, transitions, and timing with audio pulse,
   envelope, modulation, and phase measurements;
7. estimate offset and drift only when anchors and uncertainty support them; and
8. publish cross-modal results as measurements, associations, or reconstructions—not
   efficacy claims.

Initial comparison outputs should include:

- matched session duration and coverage;
- light/audio clock offset with uncertainty;
- drift estimate and residual timing error when at least two anchors exist;
- aligned-window coverage;
- light and audio pulse-rate difference;
- duty-cycle difference where comparable;
- phase or onset-offset fraction where meaningful;
- transition agreement, omissions, and unmatched regions; and
- alternative explanations and data-quality limitations.

## Evidence language

Both projects use the same hierarchy:

- **Measurement:** directly computed or observed value.
- **Detection:** algorithmically identified feature.
- **Association:** relationship linked across time, channels, commands, or modalities.
- **Reconstruction:** inferred session or protocol structure supported by evidence.
- **Hypothesis:** cautious interpretation that remains distinguishable from fact.
- **Unsupported claim:** statement not established by the available evidence.

Examples of acceptable conclusions:

- “The reconstructed light command rate was 8.00 Hz during this segment.”
- “Audio pulse onsets and light-event onsets were associated within the stated clock
  uncertainty.”
- “The available anchors support a linear drift estimate over this interval.”

Examples that require independent human-subject evidence:

- “The session entrained the listener at 8 Hz.”
- “The synchronized stimulus caused relaxation.”
- “This protocol is safe or therapeutically effective.”

## Phased execution plan

### Lumenate phase

1. Close N0 with a sanitized, reproducible baseline.
2. Complete N1 control-path reconstruction.
3. Complete controlled N2 BLE/state-machine experiments.
4. Reconstruct one complete N3 session with audio identity and clock anchors.
5. Validate the export and publish a sanitized empirical golden fixture.

### AVE phase

1. Keep the audio pulse analyzer and evidence contract stable during Lumenate N1–N3.
2. Review proposed contract changes for consumer compatibility without taking schema
   ownership away from Lumenate.
3. Implement the device-protocol importer against the first empirical fixture.
4. Add schema-drift and malformed-timeline rejection tests.
5. Implement light/audio synchronization analysis using real timing evidence.
6. Add multimodal evidence summaries and dashboard views.

### Later physical-validation phase

Compare declared session values, app/native calculations, BLE commands, and measured
optical emission. Keep these layers separate so agreement and disagreement remain
visible.

## Acceptance gate for beginning synchronization development

AVE synchronization implementation should begin when all of the following are true:

- one empirical export validates against a released Lumenate schema;
- the complete light timeline has stable temporal bounds;
- the associated audio is identified or its absence is explicit;
- at least one defensible cross-modal anchor exists;
- uncertainty is recorded rather than implied away;
- every interpreted segment links to reviewed evidence; and
- the artifact is sanitized and suitable for an AVE golden test fixture.

One anchor permits offset comparison. Two or more well-separated anchors are needed
to estimate drift. Physical optical validation is not required for the first importer,
but commanded and emitted light must remain separately labeled until N5 closes.

## Released 0.2.0 consumer implementation

AVE vendors the exact released producer schema and AVE evidence schema under
`device_protocol/contracts/`. The importer in `device_protocol/lumenate.py`
accepts only protocol `0.2.0` with AVE evidence `1.0.0`, performs JSON Schema and
cross-field validation, and normalizes light-segment times to seconds without
changing their execution-layer or evidentiary meaning. Sanitized empirical
fixtures live under `device_protocol/fixtures/` and are exercised by
consumer-side acceptance and malformed-input tests.

The released fixture set contains Vitality, Deep Exploration, Spirit, and
offline Explore exports. The AVE copies are byte-for-byte identical to the
producer artifacts, and both repositories validate them in their automated
test suites.

## Definition of shared success

The first integration milestone is complete when AVE can ingest one contract-valid
Lumenate session, verify its provenance and temporal integrity, associate it with the
correct audio analysis, and report light/audio timing relationships with explicit
uncertainty and limitations.

The larger objective is complete when at least one session can be traced from declared
session data through app/native computation and BLE transport to measured optical
output, while AVE independently characterizes the audio and reports where those
modalities align, diverge, or remain indeterminate.
