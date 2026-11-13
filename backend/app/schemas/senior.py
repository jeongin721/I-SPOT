# 고령자 건강상담 요청 · 응답(2026-11-13, API_CONTRACT 27절).
#
# 측정값 범위는 '사람이 잴 수 있는 값' 만 거른다(오타 · 단위 실수 막기). 정상 · 위험 기준이 아니다.

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import (
    GlucoseTiming,
    LivingArrangement,
    LongTermCareGrade,
    NextCheckOrigin,
    NextCheckStatus,
    ReviewStatus,
    SessionStatus,
)
from app.schemas.common import RequestModel

NOTE_MAX = 2000

#: 측정 항목 이름(추이 · 확인사항이 쓴다). 고정 항목은 systolic · diastolic · pulse · blood_glucose_fasting ·
#: blood_glucose_post_meal · blood_glucose_random · weight_kg · body_temp_c, 그 밖 결과는 "{kind}:{name}"(예: COGNITIVE_SCREENING:CIST).
MetricName = str

ExtraKind = Literal["COGNITIVE_SCREENING", "OTHER"]
MAX_EXTRA_RESULTS = 10


# ---------------------------------------------------------------- 기본정보


class SeniorProfileUpdateRequest(RequestModel):
    """보낸 칸만 바꾼다. null 을 보내면 그 칸을 비운다."""

    living_arrangement: Optional[LivingArrangement] = None
    care_grade: Optional[LongTermCareGrade] = None
    health_notes: Optional[str] = Field(default=None, max_length=NOTE_MAX)
    care_notes: Optional[str] = Field(default=None, max_length=NOTE_MAX)


class SeniorProfileResponse(BaseModel):
    case_id: uuid.UUID
    living_arrangement: Optional[LivingArrangement] = None
    care_grade: Optional[LongTermCareGrade] = None
    health_notes: Optional[str] = None
    care_notes: Optional[str] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------- 측정


class ExtraResultIn(RequestModel):
    """그 밖의 결과 하나. 예: {"kind": "COGNITIVE_SCREENING", "name": "CIST", "value": 24, "max_value": 30}."""

    kind: ExtraKind
    name: str = Field(..., min_length=1, max_length=40)
    value: float = Field(..., ge=-100000, le=100000)
    max_value: Optional[float] = Field(default=None, gt=0, le=100000)
    unit: Optional[str] = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _check(self) -> "ExtraResultIn":
        self.name = self.name.strip()
        if not self.name or ":" in self.name:
            raise ValueError("결과 이름을 적어 주세요(':' 는 쓸 수 없습니다).")
        if self.unit is not None:
            self.unit = self.unit.strip() or None
        if self.max_value is not None and self.value > self.max_value:
            raise ValueError("결과 값이 만점보다 큽니다.")
        return self


class ExtraResultOut(BaseModel):
    kind: ExtraKind
    name: str
    value: float
    max_value: Optional[float] = None
    unit: Optional[str] = None


class _MeasurementValues(RequestModel):
    systolic: Optional[int] = Field(default=None, ge=50, le=300)
    diastolic: Optional[int] = Field(default=None, ge=20, le=200)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    blood_glucose: Optional[int] = Field(default=None, ge=10, le=1000)
    glucose_timing: Optional[GlucoseTiming] = None
    weight_kg: Optional[float] = Field(default=None, ge=15, le=300)
    body_temp_c: Optional[float] = Field(default=None, ge=30, le=45)
    extra_results: Optional[List[ExtraResultIn]] = Field(default=None, max_length=MAX_EXTRA_RESULTS)
    note: Optional[str] = Field(default=None, max_length=NOTE_MAX)


VALUE_FIELDS = ("systolic", "diastolic", "pulse", "blood_glucose", "weight_kg", "body_temp_c")


