# 데이터 무결성 테스트 — 삭제 · 번호 생성 · 재분석 이후에도 데이터가 어긋나지 않는지.

import types
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.ai_adapter import set_ai_adapter_override
from app.core import storage
from app.core.database import SessionLocal
from app.models.audio import AudioFile
from app.models.case import Case
from app.schemas.session import SessionCreateRequest
from app.services import session_service
from tests.conftest import create_case, upload_audio
from tests.test_analysis import FailingAIAdapter, _run_analysis, analyzed_session


# =========================================================
# 사례 번호
# =========================================================

def test_case_number_generation_works_after_deleting_an_earlier_case(
    client: TestClient, counselor_headers, admin_headers
) -> None:
    """중간 사례를 지운 뒤에도 새 사례를 만들 수 있어야 한다.

    번호를 "기존 개수 + 1" 로 만들면, 1·2·3 중 1 을 지운 뒤 개수는 2 라서
    이미 있는 3 번을 다시 만들려다 계속 실패한다.
    """

    first = create_case(client, counselor_headers)
    second = create_case(client, counselor_headers)
    third = create_case(client, counselor_headers)

    assert client.delete(f"/api/v1/cases/{first['id']}", headers=admin_headers).status_code == 204

    response = client.post(
        "/api/v1/cases",
        json={"title": "삭제 후 새 사례", "child_alias": "아동_009"},
        headers=counselor_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["data"]["case_number"] not in {
        second["case_number"],
        third["case_number"],
    }


# =========================================================
# 사례 삭제 시 음성 파일
# =========================================================

def test_deleting_case_removes_stored_audio_files(
    client: TestClient, counselor_headers, admin_headers, session: dict
) -> None:
    """사례를 지우면 그 아래 회기의 상담 음성 파일도 저장소에서 지워져야 한다.

    DB 는 연쇄 삭제되지만 파일은 따로 지워야 한다. 남으면 삭제한 아동 상담 음성이
    디스크에 그대로 남는다(회기 삭제는 이미 파일을 지운다).
    """

    status_code, _ = upload_audio(client, counselor_headers, session["id"])
    assert status_code == 201

    with SessionLocal() as db:
        relative_path = db.scalar(
            select(AudioFile.path).where(AudioFile.session_id == uuid.UUID(session["id"]))
        )

    stored = storage.resolve_stored_path(relative_path)
    assert stored.is_file()

    response = client.delete(f"/api/v1/cases/{session['case_id']}", headers=admin_headers)

    assert response.status_code == 204
    assert not stored.exists(), "사례 삭제 후에도 상담 음성 파일이 남아 있다"


# =========================================================
# 재분석 이후 요약 근거 발화
# =========================================================

def test_summary_evidence_survives_failed_reanalysis(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """재분석이 실패해도 요약 화면의 근거 발화는 요약을 만든 분석 기준으로 유지된다.

    최신 분석 기준으로 가져오면, 실패한 재분석에는 근거가 없어서 요약은 그대로인데
    근거 발화만 사라진다.
    """

    analyzed_session(client, counselor_headers, session["id"])
    summary_url = f"/api/v1/sessions/{session['id']}/summary"

    before = client.get(summary_url, headers=counselor_headers).json()["data"]
    assert before["summary_evidence"]

    set_ai_adapter_override(FailingAIAdapter())
    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    after = client.get(summary_url, headers=counselor_headers).json()["data"]

    assert after["session_status"] == "AI_FAILED"
    assert after["summary"]["overview"] == before["summary"]["overview"]
    assert after["summary_evidence"] == before["summary_evidence"]


# =========================================================
# 회기 번호 — 동시에 만든 경우
# =========================================================

def test_concurrent_session_creation_gets_next_number_instead_of_server_error(
    client: TestClient, counselor_id, case: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    """같은 사례에 회기를 거의 동시에 만들면 둘 다 만들어지고 번호만 다르다.

    두 요청이 같은 "다음 번호" 를 계산하면 (case_id, session_number) 유니크 제약에
    걸린다. 처리하지 않으면 500 이 난다.
    """

    user = types.SimpleNamespace(id=counselor_id)
    first_db, second_db = SessionLocal(), SessionLocal()

    try:
        first_case = first_db.get(Case, uuid.UUID(case["id"]))
        second_case = second_db.get(Case, uuid.UUID(case["id"]))

        session_service.create_session(
            first_db, first_case, user, SessionCreateRequest(title="먼저 만든 회기")
        )

        # 두 번째 요청은 첫 번째가 저장하기 전에 "다음 번호 = 1" 을 계산해 둔 상태다.
        real_scalar = second_db.scalar
        calls = {"count": 0}

        def stale_once(*args, **kwargs):
            calls["count"] += 1
            return 0 if calls["count"] == 1 else real_scalar(*args, **kwargs)

        monkeypatch.setattr(second_db, "scalar", stale_once)

        created = session_service.create_session(
            second_db, second_case, user, SessionCreateRequest(title="동시에 만든 회기")
        )

        assert created.session_number == 2
    finally:
        first_db.close()
        second_db.close()
