import base64
import json

from provider.brainfm import (
    ProviderMetadataError,
    extract_brainfm_capture_tree,
    extract_brainfm_sidecars,
    parse_capture,
    validate_provider_sidecar,
    write_brainfm_capture_tree,
    write_provider_sidecars,
)


def track(filename: str, *, title: str = "Quiet Mind") -> dict:
    return {
        "id": "track-123",
        "name": title,
        "beatsPerMinute": 120,
        "brightnessLevel": 0.25,
        "complexityLevel": 0.5,
        "createdAt": "2026-08-12T00:00:00Z",
        "releaseStatus": "published",
        "hasMultipleNELs": True,
        "mentalState": {"displayValue": "Meditate"},
        "mobileActivity": {"displayValue": "Guided"},
        "tags": [
            {"type": "mood", "value": "Calm"},
            {"type": "mood", "value": "Serene"},
            {"type": "instrument", "value": "Textural Soundscape"},
            {"type": "genre", "value": "Atmospheric"},
        ],
        "variations": [
            {
                "id": "variation-456",
                "url": filename,
                "lengthInSeconds": 900,
                "neuralEffectLevel": 0.86,
                "style": "guided",
            }
        ],
        "imageUrl": "https://example.invalid/image.jpg",
    }


def test_extracts_concatenated_capture_and_omits_urls(tmp_path):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    audio = recordings / "guided.mp3"
    audio.write_bytes(b"synthetic mp3 bytes")
    provider_track = track(audio.name)
    first = {
        "result": {
            "servings": [
                {
                    "track": {
                        **provider_track,
                        "tokenedUrl": "https://example.invalid/a?token=secret",
                    }
                }
            ]
        }
    }
    second = {"result": [{"track": provider_track}]}
    capture = tmp_path / "capture"
    capture.write_text(json.dumps(first) + "\n\n" + json.dumps(second))

    sidecars = extract_brainfm_sidecars(capture, recordings)
    output_path, sidecar = sidecars[0]

    assert output_path.name == "guided.mp3.provider.json"
    assert sidecar["source_capture"]["format"] == "concatenated_json"
    assert sidecar["source_capture"]["json_document_count"] == 2
    assert sidecar["match"]["matching_occurrence_count"] == 2
    assert sidecar["match"]["unique_canonical_record_count"] == 1
    assert sidecar["provider_track"]["title"] == "Quiet Mind"
    assert sidecar["taxonomy"]["moods"] == ["Calm", "Serene"]
    assert sidecar["provider_measurements"]["neural_effect_level"] == 0.86
    serialized = json.dumps(sidecar).lower()
    assert "tokenedurl" not in serialized
    assert "token=secret" not in serialized
    assert "imageurl" not in serialized

    paths = write_provider_sidecars(sidecars)
    validate_provider_sidecar(json.loads(paths[0].read_text()))


def test_parses_json_responses_embedded_in_har(tmp_path):
    response = json.dumps({"result": [{"track": track("guided.mp3")}]}).encode()
    har = {
        "log": {
            "entries": [
                {
                    "response": {
                        "content": {
                            "text": base64.b64encode(response).decode(),
                            "encoding": "base64",
                            "mimeType": "application/json",
                        }
                    }
                },
                {"response": {"content": {"text": "not json"}}},
            ]
        }
    }
    capture = tmp_path / "favorites.har"
    capture.write_text(json.dumps(har))

    documents, capture_format = parse_capture(capture)

    assert capture_format == "har_json_responses"
    assert len(documents) == 1
    assert documents[0]["result"][0]["track"]["name"] == "Quiet Mind"


def test_conflicting_records_are_rejected(tmp_path):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / "guided.mp3").write_bytes(b"audio")
    capture = tmp_path / "capture"
    capture.write_text(
        json.dumps({"track": track("guided.mp3", title="First")})
        + json.dumps({"track": track("guided.mp3", title="Second")})
    )

    try:
        extract_brainfm_sidecars(capture, recordings)
    except ProviderMetadataError as error:
        assert "conflicting provider records" in str(error)
    else:
        raise AssertionError("conflicting provider records were accepted")


