# 구간별 음성 참고 표시(stt/voice_marks) Backend 연결 시험 — 호출 · 저장 · 실패 행 · 확정 때 재분석 · 조회.
#
# 분석 함수는 가짜를 주입한다(librosa 없이 돈다). 실제 모듈의 계산 시험은 루트 tests/test_voice_marks.py(STT CI).
# 결과 모양은 stt/voice_marks.md 3절과 같게 만든다.

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.models.audio_feature import AudioFeature
from app.services import voice_marks_service
from app.services.voice_marks_service import set_voice_marks_analyzer_override
from tests.conftest import upload_audio

SEGMENT_INPUT_KEYS = {"segment_id", "speaker", "start_ms", "end_ms"}


def first_child_id(segments: List[Dict[str, Any]]) -> Optional[str]:
    return next((s["segment_id"] for s in segments if s["speaker"] == "CHILD"), None)


def make_result(segments: List[Dict[str, Any]], flagged=None) -> Dict[str, Any]:
    """분석 모듈과 같은 모양의 결과. flagged(없으면 첫 아동 구간)에 든 아동 구간만 떨림 표시가 켜진다."""

    if flagged is None:
        flagged = (first_child_id(segments),)

    entries = []

    for segment in segments:
        if segment["speaker"] != "CHILD":
            entries.append(
                {
                    **segment,
                    "status": "UNDETERMINED",
                    "reason": "NOT_CHILD_SEGMENT",
                    "tremor": None,
                    "mumble": None,
                    "soft": None,
                    "flag_any": None,
                }
            )
            continue

        flag = segment["segment_id"] in flagged
        entries.append(
            {
                **segment,
                "status": "ANALYZED",
                "reason": None,
                "tremor": {"value": 21.4, "unit": "cent", "z": 2.0 if flag else 0.1, "flag": flag},
                "mumble": {"value": 1850.0, "unit": "Hz", "z": -0.2, "flag": False},
                "soft": {"value": -38.2, "unit": "LUFS", "z": -0.1, "flag": False},
                "flag_any": flag,
            }
        )

    child_total = sum(1 for segment in segments if segment["speaker"] == "CHILD")

    return {
        "schema_version": "1.0",
        "analyzer": "stt.voice_marks",
        "analyzer_version": "0.1.0-test",
        "status": "ANALYZED",
        "reason": None,
        "reference": {
            "child_segments_total": child_total,
            "child_segments_used": child_total,
            "min_required": 8,
            "note": "시험용",
        },
        "thresholds": {
            "tremor_z_above": 1.6066,
            "mumble_z_below": -1.619,
            "soft_z_below": -2.5,
            "basis": "시험용",
        },
        "segments": entries,
    }


class FakeAnalyzer:
    """부른 인자를 기록하고, 정해진 대로 결과를 주거나 실패한다."""

    def __init__(
        self,
        *,
        flagged=None,
        error: Optional[Exception] = None,
        sleep_seconds: float = 0.0,
        fixed_result: Any = None,
    ) -> None:
        self.flagged = flagged
        self.error = error
        self.sleep_seconds = sleep_seconds
        self.fixed_result = fixed_result
        self.calls: List[Any] = []

    def __call__(self, audio_path, segments):
        self.calls.append((audio_path, segments))

        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

        if self.error is not None:
            raise self.error

        if self.fixed_result is not None:
            return self.fixed_result

        return make_result(segments, self.flagged)


@pytest.fixture(autouse=True)
def _reset_analyzer():
    set_voice_marks_analyzer_override(None)

    yield

    set_voice_marks_analyzer_override(None)


def _run_stt(client: TestClient, headers, session_id: str) -> None:
    status_code, body = upload_audio(client, headers, session_id)
    assert status_code == 201, body

    response = client.post(f"/api/v1/sessions/{session_id}/transcript", headers=headers)
    assert response.status_code == 202, response.text


def _get_transcript(client: TestClient, headers, session_id: str) -> dict:
    response = client.get(f"/api/v1/sessions/{session_id}/transcript", headers=headers)
    assert response.status_code == 200, response.text

    return response.json()["data"]


def _get_marks(client: TestClient, headers, session_id: str):
    return client.get(f"/api/v1/sessions/{session_id}/voice-marks", headers=headers)


