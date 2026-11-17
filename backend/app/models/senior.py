# 고령자 건강상담(2026-11-13, API_CONTRACT 27절).
#
# - senior_profiles: 고령자 사례 1건에 1줄. 담당자가 고르거나 적는 기본정보(거주 형태 · 장기요양 등급 · 건강 메모).
#   건강 메모 · 복약 등 자유 글과 측정값은 봉인 칸(sealed_values, 암호화)에 둔다.
#   실명 · 연락처 · 주소는 여기 두지 않는다(아동 사례와 같이 case_personal_infos 에 암호화해 둔다).
# - health_measurements: 측정 1번에 1줄. 혈압 · 맥박 · 혈당 · 체중 · 체온 · 그 밖 결과(치매 조기검사 등) 중 잰 것만(하나는 있어야 한다).
# - care_domain_notes: 회차별 생활 · 정서 영역(식사 · 수면 · 외출 · 사회활동 · 정서) 기록과 이전 대비 변화. 담당자가 확정한 것만 저장한다.
# - next_checks: 다음 상담 확인사항. 담당자가 초안(AI · 규칙)을 두기 · 고치기 · 지우기 한 뒤 저장하고, 다음 방문 때 확인했는지 표시한다.
#
# 진단 · 판정 칸은 두지 않는다. 서버는 값과 그 변화만 내고 '정상 · 위험' 같은 기준을 붙이지 않는다.

import json
import uuid
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    CareDomain,
    CareStatus,
    DomainChange,
    NextCheckKind,
    GlucoseTiming,
    LivingArrangement,
    LongTermCareGrade,
    NextCheckOrigin,
    NextCheckStatus,
)
from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin


# ---------------------------------------------------------------- 봉인 칸(건강 정보 암호화)
#
# 봉인 칸은 파이썬 속성이고 DB 에는 sealed_values 한 칸(암호문)만 있다. 읽을 때 한 번 풀어 두고(암호문이 바뀌면 다시 품),
# 쓸 때마다 전체를 다시 암호화한다. 묶음 값에 사례 ID(와 측정 줄 ID)가 들어가므로 만들 때 id · case_id 를 먼저 정한다(_init_sealed).
# SQL 로 거르거나 정렬할 수 없다 — 서버는 측정값을 파이썬에서 계산한다.

_UNSET = object()


def _plain(row: Any) -> Dict[str, Any]:
    token = row.sealed_values
    cached = row.__dict__.get("_sealed_cache")
    if cached is not None and cached[0] == token:
        return cached[1]
    from app.core import pii_crypto

    values = json.loads(pii_crypto.decrypt_text(token, case_id=row.case_id, field=row._sealed_field())) if token else {}
    row.__dict__["_sealed_cache"] = (token, values)
    return values


def _put(row: Any, name: str, value: Any) -> None:
    from app.core import pii_crypto

    values = dict(_plain(row))
    if value is None:
        values.pop(name, None)
    else:
        values[name] = value
    token = (
        pii_crypto.encrypt_text(json.dumps(values, ensure_ascii=False, sort_keys=True), case_id=row.case_id, field=row._sealed_field())
        if values
        else None
    )
    row.sealed_values = token
    row.__dict__["_sealed_cache"] = (token, values)


def _sealed(name: str, *, decode: Optional[Callable[[Any], Any]] = None, encode: Optional[Callable[[Any], Any]] = None, default: Any = None) -> property:
    def get(row: Any) -> Any:
        value = _plain(row).get(name, _UNSET)
        if value is _UNSET or value is None:
            return default() if callable(default) else default
        return decode(value) if decode else value

    def set_(row: Any, value: Any) -> None:
        if row.case_id is None:
            raise ValueError("봉인 칸은 case_id 를 정한 뒤에 쓴다.")
        if isinstance(value, list) and not value:
            value = None
        _put(row, name, None if value is None else (encode(value) if encode else value))

    return property(get, set_)


