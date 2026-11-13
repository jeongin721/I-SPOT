# 고령자 건강상담(2026-11-13, API_CONTRACT 27절).
#
# - senior_profiles: 고령자 사례 1건에 1줄. 담당자가 고르거나 적는 기본정보(거주 형태 · 장기요양 등급 · 건강 메모).
#   실명 · 연락처 · 주소는 여기 두지 않는다(아동 사례와 같이 case_personal_infos 에 암호화해 둔다).
# - health_measurements: 측정 1번에 1줄. 혈압 · 맥박 · 혈당 · 체중 · 체온 중 잰 것만 채운다(하나는 있어야 한다).
#
# 진단 · 판정 칸은 두지 않는다. 서버는 값과 그 변화만 내고 '정상 · 위험' 같은 기준을 붙이지 않는다.

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GlucoseTiming, LivingArrangement, LongTermCareGrade
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SeniorProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "senior_profiles"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    living_arrangement: Mapped[Optional[LivingArrangement]] = mapped_column(
        SAEnum(LivingArrangement, name="living_arrangement", native_enum=False, length=20), nullable=True
    )
    care_grade: Mapped[Optional[LongTermCareGrade]] = mapped_column(
        SAEnum(LongTermCareGrade, name="long_term_care_grade", native_enum=False, length=20), nullable=True
    )
    # 본인 · 가족 · 기관 기록으로 담당자가 아는 질환 · 복용약(자유 글). AI 가 채우지 않는다.
    health_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 생활 · 돌봄 메모(자유 글). 화면이 '실명 · 연락처 · 주소 등 개인정보는 적지 마세요' 를 보인다.
    care_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class HealthMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "health_measurements"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 상담 회차에서 잰 값이면 그 회차. 회차 없이(방문 · 전화 측정) 적을 수도 있다. 회차를 지워도 측정은 남긴다.
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 수축기 혈압 mmHg
    diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 이완기 혈압 mmHg
    pulse: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 맥박 회/분
    blood_glucose: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 혈당 mg/dL
    glucose_timing: Mapped[Optional[GlucoseTiming]] = mapped_column(
        SAEnum(GlucoseTiming, name="glucose_timing", native_enum=False, length=10), nullable=True
    )
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    body_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 잰 상황 메모(예: 아침 식전, 약 먹기 전). 자유 글.
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
