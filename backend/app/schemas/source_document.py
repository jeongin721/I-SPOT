# 상담 기록 문서 Schema(API_CONTRACT 20절, 2026-11-02).

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class NoteDraft(BaseModel):
    """상담 일지 칸 초안(문서에서 옮긴 글). 없는 칸은 빈 글."""

    statement: str = ""
    attitude: str = ""
    environment: str = ""
    signals: str = ""
    opinion: str = ""


class DraftCheck(BaseModel):
    text: str


class DraftQuestion(BaseModel):
    text: str
    reason: str = ""


class FollowupDraft(BaseModel):
    checks: List[DraftCheck]
    questions: List[DraftQuestion]
    #: AI(document_note_llm) · NONE(LLM 을 쓰지 않는 서버 — 초안 없음, 상담사가 직접 쓴다)
    source: Literal["AI", "NONE"]
    model: Optional[str] = None
    generated_at: datetime


class SourceDocumentResponse(BaseModel):
    session_id: uuid.UUID
    filename: str
    #: txt · docx · hwpx · pdf
    file_format: str
    char_count: int
    #: 문서에서 뽑은 글(상담사가 쓴 원문).
    text: str
    #: AI(document_note_llm) · HEADINGS(머리줄로 나눔, AI 아님)
    fill_source: Literal["AI", "HEADINGS"]
    fill_model: Optional[str]
    note_draft: NoteDraft
    followup_draft: Optional[FollowupDraft]
    created_at: datetime
