# Speech-Aware Segmentation

Speech-aware segmentation compares AVE signal measurements during narration and
during speech-sparse portions of a guided recording. It does not remove speech,
transcribe words, or claim that either population represents listener response.

## Method

When `<recording>.transcript.json` is valid and its audio SHA-256 matches the input,
the analyzer:

1. pads each provider speech segment by 0.5 seconds;
2. merges overlapping padded segments and computes their complement;
3. measures overlap between those regions and every existing analysis window;
4. labels a window `speech_active` at 50% or greater overlap,
   `speech_sparse` at 10% or less overlap, and `mixed` otherwise; and
5. summarizes entrainment candidates, envelope modulation, and phase behavior for
   each population.

The thresholds are versioned under `ANALYSIS_CONFIGURATION["speech_context"]`.
Changing them changes run provenance and therefore the deterministic run ID.

## Outputs

`ave_speech_context.json` contains text-free intervals, configuration, aggregated
window measurements, direct active-minus-sparse comparisons, transcript hashes,
and limitations. A compact `speech_context_comparison` object is also included in
`ave_evidence.json`, allowing the Corpus Evidence Index and dashboard to compare
recordings without loading private transcripts.

The complete-program analysis remains intact and primary. No audio is cut or
concatenated because discontinuities could manufacture spectral artifacts. Mixed
windows remain visible but are excluded from the direct comparison.

## Interpretation

A signature that remains similar in speech-active and speech-sparse windows is less
likely to be solely an artifact of narration. A difference between populations is
descriptive, not automatically causal: speech, background arrangement, automation,
and program chronology may all covary. Multiple guided recordings are required
before drawing provider- or protocol-level conclusions.
