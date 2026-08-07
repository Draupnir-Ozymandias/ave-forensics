# Corpus Context and Guided-Recording Policy

AVE keeps observed signal evidence separate from contextual descriptions. This
prevents vendor language, transcripts, or expected outcomes from influencing an
acoustic finding before comparison is performed.

## Four evidence layers

1. **Observed signal evidence** — carrier, envelope, modulation-spectrum, phase,
   and protocol-hypothesis measurements produced by AVE. Protocol-family
   clustering uses only this layer.
2. **Provider taxonomy** — provider-supplied mental state, activity, moods,
   instrumentation, complexity, brightness, guided/unguided status, and similar
   descriptors. These are claims or labels, not measured facts.
3. **Speech context** — a time-aligned transcript, speaker turns, and speech/non-
   speech intervals for guided recordings. The transcript is contextual evidence;
   the original audio remains the primary specimen.
4. **Outcome claims** — statements such as relaxation or lower blood pressure,
   preserved with source, capture date, wording, qualifiers, and any linked study.
   AVE does not treat an outcome claim as proof of physiological effect.

The layers may be compared only after independent acoustic analysis. This enables
the future claimed-intent-versus-observed-signature milestone without contaminating
the observed feature set.

## Brain.fm taxonomy observed in the supplied interface capture

The August 2026 capture establishes the following useful vocabulary without tying
it to a specific recording whose selection is not visible:

- mental state: `Meditate`
- activity: `Guided`
- moods: `Calm`, `Chill`, `Dreamlike`, `Floating`, `Meditative`, `Serene`
- instrumentation: `Textural Soundscape`
- complexity: `Medium`
- brightness: `High`
- track-level examples visibly distinguish `Guided` from `Unguided`

Future harvesting should capture these fields at download time, along with the
track title, provider, page or application location, and capture date. Screenshots
are valuable source records when an export is unavailable.

## Guided recordings

Guided recordings may be ingested by the existing batch runner. However, speech is
broadband, nonstationary audio and may affect envelope, modulation, phase, and
clustering features. A guided recording must therefore retain its `Guided` label
and should not be assumed directly comparable with an unguided recording.

The recommended future analysis adds speech-aware segmentation:

- analyze the complete mixed program as delivered;
- identify speech-active and speech-sparse intervals;
- analyze speech-sparse intervals separately when sufficient audio remains; and
- compare both result sets while preserving the original timeline.

An external speech-to-text tool is acceptable. Store its time-aligned output as a
sidecar with the audio SHA-256, transcript SHA-256, language, engine/model version,
generation parameters, and timestamps. AVE can ingest and validate that sidecar
without becoming a speech-recognition project itself.

Text-to-speech synthesis belongs in `ave_generator`. The generator should retain
the source script, voice/model configuration, and generated-audio provenance. The
finished audio can then enter AVE Forensics like any other specimen.
