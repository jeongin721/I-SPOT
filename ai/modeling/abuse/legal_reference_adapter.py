"""발화별 법령 자동 인용 — SttReview 화면의 "관련 조문"에 쓴다.

[왜 이제껏 없었나]

`law/mapper.py`의 `rank_law_articles()`는 애초에 "학대유형이 감지된
발화마다 관련 조문을 자동으로 붙이는" 용도로 만들어졌고, 그 docstring도
"legal_reference_adapter.py 같은 기존 파이프라인이 씀"이라고 적혀 있었다
— 그런데 실제로 그걸 부르는 `legal_reference_adapter.py`는 코드 어디에도
없었다. 2026-10-27 다솔 디자인(`counselor-design/screens/SttReview.dc.html`,
"관련 조문" 칼럼) 검토 중 발견해서 이제 만든다.

[법령 QA(law_qa_llm.py)와 다른 점]

`law_qa_llm.py`는 상담사가 자유 질문을 타이핑하면 LLM이 답하는 Q&A다.
이 모듈은 LLM을 전혀 쓰지 않는다 — 이미 감지된 `risk_signal_points`
(major_type·텍스트)를 입력받아 `rank_law_articles`의 키워드 매칭만으로
조문을 고르는 결정적(deterministic) 로직이다. second_stage_llm.py의
2차 분석 프롬프트에 법조문 선택까지 끼워 넣지 않는 것도 같은
이유다(protective_factor_llm.py가 위험신호 탐지와 분리된 것과 같은
설계 원칙 — 이미 튜닝된 분류 프롬프트를 건드리지 않는다).

[제17조(금지행위) 같은 호(項) 단위로 보여주는 이유]

법령 전문은 "조(條)" 하나에 11개 호가 다 들어 있어서(제17조는 매매·
성적학대·신체적학대·정서적학대 등 11개를 한 번에 나열) 조 전체를
보여주면 상담사가 어느 호가 이 발화랑 관련 있는지 다시 찾아야 한다.
그래서 학대유형별로 "그 유형을 직접 가리키는 호"(_ITEM_MATCH_KEYWORD)
만 골라 보여준다 — 법령 QA(law_qa_llm.py)가 조 단위로 인용하는 것과
다른 선택이다. 매칭되는 호를 못 찾으면(조사 중 조항처럼 호 구분이
없는 조문) 조 전체 제목으로 대체한다.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ai.modeling.abuse.law_qa_llm import _build_law_corpus
from law.config import LAW_TARGET_LAWS
from law.mapper import rank_law_articles

#: Contract/파이프라인 내부에서 쓰는 한글 major_type(VALID_MAJOR_TYPES,
#: second_stage_llm.py)을 law/mapper.py의 ABUSE_LAW_KEYWORDS 키로 바꾼다.
MAJOR_TYPE_TO_MAPPER_KEY = {
    "신체학대": "physical",
    "정서학대": "emotional",
    "성학대": "sexual",
    "방임": "neglect",
}

#: SttReview 화면에 쓰는 짧은 라벨.
SHORT_LABEL = {
    "신체학대": "신체",
    "정서학대": "정서",
    "성학대": "성",
    "방임": "방임",
}

#: 조문 안에서 "이 유형을 직접 가리키는 호"를 찾을 때 쓰는 키워드.
#: ABUSE_LAW_KEYWORDS(랭킹용, 느슨함)와 달리 이건 호 텍스트 안에 실제로
#: 쓰인 문구와 정확히 일치해야 해서 따로 둔다(예: 제17조 3호 "신체적
#: 학대행위", 5호 "정서적 학대행위").
_ITEM_MATCH_KEYWORD = {
    "신체학대": "신체적 학대행위",
    "정서학대": "정서적 학대행위",
    "성학대": "성적 학대행위",
    "방임": "방임행위",
}

_ITEM_LINE_RE = re.compile(r"^(\d+(?:의\d+)?)\.\s*(.+)$")

DEFAULT_LIMIT = 2


def _split_article_items(content: str) -> List[Tuple[str, str]]:
    """조문 본문을 "호" 단위 줄로 쪼갠다.

    law_qa_llm._build_law_corpus가 가져오는 조문 content는 "1. ...\\n2.
    ...\\n제17조(금지행위) ..." 형태로, 번호 매긴 호가 줄마다 있고 조
    제목은 맨 끝에 따로 붙는다(law/client.py 응답 그대로). 이 형태를
    못 찾으면(제10조처럼 호 구분이 없는 절차 조문) 빈 리스트를 준다.
    """

    items: List[Tuple[str, str]] = []

    for line in content.splitlines():
        match = _ITEM_LINE_RE.match(line.strip())
        if match:
            items.append((match.group(1), match.group(2).strip()))

    return items


def _pick_matching_item(
    items: List[Tuple[str, str]], major_type: str
) -> Optional[Tuple[str, str]]:
    keyword = _ITEM_MATCH_KEYWORD.get(major_type)

    if not keyword:
        return None

    for item_no, item_text in items:
        if keyword in item_text:
            return item_no, item_text

    return None


def _build_legal_reference(
    article: Dict[str, Any], major_type: str
) -> Dict[str, Any]:
    content = article.get("content", "")
    items = _split_article_items(content)
    matched_item = _pick_matching_item(items, major_type)

    if matched_item:
        item_no, text = matched_item
        item_label = f"제{item_no}호"
    else:
        item_label = ""
        text = article.get("title", "")

    return {
        "short_label": SHORT_LABEL.get(major_type, major_type),
        "law_name": article.get("law_name", ""),
        "article": article.get("article", ""),
        "item_label": item_label,
        "text": text,
        "portal_url": article.get("portal_url", ""),
    }


def attach_legal_references(
    risk_signal_points: List[Dict[str, Any]],
    *,
    law_names: Optional[List[str]] = None,
    limit: int = DEFAULT_LIMIT,
) -> List[Dict[str, Any]]:
    """risk_signal_points(record_draft_llm._build_risk_signal_points 출력)
    각 항목에 관련 법조문 목록(legal_references)을 붙인 새 리스트를
    반환한다. 입력 리스트·딕셔너리는 바꾸지 않는다.

    법조문 자체를 새로 분석·판단하지 않는다 — law/mapper.py의 키워드
    랭킹 결과를 그대로 쓴다. 매칭되는 조문이 없으면 legal_references는
    빈 리스트다(지어내지 않음).
    """

    if not risk_signal_points:
        return []

    names = law_names or list(LAW_TARGET_LAWS)
    _, articles = _build_law_corpus(names)

    enriched: List[Dict[str, Any]] = []

    for point in risk_signal_points:
        major_type = point.get("major_type", "")
        mapper_key = MAJOR_TYPE_TO_MAPPER_KEY.get(major_type, major_type)
        text = point.get("text", "") or ""

        ranked = rank_law_articles(
            articles,
            abuse_type=mapper_key,
            consultation_text=text,
            limit=limit,
        )

        legal_references = [
            _build_legal_reference(article, major_type) for article in ranked
        ]

        enriched.append({**point, "legal_references": legal_references})

    return enriched


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    sample_points = [
        {
            "major_type": "신체학대",
            "subtype": "직접 신체 가해",
            "text": "아빠가 또 화났어요. 저한테 소리 지르고... 많이 때렸어요.",
            "segment_ids": ["seg_001"],
        },
        {
            "major_type": "정서학대",
            "subtype": "위협",
            "text": "말하면 더 혼난다고 했어요.",
            "segment_ids": ["seg_002"],
        },
    ]

    result = attach_legal_references(sample_points)
    print(json.dumps(result, ensure_ascii=False, indent=2))
