# 공통 요청/응답 Schema.

from typing import Any, Dict, Optional

from pydantic import BaseModel


class SessionErrorInfo(BaseModel):
    """
    재시도 가능한 실패 정보.

    Frontend 는 이 값이 존재하면 재시도 버튼을 노출할 수 있다.
    """

    code: str
    message: str


class HealthStatus(BaseModel):
    status: str
    app_name: str
    env: str
    database: str
    stt_provider: str
    ai_provider: str
    detail: Optional[Dict[str, Any]] = None
