# AI Output Contract 의 선택 필드 4개를 검증한다(2026-10-16 추가, API_CONTRACT.md 8절).
#
#   - severity_ratings / protective_factors / session_change_notes / followup_check_points
#   - 있으면 그대로, 없으면 빈 배열. schema_version 은 "1.0" 그대로
#   - level 은 1~5 정수 또는 null. 범위 밖 · 정수가 아닌 값은 Contract 위반(AI_INVALID_OUTPUT)
#   - 근거 없는 위험 항목 빼기는 위험 3필드에만 적용하고 이 4개에는 적용하지 않는다
#   - 이 필드가 없던 때 저장한 결과도 분석 조회 API 로 그대로 읽힌다
#
# 모든 값은 가상 데이터다.

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.adapters.ai_adapter import (
    AIAnalysisBundle,
    AIError,
    LangGraphAIAdapter,
    PipelineAIAdapter,
    set_ai_adapter_override,
)
from app.core.errors import ErrorCode
from app.models.analysis import AIAnalysis
from app.schemas.contracts import AIAnalysisResult
from tests.test_analysis import _get_analysis, _run_analysis, confirmed_session

OPTIONAL_FIELDS = (
    "severity_ratings",
    "protective_factors",
    "session_change_notes",
    "followup_check_points",
)

SEVERITY = {
    "major_type": "정서학대",
    "level": 3,
    "reason": "가상 사유: 꾸중이 잦다는 진술이 있다.",
    "matched_evidence": "\"엄마가 자주 소리를 질러요.\"",
    "segment_ids": ["seg_002"],
    "reviewed": False,
}
SEVERITY_NO_INFO = {
    "major_type": "방임",
    "level": None,
    "reason": "가상 사유: 정보가 부족하다.",
    "matched_evidence": "",
    "reviewed": False,
}
PROTECTIVE = {"category": "지지 관계", "text": "가상: 담임 선생님과 이야기한다.", "segment_ids": []}
CHANGE_NOTE = {"text": "가상: 지난 회기보다 말수가 늘었다.", "segment_ids": []}
CHECK_POINT = {"text": "가상: 저녁 식사를 누구와 하는지 확인 필요"}

FULL_FIELDS = {
    "severity_ratings": [SEVERITY, SEVERITY_NO_INFO],
    "protective_factors": [PROTECTIVE],
    "session_change_notes": [CHANGE_NOTE],
    "followup_check_points": [CHECK_POINT],
}

# 4개 필드가 없던 때의 결과 모양(그때 저장된 DB 값과 같다).
OLD_RESULT = {
    "schema_version": "1.0",
    "summary": {"overview": "가상 요약", "key_points": ["가상 요점"]},
    "risk_utterances": [],
    "abuse_signals": [],
    "risk_factors": [],
    "warnings": [],
}

TRANSCRIPT = {
    "schema_version": "1.0",
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "text": "요즘 어때요?"},
        {"segment_id": "seg_002", "speaker": "CHILD", "text": "엄마가 자주 소리를 질러요."},
    ],
}


def _validate(**fields) -> AIAnalysisResult:
    return AIAnalysisResult.model_validate({**OLD_RESULT, **fields})


# =========================================================
# Contract 모델
# =========================================================

def test_all_four_fields_are_kept_as_sent():
    result = _validate(**FULL_FIELDS).model_dump()

    assert result["schema_version"] == "1.0"
    assert result["severity_ratings"][0] == SEVERITY
    assert result["protective_factors"] == [PROTECTIVE]
    assert result["session_change_notes"] == [CHANGE_NOTE]
    # 빠진 segment_ids 는 빈 배열로 채운다.
    assert result["followup_check_points"] == [{**CHECK_POINT, "segment_ids": []}]


def test_missing_fields_become_empty_lists():
    result = AIAnalysisResult.model_validate(OLD_RESULT).model_dump()

    for name in OPTIONAL_FIELDS:
        assert result[name] == []


def test_severity_defaults_fill_missing_keys():
    rating = _validate(severity_ratings=[{"major_type": "신체학대"}]).severity_ratings[0]

    assert rating.level is None
    assert rating.reason == ""
    assert rating.matched_evidence == ""
    assert rating.segment_ids == []
    assert rating.reviewed is False


