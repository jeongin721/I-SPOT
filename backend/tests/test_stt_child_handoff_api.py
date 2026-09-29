"""Mock-only integration coverage for the additive STT CHILD handoff."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.adapters.abuse_classifier_adapter import PredictAbuseClassifierAdapter
from app.adapters.stt_adapter import set_stt_adapter_override
from app.schemas.contracts import STTResult
from tests.conftest import upload_audio


class StaticSTTAdapter:
    name = "static"
    model = "test"

    def __init__(self, segments):
        self._result = STTResult(schema_version="1.0", segments=segments)

    def transcribe(self, audio_path):
        return self._result


def _transcribe(client: TestClient, headers: dict, session_id: str) -> dict:
    assert upload_audio(client, headers, session_id)[0] == 201
    assert client.post(f"/api/v1/sessions/{session_id}/transcript", headers=headers).status_code == 202
    response = client.get(f"/api/v1/sessions/{session_id}/transcript", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]["transcript"]


def test_child_handoff_preserves_confirmed_text_timestamps_and_order(client, counselor_headers, session):
    set_stt_adapter_override(StaticSTTAdapter([
        {"segment_id": "q", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 900, "text": "question", "confidence": 0.8},
        {"segment_id": "c2", "speaker": "CHILD", "start_ms": 3000, "end_ms": 3400, "text": "second", "confidence": 0.8},
        {"segment_id": "u", "speaker": "UNKNOWN", "start_ms": 1800, "end_ms": 1900, "text": "review", "confidence": 0.0},
        {"segment_id": "c1", "speaker": "CHILD", "start_ms": 1000, "end_ms": 1500, "text": "first", "confidence": 0.8},
    ]))
    try:
        transcript = _transcribe(client, counselor_headers, session["id"])
    finally:
        set_stt_adapter_override(None)

    handoff = transcript["child_handoff"]
    assert transcript["schema_version"] == "1.0"
    assert handoff["child_analysis_text"] == "first second"
    assert handoff["confirmed_child_segments"] == [
        {"segment_id": "c1", "text": "first", "start_ms": 1000, "end_ms": 1500},
        {"segment_id": "c2", "text": "second", "start_ms": 3000, "end_ms": 3400},
    ]
    assert handoff["review_needed_segments"] == [
        {
            "segment_id": "u",
            "text": "review",
            "start_ms": 1800,
            "end_ms": 1900,
            "reason": "UNRESOLVED_SPEAKER",
        }
    ]
    assert all(segment["speaker"] != "CHILD" or segment["text"] in {"first", "second"} for segment in transcript["segments"])


def test_unresolved_canonical_stt_has_no_confirmed_child_and_keeps_review(client, counselor_headers, session):
    set_stt_adapter_override(StaticSTTAdapter([
        {"segment_id": "u1", "speaker": "UNKNOWN", "start_ms": 0, "end_ms": 500, "text": "unresolved", "confidence": 0.0},
    ]))
    try:
        transcript = _transcribe(client, counselor_headers, session["id"])
    finally:
        set_stt_adapter_override(None)

    handoff = transcript["child_handoff"]
    assert handoff["child_analysis_text"] == ""
    assert handoff["confirmed_child_segments"] == []
    assert handoff["review_needed_segments"] == [
        {
            "segment_id": "u1",
            "text": "unresolved",
            "start_ms": 0,
            "end_ms": 500,
            "reason": "UNRESOLVED_SPEAKER",
        }
    ]


def test_transcript_child_handoff_never_calls_classifier(client, counselor_headers, session, monkeypatch):
    def forbidden_classifier_call(*_args, **_kwargs):
        raise AssertionError("classifier must not run in the STT CHILD handoff path")

    monkeypatch.setattr(PredictAbuseClassifierAdapter, "classify", forbidden_classifier_call)
    set_stt_adapter_override(StaticSTTAdapter([
        {"segment_id": "c1", "speaker": "CHILD", "start_ms": 0, "end_ms": 500, "text": "child", "confidence": 0.0},
    ]))
    try:
        transcript = _transcribe(client, counselor_headers, session["id"])
    finally:
        set_stt_adapter_override(None)

    assert transcript["child_handoff"]["child_analysis_text"] == "child"
