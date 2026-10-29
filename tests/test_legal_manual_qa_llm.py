# 법령·매뉴얼 AI 질의(ai/modeling/abuse/legal_manual_qa_llm.py)의 매뉴얼
# 페이지 선택·인용 검증 로직을 테스트한다.
#
# 2026-10-26 현직자 인터뷰("I-SPOT 현직자 인터뷰 정리.pdf" §6-2 "법령·
# 매뉴얼 AI 질의")가 요청한 기능을 law_qa_llm.py(법령 전용)에 "2026년
# 아동학대 대응 업무 매뉴얼" 6장(서식·참고자료) 이미지를 결합해 확장한
# 첫 구현이다. 매뉴얼 원본이 텍스트가 아니라 사진이라 law_qa_llm처럼
# 조문 본문과 대조할 수 없고, "이번 호출에 실제로 첨부한 페이지인지"만
# 확인할 수 있다 — _verify_manual_references가 이 역할을 한다.

import sys
import types

import pytest

import ai.modeling.abuse.legal_manual_qa_llm as legal_manual_qa_llm
from ai.modeling.abuse.law_qa_llm import (
    LLM_TIMEOUT_MESSAGE,
    LawQALLMError,
    LawQAOutputError,
)
from ai.modeling.abuse.legal_manual_qa_llm import (
    _resolve_attached_pages,
    _select_manual_pages,
    _verify_manual_references,
)
from manual.manifest import ManualPage


def _make_pages():
    return (
        ManualPage(
            id="risk_scale",
            filename="risk_scale.jpg",
            page="350",
            title="참고자료3 아동학대 위험수준별 개입 사정 척도",
            keywords=("위험수준별", "개입사정척도", "위험요인", "보호요인"),
        ),
        ManualPage(
            id="family_scale",
            filename="family_scale.jpg",
            page="348",
            title="참고자료1 축약형 가족관계척도",
            keywords=("가족관계척도", "축약형"),
        ),
        ManualPage(
            id="initial_interview",
            filename="initial_interview.jpg",
            page="312",
            title="서식4 초기면접지(아동용)",
            keywords=("초기면접", "초기면접지", "서식4"),
        ),
    )


def test_select_manual_pages_matches_by_keyword():
    pages = _make_pages()

    selected = _select_manual_pages(
        "아동학대 위험수준별 개입사정척도 위험요인 문항이 몇 개야?", pages
    )

    assert len(selected) == 1
    assert selected[0].id == "risk_scale"


def test_select_manual_pages_returns_empty_when_no_keyword_matches():
    pages = _make_pages()

    # 법령만 묻는 질문 — 매뉴얼 자료를 첨부할 필요가 없다.
    selected = _select_manual_pages("신고의무자가 신고 안 하면 처벌이 어떻게 돼?", pages)

    assert selected == []


def test_select_manual_pages_respects_limit():
    pages = _make_pages()

    # 세 장 모두에 걸리는 공통 키워드가 없으니, 각 키워드를 다 넣어
    # 전부 매칭되게 만들고 limit으로 잘리는지 확인한다.
    question = "위험수준별 개입사정척도 가족관계척도 초기면접지 다 설명해줘"
    selected = _select_manual_pages(question, pages, limit=2)

    assert len(selected) == 2


def test_resolve_attached_pages_drops_pages_whose_image_is_missing(tmp_path, monkeypatch):
    # 2026-10-26 민규 교차검증으로 발견: _select_manual_pages가 고른
    # 후보 중 이미지 파일이 실제로 있는 페이지만 _build_manual_section
    # (프롬프트 자료 목록)·_build_user_content(실제 첨부)·
    # _verify_manual_references(인용 검증)가 똑같이 봐야 한다. 예전에는
    # _build_user_content만 혼자 필터링해서, 후보 3장 중 이미지가 1장만
    # 있어도 프롬프트엔 "첨부 자료 3개"로 나오고 나머지 2장도 인용
    # 검증을 통과했다.
    monkeypatch.setattr(legal_manual_qa_llm, "MANUAL_IMAGE_DIR", tmp_path)

    pages = _make_pages()
    (tmp_path / "risk_scale.jpg").write_bytes(b"fake-image-bytes")
    # family_scale.jpg · initial_interview.jpg는 일부러 안 만든다 —
    # "이미지가 실제로는 없는 후보" 상황을 재현한다.

    resolved = _resolve_attached_pages(list(pages))

    assert [page.id for page in resolved] == ["risk_scale"]


