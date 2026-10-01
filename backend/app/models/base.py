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


def to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """
    받은 시각을 UTC 로 바꾼다. 표시 없는 값은 UTC 로 본다(as_utc).

    DB 와 비교할 값에 쓴다. SQLite 는 비교할 때 시간대를 버리고 벽시계 글자만 보므로
    `+09:00` 이 붙은 값을 그대로 넘기면 9시간 어긋난다. PostgreSQL 은 결과가 바뀌지 않는다.
    """

    converted = as_utc(value)

    return converted.astimezone(timezone.utc) if converted is not None else None


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
