# 다음 상담 체크리스트(확인할 사항 · 추가 질문) 생성을 테스트한다.
# 외부 호출(OpenAI · 벡터 DB · NER)은 하지 않는다. LLM 은 가짜 응답으로 바꾼다.

import pytest

import rag.checklist_builder as builder
import rag.pipeline as pipeline
import rag.session as session
from rag.case_context import build_case_records, format_time, speaker_check_items
from rag.checklist_builder import (
    CheckItemDraft,
    CheckItemDrafts,
    QuestionDraft,
    QuestionDrafts,
    QuestionReview,
    QuestionReviews,
    rule_check,
)


def make_transcript():
    return {
        "segments": [
            {"segment_id": "seg_2", "speaker": "CHILD", "start_ms": 68_000, "text": "등이랑 팔이 아파요."},
            {"segment_id": "seg_1", "speaker": "CHILD", "start_ms": 3_000, "text": "아빠가 때렸어요."},
            {"segment_id": "seg_3", "speaker": "GUARDIAN", "start_ms": 90_000, "text": "애가 거짓말하는 거예요."},
            {"segment_id": "seg_4", "speaker": "UNKNOWN", "start_ms": 135_000, "text": "밥도 안 줄 때가 있어요."},
            {"segment_id": "seg_5", "speaker": "CHILD", "start_ms": 160_000, "text": "할머니한테는 아직 전화 안 했어요."},
        ]
    }


def make_previous_sessions():
    return [
        {"session_no": 5, "summary": "오래된 회차"},
        {"session_no": 6, "summary": "6회차 요약"},
        {
            "session_no": 7,
            "summary": "아동이 학교 생활을 이야기함",
            "safety_plan": "위험할 때 할머니에게 연락하기로 함",
            "check_items": [
                {"item": "등 통증이 있었는지", "status": "confirmed"},
                {"item": "할머니 연락처를 아는지", "status": "open", "note": "다음 회차에 확인"},
            ],
            "transcript": {
                "segments": [
                    {"segment_id": "p1", "speaker": "CHILD", "start_ms": 10_000, "text": "집에 가기 싫어요."},
                    {"segment_id": "p2", "speaker": "GUARDIAN", "start_ms": 20_000, "text": "괜찮아요."},
                ]
            },
        },
        {"session_no": 4, "summary": "가장 오래된 회차"},
    ]


def make_app_responses():
    return [
        {"response_id": "r1", "question": "요즘 기분은 어때?", "answer": "조금 무서워요", "answered_at": "2026-10-07"},
        {"response_id": "r2", "question": "잠은 잘 잤어?", "answer": "", "answered_at": "2026-10-08"},
    ]


# ---------------------------------------------------------------------------
# 사례 기록
# ---------------------------------------------------------------------------


def test_case_records_use_child_speech_previous_sessions_and_app_responses():
    records = build_case_records(
        make_transcript(),
        session_no=8,
        previous_sessions=make_previous_sessions(),
        child_app_responses=make_app_responses(),
    )

    assert [record["ref"] for record in records] == [f"case:{index}" for index in range(1, len(records) + 1)]

    current = [record for record in records if record["current"]]
    assert [record["label"] for record in current] == ["8회차 00:03", "8회차 01:08", "8회차 02:40"]
    assert all("거짓말" not in record["text"] and "밥도" not in record["text"] for record in records)

    previous_labels = [record["label"] for record in records if not record["current"] and record["source"] != "app_response"]
    # 최근 3개 회차(7 · 6 · 5)만, 최근 회차부터. 4회차는 빠진다.
    assert previous_labels == [
        "7회차 상담 요약",
        "7회차 안전 계획",
        "7회차 확인 사항",
        "7회차 확인 사항",
        "7회차 00:10",
        "6회차 상담 요약",
        "5회차 상담 요약",
    ]
    check_items = [record for record in records if record["source"] == "check_item"]
    assert [record["status"] for record in check_items] == ["confirmed", "open"]
    assert check_items[1]["text"] == "할머니 연락처를 아는지 — 다음 회차에 확인"
    assert not any(record["text"] == "괜찮아요." for record in records)

    app = [record for record in records if record["source"] == "app_response"]
    assert len(app) == 1  # 답이 빈 응답은 뺀다
    assert app[0]["label"] == "10/7 아이 앱 응답"
    assert app[0]["text"] == "질문: 요즘 기분은 어때? / 답: 조금 무서워요"


