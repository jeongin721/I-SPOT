# STT 검수 '1차 임시 핵심 발화' 스캔 테스트 (app/services/key_scan_service.py, API_CONTRACT 7절 key_scan).
#
# process_stt 가 전사 결과를 저장하기 전에 1차 스캔을 돌려 transcripts.key_scan 에 저장하는지,
# 실패 · 시간 초과 · 모양 오류여도 STT 는 성공으로 두는지(status=FAILED), modeling 이 아니면 부르지 않는지(SKIPPED),
# 발화별 임시 조문(legal_references)을 다듬어 저장하는지, 원문 수정 때 직전 결과를 복사해 REFRESHING 으로 두고
# 백그라운드에서 저장한 원문으로 다시 스캔하는지(2026-11-09, 비동기), 그 실패 · 멈춤 · 연이은 저장을 어떻게 처리하는지 본다.
# 스캐너는 가짜 함수다. 데이터는 모두 가상이다.

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ModuleLoadError
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import SessionStatus
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.services import key_scan_service, session_service
from tests.test_stt_transcript import _get_transcript, transcribed_session

SECRET_TEXT = "가상 비밀 문장"

REFERENCE = {
    "abuse_type": "EMOTIONAL",
    "law_name": "아동복지법",
    "article": "제17조",
    "item_label": "제5호",
    "text": "아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위",
    "portal_url": "https://www.law.go.kr/법령/아동복지법",
    "excerpt": "소리 지르고 욕을 해요",
    "score": 0.6123,
}
SAVED_REFERENCE = {**REFERENCE, "score": 0.612}


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


