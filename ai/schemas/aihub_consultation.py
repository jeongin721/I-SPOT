# AI-HUB 아동 상담 데이터의 원본 JSON 구조를 검증하기 위한 Pydantic Schema.
# info, 상담 문항, Q/A audio 데이터 등을 파싱한다.

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AIHubAudioItem(BaseModel):
    type: str
    text: str = ""
    wave: Optional[str] = None
    start: str
    end: str


class AIHubQuestionItem(BaseModel):
    항목: Optional[str] = None
    임상가코멘트: Optional[Dict[str, Any]] = None
    점수: Optional[int] = None
    문제요인: Optional[Dict[str, Any]] = None
    audio: List[AIHubAudioItem] = Field(default_factory=list)


class AIHubSection(BaseModel):
    문항: Optional[str] = None
    문항합계: Optional[int] = None
    위기단계: Optional[str] = None
    list: List[AIHubQuestionItem] = Field(default_factory=list)


class AIHubConsultation(BaseModel):
    version: int
    info: Dict[str, Any] = Field(default_factory=dict)
    list: List[AIHubSection] = Field(default_factory=list)