from __future__ import annotations

import re
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import ANALYZER_MODEL
from .retriever import search_evidence

# 다음 상담 체크리스트(추가 확인 · 질문 화면)를 만든다.
#
#   1) 확인할 사항 추출: 사례 기록(이번 회차 아동 발화 · 이전 회차 · 아이 앱 응답)에서 정보 공백 · 미이행 계획 ·
#      변화 · 불일치를 뽑는다.
#   2) 질문 생성: 확인할 사항마다 공식 근거(매뉴얼 면담 지침 · 체크리스트 · 법령 · 판례)를 보고 LLM 이 질문을 쓴다.
#   3) 검증: 규칙(근거 ID · 유도 표현 · 판단 용어 · 아동이 말하지 않은 행위자/행위) → LLM 검토.
#      상담사용 질문이 모자라면 탈락 사유를 알려 주고 한 번 더 만든다.
#
# 여기 들어오는 사례 기록 · 체크리스트 근거는 모두 비식별된 상태여야 한다(pipeline 이 가린다).

Priority = Literal["high", "medium"]
Audience = Literal["counselor", "child_app"]
QuestionType = Literal["open", "clarify"]
CheckKind = Literal["info_gap", "plan_followup", "change", "inconsistency", "checklist_gap"]

MAX_CHECK_ITEMS = 6
MAX_COUNSELOR_QUESTIONS = 5
MIN_COUNSELOR_QUESTIONS = 3
MAX_APP_QUESTIONS = 3
MAX_GENERATION_ROUNDS = 2
MAX_COUNSELOR_QUESTION_CHARS = 120
MAX_APP_QUESTION_CHARS = 50

# 업무 매뉴얼 '상담·조사·사정' 구간(metadata.MANUAL_SCREEN_SECTIONS)에서 면담 원칙을 찾는다.
# 사례 내용이 없는 고정 문장이라 비식별할 필요가 없다.
INTERVIEW_GUIDANCE_QUERY = "아동 면담 개방형 질문 비유도 질문 진술 청취 방법 아동 상담 시 유의사항"
INTERVIEW_GUIDANCE_SECTION = "상담·조사·사정"


# ---------------------------------------------------------------------------
# LLM 출력 형식
# ---------------------------------------------------------------------------


class CheckItemDraft(BaseModel):
    item: str = Field(description="다음 상담에서 확인할 내용. '~했는지', '~인지' 형태로 40자 이내")
    kind: CheckKind
    priority: Priority
    reason: str = Field(description="왜 확인이 필요한지 짧고 중립적으로")
    case_refs: list[str] = Field(default_factory=list, description="근거 사례 기록 ID(case:N)")
    knowledge_refs: list[str] = Field(default_factory=list, description="관련 공식 근거 ID(checklist:N 등)")


class CheckItemDrafts(BaseModel):
    items: list[CheckItemDraft] = Field(default_factory=list)


class QuestionDraft(BaseModel):
    check_item_id: str | None = Field(default=None, description="이 질문이 다루는 확인할 사항 ID(check:N)")
    question: str = Field(description="아동에게 할 질문")
    audience: Audience
    question_type: QuestionType
    priority: Priority
    rationale: str = Field(description="왜 이 질문이 필요한지 짧고 중립적으로")
    case_refs: list[str] = Field(default_factory=list, description="근거 사례 기록 ID(case:N)")
    knowledge_refs: list[str] = Field(
        default_factory=list,
        description="공식 근거 ID(manual:N · checklist:N · law:N · precedent:N)",
    )


class QuestionDrafts(BaseModel):
    items: list[QuestionDraft] = Field(default_factory=list)


class QuestionReview(BaseModel):
    question_id: int
    leading: bool = Field(description="답을 암시하거나 아동이 말하지 않은 행위자·행위·장소를 먼저 꺼냄")
    presupposes: bool = Field(description="아동 기록에서 확인되지 않은 사실을 전제함")
    age_inappropriate: bool = Field(description="어려운 말, 긴 문장, 한 번에 여러 가지를 물음")
    judgmental: bool = Field(description="학대·처벌·범죄 같은 판단·법률 표현, 누군가를 탓함")
    reason: str = Field(default="", description="문제가 있으면 짧은 사유")


class QuestionReviews(BaseModel):
    reviews: list[QuestionReview] = Field(default_factory=list)