def test_level_null_means_not_enough_information():
    rating = _validate(severity_ratings=[SEVERITY_NO_INFO]).severity_ratings[0]

    assert rating.level is None


@pytest.mark.parametrize("level", [1, 5])
def test_level_range_edges_are_accepted(level):
    rating = _validate(severity_ratings=[{**SEVERITY, "level": level}]).severity_ratings[0]

    assert rating.level == level


@pytest.mark.parametrize("level", [0, 6, -1, 100])
def test_level_out_of_range_is_rejected(level):
    with pytest.raises(ValidationError):
        _validate(severity_ratings=[{**SEVERITY, "level": level}])


@pytest.mark.parametrize("level", [True, False, "3", 3.0, 2.5, [3]])
def test_level_must_be_integer(level):
    """bool · 문자열 · 실수가 조용히 정수로 바뀌어 저장되지 않는다."""

    with pytest.raises(ValidationError):
        _validate(severity_ratings=[{**SEVERITY, "level": level}])


@pytest.mark.parametrize(
    "fields",
    [
        # 필수 문자열이 없음
        {"severity_ratings": [{"level": 2}]},
        {"protective_factors": [{"text": "가상"}]},
        {"protective_factors": [{"category": "지지 관계"}]},
        {"session_change_notes": [{"segment_ids": []}]},
        {"followup_check_points": [{}]},
        # 객체 대신 문자열(이경진 님 결과의 옛 모양). text 에 넣어 보내야 한다.
        {"session_change_notes": ["가상: 말수가 늘었다."]},
        {"followup_check_points": ["가상: 확인 필요"]},
        # 목록이 아님
        {"severity_ratings": SEVERITY},
        {"protective_factors": "가상"},
        # 항목 안의 형식이 틀림
        {"protective_factors": [{**PROTECTIVE, "segment_ids": "seg_002"}]},
        {"session_change_notes": [{"text": 123}]},
        {"severity_ratings": [{**SEVERITY, "segment_ids": [1, 2]}]},
        {"severity_ratings": [{**SEVERITY, "reason": None}]},
    ],
)
def test_malformed_items_are_rejected(fields):
    with pytest.raises(ValidationError):
        _validate(**fields)


def test_unknown_item_keys_are_dropped():
    """최상위 result 와 같이 모르는 칸은 버린다. 판정 필드가 새어 들어오지 않는다."""

    result = _validate(
        severity_ratings=[{**SEVERITY, "abuse_confirmed": True}],
        protective_factors=[{**PROTECTIVE, "score": 0.9}],
    ).model_dump()

    assert "abuse_confirmed" not in result["severity_ratings"][0]
    assert "score" not in result["protective_factors"][0]


# =========================================================
# Adapter: 위반은 AI_INVALID_OUTPUT, 근거 빼기는 위험 3필드만
# =========================================================

def test_pipeline_result_carries_optional_fields():
    analysis = {**OLD_RESULT, **FULL_FIELDS}

    bundle = PipelineAIAdapter()._to_bundle(SimpleNamespace(analysis=analysis))

    assert bundle.result.model_dump()["severity_ratings"][0] == SEVERITY
    assert len(bundle.result.followup_check_points) == 1


def test_pipeline_out_of_range_level_is_invalid_output():
    analysis = {**OLD_RESULT, "severity_ratings": [{**SEVERITY, "level": 6}]}

    with pytest.raises(AIError) as error:
        PipelineAIAdapter()._to_bundle(SimpleNamespace(analysis=analysis))

    assert error.value.error_code == ErrorCode.AI_INVALID_OUTPUT


def test_langgraph_carries_optional_fields_without_grounding_check():
    """segment_ids 가 비었거나 없는 번호여도 4개 필드 항목은 빼지 않고, 경고도 달지 않는다."""

    state = {
        "summary": {"overview": "가상 요약", "key_points": []},
        **FULL_FIELDS,
        "protective_factors": [{**PROTECTIVE, "segment_ids": ["seg_999"]}],
    }

    bundle = LangGraphAIAdapter()._to_bundle(state, TRANSCRIPT)
    result = bundle.result.model_dump()

    assert len(result["severity_ratings"]) == 2
    assert result["protective_factors"][0]["segment_ids"] == ["seg_999"]
    assert result["session_change_notes"] == [CHANGE_NOTE]
    assert len(result["followup_check_points"]) == 1
    assert not any("segment 근거가 없는" in warning for warning in result["warnings"])


