# 법령 AI 질의(ai/modeling/abuse/law_qa_llm.py)의 인용 검증 로직을 테스트한다.
# 2026-10-26 현직자 인터뷰("I-SPOT 현직자 인터뷰 정리.pdf")가 요청한 "법령·매뉴얼
# AI 질의" 기능의 첫 구현. 두 법령(아동복지법·아동학대범죄의 처벌 등에 관한
# 특례법)을 동시에 컨텍스트에 넣다 보니, 실제 LLM 호출로 테스트하다가 두 법령에
# 같은 번호의 조문(둘 다 "제10조", "제63조")이 있어서 조문 번호만으로 인용을
# 매칭하면 엉뚱한 법령의 조문이 붙는 버그를 발견했다 — 이 테스트가 그 회귀를
# 고정한다.

from ai.modeling.abuse.law_qa_llm import _verify_cited_articles


def _make_articles():
    return [
        {
            "law_name": "아동복지법",
            "article": "제10조",
            "title": "아동정책조정위원회",
            "content": "위원회를 둔다.",
        },
        {
            "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
            "article": "제10조",
            "title": "아동학대범죄 신고의무와 절차",
            "content": "즉시 신고하여야 한다.",
        },
        {
            "law_name": "아동복지법",
            "article": "제63조",
            "title": "면세",
            "content": "조세를 면제할 수 있다.",
        },
        {
            "law_name": "아동학대범죄의 처벌 등에 관한 특례법",
            "article": "제63조",
            "title": "과태료",
            "content": "1천만원 이하의 과태료를 부과한다.",
        },
    ]


def test_same_article_number_in_two_laws_resolves_to_correct_law():
    # 2026-10-26 실제 LLM 테스트로 발견: 두 법령 모두 "제10조"·"제63조"가
    # 있는데, 번호만으로 매칭하면 먼저 나온 법(아동복지법)의 조문이
    # 잘못 붙었다. law_name까지 같이 맞아야 통과해야 한다.
    claimed = [
        {"law_name": "아동학대범죄의 처벌 등에 관한 특례법", "article": "제10조"},
        {"law_name": "아동학대범죄의 처벌 등에 관한 특례법", "article": "제63조"},
    ]

    verified = _verify_cited_articles(claimed, _make_articles())

    assert len(verified) == 2
    for article in verified:
        assert article["law_name"] == "아동학대범죄의 처벌 등에 관한 특례법"
    titles = {article["title"] for article in verified}
    assert titles == {"아동학대범죄 신고의무와 절차", "과태료"}
    # 아동복지법 쪽의 동명 조문("아동정책조정위원회", "면세")이 섞여
    # 들어오면 안 된다.
    assert "아동정책조정위원회" not in titles
    assert "면세" not in titles


def test_nonexistent_article_is_dropped_not_fabricated():
    # LLM이 법령에 없는 조문 번호를 지어내 인용해도(법령명이 틀렸거나
    # 조문 자체가 없으면), 조용히 빠져야 한다 — 없는 근거를 있는 것처럼
    # 보여주면 안 된다.
    claimed = [
        {"law_name": "아동복지법", "article": "제999조"},
        {"law_name": "존재하지 않는 법", "article": "제10조"},
    ]

    verified = _verify_cited_articles(claimed, _make_articles())

    assert verified == []


def test_duplicate_citations_are_deduplicated():
    claimed = [
        {"law_name": "아동복지법", "article": "제10조"},
        {"law_name": "아동복지법", "article": "제10조"},
    ]

    verified = _verify_cited_articles(claimed, _make_articles())

    assert len(verified) == 1


def test_non_list_or_malformed_input_returns_empty():
    articles = _make_articles()

    assert _verify_cited_articles(None, articles) == []
    assert _verify_cited_articles("제10조", articles) == []
    assert _verify_cited_articles([{"article": "제10조"}], articles) == []
    assert _verify_cited_articles(["제10조"], articles) == []


# ------------------------------------------------------------
# 2026-10-27 §6-1(PROPOSAL_law_guide_api.md): 실패를 성공처럼 돌려주지 않는다
# ------------------------------------------------------------

import sys
import types

import pytest

import ai.modeling.abuse.law_qa_llm as law_qa_llm
from ai.modeling.abuse.law_qa_llm import LawQAOutputError


@pytest.fixture
def stub_law(monkeypatch):
    gateway = types.ModuleType("ai.modeling.abuse.privacy_gateway")
    gateway.mask_for_outbound = lambda text, **kwargs: (text, {})
    masking = types.ModuleType("ai.modeling.abuse.pii_masking")
    masking.restore_pii = lambda value, entity_map: value
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.privacy_gateway", gateway)
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.pii_masking", masking)
    monkeypatch.setattr(law_qa_llm, "_build_law_corpus", lambda names, **kwargs: ("", _make_articles()))

    return lambda behavior: monkeypatch.setattr(law_qa_llm, "_call_llm_with_retry", behavior)


def _ask():
    return law_qa_llm.answer_law_question(client=None, model="test", question="신고의무는?")


def test_llm_failure_is_raised_not_put_in_answer(stub_law):
    class AuthenticationError(Exception):
        pass

    def fail(**kwargs):
        raise AuthenticationError("Incorrect API key: sk-…")

    stub_law(fail)

    with pytest.raises(AuthenticationError):
        _ask()


@pytest.mark.parametrize("parsed", [{}, {"answer": ""}, [], None])
def test_empty_answer_raises_output_error(stub_law, parsed):
    stub_law(lambda **kwargs: parsed)

    with pytest.raises(LawQAOutputError, match="^법령 질의 답변을 만들지 못했습니다.$"):
        _ask()


def test_success_keeps_answer_and_verified_citations(stub_law):
    stub_law(
        lambda **kwargs: {
            "answer": "즉시 신고하여야 합니다.",
            "cited_articles": [{"law_name": "아동학대범죄의 처벌 등에 관한 특례법", "article": "제10조"}],
        }
    )

    result = _ask()

    # R3(2026-10-27): 법령 전용 답변에도 고정 안내가 늘 붙는다.
    assert result["answer"] == f"즉시 신고하여야 합니다.\n\n{law_qa_llm.REFERENCE_NOTICE}"
    assert [item["title"] for item in result["cited_articles"]] == ["아동학대범죄 신고의무와 절차"]
