# 고령자 생활 · 정서 영역 변화(API_CONTRACT 27절, 2026-11-16) — 식사 · 수면 · 외출 · 사회활동 · 정서.
# 회차 분석이 다섯 영역 초안을 만들고, 담당자가 확정하면 다음 회차가 그 기록과 견준다. 데이터는 모두 가상이다.

import sys
import types

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from ai.modeling.senior import care_domains  # noqa: E402
from ai.modeling.senior import senior_session_llm as session_llm  # noqa: E402
from app.adapters.senior_ai_adapter import set_senior_ai_adapter_override  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.enums import AuditAction  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402
from app.services import senior_service  # noqa: E402
from tests.conftest import create_case, create_session  # noqa: E402
from tests.test_analysis import analyzed_session  # noqa: E402

ORDER = ["MEAL", "SLEEP", "OUTING", "SOCIAL", "MOOD"]


@pytest.fixture(autouse=True)
def _clean():
    senior_service.reset_limits()
    set_senior_ai_adapter_override(None)
    yield
    set_senior_ai_adapter_override(None)
    senior_service.reset_limits()


def _senior(client: TestClient, headers) -> dict:
    return create_case(client, headers, subject_type="SENIOR", child_alias="어르신_001", child_birth_year=1944)


def _url(session_id: str) -> str:
    return f"/api/v1/sessions/{session_id}/care-domains"


def _save(client: TestClient, headers, session_id: str, items: list, status: int = 200) -> dict:
    response = client.put(_url(session_id), json={"items": items}, headers=headers)
    assert response.status_code == status, response.text
    return response.json()


# ---------------------------------------------------------------- 회차 분석 → 초안 → 확정 → 다음 회차 비교


