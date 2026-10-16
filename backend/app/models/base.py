# SQLAlchemy Declarative Base 및 공통 Mixin.
#
# PostgreSQL 이 기본이지만 테스트를 SQLite 로도 돌릴 수 있게
# dialect 중립적인 타입(Uuid, JSON+JSONB variant)만 사용한다.

import uuid
from datetime import datetime, timedelta, timezone
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

    1년 1월 1일에 `+09:00` · 9999년 12월 31일에 `-01:00` 처럼 UTC 로 바꾸면 날짜 범위를
    벗어나는 값은 가장 이른 · 가장 늦은 UTC 시각으로 자른다(그 밖에 남은 기록은 없으므로
    비교 결과가 같다). 자르지 않으면 OverflowError 가 나 500 이 된다.
    """

    converted = as_utc(value)

    if converted is None:
        return None

    try:
        return converted.astimezone(timezone.utc)
    except OverflowError:
        # 시간대가 앞서(+) 있으면 UTC 는 더 이른 시각이라 아래로, 뒤져(-) 있으면 위로 넘친다.
        edge = datetime.min if converted.utcoffset() > timedelta(0) else datetime.max

        return edge.replace(tzinfo=timezone.utc)


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
