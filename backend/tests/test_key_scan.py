# STT 검수 '1차 임시 핵심 발화' 스캔 테스트 (app/services/key_scan_service.py, API_CONTRACT 7절 key_scan).
#
# process_stt 가 전사 결과를 저장하기 전에 1차 스캔을 돌려 transcripts.key_scan 에 저장하는지,
# 실패 · 시간 초과 · 모양 오류여도 STT 는 성공으로 두는지(status=FAILED), modeling 이 아니면 부르지 않는지(SKIPPED),
# 원문 수정 때 지운 발화만 빼고 복사하는지 본다. 스캐너는 가짜 함수다. 데이터는 모두 가상이다.

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.adapters.module_loader import ModuleLoadError
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import SessionStatus
from app.models.session import ConsultationSession
from app.services import key_scan_service, session_service
from tests.test_stt_transcript import _get_transcript, transcribed_session

SECRET_TEXT = "가상 비밀 문장"


@pytest.fixture
def calls() -> List[Dict[str, Any]]:
    return []


@pytest.fixture
def modeling(monkeypatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")


def _use_scanner(monkeypatch, scanner) -> None:
    monkeypatch.setattr(key_scan_service, "_load_scanner", lambda: scanner)


def _key_scan(envelope: dict) -> Any:
    return envelope["transcript"]["key_scan"]


# =========================================================
# STT 와 함께 저장
# =========================================================

def test_mock_provider_skips_scan_without_calling_module(
    client: TestClient, counselor_headers, session: dict, monkeypatch
) -> None:
    def must_not_load():
        raise AssertionError("modeling 이 아니면 모듈을 부르지 않는다")

    monkeypatch.setattr(key_scan_service, "_load_scanner", must_not_load)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert _key_scan(envelope) == {"status": "SKIPPED", "model": None, "segments": []}


def test_scan_result_is_saved_in_transcript_order(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, calls
) -> None:
    def scanner(stt_result: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(stt_result)
        return {
            "model": "roberta_test",
            "segments": [
                {"segment_id": "seg_003", "abuse_types": ["NEGLECT", "PHYSICAL", "NEGLECT"]},
                {"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]},
                {"segment_id": "seg_999", "abuse_types": ["PHYSICAL"]},
                {"segment_id": "seg_002", "abuse_types": ["신체학대", "UNKNOWN"]},
                {"segment_id": "seg_001", "abuse_types": ["EMOTIONAL"]},
            ],
        }

    _use_scanner(monkeypatch, scanner)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    # 원문 순서 · 원문에 있는 번호만 · 모르는 유형 버림 · 같은 발화는 처음 것만 · 유형이 남지 않은 발화는 뺌.
    assert _key_scan(envelope) == {
        "status": "DONE",
        "model": "roberta_test",
        "segments": [
            {"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]},
            {"segment_id": "seg_003", "abuse_types": ["NEGLECT", "PHYSICAL"]},
        ],
    }
    # 스캐너는 STT Contract 모양(segments[] 의 segment_id · speaker · …)을 받는다.
    assert len(calls) == 1
    first = calls[0]["segments"][0]
    assert set(first) >= {"segment_id", "speaker", "start_ms", "end_ms", "text", "confidence"}
    assert isinstance(first["speaker"], str)


def test_empty_scan_is_done_with_no_segments(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    _use_scanner(monkeypatch, lambda stt_result: {"model": "roberta_test", "segments": []})

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert _key_scan(envelope) == {"status": "DONE", "model": "roberta_test", "segments": []}


@pytest.mark.parametrize(
    "result",
    [
        None,
        "seg_001",
        {"model": "x"},
        {"model": "x", "segments": "seg_001"},
        {"model": "x", "segments": ["seg_001"]},
        {"model": "x", "segments": [{"segment_id": 1, "abuse_types": ["PHYSICAL"]}]},
        {"model": "x", "segments": [{"segment_id": "seg_001", "abuse_types": "PHYSICAL"}]},
        # 해시 불가 원소(list · dict) — 예외가 STT 까지 올라가지 않는다(민규 #114).
        {"model": "x", "segments": [{"segment_id": "seg_001", "abuse_types": [["PHYSICAL"]]}]},
        {"model": "x", "segments": [{"segment_id": "seg_001", "abuse_types": [{"t": "PHYSICAL"}]}]},
    ],
)
def test_bad_shape_fails_scan_but_stt_succeeds(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, result
) -> None:
    _use_scanner(monkeypatch, lambda stt_result: result)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert _key_scan(envelope) == {"status": "FAILED", "model": None, "segments": []}
    assert len(envelope["transcript"]["segments"]) > 0


def test_scanner_error_fails_scan_without_leaking_text(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, caplog
) -> None:
    def scanner(stt_result: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError(SECRET_TEXT)

    _use_scanner(monkeypatch, scanner)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert envelope["error"] is None
    assert _key_scan(envelope)["status"] == "FAILED"
    # 예외 문구(원문이 섞일 수 있음)는 로그에 남기지 않고 종류 이름만 남긴다.
    assert SECRET_TEXT not in caplog.text


def test_module_load_error_fails_scan(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    def broken():
        raise ModuleLoadError("가상 import 실패")

    monkeypatch.setattr(key_scan_service, "_load_scanner", broken)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert _key_scan(envelope)["status"] == "FAILED"


def test_timeout_fails_scan_but_stt_succeeds(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "KEY_SCAN_TIMEOUT_SECONDS", 0.2)

    def slow(stt_result: Dict[str, Any]) -> Dict[str, Any]:
        time.sleep(1.0)
        return {"model": "late", "segments": [{"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]}]}

    _use_scanner(monkeypatch, slow)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert _key_scan(envelope) == {"status": "FAILED", "model": None, "segments": []}


# =========================================================
# 원문 수정 · 확정
# =========================================================

def test_edit_copies_key_scan_without_removed_segments(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    _use_scanner(
        monkeypatch,
        lambda stt_result: {
            "model": "roberta_test",
            "segments": [
                {"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]},
                {"segment_id": "seg_002", "abuse_types": ["NEGLECT"]},
            ],
        },
    )
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]

    # 스캐너가 다시 불리면 안 된다(문장이 바뀐 발화도 다시 스캔하지 않음).
    def must_not_rescan(stt_result):
        raise AssertionError("원문 수정 때 다시 스캔하지 않는다")

    _use_scanner(monkeypatch, must_not_rescan)

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        json={
            "segments": [{**first, "text": "고친 가상 문장"}],
            "removed_segment_ids": ["seg_002"],
        },
        headers=counselor_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["version"] == 2
    assert data["key_scan"] == {
        "status": "DONE",
        "model": "roberta_test",
        "segments": [{"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]}],
    }


def test_confirm_keeps_key_scan(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    _use_scanner(
        monkeypatch,
        lambda stt_result: {"model": "m", "segments": [{"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]}]},
    )
    transcribed_session(client, counselor_headers, session["id"])

    response = client.post(f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers)

    assert response.status_code == 200
    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert envelope["transcript"]["is_confirmed"] is True
    assert _key_scan(envelope)["segments"] == [{"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]}]


def test_copy_for_new_version_handles_old_transcripts() -> None:
    # 이 기능 전 전사본(null)은 복사해도 null 이다.
    assert key_scan_service.copy_for_new_version(None, ["seg_001"]) is None
    assert key_scan_service.copy_for_new_version(
        {"status": "SKIPPED", "model": None, "segments": []}, ["seg_001"]
    ) == {"status": "SKIPPED", "model": None, "segments": []}


# =========================================================
# 멈춘 STT 작업 마감 기준
# =========================================================

def _stt_processing_session(session_id: str, seconds_ago: float) -> ConsultationSession:
    with SessionLocal() as db:
        row = db.get(ConsultationSession, uuid.UUID(session_id))
        row.status = SessionStatus.STT_PROCESSING
        row.stt_started_at = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        db.commit()


def _expire(session_id: str) -> bool:
    with SessionLocal() as db:
        row = db.get(ConsultationSession, uuid.UUID(session_id))
        return session_service.expire_stale_processing(db, row)


def test_stale_stt_deadline_includes_key_scan_time_only_for_modeling(session: dict, monkeypatch) -> None:
    monkeypatch.setattr(settings, "STT_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(settings, "KEY_SCAN_TIMEOUT_SECONDS", 30.0)
    # STT 제한 5초 + 여유 60초 = 65초. 스캔 30초를 더하면 95초.
    elapsed = 5.0 + session_service.STALE_GRACE_SECONDS + 10

    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    _stt_processing_session(session["id"], elapsed)
    assert _expire(session["id"]) is False

    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    assert _expire(session["id"]) is True