def test_resolve_attached_pages_returns_empty_when_no_images_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(legal_manual_qa_llm, "MANUAL_IMAGE_DIR", tmp_path)

    pages = _make_pages()

    resolved = _resolve_attached_pages(list(pages))

    assert resolved == []


def test_verify_manual_references_keeps_only_attached_pages():
    pages = _make_pages()
    attached = [pages[0], pages[1]]  # risk_scale, family_scale만 첨부됐다고 가정

    # LLM이 첨부 안 된 "서식4"까지 지어내 인용한 경우 — 빠져야 한다.
    claimed = [
        "참고자료3 아동학대 위험수준별 개입 사정 척도",
        "서식4 초기면접지(아동용)",
    ]

    verified = _verify_manual_references(claimed, attached)

    # 2026-10-27 §6-2: 제목만이 아니라 id · title · page 를 준다.
    assert verified == [
        {"id": "risk_scale", "title": "참고자료3 아동학대 위험수준별 개입 사정 척도", "page": "350"}
    ]


def test_verify_manual_references_accepts_title_with_page_suffix():
    # 2026-10-26 실제 LLM 테스트로 발견: 프롬프트가 "제목 (p.350)" 형식으로
    # 자료 목록을 보여주면, LLM이 페이지 표시까지 그대로 베껴서 반환할 때가
    # 있다. 제목 완전일치만 허용하면 이런 정상 인용까지 걸러진다.
    pages = _make_pages()
    attached = [pages[0]]

    claimed = ["참고자료3 아동학대 위험수준별 개입 사정 척도 (p.350)"]

    verified = _verify_manual_references(claimed, attached)

    assert [item["id"] for item in verified] == ["risk_scale"]


def test_verify_manual_references_deduplicates():
    pages = _make_pages()
    attached = [pages[0]]

    claimed = [
        "참고자료3 아동학대 위험수준별 개입 사정 척도",
        "참고자료3 아동학대 위험수준별 개입 사정 척도",
    ]

    verified = _verify_manual_references(claimed, attached)

    assert len(verified) == 1


def test_verify_manual_references_handles_malformed_input():
    pages = _make_pages()
    attached = [pages[0]]

    assert _verify_manual_references(None, attached) == []
    assert _verify_manual_references("문자열", attached) == []
    assert _verify_manual_references([{"title": "없는 자료"}], attached) == []


# ------------------------------------------------------------
# 2026-10-27 §6-1(PROPOSAL_law_guide_api.md): 실패를 성공처럼 돌려주지 않는다
# ------------------------------------------------------------


@pytest.fixture
def stub_qa(monkeypatch, tmp_path):
    """torch 없이 answer_legal_manual_question 을 부르게 가리기 · 법령 · 첨부를 가짜로 바꾼다."""

    gateway = types.ModuleType("ai.modeling.abuse.privacy_gateway")
    gateway.mask_for_outbound = lambda text, **kwargs: (text, {})
    masking = types.ModuleType("ai.modeling.abuse.pii_masking")
    masking.restore_pii = lambda value, entity_map: value
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.privacy_gateway", gateway)
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.pii_masking", masking)

    pages = _make_pages()
    for page in pages:
        (tmp_path / page.filename).write_bytes(b"jpg")
    monkeypatch.setattr(legal_manual_qa_llm, "MANUAL_IMAGE_DIR", tmp_path)
    # _select_manual_pages 의 기본 인자(CHAPTER6_PAGES)는 정의 때 묶이므로 함수째 바꾼다.
    select = legal_manual_qa_llm._select_manual_pages
    monkeypatch.setattr(legal_manual_qa_llm, "_select_manual_pages", lambda question: select(question, pages))
    monkeypatch.setattr(legal_manual_qa_llm, "_build_law_corpus", lambda names, **kwargs: ("", []))

    def set_llm(behavior):
        monkeypatch.setattr(legal_manual_qa_llm, "_call_llm_with_retry", behavior)

    return set_llm


