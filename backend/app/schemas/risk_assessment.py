# 상담원 위험도 판단 Schema.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AbuseType, RiskLevel
from app.models.risk_assessment import RISK_REASON_MAX_LENGTH
from app.schemas.common import RequestModel


class RiskAssessmentSaveRequest(RequestModel):
    """
    한 유형의 상담원 판단. 유형은 주소에서 받는다.

    ai_level 은 서버가 그 회차 AI 분석 결과에서 읽어 채우므로 받지 않는다(보내도 무시).
    이유의 저장할 수 없는 문자(NUL · 짝 없는 서로게이트)는 RequestModel 이 422 로 거절한다.
    """

    counselor_level: RiskLevel
    reason: Optional[str] = Field(default=None, max_length=RISK_REASON_MAX_LENGTH)

    @field_validator("reason")
    @classmethod
    def _blank_reason_to_none(cls, value: Optional[str]) -> Optional[str]:
        # 공백만 있으면 이유를 적지 않은 것으로 본다.
        if value is None or not value.strip():
            return None

        return value


class RiskAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    abuse_type: AbuseType
    counselor_level: RiskLevel
    reason: Optional[str]
    ai_level: Optional[int]
    assessed_by_id: Optional[uuid.UUID]
    assessed_at: datetime
    created_at: datetime
    updated_at: datetime
