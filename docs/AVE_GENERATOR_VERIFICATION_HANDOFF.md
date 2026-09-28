# AVE Generator Verification Handoff

**Status:** Pinned cross-repository working agreement  
**Date:** 2026-09-28  
**Producer:** `Draupnir-Ozymandias/electronic_dmt` (`ave_generator`)  
**Consumer:** `Draupnir-Ozymandias/ave-forensics` (`ave_forensics`)

## Purpose

This document is the continuity reference for verifying artifacts produced by AVE
Generator with AVE Forensics. It records the exact baseline, contracts, observed
results, current verification coverage, and the next Forensics milestone.

The immediate engineering question is:

> Does the rendered artifact contain the carrier, interaural-difference, envelope,
> modulation, timing, routing, and level behavior declared by its resolved protocol,
> within explicit measurement tolerances?

Agreement establishes reproducible signal behavior only. It does not establish
brainwave entrainment, a mental state, therapeutic efficacy, exposure safety, or a
physiological response.

## Pinned implementation state

| Repository | Revision | Meaning |
|---|---|---|
| AVE Generator | `0cf7f7cebc655097b5f35ca884784617624ebb9b` | `main` merge commit for Milestone 0 |
| AVE Generator | `c1e1c27c2a42c68859506665998deaa1fb622b92` | Feature commit recorded by the clean reference render manifest |
| AVE Forensics | `568ac3851bb805ad8977d51e6d39b464a3af84c7` | Analyzer revision used for the reference evidence run |

The Generator merge commit contains the feature commit unchanged. Future results
must record their own revisions and must not silently inherit the observations in
this document after either repository changes.

## Repository ownership boundary

| AVE Generator owns | AVE Forensics owns |
|---|---|
| Audio protocol and schema | Independent signal measurements |
| Protocol validation and deterministic resolution | Carrier, envelope, phase, pulse, and modulation analysis |
| Sample generation and accumulated oscillator phase | Measurement confidence and false-positive limitations |
| Digital fades, routing, headroom, and output encoding | Canonical evidence objects and analysis provenance |
| Pre-render and completed render manifests | Expected-versus-observed comparison results |
| Generator-side black-box acceptance probes | Cross-module support or contradiction |

The repositories remain independent. Forensics must consume files and versioned
JSON; it must not import or execute Generator source as an analysis dependency.
Generator may invoke the public Forensics CLI as an external process, but it must
preserve Forensics revision, evidence hashes, and claim-level limitations.

## Authoritative Generator inputs

All paths below are relative to the AVE Generator repository.

| Artifact | Version or identity | File SHA-256 |
|---|---|---|
| `contracts/ave-audio-protocol-1.0.0.schema.json` | Audio protocol schema `1.0.0` | `469bc48a6c07ce9fdc68eb7be31c19b100920442346e13762c2567697d40e52b` |
| `contracts/examples/baseline-audio-protocol.json` | `corrected-baseline-sweep-v1` | `02224351fa37095bae109bdeb7a663fea946c1ed885c520a4c519bf353ac0239` |

For the 180-second reference resolution:

- canonical requested-protocol SHA-256:
  `c36f985ffccbccc1bf0900832c42f049d3d452cc5a7eb7c83533a7ed741e6c1b`;
- resolved-protocol SHA-256:
  `095a726ac93145d4cfb2dc9dadcc8cb25fa6812640dc2eec89e492d8c9ec876a`;
- resolved-protocol file SHA-256:
  `ba219ff525de35afee5bc00268ab93da5361eb65f9d3f40b47bb6b5dce87b0be`;
- rendered WAV SHA-256:
  `10763b4a6d392470be422baec6c7a21a751f81e86e35a6163ab46ff117566c7c`;
- duration: `180.0` seconds;
- sample rate: `44100` Hz;
- channels: `2`; and
- sample count: `7,938,000` frames.

The canonical JSON hash and file-byte hash are deliberately distinct identities.
Consumers must not substitute one for the other.

## Reproduction command

