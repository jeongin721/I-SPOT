# 구간별 음성 참고 표시(stt/voice_marks) 조회 응답.
#
# result 는 분석 모듈이 돌려준 dict 를 그대로 담는다(모양은 stt/voice_marks.md · API_CONTRACT.md 16절).
# Backend 는 그 안의 칸을 다시 해석하지 않는다. 기준값(thresholds)과 표시(flag)는 화면이 응답에서 읽는다.

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class VoiceMarksResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audio_file_id: uuid.UUID
    transcript_id: Optional[uuid.UUID]
    transcript_version: Optional[int]
    extractor: Optional[str]
    schema_version: str
    created_at: datetime
    result: Dict[str, Any]
