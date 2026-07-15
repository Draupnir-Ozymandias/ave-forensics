# AVE Forensics Laboratory

## Mission Statement

The **AVE Forensics Laboratory** is a modular research platform for the systematic, reproducible analysis of audio, visual, haptic, and multimodal stimulation systems that claim to influence attention, relaxation, sleep, meditation, cognition, perception, or other nervous-system states.

The laboratory investigates **measurable engineering characteristics, signal relationships, temporal structure, and device behavior**. It does not treat product descriptions, marketing language, subjective reports, or spiritual narratives as proof of physiological or clinical effect.

> **Core scientific principle:**  
> AVE Forensics Laboratory findings describe measurable signal properties and inferred production or device-control techniques. They do **not** establish physiological, psychological, therapeutic, or clinical efficacy without independent experimental validation.

---

## Primary Objective

Build a robust and extensible forensic toolkit capable of accepting an unknown recording or stimulation protocol and answering:

> **How was this stimulus engineered, how does it evolve over time, and what protocol hypotheses are supported by the available evidence?**

The laboratory seeks to reconstruct technical intent from observable evidence rather than repeat producer claims.

---

## Research Questions

The project is designed to investigate questions such as:

- What carriers, modulation rates, pulse structures, phase relationships, spatial patterns, and temporal transitions are present?
- Which features persist, drift, ramp, alternate, or occur only within isolated segments?
- Are apparent entrainment frequencies produced by genuine carrier pairing, amplitude modulation, phase modulation, isochronic pulses, musical intervals, harmonics, or artifacts?
- Do recordings grouped by a stated intent—such as Focus, Relax, Sleep, or Meditate—share distinguishable engineering signatures?
- How closely does an observed engineering signature align with the producer's stated intent?
- Can repeated analysis reveal families of production techniques, protocol fingerprints, or reusable design templates?
- Which conclusions are supported directly by the signal, which are inferential, and which remain outside the scope of forensic analysis?

---

## Scope

### In Scope

- Audio-file ingestion and metadata extraction
- Frequency-domain and time-domain analysis
- Stereo decomposition and inter-channel comparison
- Time-resolved protocol reconstruction
- Carrier and carrier-pair tracking
- Amplitude-envelope analysis
- Phase-relationship analysis
- Modulation-spectrum analysis
- Binaural, monaural, and isochronic candidate detection
- Frequency and modulation sweep detection
- Persistent-track association
- Evidence scoring and uncertainty reporting
- Comparison of stated intent with observed engineering signature
- Reproducible reports, plots, CSV artifacts, and versioned configurations
- Reference-library construction and benchmark testing
- Reverse engineering of lawfully accessed device software and communication protocols
- Multimodal protocol analysis involving light, audio, and haptic stimulation

### Outside Scope Without Independent Evidence

Audio or device analysis alone cannot establish that a stimulus:

- causes brainwave entrainment in a particular listener;
- produces a clinical or therapeutic benefit;
- alters consciousness in a specific or reliable way;
- treats a medical or psychiatric condition;
- stimulates a named nerve or brain region;
- reproduces the effects of meditation, psychedelics, sleep, or neurofeedback;
- is safe or effective for a specific population.

Such claims require appropriately designed human-subject research and physiological measurements.

---

## Layered Research Architecture

### 1. Signal Layer

Measures observable properties without assigning biological meaning.

Current and planned modules include:

- Audio loader and metadata inspector
- Spectrum analyzer
- Stereo analyzer
- Time-resolved analyzer
- Carrier Pair Tracker
- Envelope Analyzer
- Phase Relationship Analyzer
- Modulation Spectrum Analyzer
- Pulse and isochronic detector
- Noise and ambience classifier
- Speech and narration segment detector
- Light-pattern and device-protocol decoders
- Haptic-pattern analyzers

### 2. Evidence Layer

Converts measurements into structured evidence objects, for example:

```json
{
  "type": "persistent_carrier_pair",
  "left_carrier_hz": 348.0,
  "right_carrier_hz": 350.0,
  "difference_hz": 2.0,
  "duration_seconds": 612.0,
  "balance": 0.96,
  "stability": 0.94,
  "confidence": 0.91
}
```

Evidence objects must preserve provenance, supporting windows, configuration values, and uncertainty.

### 3. Reconstruction Layer

Associates evidence across time to identify:

- stable carrier families;
- persistent modulation tracks;
- ramps and transitions;
- protocol sections;
- repeated production motifs;
- multimodal synchronization.

### 4. Hypothesis Layer

Generates cautious interpretations such as:

- probable relaxation-oriented low-frequency modulation;
- sustained focus-oriented beta-range structure;
- alpha-to-theta transition candidate;
- persistent carrier pair consistent with binaural construction;
- likely musical or harmonic artifact;
- insufficient evidence to infer an intentional entrainment protocol.

