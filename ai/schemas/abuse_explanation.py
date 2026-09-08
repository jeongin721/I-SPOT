"""
> 모델의 탐지 결과를 LLM이 설명할 때 사용하는 Structured Output Schema다.
XAI 원본 근거, 정제된 근거 표현, 상담사용 설명을 구조화하여 검증한다.
"""

# ============================================================
# 1. Import
# ============================================================

from typing import List, Literal

from pydantic import BaseModel, Field


# ============================================================
# 2. 학대유형 정의
# ============================================================

AbuseType = Literal[
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 3. 유형별 LLM 설명 결과
# ============================================================

class AbuseExplanationItem(BaseModel):
    """
    하나의 탐지된 학대유형에 대한 LLM 설명 결과다.
    """

    type: AbuseType

    raw_evidence: List[str] = Field(
        default_factory=list,
        description="Phrase Occlusion XAI가 추출한 원본 근거 표현",
    )

    refined_evidence: List[str] = Field(
        default_factory=list,
        description=(
            "원본 근거에서 불필요한 주변 표현만 제거한 "
            "핵심 근거 표현"
        ),
    )

    explanation: str = Field(
        default="",
        description=(
            "탐지 유형과 근거 표현을 상담사가 이해할 수 있도록 "
            "설명한 문장"
        ),
    )


# ============================================================
# 4. 최종 LLM Structured Output
# ============================================================

class AbuseExplanationOutput(BaseModel):
    """
    LLM이 반환해야 하는 전체 학대 관련 신호 설명 결과다.
    """

    schema_version: Literal["1.0"] = "1.0"

    explanations: List[
        AbuseExplanationItem
    ] = Field(
        default_factory=list
    )

    warnings: List[str] = Field(
        default_factory=list
    )