def test_rule_drafts_confirm_and_compare_with_next_session(client: TestClient, counselor_headers, db) -> None:
    case = _senior(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])

    analysis = analyzed_session(client, counselor_headers, first["id"])["analysis"]
    drafts = analysis["result"]["senior"]["domain_drafts"]
    assert [d["domain"] for d in drafts] == ORDER
    mood = drafts[4]
    # 가짜 STT 의 seg_004 '그냥 그래요. 조금 힘든 날도 있어요.' — 정서 낱말. 앞 기록이 없으니 NEW.
    assert mood == {
        "domain": "MOOD",
        "text": "그냥 그래요. 조금 힘든 날도 있어요.",
        "change": "NEW",
        "change_note": None,
        "segment_ids": ["seg_004"],
        "source": "RULE",
    }
    assert drafts[0]["change"] == "NOT_MENTIONED" and drafts[0]["text"] is None

    view = client.get(_url(first["id"]), headers=counselor_headers).json()["data"]
    assert [row["label"] for row in view["domains"]] == ["식사", "수면", "외출", "사회활동", "정서"]
    assert view["confirmed"] is False and view["domains"][4]["draft"]["segment_ids"] == ["seg_004"]
    assert all(row["previous"] is None and row["saved"] is None for row in view["domains"])

    saved = _save(
        client,
        counselor_headers,
        first["id"],
        [
            {"domain": "MEAL", "change": "NEW", "text": "하루 두 끼, 혼자 드심", "origin": "COUNSELOR"},
            {"domain": "SLEEP", "change": "NOT_MENTIONED", "text": "버림", "segment_ids": ["seg_004"]},
            {"domain": "OUTING", "change": "NEW", "text": "매일 아침 동네 산책"},
            {"domain": "SOCIAL", "change": "NOT_MENTIONED"},
            {"domain": "MOOD", "change": "NEW", "text": "힘든 날도 있다고 하심", "segment_ids": ["seg_004"], "origin": "RULE", "edited": True},
        ],
    )["data"]
    assert saved["confirmed"] is True
    sleep = saved["domains"][1]["saved"]
    assert sleep["text"] is None and sleep["segment_ids"] == [] and sleep["compared_session_id"] is None
    assert saved["domains"][4]["saved"]["origin"] == "RULE" and saved["domains"][4]["saved"]["edited"] is True

    audit = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.CARE_DOMAINS_SAVED)).all()
    assert len(audit) == 1
    assert audit[0].detail["changes"] == {"NEW": 3, "NOT_MENTIONED": 2} and audit[0].detail["edited"] == 1
    assert "산책" not in str(audit[0].detail)  # 값은 감사 기록에 남기지 않는다

    # 둘째 회차: 분석 입력에 앞 기록이 들어가고, 화면은 앞 기록과 나란히 본다.
    second = create_session(client, counselor_headers, case["id"])
    drafts2 = analyzed_session(client, counselor_headers, second["id"])["analysis"]["result"]["senior"]["domain_drafts"]
    assert drafts2[4]["change"] is None  # 앞 기록이 있으면 규칙은 같은지 판단하지 않는다(담당자가 견줌)

    view2 = client.get(_url(second["id"]), headers=counselor_headers).json()["data"]
    outing = view2["domains"][2]
    assert outing["previous"]["session_number"] == first["session_number"] and outing["previous"]["text"] == "매일 아침 동네 산책"
    assert view2["domains"][1]["previous"] is None  # 수면은 이야기 없음만 있었다
    assert view2["domains"][3]["previous"] is None

    # 앞 기록이 있으면 NEW 불가, 없으면 SIMILAR · CHANGED 불가
    bad = _save(client, counselor_headers, second["id"], [{"domain": "OUTING", "change": "NEW", "text": "x"}], 400)
    assert "앞 기록이 있어" in bad["error"]["message"]
    bad = _save(client, counselor_headers, second["id"], [{"domain": "SLEEP", "change": "SIMILAR", "text": "x"}], 400)
    assert "처음 기록" in bad["error"]["message"]

    _save(
        client,
        counselor_headers,
        second["id"],
        [
            {"domain": "OUTING", "change": "CHANGED", "text": "요즘은 거의 안 나가심", "change_note": "매일 산책 → 거의 안 나감"},
            {"domain": "MEAL", "change": "SIMILAR", "text": "두 끼 드심", "change_note": "버림"},
        ],
    )
    view2 = client.get(_url(second["id"]), headers=counselor_headers).json()["data"]
    outing = view2["domains"][2]["saved"]
    assert outing["change_note"] == "매일 산책 → 거의 안 나감" and outing["compared_session_id"] == first["id"]
    assert view2["domains"][0]["saved"]["change_note"] is None  # SIMILAR 는 변화 글을 두지 않는다
    assert view2["confirmed"] is False  # 다섯 영역 중 둘만

    # 같은 영역 다시 보내면 덮어쓴다
    _save(client, counselor_headers, second["id"], [{"domain": "OUTING", "change": "SIMILAR", "text": "가끔 나가심"}])
    outing = client.get(_url(second["id"]), headers=counselor_headers).json()["data"]["domains"][2]["saved"]
    assert outing["change"] == "SIMILAR" and outing["change_note"] is None

    # 이력 비교 화면
    timeline = client.get(f"/api/v1/cases/{case['id']}/care-domains", headers=counselor_headers).json()["data"]
    assert [d["domain"] for d in timeline["domains"]] == ORDER
    assert [(e["session_number"], e["change"]) for e in timeline["domains"][2]["entries"]] == [
        (first["session_number"], "NEW"),
        (second["session_number"], "SIMILAR"),
    ]

    # 상담 이력에도 회차별로 붙는다
    history = client.get(f"/api/v1/cases/{case['id']}/senior-history", headers=counselor_headers).json()["data"]
    by_session = {e["session_id"]: e for e in history["entries"] if e["kind"] == "VISIT"}
    assert [n["domain"] for n in by_session[first["id"]]["care_domains"]] == ORDER
    assert [n["domain"] for n in by_session[second["id"]]["care_domains"]] == ["MEAL", "OUTING"]


def test_previous_skips_not_mentioned_and_later_sessions(client: TestClient, counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])
    third = create_session(client, counselor_headers, case["id"])

    _save(client, counselor_headers, first["id"], [{"domain": "SLEEP", "change": "NEW", "text": "밤에 자주 깨심"}])
    _save(client, counselor_headers, second["id"], [{"domain": "SLEEP", "change": "NOT_MENTIONED"}])

    # 셋째는 이야기 없던 둘째를 건너뛰고 첫째와 견준다
    row = client.get(_url(third["id"]), headers=counselor_headers).json()["data"]["domains"][1]
    assert row["previous"]["session_id"] == first["id"]
    # 첫째는 뒤 회차 기록과 견주지 않는다
    assert client.get(_url(first["id"]), headers=counselor_headers).json()["data"]["domains"][1]["previous"] is None


