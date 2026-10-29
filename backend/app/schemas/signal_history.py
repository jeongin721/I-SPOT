# 사례 단위 신호 이력 Schema — GET /cases/{case_id}/signal-history (API_CONTRACT 4절, 2026-10-28).
#
# 회차마다 analysis · risk-assessments 를 따로 부르던 것을 서버가 한 번에 모아 준다(이경진 님 제안,
# I-SPOT_DOCS/docs/PROPOSAL_signal_history_api.md). AI 를 새로 돌리지 않고 저장된 값만 읽는다.
# ai_level 은 'AI 제안' 이지 판정이 아니다(05_RULES §1).
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.core.enums import AbuseType, AnalysisStatus, RiskLevel, SessionStatus


class SignalHistoryType(BaseModel):
    """한 회차 · 한 유형의 AI 신호 · 심각도 제안 · 상담원 판단."""

    abuse_type: AbuseType
    # abuse_signals[].detected. 같은 유형 첫 항목. 참/거짓이 아니거나 항목이 없으면 null(근거 없어 서버가 뺀 유형 포함).
    detected: Optional[bool]
    # severity_ratings[].level 1~5. 11.2절 ai_level 과 같은 규칙(risk_assessment_service.ai_levels_by_type). 정보 부족 · 없음 → null.
    ai_level: Optional[int]
    # 유형별 상담원 판단(11.2절). 판단 전이면 둘 다 null. 회차 전체 판단(11.1절)은 회차 줄의 같은 이름 칸에 있다.
    counselor_level: Optional[RiskLevel]
    assessed_at: Optional[datetime]


class SignalHistorySession(BaseModel):
    """회차 한 줄. 분석이 끝나지 않았고 유형별 상담원 판단도 없으면 types 는 빈 목록이다."""

    session_id: uuid.UUID
    session_number: int
    consulted_at: Optional[datetime]
    status: SessionStatus
    # 그 회차의 가장 최근 분석 상태. 분석을 요청한 적이 없으면 null.
    analysis_status: Optional[AnalysisStatus]
    # 회차 전체 상담원 판단(11.1절, 2026-10-29). 판단 전이면 둘 다 null. types 를 비우는 규칙과는 무관하다.
    counselor_level: Optional[RiskLevel]
    assessed_at: Optional[datetime]
    types: List[SignalHistoryType]


class SignalHistoryResponse(BaseModel):
    case_id: uuid.UUID
    # session_number 오름차순. 분석 전 회차도 모두 들어 있다(추이 그래프의 빈 자리).
    sessions: List[SignalHistorySession]