class HealthMeasurementCreateRequest(_MeasurementValues):
    measured_at: datetime
    session_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _check(self) -> "HealthMeasurementCreateRequest":
        if all(getattr(self, name) is None for name in VALUE_FIELDS) and not self.extra_results:
            raise ValueError("측정값을 하나 이상 적어 주세요.")
        keys = [(item.kind, item.name) for item in self.extra_results or []]
        if len(keys) != len(set(keys)):
            raise ValueError("같은 종류 · 이름의 결과가 두 번 있습니다.")
        if (self.systolic is None) != (self.diastolic is None):
            raise ValueError("혈압은 수축기 · 이완기를 함께 적어 주세요.")
        if self.systolic is not None and self.diastolic is not None and self.diastolic >= self.systolic:
            raise ValueError("이완기 혈압은 수축기 혈압보다 낮아야 합니다.")
        if self.blood_glucose is not None and self.glucose_timing is None:
            raise ValueError("혈당은 잰 때(공복 · 식후 · 그 밖)를 함께 골라 주세요.")
        if self.measured_at.tzinfo is None:
            raise ValueError("measured_at 에 시간대를 붙여 주세요(예: 2026-11-13T09:00:00+09:00).")
        return self


class HealthMeasurementUpdateRequest(_MeasurementValues):
    """보낸 칸만 바꾼다. 바꾼 뒤 값으로 만들기와 같은 검사를 한다(서비스)."""

    measured_at: Optional[datetime] = None
    session_id: Optional[uuid.UUID] = None


class HealthMeasurementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    measured_at: datetime
    systolic: Optional[int] = None
    diastolic: Optional[int] = None
    pulse: Optional[int] = None
    blood_glucose: Optional[int] = None
    glucose_timing: Optional[GlucoseTiming] = None
    weight_kg: Optional[float] = None
    body_temp_c: Optional[float] = None
    extra_results: List[ExtraResultOut] = Field(default_factory=list)
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- 추이


class TrendPoint(BaseModel):
    measurement_id: uuid.UUID
    measured_at: datetime
    value: float


class MetricTrend(BaseModel):
    metric: MetricName
    label: str
    unit: str
    #: 그 밖 결과면 그 종류(COGNITIVE_SCREENING · OTHER), 고정 항목이면 null.
    kind: Optional[ExtraKind] = None
    #: 그 밖 결과의 만점(마지막 측정 기준). 없으면 null.
    max_value: Optional[float] = None
    count: int
    latest: Optional[TrendPoint] = None
    previous: Optional[TrendPoint] = None
    #: latest - previous. 둘 중 하나라도 없으면 null.
    change: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    #: 오래된 것부터.
    points: List[TrendPoint] = Field(default_factory=list)


class HealthTrendResponse(BaseModel):
    case_id: uuid.UUID
    measurement_count: int
    first_measured_at: Optional[datetime] = None
    last_measured_at: Optional[datetime] = None
    #: 값이 하나라도 있는 항목만. 고정 항목 순서 뒤에 그 밖 결과(처음 나온 순).
    metrics: List[MetricTrend] = Field(default_factory=list)


# ---------------------------------------------------------------- 다음 상담 확인사항


BasisKind = Literal["MEASUREMENT", "SESSION", "SEGMENT", "PROFILE"]


class BriefBasis(BaseModel):
    """확인사항 · 요약의 근거. MEASUREMENT 면 metric · measurement_id, SESSION 이면 session_number,
    SEGMENT 면 그 회차 녹취의 segment_ids(회차 통합 요약), PROFILE 이면 기본정보."""

    kind: BasisKind
    metric: Optional[MetricName] = None
    measurement_id: Optional[uuid.UUID] = None
    session_number: Optional[int] = None
    segment_ids: Optional[List[str]] = None


class BasisIn(RequestModel):
    kind: BasisKind
    metric: Optional[str] = Field(default=None, max_length=80)
    measurement_id: Optional[uuid.UUID] = None
    session_number: Optional[int] = Field(default=None, ge=1)
    segment_ids: Optional[List[str]] = Field(default=None, max_length=20)