def _row_count(db, session_id: str) -> int:
    rows = db.scalars(
        select(AudioFeature).where(AudioFeature.extractor == voice_marks_service.EXTRACTOR)
    ).all()

    return len([row for row in rows if str(row.session_id) == session_id])


# =========================================================
# STT 직후 계산 · 저장 · 조회
# =========================================================

def test_stt_completion_stores_marks_row_and_get_returns_it(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)

    _run_stt(client, counselor_headers, session["id"])

    envelope = _get_transcript(client, counselor_headers, session["id"])
    assert envelope["session_status"] == "STT_REVIEW_REQUIRED"
    segment_ids = [segment["segment_id"] for segment in envelope["transcript"]["segments"]]
    expected_flag = first_child_id(envelope["transcript"]["segments"])
    assert expected_flag is not None

    response = _get_marks(client, counselor_headers, session["id"])
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data is not None
    assert data["extractor"] == "stt.voice_marks"
    assert data["schema_version"] == "1.0"
    assert data["transcript_version"] == 1
    assert data["transcript_id"] == envelope["transcript"]["id"]

    audio = client.get(f"/api/v1/sessions/{session['id']}/audio", headers=counselor_headers)
    assert data["audio_file_id"] == audio.json()["data"]["id"]

    result = data["result"]
    assert result["status"] == "ANALYZED"
    # 구간은 전사본 순서 그대로, segment_id 로 잇는다.
    assert [entry["segment_id"] for entry in result["segments"]] == segment_ids
    flagged = [entry["segment_id"] for entry in result["segments"] if entry["flag_any"]]
    assert flagged == [expected_flag]
    assert result["thresholds"]["tremor_z_above"] == 1.6066
    assert len(analyzer.calls) == 1


def test_analyzer_receives_stored_audio_path_and_contract_segments(
    client: TestClient, counselor_headers, session: dict
) -> None:
    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)

    _run_stt(client, counselor_headers, session["id"])

    audio_path, segments = analyzer.calls[0]
    audio = client.get(f"/api/v1/sessions/{session['id']}/audio", headers=counselor_headers)
    stored = Path(os.environ["AUDIO_STORAGE_ROOT"]) / audio.json()["data"]["path"]

    assert isinstance(audio_path, str)
    assert Path(audio_path).resolve() == stored.resolve()
    assert Path(audio_path).is_file()

    transcript = _get_transcript(client, counselor_headers, session["id"])["transcript"]
    expected = [
        {
            "segment_id": segment["segment_id"],
            "speaker": segment["speaker"],
            "start_ms": segment["start_ms"],
            "end_ms": segment["end_ms"],
        }
        for segment in transcript["segments"]
    ]

    # 화자는 Enum 이 아니라 문자열, 시각은 정수 ms, 칸은 넷뿐이다(모듈이 JSON 으로 저장할 수 있게).
    assert segments == expected
    assert all(set(segment) == SEGMENT_INPUT_KEYS for segment in segments)
    assert all(type(segment["speaker"]) is str for segment in segments)


