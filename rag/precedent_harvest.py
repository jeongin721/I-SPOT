"""국가법령정보센터 판례 API 에서 아동학대 판례를 모아 색인용 파일로 저장한다.

판례는 바뀌지 않으므로 분석할 때마다 API 를 부르지 않고, 한 번 모아 벡터 DB 에 넣어 둔다.
API 검색은 최근 선고 순이라 상담 내용과 비슷한 사건을 고를 수 없기 때문이다.

    python -m rag.precedent_harvest      # 모으기 → law_cache/precedent_index.json
    python -m rag.indexer                # 가이드북 판례와 함께 색인

판례 API 사용 신청(open.law.go.kr)이 되어 있어야 한다. 판례 본문은 law_cache/precedents/ 에 캐시한다.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from typing import Any

from langchain_core.documents import Document

from .config import LAW_CACHE_DIR

PRECEDENT_INDEX_PATH = LAW_CACHE_DIR / "precedent_index.json"
PRECEDENT_PORTAL_URL = "https://www.law.go.kr/LSW/precInfoP.do"

# (search, query). search=1 사건명, 2 본문. 아동학대 사건명과 학대 유형별 본문 표현으로 모은다.
HARVEST_QUERIES = (
    (1, "아동학대"),
    (1, "아동복지법위반"),
    (1, "아동학대범죄의처벌등에관한특례법위반"),
    (2, "신체적 학대행위"),
    (2, "정서적 학대행위"),
    (2, "성적 학대행위"),
    (2, "방임행위"),
)
PAGE_SIZE = 100

# 판례가 어느 학대 유형인지는 판례 전문(사건명 · 판시사항 · 판결요지 · 판례내용)에 나온 표현으로 정한다(여러 유형 가능).
# 아동 사건이 아닌 판례(노인 방임, 직무유기 등)가 섞이지 않도록 아동 학대 문맥(CHILD_CONTEXT)이 있을 때만 본다.
TYPE_TERMS = {
    "physical": ("신체적 학대", "신체적학대", "아동학대치사", "아동학대중상해", "아동학대살해", "상습아동학대"),
    "emotional": ("정서적 학대", "정서적학대"),
    "sexual": ("성적 학대", "성적학대", "13세미만미성년자", "13세 미만 미성년자", "아동·청소년의성보호", "아동ㆍ청소년의성보호"),
    "neglect": ("방임행위", "방임 행위", "유기·방임", "유기ㆍ방임", "아동유기", "기본적 보호ㆍ양육", "기본적 보호·양육"),
}
CHILD_CONTEXT = ("아동학대", "아동복지법", "아동·청소년", "아동ㆍ청소년", "피해아동")

# 사실관계는 판례내용에서 이 머리글이 처음 나온 곳부터 읽는다(앞에 있는 것이 우선).
# 문장 중간의 '범죄사실'(예: "원심 판시 범죄사실 1. 가.항")은 머리글이 아니므로 대괄호 머리글만 본다.
_FACT_MARKERS = (
    re.compile(r"공소사실의\s*요지"),
    re.compile(r"【\s*범\s*죄\s*사\s*실\s*】"),
    re.compile(r"【\s*이\s*유\s*】"),
)
FACT_LENGTH = 1200
# 유형 판별에 쓰는 사실관계 길이. 판결 뒤쪽은 법 조문 전체(제17조 각 호)를 인용해 모든 유형 표현이 나오므로 앞부분만 본다.
CLASSIFY_LENGTH = 3000


def clean_html(text: Any) -> str:
    text = re.sub(r"<br\s*/?>", " ", str(text or ""), flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def _format_date(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        return clean_html(value)
    return f"{digits[:4]}. {int(digits[4:6])}. {int(digits[6:])}."


def _first_holding(holding: str, limit: int = 120) -> str:
    """판시사항의 첫 항목. 사건명은 대부분 '아동복지법위반(아동학대)'라 제목으로 구별이 안 된다."""
    parts = [part.strip(" ,/") for part in re.split(r"\[\d+\]", holding) if part.strip(" ,/")]
    first = parts[0] if parts else holding
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def _facts_title(facts: str, limit: int = 100) -> str:
    """판시사항이 없는 하급심 판결은 사실관계 첫 문장을 제목으로 쓴다. 사실 서술('피고인은 …')이 아니면 빈 문자열."""
    text = re.sub(r"^(공소사실의\s*요지|범\s*죄\s*사\s*실|이\s*유)\s*(은|는)?[\s,:]*", "", facts)
    text = re.sub(r"^([가-하1-9]\.|\d\))\s*", "", text)
    if not text.startswith("피고인"):
        return ""
    sentence = re.split(r"(?<=다\.)\s", text, maxsplit=1)[0]
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def extract_facts(body: str, length: int = FACT_LENGTH) -> str:
    """판례내용에서 공소사실의 요지 · 범죄사실을 읽는다. 둘 다 없으면 이유 부분, 그것도 없으면 처음부터 읽는다."""
    start = 0
    for marker in _FACT_MARKERS:
        found = marker.search(body)
        if found:
            start = found.start()
            break
    facts = re.sub(r"【\s*([^】]*?)\s*】", r"\1 ", body[start:])
    return re.sub(r"\s+", " ", facts).strip()[:length]


def classify_abuse_types(text: str) -> list[str]:
    if not any(term in text for term in CHILD_CONTEXT):
        return []
    return [abuse_type for abuse_type, terms in TYPE_TERMS.items() if any(term in text for term in terms)]


def build_record(prec_id: str, item: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any] | None:
    """판례 하나를 색인용 기록으로 만든다. 아동학대 유형 표현이 없으면 None."""
    holding = clean_html(detail.get("판시사항"))
    gist = clean_html(detail.get("판결요지"))
    body = clean_html(detail.get("판례내용"))
    facts = extract_facts(body)
    case_name = clean_html(detail.get("사건명") or item.get("사건명"))

    abuse_types = classify_abuse_types(
        " ".join((case_name, holding, gist, extract_facts(body, CLASSIFY_LENGTH)))
    )
    if not abuse_types:
        return None

    court = clean_html(detail.get("법원명") or item.get("법원명"))
    case_number = clean_html(detail.get("사건번호") or item.get("사건번호"))
    date = _format_date(detail.get("선고일자") or item.get("선고일자"))
    return {
        "prec_id": prec_id,
        "case_name": case_name,
        "title": _first_holding(holding) if holding else (_facts_title(facts) or case_name),
        "court": court,
        "case_number": case_number,
        "date": date,
        "citation": " ".join(part for part in (court, date, case_number) if part),
        "holding": holding,
        "gist": gist,
        "facts": facts or gist or holding,
        "abuse_types": abuse_types,
        "url": f"{PRECEDENT_PORTAL_URL}?precSeq={prec_id}",
    }


def harvest(client: Any = None, *, refresh: bool = False) -> dict[str, Any]:
    """검색어마다 모든 쪽을 받아 판례 본문을 모으고 PRECEDENT_INDEX_PATH 에 저장한다."""
    from law.client import LawApiClient

    client = client or LawApiClient()
    items: dict[str, dict[str, Any]] = {}
    for search, query in HARVEST_QUERIES:
        page = 1
        while True:
            found = client.search_precedents(query, search=search, display=PAGE_SIZE, page=page)
            for item in found:
                items.setdefault(str(item.get("판례일련번호", "")).strip(), item)
            if len(found) < PAGE_SIZE:
                break
            page += 1

    from law.client import LawApiError

    records = []
    skipped = 0
    unavailable = 0
    for prec_id, item in items.items():
        try:
            detail = client.get_precedent(prec_id, refresh=refresh)
        except LawApiError:
            # 목록에는 있지만 본문 API 가 "일치하는 판례가 없습니다"를 돌려주는 판례가 있다.
            unavailable += 1
            continue
        record = build_record(prec_id, item, detail)
        if record is None:
            skipped += 1
            continue
        records.append(record)

    PRECEDENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRECEDENT_INDEX_PATH.write_text(
        json.dumps(
            {"harvested_at": datetime.now(timezone.utc).isoformat(), "records": records},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"found": len(items), "records": len(records), "skipped": skipped, "unavailable": unavailable}


def load_harvested_documents() -> list[Document]:
    """모아 둔 판례를 색인 조각으로 만든다. 유형 필터로 찾을 수 있게 학대 유형마다 조각을 하나씩 둔다."""
    if not PRECEDENT_INDEX_PATH.exists():
        return []

    records = json.loads(PRECEDENT_INDEX_PATH.read_text(encoding="utf-8")).get("records", [])
    documents = []
    for record in records:
        for abuse_type in record["abuse_types"]:
            documents.append(
                Document(
                    page_content=f"{record['title']}\n{record['facts']}",
                    metadata={
                        "document_id": "law_api_precedents",
                        "source": "국가법령정보센터",
                        "organization": "법제처",
                        "source_type": "precedent",
                        "category": "precedent",
                        "abuse_type": abuse_type,
                        "section": "",
                        "subsection": "",
                        "screen": "",
                        "screen_section": "",
                        "year": 0,
                        "authority_level": "official",
                        "page": 0,
                        "origin": "law_api",
                        "court": record["court"],
                        "case_number": record["case_number"],
                        "case_title": record["title"],
                        "case_name": record["case_name"],
                        "citation": record["citation"],
                        "url": record["url"],
                        "chunk_id": f"prec_api_{record['prec_id']}_{abuse_type}",
                    },
                )
            )
    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description="국가법령정보센터 판례 API 에서 아동학대 판례를 모은다.")
    parser.add_argument("--refresh", action="store_true", help="캐시한 판례 본문도 다시 받는다")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()
    result = harvest(refresh=args.refresh)
    print(
        f"검색된 판례 {result['found']}건 중 아동학대 유형 판례 {result['records']}건 저장, "
        f"유형 표현 없어 {result['skipped']}건 제외, 본문 미제공 {result['unavailable']}건 → {PRECEDENT_INDEX_PATH}"
    )


if __name__ == "__main__":
    main()
