# Blind Multimodal Clock Analysis

AVE Forensics can evaluate encoded audio/video clock alignment from a
target-free muxed detector artifact without reading declaration values,
expected lag, stage boundaries, construction labels, or tolerances.

The detector decodes video frames and independently locates sustained saturated
pixel components. For every component it measures per-frame occupied pixel
area. It separately decodes the audio stream and computes channel RMS over the
same frame intervals. Normalized cross-correlation across a fixed lag search
then estimates the encoded frame offset and correlation for each component.

For `ave-demo-005-staged-av-comparison`, both discovered pixel components align
to their best-matching audio-energy traces at zero frames of lag. Their
correlations are `0.999728` or greater; audio and video streams also share the
same encoded start and duration. This supports the Boolean
`timeline.audio_video_clock_alignment` claim.

## Combining independent observations

The stage detector operates on the lossless stereo WAV while clock analysis
operates on the target-free muxed MP4. Both observations are persisted before
declaration comparison and can be combined with:

```bash
.venv/bin/python demo_verification.py bundle \
  artifacts/demo-portfolio/ave-demo-005-staged-av-comparison/observation-staged-v3/demo-observation.json \
  artifacts/demo-portfolio/ave-demo-005-staged-av-comparison/observation-clock-v1/demo-observation.json \
  --output artifacts/demo-portfolio/ave-demo-005-staged-av-comparison/observation-bundle-v1.json
```

The bundle verifies each artifact's current SHA-256 and preserves component
observation provenance, artifact identity, evidence identifiers, and blind
ordering attestations. It does not analyze new data or inspect declarations.

## Limits

- The result measures timing in the encoded media streams, not end-to-end
  physical display, light-source, audio-interface, or acoustic latency.
- Pixel occupancy is an engineering signal and is not calibrated luminance.
- AAC encoding, video cadence, frame quantization, and decoder behavior bound
  the precision of the measurement.
- Clock agreement does not establish neurological entrainment, therapeutic
  efficacy, exposure safety, or clinical benefit.
