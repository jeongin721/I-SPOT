# 다음 상담 체크리스트(추가 확인 · 질문 화면) 응답. API_CONTRACT.md 19절.
#
# result 는 rag 가 돌려준 모양 그대로다(check_items · items · validation · speaker_check_items ·
# manual_screen_references · notice). Backend 는 그 안의 칸을 다시 해석하지 않는다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.core.enums import AnalysisStatus
from app.schemas.common import SessionErrorInfo


class FollowupSuggestionResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    analysis_id: Optional[uuid.UUID]
    transcript_version: Optional[int]
    status: AnalysisStatus
    schema_version: str
    provider: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    error: Optional[SessionErrorInfo] = None
