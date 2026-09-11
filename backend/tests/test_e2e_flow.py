# Integration Test.
#
# 05_UI_INTEGRATION_QA_PROMPT.md §7 의 E2E 시나리오를 Backend 관점에서 검증한다.
#
#   로그인 → Case 조회 → Case 선택 → Session 생성 → Audio Upload
#   → STT → Transcript 표시/수정 → AI Summary → Summary 수정 → 승인
#   → Case Detail 재진입 → 데이터 유지 확인

from fastapi.testclient import TestClient

from tests.conftest import COUNSELOR_PASSWORD, upload_audio


def test_full_consultation_flow_persists_after_reentry(
    client: TestClient, counselor_id
) -> None:
    # 1) 로그인
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "counselor.a@ispot.example.com", "password": COUNSELOR_PASSWORD},
    )

    assert login.status_code == 200

    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}

    # 2) Case 생성 + 목록 조회
    case = client.post(
        "/api/v1/cases",
        json={"title": "E2E 사례", "child_alias": "아동_E2E", "child_birth_year": 2014},
        headers=headers,
    ).json()["data"]

    case_list = client.get("/api/v1/cases", headers=headers).json()["data"]

    assert case["id"] in [item["id"] for item in case_list["items"]]

    # 3) Session 생성
    session = client.post(
        f"/api/v1/cases/{case['id']}/sessions",
        json={"title": "E2E 1회기"},
        headers=headers,
    ).json()["data"]

    assert session["status"] == "CREATED"

    session_id = session["id"]

    # 4) Audio Upload
    status_code, upload_body = upload_audio(client, headers, session_id)

    assert status_code == 201
    assert upload_body["data"]["session_status"] == "AUDIO_UPLOADED"

    # 5) STT 실행 → 검수 대기
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/transcript", headers=headers
        ).status_code
        == 202
    )

    transcript_envelope = client.get(
        f"/api/v1/sessions/{session_id}/transcript", headers=headers
    ).json()["data"]

    assert transcript_envelope["session_status"] == "STT_REVIEW_REQUIRED"

    segments = transcript_envelope["transcript"]["segments"]

    assert segments

    # 6) Transcript 수정
    first_segment_id = segments[0]["segment_id"]

    edited = client.patch(
        f"/api/v1/sessions/{session_id}/transcript",
        json={
            "segments": [
                {"segment_id": first_segment_id, "text": "상담사가 확인한 문장입니다."}
            ]
        },
        headers=headers,
    ).json()["data"]

    assert edited["version"] == 2

    # 7) Transcript 확정
    confirmed = client.post(
        f"/api/v1/sessions/{session_id}/transcript/confirm", headers=headers
    ).json()["data"]

    assert confirmed["is_confirmed"] is True

    # 8) AI 분석
    assert (
        client.post(
            f"/api/v1/sessions/{session_id}/analysis", headers=headers
        ).status_code
        == 202
    )

    analysis_envelope = client.get(
        f"/api/v1/sessions/{session_id}/analysis", headers=headers
    ).json()["data"]

    assert analysis_envelope["session_status"] == "AI_REVIEW_REQUIRED"
    # 분석은 확정된 version 2 를 사용해야 한다.
    assert analysis_envelope["analysis"]["transcript_version"] == 2

    # 9) Summary 수정
    updated_summary = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={
            "overview": "E2E 검수 완료 요약",
            "key_points": ["상담사 확인 항목 1", "추가 확인 필요"],
        },
        headers=headers,
    ).json()["data"]

    assert updated_summary["is_edited"] is True

    # 10) 문서 생성 + 승인
    document = client.post(
        f"/api/v1/sessions/{session_id}/documents",
        json={"title": "상담 기록", "content": "상담사가 작성한 기록"},
        headers=headers,
    ).json()["data"]

    approved_document = client.post(
        f"/api/v1/sessions/{session_id}/documents/{document['id']}/approve",
        headers=headers,
    ).json()["data"]

    assert approved_document["status"] == "APPROVED"

    # 11) Summary 승인
    approved_summary = client.post(
        f"/api/v1/sessions/{session_id}/summary/approve", headers=headers
    ).json()["data"]

    assert approved_summary["status"] == "APPROVED"

    # 12) 재로그인 후 Case Detail 재진입 (새로고침 시나리오)
    relogin = client.post(
        "/api/v1/auth/login",
        json={"email": "counselor.a@ispot.example.com", "password": COUNSELOR_PASSWORD},
    )

    fresh_headers = {
        "Authorization": f"Bearer {relogin.json()['data']['access_token']}"
    }

    case_detail = client.get(
        f"/api/v1/cases/{case['id']}", headers=fresh_headers
    ).json()["data"]

    assert case_detail["session_count"] == 1

    session_detail = client.get(
        f"/api/v1/sessions/{session_id}", headers=fresh_headers
    ).json()["data"]

    # 13) 데이터 유지 확인
    assert session_detail["status"] == "APPROVED"
    assert session_detail["has_audio"] is True
    assert session_detail["has_transcript"] is True
    assert session_detail["transcript_version"] == 2
    assert session_detail["transcript_confirmed"] is True
    assert session_detail["has_analysis"] is True
    assert session_detail["summary_approved"] is True
    assert session_detail["error"] is None

    final_summary = client.get(
        f"/api/v1/sessions/{session_id}/summary", headers=fresh_headers
    ).json()["data"]["summary"]

    assert final_summary["overview"] == "E2E 검수 완료 요약"
    assert final_summary["key_points"] == ["상담사 확인 항목 1", "추가 확인 필요"]
    assert final_summary["status"] == "APPROVED"

    final_transcript = client.get(
        f"/api/v1/sessions/{session_id}/transcript", headers=fresh_headers
    ).json()["data"]["transcript"]

    assert final_transcript["version"] == 2

    edited_segment = next(
        segment
        for segment in final_transcript["segments"]
        if segment["segment_id"] == first_segment_id
    )

    assert edited_segment["text"] == "상담사가 확인한 문장입니다."


