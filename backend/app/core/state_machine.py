# Session 상태 전이 규칙.
#
# docs/02_ARCHITECTURE.md §4 의 공통 상태 흐름을 Backend 에서 강제한다.
# Frontend 가 순서를 건너뛰어 호출해도 DB 가 잘못된 상태로 남지 않게 한다.

from typing import Dict, Set

from app.core.enums import SessionStatus
from app.core.errors import invalid_session_state

# 정상 흐름 + 재시도/재업로드 흐름
_ALLOWED_TRANSITIONS: Dict[SessionStatus, Set[SessionStatus]] = {
    SessionStatus.CREATED: {
        SessionStatus.AUDIO_UPLOADED,
    },
    SessionStatus.AUDIO_UPLOADED: {
        SessionStatus.AUDIO_UPLOADED,  # 재업로드
        SessionStatus.STT_PROCESSING,
    },
    SessionStatus.STT_PROCESSING: {
        SessionStatus.STT_REVIEW_REQUIRED,
        SessionStatus.STT_FAILED,
    },
    SessionStatus.STT_FAILED: {
        SessionStatus.AUDIO_UPLOADED,  # 재업로드
        SessionStatus.STT_PROCESSING,  # 재시도
    },
    SessionStatus.STT_REVIEW_REQUIRED: {
        SessionStatus.STT_REVIEW_REQUIRED,  # 상담사 수정(새 version)
        SessionStatus.STT_CONFIRMED,
        SessionStatus.AUDIO_UPLOADED,  # 재업로드 후 재전사
        SessionStatus.STT_PROCESSING,
    },
    SessionStatus.STT_CONFIRMED: {
        SessionStatus.AI_PROCESSING,
        SessionStatus.STT_REVIEW_REQUIRED,  # 확정 후 재수정
    },
    SessionStatus.AI_PROCESSING: {
        SessionStatus.AI_REVIEW_REQUIRED,
        SessionStatus.AI_FAILED,
    },
    SessionStatus.AI_FAILED: {
        SessionStatus.AI_PROCESSING,  # 재시도
        SessionStatus.STT_CONFIRMED,
    },
    SessionStatus.AI_REVIEW_REQUIRED: {
        SessionStatus.AI_REVIEW_REQUIRED,  # 상담사 수정
        SessionStatus.AI_PROCESSING,  # 재분석
        SessionStatus.APPROVED,
    },
    SessionStatus.APPROVED: set(),
}

# 오류 문구에 쓰는 회기 상태 이름. 상태 코드는 문구에 넣지 않고 오류 details 에만 둔다.
# 화면(ispotvscode/src/api/adapters.ts 의 STATUS_MAP)의 상태 이름을 따르되, STT 는 업무 이름
# (ispotvscode/src/api/types.ts 의 TASK_LABELS)처럼 "원문 변환"으로 쓰고,
# 실패 상태는 화면 이름 뒤의 "— 재시도 필요"를 붙이지 않는다.
_STATUS_LABELS: Dict[SessionStatus, str] = {
    SessionStatus.CREATED: "음성 업로드 대기",
    SessionStatus.AUDIO_UPLOADED: "원문 변환 대기",
    SessionStatus.STT_PROCESSING: "원문 변환 중",
    SessionStatus.STT_REVIEW_REQUIRED: "원문 검수 필요",
    SessionStatus.STT_CONFIRMED: "AI 분석 대기",
    SessionStatus.AI_PROCESSING: "AI 분석 중",
    SessionStatus.AI_REVIEW_REQUIRED: "AI 결과 검수 필요",
    SessionStatus.APPROVED: "승인 완료",
    SessionStatus.STT_FAILED: "원문 변환 실패",
    SessionStatus.AI_FAILED: "AI 분석 실패",
}


def status_label(status: SessionStatus) -> str:
    """오류 문구에 쓸 회기 상태 이름. 이름표에 없는 상태도 코드를 드러내지 않는다."""

    return _STATUS_LABELS.get(status, "알 수 없는 상태")


def _blocked_message(current: SessionStatus, hint: str) -> str:
    if current == SessionStatus.APPROVED:
        return "승인이 끝난 회기는 바꿀 수 없습니다."

    return f"지금 회기 상태({status_label(current)})에서는 할 수 없는 요청입니다. {hint}"


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition(current, target):
        allowed = _ALLOWED_TRANSITIONS.get(current, set())
        # details.expected_status 는 지금 상태에서 넘어갈 수 있는 상태 코드다.
        # 요청에 "필요한" 상태가 아니므로 문구에는 넣지 않는다.
        expected = ", ".join(sorted(status.value for status in allowed)) or "없음"
        message = _blocked_message(current, "새로고침해 현재 상태를 확인해 주세요.")

        raise invalid_session_state(current.value, expected, message)


def assert_status_in(current: SessionStatus, allowed: Set[SessionStatus]) -> None:
    """특정 작업을 수행하기 위한 사전 상태 조건을 검사한다."""

    if current not in allowed:
        expected = ", ".join(sorted(status.value for status in allowed))
        # 상태 이름은 흐름 순서(SessionStatus 정의 순서)로 적는다.
        names = " · ".join(status_label(status) for status in SessionStatus if status in allowed)
        hint = (
            f"{names} 상태에서만 할 수 있습니다."
            if names
            else "새로고침해 현재 상태를 확인해 주세요."
        )

        raise invalid_session_state(current.value, expected, _blocked_message(current, hint))
