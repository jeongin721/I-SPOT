# STT 연동 및 Transcript 저장/조회/수정 테스트.
# STT Mock / STT Error / Timeout / 잘못된 출력을 모두 확인한다.

import time
import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from app.adapters.stt_adapter import (
    STTError,
    STTOutputError,
    set_stt_adapter_override,
    validate_stt_output,
)
from app.core.config import settings
from app.schemas.contracts import STTResult
from tests.conftest import upload_audio

STT_SEGMENT_FIELDS = {
    "segment_id",
    "speaker",
    "start_ms",
    "end_ms",
    "text",
    "confidence",
}


# =========================================================
# 테스트용 Adapter
# =========================================================

class FailingSTTAdapter:
    name = "failing"
    model = None

    def transcribe(self, audio_path):
        raise STTError("STT Provider 가 오류를 반환했습니다.")


class SlowSTTAdapter:
    name = "slow"
    model = None

    def transcribe(self, audio_path):
        time.sleep(1.0)

        return STTResult(schema_version="1.0", segments=[])


class ContractViolatingSTTAdapter:
    """STTResult 가 아닌 값을 반환하는 Provider."""

    name = "invalid"
    model = None

    def transcribe(self, audio_path):
        return {"schema_version": "1.0", "segments": []}


# =========================================================
# helper
# =========================================================

def _run_stt(client: TestClient, headers: Dict[str, str], session_id: str):
    return client.post(f"/api/v1/sessions/{session_id}/transcript", headers=headers)


def _get_transcript(client: TestClient, headers: Dict[str, str], session_id: str):
    return client.get(f"/api/v1/sessions/{session_id}/transcript", headers=headers)


def transcribed_session(
    client: TestClient, headers: Dict[str, str], session_id: str
) -> dict:
    """Audio 업로드 → STT 완료 상태까지 진행한다."""

    status_code, _ = upload_audio(client, headers, session_id)

    assert status_code == 201

    assert _run_stt(client, headers, session_id).status_code == 202

    response = _get_transcript(client, headers, session_id)

    assert response.status_code == 200

    return response.json()["data"]


# =========================================================
# STT 실행
# =========================================================

