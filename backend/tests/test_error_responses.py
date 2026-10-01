# 예상하지 못한 오류 응답 테스트.
#
# 브라우저는 CORS 헤더가 없는 응답을 막는다. 500 응답에 CORS 헤더가 빠지면 Frontend 는
# {"error": {...}} 본문을 읽지 못하고 원인 없는 네트워크(CORS) 오류만 보게 된다.

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import case_service


def test_unexpected_error_keeps_error_contract_and_cors_headers(
    counselor_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    origin = settings.CORS_ORIGINS[0]

    def broken_list_cases(*args, **kwargs):
        raise RuntimeError("예상하지 못한 오류")

    monkeypatch.setattr(case_service, "list_cases", broken_list_cases)

    # 기본 TestClient 는 서버 예외를 테스트로 다시 던지므로, 실제 응답을 보려면 끈다.
    with TestClient(app, raise_server_exceptions=False) as raw_client:
        response = raw_client.get(
            "/api/v1/cases",
            headers={**counselor_headers, "Origin": origin},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."}
    }
    assert response.headers.get("access-control-allow-origin") == origin


# =========================================================
# FastAPI · Starlette 가 직접 만드는 오류
# =========================================================
#
# 경로 · method · 본문 형식 오류는 라우터에 닿기 전에 프레임워크가 만든다. 이때도 message 는
# 한국어여야 하고(API_CONTRACT 1.2), INTERNAL_ERROR 는 5xx 에만 쓴다(12절).

def test_method_not_allowed_uses_korean_message(client: TestClient, counselor_headers) -> None:
    response = client.put("/api/v1/auth/me", headers=counselor_headers)

    assert response.status_code == 405
    assert response.json() == {
        "error": {"code": "METHOD_NOT_ALLOWED", "message": "허용되지 않는 요청 방식입니다."}
    }


def test_malformed_multipart_body_is_validation_error(
    client: TestClient, counselor_headers, session: dict
) -> None:
    """boundary 없는 multipart 는 Starlette 가 400 으로 막는다. 서버 오류(INTERNAL_ERROR)가 아니다."""

    response = client.post(
        f"/api/v1/sessions/{session['id']}/audio",
        content=b"abc",
        headers={**counselor_headers, "Content-Type": "multipart/form-data"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "VALIDATION_ERROR", "message": "요청 형식이 올바르지 않습니다."}
    }
