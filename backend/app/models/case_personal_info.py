# 사례의 개인 식별 정보(서식 4 의 실명 · 생년월일 · 가족 정보). 사례당 한 행.
#
# 값은 모두 app/core/pii_crypto.py 로 암호화한 글자(v1.<키 이름>.…)만 저장한다. 평문 칸은 없다.
# cases 표에 칸을 늘리지 않고 따로 둔 까닭: 일반 사례 응답(CaseResponse.model_validate(case))에 실수로
# 실리지 않게 하고, 권한 · 열람 기록 · 파기를 한곳에서 다루기 위해서다(specs case-personal-info-encryption 1절).
# 묶음 칸(사례관리대상자 · 면접대상자 · 가족관계 · 건강정도)은 JSON 을 통째로 암호화한다(검색에 쓰지 않음).

import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case

# 암호화하는 칸(API 칸 이름). 저장 칸은 f"{이름}_enc", 묶음 값(AAD)에도 이 이름을 쓴다 — 바꾸지 않는다.
ENCRYPTED_FIELDS = (
    "child_name",
    "child_birth_date",
    "target_person",
    "interviewee",
    "family_members",
    "health",
)


class CasePersonalInfo(TimestampMixin, Base):
    __tablename__ = "case_personal_infos"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"),
        primary_key=True,
    )

    child_name_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 이름 정확 검색용 HMAC-SHA256 hex(pii_crypto.name_index). 같은 이름의 사례가 여럿일 수 있어 고유가 아니다.
    child_name_index: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    child_birth_date_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_person_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interviewee_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    family_members_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    health_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    case: Mapped["Case"] = relationship(back_populates="personal_info")

    def __repr__(self) -> str:
        # 암호문도 찍지 않는다(키가 새면 로그가 곧 실명이다).
        return f"<CasePersonalInfo case_id={self.case_id}>"
