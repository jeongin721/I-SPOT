# 화면에 보이는 AI 초안 문장을 거르는 공용 규칙(ai/modeling/abuse/question_rules.py)을 테스트한다.
#
# 2026-10-30 rag/checklist_builder.py 에서 옮겼다. 추가 질문 AI 초안(#118) · AI 확인 메모 · rag 확인 사항이
# 같은 기준을 쓴다(specs followup-rag-checklist 5번). rag 쪽 동작이 그대로인지는 tests/test_rag_followup.py 가 본다.

import pytest

from ai.modeling.abuse.question_rules import judgment_reason, leading_reason, question_term_reason


@pytest.mark.parametrize(
    "text",
    ["학대 확정 사례로 보임", "위험 확정", "AI 판정 결과", "자동 결정", "신체학대로 판단됨", "가해자인 아버지", "처벌 대상"],
)
def test_judgment_reason_catches_definitive_expressions(text):
    assert judgment_reason(text) is not None


@pytest.mark.parametrize(
    "text",
    ["등 통증 이후 치료 여부 확인 필요", "신체학대 관련 신호가 있어 추가 확인 필요", "체크리스트 항목 확인"],
)
def test_judgment_reason_allows_neutral_counselor_text(text):
    assert judgment_reason(text) is None


@pytest.mark.parametrize(
    "text",
    ["어디 아팠지?", "병원에 갔지?", "아빠가 때린 거 맞지?", "그때 무섭지 않았어?", "집에 가기 싫잖아?"],
)
def test_leading_reason_catches_answer_fixed_questions(text):
    assert leading_reason(text) is not None


@pytest.mark.parametrize(
    "text",
    ["그때 이야기를 더 해 줄래?", "그다음엔 어떻게 됐어?", "무서울 때 누구한테 이야기할 수 있어?"],
)
def test_leading_reason_allows_open_questions(text):
    assert leading_reason(text) is None


def test_question_term_reason_blocks_legal_terms_only_in_questions():
    assert question_term_reason("신고해 본 적 있어?") is not None
    assert question_term_reason("학대받은 적 있어?") is not None
    assert question_term_reason("그다음엔 어떻게 됐어?") is None


def test_known_limit_actor_act_question_passes_these_rules():
    # 행위자 · 행위를 먼저 꺼내는 질문은 이 규칙만으로는 못 거른다(#118 의 새 낱말 검사 · rag 의 rule_check 몫).
    assert leading_reason("몇 번 맞았어?") is None
    assert question_term_reason("몇 번 맞았어?") is None