def test_every_response_uses_data_or_error_envelope(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """성공/실패 어떤 경로에서도 Response Contract 가 유지되어야 한다."""

    success_cases = [
        ("GET", "/api/v1/cases", None),
        ("GET", "/api/v1/auth/me", None),
        ("GET", f"/api/v1/sessions/{session['id']}", None),
        ("GET", f"/api/v1/sessions/{session['id']}/transcript", None),
        ("GET", f"/api/v1/sessions/{session['id']}/analysis", None),
        ("GET", f"/api/v1/sessions/{session['id']}/summary", None),
        ("GET", f"/api/v1/sessions/{session['id']}/documents", None),
        ("GET", "/health", None),
    ]

    for method, url, payload in success_cases:
        response = client.request(method, url, json=payload, headers=counselor_headers)

        assert response.status_code == 200, url

        body = response.json()

        assert list(body.keys()) == ["data"], url

    failure_cases = [
        ("GET", "/api/v1/cases/00000000-0000-0000-0000-000000000000", 404),
        ("GET", "/api/v1/nope", 404),
        ("POST", "/api/v1/cases", 422),
        ("GET", f"/api/v1/sessions/{session['id']}/audio", 404),
    ]

    for method, url, expected_status in failure_cases:
        response = client.request(method, url, json={}, headers=counselor_headers)

        assert response.status_code == expected_status, url

        body = response.json()

        assert "data" not in body, url
        assert set(body["error"].keys()) <= {"code", "message", "details"}, url
        assert body["error"]["code"], url
        assert body["error"]["message"], url


def test_health_endpoint_reports_database_and_providers(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["stt_provider"] == "mock"
    assert data["ai_provider"] == "mock"
