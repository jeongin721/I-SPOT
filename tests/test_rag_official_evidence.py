# 공식 근거 붙이기(rag/official_evidence.py)와 Backend 연동 경로(with_questions=False)를 테스트한다.
# '근거가 없는데 공식 근거로 표시'(#117 교차검증 R7) · '검토 안 한 결과가 그대로 보임'(C2)이 생기지 않는지 본다.
# 외부 호출(OpenAI · 벡터 DB · NER)은 하지 않는다. LLM 은 가짜 응답으로 바꾼다.

import pytest

pytest.importorskip("langchain_openai")

import rag.checklist_builder as builder
import rag.official_evidence as official
from rag import pipeline, session
from rag.case_context import build_case_records
from rag.checklist_builder import (
    CheckItemDraft,
    CheckItemDrafts,
    QuestionDrafts,
)
from rag.official_evidence import (
    BasisReview,
    BasisReviews,
    QuestionLink,
    QuestionLinks,
)


class FakeLLM:
    """스키마별로 정해 둔 응답을 차례로 돌려준다. 예외 객체를 넣으면 그 호출에서 던진다."""

    def __init__(self, responses):
        self.responses = {schema: list(items) for schema, items in responses.items()}
        self.prompts = []

    def __call__(self, schema, system_prompt, human_prompt):
        self.prompts.append((schema, human_prompt))
        if schema not in self.responses or not self.responses[schema]:
            raise AssertionError(f"부르지 않아야 할 LLM 호출: {schema.__name__}")
        response = self.responses[schema].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


KNOWLEDGE = [
    {"ref": "manual:1", "type": "manual", "label": "업무 매뉴얼 p.125", "text": "개방형 질문을 먼저 쓴다.",
     "excerpt": "개방형 질문을 먼저 쓴다."},
    {"ref": "checklist:1", "type": "checklist", "label": "체크리스트 p.3", "text": "[needs_confirmation] 상처 치료 여부",
     "excerpt": "상처의 치료 여부"},
    {"ref": "law:1", "type": "law", "label": "아동복지법 제17조", "text": "누구든지 …", "excerpt": "누구든지 …",
     "url": "https://www.law.go.kr/x"},
]

QUESTIONS = [
    {"draft_index": 0, "text": "등이랑 팔이 아팠던 건 지금은 어때?", "reason": "통증 이후 경과"},
    {"draft_index": 1, "text": "무서울 때 누구한테 이야기할 수 있어?", "reason": ""},
    {"draft_index": 3, "text": "학교에서는 어떻게 지내?", "reason": ""},
]


def check_item(item="치료를 받았는지", refs=("checklist:1",)):
    return {"id": "check:1", "item": item, "kind": "info_gap", "priority": "high", "reason": "치료 여부 미확인",
            "case_refs": ["case:1"], "knowledge_refs": list(refs)}


def review(*answers):
    return BasisReviews(reviews=[BasisReview(pair_id=pair_id, supports=supports) for pair_id, supports in answers])


# ---------------------------------------------------------------------------
# attach_official_evidence
# ---------------------------------------------------------------------------


def test_no_candidates_calls_no_llm_and_drops_all_official_refs(monkeypatch):
    fake = FakeLLM({})
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item()]

    result = official.attach_official_evidence(items, QUESTIONS, [])

    assert fake.prompts == []
    assert items[0]["knowledge_refs"] == []
    assert result["question_links"] == []
    assert result["validation"]["official_skipped"]