def _init_sealed(row: Any, kwargs: Dict[str, Any]) -> None:
    """id · case_id 를 먼저 정하고(묶음 값), 나머지 칸 — 봉인 칸 포함 — 을 넣는다."""

    Base.__init__(row, id=kwargs.pop("id", None) or uuid.uuid4(), case_id=kwargs.pop("case_id", None))
    for key, value in kwargs.items():
        if not hasattr(type(row), key):
            raise TypeError(f"{type(row).__name__} 에 {key} 칸이 없습니다.")
        setattr(row, key, value)


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
    # 돌봄 필요사항 [CareNeed 값](분류라 평문 — 현황 · 통계). 덧붙임 메모는 아래 봉인 칸.
    care_needs: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    # 돌봄 상태(아직 안 정했으면 null). 바꿀 때 시각 · 메모.
    care_status: Mapped[Optional[CareStatus]] = mapped_column(
        SAEnum(CareStatus, name="care_status", native_enum=False, length=25), nullable=True, index=True
    )
    care_status_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 봉인 칸(2026-11-16 민규 리뷰 '건강 메모 · 측정값 평문'): 아래 SEALED 칸을 JSON 으로 묶어 AES-256-GCM 으로 암호화한 값.
    # 묶음 값은 사례 ID + "senior_profile" 이라 다른 사례로 옮겨 붙이면 풀리지 않는다. 칸이 다 비면 null.
    sealed_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    #: 봉인 칸 — 질환 · 복용약(health_notes) · 생활 · 돌봄 메모 · 복약 여부 · 복약 메모 · 돌봄 필요 메모 · 돌봄 상태 메모.
    SEALED = ("health_notes", "care_notes", "takes_medication", "medication_notes", "care_needs_note", "care_status_note")

    def __init__(self, **kwargs: Any) -> None:
        _init_sealed(self, kwargs)

    def _sealed_field(self) -> str:
        return "senior_profile"

    health_notes = _sealed("health_notes")
    care_notes = _sealed("care_notes")
    takes_medication = _sealed("takes_medication")
    medication_notes = _sealed("medication_notes")
    care_needs_note = _sealed("care_needs_note")
    care_status_note = _sealed("care_status_note")


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

    # 봉인 칸(민규 리뷰): 측정값 전부(혈압 · 맥박 · 혈당 · 혈당 시점 · 체중 · 체온 · 그 밖 결과(치매 조기검사 등) · 메모)를
    # JSON 으로 묶어 암호화한 값. 묶음 값은 사례 ID + "health_measurement:<이 줄 ID>". 잰 시각 · 회차는 정렬 · 묶음에 써서 평문.
    sealed_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    SEALED = ("systolic", "diastolic", "pulse", "blood_glucose", "glucose_timing", "weight_kg", "body_temp_c", "extra_results", "note")

    def __init__(self, **kwargs: Any) -> None:
        _init_sealed(self, kwargs)

    def _sealed_field(self) -> str:
        return f"health_measurement:{self.id}"

    systolic = _sealed("systolic")  # 수축기 혈압 mmHg
    diastolic = _sealed("diastolic")  # 이완기 혈압 mmHg
    pulse = _sealed("pulse")  # 맥박 회/분
    blood_glucose = _sealed("blood_glucose")  # 혈당 mg/dL
    glucose_timing = _sealed("glucose_timing", decode=GlucoseTiming, encode=lambda v: GlucoseTiming(v).value)
    weight_kg = _sealed("weight_kg")
    body_temp_c = _sealed("body_temp_c")
    # 그 밖의 결과(치매 조기검사 점수 등, 개선안 '측정 종류로 구분'). [{kind, name, value, max_value?, unit?}]. 판정 칸은 없다.
    extra_results = _sealed("extra_results", default=list)
    # 잰 상황 메모(예: 아침 식전, 약 먹기 전). 자유 글.
    note = _sealed("note")

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
    kind: Mapped[NextCheckKind] = mapped_column(
        SAEnum(NextCheckKind, name="next_check_kind", native_enum=False, length=10),
        default=NextCheckKind.CHECK,
        server_default=NextCheckKind.CHECK.value,
        nullable=False,
    )
    # 봉인 칸(민규 72fc991 리뷰 '확인사항 글 평문'): text(확인 · 조치 글, 꼭 있음) · result_note(확인 결과 메모)를 JSON 으로 묶어
    # 암호화한 값. 묶음 값은 사례 ID + "next_check:<이 줄 ID>". 글로 SQL 을 거르거나 정렬하지 않는다.
    sealed_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 언제까지(조치 기한, 또는 이어 붙인 재방문 일정 날짜). 지나도 OPEN 이면 '기한 지남'.
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    # 이어 붙인 재방문 · 전화 · 재상담 일정(일정을 지우면 null).
    schedule_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("schedule_events.id", ondelete="SET NULL"), nullable=True, index=True
    )
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
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    SEALED = ("text", "result_note")

    def __init__(self, **kwargs: Any) -> None:
        _init_sealed(self, kwargs)

    def _sealed_field(self) -> str:
        return f"next_check:{self.id}"

    text = _sealed("text")
    result_note = _sealed("result_note")


class CareDomainNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """회차 하나의 영역 하나. AI · 규칙 초안(분석 결과 senior.domain_drafts)을 담당자가 검토 · 확정한 것."""

    __tablename__ = "care_domain_notes"
    __table_args__ = (UniqueConstraint("session_id", "domain", name="uq_care_domain_note_session_domain"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[CareDomain] = mapped_column(
        SAEnum(CareDomain, name="care_domain", native_enum=False, length=10), nullable=False
    )
    # 봉인 칸(민규 72fc991 리뷰 '영역 기록 글 평문'): text(이번 상태 — 어르신 말씀 · 담당자 관찰, NOT_MENTIONED 면 없음) ·
    # change_note(무엇이 어떻게 달라졌는지)를 JSON 으로 묶어 암호화한 값. 묶음 값은 사례 ID + "care_domain_note:<이 줄 ID>".
    sealed_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change: Mapped[DomainChange] = mapped_column(
        SAEnum(DomainChange, name="domain_change", native_enum=False, length=15), nullable=False
    )
    # 근거 발화(STT segment_id).
    segment_ids: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    origin: Mapped[NextCheckOrigin] = mapped_column(
        SAEnum(NextCheckOrigin, name="next_check_origin", native_enum=False, length=10), nullable=False
    )
    edited: Mapped[bool] = mapped_column(default=False, nullable=False)
    # 견준 이전 회차(저장할 때 서버가 정한다). NEW · 이전 기록 없음이면 null.
    compared_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("consultation_sessions.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    SEALED = ("text", "change_note")

    def __init__(self, **kwargs: Any) -> None:
        _init_sealed(self, kwargs)

    def _sealed_field(self) -> str:
        return f"care_domain_note:{self.id}"

    text = _sealed("text")
    # 무엇이 어떻게 달라졌는지(예: '지난번 매일 산책 → 이번엔 거의 안 나가심'). 평가 낱말 없이.
    change_note = _sealed("change_note")
