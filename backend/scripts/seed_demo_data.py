# 실행 중인 Backend 에 데모용 상담 데이터를 생성한다.
#
# 목적
#   - Frontend 가 화면을 만들 때 필요한 "모든 상태"의 데이터를 준비한다.
#   - QA 가 시연/E2E 시나리오를 반복 실행할 수 있게 한다.
#
# 데이터 원칙 (docs/05_RULES.md)
#   - 전부 합성 데이터다. 실제 아동 정보를 사용하지 않는다.
#   - 아동 실명 대신 alias 만 쓴다.
#   - 학대 정황을 지어내지 않는다. 상담 내용은 mock STT 의 중립적인 예시 문장이다.
#
# 사용 예:
#   uvicorn app.main:app --port 8000
#   python -m scripts.seed_demo_data --admin-email admin@... --admin-password ...

import argparse
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

POLL_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 0.3

# 생성할 Session 의 목표 상태.
# Frontend 는 이 상태들에 대응하는 화면을 각각 만들어야 한다.
TARGET_STATES = [
    ("CREATED", "녹음 시작 전"),
    ("AUDIO_UPLOADED", "업로드 완료, STT 대기"),
    ("STT_REVIEW_REQUIRED", "STT 검수 필요"),
    ("STT_CONFIRMED", "원문 확정, AI 대기"),
    ("AI_REVIEW_REQUIRED", "AI 요약 검수 필요"),
    ("APPROVED", "승인 완료"),
]

# 합성 사례 정보. 실제 인물과 무관하다.
DEMO_CASES: List[Dict[str, Any]] = [
    {"title": "초기 상담", "child_alias": "아동_A001", "child_birth_year": 2015},
    {"title": "정기 상담", "child_alias": "아동_A002", "child_birth_year": 2013},
    {"title": "정기 상담", "child_alias": "아동_A003", "child_birth_year": 2016},
    {"title": "추가 면담", "child_alias": "아동_A004", "child_birth_year": 2012},
    {"title": "정기 상담", "child_alias": "아동_A005", "child_birth_year": 2014},
    {"title": "종결 전 상담", "child_alias": "아동_A006", "child_birth_year": 2011},
]