def test_validation_and_access(client: TestClient, counselor_headers, other_counselor_headers) -> None:
    case = _senior(client, counselor_headers)
    session = create_session(client, counselor_headers, case["id"])

    # 녹취가 없는데 근거 발화를 달면 400
    bad = _save(client, counselor_headers, session["id"], [{"domain": "MEAL", "change": "NEW", "text": "x", "segment_ids": ["seg_001"]}], 400)
    assert "녹취에 없는" in bad["error"]["message"]
    # 이야기 있던 영역은 글이 있어야
    _save(client, counselor_headers, session["id"], [{"domain": "MEAL", "change": "NEW", "text": "  "}], 422)
    # 같은 영역 두 번 · 빈 목록 · 모르는 영역
    _save(client, counselor_headers, session["id"], [{"domain": "MEAL", "change": "NOT_MENTIONED"}] * 2, 422)
    _save(client, counselor_headers, session["id"], [], 422)
    _save(client, counselor_headers, session["id"], [{"domain": "TOILET", "change": "NOT_MENTIONED"}], 422)

    assert client.get(_url(session["id"]), headers=other_counselor_headers).status_code == 403
    assert client.get(f"/api/v1/cases/{case['id']}/care-domains", headers=other_counselor_headers).status_code == 403

    child = create_case(client, counselor_headers)
    child_session = create_session(client, counselor_headers, child["id"])
    assert client.get(_url(child_session["id"]), headers=counselor_headers).status_code == 409
    assert client.get(f"/api/v1/cases/{child['id']}/care-domains", headers=counselor_headers).status_code == 409


# ---------------------------------------------------------------- modeling 경로(가짜 모듈)


def test_modeling_passes_previous_domains_and_keeps_ai_drafts(client: TestClient, counselor_headers, monkeypatch) -> None:
    calls = []
    module = types.ModuleType("ai.modeling.senior.senior_session_llm")

    def summarize_senior_session(data, known_identifiers=None, deadline=None):
        calls.append(data)
        return {
            "overview": "AI 통합 요약",
            "key_points": [{"text": "힘든 날도 있다고 하심", "basis": [{"kind": "SEGMENT", "segment_ids": ["seg_004"]}]}],
            "check_points": [],
            "safety_mentions": [],
            "domains": care_domains.clean_domains(
                [{"domain": "OUTING", "text": "요즘 거의 안 나가신다고 하심", "change": "CHANGED", "change_note": "매일 산책 → 거의 안 나감", "refs": ["seg_004"]}],
                data,
                {"seg_004"},
            ),
            "model": "fake-senior",
        }

    module.summarize_senior_session = summarize_senior_session
    module.rule_based_session_summary = session_llm.rule_based_session_summary
    monkeypatch.setitem(sys.modules, "ai.modeling.senior.senior_session_llm", module)
    monkeypatch.setattr(settings, "SENIOR_AI_PROVIDER", "modeling")

    case = _senior(client, counselor_headers)
    first = create_session(client, counselor_headers, case["id"])
    _save(client, counselor_headers, first["id"], [{"domain": "OUTING", "change": "NEW", "text": "매일 아침 산책"}])
    second = create_session(client, counselor_headers, case["id"])

    drafts = analyzed_session(client, counselor_headers, second["id"])["analysis"]["result"]["senior"]["domain_drafts"]

    assert calls[0]["previous_domains"] == [
        {"domain": "OUTING", "text": "매일 아침 산책", "session_number": first["session_number"], "date": calls[0]["previous_domains"][0]["date"]}
    ]
    assert drafts[2]["source"] == "AI" and drafts[2]["change"] == "CHANGED"
    assert drafts[2]["change_note"] == "매일 산책 → 거의 안 나감"
    # 빠진 영역은 규칙으로 채운다
    assert drafts[4]["source"] == "RULE" and drafts[4]["segment_ids"] == ["seg_004"]


# ---------------------------------------------------------------- 모듈 단위