def test_format_time():
    assert format_time(68_000) == "01:08"
    assert format_time(3_723_000) == "1:02:03"
    assert format_time(None) == "00:00"


def test_speaker_check_items_never_carry_utterance_text():
    items = speaker_check_items(make_transcript(), session_no=8)

    assert len(items) == 1
    item = items[0]
    assert item["item"] == "02:15 발화의 화자"
    assert item["basis"][0]["label"] == "8회차 02:15 · 화자 불확실"
    assert item["basis"][0]["segment_id"] == "seg_4"
    assert "밥" not in str(item)


# ---------------------------------------------------------------------------
# 규칙 검증
# ---------------------------------------------------------------------------


def counselor(question):
    return {"question": question, "audience": "counselor"}


def child_app(question):
    return {"question": question, "audience": "child_app"}


@pytest.mark.parametrize(
    "question",
    [
        "아빠가 때렸지?",
        "그때 많이 아팠죠?",
        "병원에 가지 않았어?",
        "그건 학대라고 생각해?",
        "누가 신고했는지 알아?",
    ],
)
def test_rule_check_rejects_leading_and_judgmental_questions(question):
    assert rule_check(counselor(question), "아빠가 때렸어요.") is not None


def test_rule_check_allows_child_words_but_not_new_actor_or_act():
    cited = "아빠가 때렸어요. 등이랑 팔이 아파요."

    # 아동이 말한 행위자 · 행위를 활용형만 바꿔 되묻는 것은 허용
    assert rule_check(counselor("아빠가 때렸을 때 이야기를 더 해 줄래?"), cited) is None
    assert rule_check(counselor("등이랑 팔이 아픈 건 지금은 어때?"), cited) is None
    # 아동이 말하지 않은 행위자
    assert rule_check(counselor("엄마가 때렸을 때는 어땠어?"), cited) is not None
    # 아동이 말하지 않은 행위
    assert rule_check(counselor("아빠가 만졌을 때는 어땠어?"), cited) is not None
    # 비식별 토큰도 행위자로 본다
    assert rule_check(counselor("[PERSON_01]이 때렸을 때 어디 있었어?"), cited) is not None
    assert rule_check(counselor("[PERSON_01]이 때렸을 때 어디 있었어?"), "[PERSON_01]이 때렸어요") is None


def test_rule_check_child_app_questions_are_short_and_never_ask_about_acts():
    assert rule_check(child_app("요즘 몸이 아픈 곳이 있어?"), "") is None
    assert rule_check(child_app("요즘 누가 때린 적 있어?"), "") is not None
    assert rule_check(child_app("요즘 " + "아주 " * 20 + "기분은 어때?"), "") is not None


# ---------------------------------------------------------------------------
# 생성 흐름 (가짜 LLM)
# ---------------------------------------------------------------------------


class FakeLLM:
    """스키마별로 정해 둔 응답을 차례로 돌려준다. 예외 객체를 넣으면 그 호출에서 던진다."""

    def __init__(self, responses):
        self.responses = {schema: list(items) for schema, items in responses.items()}
        self.prompts = []

    def __call__(self, schema, system_prompt, human_prompt):
        self.prompts.append((schema, human_prompt))
        response = self.responses[schema].pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def masked_records():
    records = build_case_records(
        make_transcript(),
        session_no=8,
        previous_sessions=make_previous_sessions()[2:3],
        child_app_responses=make_app_responses(),
    )
    return records


def ref_of(records, label):
    return next(record["ref"] for record in records if record["label"] == label)


CHECKLIST_RESULTS = [
    {"status": "needs_confirmation", "item": "상처의 치료 여부", "source": "체크리스트.pdf", "page": 3},
    {"status": "excluded", "item": "관련 없음", "source": "체크리스트.pdf", "page": 4},
]
LAW_ARTICLES = [{"law_name": "아동복지법", "article": "제17조", "title": "금지행위", "content": "누구든지 …"}]
PRECEDENTS = [{"title": "친부가 자녀를 때림", "summary": "…", "citation": "인천지방법원 2022고정1131"}]
GUIDANCE = [
    {
        "content": "아동 면담 시 개방형 질문을 먼저 사용한다.",
        "metadata": {"source": "업무 매뉴얼.pdf", "page": 125, "screen_section": "상담·조사·사정", "chunk_id": "m1"},
    }
]