def test_stt_requires_audio_first(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = _run_stt(client, counselor_headers, session["id"])

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AUDIO_NOT_FOUND"


def test_stt_request_returns_202_and_processing_status(
    client: TestClient, counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"])

    response = _run_stt(client, counselor_headers, session["id"])

    assert response.status_code == 202
    assert response.json()["data"]["session_status"] == "STT_PROCESSING"


def test_mock_stt_produces_contract_compliant_transcript(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"

    transcript = envelope["transcript"]

    assert transcript["version"] == 1
    assert transcript["schema_version"] == "1.0"
    assert transcript["source"] == "STT"
    assert transcript["is_confirmed"] is False
    assert transcript["stt_provider"] == "mock"
    assert transcript["segments"]

    for segment in transcript["segments"]:
        # STT Contract 에 없는 필드를 segment 안에 추가하지 않는다.
        assert set(segment.keys()) == STT_SEGMENT_FIELDS
        assert segment["speaker"] in {
            "COUNSELOR",
            "CHILD",
            "GUARDIAN",
            "OTHER",
            "UNKNOWN",
        }
        assert 0.0 <= segment["confidence"] <= 1.0
        assert segment["end_ms"] >= segment["start_ms"]


def test_transcript_before_stt_returns_null_transcript(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """Polling 대응: 아직 결과가 없으면 404 가 아니라 transcript=null 이다."""

    response = _get_transcript(client, counselor_headers, session["id"])

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["transcript"] is None
    assert data["session_status"] == "CREATED"


def test_stt_cannot_run_before_audio_upload_state(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """CREATED 상태에서는 STT 를 시작할 수 없다."""

    response = _run_stt(client, counselor_headers, session["id"])

    assert response.status_code in {404, 409}


def test_session_detail_reflects_transcript_progress(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    response = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers)
    data = response.json()["data"]

    assert data["has_audio"] is True
    assert data["has_transcript"] is True
    assert data["transcript_version"] == 1
    assert data["transcript_confirmed"] is False


# =========================================================
# STT 실패 / 재시도
# =========================================================

def test_stt_provider_error_sets_failed_state_with_error_info(
    client: TestClient, counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"])
    set_stt_adapter_override(FailingSTTAdapter())

    assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_FAILED"
    assert envelope["transcript"] is None
    assert envelope["error"]["code"] == "STT_FAILED"
    assert envelope["error"]["message"]


def test_stt_timeout_sets_timeout_error_code(
    client: TestClient, counselor_headers, session: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_audio(client, counselor_headers, session["id"])

    monkeypatch.setattr(settings, "STT_TIMEOUT_SECONDS", 0.2)
    set_stt_adapter_override(SlowSTTAdapter())

    assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_FAILED"
    assert envelope["error"]["code"] == "STT_TIMEOUT"


def test_stt_contract_violation_sets_invalid_output_code(
    client: TestClient, counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"])
    set_stt_adapter_override(ContractViolatingSTTAdapter())

    assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_FAILED"
    assert envelope["error"]["code"] == "STT_INVALID_OUTPUT"


def test_stt_can_be_retried_after_failure(
    client: TestClient, counselor_headers, session: dict
) -> None:
    upload_audio(client, counselor_headers, session["id"])
    set_stt_adapter_override(FailingSTTAdapter())

    _run_stt(client, counselor_headers, session["id"])

    # Provider 를 정상으로 되돌리고 재시도한다.
    set_stt_adapter_override(None)

    assert _run_stt(client, counselor_headers, session["id"]).status_code == 202

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert envelope["error"] is None
    assert envelope["transcript"]["segments"]


# =========================================================
# Adapter 출력 검증 (단위 테스트)
# =========================================================

def test_validate_stt_output_accepts_contract_payload() -> None:
    result = validate_stt_output(
        {
            "schema_version": "1.0",
            "segments": [
                {
                    "segment_id": "seg_001",
                    "speaker": "CHILD",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "text": "예시",
                    "confidence": 0.9,
                }
            ],
        }
    )

    assert isinstance(result, STTResult)
    assert result.segments[0].segment_id == "seg_001"


def test_validate_stt_output_rejects_unknown_speaker() -> None:
    with pytest.raises(STTOutputError):
        validate_stt_output(
            {
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "speaker": "TEACHER",
                        "start_ms": 0,
                        "end_ms": 1000,
                        "text": "예시",
                        "confidence": 0.9,
                    }
                ]
            }
        )


def test_validate_stt_output_rejects_confidence_out_of_range() -> None:
    with pytest.raises(STTOutputError):
        validate_stt_output(
            {
                "segments": [
                    {
                        "segment_id": "seg_001",
                        "speaker": "CHILD",
                        "start_ms": 0,
                        "end_ms": 1000,
                        "text": "예시",
                        "confidence": 1.7,
                    }
                ]
            }
        )


def test_validate_stt_output_rejects_duplicate_segment_ids() -> None:
    segment = {
        "segment_id": "seg_001",
        "speaker": "CHILD",
        "start_ms": 0,
        "end_ms": 1000,
        "text": "예시",
        "confidence": 0.9,
    }

    with pytest.raises(STTOutputError):
        validate_stt_output({"segments": [segment, dict(segment)]})


def test_validate_stt_output_rejects_non_object() -> None:
    with pytest.raises(STTOutputError):
        validate_stt_output("not a dict")


# =========================================================
# 상담사 수정 / 확정
# =========================================================

def test_transcript_edit_creates_new_version(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    target = envelope["transcript"]["segments"][0]

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={
            "segments": [
                {
                    "segment_id": target["segment_id"],
                    "text": "상담사가 수정한 문장입니다.",
                    "speaker": "GUARDIAN",
                }
            ]
        },
        headers=counselor_headers,
    )

    assert response.status_code == 200

    transcript = response.json()["data"]

    assert transcript["version"] == 2
    assert transcript["source"] == "COUNSELOR_EDIT"
    assert target["segment_id"] in transcript["edited_segment_ids"]

    edited = next(
        segment
        for segment in transcript["segments"]
        if segment["segment_id"] == target["segment_id"]
    )

    assert edited["text"] == "상담사가 수정한 문장입니다."
    assert edited["speaker"] == "GUARDIAN"
    # confidence 는 STT 값이므로 상담사 수정으로 바뀌지 않는다.
    assert edited["confidence"] == target["confidence"]


def test_transcript_edit_preserves_previous_version_count(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    original_count = len(envelope["transcript"]["segments"])
    target = envelope["transcript"]["segments"][0]

    client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"segments": [{"segment_id": target["segment_id"], "text": "수정"}]},
        headers=counselor_headers,
    )

    latest = _get_transcript(client, counselor_headers, session["id"]).json()["data"]

    assert latest["transcript"]["version"] == 2
    assert len(latest["transcript"]["segments"]) == original_count


def test_transcript_edit_can_remove_segment(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    segments = envelope["transcript"]["segments"]
    removed_id = segments[-1]["segment_id"]

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"removed_segment_ids": [removed_id]},
        headers=counselor_headers,
    )

    assert response.status_code == 200

    remaining = {
        segment["segment_id"] for segment in response.json()["data"]["segments"]
    }

    assert removed_id not in remaining
    assert len(remaining) == len(segments) - 1


def test_transcript_edit_rejects_unknown_segment_id(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"segments": [{"segment_id": "seg_999", "text": "없는 구간"}]},
        headers=counselor_headers,
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_FOUND"


def test_transcript_edit_requires_at_least_one_change(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"segments": []},
        headers=counselor_headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_transcript_edit_rejects_inverted_time_range(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    target = envelope["transcript"]["segments"][0]

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={
            "segments": [
                {
                    "segment_id": target["segment_id"],
                    "start_ms": 5000,
                    "end_ms": 1000,
                }
            ]
        },
        headers=counselor_headers,
    )

    assert response.status_code == 422


def test_transcript_edit_without_transcript_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"segments": [{"segment_id": "seg_001", "text": "수정"}]},
        headers=counselor_headers,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_SESSION_STATE"


def test_confirm_transcript_moves_to_confirmed(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_confirmed"] is True

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]

    assert detail["status"] == "STT_CONFIRMED"
    assert detail["transcript_confirmed"] is True


def test_confirm_twice_returns_already_confirmed(
    client: TestClient, counselor_headers, session: dict
) -> None:
    transcribed_session(client, counselor_headers, session["id"])

    client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    second = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "TRANSCRIPT_ALREADY_CONFIRMED"


def test_edit_after_confirm_returns_to_review_state(
    client: TestClient, counselor_headers, session: dict
) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    target = envelope["transcript"]["segments"][0]

    client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={"segments": [{"segment_id": target["segment_id"], "text": "재수정"}]},
        headers=counselor_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_confirmed"] is False

    detail = client.get(
        f"/api/v1/sessions/{session['id']}", headers=counselor_headers
    ).json()["data"]

    assert detail["status"] == "STT_REVIEW_REQUIRED"


def test_confirm_without_transcript_returns_not_found(
    client: TestClient, counselor_headers, session: dict
) -> None:
    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TRANSCRIPT_NOT_FOUND"


def test_stt_on_missing_session_returns_session_not_found(
    client: TestClient, counselor_headers
) -> None:
    response = _run_stt(client, counselor_headers, str(uuid.uuid4()))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SESSION_NOT_FOUND"
