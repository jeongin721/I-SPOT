# 상담원 위험도 판단. 상담원이 상/중/하로 판단한 값을 저장한다.
#  - SessionOverallRiskAssessment: 회차 전체 판단 하나(2026-10-29 추가, 화면이 쓰는 것)
#  - SessionRiskAssessment: 학대 유형마다 하나(기존 그대로. 기록 · signal-history 용)
#
# AI 는 유형별 심각도(1~5)를 제안만 하고 판단은 상담원이 한다(05_RULES.md).
# ai_level 은 판단할 때 화면에 있던 AI 제안을 그대로 남긴 기록이다. 두 척도를
# 대응시키는 규칙과 사례 단위 위험도 계산은 팀 결정 전이라 여기서 하지 않는다.

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AbuseType, RiskLevel
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.session import ConsultationSession

# 판단 이유 최대 길이
RISK_REASON_MAX_LENGTH = 1000


class SessionRiskAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_risk_assessments"
    __table_args__ = (
        # 한 회차의 한 유형에는 판단이 하나다. 다시 판단하면 그 행을 고친다.
        UniqueConstraint("session_id", "abuse_type", name="uq_risk_assessment_session_type"),
        CheckConstraint(
            "ai_level IS NULL OR (ai_level >= 1 AND ai_level <= 5)",
            name="ck_risk_assessment_ai_level",
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    abuse_type: Mapped[AbuseType] = mapped_column(
        SAEnum(AbuseType, name="abuse_type", native_enum=False, length=20),
        nullable=False,
    )
    counselor_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level", native_enum=False, length=10),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(RISK_REASON_MAX_LENGTH), nullable=True
    )

    # 판단 당시 그 회차 AI 분석 결과의 같은 유형 심각도(1~5). 없거나 정보 부족이면 null.
    ai_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    assessed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["ConsultationSession"] = relationship(back_populates="risk_assessments")

    def __repr__(self) -> str:
        return (
            f"<SessionRiskAssessment id={self.id} abuse_type={self.abuse_type.value} "
            f"level={self.counselor_level.value}>"
        )


class SessionOverallRiskAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """회차 전체에 대한 상담원 판단 하나(상/중/하). 유형별 판단(SessionRiskAssessment)과 따로 둔다."""

    __tablename__ = "session_overall_risk_assessments"
    __table_args__ = (
        # 한 회차에 판단이 하나다. 다시 판단하면 그 행을 고친다.
        UniqueConstraint("session_id", name="uq_overall_risk_assessment_session"),
        CheckConstraint(
            "ai_level IS NULL OR (ai_level >= 1 AND ai_level <= 5)",
            name="ck_overall_risk_assessment_ai_level",
        ),
    )

    # 유니크 제약(uq_overall_risk_assessment_session)이 session_id 인덱스를 겸한다. index=True 를 더 두면 같은 열에 인덱스가 둘이 된다.
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    counselor_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level", native_enum=False, length=10),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(RISK_REASON_MAX_LENGTH), nullable=True
    )

    # 판단 당시 그 회차 AI 분석 결과의 유형별 심각도(1~5) 가운데 가장 높은 값.
    # 유효한 값이 하나도 없거나 분석이 없거나 · 처리 중 · 실패면 null.
    ai_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    assessed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["ConsultationSession"] = relationship(
        back_populates="overall_risk_assessment"
    )

    def __repr__(self) -> str:
        return (
            f"<SessionOverallRiskAssessment id={self.id} session_id={self.session_id} "
            f"level={self.counselor_level.value}>"
        )
