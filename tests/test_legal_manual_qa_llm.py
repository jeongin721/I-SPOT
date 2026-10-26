# 법령·매뉴얼 AI 질의(ai/modeling/abuse/legal_manual_qa_llm.py)의 매뉴얼
# 페이지 선택·인용 검증 로직을 테스트한다.
#
# 2026-10-26 현직자 인터뷰("I-SPOT 현직자 인터뷰 정리.pdf" §6-2 "법령·
# 매뉴얼 AI 질의")가 요청한 기능을 law_qa_llm.py(법령 전용)에 "2026년
# 아동학대 대응 업무 매뉴얼" 6장(서식·참고자료) 이미지를 결합해 확장한
# 첫 구현이다. 매뉴얼 원본이 텍스트가 아니라 사진이라 law_qa_llm처럼
# 조문 본문과 대조할 수 없고, "이번 호출에 실제로 첨부한 페이지인지"만
# 확인할 수 있다 — _verify_manual_references가 이 역할을 한다.

from ai.modeling.abuse.legal_manual_qa_llm import (
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


def test_verify_manual_references_keeps_only_attached_pages():
    pages = _make_pages()
    attached = [pages[0], pages[1]]  # risk_scale, family_scale만 첨부됐다고 가정

    # LLM이 첨부 안 된 "서식4"까지 지어내 인용한 경우 — 빠져야 한다.
    claimed = [
        "참고자료3 아동학대 위험수준별 개입 사정 척도",
        "서식4 초기면접지(아동용)",
    ]

    verified = _verify_manual_references(claimed, attached)

    assert verified == ["참고자료3 아동학대 위험수준별 개입 사정 척도"]


def test_verify_manual_references_accepts_title_with_page_suffix():
    # 2026-10-26 실제 LLM 테스트로 발견: 프롬프트가 "제목 (p.350)" 형식으로
    # 자료 목록을 보여주면, LLM이 페이지 표시까지 그대로 베껴서 반환할 때가
    # 있다. 제목 완전일치만 허용하면 이런 정상 인용까지 걸러진다.
    pages = _make_pages()
    attached = [pages[0]]

    claimed = ["참고자료3 아동학대 위험수준별 개입 사정 척도 (p.350)"]

    verified = _verify_manual_references(claimed, attached)

    assert verified == ["참고자료3 아동학대 위험수준별 개입 사정 척도"]


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