def test_voice_marks_off_by_default_stores_nothing_and_get_returns_null(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    assert settings.VOICE_MARKS_PROVIDER == "off"

    _run_stt(client, counselor_headers, session["id"])

    assert _get_transcript(client, counselor_headers, session["id"])["session_status"] == (
        "STT_REVIEW_REQUIRED"
    )
    assert _row_count(db, session["id"]) == 0

    response = _get_marks(client, counselor_headers, session["id"])
    assert response.status_code == 200
    assert response.json() == {"data": None}


# =========================================================
# 실패는 UNDETERMINED · ANALYSIS_ERROR 행으로, 회차 상태는 그대로
# =========================================================

def _assert_error_row(client: TestClient, headers, session_id: str) -> dict:
    assert _get_transcript(client, headers, session_id)["session_status"] == "STT_REVIEW_REQUIRED"

    data = _get_marks(client, headers, session_id).json()["data"]
    assert data is not None
    result = data["result"]
    assert result["status"] == "UNDETERMINED"
    assert result["reason"] == "ANALYSIS_ERROR"
    assert result["analyzer"] == "stt.voice_marks"
    assert result["thresholds"]["tremor_z_above"] is None

    transcript = _get_transcript(client, headers, session_id)["transcript"]
    assert [entry["segment_id"] for entry in result["segments"]] == [
        segment["segment_id"] for segment in transcript["segments"]
    ]
    assert all(entry["status"] == "UNDETERMINED" for entry in result["segments"])
    assert all(entry["reason"] == "ANALYSIS_ERROR" for entry in result["segments"])
    assert all(entry["flag_any"] is None for entry in result["segments"])

    child_count = sum(1 for segment in transcript["segments"] if segment["speaker"] == "CHILD")
    assert result["reference"]["child_segments_total"] == child_count

    return result


def test_analyzer_exception_stores_error_row_and_keeps_session_state(
    client: TestClient, counselor_headers, session: dict
) -> None:
    set_voice_marks_analyzer_override(FakeAnalyzer(error=RuntimeError("계산 실패")))

    _run_stt(client, counselor_headers, session["id"])

    _assert_error_row(client, counselor_headers, session["id"])


def test_analyzer_timeout_stores_error_row(
    client: TestClient, counselor_headers, session: dict, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "VOICE_MARKS_TIMEOUT_SECONDS", 0.2)
    set_voice_marks_analyzer_override(FakeAnalyzer(sleep_seconds=1.0))

    _run_stt(client, counselor_headers, session["id"])

    _assert_error_row(client, counselor_headers, session["id"])


def test_result_with_wrong_shape_is_stored_as_error_row(
    client: TestClient, counselor_headers, session: dict
) -> None:
    set_voice_marks_analyzer_override(FakeAnalyzer(fixed_result=["not", "a", "dict"]))

    _run_stt(client, counselor_headers, session["id"])

    _assert_error_row(client, counselor_headers, session["id"])


def test_error_result_helper_echoes_segments() -> None:
    segments = [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 1000},
        {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 1200, "end_ms": 3000},
    ]

    result = voice_marks_service.error_result(segments)

    assert result["status"] == "UNDETERMINED" and result["reason"] == "ANALYSIS_ERROR"
    assert result["reference"]["child_segments_total"] == 1
    assert [entry["segment_id"] for entry in result["segments"]] == ["seg_001", "seg_002"]
    assert result["segments"][1]["speaker"] == "CHILD"
    assert result["segments"][1]["start_ms"] == 1200
    assert result["segments"][1]["tremor"] is None


# =========================================================
# 확정 때 재분석 — 아동 구간이 바뀌었을 때만
# =========================================================

def test_confirm_without_changes_does_not_reanalyze(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)
    _run_stt(client, counselor_headers, session["id"])

    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )
    assert response.status_code == 200, response.text

    assert len(analyzer.calls) == 1
    assert _row_count(db, session["id"]) == 1
    assert _get_marks(client, counselor_headers, session["id"]).json()["data"]["transcript_version"] == 1


def test_confirm_reanalyzes_when_child_segments_changed(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)
    _run_stt(client, counselor_headers, session["id"])

    transcript = _get_transcript(client, counselor_headers, session["id"])["transcript"]
    # 검수에서 아동이 아니던 구간 하나를 아동으로 고친다(STT 직후 화자가 UNKNOWN 이던 구간이 대표적).
    changed = next(segment for segment in transcript["segments"] if segment["speaker"] != "CHILD")

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        headers=counselor_headers,
        json={"segments": [{"segment_id": changed["segment_id"], "speaker": "CHILD"}]},
    )
    assert response.status_code == 200, response.text
    assert len(analyzer.calls) == 1  # 수정만으로는 돌리지 않는다

    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )
    assert response.status_code == 200, response.text

    assert len(analyzer.calls) == 2
    _, segments = analyzer.calls[1]
    assert next(s for s in segments if s["segment_id"] == changed["segment_id"])["speaker"] == "CHILD"

    assert _row_count(db, session["id"]) == 2
    data = _get_marks(client, counselor_headers, session["id"]).json()["data"]
    assert data["transcript_version"] == 2
    assert any(
        entry["segment_id"] == changed["segment_id"] and entry["status"] == "ANALYZED"
        for entry in data["result"]["segments"]
    )


def test_confirm_runs_analysis_when_no_row_exists_yet(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    # STT 때는 꺼져 있었고(행 없음) 확정 때 켜진 경우: 한 번 돌린다.
    _run_stt(client, counselor_headers, session["id"])
    assert _row_count(db, session["id"]) == 0

    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)

    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )
    assert response.status_code == 200, response.text

    assert len(analyzer.calls) == 1
    assert _row_count(db, session["id"]) == 1


