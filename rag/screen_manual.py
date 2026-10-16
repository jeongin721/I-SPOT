from __future__ import annotations

import argparse
import json
import re
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from .config import ANALYZER_MODEL
from .metadata import SCREEN_NAMES, SCREEN_PRIORITY_SECTIONS, strip_section_prefix
from .resource_ranker import format_document_reference
from .retriever import search_evidence
from .vector_store import get_vector_store


# 화면별 최소 코사인 유사도. 이보다 낮으면 '맞는 내용 없음'으로 보고 빈 목록을 돌려준다.
# 2026-10 측정(원문 정리 + 구간 이름 색인, 화면별 맞는 질문 4개 · 무관한 문장 3개의 1위 점수):
#   prebriefing 맞음 0.37~0.47 / 무관 0.15~0.28
#   closure     맞음 0.47~0.57 / 무관 0.19~0.32
# 표본이 작으므로 실제 상담 문장이 쌓이면 다시 맞춘다.
SCREEN_MIN_SIMILARITY: dict[str, float] = {
    "prebriefing": 0.32,
    "closure": 0.35,
}

# 이 화면은 벡터 검색 대신 서식 항목 전체를 LLM 에 보여 주고 맞는 항목만 고르게 한다.
# 서식 항목은 짧고 PDF 추출 글자가 깨져 있어(예아 니 오 …) 임베딩 점수만으로는 맞는 항목을 고르지 못한다.
LLM_ITEM_SCREENS = {"followup"}