class BriefCheckItem(BaseModel):
    text: str
    basis: List[BriefBasis] = Field(default_factory=list)


class SeniorBriefResponse(BaseModel):
    case_id: uuid.UUID
    #: RULE = 규칙으로 묶음(AI 생성 아님), AI = LLM 초안(담당자 확인 전제).
    source: Literal["RULE", "AI"]
    model: Optional[str] = None
    summary: str
    check_items: List[BriefCheckItem] = Field(default_factory=list)
    generated_at: datetime


# ---------------------------------------------------------------- 다음 상담 확인사항(저장)

NEXT_CHECK_TEXT_MAX = 300


class NextCheckItemIn(RequestModel):
    text: str = Field(..., min_length=1, max_length=NEXT_CHECK_TEXT_MAX)
    #: 초안(AI · RULE)을 그대로 두거나 고쳐서 저장하면 그 출처, 담당자가 새로 쓰면 COUNSELOR.
    origin: NextCheckOrigin = NextCheckOrigin.COUNSELOR
    #: 초안을 고쳐서 저장했는가. COUNSELOR 면 무시한다.
    edited: bool = False
    basis: List[BasisIn] = Field(default_factory=list, max_length=10)


class NextChecksSaveRequest(RequestModel):
    """담당자가 초안을 두기 · 고치기 · 지우기 한 뒤 남긴 것만 보낸다(지운 초안은 보내지 않는다)."""

    source_session_id: Optional[uuid.UUID] = None
    items: List[NextCheckItemIn] = Field(..., min_length=1, max_length=20)


class NextCheckUpdateRequest(RequestModel):
    text: Optional[str] = Field(default=None, min_length=1, max_length=NEXT_CHECK_TEXT_MAX)
    status: Optional[NextCheckStatus] = None
    #: DONE · DROPPED 로 바꿀 때 확인한 방문(회차). 없어도 된다.
    checked_session_id: Optional[uuid.UUID] = None
    result_note: Optional[str] = Field(default=None, max_length=1000)


class NextCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_id: uuid.UUID
    source_session_id: Optional[uuid.UUID] = None
    text: str
    basis: List[BriefBasis] = Field(default_factory=list)
    origin: NextCheckOrigin
    edited: bool
    status: NextCheckStatus
    checked_session_id: Optional[uuid.UUID] = None
    checked_at: Optional[datetime] = None
    result_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------- 상담 이력 조회


class HistorySummary(BaseModel):
    overview: str = ""
    key_points: List[str] = Field(default_factory=list)
    #: DRAFT(검토 전) · APPROVED(담당자 승인).
    status: ReviewStatus


class HistoryEntry(BaseModel):
    """VISIT = 상담 회차 하나(그 회차에 단 측정 · 확인사항 포함), MEASUREMENT = 회차 없이 적은 측정 하나."""

    kind: Literal["VISIT", "MEASUREMENT"]
    #: 정렬 기준 시각(회차는 상담일 · 없으면 만든 때, 측정은 잰 때).
    at: datetime
    session_id: Optional[uuid.UUID] = None
    session_number: Optional[int] = None
    session_title: Optional[str] = None
    session_status: Optional[SessionStatus] = None
    summary: Optional[HistorySummary] = None
    measurements: List[HealthMeasurementResponse] = Field(default_factory=list)
    #: 이 방문에서 만든 확인사항.
    checks_created: List[NextCheckResponse] = Field(default_factory=list)
    #: 이 방문에서 확인한(DONE · DROPPED) 확인사항.
    checks_resolved: List[NextCheckResponse] = Field(default_factory=list)


class SeniorHistoryResponse(BaseModel):
    case_id: uuid.UUID
    #: 최근 것부터.
    entries: List[HistoryEntry] = Field(default_factory=list)
    #: 아직 확인하지 않은(OPEN) 확인사항 — 다음 방문 때 볼 것.
    open_checks: List[NextCheckResponse] = Field(default_factory=list)
