def generate_protocol_summary(hypotheses, top_n=8):
    lines = []

    lines.append("## Protocol Hypothesis Summary")

    if not hypotheses:
        lines.append("- No protocol hypotheses exceeded the scoring threshold.")
        return "\n".join(lines)

    primary = hypotheses[0]

    lines.append("\n### Primary Hypothesis")
    lines.append(
        f"- **{primary['intent']}** at "
        f"**{primary['average_difference_hz']} Hz** "
        f"for **{primary['duration_seconds']} seconds** "
        f"(score {primary['hypothesis_score']})"
    )

    lines.append("\n### Supporting / Secondary Hypotheses")

    for h in hypotheses[1:top_n]:
        lines.append(
            f"- {h['average_difference_hz']} Hz "
            f"({h['brainwave_band']}) — "
            f"{h['intent']}; "
            f"duration {h['duration_seconds']}s; "
            f"score {h['hypothesis_score']}"
        )

    lines.append("\n### Forensic Caution")
    lines.append(
        "- Long beta/gamma tracks may reflect intentional stimulation, musical intervals, harmonics, or production artifacts."
    )
    lines.append(
        "- These hypotheses describe signal structure only, not confirmed physiological response."
    )

    return "\n".join(lines)