def search_screen_manual(
    text: str,
    screen: str,
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """업무 매뉴얼에서 해당 화면 구간(metadata.MANUAL_SCREEN_SECTIONS)만 검색한다.

    screen: followup(추가 확인 · 질문) / prebriefing(상담 전 브리핑) / closure(종결 검토)
    맞는 내용이 없으면 빈 목록을 돌려준다. 구간 밖 내용(전달체계, 입양 등)은 검색되지 않는다.
    """
    if screen not in SCREEN_NAMES:
        raise ValueError(f"알 수 없는 화면입니다: {screen} ({', '.join(SCREEN_NAMES)})")

    query = text.strip()
    if not query:
        raise ValueError("검색할 문장이 비어 있습니다.")

    if screen in LLM_ITEM_SCREENS:
        return _select_form_items(query, screen, top_k)

    # 기준점으로 무관한 후보를 먼저 거르고(남는 게 없으면 LLM 을 부르지 않는다), 남은 후보를 LLM 이 확인한다.
    candidates = search_evidence(
        query,
        top_k=max(top_k * 3, CANDIDATE_POOL),
        screen=screen,
        min_similarity=SCREEN_MIN_SIMILARITY.get(screen),
    )
    if not candidates:
        return []

    references = []
    for item, reason in _verify_candidates(query, screen, candidates, top_k):
        reference = format_document_reference(item)
        reference["summary"] = _strip_page_header(reference["summary"])
        reference["similarity"] = item["similarity"]
        reference["reason"] = reason
        references.append(reference)
    return references


# ---------------------------------------------------------------------------
# 검색 후보 확인 (prebriefing · closure)
# ---------------------------------------------------------------------------

# LLM 에 보일 검색 후보 수. 많을수록 맞는 조각을 놓칠 일이 줄지만 호출이 길어진다.
CANDIDATE_POOL = 9

SCREEN_PURPOSES = {
    "prebriefing": "상담 전에 지난 회차 이후 아동의 양육상황 · 보호 상황에서 무엇을 점검할지 확인한다.",
    "closure": "사례를 종결해도 되는지 판단하는 기준과 종결 후 사후관리에서 점검할 내용을 확인한다.",
}

VERIFY_SYSTEM_PROMPT = """당신은 아동 상담사에게 보여 줄 업무 매뉴얼 근거를 고르는 보조 분석기입니다.

화면 목적: {purpose}

[찾는 내용]과 업무 매뉴얼 [검색 후보]를 비교해, 아래 두 조건을 모두 만족하는 후보만 고르세요.
1. [찾는 내용]의 상황과 직접 관련된 내용이다. 단어가 비슷하다는 이유만으로 고르지 않습니다.
2. 화면 목적에 쓸모 있는 내용(점검할 항목, 판단 기준, 확인할 사항)이 담겨 있다.
   작성자 · 작성 시기 · 결재 · 송부처처럼 서식 작성 절차만 있거나, 빈칸 이름만 나열된 후보는 고르지 않습니다.

규칙:
- 맞는 후보가 없으면 빈 배열을 돌려줍니다. 억지로 채우지 않습니다.
- 관련성이 높은 순서로 최대 {limit}개까지 고릅니다.
- reason 에는 [찾는 내용]의 어떤 부분과 맞는지 짧고 중립적으로 씁니다.
- 학대 여부나 법적 판단을 하지 않습니다.
"""


def _verify_candidates(
    query: str,
    screen: str,
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[tuple[dict[str, Any], str]]:
    candidate_lines = []
    for index, item in enumerate(candidates, start=1):
        section = str(item["metadata"].get("screen_section", ""))
        body = " ".join(strip_section_prefix(item["content"], section).split())
        candidate_lines.append(f"[{index}] ({section}) {body}")

    llm = ChatOpenAI(model=ANALYZER_MODEL).with_structured_output(ItemSelection)
    result = llm.invoke(
        [
            ("system", VERIFY_SYSTEM_PROMPT.format(purpose=SCREEN_PURPOSES[screen], limit=top_k)),
            ("human", f"[찾는 내용]\n{query}\n\n[검색 후보]\n" + "\n".join(candidate_lines)),
        ]
    )

    chosen: list[tuple[dict[str, Any], str]] = []
    seen: set[int] = set()
    for match in result.matches:
        if not 1 <= match.item_id <= len(candidates) or match.item_id in seen:
            continue
        chosen.append((candidates[match.item_id - 1], match.reason.strip()))
        seen.add(match.item_id)
        if len(chosen) >= top_k:
            break
    return chosen


# ---------------------------------------------------------------------------
# 서식 항목 고르기 (followup)
# ---------------------------------------------------------------------------


class ItemMatch(BaseModel):
    item_id: int = Field(description="후보 목록의 item_id")
    reason: str = Field(description="상담 내용의 어떤 부분이 이 항목과 맞는지 짧고 중립적으로")


class ItemSelection(BaseModel):
    matches: list[ItemMatch] = Field(
        default_factory=list,
        description="상담 내용과 직접 관련된 항목만. 없으면 빈 배열",
    )


ITEM_SYSTEM_PROMPT = """당신은 아동 상담사가 다음 상담에서 확인할 항목을 고르는 보조 분석기입니다.

[상담 내용]과 업무 매뉴얼 점검표 [항목 목록]을 비교해, 상담 내용에 직접 나온 상황을 점검하는 항목만 고르세요.

규칙:
- 상담 내용에 해당 항목의 상황이 실제로 언급된 경우에만 고릅니다. 단어가 비슷하다는 이유만으로 고르지 않습니다.
- 맞는 항목이 없으면 빈 배열을 돌려줍니다. 억지로 채우지 않습니다.
- 아동 상황 점검표 항목과 친부모 상황 점검표 항목이 똑같이 맞으면 아동 상황 점검표 항목을 먼저 둡니다.
- 관련성이 높은 순서로 최대 {limit}개까지 고릅니다.
- 학대 여부나 법적 판단을 하지 않습니다.
"""

# 표 칸의 선택지("예 아니오 불분명함", 글자 사이가 벌어진 것 포함)는 항목 뜻과 무관해 지운다.
_ANSWER_CHOICES = re.compile(r"예\s*아\s*니\s*오\s*불\s*분\s*명\s*함")


def _clean_item_text(text: str) -> str:
    return " ".join(_ANSWER_CHOICES.sub(" ", text).split())


def _load_form_items(screen: str) -> list[dict[str, Any]]:
    """화면 구간의 서식 번호 항목을 (서식, 번호)마다 하나로 모은다.

    서식 8 · 9 는 같은 항목이 평가표와 작성방법에 두 번 나온다. 앞의 평가표 문장을 항목으로,
    뒤의 작성방법 문장을 설명으로 쓴다.
    """
    stored = get_vector_store()._collection.get(
        where={"screen": screen},
        include=["documents", "metadatas"],
    )

    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    rows = sorted(
        zip(stored["documents"], stored["metadatas"]),
        key=lambda row: (int(row[1].get("page", 0) or 0), str(row[1].get("chunk_id", ""))),
    )
    for content, metadata in rows:
        item_no = metadata.get("item_no")
        if item_no is None:
            continue
        section = str(metadata.get("screen_section", ""))
        key = (section, int(item_no))
        text = _clean_item_text(strip_section_prefix(content, section))
        if key not in grouped:
            grouped[key] = {"metadata": metadata, "item": text, "detail": ""}
        elif not grouped[key]["detail"]:
            grouped[key]["detail"] = text

    priority = SCREEN_PRIORITY_SECTIONS.get(screen, ())
    return sorted(
        grouped.values(),
        key=lambda entry: (
            0 if entry["metadata"].get("screen_section") in priority else 1,
            str(entry["metadata"].get("screen_section", "")),
            int(entry["metadata"].get("item_no", 0)),
        ),
    )


def _select_form_items(query: str, screen: str, top_k: int) -> list[dict[str, Any]]:
    items = _load_form_items(screen)
    if not items:
        return []

    item_lines = [
        f"[{index}] ({entry['metadata'].get('screen_section', '')} {entry['metadata'].get('item_no')}번) {entry['item']}"
        for index, entry in enumerate(items, start=1)
    ]
    llm = ChatOpenAI(model=ANALYZER_MODEL).with_structured_output(ItemSelection)
    result = llm.invoke(
        [
            ("system", ITEM_SYSTEM_PROMPT.format(limit=top_k)),
            ("human", f"[상담 내용]\n{query}\n\n[항목 목록]\n" + "\n".join(item_lines)),
        ]
    )

    references: list[dict[str, Any]] = []
    seen: set[int] = set()
    for match in result.matches:
        if not 1 <= match.item_id <= len(items) or match.item_id in seen:
            continue
        entry = items[match.item_id - 1]
        metadata = entry["metadata"]
        reference = format_document_reference({"content": entry["item"], "metadata": metadata})
        reference["item_no"] = metadata.get("item_no")
        reference["detail"] = entry["detail"]
        reference["reason"] = match.reason.strip()
        references.append(reference)
        seen.add(match.item_id)
        if len(references) >= top_k:
            break
    return references


# 매뉴얼 PDF 쪽 머리말("| 265 ", "154 | 2026 "). 화면에 쪽 번호를 보이지 않으므로 요약에서 뺀다.
_PAGE_HEADER = re.compile(r"^\s*(?:\|\s*\d{1,3}|\d{1,3}\s*\|\s*2026)\s*")


def _strip_page_header(summary: str) -> str:
    return _PAGE_HEADER.sub("", summary, count=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="화면별 업무 매뉴얼 구간 검색")
    parser.add_argument("text", help="검색할 상담 문장 또는 질문")
    parser.add_argument("--screen", required=True, choices=list(SCREEN_NAMES))
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    references = search_screen_manual(args.text, args.screen, top_k=args.top_k)

    if args.json:
        print(json.dumps(references, ensure_ascii=False, indent=2))
        return

    print(f"[{SCREEN_NAMES[args.screen]}] 매뉴얼 검색 결과 {len(references)}건")
    if not references:
        print("- 상담 내용과 맞는 매뉴얼 내용이 없습니다.")
    for index, reference in enumerate(references, start=1):
        number = f" {reference['item_no']}번" if reference.get("item_no") else ""
        print(f"{index}. {reference['section']}{number}")
        print(f"   {reference['summary']}")
        if reference.get("reason"):
            print(f"   이유: {reference['reason']}")


if __name__ == "__main__":
    main()
