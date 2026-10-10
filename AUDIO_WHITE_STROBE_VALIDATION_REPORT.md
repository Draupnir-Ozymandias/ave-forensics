# Aura Cleansing / white-strobe audiovisual validation

Completed 2026-10-10 by Platform after the Forensics chat reached its usage limit. Forensics saved source observations before its interruption; Platform independently audited the final generated media.

The first 300 seconds of the 900-second stereo track are preserved in pitch and sample rate. The synchronized derivative multiplies both channels by the same 0.70–1.0 gain, derived from actual encoded white-frame gates, with centered Gaussian smoothing (2.5ms sigma, 10ms support each side) and 50ms depth transitions at 1.5s and 298s. Outside the active interval audio remains dry. It preserves stereo routing; amplitude modulation adds sidebands and changes the source envelope. It does not retune dominant spectral components or remove existing rhythms.

Source observations in ave_forensics/artifacts/audio-white-alignment distinguish audible peaks near 73.5 and 147Hz from slow envelope activity around 0.60/0.85Hz and a band-dependent approximately 8Hz rhythm. Detrended broadband RMS/white-gate correlation was approximately 0.00061 left and -0.00017 right. These are evidence of little natural timing association, not physiological findings.

Final artifact: /Users/eric/Projects/media/ave_generator/output/audio-white-strobe-300s/audio-white-strobe-300s.mp4
MP4 SHA-256: 40654548585103e4ac456a7bad3fcf9f75f20d099877d6ef5c05794e01707d64

Validation findings:

- Exactly 13,230,000 PCM samples per channel, stereo at 44.1kHz: 300 seconds.
- Original and muxed video packet payload hashes match. Existing full white-video frame verification therefore applies unchanged: 36,000 frames at 120fps.
- Both stream start times are 0; both stream durations are 300 seconds.
- Source-relative gain observation was saved before loading the protocol. It recovered gain approximately 0.70–1.0.
- Independently reconstructing the declared envelope from Forensics' observed pixels matches all 26,460,000 processed PCM channel values exactly after integer rounding: zero sample mismatches. No Generator synthesis functions or producer resolved plan were used in this comparison.
- Processed PCM sample peak 0.72647095 (about -2.78dBFS), zero clipped samples. Decoded AAC sample peak 0.72637939. These are sample-peak checks, not oversampled true-peak measurements.
- Decoded AAC correlates 0.999995 with the processed WAV at zero lag. Its raw decode has 80 trailing samples beyond the nominal duration (about 1.81ms codec padding); declared container audio duration remains 300s.
- Generator reports 70 tests passing.

The 71 analytic gates missed by video sampling do not create extra audio peaks: modulation follows actual visible gates. Smoothing spreads acoustic transitions around encoded boundaries, so this is synchronized smoothed volume modulation rather than exact rectangular acoustic pulses. Underlying approximately 8Hz source rhythm remains layered beneath the added gain; uniformly dominant output modulation at the strobe rate has not been established. Physical display/audio latency remains unmeasured.

Evidence label retained: exploratory working-tree experiment. This custom audit is not a formal portfolio agreement report or clean-source release.

WARNING: flashing white light / photosensitivity risk. No autoplay. No entrainment, therapeutic benefit, exposure-safety or Nova-equivalence claim.

Audit artifacts: observation.json, gain-observation.npz, comparison.json and the two audit scripts alongside this report. The source Forensics observation files remain in ave_forensics/artifacts/audio-white-alignment.
