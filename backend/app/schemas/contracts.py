# 팀 공통 Contract 의 Pydantic 표현.
#
# 이 파일의 필드는 docs/02_ARCHITECTURE.md §6 (STT Contract), §7 (AI Output Contract)
# 와 1:1 로 대응한다. Backend 단독으로 이 구조를 변경하지 않는다.
# 팀 B 의 ai/schemas/analysis.py 와 동일한 형태를 유지한다.

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, StrictInt, field_validator, model_serializer, model_validator

from app.core.enums import Speaker

SCHEMA_VERSION = "1.0"


# =========================================================
# STT Contract
# =========================================================

class STTSegment(BaseModel):
    """STT Contract 의 segment. 필드를 추가하거나 제거하지 않는다."""

    segment_id: str = Field(..., min_length=1, max_length=50)
    speaker: Speaker
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_time_range(self) -> "STTSegment":
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms 는 start_ms 보다 작을 수 없습니다.")

        return self


class STTResult(BaseModel):
    """STT Adapter 가 반환해야 하는 최상위 구조."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    segments: List[STTSegment] = Field(default_factory=list)

    @field_validator("segments")
    @classmethod
    def _check_unique_segment_ids(cls, segments: List[STTSegment]) -> List[STTSegment]:
        seen = {segment.segment_id for segment in segments}

        if len(seen) != len(segments):
            raise ValueError("segment_id 가 중복되었습니다.")

        return segments


# =========================================================
# AI Output Contract
# =========================================================

class SummaryAssessmentField(BaseModel):
    """상담 요약 사정 관점 한 칸. text 는 AI 초안 문장, segment_ids 는 근거 발화 번호(비어 올 수 있다)."""

    text: str = ""
    segment_ids: List[str] = Field(default_factory=list)


class SummaryAssessment(BaseModel):
    """상담 요약 사정 관점 4칸(2026-10-27, 10/27 디자인 NoteWrite).

    safety_changes: (안전관련) 조사 후 변화된 사항
    strengths_resources: 아동안전과 관련된 강점과 자원
    safety_risks: 아동안전과 관련된 위험요인(최상위 risk_factors 와 다른 칸이다)
    desired_changes: 앞으로 원하는 변화 · 원하는 서비스/지원
    없으면 모두 빈 칸이다. 이 필드가 없던 때 저장한 결과도 그대로 읽힌다.
    """

    safety_changes: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    strengths_resources: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    safety_risks: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)
    desired_changes: SummaryAssessmentField = Field(default_factory=SummaryAssessmentField)


class AISummaryBody(BaseModel):
    overview: str = ""
    key_points: List[str] = Field(default_factory=list)
    assessment: SummaryAssessment = Field(default_factory=SummaryAssessment)


# 아래 4개는 2026-10-16 합의로 추가한 선택 필드다(API_CONTRACT.md 8절).
# 모두 AI 제안이고 판단은 상담원이 한다. segment_ids 는 근거 발화 번호이며
# 아직 비어 올 수 있다. 근거 없는 위험 항목 빼기(drop_ungrounded_risk_items)는
# 위험 3필드에만 적용하고 여기에는 적용하지 않는다.

class SeverityRating(BaseModel):
    """학대 유형별 심각도 참고값. level 은 1~5, 정보가 부족하면 null."""

    major_type: str
    # bool 이나 "3" 같은 문자열이 정수로 바뀌어 들어오지 않게 StrictInt 로 받는다.
    level: Optional[StrictInt] = Field(default=None, ge=1, le=5)
    reason: str = ""
    matched_evidence: str = ""
    segment_ids: List[str] = Field(default_factory=list)
    reviewed: bool = False


class ProtectiveFactor(BaseModel):
    """보호 요인 한 줄."""

    category: str
    text: str
    segment_ids: List[str] = Field(default_factory=list)


class SessionChangeNote(BaseModel):
    """이전 회기와 달라진 점 메모. 나중에 근거 번호를 붙여도 모양이 같도록 객체로 받는다."""

    text: str
    segment_ids: List[str] = Field(default_factory=list)


class FollowupCheckPoint(BaseModel):
    """다음 회기에 확인할 점에 대한 AI 메모. 질문 은행의 질문이 아니다.

    previous_session_label(2026-10-28, 선택): 근거가 지난 회차 확정 요약뿐인 메모의 그 회차 이름("7회차").
    이때 segment_ids 는 빈 배열이다. AI 경계(followup_check_llm)가 사례 정보의 직전 승인 회차 이름만 붙이고,
    segment_ids 도 이 값도 없는 메모는 만들지 않는다.
    """

    text: str
    segment_ids: List[str] = Field(default_factory=list)
    previous_session_label: Optional[str] = Field(default=None, max_length=20)

    @model_serializer(mode="wrap")
    def _omit_empty_label(self, handler: Any) -> Dict[str, Any]:
        # 선택 키라 값이 있을 때만 싣는다 — 예전 메모 · 저장 결과의 모양({text, segment_ids})이 바뀌지 않게.
        data = handler(self)
        if data.get("previous_session_label") is None:
            data.pop("previous_session_label", None)
        return data


class AIAnalysisResult(BaseModel):
    """
    AI 담당의 Structured JSON Contract.

    9월에는 위험 관련 필드가 빈 배열일 수 있다.
    Backend 는 내용을 판단하지 않고 그대로 저장/전달한다.
    선택 필드 4개(severity_ratings 등)는 없으면 빈 배열이다. 이 필드가 없던
    때 저장한 결과도 그대로 읽힌다(schema_version 은 "1.0" 그대로).
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    summary: AISummaryBody = Field(default_factory=AISummaryBody)
    risk_utterances: List[Dict[str, Any]] = Field(default_factory=list)
    abuse_signals: List[Dict[str, Any]] = Field(default_factory=list)
    risk_factors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    severity_ratings: List[SeverityRating] = Field(default_factory=list)
    protective_factors: List[ProtectiveFactor] = Field(default_factory=list)
    session_change_notes: List[SessionChangeNote] = Field(default_factory=list)
    followup_check_points: List[FollowupCheckPoint] = Field(default_factory=list)


class SummaryEvidenceItem(BaseModel):
    """
    AI 파이프라인 내부 결과인 근거 연결 정보.

    공통 Contract 에는 포함되지 않으므로 별도 필드로 전달한다.
    팀 B 의 EvidenceLink(text/segment_ids/score) 를 API 용으로 옮긴 구조다.
    """

    key_point: str = ""
    segment_ids: List[str] = Field(default_factory=list)
    score: float = 0.0