def _seg(segment_id: str, abuse_types: List[str], legal_references: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {"segment_id": segment_id, "abuse_types": abuse_types, "legal_references": legal_references or []}


def _expected(
    status: str,
    model: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    *,
    scanned_version: Optional[int] = None,
    started_at: Any = None,
) -> Dict[str, Any]:
    """응답의 key_scan 모양 전체(스키마가 없는 칸은 null 로 준다)."""

    return {
        "status": status,
        "model": model,
        "segments": segments or [],
        "scanned_version": scanned_version,
        "started_at": started_at,
    }


def _patch(client: TestClient, headers, session_id: str, **payload) -> dict:
    response = client.patch(f"/api/v1/sessions/{session_id}/transcript", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _first_scan() -> Dict[str, Any]:
    return {
        "model": "roberta_test",
        "segments": [
            {"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]},
            {"segment_id": "seg_002", "abuse_types": ["NEGLECT"]},
        ],
    }


def _scanner_by_text(calls: List[Dict[str, Any]]):
    """고친 문장("고친")이 있으면 그 발화만 정서 + 조문으로, 아니면 처음 결과로."""

    def scanner(stt_result: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(stt_result)
        edited = [segment for segment in stt_result["segments"] if "고친" in segment["text"]]
        if edited:
            return {
                "model": "roberta_test",
                "segments": [
                    {"segment_id": edited[0]["segment_id"], "abuse_types": ["EMOTIONAL"], "legal_references": [REFERENCE]}
                ],
            }
        return _first_scan()

    return scanner


def _latest_transcript(session_id: str) -> Transcript:
    with SessionLocal() as db:
        row = db.scalar(
            select(Transcript)
            .where(Transcript.session_id == uuid.UUID(session_id))
            .order_by(Transcript.version.desc())
            .limit(1)
        )
        db.expunge(row)
        return row


def _set_key_scan(transcript_id: uuid.UUID, value: Dict[str, Any]) -> None:
    with SessionLocal() as db:
        row = db.get(Transcript, transcript_id)
        row.key_scan = value
        db.commit()


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
    assert _key_scan(envelope) == _expected("SKIPPED")


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
    # 원문 순서 · 원문에 있는 번호만 · 모르는 유형 버림 · 같은 발화는 유형이 남는 첫 것만 · 유형이 남지 않은 발화는 뺌.
    # 조문을 안 준 발화는 빈 목록. scanned_version 은 이 전사본 version(1).
    assert _key_scan(envelope) == _expected(
        "DONE",
        "roberta_test",
        [_seg("seg_001", ["PHYSICAL"]), _seg("seg_003", ["NEGLECT", "PHYSICAL"])],
        scanned_version=1,
    )
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

    assert _key_scan(envelope) == _expected("DONE", "roberta_test", [], scanned_version=1)


def test_legal_references_are_kept_per_segment_and_junk_is_dropped(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    long_text = "가" * 1500
    many = [{**REFERENCE, "abuse_type": "PHYSICAL", "item_label": f"제{index}호"} for index in range(12)]

    _use_scanner(
        monkeypatch,
        lambda stt_result: {
            "model": "roberta_test",
            "segments": [
                {
                    "segment_id": "seg_001",
                    "abuse_types": ["EMOTIONAL"],
                    "legal_references": [
                        REFERENCE,  # 그대로(점수는 소수 셋째 자리)
                        {**REFERENCE, "abuse_type": "OTHER"},  # 모르는 유형 → 뺌
                        {**REFERENCE, "law_name": ""},  # 법령 이름 없음 → 뺌
                        "bad",  # dict 아님 → 뺌
                        {**REFERENCE, "abuse_type": "NEGLECT"},  # 이 발화에 남은 유형이 아님 → 뺌
                        {**REFERENCE, "abuse_type": None, "text": long_text, "score": "0.9"},  # 유형 없음은 둠 · 글자 수 · 점수 모양
                    ],
                },
                {"segment_id": "seg_002", "abuse_types": ["PHYSICAL"], "legal_references": many},
                {"segment_id": "seg_003", "abuse_types": ["PHYSICAL"], "legal_references": "bad"},
            ],
        },
    )

    envelope = transcribed_session(client, counselor_headers, session["id"])
    segments = _key_scan(envelope)["segments"]

    assert segments[0]["legal_references"] == [
        SAVED_REFERENCE,
        {**SAVED_REFERENCE, "abuse_type": None, "text": "가" * 1000, "score": None},
    ]
    assert len(segments[1]["legal_references"]) == key_scan_service.MAX_REFERENCES_PER_SEGMENT
    assert segments[2] == _seg("seg_003", ["PHYSICAL"])


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
    assert _key_scan(envelope) == _expected("FAILED")
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
    assert _key_scan(envelope) == _expected("FAILED")


def test_module_load_runtime_error_fails_scan_but_stt_succeeds(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    # ImportError 가 아닌 예외(모델 파일 · CUDA 초기화 등)도 STT 를 실패시키지 않는다(민규 #114 R1).
    def broken():
        raise RuntimeError("가상 CUDA 초기화 실패")

    monkeypatch.setattr(key_scan_service, "_load_scanner", broken)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert envelope["transcript"]["segments"]
    assert _key_scan(envelope) == _expected("FAILED")


def test_slow_module_load_counts_toward_timeout(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    # 불러오기 시간도 제한 안에 든다 — 스캐너 자체는 빨라도 불러오기가 길면 FAILED(민규 #114 R2).
    monkeypatch.setattr(settings, "KEY_SCAN_TIMEOUT_SECONDS", 0.05)

    def slow_load():
        time.sleep(0.35)
        return lambda stt_result: {"model": "late", "segments": [{"segment_id": "seg_001", "abuse_types": ["PHYSICAL"]}]}

    monkeypatch.setattr(key_scan_service, "_load_scanner", slow_load)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    assert _key_scan(envelope) == _expected("FAILED")


# =========================================================
# 원문 수정 — 직전 결과를 복사해 두고 저장한 원문으로 다시 스캔(비동기)
# =========================================================

def test_edit_starts_refresh_and_rescans_the_saved_text(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, calls
) -> None:
    _use_scanner(monkeypatch, _scanner_by_text(calls))
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]
    assert len(calls) == 1

    data = _patch(
        client,
        counselor_headers,
        session["id"],
        segments=[{**first, "text": "고친 가상 문장"}],
        removed_segment_ids=["seg_002"],
    )

    # 응답: 새 version 은 REFRESHING — 직전 결과(지운 발화만 뺌)를 보여 주고 scanned_version 은 직전 version 이다.
    assert data["version"] == 2
    key_scan = data["key_scan"]
    assert isinstance(key_scan.pop("started_at"), str)
    expected = _expected("REFRESHING", "roberta_test", [_seg("seg_001", ["PHYSICAL"])], scanned_version=1)
    expected.pop("started_at")
    assert key_scan == expected

    # 응답 뒤 백그라운드 작업이 저장한 원문(고친 문장 · seg_002 없음)으로 다시 스캔해 DONE 으로 바꾼다.
    assert len(calls) == 2
    rescanned = calls[1]["segments"]
    assert [segment["segment_id"] for segment in rescanned] and "seg_002" not in [s["segment_id"] for s in rescanned]
    assert any(segment["text"] == "고친 가상 문장" for segment in rescanned)

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert envelope["transcript"]["version"] == 2
    assert _key_scan(envelope) == _expected(
        "DONE", "roberta_test", [_seg("seg_001", ["EMOTIONAL"], [SAVED_REFERENCE])], scanned_version=2
    )


def test_edit_without_modeling_copies_previous_result_and_does_not_rescan(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, calls
) -> None:
    _use_scanner(monkeypatch, _scanner_by_text(calls))
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]

    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")

    data = _patch(client, counselor_headers, session["id"], segments=[{**first, "text": "고친 가상 문장"}])

    assert data["key_scan"] == _expected(
        "DONE", "roberta_test", [_seg("seg_001", ["PHYSICAL"]), _seg("seg_002", ["NEGLECT"])], scanned_version=1
    )
    assert len(calls) == 1
    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert _key_scan(envelope)["status"] == "DONE"


def test_rescan_failure_keeps_the_previous_result(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    _use_scanner(monkeypatch, lambda stt_result: _first_scan())
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]

    def broken(stt_result):
        raise RuntimeError(SECRET_TEXT)

    _use_scanner(monkeypatch, broken)

    data = _patch(client, counselor_headers, session["id"], segments=[{**first, "text": "고친 가상 문장"}])
    assert data["key_scan"]["status"] == "REFRESHING"

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    # 다시 스캔은 실패했지만 저장 전 결과(직전 version 의 발화 · scanned_version 1)는 그대로 보인다.
    assert _key_scan(envelope) == _expected(
        "FAILED", "roberta_test", [_seg("seg_001", ["PHYSICAL"]), _seg("seg_002", ["NEGLECT"])], scanned_version=1
    )


def test_stale_refresh_is_closed_as_failed_on_get(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch
) -> None:
    _use_scanner(monkeypatch, lambda stt_result: _first_scan())
    transcribed_session(client, counselor_headers, session["id"])
    transcript = _latest_transcript(session["id"])

    # 작업이 사라진 REFRESHING(서버 재시작 등) — 제한 시간 + 여유를 넘겼다.
    old = datetime.now(timezone.utc) - timedelta(
        seconds=settings.KEY_SCAN_TIMEOUT_SECONDS + key_scan_service.STALE_GRACE_SECONDS + 5
    )
    _set_key_scan(
        transcript.id,
        {
            "status": "REFRESHING",
            "model": "roberta_test",
            "segments": [_seg("seg_001", ["PHYSICAL"])],
            "scanned_version": 1,
            "started_at": old.isoformat(),
        },
    )

    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert _key_scan(envelope) == _expected("FAILED", "roberta_test", [_seg("seg_001", ["PHYSICAL"])], scanned_version=1)

    # 아직 제한 시간 안인 REFRESHING 은 그대로 둔다.
    fresh = datetime.now(timezone.utc) - timedelta(seconds=1)
    _set_key_scan(transcript.id, {"status": "REFRESHING", "model": "roberta_test", "segments": [], "started_at": fresh.isoformat()})
    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert _key_scan(envelope)["status"] == "REFRESHING"


def test_refresh_job_skips_superseded_or_changed_rows(
    client: TestClient, counselor_headers, session: dict, modeling, monkeypatch, calls
) -> None:
    _use_scanner(monkeypatch, _scanner_by_text(calls))
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]

    _patch(client, counselor_headers, session["id"], segments=[{**first, "text": "고친 가상 문장 1"}])
    second = _latest_transcript(session["id"])
    _patch(client, counselor_headers, session["id"], segments=[{**first, "text": "고친 가상 문장 2"}])
    third = _latest_transcript(session["id"])
    assert (second.version, third.version) == (2, 3)
    assert len(calls) == 3  # STT 1 + 저장 2 (각 version 의 작업이 돌았다)

    # 더 새 version 이 있는 version 2 의 REFRESHING 은 모델을 돌리지 않고 그대로 둔다(그 version 은 더는 보이지 않는다).
    marker = datetime.now(timezone.utc).isoformat()
    _set_key_scan(second.id, {"status": "REFRESHING", "model": "roberta_test", "segments": [], "started_at": marker})
    key_scan_service.refresh(second.id, marker)
    assert len(calls) == 3
    assert _latest_transcript(session["id"]).id == third.id

    # 시작 시각이 다른(다른 저장이 먼저 손댄) 행도 돌리지 않는다.
    _set_key_scan(third.id, {"status": "REFRESHING", "model": "roberta_test", "segments": [], "started_at": marker})
    key_scan_service.refresh(third.id, "2026-01-01T00:00:00+00:00")
    assert len(calls) == 3

    # 맞는 시작 시각이면 돌리고 DONE 으로 바꾼다.
    key_scan_service.refresh(third.id, marker)
    assert len(calls) == 4
    envelope = _get_transcript(client, counselor_headers, session["id"]).json()["data"]
    assert _key_scan(envelope)["status"] == "DONE" and _key_scan(envelope)["scanned_version"] == 3


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
    assert _key_scan(envelope)["segments"] == [_seg("seg_001", ["PHYSICAL"])]


def test_copy_for_new_version_handles_old_and_refreshing_values() -> None:
    # 이 기능 전 전사본(null)은 복사해도 null 이다.
    assert key_scan_service.copy_for_new_version(None, ["seg_001"]) is None
    assert key_scan_service.copy_for_new_version(
        {"status": "SKIPPED", "model": None, "segments": []}, ["seg_001"]
    ) == {"status": "SKIPPED", "model": None, "segments": []}

    # 직전 version 이 아직 다시 스캔하는 중이면 복사본은 그 작업과 무관하다 — 발화가 남으면 DONE, 없으면 FAILED, started_at 없음.
    refreshing = {"status": "REFRESHING", "model": "m", "segments": [_seg("seg_001", ["PHYSICAL"])], "scanned_version": 1, "started_at": "x"}
    assert key_scan_service.copy_for_new_version(refreshing, []) == {
        "status": "DONE", "model": "m", "segments": [_seg("seg_001", ["PHYSICAL"])], "scanned_version": 1
    }
    assert key_scan_service.copy_for_new_version(refreshing, ["seg_001"])["status"] == "FAILED"

    # begin_refresh 는 복사본에 REFRESHING · 시작 시각을 붙인다. 직전 값이 없으면 빈 segments 로 시작한다.
    started = key_scan_service.begin_refresh(None, [])
    assert started["status"] == "REFRESHING" and started["segments"] == [] and isinstance(started["started_at"], str)


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
