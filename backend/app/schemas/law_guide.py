# 법령 · 매뉴얼 AI 질문 Schema — POST /law-guide/questions (API_CONTRACT 16절, 2026-10-28).
#
# LawGuide 화면의 'AI 에게 묻기'. 질문 하나를 받아 조문 근거를 단 답을 돌려준다(이경진 님 제안서
# I-SPOT_DOCS/docs/PROPOSAL_law_guide_api.md). 답은 참고용이고 판정이 아니다(05_RULES §1).
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import RequestModel

#: 질문 길이 상한(앞뒤 공백을 뺀 뒤). 넘으면 422 VALIDATION_ERROR.
QUESTION_MAX_LENGTH = 500


class LawGuideQuestionRequest(RequestModel):
    """질문 하나. 대화 맥락은 받지 않는다(AI 모듈이 이전 대화를 받지 않아서)."""

    question: str = Field(min_length=1, max_length=QUESTION_MAX_LENGTH)

    @field_validator("question", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        # 앞뒤 공백을 뺀 뒤 길이를 잰다 — 공백만 보낸 질문은 빈 질문이다.
        return value.strip() if isinstance(value, str) else value


class LawSourceResponse(BaseModel):
    """답변이 근거로 쓴 조문. 실제 조문 목록과 대조해 통과한 것만 온다(모듈 _verify_cited_articles)."""

    law_name: str
    article: str
    title: str = ""
    content: str = ""
    # 조문 시행일(법령 자료의 조문시행일자, "20261002" 꼴). 자료에 없으면 null.
    effective_date: Optional[str] = None
    # 국가법령정보센터 조문 주소. 만들 수 없으면 null.
    portal_url: Optional[str] = None


class ManualSourceResponse(BaseModel):
    """답변이 근거로 쓴 매뉴얼 자료(이번 질문에 실제로 첨부한 페이지 중에서만). 내용이 그 페이지에 있다는 보장은 아니다."""

    id: str
    title: str
    # 쪽수 문자열. 모르면 "?".
    page: str = "?"


class LawGuideSourcesResponse(BaseModel):
    laws: List[LawSourceResponse] = Field(default_factory=list)
    # 매뉴얼 사진은 기관 대외비라 기본으로 첨부하지 않는다(manual/config.MANUAL_QA_ATTACH_IMAGES=false) — 그러면 늘 [].
    manual: List[ManualSourceResponse] = Field(default_factory=list)


class LawGuideAnswerResponse(BaseModel):
    # 답변 본문. 비어 있지 않다(빈 답은 502 AI_INVALID_OUTPUT). 끝에 모듈이 붙인 참고용 안내가 있다.
    answer: str
    sources: LawGuideSourcesResponse
    # 답한 모델 이름(mock 이면 "mock").
    model: str
    answered_at: datetime
