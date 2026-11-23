# 사내 공지사항(상담사 앱 · 홈 '사내 공지사항', 11/19 디자인 README · 2026-11-20). 한 행이 공지 하나.
#
# 로그인한 상담사 · 관리자 누구나 읽고, 쓰고 고치고 지우는 것은 관리자만. 기관 공지라 내담자 정보가 들어가지 않으므로
# 본문을 암호화하지 않는다(공지에 아이 이름 등을 적지 않는다 — API_CONTRACT 28절).
# 읽음 표시는 디자인처럼 폰에 둔다(ispot-app-notice).
import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User

NOTICE_TITLE_MAX_LENGTH = 120
NOTICE_BODY_MAX_LENGTH = 4000
NOTICE_TEAM_MAX_LENGTH = 40


class Notice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notices"

    title: Mapped[str] = mapped_column(String(NOTICE_TITLE_MAX_LENGTH), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # 목록의 빨간 '중요' 표시.
    important: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    # 공지를 낸 부서(디자인의 '10/28 · 운영지원팀'). 없으면 쓴 사람 이름을 보인다.
    team: Mapped[Optional[str]] = mapped_column(String(NOTICE_TEAM_MAX_LENGTH), nullable=True)
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    author: Mapped[Optional["User"]] = relationship(foreign_keys=[author_id])

    def __repr__(self) -> str:
        return f"<Notice id={self.id}>"
