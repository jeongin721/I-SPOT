# I-SPOT Backend 공통 Enum.
# docs/02_ARCHITECTURE.md 의 공통 상태 / STT Contract / AI Output Contract 를 그대로 따른다.

from enum import Enum


class UserRole(str, Enum):
    """사용자 권한. 자유 회원가입은 없으며 관리자가 계정을 생성한다."""

    COUNSELOR = "COUNSELOR"
    ADMIN = "ADMIN"


class CaseStatus(str, Enum):
    """사례 상태. 종결은 상담사/관리자의 명시적 행위로만 발생한다."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class SessionStatus(str, Enum):
    """
    상담 Session 상태.

    docs/02_ARCHITECTURE.md 공통 상태:
        CREATED
        → AUDIO_UPLOADED
        → STT_PROCESSING
        → STT_REVIEW_REQUIRED
        → STT_CONFIRMED
        → AI_PROCESSING
        → AI_REVIEW_REQUIRED
        → APPROVED

    ASSUMPTION:
    공통 문서는 "실패 시 재시도 가능한 상태/오류 정보를 유지한다"만 규정하고
    실패 상태 이름을 정의하지 않았다. MVP에서는 가장 단순하게
    STT_FAILED / AI_FAILED 두 상태를 추가하고, 재시도 시 각각
    AUDIO_UPLOADED / STT_CONFIRMED 로 되돌린다.
    """

    CREATED = "CREATED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    STT_PROCESSING = "STT_PROCESSING"
    STT_REVIEW_REQUIRED = "STT_REVIEW_REQUIRED"
    STT_CONFIRMED = "STT_CONFIRMED"
    AI_PROCESSING = "AI_PROCESSING"
    AI_REVIEW_REQUIRED = "AI_REVIEW_REQUIRED"
    APPROVED = "APPROVED"

    STT_FAILED = "STT_FAILED"
    AI_FAILED = "AI_FAILED"


class Speaker(str, Enum):
    """STT Contract speaker Enum. 확실하지 않으면 UNKNOWN 을 사용한다."""

    COUNSELOR = "COUNSELOR"
    CHILD = "CHILD"
    GUARDIAN = "GUARDIAN"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TranscriptSource(str, Enum):
    """Transcript version 이 생성된 경로."""

    STT = "STT"
    COUNSELOR_EDIT = "COUNSELOR_EDIT"


class AnalysisStatus(str, Enum):
    """AI 분석 실행 상태."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    """
    상담사 검수 대상(Summary/Document) 상태.

    Human-in-the-loop 원칙(docs/05_RULES.md)에 따라
    AI 생성 결과는 항상 DRAFT 로 시작한다.
    """

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class AuditAction(str, Enum):
    """수정/승인 이력 추적용 Audit action."""

    CASE_CREATED = "CASE_CREATED"
    CASE_UPDATED = "CASE_UPDATED"
    CASE_DELETED = "CASE_DELETED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_UPDATED = "SESSION_UPDATED"
    SESSION_DELETED = "SESSION_DELETED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    STT_REQUESTED = "STT_REQUESTED"
    STT_COMPLETED = "STT_COMPLETED"
    STT_FAILED = "STT_FAILED"
    TRANSCRIPT_UPDATED = "TRANSCRIPT_UPDATED"
    TRANSCRIPT_CONFIRMED = "TRANSCRIPT_CONFIRMED"
    ANALYSIS_REQUESTED = "ANALYSIS_REQUESTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    SUMMARY_UPDATED = "SUMMARY_UPDATED"
    SUMMARY_APPROVED = "SUMMARY_APPROVED"
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    DOCUMENT_APPROVED = "DOCUMENT_APPROVED"
