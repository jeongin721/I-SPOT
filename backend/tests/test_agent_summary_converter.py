# agent/summary_converter.py 를 검증한다.
#
# ai-modeling analyze_audio_session 결과(가짜 dict)를 서버 요약 응답 모양으로
# 바꾸는지 본다. 이경진 님 모듈은 import 하지 않는다(torch · 가중치 · OpenAI 불필요).
# 모든 발화는 가상 데이터다.
#
#   - 정상 변환: overview · key_points · summary_evidence · score
#   - 보호자 · 화자 미상 · 상담사 근거가 걸러지고, 다 걸러진 항목은 요지에서도 빠지는가
#   - 원문에 없는 segment_id 가 빠지는가
#   - record_draft 없음 · 빈 요약 · 아동 발화만 있고 요지 없음 → 빈 값 + 경고
#   - 잘못된 형식에서 죽지 않는가
#   - 중복 근거 · 중복 문장 · 원문의 중복 segment_id
#   - 결과가 AI Output Contract 와 LangGraphAIAdapter._to_bundle 을 통과하는가

import ast
import copy
from pathlib import Path

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

ensure_repo_root_on_path()

from agent.summary_converter import (  # noqa: E402
    KEY_POINTS_EMPTY_WARNING,
    OVERVIEW_EMPTY_WARNING,
    convert_summary,
)
from ai.services.evidence_linker import calculate_similarity  # noqa: E402
from app.adapters.ai_adapter import LangGraphAIAdapter  # noqa: E402
from app.core.config import REPO_ROOT  # noqa: E402
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem  # noqa: E402

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 1000,
         "text": "요즘 학교는 어때요?", "confidence": 0.9},
        {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 1000, "end_ms": 2000,
         "text": "학교 끝나고 도서관에서 동화책을 읽어요.", "confidence": 0.9},
        {"segment_id": "seg_003", "speaker": "GUARDIAN", "start_ms": 2000, "end_ms": 3000,
         "text": "집에서는 저녁마다 숙제를 같이 해요.", "confidence": 0.9},
        {"segment_id": "seg_004", "speaker": "CHILD", "start_ms": 3000, "end_ms": 4000,
         "text": "주말에는 놀이터에서 친구랑 줄넘기를 해요.", "confidence": 0.9},
        {"segment_id": "seg_005", "speaker": "UNKNOWN", "start_ms": 4000, "end_ms": 5000,
         "text": "줄넘기 대회도 나갔어요.", "confidence": 0.0},
        {"segment_id": "seg_006", "speaker": "OTHER", "start_ms": 5000, "end_ms": 6000,
         "text": "선생님이 칭찬했어요.", "confidence": 0.9},
    ],
}

OVERVIEW = "아동은 학교생활과 주말 놀이에 대해 이야기했다."


def _session_result(points=None, summary=OVERVIEW, **extra):
    """analyze_audio_session 반환 dict 의 가짜. 변환기가 읽는 키만 채운다."""

    result = {
        "counseling_summary": summary,
        "counseling_note": "상담 일지 문자열(변환기는 쓰지 않음)",
        "record_draft": {
            "session_overview": "녹취 1분 · 발화 6건",
            "child_statement_points": points if points is not None else [],
            "risk_signal_points": [],
            "counselor_observation": "",
        },
        "segments": [],
    }
    result.update(extra)
    return result


def _point(text, *segment_ids):
    return {"text": text, "segment_ids": list(segment_ids)}


# =========================================================
# 정상 변환
# =========================================================

def test_converts_summary_and_child_statement_points():
    result = convert_summary(
        _session_result([
            _point("방과 후 도서관에서 동화책을 읽는다고 말했다.", "seg_002"),
            _point("주말에 놀이터에서 친구와 줄넘기를 한다고 말했다.", "seg_004"),
        ]),
        TRANSCRIPT,
    )

    assert result["summary"] == {
        "overview": OVERVIEW,
        "key_points": [
            "방과 후 도서관에서 동화책을 읽는다고 말했다.",
            "주말에 놀이터에서 친구와 줄넘기를 한다고 말했다.",
        ],
    }
    assert [item["segment_ids"] for item in result["summary_evidence"]] == [["seg_002"], ["seg_004"]]
    assert [item["key_point"] for item in result["summary_evidence"]] == result["summary"]["key_points"]
    assert result["warnings"] == []