CHECK_ITEM_SYSTEM_PROMPT = """당신은 아동 상담사가 다음 상담 전에 챙길 '확인할 사항'을 정리하는 보조 분석기입니다.

[사례 기록](이번 회차 아동 발화 · 이전 회차 기록 · 아이 앱 응답)과 [공식 체크리스트 확인 결과]를 보고,
다음 상담에서 확인이 필요한 사항을 3~6개 고르세요.

찾을 것(kind):
- info_gap: 아동이 언급했지만 시기 · 빈도 · 결과(치료 여부 등) · 현재 상태가 확인되지 않은 내용
- plan_followup: 이전 회차의 안전 계획이나 확인 사항(status=open) 중 이행 여부가 확인되지 않은 것
- change: 이전 회차나 아이 앱 응답과 비교해 달라진 점
- inconsistency: 기록끼리 서로 맞지 않는 부분. 어느 쪽이 맞다고 판단하지 않습니다.
- checklist_gap: 체크리스트에서 needs_confirmation 으로 남은 항목 중 이 사례에서 실제로 확인할 가치가 있는 것

규칙:
- item 은 '~했는지', '~인지'처럼 확인할 내용을 40자 이내로 씁니다. 확인되지 않은 사실을 사실처럼 쓰지 않습니다.
- case_refs 에 근거가 된 사례 기록 ID(case:N)를 하나 이상 넣습니다.
- checklist_gap 은 knowledge_refs 에 해당 checklist:N 을 넣습니다.
- 제공된 ID만 씁니다. 기록에 없는 내용을 지어내지 않습니다.
- 이미 확인된 사항(status=confirmed)은 다시 고르지 않습니다.
- 학대 여부나 법 위반 여부를 판단하지 않습니다.
- 확인할 사항이 없으면 빈 배열을 돌려줍니다.
"""

QUESTION_SYSTEM_PROMPT = """당신은 아동 상담사가 다음 상담에서 쓸 질문 초안을 만드는 보조 도구입니다. 상담사가 승인해야 쓰입니다.

[확인할 사항]마다 [사례 기록]과 [공식 근거](업무 매뉴얼 · 체크리스트 · 법령 · 판례)를 근거로 질문을 만드세요.

대상(audience):
- counselor: 상담사가 다음 상담에서 아동에게 직접 묻는 질문. 3~5개.
- child_app: 상담 전에 아이 앱으로 먼저 보낼 질문. 0~3개. 쉬운 말로 40자 이내로 씁니다.
  일상 · 기분 · 몸 상태 · 도움받을 사람처럼 아이 혼자 답해도 부담이 적은 내용만 묻습니다.
  특정 사건이나 행위(때림, 만짐, 욕 등)는 아이 앱으로 묻지 않습니다.

질문 원칙(업무 매뉴얼 · 아동 면담 지침):
- 열린 질문(open)을 먼저 씁니다. 예: "~에 대해 더 이야기해 줄래?", "그다음엔 어떻게 됐어?"
- 확인 질문(clarify)은 아동이 이미 말한 내용을 구체화할 때만 씁니다.
- 아동이 말하지 않은 행위자 · 행위 · 장소를 질문에서 먼저 꺼내지 않습니다.
  아동이 이미 말한 내용은 아동이 쓴 표현 그대로 되물을 수 있습니다.
- 답을 암시하는 질문("~했지?", "~맞지?"), 부정형 질문("~하지 않았어?"), 선택지를 강요하는 질문을 쓰지 않습니다.
- 학대 · 처벌 · 신고 · 범죄 · 가해 같은 판단 · 법률 용어를 질문에 쓰지 않습니다.
- 확인되지 않은 사실을 전제하지 않습니다. 한 질문에는 한 가지만 묻습니다.

근거 쓰는 법:
- case_refs 에 질문의 근거가 된 사례 기록 ID(case:N)를 하나 이상 넣습니다.
- knowledge_refs 에 공식 근거 ID(manual:N · checklist:N · law:N · precedent:N)를 하나 이상 넣습니다.
- 법령은 왜 확인이 중요한지의 배경으로만 씁니다. 법률 해석을 질문이나 rationale 에 단정하지 않습니다.
- 판례는 어떤 사실(반복성, 상처 정도, 시기 등)이 중요하게 다뤄지는지 참고만 합니다. 판례 속 사건 내용을 질문에 옮기지 않습니다.
- 제공된 ID만 씁니다.
"""

