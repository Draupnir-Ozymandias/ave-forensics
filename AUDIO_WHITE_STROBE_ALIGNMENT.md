# Audio / white-strobe source alignment

2026-10-10. Source observations were completed by Forensics and preserved in artifacts/audio-white-alignment/audio-observation.json, alignment-comparison.json, and alignment-traces.npz. Platform compiled this brief after the Forensics chat hit its usage limit.

First 300s of AuraCleansing_120bpm_15m.mp3. Strong audible spectral peaks near 73.5 and 147Hz are distinct from slower envelope rhythms. Broadband mean envelope has peaks near 0.60/0.85Hz; approximately 8Hz modulation is present and band-dependent. Existing detrended RMS/white-gate correlations are near zero in both channels.

Recommendation: preserve pitch and stereo routing, add explicitly synthetic amplitude modulation from actual observed white-frame gates. Declare smoothing and gain floor rather than claiming carrier-frequency synchronization. Generator adopted gain 0.70–1.0, centered Gaussian smoothing, and preserved video packets. See AUDIO_WHITE_STROBE_VALIDATION_REPORT.md for independent final-media checks performed by Platform.
