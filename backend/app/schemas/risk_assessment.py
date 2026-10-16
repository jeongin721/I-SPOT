# 상담원 위험도 판단 Schema.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import AbuseType, RiskLevel
from app.models.risk_assessment import RISK_REASON_MAX_LENGTH


def _has_unstorable_character(value: str) -> bool:
    """
    PostgreSQL 이 저장할 수 없는 글자가 있는가.

    - NUL(U+0000): text 칸에 넣으면 DataError 로 500 이 된다.
    - 짝 없는 서로게이트(U+D800~U+DFFF): UTF-8 로 바꿀 수 없어 500 이 된다.
    둘 다 JSON 이스케이프(\\u0000, \\ud800)로 들어올 수 있다. 저장 단계까지 가면
    오류 로그에 원문이 실릴 수 있어 입력에서 막는다.
    """

    return any(char == "\x00" or "\ud800" <= char <= "\udfff" for char in value)


class RiskAssessmentSaveRequest(BaseModel):
    """
    한 유형의 상담원 판단. 유형은 주소에서 받는다.

    ai_level 은 서버가 그 회차 AI 분석 결과에서 읽어 채우므로 받지 않는다(보내도 무시).
    """

    counselor_level: RiskLevel
    reason: Optional[str] = Field(default=None, max_length=RISK_REASON_MAX_LENGTH)

    @field_validator("reason")
    @classmethod
    def _blank_reason_to_none(cls, value: Optional[str]) -> Optional[str]:
        # 공백만 있으면 이유를 적지 않은 것으로 본다.
        if value is None or not value.strip():
            return None

        if _has_unstorable_character(value):
            # 오류 응답 · 로그에 원문이 나가지 않게 값은 문구에 넣지 않는다.
            raise ValueError("판단 이유에 저장할 수 없는 문자가 있습니다.")

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