def test_only_reviewed_pairs_survive_and_code_checks_drop_bad_links(monkeypatch):
    fake = FakeLLM(
        {
            QuestionLinks: [
                QuestionLinks(
                    links=[
                        # Q1: 후보 밖 번호(manual:9)는 빠지고, 남은 두 개 중 검토에서 하나만 통과
                        QuestionLink(question_id=1, knowledge_refs=["manual:1", "manual:9", "checklist:1"],
                                     why="면담 지침과 체크리스트 항목"),
                        # Q2: 이유에 판정 표현 → 연결째 뺀다
                        QuestionLink(question_id=2, knowledge_refs=["manual:1"], why="학대로 확정된 사안이라"),
                        # Q2 두 번째 답 → 같은 질문에 두 번 답했으므로 뺀다
                        QuestionLink(question_id=2, knowledge_refs=["law:1"], why="법령 배경"),
                        # Q3: 이유가 비었다 → 뺀다
                        QuestionLink(question_id=3, knowledge_refs=["law:1"], why=""),
                        # 없는 질문 번호
                        QuestionLink(question_id=7, knowledge_refs=["law:1"], why="법령 배경"),
                    ]
                )
            ],
            # 쌍: P1 확인할 사항-checklist:1, P2 Q1-manual:1, P3 Q1-checklist:1
            BasisReviews: [review((1, True), (2, True), (3, False))],
        }
    )
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item()]

    result = official.attach_official_evidence(items, QUESTIONS, KNOWLEDGE)

    assert items[0]["knowledge_refs"] == ["checklist:1"]
    assert result["question_links"] == [
        {"draft_index": 0, "text": QUESTIONS[0]["text"], "knowledge_refs": ["manual:1"], "why": "면담 지침과 체크리스트 항목"}
    ]
    validation = result["validation"]
    # 뺀 연결: manual:9 · Q2(판정) 1 · Q2 두 번째 1 · Q3(이유 없음) 1 · Q7 1
    assert validation["official_unlinked"] == 5
    assert validation["official_review_rejected"] == 1
    assert validation["question_links"] == 1

    review_prompt = next(prompt for schema, prompt in fake.prompts if schema is BasisReviews)
    assert "[P3] 질문: 등이랑 팔이 아팠던 건 지금은 어때?" in review_prompt
    assert "연결 이유: 면담 지침과 체크리스트 항목" in review_prompt


def test_review_failure_drops_every_official_ref(monkeypatch):
    fake = FakeLLM(
        {
            QuestionLinks: [QuestionLinks(links=[QuestionLink(question_id=1, knowledge_refs=["manual:1"], why="면담 지침")])],
            BasisReviews: [RuntimeError("timeout")],
        }
    )
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item()]

    result = official.attach_official_evidence(items, QUESTIONS, KNOWLEDGE)

    assert items[0]["knowledge_refs"] == []
    assert result["question_links"] == []
    assert result["validation"]["official_review_error"] == "공식 근거 검토 실패: RuntimeError"


@pytest.mark.parametrize(
    "answers",
    [
        [],  # 답 누락
        [(1, True), (1, False)],  # 같은 쌍에 두 번(엇갈림)
        [(1, True), (1, True)],  # 같은 쌍에 두 번(같아도 하나로 보지 않는다)
        [(2, True)],  # 없는 쌍 번호
    ],
)
def test_missing_or_duplicate_review_answers_count_as_no(monkeypatch, answers):
    fake = FakeLLM({BasisReviews: [review(*answers)]})
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item()]

    result = official.attach_official_evidence(items, [], KNOWLEDGE)

    assert items[0]["knowledge_refs"] == []
    assert result["validation"]["official_review_rejected"] == 1


def test_link_failure_keeps_reviewing_check_items(monkeypatch):
    fake = FakeLLM({QuestionLinks: [RuntimeError("timeout")], BasisReviews: [review((1, True))]})
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item()]

    result = official.attach_official_evidence(items, QUESTIONS, KNOWLEDGE)

    assert items[0]["knowledge_refs"] == ["checklist:1"]
    assert result["question_links"] == []
    assert result["validation"]["question_link_error"] == "질문 공식 근거 연결 실패: RuntimeError"


def test_no_pairs_skips_review(monkeypatch):
    fake = FakeLLM({QuestionLinks: [QuestionLinks(links=[QuestionLink(question_id=1, knowledge_refs=[], why="")])]})
    monkeypatch.setattr(official, "_invoke", fake)
    items = [check_item(refs=())]

    result = official.attach_official_evidence(items, QUESTIONS, KNOWLEDGE)

    assert [schema for schema, _ in fake.prompts] == [QuestionLinks]
    assert result["question_links"] == []


# ---------------------------------------------------------------------------
# build_next_session_checklist(with_questions=False)
# ---------------------------------------------------------------------------


def make_records():
    transcript = {
        "segments": [
            {"segment_id": "seg_1", "speaker": "CHILD", "start_ms": 3_000, "text": "아빠가 때렸어요."},
            {"segment_id": "seg_2", "speaker": "CHILD", "start_ms": 68_000, "text": "등이랑 팔이 아파요."},
        ]
    }
    return build_case_records(transcript, session_no=8, session_id="sess-8")


CHECKLIST_RESULTS = [{"status": "needs_confirmation", "item": "상처의 치료 여부", "source": "체크리스트.pdf", "page": 3}]
GUIDANCE = [
    {
        "content": "아동 면담 시 개방형 질문을 먼저 사용한다.",
        "metadata": {"source": "업무 매뉴얼.pdf", "page": 125, "screen_section": "상담·조사·사정", "chunk_id": "m1"},
    }
]


