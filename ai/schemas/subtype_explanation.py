"""
I-SPOT 2차 세부유형 LLM 설명 결과의 Structured Output Schema를 정의한다.
LLM이 세부유형을 재판단하지 않고 근거 구간과 상담사용 설명만 반환하도록 제한한다.
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
    하나의 탐지된 세부유형에 대한 LLM 설명 결과다.
    """

    subtype: str = Field(
        ...,
        description="2차 모델이 탐지한 세부유형 코드",
    )

    subtype_name: str = Field(
        ...,
        description="세부유형의 한글 표시명",
    )

    evidence_text: str = Field(
        default="",
        description=(
            "original_text에 실제 존재하는 "
            "근거 발화 또는 최소 의미 구간"
        ),
    )

    explanation: str = Field(
        default="",
        description=(
            "해당 표현이 탐지된 세부유형과 "
            "어떻게 연결되는지 설명한 상담사용 문장"
        ),
    )


# ============================================================
# 3. 전체 LLM 출력
# ============================================================

class SubtypeExplanationOutput(BaseModel):
    """
    2차 세부유형에 대한 전체 LLM Structured Output이다.
    """

    schema_version: str = Field(
        default="1.0",
        description="출력 Schema 버전",
    )

    explanations: List[
        SubtypeExplanationItem
    ] = Field(
        default_factory=list,
        description="탐지된 세부유형별 설명 목록",
    )

    warnings: List[str] = Field(
        default_factory=list,
        description=(
            "근거 부족, 원문 확인 필요 등 "
            "추가 확인 사항"
        ),
    )