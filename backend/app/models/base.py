# SQLAlchemy Declarative Base 및 공통 Mixin.
#
# PostgreSQL 이 기본이지만 테스트를 SQLite 로도 돌릴 수 있게
# dialect 중립적인 타입(Uuid, JSON+JSONB variant)만 사용한다.

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# MVP 에서 AI 상세 결과는 JSONB 를 사용한다. (docs/02_ARCHITECTURE.md)
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    SQLite 는 시간대 없이 돌려준다. 저장은 UTC 이므로 UTC 로 본다.
    PostgreSQL 은 시간대를 그대로 돌려주므로 값이 바뀌지 않는다.
    """

    if value is None:
        return None

    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
