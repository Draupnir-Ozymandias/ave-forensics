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

The first six-recording guided harvest subsequently confirmed that Brain.fm exposes
stable track and variation IDs, exact MP3 filenames, mental state, guided activity,
style, BPM, numeric brightness and complexity, neural-effect level, declared
duration, genres, subgenres, moods, instruments, creation time, and release state.
These fields now live in validated `*.provider.json` sidecars. Provider URLs and
access tokens are deliberately excluded.

## Guided recordings

Guided recordings may be ingested by the existing batch runner. However, speech is
broadband, nonstationary audio and may affect envelope, modulation, phase, and
clustering features. A guided recording must therefore retain its `Guided` label
and should not be assumed directly comparable with an unguided recording.

AVE now performs speech-aware segmentation when a validated transcript sidecar is
available:

- analyze the complete mixed program as delivered;
- identify speech-active and speech-sparse intervals;
- classify existing analysis windows by their overlap with buffered speech timing;
- compare speech-active and speech-sparse window populations while retaining mixed
  windows as an explicit ambiguous class; and
- preserve the complete-program analysis as the primary evidence.

This avoids concatenating discontinuous audio regions, which could introduce false
spectral boundaries. The derived comparison is stored in `ave_speech_context.json`
and as a canonical `speech_context_comparison` evidence object. See
`SPEECH_AWARE_SEGMENTATION.md`.

An external speech-to-text tool is acceptable. Raw time-aligned output remains in
ignored `captured/transcripts/` storage because it may contain copyrighted text and
cloud identifiers. AVE's committed transcript sidecar stores audio, raw-response,
and verbatim-content SHA-256 digests; language and engine/model provenance;
generation parameters; and text-free speech timestamps and confidence. AVE can
therefore validate speech context without becoming a speech-recognition project or
publishing the source script. See `TRANSCRIPT_SIDECARS.md`.

Text-to-speech synthesis belongs in `ave_generator`. The generator should retain
the source script, voice/model configuration, and generated-audio provenance. The
finished audio can then enter AVE Forensics like any other specimen.