def test_score_uses_local_similarity_max_over_child_segments():
    key_point = "주말에 놀이터에서 친구와 줄넘기를 한다고 말했다."

    result = convert_summary(
        _session_result([_point(key_point, "seg_002", "seg_004")]),
        TRANSCRIPT,
    )

    expected = max(
        calculate_similarity(key_point, TRANSCRIPT["segments"][1]["text"]),
        calculate_similarity(key_point, TRANSCRIPT["segments"][3]["text"]),
    )
    score = result["summary_evidence"][0]["score"]

    assert score == expected
    assert 0.0 < score <= 1.0


def test_strips_whitespace_from_overview_and_points():
    result = convert_summary(
        _session_result([_point("  도서관에서 책을 읽는다.  ", "seg_002")], summary="  요약  "),
        TRANSCRIPT,
    )

    assert result["summary"] == {"overview": "요약", "key_points": ["도서관에서 책을 읽는다."]}


def test_does_not_mutate_inputs():
    session_result = _session_result([_point("도서관에서 책을 읽는다.", "seg_002", "seg_003")])
    transcript = copy.deepcopy(TRANSCRIPT)
    before = (copy.deepcopy(session_result), copy.deepcopy(transcript))

    convert_summary(session_result, transcript)

    assert (session_result, transcript) == before


# =========================================================
# 근거 거르기 — 아동(CHILD) 발화만
# =========================================================

@pytest.mark.parametrize("segment_id", ["seg_001", "seg_003", "seg_005", "seg_006"])
def test_drops_point_supported_only_by_non_child_speaker(segment_id):
    """상담사 · 보호자 · 화자 미상 · 기타 발화만 근거인 항목은 요지에서도 뺀다."""

    result = convert_summary(
        _session_result([
            _point("아동 근거가 있는 요지", "seg_002"),
            _point("아동이 아닌 화자만 근거인 요지", segment_id),
        ]),
        TRANSCRIPT,
    )

    assert result["summary"]["key_points"] == ["아동 근거가 있는 요지"]
    assert [item["key_point"] for item in result["summary_evidence"]] == ["아동 근거가 있는 요지"]
    assert result["warnings"] == []


def test_keeps_only_child_segments_in_mixed_evidence():
    result = convert_summary(
        _session_result([_point("줄넘기를 한다.", "seg_003", "seg_004", "seg_005")]),
        TRANSCRIPT,
    )

    assert result["summary_evidence"][0]["segment_ids"] == ["seg_004"]


def test_drops_segment_ids_missing_from_transcript():
    result = convert_summary(
        _session_result([
            _point("원문에 있는 근거와 없는 근거", "seg_999", "seg_002"),
            _point("원문에 없는 근거만 있는 요지", "seg_404"),
        ]),
        TRANSCRIPT,
    )

    assert result["summary"]["key_points"] == ["원문에 있는 근거와 없는 근거"]
    assert result["summary_evidence"][0]["segment_ids"] == ["seg_002"]


def test_ignores_segments_returned_inside_session_result():
    """모듈이 돌려준 segments 가 아니라 서버가 넘긴 원문으로 화자를 확인한다."""

    forged = [{"segment_id": "seg_003", "speaker": "CHILD", "text": "보호자 발화를 아동으로 표시"}]

    result = convert_summary(
        _session_result([_point("보호자 발화가 근거인 요지", "seg_003")], segments=forged),
        TRANSCRIPT,
    )

    assert result["summary"]["key_points"] == []
    assert result["summary_evidence"] == []


def test_all_points_filtered_adds_warning():
    result = convert_summary(
        _session_result([_point("보호자 발화만 근거", "seg_003")]),
        TRANSCRIPT,
    )

    assert result["summary"]["key_points"] == []
    assert result["warnings"] == [KEY_POINTS_EMPTY_WARNING]


# =========================================================
# 값이 없을 때 — 빈 값 + 경고
# =========================================================

def test_missing_record_draft_with_child_speech_warns():
    session_result = _session_result()
    del session_result["record_draft"]

    result = convert_summary(session_result, TRANSCRIPT)

    assert result["summary"] == {"overview": OVERVIEW, "key_points": []}
    assert result["summary_evidence"] == []
    assert result["warnings"] == [KEY_POINTS_EMPTY_WARNING]


def test_empty_child_statement_points_with_child_speech_warns():
    """기록 초안은 LLM 실패를 삼켜 빈 목록을 준다. 아동 발화가 있으면 경고한다."""

    result = convert_summary(_session_result([]), TRANSCRIPT)

    assert result["summary"]["key_points"] == []
    assert result["warnings"] == [KEY_POINTS_EMPTY_WARNING]


def test_no_child_speech_and_no_points_has_no_key_points_warning():
    transcript = {
        "segments": [s for s in TRANSCRIPT["segments"] if s["speaker"] != "CHILD"],
    }

    result = convert_summary(_session_result([]), transcript)

    assert result["summary"]["key_points"] == []
    assert result["warnings"] == []


