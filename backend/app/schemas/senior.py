# 고령자 건강상담 요청 · 응답(2026-11-13, API_CONTRACT 27절).
#
# 측정값 범위는 '사람이 잴 수 있는 값' 만 거른다(오타 · 단위 실수 막기). 정상 · 위험 기준이 아니다.

import uuid
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import GlucoseTiming, LivingArrangement, LongTermCareGrade
from app.schemas.common import RequestModel

NOTE_MAX = 2000

#: 측정 항목(추이 · 확인사항이 쓰는 이름). 혈당은 잰 때(공복 · 식후 · 그 밖)마다 따로 본다.
MetricName = Literal[
    "systolic",
    "diastolic",
    "pulse",
    "blood_glucose_fasting",
    "blood_glucose_post_meal",
    "blood_glucose_random",
    "weight_kg",
    "body_temp_c",
]


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


class _MeasurementValues(RequestModel):
    systolic: Optional[int] = Field(default=None, ge=50, le=300)
    diastolic: Optional[int] = Field(default=None, ge=20, le=200)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)
    blood_glucose: Optional[int] = Field(default=None, ge=10, le=1000)
    glucose_timing: Optional[GlucoseTiming] = None
    weight_kg: Optional[float] = Field(default=None, ge=15, le=300)
    body_temp_c: Optional[float] = Field(default=None, ge=30, le=45)
    note: Optional[str] = Field(default=None, max_length=NOTE_MAX)


VALUE_FIELDS = ("systolic", "diastolic", "pulse", "blood_glucose", "weight_kg", "body_temp_c")


class HealthMeasurementCreateRequest(_MeasurementValues):
    measured_at: datetime
    session_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def _check(self) -> "HealthMeasurementCreateRequest":
        if all(getattr(self, name) is None for name in VALUE_FIELDS):
            raise ValueError("측정값을 하나 이상 적어 주세요.")
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
    #: 값이 하나라도 있는 항목만, MetricName 순서대로.
    metrics: List[MetricTrend] = Field(default_factory=list)


# ---------------------------------------------------------------- 다음 상담 확인사항


class BriefBasis(BaseModel):
    """확인사항의 근거. kind=MEASUREMENT 면 metric · measurement_id, SESSION 이면 session_number."""

    kind: Literal["MEASUREMENT", "SESSION", "PROFILE"]
    metric: Optional[MetricName] = None
    measurement_id: Optional[uuid.UUID] = None
    session_number: Optional[int] = None


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
