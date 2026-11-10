from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ai.modeling.abuse.question_rules import judgment_reason

from .config import ANALYZER_MODEL

# 공식 근거 붙이기 — 연결 → 코드 검사 → 검토. Backend 연동(backend API_CONTRACT 19절)이 쓴다.
#
# Backend 는 추가 질문을 #118 초안 하나에서만 만든다(팀장님 10/29 결정 ②). 그 질문과 확인할 사항에
# 이번 회차 공식 근거(checklist_builder.build_knowledge_entries — 매뉴얼 · 체크리스트 · 법령 · 판례)를 붙일 때
# '근거가 없는데 공식 근거로 표시'(#117 교차검증 R7) · '검토 안 한 결과가 그대로 보임'(C2)이 생기지 않게 한다.
#
#   1) 후보: 같은 분석에서 이미 찾은 공식 근거 목록만 쓴다(새 검색 없음). 0개면 LLM 을 부르지 않는다.
#   2) 연결: 질문마다 뒷받침하는 공식 근거 0~2개와 이유 한 줄을 LLM 이 고른다. 0개도 정상 답이다.
#      확인할 사항은 extract_check_items 가 이미 고른 knowledge_refs 를 쓴다.
#   3) 코드 검사: 후보에 있는 번호 · 같은 질문 두 번 없음 · 이유가 비지 않음 · 이유에 판정 · 단정 표현 없음.
#   4) 검토: (문장, 공식 근거) 쌍마다 실제로 뒷받침하는지 LLM 에 예 · 아니오를 묻고 '예' 인 쌍만 남긴다.
#   5) 검토가 실패하면 공식 근거를 모두 뺀다. 검토하지 않은 공식 근거는 내보내지 않는다.
#
# 여기 들어오는 질문 · 확인할 사항 문장은 비식별된 상태여야 한다(pipeline 이 가린다).

MAX_LINK_REFS = 2


class QuestionLink(BaseModel):
    question_id: int = Field(description="질문 번호(Q3 이면 3)")
    knowledge_refs: list[str] = Field(
        default_factory=list,
        description="이 질문을 뒷받침하는 공식 근거 ID(manual:N · checklist:N · law:N · precedent:N). 없으면 빈 배열, 많아야 2개",
    )
    why: str = Field(default="", description="그 공식 근거가 이 질문을 어떻게 뒷받침하는지 한 줄. 중립적으로")


class QuestionLinks(BaseModel):
    links: list[QuestionLink] = Field(default_factory=list)


class BasisReview(BaseModel):
    pair_id: int = Field(description="쌍 번호(P3 이면 3)")
    supports: bool = Field(description="공식 근거 발췌가 이 문장을 확인하거나 물어야 하는 이유를 실제로 뒷받침하면 true")


class BasisReviews(BaseModel):
    reviews: list[BasisReview] = Field(default_factory=list)


LINK_SYSTEM_PROMPT = """당신은 아동 상담사가 다음 상담에서 쓸 질문 초안에 공식 근거를 이어 주는 보조 도구입니다.

[질문]마다 [공식 근거](업무 매뉴얼 · 면담 지침 · 체크리스트 · 법령 · 판례 발췌) 가운데,
그 질문을 왜 물어야 하는지 또는 어떻게 물어야 하는지를 실제로 뒷받침하는 것을 고르세요.

규칙:
- 질문마다 question_id(Q 번호의 숫자)로 한 번씩 답합니다.
- knowledge_refs 에는 제공된 공식 근거 ID만 씁니다. 많아야 2개입니다.
- 주제만 비슷하고 그 질문을 뒷받침하지 않으면 고르지 않습니다. 맞는 근거가 없으면 빈 배열로 둡니다. 억지로 채우지 않습니다.
- why 에는 그 근거가 질문을 어떻게 뒷받침하는지 한 줄로 씁니다. 발췌에 없는 내용을 지어내지 않습니다.
- 학대 여부나 법 위반 여부를 판단하거나 단정하지 않습니다.
"""

