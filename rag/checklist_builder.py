from __future__ import annotations

from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import ANALYZER_MODEL


Priority = Literal["high", "medium"]


class NextSessionItem(BaseModel):
    question: str = Field(description="다음 상담에서 확인할 중립적이고 비유도적인 질문")
    priority: Priority = Field(description="확인 우선순위")
    rationale: str = Field(description="왜 이 질문이 필요한지 짧은 설명")
    basis_refs: list[str] = Field(
        default_factory=list,
        description="제공된 checklist:N 또는 law:N 근거 ID 목록",
    )


class NextSessionChecklist(BaseModel):
    items: list[NextSessionItem] = Field(default_factory=list)


SYSTEM_PROMPT = """당신은 아동 상담사의 다음 상담 준비를 돕는 보조 도구입니다.
상담 원문, 공식 체크리스트 분석 결과, 관련 법령 조문만 근거로 다음 상담에서 확인할 질문을 구성하세요.

중요 규칙:
- 학대 여부나 법 위반 여부를 확정하지 마세요.
- 새로운 법적 기준이나 공식 체크리스트 항목을 만들어내지 마세요.
- 질문은 중립적이고 비유도적으로 작성하세요.
- 현재 상담에서 이미 확인된 사실을 다시 사실처럼 전제하지 마세요.
- needs_confirmation 항목과 정보 공백을 우선 확인하세요.
- 법령은 질문의 배경 근거로만 사용하고, 법률 해석을 단정하지 마세요.
- 각 질문은 반드시 제공된 basis_ref 중 하나 이상을 사용하세요.
- 3~5개 질문만 생성하세요.
"""


def _build_reference_text(
    checklist_results: list[dict[str, Any]],
    law_articles: list[dict[str, Any]],
) -> tuple[str, set[str]]:
    lines: list[str] = []
    valid_refs: set[str] = set()

    for index, item in enumerate(checklist_results, start=1):
        if item.get("status") not in {"matched", "needs_confirmation"}:
            continue
        ref = f"checklist:{index}"
        valid_refs.add(ref)
        lines.append(
            f"[{ref}] status={item.get('status')}\n"
            f"항목: {item.get('item', '')}\n"
            f"근거: {item.get('evidence') or '현재 상담에서 직접 확인되지 않음'}\n"
            f"출처: {item.get('source', '')} p.{item.get('page', '')}"
        )

    for index, article in enumerate(law_articles, start=1):
        ref = f"law:{index}"
        valid_refs.add(ref)
        content = str(article.get("content", ""))[:1800]
        lines.append(
            f"[{ref}] {article.get('law_name', '')} {article.get('article', '')} "
            f"{article.get('title', '')}\n{content}"
        )

    return "\n\n".join(lines), valid_refs


def _fallback_items(
    fallback_questions: list[str],
    valid_refs: set[str],
) -> NextSessionChecklist:
    basis = [next(iter(sorted(valid_refs)))] if valid_refs else []
    items: list[NextSessionItem] = []

    for question in fallback_questions[:5]:
        question = question.strip()
        if not question:
            continue
        items.append(
            NextSessionItem(
                question=question,
                priority="medium",
                rationale="현재 상담에서 관련 정보를 추가로 확인할 필요가 있습니다.",
                basis_refs=basis,
            )
        )

    return NextSessionChecklist(items=items)


def build_next_session_checklist(
    consultation_text: str,
    checklist_results: list[dict[str, Any]],
    law_articles: list[dict[str, Any]],
    *,
    fallback_questions: list[str] | None = None,
) -> dict[str, Any]:
    reference_text, valid_refs = _build_reference_text(
        checklist_results,
        law_articles,
    )
    fallback_questions = fallback_questions or []

    if not valid_refs:
        return {"items": []}

    llm = ChatOpenAI(model=ANALYZER_MODEL)
    structured_llm = llm.with_structured_output(NextSessionChecklist)

    prompt = f"""[상담 원문]
{consultation_text}

[사용 가능한 공식 근거]
{reference_text}

위 정보만 사용하여 다음 상담에서 확인할 질문을 3~5개 작성하세요.
각 질문의 basis_refs에는 위에 제공된 ID만 사용하세요.
"""

    try:
        raw = structured_llm.invoke(
            [
                ("system", SYSTEM_PROMPT),
                ("human", prompt),
            ]
        )
    except Exception:
        return _fallback_items(fallback_questions, valid_refs).model_dump()

    cleaned: list[NextSessionItem] = []
    seen_questions: set[str] = set()

    for item in raw.items:
        question = item.question.strip()
        if not question or question in seen_questions:
            continue

        refs = [ref for ref in item.basis_refs if ref in valid_refs]
        if not refs:
            continue

        cleaned.append(
            NextSessionItem(
                question=question,
                priority=item.priority,
                rationale=item.rationale.strip(),
                basis_refs=list(dict.fromkeys(refs)),
            )
        )
        seen_questions.add(question)
        if len(cleaned) >= 5:
            break

    if len(cleaned) < 3 and fallback_questions:
        fallback = _fallback_items(fallback_questions, valid_refs)
        for item in fallback.items:
            if item.question in seen_questions:
                continue
            cleaned.append(item)
            seen_questions.add(item.question)
            if len(cleaned) >= 5:
                break

    return NextSessionChecklist(items=cleaned).model_dump()