SEGMENTS = [
    {"segment_id": "s1", "speaker": "COUNSELOR", "text": "식사는 잘 하세요? 밤에 잠은 잘 주무세요?"},  # 담당자 말은 안 본다
    {"segment_id": "s2", "speaker": "CHILD", "text": "입맛이 없어서 하루 한 끼 먹어."},
    {"segment_id": "s3", "speaker": "CHILD", "text": "밤에 두세 번은 깨."},
    {"segment_id": "s4", "speaker": "CHILD", "text": "경로당은 요즘 안 가. 다리가 아파서 집에만 있어."},
    {"segment_id": "s5", "speaker": "CHILD", "text": "혼자 있으니 좀 외롭지."},
]


def test_rule_domains_pick_client_utterances() -> None:
    drafts = care_domains.rule_based_domains({"segments": SEGMENTS, "previous_domains": [{"domain": "MEAL", "text": "세 끼", "session_number": 1}]})

    by = {d["domain"]: d for d in drafts}
    assert [d["domain"] for d in drafts] == ORDER
    assert by["MEAL"]["segment_ids"] == ["s2"] and by["MEAL"]["change"] is None  # 앞 기록 있음 → 담당자가 견줌
    assert by["SLEEP"]["segment_ids"] == ["s3"] and by["SLEEP"]["change"] == "NEW"
    assert by["OUTING"]["segment_ids"] == ["s4"]
    assert by["SOCIAL"]["segment_ids"] == ["s4"]
    assert by["MOOD"]["segment_ids"] == ["s5"]


def test_clean_domains_rules() -> None:
    data = {"segments": SEGMENTS, "previous_domains": [{"domain": "MEAL", "text": "세 끼", "session_number": 1}]}
    raw = [
        {"domain": "MEAL", "text": "하루 한 끼 드신다고 하심", "change": "CHANGED", "change_note": "세 끼 → 한 끼, 우울 의심", "refs": ["s2", "s99"]},
        {"domain": "SLEEP", "text": "밤에 두세 번 깨신다고 하심", "change": "SIMILAR", "refs": ["s3"]},  # 앞 기록 없음 → NEW
        {"domain": "OUTING", "text": "치매 증상으로 보임", "change": "CHANGED", "refs": ["s4"]},  # 금지 말 → 규칙으로
        {"domain": "SOCIAL", "text": "경로당에 안 가심", "change": "NEW", "refs": []},  # 근거 없음 → 규칙으로
        {"domain": "MOOD", "change": "NOT_MENTIONED", "text": "무시", "refs": ["s5"]},
        {"domain": "MEAL", "text": "두 번째는 무시", "change": "SIMILAR", "refs": ["s2"]},
        "x",
    ]

    cleaned = {d["domain"]: d for d in care_domains.clean_domains(raw, data, {"s1", "s2", "s3", "s4", "s5"})}

    assert cleaned["MEAL"] == {
        "domain": "MEAL", "text": "하루 한 끼 드신다고 하심", "change": "CHANGED", "change_note": None,  # 판정 낱말 든 변화 글은 버림
        "segment_ids": ["s2"], "source": "AI",
    }
    assert cleaned["SLEEP"]["change"] == "NEW" and cleaned["SLEEP"]["source"] == "AI"
    assert cleaned["OUTING"]["source"] == "RULE" and cleaned["SOCIAL"]["source"] == "RULE"
    assert cleaned["MOOD"] == {"domain": "MOOD", "text": None, "change": "NOT_MENTIONED", "change_note": None, "segment_ids": [], "source": "AI"}

    # 앞 기록이 있는데 NEW 라고 하면 담당자가 견주게 비운다
    again = care_domains.clean_domains([{"domain": "MEAL", "text": "한 끼 드심", "change": "NEW", "refs": ["s2"]}], data, {"s2"})
    assert again[0]["change"] is None


def test_prompt_lists_previous_records() -> None:
    section = care_domains.prompt_section({"previous_domains": [{"domain": "OUTING", "text": "매일 산책", "session_number": 2, "date": "2026-11-10"}]})
    assert "외출(OUTING), 2회차 2026-11-10: 매일 산책" in section
    assert "식사(MEAL): 앞 기록 없음" in section
    assert "{" not in care_domains.PROMPT_SECTION.replace("{previous}", "").replace("{max_text}", "").replace("{max_note}", "")
    # 프롬프트 전체 format 이 깨지지 않는다
    session_llm.SYSTEM_PROMPT.format(
        max_overview=1, max_points=1, max_checks=1, max_chars=1, visit="", history="", transcript="",
        domains_output=care_domains.PROMPT_OUTPUT, domains_section=section,
    )