def _ask():
    return legal_manual_qa_llm.answer_legal_manual_question(
        client=None, model="test", question="위험수준별 개입사정척도 위험요인은?"
    )


def test_llm_failure_is_raised_not_put_in_answer(stub_qa):
    def fail(**kwargs):
        raise TimeoutError("2차 LLM 호출이 마감 시각을 넘겨 실패: Error code: 401 sk-secret123")

    stub_qa(fail)

    with pytest.raises(TimeoutError) as caught:
        _ask()

    # 종류는 그대로(AI_TIMEOUT), 문구는 고정 · 체인 없음(2026-10-27 민규 교차검증).
    assert str(caught.value) == LLM_TIMEOUT_MESSAGE
    assert caught.value.__cause__ is None


def test_other_llm_failure_becomes_fixed_text_error(stub_qa):
    def fail(**kwargs):
        raise RuntimeError("2차 LLM 호출 실패: Error code: 401 sk-secret123")

    stub_qa(fail)

    with pytest.raises(LawQALLMError) as caught:
        _ask()

    assert str(caught.value) == "법령 질의 LLM 호출 실패(RuntimeError)"
    assert caught.value.__cause__ is None


@pytest.mark.parametrize("parsed", [{}, {"answer": "   "}, "문자열", None])
def test_empty_answer_raises_output_error(stub_qa, parsed):
    stub_qa(lambda **kwargs: parsed)

    with pytest.raises(LawQAOutputError):
        _ask()


def test_manual_images_are_not_sent_by_default(stub_qa):
    """매뉴얼 사진은 기관 대외비라 기본(MANUAL_QA_ATTACH_IMAGES=false)에는 LLM 에 첨부하지 않는다(2026-10-28).
    법령만으로 답하고, LLM 이 매뉴얼을 인용해도 첨부한 자료가 없으니 manual_references 는 비어 있다."""

    assert legal_manual_qa_llm.MANUAL_QA_ATTACH_IMAGES is False
    seen = {}

    def fake_llm(**kwargs):
        seen["user_prompt"] = kwargs["user_prompt"]
        return {
            "answer": "응급조치는 72시간을 넘을 수 없어요.",
            "cited_articles": [],
            "manual_references": ["참고자료3 아동학대 위험수준별 개입 사정 척도"],
        }

    stub_qa(fake_llm)
    result = _ask()

    assert isinstance(seen["user_prompt"], str)  # 이미지 배열이 아니라 글만 보냄
    assert result["manual_references"] == []


def test_success_returns_answer_with_notice_and_page_ids(stub_qa, monkeypatch):
    # 기관 허락을 받아 첨부를 켠 경우.
    monkeypatch.setattr(legal_manual_qa_llm, "MANUAL_QA_ATTACH_IMAGES", True)
    stub_qa(
        lambda **kwargs: {
            "answer": "위험요인 문항은 …",
            "cited_articles": [],
            "manual_references": ["참고자료3 아동학대 위험수준별 개입 사정 척도"],
        }
    )

    result = _ask()

    assert result["answer"].startswith("위험요인 문항은 …")
    assert "참고용" in result["answer"]
    assert result["manual_references"] == [
        {"id": "risk_scale", "title": "참고자료3 아동학대 위험수준별 개입 사정 척도", "page": "350"}
    ]
