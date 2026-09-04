"""Versioned parameters for the canonical AVE analysis pipeline."""

ANALYSIS_CONFIGURATION = {
    "configuration_schema_version": "1.2.0",
    "global_spectrum": {
        "top_n": 10,
        "min_frequency_hz": 1.0,
        "max_frequency_hz": 5000.0,
        "max_fft_seconds": 60.0,
        "max_segments": 8,
    },
    "timeline": {
        "window_seconds": 10.0,
        "hop_seconds": 5.0,
        "peaks_per_channel": 15,
    },
    "carrier_tracking": {
        "max_frequency_jump_hz": 1.0,
        "max_gap_windows": 2,
        "min_track_windows": 6,
    },
    "carrier_pairing": {
        "min_overlap_ratio": 0.75,
        "max_pair_difference_hz": 40.0,
        "min_difference_hz": 0.0,
        "min_duration_seconds": 30.0,
        "min_amplitude_balance": 0.25,
    },
    "envelope": {
        "minimum_carrier_center_hz": 20.0,
        "bandwidth_hz": 8.0,
        "sample_rate": 200,
        "global_min_modulation_hz": 0.1,
        "global_max_modulation_hz": 40.0,
        "timeline_min_modulation_hz": 0.1,
        "timeline_max_modulation_hz": 10.0,
        "window_seconds": 30.0,
        "hop_seconds": 15.0,
    },
    "modulation_spectrum": {
        "max_frequency_jump_hz": 1.0,
        "max_stereo_difference_hz": 0.25,
        "min_track_windows": 3,
        "min_relative_power": 0.05,
        "min_modulation_depth": 0.02,
    },
    "phase": {
        "bandwidth_hz": 8.0,
        "window_seconds": 30.0,
        "hop_seconds": 15.0,
        "trim_seconds": 0.5,
    },
    "hypothesis": {
        "minimum_score": 0.005,
        "deduplication_tolerance_hz": 0.35,
    },
    "speech_context": {
        "padding_seconds": 0.5,
        "active_minimum_overlap": 0.5,
        "sparse_maximum_overlap": 0.1,
    },
}
