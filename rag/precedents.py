from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document

# 교육부 가이드북의 "❖ 판례로 보는 신체학대 사례 – 학대행위자가 부모 등인 경우" 같은 머리글.
_SECTION_HEADER = re.compile(
    r"❖\s*판례로 보는\s*(?P<kind>신체학대|정서학대|성학대|방임 및 유기)\s*사례\s*[-–]\s*"
    r"학대행위자가\s*(?P<actor>.+?)인\s*경우"
)
# 판례가 아닌 다음 머리글(징후, 예시 등)이 나오면 판례 구간이 끝난다.
_OTHER_HEADER = re.compile(r"❖")
# 사건 끝의 출처. 예: (인천지방법원 2022고정1131), (청주지방법원 2020노860, 충주지원 2020고단126)
_CASE_REF = re.compile(
    r"\((?P<ref>[^()]*?(?:법원|지원)[^()]*?\d{4}\s*[가-힣]{1,3}\s*\d+[^()]*)\)\s*$"
)
_CASE_NUMBER = re.compile(r"\d{4}[가-힣]{1,3}\d+")
# 쪽 머리(쪽 번호, 장 목록)는 본문이 아니다.
_PAGE_NOISE = re.compile(r"^\s*(\d{3}|.*아동학대 개념과 이해.*|.*피해아동 이해와 대화법.*)\s*$")

KIND_TO_ABUSE_TYPE = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임 및 유기": "neglect",
}


