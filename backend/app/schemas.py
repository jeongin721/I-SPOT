from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.models import SessionStatus

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    """Success envelope: {"data": ...} (see docs/02_ARCHITECTURE.md §5)."""

    data: T


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    created_at: datetime


class SessionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    title: str
    status: SessionStatus
    created_at: datetime
