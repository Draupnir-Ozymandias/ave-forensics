# Pulse and Isochronic Pattern Analysis

The pulse analyzer measures broadband amplitude timing independently of carrier
tracking. This is important because a hard-gated pulse train can remain visible in
the complete waveform even when music, speech, or changing instrumentation prevents
the toolkit from resolving one persistent acoustic carrier pair.

## Measurements

For each channel, AVE downsamples frame-level RMS energy to a 200 Hz envelope and
reports:

- pulse repetition rate from threshold-crossing intervals;
- onset regularity and interval coefficient of variation;
- active-state duty cycle;
- low/high-state separation, low-state occupancy, and harmonic fraction;
- relative envelope dynamic range; and
- a bounded structural-classification confidence.

Stereo recordings also receive a timing relationship: `synchronized`, `alternating`,
`phase_offset`, `different_rates`, or `not_available`. Twenty-second windows with a
ten-second hop preserve changes over time in `ave_pulse_analysis.json`.

## Classifications

- `synchronized_isochronic_pulse_candidate` — regular hard gating is present in
  both channels with coincident onsets.
- `alternating_isochronic_pulse_candidate` — regular hard gating alternates between
  channels at approximately half a cycle.
- `stereo_offset_isochronic_pulse_candidate` — both channels are hard-gated at a
  compatible rate with another measurable timing offset.
- `channel_specific_isochronic_pulse_candidate` — hard gating is present without a
  synchronized or alternating two-channel relationship.
- `periodic_amplitude_pulsation` — periodic timing is present but the waveform does
  not meet the hard-gating criteria.
- `smooth_amplitude_modulation` — regular modulation has a continuous rather than
  gate-like envelope.
- `irregular_transients` — amplitude events are present but their spacing is not
  sufficiently regular.
- `no_periodic_pulse` or `insufficient_data` — no supported pulse conclusion is
  available.

The word *isochronic* is used only as an engineering description of hard, regular
amplitude gating. It is not evidence of a provider's intent, therapeutic efficacy,
brain entrainment, or any physiological response.

## Outputs and corpus integration

Each canonical run writes the detailed `ave_pulse_analysis.json` artifact and adds
one `broadband_pulse_pattern` object to `ave_evidence.json`. The Corpus Evidence
Index carries the primary rate, duty cycle, regularity, stereo timing, and confidence
into JSON and CSV. The dashboard shows the classification distribution and recording
drill-down fields.

Legacy analyses remain valid but have no pulse fields. Rerun a recording—or rerun the
batch corpus with `--no-resume`—before comparing pulse distributions. Pulse fields are
not yet clustering inputs; that prevents partially rerun corpora from changing family
geometry merely because the new measurement is absent from older evidence.

## Validation

Synthetic regression tests cover synchronized hard gating, half-cycle stereo
alternation, smooth sinusoidal amplitude modulation, constant-amplitude audio,
irregular transient trains, and a mid-recording pulse-rate change. This establishes
known signal-level behavior; real-world thresholds should remain subject to corpus
calibration as more providers and device protocols are collected.