Hypotheses must remain distinguishable from detections.

### 5. Reporting Layer

Every report should include:

- laboratory and software version;
- Git commit;
- analysis date;
- input-file hash;
- analysis configuration;
- window, hop, FFT, and threshold settings;
- claimed intent and source metadata;
- observed engineering signature;
- evidence summary;
- protocol reconstruction;
- protocol hypotheses;
- confidence and limitations;
- generated artifact paths.

---

## Reference Library

The reference library will group recordings and protocols by producer-supplied labels and known construction methods.

Initial Brain.fm categories include:

- Focus
  - Creativity
  - Deep Work
  - Learning
  - Light Work
  - Motivation
- Meditate
  - Guided
  - Unguided
- Relax
  - Chill
  - Destress
  - Recharge
  - Travel
  - Unwind
- Sleep
  - Deep Sleep
  - Guided Sleep
  - Power Nap
  - Sleep and Wake
  - Wind Down

A separate synthetic and control library should contain:

- pure tones;
- known binaural pairs;
- monaural beats;
- amplitude-modulated carriers;
- isochronic pulses;
- phase-modulated signals;
- frequency sweeps;
- white, pink, and brown noise;
- ordinary music without intentional entrainment;
- sham controls.

Commercial or captured media must remain outside version control unless redistribution rights are explicit. Repository manifests should store metadata and provenance, not copyrighted recordings.

---

## Validation Strategy

The laboratory will be validated with:

1. **Synthetic ground truth**  
   Signals with precisely known carriers, modulation rates, phases, and transitions.

2. **Known-technique references**  
   Samples intentionally constructed as binaural, monaural, isochronic, amplitude-modulated, or phase-modulated stimuli.

3. **Negative controls**  
   Music and ambient recordings without intended neuromodulation features.

4. **Claim-versus-observation comparisons**  
   Producer-stated categories compared with measured engineering signatures.

5. **Regression testing**  
   Re-run the reference library after algorithm changes and compare results across Git commits and laboratory versions.

6. **Cross-module corroboration**  
   Strong hypotheses should be supported by multiple independent evidence types rather than a single FFT-derived relationship.

---

## Confidence Model

Each conclusion should identify its level:

- **Measurement:** directly computed property.
- **Detection:** algorithmically identified feature.
- **Association:** feature tracked or linked across time or channels.
- **Reconstruction:** inferred protocol segment or engineering relationship.
- **Hypothesis:** cautious interpretation of probable intent.
- **Unsupported claim:** proposition not established by available evidence.

Confidence must reflect signal quality, persistence, stability, channel balance, cross-module agreement, and known false-positive modes.

---

## Lumenate Nova Device-Forensics Integration

A parallel project thread is examining the **Lumenate Nova light mask** and its companion Android application. That work includes establishing a clean APK-analysis environment, using tools such as JADX and apktool, accounting for possible ProGuard or R8 obfuscation, and investigating device communication and stimulation protocols.

Relevant findings will be incorporated into AVE as a multimodal evidence source, including where available:

- session definitions;
- timing and sequencing logic;
- light intensity and pulse patterns;
- color or channel control;
- audio-light synchronization;
- Bluetooth or other device commands;
- protocol metadata;
- application-side transformations;
- firmware or hardware constraints.

The Lumenate work should remain a distinct forensic workstream while publishing validated evidence and protocol models into the AVE architecture.

---

## Ethical and Legal Principles

- Analyze only lawfully obtained recordings, applications, devices, and communications.
- Do not redistribute proprietary media or copyrighted commercial recordings.
- Separate empirical observations from interpretations and marketing claims.
- Avoid clinical language unsupported by controlled evidence.
- Preserve reproducibility, provenance, and uncertainty.
- Do not bypass access controls or use the laboratory to compromise unrelated systems.
- Protect participant privacy if physiological or subjective data are later collected.

---

## Near-Term Roadmap

### AVE v0.4

1. Carrier Pair Tracker
2. Envelope Analyzer
3. Phase Relationship Analyzer
4. Modulation Spectrum Analyzer

### Subsequent Work

- Evidence-object schema
- Batch corpus runner
- Per-recording metadata manifests
- Input hashing and run provenance
- Reference-library comparison dashboard
- Protocol-family clustering
- Claimed-intent versus observed-signature scoring
- Light/audio/haptic synchronization analysis
- Device-protocol ingestion from the Lumenate Nova workstream

---

## Definition of Success

AVE Forensics Laboratory reaches its first major objective when it can analyze an unknown stimulation recording or device session and produce a reproducible, evidence-backed answer to:

> **What measurable engineering relationships are present, how do they evolve over time, and which protocol interpretations are justified by the evidence?**

The laboratory's credibility will depend not on how extraordinary its conclusions sound, but on how carefully it distinguishes measurement, inference, uncertainty, and unsupported claims.
