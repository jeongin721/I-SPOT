# 상담 기록 문서 Schema.

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import ReviewStatus


class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="", max_length=50000)
    doc_type: str = Field(default="CONSULTATION_RECORD", max_length=50)


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    content: Optional[str] = Field(default=None, max_length=50000)

    @model_validator(mode="after")
    def _require_change(self) -> "DocumentUpdateRequest":
        if self.title is None and self.content is None:
            raise ValueError("수정할 필드를 최소 1개 지정해야 합니다.")

        return self


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    doc_type: str
    title: str
    content: str
    status: ReviewStatus
    created_by_id: Optional[uuid.UUID]
    approved_by_id: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