def test_child_segment_with_blank_text_is_not_child_speech():
    transcript = {
        "segments": [
            {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "괜찮아요?"},
            {"segment_id": "seg_002", "speaker": "CHILD", "text": "   "},
        ],
    }

    result = convert_summary(_session_result([_point("빈 발화가 근거", "seg_002")]), transcript)

    assert result["summary"]["key_points"] == []
    # 요지가 왔는데 다 걸러졌으므로 경고한다
    assert result["warnings"] == [KEY_POINTS_EMPTY_WARNING]


@pytest.mark.parametrize("summary", ["", "   ", None])
def test_empty_overview_warns(summary):
    result = convert_summary(
        _session_result([_point("도서관에서 책을 읽는다.", "seg_002")], summary=summary),
        TRANSCRIPT,
    )

    assert result["summary"]["overview"] == ""
    assert result["summary"]["key_points"] == ["도서관에서 책을 읽는다."]
    assert result["warnings"] == [OVERVIEW_EMPTY_WARNING]


# =========================================================
# 잘못된 형식 — 죽지 않는다
# =========================================================

@pytest.mark.parametrize("session_result", [None, "문자열", 42, [], ["counseling_summary"]])
def test_non_dict_session_result_returns_empty_with_warnings(session_result):
    result = convert_summary(session_result, TRANSCRIPT)

    assert result == {
        "summary": {"overview": "", "key_points": []},
        "summary_evidence": [],
        "warnings": [OVERVIEW_EMPTY_WARNING, KEY_POINTS_EMPTY_WARNING],
    }


@pytest.mark.parametrize(
    "field, value",
    [
        ("counseling_summary", 123),
        ("counseling_summary", ["요약"]),
        ("record_draft", "기록 초안 문자열"),
        ("record_draft", [_point("목록", "seg_002")]),
        ("record_draft", {"child_statement_points": "문자열"}),
        ("record_draft", {"child_statement_points": {"text": "dict", "segment_ids": ["seg_002"]}}),
    ],
)
def test_wrong_field_types_do_not_raise(field, value):
    session_result = _session_result([_point("도서관에서 책을 읽는다.", "seg_002")])
    session_result[field] = value

    result = convert_summary(session_result, TRANSCRIPT)

    AIAnalysisResult.model_validate({"summary": result["summary"], "warnings": result["warnings"]})
    assert result["warnings"]


def test_skips_malformed_points():
    points = [
        "문자열 항목",
        None,
        {"segment_ids": ["seg_002"]},
        {"text": None, "segment_ids": ["seg_002"]},
        {"text": 7, "segment_ids": ["seg_002"]},
        {"text": "   ", "segment_ids": ["seg_002"]},
        {"text": "근거 없음"},
        {"text": "근거가 None", "segment_ids": None},
        # 문자열 하나를 글자마다 쪼개 segment_id 로 쓰지 않는다
        {"text": "근거가 문자열", "segment_ids": "seg_002"},
        {"text": "근거가 dict", "segment_ids": {"seg_002": True}},
        {"text": "근거 원소가 이상함", "segment_ids": [None, True, 3.5, {"id": "seg_002"}, ""]},
        _point("정상 항목", "seg_004"),
    ]

    result = convert_summary(_session_result(points), TRANSCRIPT)

    assert result["summary"]["key_points"] == ["정상 항목"]
    assert result["warnings"] == []


def test_integer_segment_id_matches_string_id():
    """이경진 님 _clean_points 와 같게 정수 segment_id 는 문자열로 본다."""

    transcript = {"segments": [{"segment_id": "7", "speaker": "CHILD", "text": "줄넘기를 했어요."}]}

    result = convert_summary(_session_result([_point("줄넘기를 했다.", 7)]), transcript)

    assert result["summary_evidence"][0]["segment_ids"] == ["7"]


@pytest.mark.parametrize(
    "transcript",
    [
        None,
        "원문",
        {},
        {"segments": None},
        {"segments": "seg_002"},
        {"segments": [None, "seg_002", {"speaker": "CHILD", "text": "segment_id 없음"},
                      {"segment_id": 2, "speaker": "CHILD", "text": "숫자 id"}]},
    ],
)
def test_malformed_transcript_drops_all_evidence(transcript):
    result = convert_summary(_session_result([_point("도서관에서 책을 읽는다.", "seg_002")]), transcript)

    assert result["summary"] == {"overview": OVERVIEW, "key_points": []}
    assert result["summary_evidence"] == []
    assert result["warnings"] == [KEY_POINTS_EMPTY_WARNING]


