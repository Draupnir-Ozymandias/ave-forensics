# Blind Audio Stage Segmentation

AVE Forensics reconstructs sustained construction changes in short synthetic
demonstrations without reading declared stage counts, transition times, classes,
rates, duty cycles, targets, or tolerances.

The detector computes fixed-window features for interchannel difference,
carrier-envelope level and variation, low/high envelope occupancy, and near-zero
sample occupancy. Adjacent-window feature changes above a fixed threshold form
candidate boundaries subject to a minimum stage duration. Each resulting stage
is then classified independently with carrier, envelope, and gated-pulse
analysis over the complete reconstructed stage.

For `ave-demo-005-staged-av-comparison`, the blind detector reconstructs:

- three stages;
- transitions at 5.0 and 10.0 seconds;
- a 0–5 second binaural construction with a 10 Hz interchannel difference;
- a 5–10 second smooth-amplitude-modulation stage near 10 Hz, with confidence
  narrowly below the declaration's support threshold; and
- a 10–15 second hard-gated stage near 10 Hz and 0.25 duty cycle.

These observations are persisted before declaration comparison. Repeated
transition metrics are compared only in the post-observation phase.

## Limits

- Boundary timing is quantized to the configured feature-window grid.
- The method targets short synthetic demonstrations with sustained changes; it
  is not a general-purpose music segmentation claim.
- An audio-only detector input cannot establish audio-to-video clock alignment.
- Construction agreement does not establish neurological entrainment,
  therapeutic efficacy, subjective outcome, exposure safety, or clinical
  benefit.