def test_langgraph_still_drops_ungrounded_risk_items_next_to_optional_fields():
    state = {
        "summary": {"overview": "가상 요약", "key_points": []},
        "risk_factors": [{"code": "가상", "segment_ids": []}],
        **FULL_FIELDS,
    }

    result = LangGraphAIAdapter()._to_bundle(state, TRANSCRIPT).result

    assert result.risk_factors == []
    assert "segment 근거가 없는 신호 1건을 제외했습니다." in result.warnings
    assert len(result.severity_ratings) == 2


def test_langgraph_out_of_range_level_is_invalid_output():
    state = {"severity_ratings": [{**SEVERITY, "level": 0}]}

    with pytest.raises(AIError) as error:
        LangGraphAIAdapter()._to_bundle(state, TRANSCRIPT)

    assert error.value.error_code == ErrorCode.AI_INVALID_OUTPUT


def test_langgraph_without_optional_fields_gives_empty_lists():
    result = LangGraphAIAdapter()._to_bundle({}, TRANSCRIPT).result.model_dump()

    for name in OPTIONAL_FIELDS:
        assert result[name] == []


@pytest.mark.parametrize("name", OPTIONAL_FIELDS)
@pytest.mark.parametrize("value", [None, False, 0, "", {}])
def test_langgraph_falsy_non_list_is_invalid_output(name, value):
    """키가 없을 때만 빈 배열이다. 배열이 아닌 값을 명시하면 Pipeline 처럼 Contract 위반이다.

    Codex 교차검증(10/16): `or []` 로 받아 None · {} 등이 빈 배열로 바뀌어 통과했다.
    """

    with pytest.raises(AIError) as error:
        LangGraphAIAdapter()._to_bundle({name: value}, TRANSCRIPT)

    assert error.value.error_code == ErrorCode.AI_INVALID_OUTPUT


# =========================================================
# 분석 조회 API
# =========================================================

class OptionalFieldsAIAdapter:
    name = "optional-fields"

    def analyze(self, transcript_payload):
        result = AIAnalysisResult.model_validate({**OLD_RESULT, **FULL_FIELDS})

        return AIAnalysisBundle(result=result, provider=self.name)


def test_analysis_api_returns_optional_fields_as_stored(
    client: TestClient, counselor_headers, session: dict
) -> None:
    confirmed_session(client, counselor_headers, session["id"])
    set_ai_adapter_override(OptionalFieldsAIAdapter())

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    analysis = _get_analysis(client, counselor_headers, session["id"]).json()["data"]["analysis"]

    assert analysis["status"] == "COMPLETED"
    assert analysis["schema_version"] == "1.0"

    result = analysis["result"]

    assert result["severity_ratings"] == [
        SEVERITY,
        {**SEVERITY_NO_INFO, "segment_ids": []},
    ]
    assert result["protective_factors"] == [PROTECTIVE]
    assert result["session_change_notes"] == [CHANGE_NOTE]
    assert result["followup_check_points"] == [{**CHECK_POINT, "segment_ids": []}]


def test_old_stored_result_without_optional_fields_is_still_readable(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    """필드가 생기기 전에 저장된 결과(4개 키 없음)도 조회되고, 빈 배열로 나온다."""

    confirmed_session(client, counselor_headers, session["id"])

    assert _run_analysis(client, counselor_headers, session["id"]).status_code == 202

    row = db.query(AIAnalysis).filter(AIAnalysis.session_id == uuid.UUID(session["id"])).one()
    row.result = dict(OLD_RESULT)
    db.commit()

    response = _get_analysis(client, counselor_headers, session["id"])

    assert response.status_code == 200

    result = response.json()["data"]["analysis"]["result"]

    assert result["schema_version"] == "1.0"
    assert result["summary"] == OLD_RESULT["summary"]

    for name in OPTIONAL_FIELDS:
        assert result[name] == []
