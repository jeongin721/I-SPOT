# 고령자 건강상담(2026-11-13, API_CONTRACT 27절).
#
# - senior_profiles: 고령자 사례 1건에 1줄. 담당자가 고르거나 적는 기본정보(거주 형태 · 장기요양 등급 · 건강 메모).
#   실명 · 연락처 · 주소는 여기 두지 않는다(아동 사례와 같이 case_personal_infos 에 암호화해 둔다).
# - health_measurements: 측정 1번에 1줄. 혈압 · 맥박 · 혈당 · 체중 · 체온 · 그 밖 결과(치매 조기검사 등) 중 잰 것만(하나는 있어야 한다).
# - next_checks: 다음 상담 확인사항. 담당자가 초안(AI · 규칙)을 두기 · 고치기 · 지우기 한 뒤 저장하고, 다음 방문 때 확인했는지 표시한다.
#
# 진단 · 판정 칸은 두지 않는다. 서버는 값과 그 변화만 내고 '정상 · 위험' 같은 기준을 붙이지 않는다.

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    GlucoseTiming,
    LivingArrangement,
    LongTermCareGrade,
    NextCheckOrigin,
    NextCheckStatus,
)
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


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
    # 그 밖의 결과(치매 조기검사 점수 등, 개선안 '측정 종류로 구분'). [{kind, name, value, max_value?, unit?}].
    # 어떤 검사를 넣을지는 현장 서식을 보고 정하므로 칸을 따로 만들지 않는다. 판정 칸은 없다.
    extra_results: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    # 잰 상황 메모(예: 아침 식전, 약 먹기 전). 자유 글.
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class NextCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "next_checks"

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 이 확인사항을 만든 방문(회차). 회차 없이(사례 브리핑에서) 저장할 수도 있다.
    source_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # 근거 [{kind: MEASUREMENT|SESSION|SEGMENT|PROFILE, ...}] — 초안이 붙인 그대로. 담당자가 직접 쓴 것은 빈 목록.
    basis: Mapped[List[Dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    origin: Mapped[NextCheckOrigin] = mapped_column(
        SAEnum(NextCheckOrigin, name="next_check_origin", native_enum=False, length=10), nullable=False
    )
    # AI · 규칙 초안을 담당자가 고쳐서 저장했는가(개선안 지표 'AI 초안 수정량').
    edited: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[NextCheckStatus] = mapped_column(
        SAEnum(NextCheckStatus, name="next_check_status", native_enum=False, length=10),
        default=NextCheckStatus.OPEN,
        nullable=False,
        index=True,
    )
    # 다음 방문 때 확인한 회차 · 시각 · 메모(DONE · DROPPED 일 때).
    checked_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="SET NULL"), nullable=True
    )
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
