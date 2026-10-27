# 발화별 법령 자동 인용(ai/modeling/abuse/legal_reference_adapter.py)을
# 테스트한다.
#
# 2026-10-27 다솔 디자인(counselor-design/screens/SttReview.dc.html,
# "관련 조문" 칼럼) 검토 중 발견: law/mapper.py의 rank_law_articles는
# 애초에 이 용도로 만들어졌지만 실제로 부르는 코드(legal_reference_adapter.py)
# 가 없었다. LLM을 쓰지 않는 결정적 로직이라(rank_law_articles의 키워드
# 매칭만 씀) 실제 법령 데이터 없이도 순수 함수로 테스트할 수 있다.

from ai.modeling.abuse.legal_reference_adapter import (
    _build_legal_reference,
    _pick_matching_item,
    _split_article_items,
    attach_legal_references,
)


_ARTICLE_17 = {
    "law_name": "아동복지법",
    "article": "제17조",
    "title": "금지행위",
    "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=290207&joNo=0017&joBrNo=00",
    "content": (
        "1. 아동을 매매하는 행위\n"
        "2. 아동에게 음란한 행위를 시키거나 이를 매개하는 행위\n"
        "3. 아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위\n"
        "5. 아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위\n"
        "제17조(금지행위) 누구든지 다음 각 호의 어느 하나에 해당하는 행위를 하여서는 아니 된다."
    ),
}

_ARTICLE_10 = {
    "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
    "article": "제10조",
    "title": "아동학대범죄 신고의무와 절차",
    "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=289809&joNo=0010&joBrNo=00",
    "content": "① 누구든지 아동학대범죄를 알게 된 경우나... 신고할 수 있다.\n제10조(아동학대범죄 신고의무와 절차)",
}


def test_split_article_items_parses_numbered_lines():
    items = _split_article_items(_ARTICLE_17["content"])

    assert items == [
        ("1", "아동을 매매하는 행위"),
        ("2", "아동에게 음란한 행위를 시키거나 이를 매개하는 행위"),
        ("3", "아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위"),
        ("5", "아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위"),
    ]


def test_split_article_items_returns_empty_when_no_numbered_items():
    # 제10조처럼 호 구분이 없는 절차 조문 — 빈 리스트.
    items = _split_article_items(_ARTICLE_10["content"])

    assert items == []


def test_pick_matching_item_finds_physical_abuse_item():
    items = _split_article_items(_ARTICLE_17["content"])

    matched = _pick_matching_item(items, "신체학대")

    assert matched == ("3", "아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위")


def test_pick_matching_item_finds_emotional_abuse_item():
    items = _split_article_items(_ARTICLE_17["content"])

    matched = _pick_matching_item(items, "정서학대")

    assert matched == ("5", "아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위")


def test_pick_matching_item_returns_none_when_no_match():
    items = _split_article_items(_ARTICLE_17["content"])

    # "방임행위"를 가리키는 호가 이 조문 발췌에는 없다.
    assert _pick_matching_item(items, "방임") is None


def test_build_legal_reference_uses_item_text_when_matched():
    reference = _build_legal_reference(_ARTICLE_17, "신체학대")

    assert reference == {
        "short_label": "신체",
        "law_name": "아동복지법",
        "article": "제17조",
        "item_label": "제3호",
        "text": "아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위",
        "portal_url": _ARTICLE_17["portal_url"],
    }


def test_build_legal_reference_falls_back_to_article_title_when_no_items():
    # 제10조처럼 호 구분이 없으면 조 제목으로 대체한다(지어내지 않음).
    reference = _build_legal_reference(_ARTICLE_10, "신체학대")

    assert reference["item_label"] == ""
    assert reference["text"] == "아동학대범죄 신고의무와 절차"


def test_attach_legal_references_returns_empty_list_for_empty_input():
    # 빈 입력이면 law/client.py 네트워크 호출(_build_law_corpus) 전에
    # 바로 빠져나가야 한다 — law_qa_llm 테스트와 같은 이유로, 이
    # 테스트는 법령 API·캐시 없이도 돌아야 한다.
    assert attach_legal_references([]) == []


def test_attach_legal_references_does_not_mutate_input(monkeypatch):
    # _build_law_corpus(네트워크·캐시 의존)를 가짜로 바꿔서, 이 테스트가
    # law_qa_llm 테스트들처럼 순수 함수 수준으로 돌게 한다.
    import ai.modeling.abuse.legal_reference_adapter as adapter_module

    monkeypatch.setattr(
        adapter_module,
        "_build_law_corpus",
        lambda names: ("", [_ARTICLE_17]),
    )

    points = [
        {"major_type": "신체학대", "text": "많이 때렸어요.", "segment_ids": ["seg_001"]}
    ]

    attach_legal_references(points, law_names=["아동복지법"])

    # 원본 딕셔너리에 legal_references가 끼어들지 않아야 한다.
    assert "legal_references" not in points[0]