REVIEW_SYSTEM_PROMPT = """당신은 아동 면담 질문을 검토하는 검토자입니다. 각 질문을 [아동 기록]과 비교해 판정하세요.

- leading: 답을 암시하거나, 아동 기록에 없는 행위자 · 행위 · 장소를 먼저 꺼내거나, 예/아니오로 특정 답을 유도한다.
- presupposes: 아동 기록에서 확인되지 않은 사실을 사실처럼 전제한다.
- age_inappropriate: 아동이 이해하기 어려운 말, 긴 문장, 한 번에 여러 가지를 묻는다.
- judgmental: 학대 · 처벌 · 범죄 같은 판단 · 법률 표현이 있거나 누군가를 탓한다.

문제가 없으면 모두 false 로 둡니다. 모든 질문을 question_id 로 한 번씩 판정합니다. reason 은 짧게 씁니다.
"""


def _invoke(schema: type[BaseModel], system_prompt: str, human_prompt: str) -> Any:
    llm = ChatOpenAI(model=ANALYZER_MODEL).with_structured_output(schema)
    return llm.invoke([("system", system_prompt), ("human", human_prompt)])


# ---------------------------------------------------------------------------
# 공식 근거 정리
# ---------------------------------------------------------------------------


def _shorten(text: Any, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def load_interview_guidance(top_k: int = 3) -> list[dict[str, Any]]:
    """업무 매뉴얼 '상담·조사·사정' 구간에서 면담 원칙 조각을 찾는다. 색인이 없거나 실패하면 빈 목록."""
    try:
        return search_evidence(
            INTERVIEW_GUIDANCE_QUERY,
            top_k=top_k,
            screen="followup",
            screen_section=INTERVIEW_GUIDANCE_SECTION,
        )
    except Exception:
        return []


def build_knowledge_entries(
    checklist_results: list[dict[str, Any]],
    law_articles: list[dict[str, Any]],
    manual_results: list[dict[str, Any]],
    precedents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """질문 생성에 줄 공식 근거를 ref(manual:N 등) · 화면 표기(label) · 프롬프트용 본문(text)으로 만든다."""
    entries: list[dict[str, Any]] = []

    seen_chunks: set[str] = set()
    index = 0
    for result in manual_results:
        metadata = result.get("metadata", {})
        chunk_id = str(metadata.get("chunk_id", ""))
        if chunk_id and chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)
        index += 1
        page = metadata.get("page")
        section = metadata.get("screen_section") or metadata.get("category") or ""
        label = " · ".join(part for part in (str(metadata.get("source", "매뉴얼")), str(section)) if part)
        entries.append(
            {
                "ref": f"manual:{index}",
                "type": str(metadata.get("source_type") or "manual"),
                "label": f"{label} p.{page}" if page else label,
                "text": _shorten(result.get("content"), 600),
                "excerpt": _shorten(result.get("content"), 600),
                "source": metadata.get("source", ""),
                "page": page,
                "chunk_id": chunk_id,
            }
        )

    for index, item in enumerate(checklist_results, start=1):
        # 번호는 checklist_results 순서 그대로 쓴다(pipeline 결과의 checklist_results[N-1]).
        if item.get("status") not in {"matched", "needs_confirmation"}:
            continue
        page = item.get("page")
        entries.append(
            {
                "ref": f"checklist:{index}",
                "type": "checklist",
                "label": f"{item.get('source') or '체크리스트'} p.{page}" if page else str(item.get("source") or "체크리스트"),
                "text": f"[{item.get('status')}] {_shorten(item.get('item'), 400)}",
                "excerpt": _shorten(item.get("item"), 400),
                "source": item.get("source", ""),
                "page": page,
                "chunk_id": item.get("chunk_id", ""),
            }
        )

    for index, article in enumerate(law_articles, start=1):
        label = " ".join(
            str(part) for part in (article.get("law_name"), article.get("article"), article.get("title")) if part
        )
        entries.append(
            {
                "ref": f"law:{index}",
                "type": "law",
                "label": label,
                "text": _shorten(article.get("content"), 500),
                "excerpt": _shorten(article.get("content"), 500),
                "url": article.get("portal_url", ""),
            }
        )

    for index, precedent in enumerate(precedents, start=1):
        entries.append(
            {
                "ref": f"precedent:{index}",
                "type": "precedent",
                "label": str(precedent.get("citation") or precedent.get("title") or "판례"),
                "text": f"{_shorten(precedent.get('title'), 120)}: {_shorten(precedent.get('summary'), 300)}",
                "excerpt": f"{_shorten(precedent.get('title'), 120)} — {_shorten(precedent.get('summary'), 300)}",
                "url": precedent.get("url", ""),
                "source": precedent.get("source", ""),
                "page": precedent.get("page"),
            }
        )

    return entries


# ---------------------------------------------------------------------------
# 프롬프트 본문
# ---------------------------------------------------------------------------

_SOURCE_GROUPS = (
    ("이번 회차 아동 발화", lambda record: record.get("current")),
    ("이전 회차 기록", lambda record: not record.get("current") and record.get("source") != "app_response"),
    ("아이 앱 응답", lambda record: record.get("source") == "app_response"),
)


def _record_line(record: dict[str, Any]) -> str:
    status = f" status={record['status']}" if record.get("status") else ""
    return f"[{record['ref']}] ({record.get('label', '')}{status}) {record.get('text', '')}"


def _case_text(records: list[dict[str, Any]]) -> str:
    blocks = []
    for title, belongs in _SOURCE_GROUPS:
        lines = [_record_line(record) for record in records if belongs(record)]
        if lines:
            blocks.append(f"<{title}>\n" + "\n".join(lines))
    return "\n\n".join(blocks)


def _knowledge_text(entries: list[dict[str, Any]], types: set[str] | None = None) -> str:
    return "\n".join(
        f"[{entry['ref']}] ({entry['label']}) {entry['text']}"
        for entry in entries
        if types is None or entry["ref"].split(":")[0] in types
    )


def _check_item_text(check_items: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"[{item['id']}] ({item['kind']}, {item['priority']}) {item['item']} "
        f"— 근거 {', '.join(item['case_refs'] + item['knowledge_refs'])}"
        for item in check_items
    )


# ---------------------------------------------------------------------------
# 1) 확인할 사항
# ---------------------------------------------------------------------------


def _filter_refs(refs: list[str], valid: set[str]) -> list[str]:
    return list(dict.fromkeys(ref.strip() for ref in refs if ref.strip() in valid))


def extract_check_items(
    case_records: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    case_refs = {record["ref"] for record in case_records}
    knowledge_refs = {entry["ref"] for entry in knowledge}
    checklist_text = _knowledge_text(knowledge, {"checklist"}) or "(없음)"

    raw = _invoke(
        CheckItemDrafts,
        CHECK_ITEM_SYSTEM_PROMPT,
        f"[사례 기록]\n{_case_text(case_records)}\n\n[공식 체크리스트 확인 결과]\n{checklist_text}",
    )

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in raw.items:
        text = draft.item.strip()
        refs = _filter_refs(draft.case_refs, case_refs)
        if not text or text in seen or not refs:
            continue
        seen.add(text)
        items.append(
            {
                "id": f"check:{len(items) + 1}",
                "item": text,
                "kind": draft.kind,
                "priority": draft.priority,
                "reason": draft.reason.strip(),
                "case_refs": refs,
                "knowledge_refs": _filter_refs(draft.knowledge_refs, knowledge_refs),
            }
        )
        if len(items) >= MAX_CHECK_ITEMS:
            break
    return items


# ---------------------------------------------------------------------------
# 3) 규칙 검증
# ---------------------------------------------------------------------------

# 판단 · 법률 용어. 질문 문장에만 적용한다(rationale 은 상담사만 본다).
JUDGMENT_TERMS = ("학대", "처벌", "신고", "범죄", "가해", "피해자", "폭행", "위반", "고소", "법적", "법률")

# 답을 정해 두고 확인받는 꼬리 · 부정형 질문("~했지?", "~맞지?", "~하지 않았어?")
_LEADING_ENDING = re.compile(
    r"(?:[가-힣]지|죠|맞아|맞나요|잖아요?|않았어요?|않았니|않았나요|않니|아니야|아니지)\s*\?*\s*$"
)

# 행위자 · 행위가 한 질문에 같이 나오면, 둘 다 아동이 이미 쓴 표현일 때만 허용한다.
PERSON_TERMS = (
    "아빠", "엄마", "아버지", "어머니", "부모", "할머니", "할아버지", "선생님", "삼촌", "이모", "고모",
    "오빠", "언니", "누나", "계부", "계모", "새아빠", "새엄마", "아저씨", "아줌마",
)
_MASK_TOKEN = re.compile(r"\[[A-Z]+_\d+\]")
# 활용형이 달라도("때렸어요" ↔ "때렸을 때") 같은 행위로 본다.
ACT_TERMS: dict[str, tuple[str, ...]] = {
    "때림": ("때리", "때렸", "때린", "때려"),
    "맞음": ("맞았", "맞은", "맞아서"),
    "만짐": ("만지", "만졌", "만진"),
    "욕": ("욕을", "욕했", "욕하"),
    "굶김": ("굶",),
    "밂": ("밀쳤", "밀쳐", "밀었"),
    "던짐": ("던졌", "던지", "던져"),
    "꼬집음": ("꼬집",),
    "가둠": ("가뒀", "가두", "가둬"),
}


def _persons_in(text: str) -> set[str]:
    return {term for term in PERSON_TERMS if term in text} | set(_MASK_TOKEN.findall(text))


def _acts_in(text: str) -> set[str]:
    return {act for act, forms in ACT_TERMS.items() if any(form in text for form in forms)}


def rule_check(question: dict[str, Any], cited_text: str) -> str | None:
    """규칙에 걸리면 탈락 사유를, 통과하면 None 을 돌려준다. cited_text: 질문이 근거로 단 사례 기록 원문."""
    text = question["question"]
    audience = question["audience"]

    limit = MAX_APP_QUESTION_CHARS if audience == "child_app" else MAX_COUNSELOR_QUESTION_CHARS
    if len(text) > limit:
        return "질문이 너무 깁니다"
    if any(term in text for term in JUDGMENT_TERMS):
        return "판단 · 법률 용어가 들어 있습니다"
    if _LEADING_ENDING.search(text):
        return "답을 정해 두고 확인받는 질문입니다"

    acts = _acts_in(text)
    if audience == "child_app" and acts:
        return "아이 앱 질문에서 특정 행위를 묻습니다"

    persons = _persons_in(text)
    if acts and persons and not (acts <= _acts_in(cited_text) and persons <= _persons_in(cited_text)):
        return "아동이 말하지 않은 행위자 · 행위를 질문에 넣었습니다"
    return None


# ---------------------------------------------------------------------------
# 2) 질문 생성 + 3) 검증
# ---------------------------------------------------------------------------


def _generate_questions(
    check_items: list[dict[str, Any]],
    case_records: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
    rejected: list[tuple[str, str]],
) -> list[QuestionDraft]:
    parts = []
    if check_items:
        parts.append(f"[확인할 사항]\n{_check_item_text(check_items)}")
    parts.append(f"[사례 기록]\n{_case_text(case_records)}")
    parts.append(f"[공식 근거]\n{_knowledge_text(knowledge)}")
    if rejected:
        parts.append(
            "[다시 만들 때 피할 질문 — 검증에서 탈락]\n"
            + "\n".join(f"- {question} (사유: {reason})" for question, reason in rejected)
        )
    parts.append(
        "상담사용(counselor) 질문 3~5개와 아이 앱(child_app) 질문 0~3개를 만드세요. "
        "check_item_id 에는 위 확인할 사항 ID를 씁니다."
    )
    return _invoke(QuestionDrafts, QUESTION_SYSTEM_PROMPT, "\n\n".join(parts)).items


def _review_questions(
    questions: list[dict[str, Any]],
    cited_texts: list[str],
) -> dict[int, str | None] | None:
    """LLM 검토. {질문 번호: 탈락 사유 또는 None}. 검토 호출 자체가 실패하면 None."""
    lines = []
    for index, (question, cited) in enumerate(zip(questions, cited_texts), start=1):
        lines.append(f"[{index}] ({question['audience']}) {question['question']}\n    [아동 기록] {cited}")
    try:
        raw = _invoke(QuestionReviews, REVIEW_SYSTEM_PROMPT, "\n".join(lines))
    except Exception:
        return None

    verdicts: dict[int, str | None] = {}
    for review in raw.reviews:
        if not 1 <= review.question_id <= len(questions) or review.question_id in verdicts:
            continue
        failed = review.leading or review.presupposes or review.age_inappropriate or review.judgmental
        verdicts[review.question_id] = (review.reason.strip() or "검토 기준 미충족") if failed else None
    # 검토에서 빠진 질문은 통과시키지 않는다.
    for index in range(1, len(questions) + 1):
        verdicts.setdefault(index, "검토 결과 없음")
    return verdicts


def _clean_draft(
    draft: QuestionDraft,
    case_refs: set[str],
    knowledge_refs: set[str],
    check_ids: set[str],
    require_knowledge: bool,
) -> dict[str, Any] | None:
    question = draft.question.strip()
    refs = _filter_refs(draft.case_refs, case_refs)
    knowledge = _filter_refs(draft.knowledge_refs, knowledge_refs)
    if not question or not refs or (require_knowledge and not knowledge):
        return None
    check_id = (draft.check_item_id or "").strip()
    return {
        "question": question,
        "audience": draft.audience,
        "question_type": draft.question_type,
        "priority": draft.priority,
        "rationale": draft.rationale.strip(),
        "check_item_id": check_id if check_id in check_ids else None,
        "case_refs": refs,
        "knowledge_refs": knowledge,
        "basis_refs": refs + knowledge,
    }


def _accepted_counts(accepted: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "counselor": sum(1 for item in accepted if item["audience"] == "counselor"),
        "child_app": sum(1 for item in accepted if item["audience"] == "child_app"),
    }


def generate_validated_questions(
    check_items: list[dict[str, Any]],
    case_records: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    record_by_ref = {record["ref"]: record for record in case_records}
    knowledge_refs = {entry["ref"] for entry in knowledge}
    check_ids = {item["id"] for item in check_items}
    caps = {"counselor": MAX_COUNSELOR_QUESTIONS, "child_app": MAX_APP_QUESTIONS}

    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected: list[tuple[str, str]] = []
    stats = {"generated": 0, "rule_rejected": 0, "review_rejected": 0, "rounds": 0, "reviewed": True}

    for _ in range(MAX_GENERATION_ROUNDS):
        try:
            drafts = _generate_questions(check_items, case_records, knowledge, rejected)
        except Exception:
            # 첫 회차 실패는 호출부가 대체 질문으로 처리한다. 다시 만들기가 실패하면 앞 회차 결과를 그대로 쓴다.
            if not stats["rounds"]:
                raise
            break
        stats["rounds"] += 1
        stats["generated"] += len(drafts)

        candidates: list[dict[str, Any]] = []
        cited_texts: list[str] = []
        for draft in drafts:
            item = _clean_draft(draft, set(record_by_ref), knowledge_refs, check_ids, bool(knowledge_refs))
            if item is None:
                stats["rule_rejected"] += 1
                continue
            if item["question"] in seen:
                continue
            cited = " ".join(record_by_ref[ref].get("text", "") for ref in item["case_refs"])
            reason = rule_check(item, cited)
            if reason:
                stats["rule_rejected"] += 1
                rejected.append((item["question"], reason))
                continue
            seen.add(item["question"])
            candidates.append(item)
            cited_texts.append(cited)

        verdicts = _review_questions(candidates, cited_texts) if candidates else {}
        if verdicts is None:
            stats["reviewed"] = False
        for index, item in enumerate(candidates, start=1):
            reason = verdicts.get(index) if verdicts is not None else None
            if reason:
                stats["review_rejected"] += 1
                rejected.append((item["question"], reason))
                continue
            if _accepted_counts(accepted)[item["audience"]] >= caps[item["audience"]]:
                continue
            item["review_status"] = "passed" if verdicts is not None else "not_reviewed"
            accepted.append(item)

        if _accepted_counts(accepted)["counselor"] >= MIN_COUNSELOR_QUESTIONS:
            break

    # 상담사용 질문을 앞에, 같은 대상 안에서는 high 를 앞에 둔다.
    accepted.sort(key=lambda item: (item["audience"] != "counselor", item["priority"] != "high"))
    return accepted, stats


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def _basis(refs: list[str], record_by_ref: dict[str, dict[str, Any]], entry_by_ref: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """화면 '근거 · 8회차 01:08 · 7회차 안전 계획' 표기와 근거 링크에 쓸 목록.

    - 사례 기록: session_id + segment_id 로 STT 검수의 그 발화(segmentHref), session_id 만 있으면 회차 상세,
      response_id 로 아이 앱 응답을 연다. excerpt 는 그 기록 원문(결과를 돌려줄 때 비식별 토큰을 되돌린다).
    - 공식 근거: 법령 · 판례는 url(국가법령정보센터)로 연다. 매뉴얼 · 체크리스트 원본 PDF 는 올릴 수 없어
      excerpt(LLM 에 준 발췌)와 source · page 를 그 자리에서 보여 준다.
    """
    basis = []
    for ref in refs:
        if ref in record_by_ref:
            record = record_by_ref[ref]
            basis.append(
                {
                    "ref": ref,
                    "type": "case",
                    "source": record.get("source", ""),
                    "label": record.get("label", ""),
                    "session_no": record.get("session_no"),
                    "session_id": record.get("session_id"),
                    "segment_id": record.get("segment_id"),
                    "start_ms": record.get("start_ms"),
                    "response_id": record.get("response_id"),
                    "excerpt": record.get("text", ""),
                }
            )
        elif ref in entry_by_ref:
            entry = entry_by_ref[ref]
            basis.append(
                {
                    key: entry.get(key)
                    for key in ("ref", "type", "label", "source", "page", "chunk_id", "url", "excerpt")
                    if entry.get(key) not in (None, "")
                }
            )
    return basis


def _fallback_questions(
    fallback_questions: list[str],
    knowledge: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """질문 생성 LLM 이 실패했을 때 체크리스트 판정 단계의 추가 질문을 규칙 검증만 거쳐 쓴다."""
    refs = [knowledge[0]["ref"]] if knowledge else []
    items = []
    for question in fallback_questions[:MAX_COUNSELOR_QUESTIONS]:
        item = {
            "question": question.strip(),
            "audience": "counselor",
            "question_type": "open",
            "priority": "medium",
            "rationale": "현재 상담에서 관련 정보를 추가로 확인할 필요가 있습니다.",
            "check_item_id": None,
            "case_refs": [],
            "knowledge_refs": refs,
            "basis_refs": refs,
            "review_status": "fallback",
        }
        if item["question"] and rule_check(item, "") is None:
            items.append(item)
    return items


def build_next_session_checklist(
    case_records: list[dict[str, Any]],
    checklist_results: list[dict[str, Any]],
    law_articles: list[dict[str, Any]],
    *,
    manual_results: list[dict[str, Any]] | None = None,
    precedents: list[dict[str, Any]] | None = None,
    fallback_questions: list[str] | None = None,
) -> dict[str, Any]:
    """다음 상담 전 확인할 사항(check_items)과 추가 질문(items)을 만든다.

    case_records: case_context.build_case_records 결과를 비식별한 것(ref · label · text …).
    반환:
      check_items  — 확인할 사항. 각 항목에 근거(basis)가 붙는다.
      items        — 추가 질문. audience(counselor | child_app), question_type(open | clarify),
                     근거(basis · case_refs · knowledge_refs), review_status(passed | not_reviewed | fallback)
      validation   — 생성 · 탈락 수(질문 문장은 싣지 않는다)
    """
    records = [record for record in case_records if str(record.get("text") or "").strip()]
    if not records:
        return {"check_items": [], "items": [], "validation": {}}

    manual = [*load_interview_guidance(), *(manual_results or [])]
    knowledge = build_knowledge_entries(checklist_results, law_articles, manual, precedents or [])
    record_by_ref = {record["ref"]: record for record in records}
    entry_by_ref = {entry["ref"]: entry for entry in knowledge}

    try:
        check_items = extract_check_items(records, knowledge)
    except Exception:
        check_items = []

    validation: dict[str, Any]
    try:
        questions, validation = generate_validated_questions(check_items, records, knowledge)
    except Exception as error:
        questions = _fallback_questions(fallback_questions or [], knowledge)
        validation = {"error": f"질문 생성 실패: {type(error).__name__}", "fallback": True}

    for item in check_items:
        item["basis"] = _basis(item["case_refs"] + item["knowledge_refs"], record_by_ref, entry_by_ref)
    for item in questions:
        item["basis"] = _basis(item["basis_refs"], record_by_ref, entry_by_ref)

    return {"check_items": check_items, "items": questions, "validation": validation}
