from __future__ import annotations

from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import ANALYZER_MODEL


ChecklistStatus = Literal["matched", "needs_confirmation", "excluded"]


class ChecklistJudgement(BaseModel):
    candidate_id: int = Field(description="검색 후보의 candidate_id")
    status: ChecklistStatus = Field(
        description=(
            "matched: 상담 내용에 직접 근거가 있음, "
            "needs_confirmation: 관련 가능성은 있으나 현재 상담만으로 확인 불가, "
            "excluded: 현재 상담과 직접 관련성이 낮음"
        )
    )
    evidence: str | None = Field(
        default=None,
        description=(
            "matched인 경우 상담 원문에서 그대로 인용한 근거 문장. "
            "직접 근거가 없으면 null"
        ),
    )
    reason: str = Field(description="판단 이유를 짧고 중립적으로 설명")


class EvidenceAnalysis(BaseModel):
    judgements: list[ChecklistJudgement]
    additional_questions: list[str] = Field(
        default_factory=list,
        description=(
            "현재 상담에서 확인되지 않은 핵심 정보를 확인하기 위한 "
            "중립적이고 비유도적인 추가 질문. 최대 5개"
        ),
    )


SYSTEM_PROMPT = """당신은 아동 상담 기록을 정리하는 보조 분석기입니다.

목표는 상담 내용과 검색된 공식 체크리스트 항목을 비교하여 상담사가 확인할 정보를 구조화하는 것입니다.
학대 여부를 확정하거나 법적 판단을 내리지 마세요.

판단 규칙:
1. matched
   - 상담 원문에 해당 체크리스트 항목을 직접 뒷받침하는 표현이 명확히 있을 때만 사용합니다.
   - evidence에는 반드시 상담 원문에서 그대로 가져온 문장을 넣습니다.
2. needs_confirmation
   - 검색 항목이 상담 내용과 관련될 수 있지만 현재 원문만으로는 확인할 수 없을 때 사용합니다.
   - evidence는 null로 둡니다.
3. excluded
   - 검색은 되었지만 현재 상담 내용과 직접 관련성이 낮으면 사용합니다.
   - evidence는 null로 둡니다.

추가 질문 규칙:
- needs_confirmation 항목 중 실제 확인 가치가 높은 내용만 질문합니다.
- 질문은 중립적이고 비유도적으로 작성합니다.
- 확인되지 않은 사실을 전제로 질문하지 않습니다.
- 같은 의미의 질문을 반복하지 않습니다.
- 최대 5개만 작성합니다.
- 새로운 체크리스트 항목을 만들지 않습니다.
"""


def _build_candidate_text(candidates: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        lines.append(f"[{index}] {candidate['content']}")
    return "\n".join(lines)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def _is_evidence_from_consultation(evidence: str, consultation_text: str) -> bool:
    evidence_norm = _normalize_text(evidence)
    consultation_norm = _normalize_text(consultation_text)
    return bool(evidence_norm) and evidence_norm in consultation_norm


def analyze_checklist_candidates(
    consultation_text: str,
    candidates: list[dict[str, Any]],
) -> EvidenceAnalysis:
    if not consultation_text.strip():
        raise ValueError("consultation_text가 비어 있습니다.")

    if not candidates:
        return EvidenceAnalysis(judgements=[], additional_questions=[])

    llm = ChatOpenAI(model=ANALYZER_MODEL)
    structured_llm = llm.with_structured_output(EvidenceAnalysis)

    user_prompt = f"""[상담 원문]
{consultation_text}

[검색된 체크리스트 후보]
{_build_candidate_text(candidates)}

각 후보를 candidate_id 기준으로 반드시 한 번씩 판단하세요.
"""

    raw_result = structured_llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
    )

    valid_ids = set(range(1, len(candidates) + 1))
    cleaned: list[ChecklistJudgement] = []
    seen_ids: set[int] = set()

    for judgement in raw_result.judgements:
        if judgement.candidate_id not in valid_ids:
            continue
        if judgement.candidate_id in seen_ids:
            continue

        status = judgement.status
        evidence = (judgement.evidence or "").strip() or None
        reason = judgement.reason.strip()

        # matched 근거는 상담 원문에 실제로 존재하는 문장만 허용한다.
        # LLM이 원문을 바꾸어 쓰거나 근거를 만들어낸 경우 확인 필요로 낮춘다.
        if status == "matched":
            if evidence is None or not _is_evidence_from_consultation(
                evidence,
                consultation_text,
            ):
                status = "needs_confirmation"
                evidence = None
                reason = (
                    "체크리스트와 관련성은 있으나 상담 원문에서 "
                    "직접 인용 가능한 근거를 확인하지 못했습니다."
                )
        else:
            evidence = None

        cleaned.append(
            ChecklistJudgement(
                candidate_id=judgement.candidate_id,
                status=status,
                evidence=evidence,
                reason=reason,
            )
        )
        seen_ids.add(judgement.candidate_id)

    # 모델이 후보를 누락한 경우에는 화면에 확정 정보로 노출되지 않도록 제외 처리한다.
    for candidate_id in sorted(valid_ids - seen_ids):
        cleaned.append(
            ChecklistJudgement(
                candidate_id=candidate_id,
                status="excluded",
                evidence=None,
                reason="자동 분석 결과에서 직접 관련성을 확인하지 못했습니다.",
            )
        )

    cleaned.sort(key=lambda item: item.candidate_id)

    questions: list[str] = []
    for question in raw_result.additional_questions:
        normalized = question.strip()
        if normalized and normalized not in questions:
            questions.append(normalized)
        if len(questions) >= 5:
            break

    return EvidenceAnalysis(
        judgements=cleaned,
        additional_questions=questions,
    )
