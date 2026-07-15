def generate_markdown_report(metadata, spectrum, stereo, candidates):
    lines = []

    lines.append("# AVE Forensics Laboratory Report\n")

    lines.append("## Audio Metadata")
    for key, value in metadata.items():
        lines.append(f"- **{key}**: {value}")

    lines.append("\n## Global Frequency Peaks")
    for freq, mag in spectrum["top_peaks"]:
        lines.append(f"- {freq:.2f} Hz | magnitude: {mag:.4f}")

    lines.append("\n## Stereo Analysis")
    lines.append(f"- **Stereo file**: {stereo['is_stereo']}")
    lines.append(f"- **Left/right correlation**: {stereo['left_right_correlation']}")

    lines.append("\n## Classified Entrainment Candidates")
    for c in candidates:
        lines.append(
            f"- {c['left_hz']} Hz / {c['right_hz']} Hz "
            f"→ {c['difference_hz']} Hz "
            f"({c['brainwave_band']}), confidence {c['confidence']}"
        )

    lines.append("\n## Interpretation Notes")
    lines.append(
        "- Candidate binaural relationships indicate frequency differences between strong left/right channel peaks."
    )
    lines.append(
        "- These are forensic signal candidates, not proof of physiological entrainment."
    )
    lines.append(
        "- Additional confirmation requires time-window analysis, modulation detection, and channel-isolation review."
    )

    return "\n".join(lines)