@pytest.fixture
def guidance_only(monkeypatch):
    monkeypatch.setattr(builder, "search_evidence", lambda query, **kwargs: GUIDANCE)


def test_backend_path_never_generates_questions_and_keeps_only_reviewed_official_basis(monkeypatch, guidance_only):
    records = make_records()
    pain = next(record["ref"] for record in records if record["label"] == "8회차 01:08")
    builder_fake = FakeLLM(
        {
            CheckItemDrafts: [
                CheckItemDrafts(
                    items=[
                        CheckItemDraft(item="치료를 받았는지", kind="info_gap", priority="high", reason="치료 여부 미확인",
                                       case_refs=[pain], knowledge_refs=["checklist:1", "manual:1"]),
                    ]
                )
            ],
            # QuestionDrafts 는 넣지 않는다 — 부르면 FakeLLM 이 실패시킨다.
        }
    )
    official_fake = FakeLLM(
        {
            QuestionLinks: [QuestionLinks(links=[QuestionLink(question_id=1, knowledge_refs=["manual:1"], why="면담 지침")])],
            # 쌍: P1 확인-checklist:1 · P2 확인-manual:1(면담 지침) · P3 질문-manual:1
            BasisReviews: [review((1, True), (2, False), (3, True))],
        }
    )
    monkeypatch.setattr(builder, "_invoke", builder_fake)
    monkeypatch.setattr(official, "_invoke", official_fake)

    result = builder.build_next_session_checklist(
        records,
        CHECKLIST_RESULTS,
        [],
        with_questions=False,
        link_questions=[{"draft_index": 2, "text": "등이랑 팔이 아팠던 건 지금은 어때?", "reason": ""}],
    )

    assert QuestionDrafts not in [schema for schema, _ in builder_fake.prompts]
    assert result["items"] == []

    item = result["check_items"][0]
    assert item["knowledge_refs"] == ["checklist:1"]
    assert [(basis["type"], basis.get("segment_id")) for basis in item["basis"]] == [("case", "seg_2"), ("checklist", None)]

    assert result["question_evidence"] == [
        {
            "draft_index": 2,
            "knowledge_refs": ["manual:1"],
            "basis": [
                {
                    "ref": "manual:1",
                    "type": "manual",
                    "label": "업무 매뉴얼.pdf · 상담·조사·사정 p.125",
                    "source": "업무 매뉴얼.pdf",
                    "page": 125,
                    "chunk_id": "m1",
                    "excerpt": "아동 면담 시 개방형 질문을 먼저 사용한다.",
                    "why": "면담 지침",
                }
            ],
        }
    ]

    # 저장될 결과 전체에서 공식 근거(type ≠ case)는 모두 검토 '예' 를 받은 쌍이다.
    approved = {("check", "checklist:1"), ("question", "manual:1")}
    shown = {("check", basis["ref"]) for basis in item["basis"] if basis["type"] != "case"}
    shown |= {("question", basis["ref"]) for entry in result["question_evidence"] for basis in entry["basis"]}
    assert shown == approved


def test_backend_path_reports_extraction_failure_without_further_calls(monkeypatch, guidance_only):
    builder_fake = FakeLLM({CheckItemDrafts: [RuntimeError("timeout")]})
    official_fake = FakeLLM({})
    monkeypatch.setattr(builder, "_invoke", builder_fake)
    monkeypatch.setattr(official, "_invoke", official_fake)

    result = builder.build_next_session_checklist(
        make_records(), CHECKLIST_RESULTS, [], with_questions=False,
        link_questions=[{"draft_index": 0, "text": "지금은 어때?", "reason": ""}],
    )

    assert result == {
        "check_items": [],
        "items": [],
        "question_evidence": [],
        "validation": {"check_error": "확인할 사항 추출 실패: RuntimeError"},
    }
    assert official_fake.prompts == []


def test_backend_path_without_records_returns_empty_question_evidence():
    assert builder.build_next_session_checklist([], CHECKLIST_RESULTS, [], with_questions=False) == {
        "check_items": [],
        "items": [],
        "question_evidence": [],
        "validation": {},
    }


# ---------------------------------------------------------------------------
# pipeline 비식별 · session 플래그
# ---------------------------------------------------------------------------


def fake_restore(value, entity_map):
    if isinstance(value, dict):
        return {key: fake_restore(sub, entity_map) for key, sub in value.items()}
    if isinstance(value, list):
        return [fake_restore(item, entity_map) for item in value]
    if isinstance(value, str):
        for token, original in entity_map.items():
            value = value.replace(token, original)
    return value


