# 실행 중인 Backend 에 대해 전체 상담 Flow 를 한 번 수행하는 Smoke Test.
#
# pytest 는 TestClient 를 사용하므로 BackgroundTask 가 즉시 끝난다.
# 이 script 는 실제 서버에 붙어 Polling 동작까지 확인하기 때문에
# 통합/시연 환경 점검(05_UI_INTEGRATION_QA_PROMPT.md)에 사용할 수 있다.
#
# 사용 예:
#   uvicorn app.main:app --port 8000
#   python -m scripts.smoke_api --email admin@ispot.example.com --password demo-pass-1234

import argparse
import struct
import sys
import time
from typing import Any, Dict, Optional

import httpx

TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 0.5


def make_wav_bytes(duration_ms: int = 1000, sample_rate: int = 8000) -> bytes:
    """검증용 무음 WAV. 실제 상담 음성을 사용하지 않는다."""

    channels = 1
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    data_size = int(byte_rate * duration_ms / 1000)

    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, sample_rate, byte_rate, channels * bits // 8, bits)
        + b"data"
        + struct.pack("<I", data_size)
        + b"\x00" * data_size
    )


class SmokeClient:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
        self.headers: Dict[str, str] = {}

    def close(self) -> None:
        self.client.close()

    def call(
        self,
        method: str,
        path: str,
        *,
        expect: int,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = self.client.request(
            method,
            path,
            json=json,
            files=files,
            headers=self.headers,
        )

        if response.status_code != expect:
            raise SystemExit(
                f"FAIL {method} {path}\n"
                f"  expected {expect}, got {response.status_code}\n"
                f"  body: {response.text}"
            )

        if response.status_code == 204:
            return {}

        return response.json().get("data", {})

    def poll_until(self, path: str, field: str, targets: set, label: str) -> Dict[str, Any]:
        deadline = time.monotonic() + TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            data = self.call("GET", path, expect=200)
            status = data.get(field)

            if status in targets:
                return data

            time.sleep(POLL_INTERVAL_SECONDS)

        raise SystemExit(f"FAIL {label}: {TIMEOUT_SECONDS}초 안에 완료되지 않았습니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="I-SPOT Backend Smoke Test")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)

    args = parser.parse_args()

    api = SmokeClient(args.base_url)
    step = 0

    def log(message: str) -> None:
        nonlocal step
        step += 1
        print(f"[{step:2d}] {message}")

    try:
        health = api.call("GET", "/health", expect=200)
        log(f"health: db={health['database']} stt={health['stt_provider']} ai={health['ai_provider']}")

        login = api.call(
            "POST",
            "/api/v1/auth/login",
            expect=200,
            json={"email": args.email, "password": args.password},
        )
        api.headers = {"Authorization": f"Bearer {login['access_token']}"}
        log(f"login: {login['user']['email']} ({login['user']['role']})")

        case = api.call(
            "POST",
            "/api/v1/cases",
            expect=201,
            json={
                "title": "Smoke Test 사례",
                "child_alias": "아동_SMOKE",
                "child_birth_year": 2015,
            },
        )
        log(f"case 생성: {case['case_number']}")

        session = api.call(
            "POST",
            f"/api/v1/cases/{case['id']}/sessions",
            expect=201,
            json={"title": "Smoke 1회기"},
        )
        session_id = session["id"]
        log(f"session 생성: #{session['session_number']} status={session['status']}")

        upload = api.call(
            "POST",
            f"/api/v1/sessions/{session_id}/audio",
            expect=201,
            files={"file": ("smoke.wav", make_wav_bytes(), "audio/wav")},
        )
        log(
            f"audio 업로드: {upload['audio']['size_bytes']} bytes "
            f"duration={upload['audio']['duration_ms']}ms status={upload['session_status']}"
        )

        api.call("POST", f"/api/v1/sessions/{session_id}/transcript", expect=202)
        log("STT 요청 (202)")

        envelope = api.poll_until(
            f"/api/v1/sessions/{session_id}/transcript",
            "session_status",
            {"STT_REVIEW_REQUIRED", "STT_FAILED"},
            "STT 완료 대기",
        )

        if envelope["session_status"] == "STT_FAILED":
            raise SystemExit(f"FAIL STT: {envelope.get('error')}")

        segments = envelope["transcript"]["segments"]
        log(f"STT 완료: version={envelope['transcript']['version']} segments={len(segments)}")

        first_segment_id = segments[0]["segment_id"]

        edited = api.call(
            "PATCH",
            f"/api/v1/sessions/{session_id}/transcript",
            expect=200,
            json={
                "segments": [
                    {"segment_id": first_segment_id, "text": "상담사가 확인한 문장입니다."}
                ]
            },
        )
        log(f"transcript 수정: version={edited['version']} edited={edited['edited_segment_ids']}")

        confirmed = api.call(
            "POST", f"/api/v1/sessions/{session_id}/transcript/confirm", expect=200
        )
        log(f"transcript 확정: is_confirmed={confirmed['is_confirmed']}")

        api.call("POST", f"/api/v1/sessions/{session_id}/analysis", expect=202)
        log("AI 분석 요청 (202)")

        analysis_envelope = api.poll_until(
            f"/api/v1/sessions/{session_id}/analysis",
            "session_status",
            {"AI_REVIEW_REQUIRED", "AI_FAILED"},
            "AI 분석 완료 대기",
        )

        if analysis_envelope["session_status"] == "AI_FAILED":
            raise SystemExit(f"FAIL AI: {analysis_envelope.get('error')}")

        analysis = analysis_envelope["analysis"]
        log(
            f"AI 완료: provider={analysis['provider']} "
            f"transcript_version={analysis['transcript_version']} "
            f"key_points={len(analysis['result']['summary']['key_points'])} "
            f"evidence={len(analysis['summary_evidence'])}"
        )

        summary_envelope = api.call(
            "GET", f"/api/v1/sessions/{session_id}/summary", expect=200
        )
        log(f"summary 초안: status={summary_envelope['summary']['status']}")

        updated = api.call(
            "PATCH",
            f"/api/v1/sessions/{session_id}/summary",
            expect=200,
            json={
                "overview": "Smoke Test 검수 요약",
                "key_points": ["확인된 내용", "추가 확인 필요"],
            },
        )
        log(f"summary 수정: is_edited={updated['is_edited']}")

        approved = api.call(
            "POST", f"/api/v1/sessions/{session_id}/summary/approve", expect=200
        )
        log(f"summary 승인: status={approved['status']}")

        detail = api.call("GET", f"/api/v1/sessions/{session_id}", expect=200)
        log(
            f"재조회: status={detail['status']} "
            f"transcript_version={detail['transcript_version']} "
            f"summary_approved={detail['summary_approved']}"
        )

        assert detail["status"] == "APPROVED"
        assert detail["summary_approved"] is True
        assert detail["transcript_version"] == 2

        final_summary = api.call(
            "GET", f"/api/v1/sessions/{session_id}/summary", expect=200
        )["summary"]

        assert final_summary["overview"] == "Smoke Test 검수 요약"

        error_body = api.client.get(
            "/api/v1/cases/00000000-0000-0000-0000-000000000000", headers=api.headers
        ).json()

        assert error_body["error"]["code"] == "CASE_NOT_FOUND"
        log("오류 Response Contract 확인: error.code / error.message")

        print("\nSMOKE TEST PASSED")

        return 0
    finally:
        api.close()


if __name__ == "__main__":
    sys.exit(main())