REVIEW_SYSTEM_PROMPT = """당신은 상담 보조 자료의 근거 표시를 검토하는 검토자입니다.

각 쌍(P 번호)은 상담사 화면에 보일 문장(다음 상담 전 확인할 사항 또는 아동에게 할 질문)과,
그 문장의 '공식 근거'로 붙이려는 발췌입니다. 발췌가 그 문장을 확인하거나 물어야 하는 이유를
실제로 뒷받침하면 supports=true, 아니면 false 로 판정하세요.

- 발췌에 그런 내용이 없거나, 주제만 비슷하거나, 다른 상황을 말하면 false 입니다.
- 연결 이유가 있으면 그 이유가 발췌 내용과 맞는지도 봅니다. 맞지 않으면 false 입니다.
- 애매하면 false 입니다.
- 모든 쌍을 pair_id(P 번호의 숫자)로 한 번씩 판정합니다.
"""


def _invoke(schema: type[BaseModel], system_prompt: str, human_prompt: str) -> Any:
    llm = ChatOpenAI(model=ANALYZER_MODEL).with_structured_output(schema)
    return llm.invoke([("system", system_prompt), ("human", human_prompt)])


def _one_line(text: Any) -> str:
    return " ".join(str(text or "").split())


def _knowledge_lines(knowledge: list[dict[str, Any]]) -> str:
    return "\n".join(f"[{entry['ref']}] ({entry['label']}) {entry['text']}" for entry in knowledge)


# ---------------------------------------------------------------------------
# 2) 연결 + 3) 코드 검사
# ---------------------------------------------------------------------------