def test_questions_are_masked_with_the_same_tokens_as_case_records(monkeypatch):
    payloads = []

    def fake_mask(payload, known_identifiers=None):
        payloads.append(payload)

        def mask(value):
            if isinstance(value, dict):
                return {key: mask(sub) for key, sub in value.items()}
            if isinstance(value, list):
                return [mask(item) for item in value]
            return value.replace("민수", "[PERSON_01]") if isinstance(value, str) else value

        return mask(payload), {"[PERSON_01]": "민수"}

    captured = {}

    def fake_analyze(text, abuse_type, **kwargs):
        captured.update(kwargs)
        return {"next_session_checklist": {"question_evidence": [{"draft_index": 0, "basis": [{"why": "[PERSON_01] 관련"}]}]}}

    monkeypatch.setattr(pipeline, "mask_payload", fake_mask)
    monkeypatch.setattr(pipeline, "_analyze_masked", fake_analyze)
    monkeypatch.setattr(pipeline, "restore", fake_restore)

    questions = [{"draft_index": 0, "text": "민수랑 있을 때는 어때?", "reason": "민수 언급"}]
    result = pipeline.analyze_consultation_evidence(
        "민수가 때렸어요",
        "physical",
        case_records=[{"ref": "case:1", "current": True, "label": "8회차 00:03", "text": "민수가 때렸어요"}],
        with_questions=False,
        link_questions=questions,
    )

    assert len(payloads) == 1  # 상담 문장 · 기록 · 질문을 한 번에 가린다(토큰 일치)
    assert captured["with_questions"] is False
    assert captured["link_questions"] == [{"draft_index": 0, "text": "[PERSON_01]랑 있을 때는 어때?", "reason": "[PERSON_01] 언급"}]
    assert questions[0]["text"] == "민수랑 있을 때는 어때?"  # 넘겨받은 원본은 바꾸지 않는다
    assert result["next_session_checklist"]["question_evidence"][0]["basis"][0]["why"] == "민수 관련"
    assert "question_link_warning" not in result


def test_question_only_block_retries_without_questions(monkeypatch):
    from rag.privacy import RagPrivacyBlocked

    calls = []

    def fake_mask(payload, known_identifiers=None):
        calls.append(sorted(payload))
        if "questions" in payload:
            raise RagPrivacyBlocked(["questions[0].text: NER 개체 잔존(PS)"])
        return payload, {}

    captured = {}

    def fake_analyze(text, abuse_type, **kwargs):
        captured.update(kwargs)
        return {}

    monkeypatch.setattr(pipeline, "mask_payload", fake_mask)
    monkeypatch.setattr(pipeline, "_analyze_masked", fake_analyze)
    monkeypatch.setattr(pipeline, "restore", lambda value, entity_map: value)

    records = [
        {"ref": "case:1", "current": True, "label": "8회차 00:03", "text": "등이 아파요"},
        {"ref": "case:2", "current": False, "label": "7회차 상담 요약", "text": "학교 이야기"},
    ]
    result = pipeline.analyze_consultation_evidence(
        "등이 아파요", "physical", case_records=records, with_questions=False,
        link_questions=[{"draft_index": 0, "text": "박○○ 선생님이랑은 어때?", "reason": ""}],
    )

    assert calls == [["case", "questions", "text"], ["case", "text"]]
    assert captured["link_questions"] == []
    assert [record["ref"] for record in captured["case_records"]] == ["case:1", "case:2"]  # 기록은 그대로
    assert "공식 근거를 붙이지 않았습니다" in result["question_link_warning"]
    assert "case_context_warning" not in result


def test_session_flags_skip_manual_references_and_pass_questions(monkeypatch):
    captured = {}

    def fake_analyze(**kwargs):
        captured.update(kwargs)
        return {"next_session_checklist": {"check_items": [], "items": [], "question_evidence": []}}

    monkeypatch.setattr(session, "analyze_consultation_evidence", fake_analyze)
    monkeypatch.setattr(session, "build_screen_references", lambda *a, **k: pytest.fail("매뉴얼 화면 근거를 부르지 않는다"))

    questions = [{"draft_index": 0, "text": "지금은 어때?", "reason": ""}]
    result = session.analyze_reviewed_transcript(
        {"segments": [{"segment_id": "seg_1", "speaker": "CHILD", "start_ms": 0, "text": "등이 아파요."}]},
        "physical",
        session_no=8,
        with_questions=False,
        with_manual_references=False,
        link_questions=questions,
    )

    assert captured["with_questions"] is False
    assert captured["link_questions"] == questions
    assert result["manual_screen_references"] is None
    assert result["privacy_blocked"] is False