With the repositories in sibling directories and their environments installed, run
from AVE Generator:

```bash
.venv/bin/python -m ave_audio_generator milestone0 \
  --output-dir output/milestone-0 \
  --forensics-repo ../ave_forensics
```

This command generates and verifies both 10- and 180-second WAV files. It invokes
AVE Forensics only for the 180-second artifact because the accelerated 10-second
sweep is shorter than the default Forensics observation windows.

Generated WAV, media, manifests, and Forensics output remain ignored build
artifacts. The protocol, schema, tests, and this agreement are the tracked sources
of truth. Do not commit the 31.75 MB reference WAV merely to avoid regeneration.

## Declared signal behavior

The baseline is an engineering calibration sweep, not a state profile.

- Carrier: `528` Hz.
- Harmonic partials: `528`, `1056`, `1584`, and `2112` Hz with declared relative
  amplitudes `1.0`, `0.6`, `0.4`, and `0.2`.
- Sweep: linear `0` to `360` Hz over the declared duration.
- Binaural policy: right-channel difference applies to the fundamental only and is
  capped at `40` Hz; higher harmonics remain shared.
- Binaural-to-isochronic crossfade: `36` to `44` Hz.
- Isochronic modulation: sweep clipped to `40` through `80` Hz.
- Isochronic-to-harmonic crossfade: `76` to `84` Hz.
- Harmonic-stage modulation: follows the accumulated `0` to `360` Hz sweep.
- Output peak target: `0.9` linear sample amplitude.
- Endpoint fade: `0.05` seconds.
- Oscillator rule: exclusive discrete frequency accumulation across chunk
  boundaries. A time-varying oscillator must never be evaluated as `f(t) * t`.

## Reference Generator verification

The clean 180-second Generator manifest passed all of its checks:

| Check | Expected | Measured | Tolerance |
|---|---:|---:|---:|
| Sample rate | 44100 Hz | 44100 Hz | exact |
| Sample count | 7,938,000 | 7,938,000 | exact |
| Sample peak | at most 0.9 | 0.8999908444 | 1 PCM16 LSB |
| Endpoint peak | 0 | 0 | 1 PCM16 LSB |
| Left carrier | 528 Hz | 528 Hz | 3.5 Hz |
| Right fundamental at 20 Hz difference | 548 Hz | 547.9999553 Hz | 3.5 Hz |
| Isochronic probe | 60 Hz | 59.9998694 Hz | 4 Hz |
| Harmonic-stage probe | 120 Hz | 119.9980172 Hz | 4 Hz |
| Shared isochronic stereo delta | 0 | 0 | 2 PCM16 LSB |
| Audio/visual duration | 180 s | 180 s | exact |

These are Generator acceptance measurements, not substitutes for independent
Forensics evidence.

## Reference Forensics observations

At the pinned Forensics revision, analysis produced nine canonical evidence objects
covering broadband pulse structure, carrier envelope, modulation reconstruction,
persistent carrier pairs, and time-resolved phase relationship.

The evidence provenance correctly binds to the reference WAV SHA-256. Forensics
matched all declared shared carriers:

| Expected pair | Measured pair | Observed range |
|---:|---:|---:|
| 528 / 528 Hz | 528 / 528 Hz | 15–180 s |
| 1056 / 1056 Hz | 1056 / 1056 Hz | 0–180 s |
| 1584 / 1584 Hz | 1584 / 1584 Hz | 0–180 s |
| 2112 / 2112 Hz | 2112 / 2112 Hz | 0–180 s |

The time-resolved timeline agreed exactly with the early binaural ramp:

| Window | Midpoint | Expected difference | Measured difference | Error |
|---|---:|---:|---:|---:|
| 0–10 s | 5 s | 10 Hz | 10 Hz | 0 Hz |
| 5–15 s | 10 s | 20 Hz | 20 Hz | 0 Hz |
| 10–20 s | 15 s | 30 Hz | 30 Hz | 0 Hz |

One reference run produced:

