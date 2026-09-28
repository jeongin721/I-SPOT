# API 오류 Contract 구현.
# docs/02_ARCHITECTURE.md 의 실패 응답 형식을 모든 오류에 대해 보장한다.
#
#   {"error": {"code": "ERROR_CODE", "message": "message"}}

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Frontend 와 공유하는 오류 코드. 임의로 값을 변경하지 않는다."""

    # 인증 / 권한
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    UNAUTHORIZED = "UNAUTHORIZED"
    INACTIVE_USER = "INACTIVE_USER"
    FORBIDDEN = "FORBIDDEN"

    # 조회
    NOT_FOUND = "NOT_FOUND"
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    AUDIO_NOT_FOUND = "AUDIO_NOT_FOUND"
    TRANSCRIPT_NOT_FOUND = "TRANSCRIPT_NOT_FOUND"
    ANALYSIS_NOT_FOUND = "ANALYSIS_NOT_FOUND"
    SUMMARY_NOT_FOUND = "SUMMARY_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"

    # 입력 검증
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"

    # 상태 전이
    INVALID_SESSION_STATE = "INVALID_SESSION_STATE"
    TRANSCRIPT_NOT_CONFIRMED = "TRANSCRIPT_NOT_CONFIRMED"
    TRANSCRIPT_ALREADY_CONFIRMED = "TRANSCRIPT_ALREADY_CONFIRMED"
    ALREADY_APPROVED = "ALREADY_APPROVED"

    # Audio
    AUDIO_EMPTY_FILE = "AUDIO_EMPTY_FILE"
    AUDIO_TOO_LARGE = "AUDIO_TOO_LARGE"
    AUDIO_UNSUPPORTED_TYPE = "AUDIO_UNSUPPORTED_TYPE"
    AUDIO_INVALID_FILENAME = "AUDIO_INVALID_FILENAME"
    AUDIO_CORRUPTED = "AUDIO_CORRUPTED"
    AUDIO_STORAGE_ERROR = "AUDIO_STORAGE_ERROR"

    # STT
    STT_FAILED = "STT_FAILED"
    STT_TIMEOUT = "STT_TIMEOUT"
    STT_INVALID_OUTPUT = "STT_INVALID_OUTPUT"

    # AI
    AI_FAILED = "AI_FAILED"
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_INVALID_OUTPUT = "AI_INVALID_OUTPUT"
    AI_AUTH_ERROR = "AI_AUTH_ERROR"
    AI_QUOTA_ERROR = "AI_QUOTA_ERROR"

    # 기타
    INTERNAL_ERROR = "INTERNAL_ERROR"


class APIError(Exception):
    """
    Backend 전체에서 사용하는 오류 타입.

    Router/Service 는 HTTPException 대신 이 예외를 사용해
    Response Contract 를 한 곳에서 보장한다.
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details

    def to_payload(self) -> Dict[str, Any]:
        error: Dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }

        if self.details:
            error["details"] = self.details

        return {"error": error}


# =========================================================
# 자주 쓰는 오류 생성 helper
# =========================================================

def unauthorized(message: str = "인증이 필요합니다.") -> APIError:
    return APIError(ErrorCode.UNAUTHORIZED, message, status_code=401)


def forbidden(message: str = "해당 리소스에 접근할 권한이 없습니다.") -> APIError:
    return APIError(ErrorCode.FORBIDDEN, message, status_code=403)


def not_found(code: ErrorCode, message: str) -> APIError:
    return APIError(code, message, status_code=404)


def conflict(code: ErrorCode, message: str) -> APIError:
    return APIError(code, message, status_code=409)


def bad_request(code: ErrorCode, message: str) -> APIError:
    return APIError(code, message, status_code=400)


def invalid_session_state(current: str, expected: str) -> APIError:
    return APIError(
        ErrorCode.INVALID_SESSION_STATE,
        f"현재 상태({current})에서는 처리할 수 없습니다. 필요 상태: {expected}",
        status_code=409,
        details={"current_status": current, "expected_status": expected},
    )
