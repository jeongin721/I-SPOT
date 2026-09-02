# AI 파이프라인의 입력 및 출력 안정성을 추가 검증한다.
# 긴 Transcript, 잘못된 AI-HUB JSON, 요약의 원문 기반 여부 등을 테스트한다.

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from ai.adapters.aihub_transcript import aihub_to_transcript
from ai.schemas.analysis import KeyPointItem
from ai.services.summary_service import summarize_consultation


def make_long_consultation(count: int = 100):
    """긴 상담 테스트용 Synthetic AI-HUB JSON."""

    audio = []
    current_ms = 0

    for index in range(count):
        start_seconds = current_ms // 1000
        end_seconds = start_seconds + 2

        audio.append(
            {
                "type": "Q",
                "text": f"{index + 1}번째 질문입니다.",
                "wave": "synthetic.wav",
                "start": (
                    f"{start_seconds // 60:02d}:"
                    f"{start_seconds % 60:02d}.000"
                ),
                "end": (
                    f"{end_seconds // 60:02d}:"
                    f"{end_seconds % 60:02d}.000"
                ),
            }
        )

        current_ms += 3000

        start_seconds = current_ms // 1000
        end_seconds = start_seconds + 2

        audio.append(
            {
                "type": "A",
                "text": f"{index + 1}번째 답변입니다.",
                "wave": "synthetic.wav",
                "start": (
                    f"{start_seconds // 60:02d}:"
                    f"{start_seconds % 60:02d}.000"
                ),
                "end": (
                    f"{end_seconds // 60:02d}:"
                    f"{end_seconds % 60:02d}.000"
                ),
            }
        )

        current_ms += 3000

    return {
        "version": 1,
        "info": {
            "ID": "SYNTHETIC_LONG_001",
        },
        "list": [
            {
                "문항": "Synthetic 장문 상담",
                "list": [
                    {
                        "항목": "장문 테스트",
                        "audio": audio,
                    }
                ],
            }
        ],
    }


def test_long_transcript_conversion():
    """
    긴 상담 데이터도 모든 Q/A 발화를
    누락 없이 Transcript로 변환해야 한다.
    """

    raw = make_long_consultation(
        count=100
    )

    transcript = aihub_to_transcript(
        raw
    )

    # Q 100개 + A 100개
    assert len(transcript.segments) == 200

    assert (
        transcript.segments[0].segment_id
        == "seg_001"
    )

    assert (
        transcript.segments[-1].segment_id
        == "seg_200"
    )

    # AI-HUB Q → 내부 COUNSELOR
    assert (
        transcript.segments[0].speaker
        == "COUNSELOR"
    )

    # AI-HUB A → 내부 CHILD
    assert (
        transcript.segments[1].speaker
        == "CHILD"
    )


def test_invalid_aihub_json_missing_version():
    """
    필수 version이 없는 AI-HUB JSON은
    정상 입력으로 처리하면 안 된다.
    """

    invalid_raw = {
        "info": {
            "ID": "SYNTHETIC_INVALID_001",
        },
        "list": [],
    }

    with pytest.raises(
        ValidationError
    ):
        aihub_to_transcript(
            invalid_raw
        )


def test_invalid_aihub_json_missing_timestamp():
    """
    audio에 필수 timestamp가 없으면
    ValidationError가 발생해야 한다.
    """

    invalid_raw = {
        "version": 1,
        "info": {
            "ID": "SYNTHETIC_INVALID_002",
        },
        "list": [
            {
                "문항": "테스트",
                "list": [
                    {
                        "항목": "테스트",
                        "audio": [
                            {
                                "type": "A",
                                "text": "테스트 답변",
                                "wave": "synthetic.wav",

                                # start 의도적으로 누락
                                "end": "00:02.000",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with pytest.raises(
        ValidationError
    ):
        aihub_to_transcript(
            invalid_raw
        )


@patch(
    "ai.services.summary_service.OpenAI"
)
def test_summary_output_is_based_on_transcript(
    mock_openai,
):
    """
    정상적인 LLM 응답이 Transcript의 내용을
    기반으로 반환되는지 기본 검증한다.

    실제 환각 품질 평가는 별도 평가 단계에서 수행한다.
    """

    raw = {
        "version": 1,
        "info": {
            "ID": "SYNTHETIC_GROUNDING_001",
        },
        "list": [
            {
                "문항": "학교생활",
                "list": [
                    {
                        "항목": "학교생활",
                        "audio": [
                            {
                                "type": "Q",
                                "text": "학교생활은 어때?",
                                "wave": "synthetic.wav",
                                "start": "00:00.000",
                                "end": "00:02.000",
                            },
                            {
                                "type": "A",
                                "text": (
                                    "수학 숙제가 많아서 "
                                    "힘들어요."
                                ),
                                "wave": "synthetic.wav",
                                "start": "00:03.000",
                                "end": "00:05.000",
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

    # 현재 Summary Structured Output 형식
    mock_key_point = KeyPointItem(
        point="수학 숙제가 많아서 힘들다고 말했다.",
        segment_ids=["seg_002"],
    )

    mock_summary = MagicMock()
    mock_summary.overview = (
        "아동은 수학 숙제가 많아 "
        "힘들다고 말했다."
    )
    mock_summary.key_points = [
        mock_key_point
    ]

    mock_parsed = MagicMock()
    mock_parsed.schema_version = "1.0"
    mock_parsed.summary = mock_summary
    mock_parsed.risk_utterances = []
    mock_parsed.abuse_signals = []
    mock_parsed.risk_factors = []
    mock_parsed.warnings = []

    # 현재 summary_service.py는
    # response.choices[0].message.parsed 사용
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed

    mock_response = MagicMock()
    mock_response.choices = [
        mock_choice
    ]

    mock_client = MagicMock()

    # 현재 summary_service.py는
    # client.beta.chat.completions.parse 사용
    mock_client.beta.chat.completions.parse.return_value = (
        mock_response
    )

    mock_openai.return_value = mock_client

    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
        },
    ):
        result = summarize_consultation(
            transcript
        )

    source_text = " ".join(
        segment.text
        for segment in transcript.segments
    )

    # 핵심 사실이 실제 Transcript에 존재하는지 확인
    assert "수학 숙제" in source_text
    assert "수학 숙제" in result.summary.overview

    # 근거 segment_id가 유지되는지 확인
    assert (
        result.summary.key_points[0].segment_ids
        == ["seg_002"]
    )

    # 현재 요약 단계에서는 위험 분석 금지
    assert result.risk_utterances == []
    assert result.abuse_signals == []
    assert result.risk_factors == []

    