@pytest.fixture
def no_vector_db(monkeypatch):
    calls = []

    def fake_search(query, **kwargs):
        calls.append(kwargs)
        return GUIDANCE

    monkeypatch.setattr(builder, "search_evidence", fake_search)
    return calls


def test_two_stage_generation_validates_refs_rules_and_review(monkeypatch, no_vector_db):
    records = masked_records()
    pain = ref_of(records, "8회차 01:08")
    hit = ref_of(records, "8회차 00:03")
    plan = ref_of(records, "7회차 안전 계획")
    app = ref_of(records, "10/7 아이 앱 응답")

    fake = FakeLLM(
        {
            CheckItemDrafts: [
                CheckItemDrafts(
                    items=[
                        CheckItemDraft(item="등 · 팔 통증 이후 치료를 받았는지", kind="info_gap", priority="high",
                                       reason="치료 여부 미확인", case_refs=[pain], knowledge_refs=["checklist:1"]),
                        CheckItemDraft(item="조모 연락 체계가 실제로 쓰였는지", kind="plan_followup", priority="high",
                                       reason="안전 계획 이행 미확인", case_refs=[plan, "case:999"]),
                        CheckItemDraft(item="근거 없는 항목", kind="info_gap", priority="medium",
                                       reason="", case_refs=["case:999"]),
                    ]
                )
            ],
            QuestionDrafts: [
                QuestionDrafts(
                    items=[
                        QuestionDraft(check_item_id="check:1", question="등이랑 팔이 아팠던 건 지금은 어때? 누가 봐 준 적 있어?",
                                      audience="counselor", question_type="open", priority="high", rationale="치료 여부",
                                      case_refs=[pain], knowledge_refs=["manual:1", "checklist:1"]),
                        QuestionDraft(check_item_id="check:1", question="병원에 갔지?", audience="counselor",
                                      question_type="clarify", priority="high", rationale="", case_refs=[pain],
                                      knowledge_refs=["manual:1"]),
                        QuestionDraft(check_item_id="check:2", question="할머니한테 연락해 본 적 있어?",
                                      audience="counselor", question_type="open", priority="medium", rationale="",
                                      case_refs=[plan], knowledge_refs=[]),
                        QuestionDraft(check_item_id="check:9", question="그 이야기를 하면 어떤 일이 생길 것 같아?",
                                      audience="counselor", question_type="open", priority="medium", rationale="",
                                      case_refs=[hit], knowledge_refs=["law:1"]),
                        QuestionDraft(question="요즘 기분은 어때?", audience="child_app", question_type="open",
                                      priority="medium", rationale="", case_refs=[app], knowledge_refs=["manual:1"]),
                    ]
                ),
                QuestionDrafts(
                    items=[
                        QuestionDraft(check_item_id="check:2", question="무서울 때 누구한테 이야기할 수 있어?",
                                      audience="counselor", question_type="open", priority="medium", rationale="",
                                      case_refs=[plan], knowledge_refs=["manual:1"]),
                        QuestionDraft(check_item_id="check:2", question="할머니한테 전화하는 건 어떤 것 같아?",
                                      audience="counselor", question_type="open", priority="medium", rationale="",
                                      case_refs=[plan], knowledge_refs=["precedent:1"]),
                    ]
                ),
            ],
            QuestionReviews: [
                QuestionReviews(
                    reviews=[
                        QuestionReview(question_id=1, leading=False, presupposes=False, age_inappropriate=False, judgmental=False),
                        QuestionReview(question_id=2, leading=False, presupposes=False, age_inappropriate=False, judgmental=False),
                        # 3번(아이 앱 질문)은 검토에서 빠졌다 → 통과시키지 않는다.
                    ]
                ),
                QuestionReviews(
                    reviews=[
                        QuestionReview(question_id=1, leading=False, presupposes=False, age_inappropriate=False, judgmental=False),
                        QuestionReview(question_id=2, leading=False, presupposes=True, age_inappropriate=False,
                                       judgmental=False, reason="계획 이행을 전제"),
                    ]
                ),
            ],
        }
    )
    monkeypatch.setattr(builder, "_invoke", fake)

    result = builder.build_next_session_checklist(
        records,
        CHECKLIST_RESULTS,
        LAW_ARTICLES,
        precedents=PRECEDENTS,
        fallback_questions=["쓰이면 안 되는 대체 질문"],
    )

    # 면담 지침은 업무 매뉴얼 '상담·조사·사정' 구간에서 찾는다.
    assert no_vector_db[0]["screen"] == "followup"
    assert no_vector_db[0]["screen_section"] == "상담·조사·사정"

    # 1) 확인할 사항: 없는 ID는 지우고, 사례 근거가 하나도 없는 항목은 버린다.
    check_items = result["check_items"]
    assert [item["item"] for item in check_items] == ["등 · 팔 통증 이후 치료를 받았는지", "조모 연락 체계가 실제로 쓰였는지"]
    assert check_items[1]["case_refs"] == [plan]
    assert [basis["label"] for basis in check_items[0]["basis"]] == ["8회차 01:08", "체크리스트.pdf p.3"]

    # 2) 질문: 유도형 · 공식 근거 없음은 규칙에서, 검토 누락 · 전제는 LLM 검토에서 떨어진다.
    questions = result["items"]
    assert [item["question"] for item in questions] == [
        "등이랑 팔이 아팠던 건 지금은 어때? 누가 봐 준 적 있어?",
        "그 이야기를 하면 어떤 일이 생길 것 같아?",
        "무서울 때 누구한테 이야기할 수 있어?",
    ]
    assert all(item["review_status"] == "passed" for item in questions)
    assert questions[1]["check_item_id"] is None  # 없는 확인할 사항 ID는 지운다
    first_basis = [basis["label"] for basis in questions[0]["basis"]]
    assert first_basis == ["8회차 01:08", "업무 매뉴얼.pdf · 상담·조사·사정 p.125", "체크리스트.pdf p.3"]
    assert questions[0]["basis"][0]["segment_id"] == "seg_2"
    assert questions[0]["basis"][0]["start_ms"] == 68_000

    # 3) 상담사용 질문이 3개가 안 돼서 탈락 사유를 알려 주고 한 번 더 만들었다.
    validation = result["validation"]
    assert validation["rounds"] == 2
    assert validation["rule_rejected"] == 2
    assert validation["review_rejected"] == 2
    second_prompt = [prompt for schema, prompt in fake.prompts if schema is QuestionDrafts][1]
    assert "병원에 갔지?" in second_prompt and "답을 정해 두고" in second_prompt


