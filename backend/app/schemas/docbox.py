# 문서함 Schema(API_CONTRACT 23절, 2026-11-05).
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.docbox import DOCBOX_FOLDER_NAME_MAX_LENGTH
from app.schemas.common import RequestModel


class DocboxFolderResponse(BaseModel):
    id: uuid.UUID
    name: str
    count: int


class DocboxFileResponse(BaseModel):
    id: uuid.UUID
    folder_id: Optional[uuid.UUID]
    name: str
    content_type: str
    size_bytes: int
    #: 'text' · 'image' · 'other'
    preview_kind: str
    #: 첫 페이지 글(preview_kind 가 text 일 때만).
    preview_text: Optional[str]
    uploaded_by_name: Optional[str]
    created_at: datetime


class DocboxListResponse(BaseModel):
    folders: List[DocboxFolderResponse]
    files: List[DocboxFileResponse]


class DocboxFolderCreateRequest(RequestModel):
    name: str = Field(min_length=1, max_length=DOCBOX_FOLDER_NAME_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("폴더 이름을 입력해 주세요.")
        return value


class DocboxFileMoveRequest(RequestModel):
    #: null 이면 '폴더 없음'.
    folder_id: Optional[uuid.UUID]


class DocboxUploadResponse(BaseModel):
    files: List[DocboxFileResponse]
