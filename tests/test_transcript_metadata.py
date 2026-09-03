import hashlib
import json

import numpy as np
import soundfile as sf

from transcripts.sidecar import (
    TranscriptSidecarError,
    import_aws_transcribe,
    validate_transcript_sidecar,
    write_transcript_sidecar,
)


def aws_response(*, status="COMPLETED") -> dict:
    return {
        "jobName": "private-job-name",
        "accountId": "123456789012",
        "status": status,
        "results": {
            "transcripts": [{"transcript": "Private source words stay private."}],
            "items": [
                {
                    "id": 0,
                    "type": "pronunciation",
                    "start_time": "1.0",
                    "end_time": "2.0",
                    "alternatives": [{"confidence": "0.90", "content": "Private"}],
                },
                {
                    "id": 1,
                    "type": "punctuation",
                    "alternatives": [{"confidence": "0.0", "content": "."}],
                },
                {
                    "id": 2,
                    "type": "pronunciation",
                    "start_time": "4.0",
                    "end_time": "5.0",
                    "alternatives": [{"confidence": "0.70", "content": "words"}],
                },
            ],
            "audio_segments": [
                {
                    "id": 0,
                    "start_time": "1.0",
                    "end_time": "2.0",
                    "transcript": "Private.",
                    "items": [0, 1],
                },
                {
                    "id": 1,
                    "start_time": "4.0",
                    "end_time": "5.0",
                    "transcript": "words",
                    "items": [2],
                },
            ],
        },
    }


def import_sidecar(tmp_path):
    recording = tmp_path / "guided.wav"
    sf.write(recording, np.zeros(80_000, dtype=np.float32), 8_000)
    raw = tmp_path / "guided.json"
    raw.write_text(json.dumps(aws_response()))
    sidecar = import_aws_transcribe(
        raw,
        recording,
        region="us-east-2",
        language_code="en-US",
        media_format="wav",
        media_sample_rate_hz=8_000,
        created_at="2026-09-03T13:31:55",
        completed_at="2026-09-03T13:32:12",
        timestamp_timezone="unknown",
    )
    return recording, raw, sidecar


def test_imports_aws_timing_without_committing_verbatim_text(tmp_path):
    recording, raw, sidecar = import_sidecar(tmp_path)

    assert sidecar["recording"]["duration_seconds"] == 10.0
    assert sidecar["raw_transcript"]["sha256"] == hashlib.sha256(
        raw.read_bytes()
    ).hexdigest()
    assert sidecar["transcription_engine"]["region"] == "us-east-2"
    assert sidecar["transcription_engine"]["model_kind"] == "standard"
    assert sidecar["statistics"]["segment_count"] == 2
    assert sidecar["statistics"]["timed_pronunciation_count"] == 2
    assert sidecar["statistics"]["punctuation_count"] == 1
    assert sidecar["statistics"]["mean_pronunciation_confidence"] == 0.8
    assert sidecar["statistics"]["speech_coverage_ratio"] == 0.2
    serialized = json.dumps(sidecar).lower()
    assert "private source words" not in serialized
    assert "private-job-name" not in serialized
    assert "123456789012" not in serialized
    assert "s3://" not in serialized

    output, status = write_transcript_sidecar(sidecar, recording)
    assert status == "written"
    assert output.name == "guided.wav.transcript.json"
    assert write_transcript_sidecar(sidecar, recording)[1] == "unchanged"
    validate_transcript_sidecar(json.loads(output.read_text()))


def test_rejects_incomplete_or_out_of_bounds_aws_timeline(tmp_path):
    recording = tmp_path / "guided.wav"
    sf.write(recording, np.zeros(8_000, dtype=np.float32), 8_000)
    raw = tmp_path / "guided.json"
    response = aws_response(status="IN_PROGRESS")
    raw.write_text(json.dumps(response))

    try:
        import_aws_transcribe(
            raw,
            recording,
            region="us-east-2",
            language_code="en-US",
            media_format="wav",
            media_sample_rate_hz=8_000,
        )
    except TranscriptSidecarError as error:
        assert "COMPLETED" in str(error)
    else:
        raise AssertionError("incomplete transcript was accepted")

    response["status"] = "COMPLETED"
    raw.write_text(json.dumps(response))
    try:
        import_aws_transcribe(
            raw,
            recording,
            region="us-east-2",
            language_code="en-US",
            media_format="wav",
            media_sample_rate_hz=8_000,
        )
    except TranscriptSidecarError as error:
        assert "exceeds recording duration" in str(error)
    else:
        raise AssertionError("out-of-bounds transcript was accepted")


def test_validator_rejects_private_provider_fields(tmp_path):
    _, _, sidecar = import_sidecar(tmp_path)
    sidecar["job_configuration"]["accountId"] = "123456789012"

    try:
        validate_transcript_sidecar(sidecar)
    except TranscriptSidecarError as error:
        assert "private field" in str(error)
    else:
        raise AssertionError("private provider field was accepted")