def test_review_failure_keeps_rule_checked_questions_marked_not_reviewed(monkeypatch, no_vector_db):
    records = masked_records()
    pain = ref_of(records, "8회차 01:08")
    question = QuestionDraft(question="등이랑 팔이 아팠던 건 지금은 어때?", audience="counselor",
                             question_type="open", priority="high", rationale="", case_refs=[pain],
                             knowledge_refs=["manual:1"])
    fake = FakeLLM(
        {
            CheckItemDrafts: [RuntimeError("timeout")],
            QuestionDrafts: [QuestionDrafts(items=[question]), RuntimeError("timeout")],
            QuestionReviews: [RuntimeError("timeout")],
        }
    )
    monkeypatch.setattr(builder, "_invoke", fake)

    result = builder.build_next_session_checklist(records, [], [])

    assert result["check_items"] == []
    assert [item["review_status"] for item in result["items"]] == ["not_reviewed"]
    assert result["validation"]["reviewed"] is False
    assert result["validation"]["rounds"] == 1  # 다시 만들기가 실패해도 앞 회차 결과는 남긴다


def test_generation_failure_falls_back_to_rule_checked_questions(monkeypatch, no_vector_db):
    fake = FakeLLM({CheckItemDrafts: [CheckItemDrafts()], QuestionDrafts: [RuntimeError("timeout")]})
    monkeypatch.setattr(builder, "_invoke", fake)

    result = builder.build_next_session_checklist(
        masked_records(),
        CHECKLIST_RESULTS,
        [],
        fallback_questions=["그때 이야기를 더 해 줄래?", "아빠가 때렸지?"],
    )

    assert [item["question"] for item in result["items"]] == ["그때 이야기를 더 해 줄래?"]
    assert result["items"][0]["review_status"] == "fallback"
    assert result["validation"]["fallback"] is True