def link_question_evidence(
    questions: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """질문마다 뒷받침하는 공식 근거 번호를 고른다.

    questions: [{draft_index, text, reason?}] — Backend 가 넘긴 #118 초안(비식별된 문장).
    반환: ([{draft_index, text, knowledge_refs, why}], 코드 검사로 뺀 연결 수). 공식 근거가 0개인 질문은 싣지 않는다.
    """
    valid = {entry["ref"] for entry in knowledge}
    question_lines = "\n".join(
        f"[Q{number}] {_one_line(question['text'])}"
        + (f" (초안 이유: {_one_line(question['reason'])})" if _one_line(question.get("reason")) else "")
        for number, question in enumerate(questions, start=1)
    )

    raw = _invoke(
        QuestionLinks,
        LINK_SYSTEM_PROMPT,
        f"[질문]\n{question_lines}\n\n[공식 근거]\n{_knowledge_lines(knowledge)}",
    )

    links: list[dict[str, Any]] = []
    seen: set[int] = set()
    dropped = 0
    for link in raw.links:
        refs = list(dict.fromkeys(ref.strip() for ref in link.knowledge_refs if ref.strip()))
        # 없는 질문 번호 · 같은 질문에 두 번 답한 것은 그 답째 뺀다(어느 답이 맞는지 모른다).
        if not 1 <= link.question_id <= len(questions) or link.question_id in seen:
            dropped += len(refs)
            continue
        seen.add(link.question_id)

        kept = [ref for ref in refs if ref in valid][:MAX_LINK_REFS]
        dropped += len(refs) - len(kept)
        if not kept:
            continue

        why = _one_line(link.why)
        # 이유는 화면(공식 근거 펼침)에 그대로 보인다. 비었거나 판정 · 단정 표현이 있으면 연결째 뺀다.
        if not why or judgment_reason(why):
            dropped += len(kept)
            continue

        question = questions[link.question_id - 1]
        links.append(
            {
                "draft_index": question["draft_index"],
                "text": question["text"],
                "knowledge_refs": kept,
                "why": why,
            }
        )
    return links, dropped


# ---------------------------------------------------------------------------
# 4) 검토
# ---------------------------------------------------------------------------


def review_official_basis(pairs: list[dict[str, Any]]) -> set[int]:
    """(문장, 공식 근거) 쌍마다 실제로 뒷받침하는지 묻는다. '예' 인 쌍 번호(1부터)만 돌려준다.

    pairs: [{kind('확인할 사항' | '질문'), text, label, excerpt, why?}]
    답이 없거나 같은 쌍에 두 번 답한 쌍은 '아니오' 로 본다. LLM 호출이 실패하면 예외를 그대로 낸다
    (부르는 쪽이 공식 근거를 모두 뺀다).
    """
    lines = []
    for number, pair in enumerate(pairs, start=1):
        line = (
            f"[P{number}] {pair['kind']}: {_one_line(pair['text'])}\n"
            f"  공식 근거({_one_line(pair['label'])}): {_one_line(pair['excerpt'])}"
        )
        if pair.get("why"):
            line += f"\n  연결 이유: {_one_line(pair['why'])}"
        lines.append(line)

    raw = _invoke(BasisReviews, REVIEW_SYSTEM_PROMPT, "\n".join(lines))

    answers: dict[int, list[bool]] = {}
    for review in raw.reviews:
        if 1 <= review.pair_id <= len(pairs):
            answers.setdefault(review.pair_id, []).append(review.supports is True)
    return {pair_id for pair_id, values in answers.items() if values == [True]}


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def attach_official_evidence(
    check_items: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
) -> dict[str, Any]:
    """확인할 사항과 질문에 검토를 통과한 공식 근거만 남긴다.

    check_items: extract_check_items 결과. 각 항목의 knowledge_refs 를 검토를 통과한 것만 남게 고쳐 쓴다.
    questions: [{draft_index, text, reason?}] — Backend 가 넘긴 #118 초안. 비면 질문 연결을 하지 않는다.
    반환:
      question_links — [{draft_index, text, knowledge_refs, why}]. 검토를 통과한 공식 근거가 1개 이상인 질문만.
      validation     — official_unlinked(코드 검사로 뺀 연결 수) · official_review_rejected(검토에서 뺀 쌍 수) ·
                       question_links(공식 근거가 붙은 질문 수), 그리고 건너뛰었거나 실패했으면 그 사유
                       (official_skipped · question_link_error · official_review_error — 예외 종류만, 문장은 싣지 않는다).
    """
    validation: dict[str, Any] = {"official_unlinked": 0, "official_review_rejected": 0, "question_links": 0}

    def drop_all() -> dict[str, Any]:
        for item in check_items:
            item["knowledge_refs"] = []
        return {"question_links": [], "validation": validation}

    if not knowledge:
        validation["official_skipped"] = "공식 근거 후보가 없습니다."
        return drop_all()

    entry_by_ref = {entry["ref"]: entry for entry in knowledge}

    links: list[dict[str, Any]] = []
    if questions:
        try:
            links, unlinked = link_question_evidence(questions, knowledge)
            validation["official_unlinked"] = unlinked
        except Exception as error:  # noqa: BLE001 — 연결이 실패하면 질문에만 공식 근거를 붙이지 않는다
            validation["question_link_error"] = f"질문 공식 근거 연결 실패: {type(error).__name__}"

    # 검토할 쌍: (붙일 곳, 번호). 붙일 곳은 ("check", 확인할 사항 순번) 또는 ("question", 연결 순번).
    targets: list[tuple[tuple[str, int], str]] = []
    pairs: list[dict[str, Any]] = []
    for index, item in enumerate(check_items):
        item["knowledge_refs"] = [ref for ref in item.get("knowledge_refs") or [] if ref in entry_by_ref]
        for ref in item["knowledge_refs"]:
            targets.append((("check", index), ref))
            pairs.append(
                {
                    "kind": "확인할 사항",
                    "text": item["item"],
                    "label": entry_by_ref[ref]["label"],
                    "excerpt": entry_by_ref[ref].get("excerpt") or entry_by_ref[ref].get("text", ""),
                }
            )
    for index, link in enumerate(links):
        for ref in link["knowledge_refs"]:
            targets.append((("question", index), ref))
            pairs.append(
                {
                    "kind": "질문",
                    "text": link["text"],
                    "label": entry_by_ref[ref]["label"],
                    "excerpt": entry_by_ref[ref].get("excerpt") or entry_by_ref[ref].get("text", ""),
                    "why": link["why"],
                }
            )

    if not pairs:
        return {"question_links": [], "validation": validation}

    try:
        approved = review_official_basis(pairs)
    except Exception as error:  # noqa: BLE001 — 검토를 못 하면 공식 근거를 하나도 내보내지 않는다
        validation["official_review_error"] = f"공식 근거 검토 실패: {type(error).__name__}"
        return drop_all()

    kept: dict[tuple[str, int], list[str]] = {}
    for number, (target, ref) in enumerate(targets, start=1):
        if number in approved:
            kept.setdefault(target, []).append(ref)
    validation["official_review_rejected"] = len(pairs) - len(approved)

    for index, item in enumerate(check_items):
        item["knowledge_refs"] = kept.get(("check", index), [])

    question_links = []
    for index, link in enumerate(links):
        refs = kept.get(("question", index), [])
        if refs:
            question_links.append({**link, "knowledge_refs": refs})
    validation["question_links"] = len(question_links)

    return {"question_links": question_links, "validation": validation}
