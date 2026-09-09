"""
I-SPOT 2차 세부유형 LLM 설명 결과의 Structured Output Schema를 정의한다.
XAI 핵심 근거 표현을 보존하고, LLM은 해당 근거와 탐지 결과에 대한 설명만 생성한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import List

from pydantic import BaseModel, Field


# ============================================================
# 2. 개별 세부유형 설명
# ============================================================

class SubtypeExplanationItem(BaseModel):
    """
    하나의 탐지된 세부유형에 대한 설명 결과다.

    evidence_text:
        XAI 후보 중 해당 세부유형 탐지에 기여한 핵심 표현

    source_text:
        evidence_text가 포함된 원본 상담 발화

    explanation:
        핵심 표현이 해당 세부유형 탐지와 어떻게 연결되는지
        LLM이 상담사용으로 정리한 설명
    """

    subtype: str = Field(
        ...,
        description="2차 모델이 탐지한 세부유형 코드",
    )

    subtype_name: str = Field(
        ...,
        description="세부유형의 한글 표시명",
    )

    evidence_text: List[str] = Field(
        default_factory=list,
        description=(
            "XAI evidence_candidates 중 "
            "해당 세부유형 탐지를 설명하는 핵심 표현 목록"
        ),
    )

    source_text: str = Field(
        default="",
        description=(
            "evidence_text가 실제로 포함된 원본 상담 발화"
        ),
    )

    explanation: str = Field(
        default="",
        description=(
            "선택된 XAI 핵심 표현이 해당 세부유형 관련 신호와 "
            "어떻게 연결되는지 설명한 상담사용 문장"
        ),
    )


# ============================================================
# 3. 전체 LLM 출력
# ============================================================

class SubtypeExplanationOutput(BaseModel):
    """
    탐지된 모든 세부유형에 대한 LLM Structured Output이다.

    LLM은 subtype을 새로 판단하지 않으며,
    XAI 근거 선별 및 설명만 수행한다.
    """

    schema_version: str = Field(
        default="1.0",
        description="출력 Schema 버전",
    )

    explanations: List[SubtypeExplanationItem] = Field(
        default_factory=list,
        description="탐지된 세부유형별 XAI 근거 및 설명",
    )

    warnings: List[str] = Field(
        default_factory=list,
        description=(
            "적절한 XAI 근거를 선택할 수 없는 경우 등 "
            "추가 확인이 필요한 사항"
        ),
    )