def make_wav_bytes(duration_ms: int = 1500, sample_rate: int = 8000) -> bytes:
    """검증용 무음 WAV. 실제 상담 음성이 아니다."""

    channels = 1
    bits = 16
    byte_rate = sample_rate * channels * bits // 8
    data_size = int(byte_rate * duration_ms / 1000)

    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVEfmt "
        + struct.pack(
            "<IHHIIHH",
            16, 1, channels, sample_rate, byte_rate,
            channels * bits // 8, bits,
        )
        + b"data"
        + struct.pack("<I", data_size)
        + b"\x00" * data_size
    )


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=30.0)
        self.headers: Dict[str, str] = {}

    def close(self) -> None:
        self.http.close()

    def login(self, email: str, password: str) -> Dict[str, Any]:
        data = self.call(
            "POST", "/api/v1/auth/login", 200,
            json={"email": email, "password": password},
        )
        self.headers = {"Authorization": f"Bearer {data['access_token']}"}

        return data["user"]

    def call(
        self,
        method: str,
        path: str,
        expect: int,
        *,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = self.http.request(
            method, path, json=json, files=files, headers=self.headers
        )

        if response.status_code != expect:
            raise SystemExit(
                f"실패 {method} {path}\n"
                f"  기대 {expect}, 실제 {response.status_code}\n"
                f"  {response.text}"
            )

        return {} if response.status_code == 204 else response.json().get("data", {})

    def wait_for_status(self, session_id: str, done: set, label: str) -> str:
        deadline = time.monotonic() + POLL_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            data = self.call("GET", f"/api/v1/sessions/{session_id}", 200)

            if data["status"] in done:
                return data["status"]

            time.sleep(POLL_INTERVAL_SECONDS)

        raise SystemExit(f"시간 초과: {label} (session={session_id})")


def advance_session(api: ApiClient, session_id: str, target: str) -> str:
    """Session 을 목표 상태까지 진행시킨다."""

    if target == "CREATED":
        return "CREATED"

    api.call(
        "POST", f"/api/v1/sessions/{session_id}/audio", 201,
        files={"file": ("consultation.wav", make_wav_bytes(), "audio/wav")},
    )

    if target == "AUDIO_UPLOADED":
        return target

    api.call("POST", f"/api/v1/sessions/{session_id}/transcript", 202)
    status = api.wait_for_status(
        session_id, {"STT_REVIEW_REQUIRED", "STT_FAILED"}, "STT 처리"
    )

    if status == "STT_FAILED":
        raise SystemExit(f"STT 실패: session={session_id}")

    if target == "STT_REVIEW_REQUIRED":
        return target

    # 상담사가 원문 일부를 수정한 상태를 만든다 (검수 화면 테스트용).
    envelope = api.call("GET", f"/api/v1/sessions/{session_id}/transcript", 200)
    segments = envelope["transcript"]["segments"]

    api.call(
        "PATCH", f"/api/v1/sessions/{session_id}/transcript", 200,
        json={
            "segments": [
                {
                    "segment_id": segments[0]["segment_id"],
                    "text": "상담사가 검수하며 수정한 문장입니다.",
                }
            ]
        },
    )
    api.call("POST", f"/api/v1/sessions/{session_id}/transcript/confirm", 200)

    if target == "STT_CONFIRMED":
        return target

    api.call("POST", f"/api/v1/sessions/{session_id}/analysis", 202)
    status = api.wait_for_status(
        session_id, {"AI_REVIEW_REQUIRED", "AI_FAILED"}, "AI 분석"
    )

    if status == "AI_FAILED":
        raise SystemExit(f"AI 분석 실패: session={session_id}")

    if target == "AI_REVIEW_REQUIRED":
        return target

    api.call(
        "PATCH", f"/api/v1/sessions/{session_id}/summary", 200,
        json={
            "overview": "상담사가 검토해 정리한 요약입니다.",
            "key_points": ["확인된 내용", "다음 회기에 추가 확인 필요"],
        },
    )
    api.call("POST", f"/api/v1/sessions/{session_id}/summary/approve", 200)

    return "APPROVED"


def main() -> int:
    parser = argparse.ArgumentParser(description="I-SPOT 데모 데이터 생성")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument(
        "--counselor-email",
        default="counselor@ispot.example.com",
        help="권한 분리 확인용으로 이 상담사에게도 사례를 1건 배정한다.",
    )

    args = parser.parse_args()

    api = ApiClient(args.base_url)
    created: List[Tuple[str, str, str]] = []

    try:
        user = api.login(args.admin_email, args.admin_password)

        if user["role"] != "ADMIN":
            raise SystemExit("관리자 계정으로 실행해야 합니다.")

        print(f"로그인: {user['email']} ({user['role']})\n")

        # 권한 분리 확인용 상담사 id 조회
        counselor_id = None
        for candidate in api.call("GET", "/api/v1/auth/users", 200):
            if candidate["email"] == args.counselor_email:
                counselor_id = candidate["id"]
                break

        for index, (target, description) in enumerate(TARGET_STATES):
            spec = DEMO_CASES[index % len(DEMO_CASES)]

            payload = dict(spec)

            # 마지막 사례는 다른 상담사에게 배정해 권한 격리를 확인할 수 있게 한다.
            if index == len(TARGET_STATES) - 1 and counselor_id:
                payload["counselor_id"] = counselor_id

            case = api.call("POST", "/api/v1/cases", 201, json=payload)

            session = api.call(
                "POST", f"/api/v1/cases/{case['id']}/sessions", 201,
                json={"title": f"{index + 1}회기 상담"},
            )

            status = advance_session(api, session["id"], target)

            owner = "상담사B" if payload.get("counselor_id") else "관리자"
            created.append((case["case_number"], status, f"{description} / 담당: {owner}"))

            print(f"  {case['case_number']}  {status:<20} {description}")

        print()
        print(f"생성 완료: 사례 {len(created)}건")

        total = api.call("GET", "/api/v1/cases?page_size=100", 200)["meta"]["total"]
        print(f"관리자 기준 전체 사례: {total}건")

        return 0
    finally:
        api.close()


if __name__ == "__main__":
    sys.exit(main())
