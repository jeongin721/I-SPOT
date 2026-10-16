from __future__ import annotations

import argparse
import json
import re
from typing import Any

from .metadata import SCREEN_NAMES, SCREEN_PRIORITY_SECTIONS
from .resource_ranker import format_document_reference
from .retriever import search_evidence


def search_screen_manual(
    text: str,
    screen: str,
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """업무 매뉴얼에서 해당 화면 구간(metadata.MANUAL_SCREEN_SECTIONS)만 검색한다.

    screen: followup(추가 확인 · 질문) / prebriefing(상담 전 브리핑) / closure(종결 검토)
    구간 밖 내용(전달체계, 입양, 실종아동 등)은 검색되지 않는다.
    """
    if screen not in SCREEN_NAMES:
        raise ValueError(f"알 수 없는 화면입니다: {screen} ({', '.join(SCREEN_NAMES)})")

    query = text.strip()
    if not query:
        raise ValueError("검색할 문장이 비어 있습니다.")

    results = _search_with_priority(query, screen, top_k)
    references = [format_document_reference(item) for item in results]
    for reference in references:
        reference["summary"] = _strip_page_header(reference["summary"])
    return references


def _search_with_priority(query: str, screen: str, top_k: int) -> list[dict[str, Any]]:
    """우선 구간(SCREEN_PRIORITY_SECTIONS)에서 top_k - 1 개까지 먼저 고르고, 나머지는 화면 전체 구간에서 채운다.

    한 자리는 다른 구간 몫으로 남겨 결과가 우선 구간 하나로만 채워지지 않게 한다.
    """
    priority_sections = SCREEN_PRIORITY_SECTIONS.get(screen, ())
    if not priority_sections or top_k < 2:
        return search_evidence(query, top_k=top_k, screen=screen)

    results: list[dict[str, Any]] = []
    for section in priority_sections:
        results.extend(
            search_evidence(query, top_k=top_k - 1, screen=screen, screen_section=section)
        )
    results = results[: top_k - 1]

    seen = {item.get("metadata", {}).get("chunk_id") for item in results}
    # 우선 구간 조각이 다시 나올 수 있으므로 넉넉히 받아 겹치지 않는 것으로 채운다.
    for item in search_evidence(query, top_k=top_k * 2, screen=screen):
        if len(results) >= top_k:
            break
        chunk_id = item.get("metadata", {}).get("chunk_id")
        if chunk_id in seen or item.get("metadata", {}).get("screen_section") in priority_sections:
            continue
        results.append(item)
        seen.add(chunk_id)

    return results


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
    for index, reference in enumerate(references, start=1):
        print(f"{index}. {reference['section']}")
        print(f"   {reference['summary']}")


if __name__ == "__main__":
    main()
