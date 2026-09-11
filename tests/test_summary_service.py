# LLM 상담 요약 서비스의 정상 출력과 예외 처리를 테스트한다.
# Structured Output, 정보 부족, 환경변수 누락, 잘못된 출력 등의 상황을 검증한다.

from unittest.mock import MagicMock, patch

import pytest

from ai.adapters.aihub_transcript import aihub_to_transcript
from ai.schemas.analysis import AIAnalysisOutput
from ai.services.summary_service import (
    SummaryOutputError,
    summarize_consultation,
)


# =========================================================
# Synthetic Test Data
# =========================================================

SAMPLE = {
    "version": 1,
    "info": {
        "ID": "SYNTHETIC_001"
    },
    "list": [
        {
            "문항": "가정생활",
            "문항합계": 0,
            "위기단계": "정상군",
            "list": [
                {
                    "항목": "가족관계",
                    "점수": 0,
                    "audio": [
                        {
                            "type": "Q",
                            "text": "집에서는 요즘 어떻게 지내?",
                            "wave": "all.wav",
                            "start": "00:00.000",
                            "end": "00:02.000",
                        },
                        {
                            "type": "A",
                            "text": (
                                "동생이랑 자주 싸우기는 하는데 "
                                "엄마랑은 이야기를 많이 해요."
                            ),
                            "wave": "all.wav",
                            "start": "00:03.000",
                            "end": "00:07.000",
                        },
                        {
                            "type": "Q",
                            "text": "요즘 힘들거나 걱정되는 건 있어?",
                            "wave": "all.wav",
                            "start": "00:08.000",
                            "end": "00:10.000",
                        },
                        {
                            "type": "A",
                            "text": (
                                "학교 숙제가 많아서 "
                                "조금 스트레스 받아요."
                            ),
                            "wave": "all.wav",
                            "start": "00:11.000",
                            "end": "00:14.000",
                        },
                    ],
                }
            ],
        }
    ],
}


def mock_environment():
    return patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
        },
    )


def make_mock_output(
    overview,
    key_points,
    warnings=None,
    risk_utterances=None,
    abuse_signals=None,
    risk_factors=None,
):
    """
    LLM Structured Output Mock 객체 생성.
    """

    mock_summary = MagicMock()

    mock_summary.overview = overview
    mock_summary.key_points = key_points

    mock_parsed = MagicMock()

    mock_parsed.schema_version = "1.0"
    mock_parsed.summary = mock_summary

    mock_parsed.risk_utterances = (
        risk_utterances or []
    )

    mock_parsed.abuse_signals = (
        abuse_signals or []
    )

    mock_parsed.risk_factors = (
        risk_factors or []
    )

    mock_parsed.warnings = (
        warnings or []
    )

    return mock_parsed