# =========================================================
# 조회 권한
# =========================================================

def test_get_voice_marks_requires_login_and_case_access(
    client: TestClient, counselor_headers, other_counselor_headers, session: dict
) -> None:
    set_voice_marks_analyzer_override(FakeAnalyzer())
    _run_stt(client, counselor_headers, session["id"])
    url = f"/api/v1/sessions/{session['id']}/voice-marks"

    assert client.get(url).status_code == 401

    forbidden = client.get(url, headers=other_counselor_headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    import uuid

    missing = client.get(f"/api/v1/sessions/{uuid.uuid4()}/voice-marks", headers=counselor_headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "SESSION_NOT_FOUND"


# =========================================================
# 교차검증(10/28)에서 잡힌 것 — 느린 옛 분석 · 계약을 어긴 분석기 출력
# =========================================================

def test_late_result_for_older_version_does_not_hide_newer_row(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    """v1 분석이 v2(확정 재분석)보다 늦게 저장돼도 조회는 v2 를 준다(저장 시각이 아니라 version 기준)."""

    import uuid as _uuid

    analyzer = FakeAnalyzer()
    set_voice_marks_analyzer_override(analyzer)
    _run_stt(client, counselor_headers, session["id"])

    transcript_v1 = _get_transcript(client, counselor_headers, session["id"])["transcript"]
    changed = next(s for s in transcript_v1["segments"] if s["speaker"] != "CHILD")
    client.patch(
        f"/api/v1/sessions/{session['id']}/transcript",
        headers=counselor_headers,
        json={"segments": [{"segment_id": changed["segment_id"], "speaker": "CHILD"}]},
    )
    assert (
        client.post(
            f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
        ).status_code
        == 200
    )
    assert _get_marks(client, counselor_headers, session["id"]).json()["data"]["transcript_version"] == 2

    # 느린 v1 분석이 이제야 끝나 저장되는 상황을 그대로 재현한다.
    voice_marks_service.analyze_for_transcript(
        _uuid.UUID(session["id"]), _uuid.UUID(transcript_v1["id"])
    )

    assert _row_count(db, session["id"]) == 3  # 이력은 남긴다
    data = _get_marks(client, counselor_headers, session["id"]).json()["data"]
    assert data["transcript_version"] == 2
    assert data["transcript_id"] != transcript_v1["id"]


def test_result_with_unknown_status_is_stored_as_error_row(
    client: TestClient, counselor_headers, session: dict
) -> None:
    def odd_status(audio_path, segments):
        result = make_result(segments)
        result["status"] = "DONE /tmp/secret-path"

        return result

    set_voice_marks_analyzer_override(odd_status)
    _run_stt(client, counselor_headers, session["id"])

    _assert_error_row(client, counselor_headers, session["id"])


def test_result_that_cannot_be_saved_as_json_is_stored_as_error_row(
    client: TestClient, counselor_headers, session: dict
) -> None:
    def with_set(audio_path, segments):
        result = make_result(segments)
        result["reference"]["note"] = {"not", "json"}

        return result

    set_voice_marks_analyzer_override(with_set)
    _run_stt(client, counselor_headers, session["id"])

    # 행이 없어지는 것이 아니라 ANALYSIS_ERROR 행이 남는다.
    _assert_error_row(client, counselor_headers, session["id"])


def test_confirm_survives_malformed_segment_keys_in_previous_row(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """저장된 결과의 아동 구간 시각이 정수가 아니어도(계약 위반) 확정은 200 이고, 재분석을 한 번 돌린다."""

    calls = []

    def malformed(audio_path, segments):
        calls.append(segments)
        result = make_result(segments)
        child = next(entry for entry in result["segments"] if entry["speaker"] == "CHILD")
        child["start_ms"] = []

        return result

    set_voice_marks_analyzer_override(malformed)
    _run_stt(client, counselor_headers, session["id"])
    assert len(calls) == 1

    response = client.post(
        f"/api/v1/sessions/{session['id']}/transcript/confirm", headers=counselor_headers
    )

    assert response.status_code == 200, response.text
    assert _get_transcript(client, counselor_headers, session["id"])["session_status"] == "STT_CONFIRMED"
    assert len(calls) == 2
