# 고령자 '추가 질문' 초안(2026-11-17, 아동 followup_question_llm 을 대상만 바꿔 옮김). 데이터는 모두 가상이다.
# 회차 분석 결과 followup_questions 에 담기고, 담당자가 승인하면 18절 저장 API(PUT /sessions/{id}/followup-questions)로 들어간다.

import types

import pytest
from fastapi.testclient import TestClient

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.senior import followup_question_llm as fq  # noqa: E402
from ai.modeling.senior import senior_session_llm as session_llm  # noqa: E402
from app.adapters.senior_ai_adapter import SeniorAIAdapter, set_senior_ai_adapter_override  # noqa: E402
from app.services import senior_service  # noqa: E402
from tests.conftest import create_case, create_session  # noqa: E402
from tests.test_analysis import analyzed_session  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    senior_service.reset_limits()
    set_senior_ai_adapter_override(None)
    yield
    set_senior_ai_adapter_override(None)
    senior_service.reset_limits()


SEGMENTS = [
    {"segment_id": "s1", "speaker": "COUNSELOR", "text": "요즘 어떻게 지내세요?"},
    {"segment_id": "s2", "speaker": "CHILD", "text": "요새 밥맛이 없어서 하루 한 끼 먹어."},
    {"segment_id": "s3", "speaker": "CHILD", "text": "아들이 한 달에 한 번 전화해."},
]


# ---------------------------------------------------------------- 코드 검사


def test_clean_keeps_open_questions_with_evidence() -> None:
    raw = [
        {"text": "밥맛이 없으신 건 언제부터 그러셨어요?", "refs": ["s2"], "reason": "식사를 거르는 기간이 안 나옴"},
        {"text": "아드님과는 주로 무슨 이야기를 나누세요?", "refs": ["s3"], "reason": ""},
    ]
    cleaned = fq._clean_questions(raw, SEGMENTS)
    assert [q["text"] for q in cleaned] == [raw[0]["text"], raw[1]["text"]]
    assert cleaned[0] == {"text": raw[0]["text"], "kind": "OPEN", "segment_ids": ["s2"], "reason": raw[0]["reason"], "bank_code": None}


@pytest.mark.parametrize(
    "text, refs",
    [
        ("밥은 잘 드셨어요?", ["s2"]),  # 닫힌 질문(열린 표지 없음)
        ("딸은 언제 오세요?", ["s2"]),  # 어르신이 말하지 않은 사람
        ("아드님이 때린 적은 언제예요?", ["s3"]),  # 말하지 않은 행위
        ("식사는 언제 하세요? 누구랑 드세요?", ["s2"]),  # 물음 둘
        ("우울증 때문에 입맛이 없는 건 언제부터예요?", ["s2"]),  # 진단 말
        ("학대받으신 건 언제예요?", ["s2"]),  # 판단 용어
        ("요새 밥맛이 없으시죠?", ["s2"]),  # 꼬리 질문
        ("식사는 어떻게 하세요?", []),  # 근거 없음
        ("식사는 어떻게 하세요?", ["s99"]),  # 없는 발화 번호
    ],
)
def test_clean_drops_bad_questions(text: str, refs: list) -> None:
    assert fq._clean_questions([{"text": text, "refs": refs, "reason": ""}], SEGMENTS) == []


def test_clean_drops_judgment_reason_and_caps_count() -> None:
    bad = {"text": "밥맛이 없으신 건 언제부터예요?", "refs": ["s2"], "reason": "우울증 의심"}
    assert fq._clean_questions([bad], SEGMENTS) == []
    many = [{"text": f"하루 한 끼 드시는 건 {n}번째로 언제부터예요?", "refs": ["s2"]} for n in range(8)]
    assert len(fq._clean_questions(many, SEGMENTS)) == fq.MAX_QUESTIONS


def test_bank_sentences_pass_own_checks() -> None:
    for text in fq.DOMAIN_BANK.values():
        assert fq.question_problem(text, "") is None, text


def test_bank_questions_for_not_mentioned_domains() -> None:
    domains = [
        {"domain": "MEAL", "change": "NEW"},
        {"domain": "SLEEP", "change": "NOT_MENTIONED"},
        {"domain": "OUTING", "change": "NOT_MENTIONED"},
        {"domain": "SOCIAL", "change": "NOT_MENTIONED"},
        {"domain": "MOOD", "change": "NOT_MENTIONED"},
    ]
    bank = fq.bank_questions(domains)
    assert [q["bank_code"] for q in bank] == ["SENIOR_SLEEP", "SENIOR_OUTING", "SENIOR_SOCIAL"]  # 셋까지
    assert all(q["kind"] == "BANK" and q["segment_ids"] == [] for q in bank)
    assert bank[0]["reason"] == "이번 방문에 수면 이야기가 나오지 않음"

    llm = [{"text": f"질문 {n} 은 어떠세요?", "kind": "OPEN", "segment_ids": ["s2"], "reason": "", "bank_code": None} for n in range(4)]
    merged = fq.merge_questions(llm, domains)
    assert len(merged) == fq.MAX_QUESTIONS and merged[-1]["bank_code"] == "SENIOR_SLEEP"


# ---------------------------------------------------------------- 회차 분석 → 결과 → 승인 저장


def test_rule_analysis_has_bank_questions_and_saves(client: TestClient, counselor_headers) -> None:
    case = create_case(client, counselor_headers, subject_type="SENIOR", child_alias="어르신_002", child_birth_year=1942)
    session = create_session(client, counselor_headers, case["id"])

    result = analyzed_session(client, counselor_headers, session["id"])["analysis"]["result"]
    drafts = result["followup_questions"]
    missing = [d["domain"] for d in result["senior"]["domain_drafts"] if d["change"] == "NOT_MENTIONED"]
    assert [q["bank_code"] for q in drafts] == [f"SENIOR_{d}" for d in missing][: fq.MAX_BANK_QUESTIONS]

    if drafts:  # 승인 저장은 아동과 같은 18절 API
        body = {"questions": [{"text": drafts[0]["text"], "kind": "BANK", "source": "AI", "segment_ids": [], "bank_code": drafts[0]["bank_code"]}]}
        response = client.put(f"/api/v1/sessions/{session['id']}/followup-questions", json=body, headers=counselor_headers)
        assert response.status_code == 200, response.text
        assert response.json()["data"]["questions"][0]["text"] == drafts[0]["text"]


def test_adapter_passes_ai_questions() -> None:
    raw = session_llm.rule_based_session_summary({"segments": SEGMENTS})
    raw["followup_questions"] = [{"text": "밥맛이 없으신 건 언제부터예요?", "kind": "OPEN", "segment_ids": ["s2"], "reason": "기간", "bank_code": None}]
    bundle = SeniorAIAdapter(provider="rule")._to_bundle(raw, {"segments": SEGMENTS}, "AI")
    assert bundle.result.followup_questions[0].text == "밥맛이 없으신 건 언제부터예요?"


def test_wait_questions_gives_empty_on_failure() -> None:
    """LLM 모드에서 질문 호출이 늦거나 실패해도 요약은 나온다 — 질문만 [] (은행 질문은 그대로 붙는다)."""

    future = types.SimpleNamespace(result=lambda timeout=None: (_ for _ in ()).throw(RuntimeError("늦음")), cancel=lambda: None)
    assert session_llm._wait_questions(future, None) == []
    assert fq.merge_questions([], [{"domain": "MEAL", "change": "NOT_MENTIONED"}])[0]["bank_code"] == "SENIOR_MEAL"
