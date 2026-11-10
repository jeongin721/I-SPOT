# 상담사 메모(앱 · 메모 '현장에서 바로 적어 두기', 2026-11-10, API_CONTRACT 25절). 한 행이 메모 하나.
#
# 메모는 쓴 상담사만 읽고 고치고 지운다(관리자도 남의 메모는 못 본다 — 민규 #169).
# 본문에 아이 이름 등이 들어가므로 내담자 정보처럼 pii_crypto 로 암호화한 글자(text_enc)만 저장한다. 평문 칸은 없다.
# 관련 사례(case_id)는 골라서. 담당이 바뀌어 지금 볼 수 없는 사례의 메모는 목록 · 읽기에서 빠진다(memo_service).
import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.case import Case

#: 본문 최대 글자 수(평문 기준).
MEMO_TEXT_MAX_LENGTH = 4000


class CounselorMemo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "counselor_memos"
    __table_args__ = (Index("ix_counselor_memos_owner_created", "owner_id", "created_at"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # pii_crypto.encrypt_memo 로 만든 v1.<키 이름>.… 글자.
    text_enc: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped[Optional["Case"]] = relationship(foreign_keys=[case_id])

    def __repr__(self) -> str:
        # 본문 · 암호문은 찍지 않는다.
        return f"<CounselorMemo id={self.id}>"
