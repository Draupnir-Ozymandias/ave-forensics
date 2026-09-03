import argparse
from pathlib import Path

from transcripts.sidecar import (
    TranscriptSidecarError,
    import_aws_transcribe,
    transcript_sidecar_path_for,
    write_transcript_sidecar,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a text-free AVE transcript sidecar from an AWS response."
    )
    parser.add_argument("raw_response", type=Path)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--region", required=True)
    parser.add_argument("--language-code", required=True)
    parser.add_argument("--media-format", required=True)
    parser.add_argument("--media-sample-rate-hz", required=True, type=int)
    parser.add_argument("--model-name")
    parser.add_argument("--created-at")
    parser.add_argument("--started-at")
    parser.add_argument("--completed-at")
    parser.add_argument("--timestamp-timezone")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()
    sidecar = import_aws_transcribe(
        arguments.raw_response,
        arguments.recording,
        region=arguments.region,
        language_code=arguments.language_code,
        media_format=arguments.media_format,
        media_sample_rate_hz=arguments.media_sample_rate_hz,
        model_name=arguments.model_name,
        created_at=arguments.created_at,
        started_at=arguments.started_at,
        completed_at=arguments.completed_at,
        timestamp_timezone=arguments.timestamp_timezone,
    )
    output_path = transcript_sidecar_path_for(arguments.recording)
    status = "validated"
    if not arguments.dry_run:
        output_path, status = write_transcript_sidecar(
            sidecar, arguments.recording, overwrite=arguments.overwrite
        )
    statistics_block = sidecar["statistics"]
    print(f"Transcript sidecar: {status}: {output_path}")
    print(f"  segments:             {statistics_block['segment_count']}")
    print(
        f"  timed pronunciations: {statistics_block['timed_pronunciation_count']}"
    )
    print(f"  speech coverage:      {statistics_block['speech_coverage_ratio']:.1%}")
    print(
        "  mean confidence:      "
        f"{statistics_block['mean_pronunciation_confidence']:.3f}"
    )


if __name__ == "__main__":
    try:
        main()
    except TranscriptSidecarError as error:
        raise SystemExit(f"Transcript sidecar error: {error}") from error