# =========================================================
# 정상 요약
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_summary_success(mock_openai):
    transcript = aihub_to_transcript(
        SAMPLE
    )

    mock_parsed = make_mock_output(
        overview=(
            "아동은 동생과 자주 다투지만 "
            "어머니와 대화를 많이 하며, "
            "학교 숙제로 스트레스를 느낀다고 말했다."
        ),
        key_points=[
            "동생과 자주 다툰다고 말했다.",
            "어머니와 대화를 많이 한다고 말했다.",
            "학교 숙제로 스트레스를 느낀다고 말했다.",
        ],
    )

    mock_response = MagicMock()

    mock_response.output_parsed = (
        mock_parsed
    )

    mock_client = MagicMock()

    mock_client.responses.parse.return_value = (
        mock_response
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        result = summarize_consultation(
            transcript
        )

    assert isinstance(
        result,
        AIAnalysisOutput,
    )

    assert result.schema_version == "1.0"

    assert "학교 숙제" in (
        result.summary.overview
    )

    assert len(
        result.summary.key_points
    ) == 3

    assert result.risk_utterances == []
    assert result.abuse_signals == []
    assert result.risk_factors == []
    assert isinstance(result.warnings, list)


# =========================================================
# 정보 부족
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_summary_insufficient_information(
    mock_openai,
):
    raw = {
        "version": 1,
        "info": {
            "ID": "SYNTHETIC_002"
        },
        "list": [
            {
                "문항": "상담",
                "list": [
                    {
                        "항목": "기본상담",
                        "audio": [
                            {
                                "type": "Q",
                                "text": "오늘 기분은 어때?",
                                "wave": "all.wav",
                                "start": "00:00.000",
                                "end": "00:02.000",
                            },
                            {
                                "type": "A",
                                "text": "잘 모르겠어요.",
                                "wave": "all.wav",
                                "start": "00:03.000",
                                "end": "00:04.000",
                            },
                        ],
                    }
                ],
            }
        ],
    }

    transcript = aihub_to_transcript(
        raw
    )

    mock_parsed = make_mock_output(
        overview=(
            "상담 내용만으로 구체적인 상태를 "
            "파악하기 어렵다."
        ),
        key_points=[],
        warnings=[
            "추가 확인 필요"
        ],
    )

    mock_response = MagicMock()

    mock_response.output_parsed = (
        mock_parsed
    )

    mock_client = MagicMock()

    mock_client.responses.parse.return_value = (
        mock_response
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        result = summarize_consultation(
            transcript
        )

    assert result.summary.key_points == []

    assert "추가 확인 필요" in result.warnings

    assert result.risk_utterances == []
    assert result.abuse_signals == []
    assert result.risk_factors == []


# =========================================================
# 환경변수
# =========================================================

def test_missing_api_key():
    transcript = aihub_to_transcript(
        SAMPLE
    )

    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "",
            "OPENAI_MODEL": "test-model",
        },
    ):
        with pytest.raises(
            RuntimeError,
            match="OPENAI_API_KEY",
        ):
            summarize_consultation(
                transcript
            )


def test_missing_model():
    transcript = aihub_to_transcript(
        SAMPLE
    )

    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "",
        },
    ):
        with pytest.raises(
            RuntimeError,
            match="OPENAI_MODEL",
        ):
            summarize_consultation(
                transcript
            )


# =========================================================
# Structured Output 오류
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_llm_returns_none(
    mock_openai,
):
    transcript = aihub_to_transcript(
        SAMPLE
    )

    mock_response = MagicMock()

    mock_response.output_parsed = None

    mock_client = MagicMock()

    mock_client.responses.parse.return_value = (
        mock_response
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        with pytest.raises(
            SummaryOutputError,
            match="Structured Output",
        ):
            summarize_consultation(
                transcript
            )


# =========================================================
# 요약 단계 위험 결과 차단
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_risk_result_is_rejected_in_summary_stage(
    mock_openai,
):
    transcript = aihub_to_transcript(
        SAMPLE
    )

    mock_parsed = make_mock_output(
        overview=(
            "아동은 학교 숙제로 "
            "스트레스를 느낀다고 말했다."
        ),
        key_points=[
            "학교 숙제가 많아 "
            "스트레스를 받는다고 말했다."
        ],
        risk_utterances=[
            "위험 발화"
        ],
    )

    mock_response = MagicMock()

    mock_response.output_parsed = (
        mock_parsed
    )

    mock_client = MagicMock()

    mock_client.responses.parse.return_value = (
        mock_response
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        with pytest.raises(
            SummaryOutputError,
            match="위험 분석 결과",
        ):
            summarize_consultation(
                transcript
            )


# =========================================================
# 일반 API 오류
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_api_error(
    mock_openai,
):
    transcript = aihub_to_transcript(
        SAMPLE
    )

    mock_client = MagicMock()

    mock_client.responses.parse.side_effect = (
        Exception(
            "Mock API Error"
        )
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        with pytest.raises(
            Exception,
            match="Mock API Error",
        ):
            summarize_consultation(
                transcript
            )


# =========================================================
# Timeout Mock
# =========================================================

@patch("ai.services.summary_service.OpenAI")
def test_timeout_error(
    mock_openai,
):
    transcript = aihub_to_transcript(
        SAMPLE
    )

    mock_client = MagicMock()

    mock_client.responses.parse.side_effect = (
        TimeoutError(
            "Mock Timeout"
        )
    )

    mock_openai.return_value = (
        mock_client
    )

    with mock_environment():
        with pytest.raises(
            TimeoutError,
            match="Mock Timeout",
        ):
            summarize_consultation(
                transcript
            )