def _join_lines(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", "".join(lines)).strip()


def _parse_ref(ref: str) -> tuple[str, str, str]:
    """출처 괄호 안을 (법원, 사건번호들, 출처 원문)으로 나눈다. 줄바꿈으로 갈라진 사건번호(2021고 정650)는 붙인다."""
    citation = re.sub(r"(\d{4})\s*([가-힣]{1,3})\s*(\d+)", r"\1\2\3", re.sub(r"\s+", " ", ref).strip())
    numbers = _CASE_NUMBER.findall(citation)
    court = citation.split(numbers[0])[0].strip() if numbers else citation
    return court, ", ".join(numbers), citation


def extract_precedent_cases(pages: list[Document]) -> list[dict[str, Any]]:
    """가이드북 쪽 목록에서 '판례로 보는 ○○ 사례' 구간의 사건을 하나씩 뽑는다.

    사건 하나는 '제목 한 줄 → 사실관계 → (법원 사건번호)' 로 끝난다. 쪽을 넘겨 이어지는 사건도 있어
    같은 문서의 쪽을 순서대로 이어 붙여 읽는다.
    """
    cases: list[dict[str, Any]] = []
    section: dict[str, str] | None = None
    title: str | None = None
    body: list[str] = []
    body_page = 0

    for page_doc in sorted(pages, key=lambda doc: int(doc.metadata.get("page", 0) or 0)):
        page = int(page_doc.metadata.get("page", 0) or 0)
        for raw_line in (page_doc.page_content or "").splitlines():
            # 줄 끝 공백은 남긴다. PDF 는 낱말 사이에서 줄을 바꿀 때 끝에 공백을 두고,
            # 낱말 중간에서 바꿀 때는 두지 않아서, 그대로 이어 붙이면 띄어쓰기가 맞는다.
            line = raw_line
            if not line.strip() or _PAGE_NOISE.match(line):
                continue

            header = _SECTION_HEADER.search(line)
            if header:
                section = {
                    "kind": header.group("kind"),
                    "actor": re.sub(r"\s+", " ", header.group("actor")).strip(),
                }
                title, body = None, []
                continue

            if _OTHER_HEADER.search(line):
                section, title, body = None, None, []
                continue

            if section is None:
                continue

            if title is None:
                title, body_page = line.strip(), page
                continue

            body.append(line)
            text = _join_lines(body)
            ref = _CASE_REF.search(text)
            if not ref:
                continue

            court, case_number, citation = _parse_ref(ref.group("ref"))
            cases.append(
                {
                    "title": title,
                    "facts": text[: ref.start()].strip(),
                    "court": court,
                    "case_number": case_number,
                    "citation": citation,
                    "abuse_type": KIND_TO_ABUSE_TYPE[section["kind"]],
                    "abuse_kind": section["kind"],
                    "perpetrator": section["actor"],
                    "page": body_page,
                }
            )
            title, body = None, []

    return cases


def build_precedent_documents(pages: list[Document]) -> list[Document]:
    """원문 쪽 목록에서 판례 사건을 사건 하나당 조각 하나로 만든다(source_type=precedent).

    쪽 단위 조각은 판례 여러 건과 징후 목록이 섞여 있어, 사건별로 따로 색인해야
    상담 내용과 비슷한 사건 하나를 정확히 돌려줄 수 있다.
    """
    by_source: dict[str, list[Document]] = {}
    for page_doc in pages:
        by_source.setdefault(str(page_doc.metadata.get("source", "")), []).append(page_doc)

    documents: list[Document] = []
    for source_pages in by_source.values():
        cases = extract_precedent_cases(source_pages)
        if not cases:
            continue

        base = source_pages[0].metadata
        document_id = str(base.get("document_id", "document"))
        for index, case in enumerate(cases, start=1):
            metadata = {
                "document_id": document_id,
                "source": base.get("source", ""),
                "source_path": base.get("source_path", ""),
                "organization": base.get("organization", ""),
                "source_type": "precedent",
                "category": "precedent",
                "abuse_type": case["abuse_type"],
                "section": f"판례로 보는 {case['abuse_kind']} 사례",
                "subsection": case["perpetrator"],
                "screen": "",
                "screen_section": "",
                "year": 0,
                "authority_level": "reference",
                "page": case["page"],
                "court": case["court"],
                "case_number": case["case_number"],
                "case_title": case["title"],
                "origin": "guidebook",
                "citation": case["citation"],
                "chunk_id": f"{document_id}_prec_{index:03d}",
            }
            documents.append(
                Document(page_content=f"{case['title']}\n{case['facts']}", metadata=metadata)
            )

    return documents


# 판례 최소 코사인 유사도. 이보다 낮으면 비슷한 사건이 없는 것으로 본다.
# 2026-10 측정(가이드북 23건 + 법령 API 판례, 학대 유형 필터 적용, 1위 점수):
#   맞는 문장 9개 0.26~0.53 / 무관한 문장 5개 0.13~0.32
# 두 범위가 겹쳐서 무관한 문장 5개 중 2개는 걸러지지 않는다. 실제 상담 문장이 쌓이면 다시 맞춘다.
PRECEDENT_MIN_SIMILARITY = 0.25


def _shorten(text: str, limit: int = 500) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def search_precedents(
    text: str,
    abuse_type: str,
    *,
    top_k: int = 3,
    min_similarity: float | None = PRECEDENT_MIN_SIMILARITY,
) -> list[dict[str, Any]]:
    """색인해 둔 판례(가이드북 사례 + 법령 API 에서 모아 둔 판례) 중 상담 내용과 비슷한 사건을 찾는다.

    분석할 때 국가법령정보센터를 부르지 않는다. text 는 비식별한 문장이어야 한다(임베딩을 위해 OpenAI 로 나간다).
    한 판례가 여러 학대 유형에 걸리면 유형마다 조각이 있어, 유형 필터 없이 찾을 때는 같은 사건을 한 번만 남긴다.
    """
    from .retriever import search_evidence

    found = search_evidence(
        text,
        top_k=top_k * 3,
        source_type="precedent",
        abuse_type=None if abuse_type == "multiple" else abuse_type,
        min_similarity=min_similarity,
    )

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in found:
        metadata = item.get("metadata", {})
        key = str(metadata.get("case_number") or metadata.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)

        content = str(item.get("content", ""))
        title, _, facts = content.partition("\n")
        results.append(
            {
                "type": "precedent",
                "origin": metadata.get("origin") or "guidebook",
                "title": metadata.get("case_title") or title,
                "case_name": metadata.get("case_name", ""),
                "summary": _shorten(facts.strip() or content),
                "court": metadata.get("court", ""),
                "case_number": metadata.get("case_number", ""),
                "citation": metadata.get("citation", ""),
                "abuse_type": metadata.get("abuse_type", ""),
                "perpetrator": metadata.get("subsection", ""),
                "source": metadata.get("source", ""),
                "page": metadata.get("page") or None,
                "url": metadata.get("url", ""),
                "similarity": item.get("similarity"),
            }
        )
        if len(results) >= top_k:
            break
    return results


def find_similar_precedents(
    text: str,
    abuse_type: str,
    *,
    top_k: int = 3,
) -> tuple[list[dict[str, Any]], str | None]:
    """관련 법령 옆에 보여 줄 유사 판례. 실패해도 분석 전체를 멈추지 않고 사유를 경고로 돌려준다."""
    try:
        return search_precedents(text, abuse_type, top_k=top_k), None
    except Exception as error:  # noqa: BLE001 — 판례 검색 실패는 경고로 돌려주고 분석은 계속한다
        return [], f"판례 검색 실패: {type(error).__name__}"