# =========================================================
# 중복
# =========================================================

def test_duplicate_segment_ids_in_point_are_collapsed():
    result = convert_summary(
        _session_result([_point("도서관에서 책을 읽는다.", "seg_002", "seg_002", "seg_004", "seg_002")]),
        TRANSCRIPT,
    )

    assert result["summary_evidence"][0]["segment_ids"] == ["seg_002", "seg_004"]


def test_duplicate_point_text_is_merged():
    result = convert_summary(
        _session_result([
            _point("놀이터에서 줄넘기를 한다.", "seg_004"),
            _point("도서관에서 책을 읽는다.", "seg_002"),
            _point(" 놀이터에서 줄넘기를 한다. ", "seg_002", "seg_004"),
        ]),
        TRANSCRIPT,
    )

    assert result["summary"]["key_points"] == ["놀이터에서 줄넘기를 한다.", "도서관에서 책을 읽는다."]
    assert result["summary_evidence"][0]["segment_ids"] == ["seg_004", "seg_002"]
    assert result["summary_evidence"][0]["score"] == max(
        calculate_similarity("놀이터에서 줄넘기를 한다.", TRANSCRIPT["segments"][1]["text"]),
        calculate_similarity("놀이터에서 줄넘기를 한다.", TRANSCRIPT["segments"][3]["text"]),
    )


def test_duplicated_segment_id_in_transcript_is_not_used_as_evidence():
    """원문에 같은 segment_id 가 두 번 나오면 화자를 확정할 수 없어 쓰지 않는다."""

    transcript = {
        "segments": [
            {"segment_id": "seg_100", "speaker": "CHILD", "text": "도서관에 갔어요."},
            {"segment_id": "seg_100", "speaker": "GUARDIAN", "text": "도서관에 데려갔어요."},
            {"segment_id": "seg_101", "speaker": "CHILD", "text": "책을 빌렸어요."},
        ],
    }

    result = convert_summary(
        _session_result([
            _point("도서관에 갔다.", "seg_100"),
            _point("책을 빌렸다.", "seg_100", "seg_101"),
        ]),
        transcript,
    )

    assert result["summary"]["key_points"] == ["책을 빌렸다."]
    assert result["summary_evidence"][0]["segment_ids"] == ["seg_101"]


# =========================================================
# 계약 검증
# =========================================================

def _converted():
    return convert_summary(
        _session_result([
            _point("방과 후 도서관에서 동화책을 읽는다고 말했다.", "seg_002"),
            _point("보호자 발화만 근거", "seg_003"),
            _point("주말에 놀이터에서 친구와 줄넘기를 한다고 말했다.", "seg_004", "seg_404"),
        ]),
        TRANSCRIPT,
    )


def test_converted_result_satisfies_ai_output_contract():
    converted = _converted()

    result = AIAnalysisResult.model_validate(
        {
            "schema_version": "1.0",
            "summary": converted["summary"],
            "risk_utterances": [],
            "abuse_signals": [],
            "risk_factors": [],
            "warnings": converted["warnings"],
        }
    )
    evidence = [SummaryEvidenceItem.model_validate(item) for item in converted["summary_evidence"]]

    assert result.summary.key_points == [item.key_point for item in evidence]
    assert set(converted) == {"summary", "summary_evidence", "warnings"}


def test_converted_result_passes_langgraph_adapter_bundle():
    """그래프 최종 State 로 넣었을 때 어댑터의 마지막 관문(_to_bundle)을 통과한다."""

    converted = _converted()
    state = {
        "summary": converted["summary"],
        "summary_evidence": converted["summary_evidence"],
        "warnings": converted["warnings"],
        "risk_utterances": [],
        "abuse_signals": [],
        "risk_factors": [],
    }

    bundle = LangGraphAIAdapter()._to_bundle(state, TRANSCRIPT)

    assert bundle.result.summary.key_points == converted["summary"]["key_points"]
    assert [item.key_point for item in bundle.summary_evidence] == converted["summary"]["key_points"]
    assert [item.segment_ids for item in bundle.summary_evidence] == [["seg_002"], ["seg_004"]]
    assert bundle.result.risk_utterances == []
    assert bundle.result.abuse_signals == []
    assert bundle.result.risk_factors == []


def test_converter_does_not_import_ai_modeling_or_llm_clients():
    """변환기는 torch · 가중치 · OpenAI 없이 돌아야 한다."""

    source = (Path(REPO_ROOT) / "agent" / "summary_converter.py").read_text(encoding="utf-8")
    imported = set()

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    assert imported == {"typing", "ai.services.evidence_linker"}