def test_validator_rejects_tokenized_content(tmp_path):
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    (recordings / "guided.mp3").write_bytes(b"audio")
    capture = tmp_path / "capture"
    capture.write_text(json.dumps({"track": track("guided.mp3")}))
    _, sidecar = extract_brainfm_sidecars(capture, recordings)[0]
    sidecar["provider_track"]["authorizationToken"] = "secret"

    try:
        validate_provider_sidecar(sidecar)
    except ProviderMetadataError as error:
        assert "sensitive field" in str(error)
    else:
        raise AssertionError("sensitive provider content was accepted")


def test_batch_pairs_capture_tree_globally_and_preserves_aliases(tmp_path):
    captures = tmp_path / "captured" / "brainfm"
    recordings = tmp_path / "samples" / "brainfm"
    (captures / "focus").mkdir(parents=True)
    (recordings / "focus" / "deep_work").mkdir(parents=True)
    (recordings / "focus" / "light_work").mkdir(parents=True)
    (recordings / "sleep").mkdir(parents=True)
    filename = "shared.name_VBR5.mp3"
    for directory in (
        recordings / "focus" / "deep_work",
        recordings / "focus" / "light_work",
    ):
        (directory / filename).write_bytes(b"same audio")
    (recordings / "sleep" / "missing.mp3").write_bytes(b"no capture")
    (captures / "focus" / "shared.name_VBR5.json").write_text(
        json.dumps({"track": track(filename)})
    )
    (captures / "focus" / "orphan.json").write_text(json.dumps({"unused": True}))
    (captures / "focus" / "shared.name_VBR5.png").write_bytes(b"screenshot")

    entries = extract_brainfm_capture_tree(captures, recordings)

    ready = [entry for entry in entries if entry.status == "ready"]
    assert len(ready) == 2
    assert {entry.recording_path.parent.name for entry in ready} == {
        "deep_work",
        "light_work",
    }
    assert len([entry for entry in entries if entry.status == "missing_capture"]) == 1
    assert len([entry for entry in entries if entry.status == "unmatched_capture"]) == 1

    written = write_brainfm_capture_tree(entries)
    assert len(written) == 2
    rerun = extract_brainfm_capture_tree(captures, recordings)
    assert len([entry for entry in rerun if entry.status == "unchanged"]) == 2


def test_batch_rejects_duplicate_capture_basenames(tmp_path):
    captures = tmp_path / "captured"
    recordings = tmp_path / "recordings"
    captures.mkdir()
    recordings.mkdir()
    (recordings / "guided.mp3").write_bytes(b"audio")
    payload = json.dumps({"track": track("guided.mp3")})
    (captures / "guided").write_text(payload)
    (captures / "guided.json").write_text(payload)

    entries = extract_brainfm_capture_tree(captures, recordings)

    assert len([entry for entry in entries if entry.status == "ambiguous_capture"]) == 2
    assert len([entry for entry in entries if entry.status == "missing_capture"]) == 1
    assert not write_brainfm_capture_tree(entries)


def test_batch_marks_conflicting_provider_records_invalid(tmp_path):
    captures = tmp_path / "captured"
    recordings = tmp_path / "recordings"
    captures.mkdir()
    recordings.mkdir()
    (recordings / "guided.mp3").write_bytes(b"audio")
    (captures / "guided").write_text(
        json.dumps({"track": track("guided.mp3", title="First")})
        + json.dumps({"track": track("guided.mp3", title="Second")})
    )

    entries = extract_brainfm_capture_tree(captures, recordings)

    invalid = [entry for entry in entries if entry.status == "invalid_capture"]
    assert len(invalid) == 1
    assert "conflicting provider records" in invalid[0].message
    assert not write_brainfm_capture_tree(entries)