def test_no_case_records_skips_llm(monkeypatch):
    monkeypatch.setattr(builder, "_invoke", lambda *args: pytest.fail("사례 기록이 없으면 LLM 을 부르지 않는다"))

    assert builder.build_next_session_checklist([], CHECKLIST_RESULTS, LAW_ARTICLES) == {
        "check_items": [],
        "items": [],
        "validation": {},
    }


# ---------------------------------------------------------------------------
# 비식별 · 연결
# ---------------------------------------------------------------------------


def test_pipeline_masks_text_and_case_records_together(monkeypatch):
    masked_payloads = []

    def fake_mask(payload, known_identifiers=None):
        masked_payloads.append((payload, known_identifiers))

        def mask(value):
            if isinstance(value, dict):
                return {key: mask(sub) for key, sub in value.items()}
            return value.replace("민수", "[PERSON_01]")

        return mask(payload), {"[PERSON_01]": "민수"}

    captured = {}

    def fake_analyze(text, abuse_type, **kwargs):
        captured["text"] = text
        captured["records"] = kwargs["case_records"]
        return {"next_session_checklist": {"items": [{"question": "[PERSON_01]이랑 있을 때는 어때?"}]}}

    def fake_restore(value, entity_map):
        if isinstance(value, dict):
            return {key: fake_restore(sub, entity_map) for key, sub in value.items()}
        if isinstance(value, list):
            return [fake_restore(item, entity_map) for item in value]
        if isinstance(value, str):
            for token, original in entity_map.items():
                value = value.replace(token, original)
        return value

    monkeypatch.setattr(pipeline, "mask_payload", fake_mask)
    monkeypatch.setattr(pipeline, "_analyze_masked", fake_analyze)
    monkeypatch.setattr(pipeline, "restore", fake_restore)

    records = [
        {"ref": "case:1", "current": True, "label": "8회차 00:03", "text": "민수가 때렸어요"},
        {"ref": "case:2", "current": False, "source": "app_response", "label": "10/7 아이 앱 응답", "text": "민수 형이 무서워요"},
    ]
    result = pipeline.analyze_consultation_evidence(
        "민수가 때렸어요", "physical", known_identifiers=["민수"], case_records=records
    )

    assert len(masked_payloads) == 1  # 상담 문장과 사례 기록을 한 번에 가린다(토큰 일치)
    assert masked_payloads[0][1] == ["민수"]
    assert captured["text"] == "[PERSON_01]가 때렸어요"
    assert [record["text"] for record in captured["records"]] == ["[PERSON_01]가 때렸어요", "[PERSON_01] 형이 무서워요"]
    assert captured["records"][1]["label"] == "10/7 아이 앱 응답"
    assert records[0]["text"] == "민수가 때렸어요"  # 넘겨받은 원본은 바꾸지 않는다
    assert result["next_session_checklist"]["items"][0]["question"] == "민수이랑 있을 때는 어때?"


def test_session_passes_case_context_to_pipeline(monkeypatch):
    captured = {}

    def fake_analyze(**kwargs):
        captured.update(kwargs)
        return {"next_session_checklist": {"check_items": [], "items": []}}

    monkeypatch.setattr(session, "analyze_consultation_evidence", fake_analyze)
    monkeypatch.setattr(session, "build_screen_references", lambda *a, **k: {"references": {}, "errors": {}})

    result = session.analyze_reviewed_transcript(
        make_transcript(),
        "physical",
        session_no=8,
        previous_sessions=make_previous_sessions(),
        child_app_responses=make_app_responses(),
    )

    labels = [record["label"] for record in captured["case_records"]]
    assert labels[:3] == ["8회차 00:03", "8회차 01:08", "8회차 02:40"]
    assert "7회차 안전 계획" in labels and "10/7 아이 앱 응답" in labels
    assert captured["text"] == "아빠가 때렸어요. 등이랑 팔이 아파요. 할머니한테는 아직 전화 안 했어요."
    assert [item["item"] for item in result["speaker_check_items"]] == ["02:15 발화의 화자"]


