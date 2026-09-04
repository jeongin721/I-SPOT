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


def can_transition(current: SessionStatus, target: SessionStatus) -> bool:
    return target in _ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: SessionStatus, target: SessionStatus) -> None:
    if not can_transition(current, target):
        allowed = _ALLOWED_TRANSITIONS.get(current, set())
        expected = ", ".join(sorted(status.value for status in allowed)) or "없음"

        raise invalid_session_state(current.value, expected)


def assert_status_in(current: SessionStatus, allowed: Set[SessionStatus]) -> None:
    """특정 작업을 수행하기 위한 사전 상태 조건을 검사한다."""

    if current not in allowed:
        expected = ", ".join(sorted(status.value for status in allowed))

        raise invalid_session_state(current.value, expected)
