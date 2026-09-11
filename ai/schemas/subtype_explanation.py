"""
I-SPOT 2차 세부유형 LLM 설명 결과의 Structured Output Schema를 정의한다.
XAI 근거와 원본 발화를 보존하고 LLM은 근거 선별 및 설명만 생성한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 2. 공통 Strict 설정
# ============================================================

class StrictBaseModel(BaseModel):
    """
    Structured Output에 정의되지 않은 필드가
    임의로 추가되는 것을 방지한다.
    """

    model_config = ConfigDict(
        extra="forbid"
    )


# ============================================================
# 3. 개별 XAI 근거 설명
# ============================================================

class SubtypeEvidenceExplanation(
    StrictBaseModel
):
    """
    하나의 XAI 근거 표현과 해당 원본 발화,
    그리고 LLM 설명을 저장한다.
    """

    evidence_text: str = Field(
        ...,
        min_length=1,
        description=(
            "Phrase Occlusion XAI가 생성한 "
            "evidence_candidates 중 선택된 핵심 표현"
        ),
    )

    source_text: str = Field(
        ...,
        min_length=1,
        description=(
            "선택된 evidence_text가 포함된 "
            "원본 상담 발화. 입력 원문을 그대로 사용한다."
        ),
    )

    explanation: str = Field(
        ...,
        min_length=1,
        description=(
            "선택된 XAI 표현이 이미 탐지된 세부유형과 "
            "어떻게 연결되는지 설명한 상담사용 문장"
        ),
    )


# ============================================================
# 4. 세부유형별 설명
# ============================================================

class SubtypeExplanationItem(
    StrictBaseModel
):
    """
    하나의 탐지된 세부유형에 대한
    XAI 근거 선택 및 LLM 설명 결과다.

    LLM은 subtype과 subtype_name을 변경할 수 없다.
    """

    subtype: str = Field(
        ...,
        min_length=1,
        description=(
            "2차 RoBERTa 모델이 이미 탐지한 "
            "세부유형 코드"
        ),
    )

    subtype_name: str = Field(
        ...,
        min_length=1,
        description=(
            "2차 모델 세부유형의 한글 표시명"
        ),
    )

    evidence: List[
        SubtypeEvidenceExplanation
    ] = Field(
        default_factory=list,
        description=(
            "XAI 후보 중 해당 세부유형을 "
            "설명하는 데 적절하다고 선택된 근거 목록"
        ),
    )


# ============================================================
# 5. 전체 Structured Output
# ============================================================

class SubtypeExplanationOutput(
    StrictBaseModel
):
    """
    탐지된 모든 세부유형에 대한
    LLM Structured Output이다.

    LLM은 분류를 수행하지 않으며
    기존 탐지 결과의 XAI 근거 선별과 설명만 수행한다.
    """

    schema_version: Literal["1.0"] = Field(
        default="1.0",
        description="Structured Output Schema 버전",
    )

    explanations: List[
        SubtypeExplanationItem
    ] = Field(
        default_factory=list,
        description=(
            "2차 모델이 탐지한 세부유형별 "
            "XAI 근거 및 LLM 설명"
        ),
    )

    warnings: List[str] = Field(
        default_factory=list,
        description=(
            "의미 있는 XAI 근거가 부족하거나 "
            "설명을 생성하기 어려운 경우의 경고"
        ),
    )