def test_blocked_previous_records_fall_back_to_current_session(monkeypatch):
    from rag.privacy import RagPrivacyBlocked

    def fake_mask(payload, known_identifiers=None):
        if any("박○○ 선생님" in text for text in payload["case"].values()):
            raise RagPrivacyBlocked(["case.case:2: NER 개체 잔존(PS)"])
        return payload, {}

    captured = {}

    def fake_analyze(text, abuse_type, **kwargs):
        captured["records"] = kwargs["case_records"]
        return {}

    monkeypatch.setattr(pipeline, "mask_payload", fake_mask)
    monkeypatch.setattr(pipeline, "_analyze_masked", fake_analyze)
    monkeypatch.setattr(pipeline, "restore", lambda value, entity_map: value)

    records = [
        {"ref": "case:1", "current": True, "label": "8회차 00:03", "text": "등이 아파요"},
        {"ref": "case:2", "current": False, "label": "7회차 상담 요약", "text": "박○○ 선생님과 통화"},
    ]
    result = pipeline.analyze_consultation_evidence("등이 아파요", "physical", case_records=records)

    assert [record["ref"] for record in captured["records"]] == ["case:1"]
    assert "이번 회차 아동 발화만" in result["case_context_warning"]

    # 이번 회차 발화가 막히면 그대로 막는다.
    records[0]["text"] = "박○○ 선생님이 때렸어요"
    with pytest.raises(RagPrivacyBlocked):
        pipeline.analyze_consultation_evidence("박○○ 선생님이 때렸어요", "physical", case_records=records)


def test_basis_carries_link_targets_and_excerpts(monkeypatch, no_vector_db):
    previous = make_previous_sessions()[2:3]
    previous[0]["session_id"] = "sess-7"
    records = build_case_records(
        make_transcript(),
        session_no=8,
        session_id="sess-8",
        previous_sessions=previous,
        child_app_responses=make_app_responses(),
    )
    pain = ref_of(records, "8회차 01:08")
    plan = ref_of(records, "7회차 안전 계획")
    app = ref_of(records, "10/7 아이 앱 응답")
    fake = FakeLLM(
        {
            CheckItemDrafts: [CheckItemDrafts()],
            QuestionDrafts: [
                QuestionDrafts(
                    items=[
                        QuestionDraft(question="등이랑 팔이 아팠던 건 지금은 어때?", audience="counselor",
                                      question_type="open", priority="high", rationale="",
                                      case_refs=[pain, plan, app], knowledge_refs=["manual:1", "law:1", "precedent:1"]),
                    ]
                )
            ],
            QuestionReviews: [
                QuestionReviews(reviews=[QuestionReview(question_id=1, leading=False, presupposes=False,
                                                        age_inappropriate=False, judgmental=False)])
            ],
        }
    )
    monkeypatch.setattr(builder, "_invoke", fake)
    law = [{**LAW_ARTICLES[0], "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=1&joNo=0017"}]
    precedent = [{**PRECEDENTS[0], "url": "https://www.law.go.kr/LSW/precInfoP.do?precSeq=1"}]

    result = builder.build_next_session_checklist(records, [], law, precedents=precedent)
    basis = {item["ref"]: item for item in result["items"][0]["basis"]}

    # 이번 회차 발화 → STT 검수 링크(회차 ID + 발화 ID), 원문 발췌
    assert basis[pain]["session_id"] == "sess-8"
    assert basis[pain]["segment_id"] == "seg_2"
    assert basis[pain]["excerpt"] == "등이랑 팔이 아파요."
    # 이전 회차 안전 계획 → 그 회차 상세 링크
    assert basis[plan]["session_id"] == "sess-7"
    assert basis[plan]["excerpt"] == "위험할 때 할머니에게 연락하기로 함"
    # 아이 앱 응답
    assert basis[app]["response_id"] == "r1"
    # 매뉴얼은 발췌 · 쪽, 법령 · 판례는 원문 주소
    assert basis["manual:1"]["excerpt"] == "아동 면담 시 개방형 질문을 먼저 사용한다."
    assert basis["manual:1"]["page"] == 125
    assert basis["law:1"]["url"].startswith("https://www.law.go.kr/LSW/lsInfoP.do")
    assert basis["precedent:1"]["url"].startswith("https://www.law.go.kr/LSW/precInfoP.do")

    # 회차 ID 는 링크용으로 결과에만 싣고 LLM 에는 보내지 않는다.
    assert not any("sess-" in prompt for _, prompt in fake.prompts)
    assert speaker_check_items(make_transcript(), session_no=8, session_id="sess-8")[0]["basis"][0]["session_id"] == "sess-8"