- `ave_evidence.json` SHA-256:
  `dfd9888ab0b3403bcce724d5a0f18af47bc698974b38467ed51d6406f213f420`;
- `ave_timeline.csv` SHA-256:
  `99303b5aa31661a7f6acba112d5a4661cdba6b0618a9808685d2e3856f968ade`.

Those two output hashes are audit records for that exact run, not portable golden
identities. Forensics run provenance, evidence IDs, or reports may legitimately
change with the output path, analysis revision, dependency versions, or analysis
configuration. The input WAV hash, pinned source revisions, measurement values, and
declared tolerances are the comparison anchors.

## Open verification gap

The pinned Forensics configuration does not independently reconstruct the later
continuous isochronic and harmonic modulation ramps. Its whole-file modulation
reconstruction reports no significant modulation tracks for this chirped stimulus,
even though Generator black-box probes measure the programmed 60 and 120 Hz values.

Therefore:

- persistent carrier structure is independently verified;
- the early binaural-difference ramp is independently verified;
- Generator-side signal probes verify selected later modulation values; and
- continuous 40–80 Hz isochronic and 84–360 Hz harmonic-stage ramp reconstruction
  remains open Forensics work.

The absence of a Forensics reconstruction must not be rewritten as absence of the
programmed signal, and Generator measurements must not be mislabeled as independent
Forensics confirmation.

## Next Forensics milestone

Implement continuous modulation-ramp analysis against the generated 180-second
positive control.

The work should:

1. analyze modulation in time-resolved windows rather than only as a stationary
   whole-file spectrum;
2. preserve window start/end, center-time, measured frequency, confidence,
   continuity, and local failure reason;
3. distinguish the isochronic and harmonic stages using measurements rather than
   intent labels;
4. compare each supported window with the resolved Generator curve at the same
   monotonic time;
5. emit canonical evidence using an existing compatible evidence type, or version
   the evidence schema deliberately if a new type is required;
6. retain unsupported or low-confidence windows rather than interpolating them into
   apparently complete evidence; and
7. add the Generator fixture as a positive control without committing the rendered
   WAV.

### Acceptance criteria

- The analyzed input SHA-256 equals the manifest WAV SHA-256.
- Time bounds remain within `0.0` through `180.0` seconds.
- The stable 528 Hz carrier and declared shared harmonics remain detectable.
- The early binaural timeline continues to recover 10, 20, and 30 Hz within `0.5`
  Hz at the existing window midpoints.
- The isochronic analysis recovers the resolved modulation curve over supported
  windows within a preregistered tolerance no looser than `4` Hz.
- The harmonic-stage analysis recovers the resolved modulation curve over supported
  windows within a preregistered tolerance no looser than `4` Hz.
- Coverage, misses, confidence, and transition contamination are reported
  separately; a mean error must not hide unsupported windows.
- Repeated analysis with the same input, source revision, dependencies, and
  configuration produces the same canonical measurements.
- Canonical evidence limitations state that signal reconstruction does not establish
  intent, safety, brain response, or efficacy.

## Continuity checklist

Before continuing this milestone:

1. verify both repository revisions and clean/dirty state;
2. verify the Generator schema and fixture file hashes above;
3. regenerate the reference WAV rather than copying an unverified artifact;
4. verify the WAV hash before treating the reference observations as comparable;
5. preserve the resolved protocol and render manifest beside analysis output;
6. record the Forensics configuration version and source-tree provenance;
7. keep Generator acceptance results separate from Forensics measurements; and
8. update this handoff when contracts, tolerances, or ownership boundaries change.

## Source-of-truth order

When sources disagree, use this order:

1. versioned schema and protocol artifacts at their pinned Generator revision;
2. resolved protocol and completed render manifest from the current run;
3. canonical Forensics evidence and run provenance;
4. this handoff document; and
5. narrative console output or historical planning prose.

Never preserve a contradiction by silently choosing the more convenient source.
Record it as a limitation or open issue and resolve it through a versioned change.
