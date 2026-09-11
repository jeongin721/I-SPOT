# 실제 OpenAI API 호출 없이 Mock LLM 결과로 전체 AI 파이프라인을 직접 실행한다.
# Transcript, Summary, Evidence 연결 결과를 터미널에서 눈으로 확인하기 위한 데모 파일이다.

import json
from unittest.mock import patch

from ai.adapters.aihub_transcript import aihub_to_transcript
from ai.schemas.analysis import (
    AIAnalysisOutput,
    Summary,
)
from ai.services.analysis_pipeline import (
    run_analysis_pipeline,
)


SAMPLE = {
    "version": 1,
    "info": {
        "ID": "SYNTHETIC_MOCK_DEMO_001"
    },
    "list": [
        {
            "문항": "학교 및 가정생활",
            "list": [
                {
                    "항목": "상담",
                    "audio": [
                        {
                            "type": "Q",
                            "text": "학교생활은 요즘 어때?",
                            "wave": "synthetic.wav",
                            "start": "00:00.000",
                            "end": "00:02.000",
                        },
                        {
                            "type": "A",
                            "text": "수학 숙제가 많아서 요즘 조금 힘들어요.",
                            "wave": "synthetic.wav",
                            "start": "00:03.000",
                            "end": "00:06.000",
                        },
                        {
                            "type": "Q",
                            "text": "집에서는 어떻게 지내?",
                            "wave": "synthetic.wav",
                            "start": "00:07.000",
                            "end": "00:09.000",
                        },
                        {
                            "type": "A",
                            "text": "동생이랑 가끔 싸우지만 엄마랑 이야기를 많이 해요.",
                            "wave": "synthetic.wav",
                            "start": "00:10.000",
                            "end": "00:14.000",
                        },
                        {
                            "type": "Q",
                            "text": "요즘 특별히 걱정되는 건 있어?",
                            "wave": "synthetic.wav",
                            "start": "00:15.000",
                            "end": "00:17.000",
                        },
                        {
                            "type": "A",
                            "text": "숙제 말고는 딱히 없어요.",
                            "wave": "synthetic.wav",
                            "start": "00:18.000",
                            "end": "00:20.000",
                        },
                    ],
                }
            ],
        }
    ],
}


MOCK_LLM_RESULT = AIAnalysisOutput(
    schema_version="1.0",
    summary=Summary(
        overview=(
            "아동은 수학 숙제가 많아 힘들다고 말했으며, "
            "동생과 가끔 다투지만 어머니와는 이야기를 많이 한다고 말했다."
        ),
        key_points=[
            "수학 숙제가 많아서 힘들다고 말했다.",
            "동생과 가끔 싸운다고 말했다.",
            "엄마와 이야기를 많이 한다고 말했다.",
            "숙제 외에는 특별히 걱정되는 것이 없다고 말했다.",
        ],
    ),
    risk_utterances=[],
    abuse_signals=[],
    risk_factors=[],
    warnings=[],
)


def print_transcript(transcript):
    print("\n" + "=" * 70)
    print("1. AI-HUB JSON → I-SPOT Transcript")
    print("=" * 70)

    for segment in transcript.segments:
        print(
            f"[{segment.segment_id}] "
            f"{segment.speaker:<10} "
            f"{segment.start_ms:>6}ms ~ "
            f"{segment.end_ms:>6}ms"
        )

        print(
            f"    {segment.text}"
        )


def print_summary(result):
    print("\n" + "=" * 70)
    print("2. MOCK LLM SUMMARY")
    print("=" * 70)

    print("\n[Overview]")
    print(
        result.analysis.summary.overview
    )

    print("\n[Key Points]")

    for index, point in enumerate(
        result.analysis.summary.key_points,
        start=1,
    ):
        print(
            f"{index}. {point}"
        )


def print_evidence(result, transcript):
    print("\n" + "=" * 70)
    print("3. SUMMARY → EVIDENCE SEGMENT LINK")
    print("=" * 70)

    segment_map = {
        segment.segment_id: segment
        for segment in transcript.segments
    }

    for index, evidence in enumerate(
        result.summary_evidence,
        start=1,
    ):
        print(
            f"\n[Key Point {index}]"
        )

        print(
            f"요약: {evidence.text}"
        )

        print(
            f"score: {evidence.score:.3f}"
        )

        if not evidence.segment_ids:
            print(
                "근거: 연결된 segment 없음"
            )
            continue

        print(
            f"근거 segment: "
            f"{evidence.segment_ids}"
        )

        for segment_id in (
            evidence.segment_ids
        ):
            segment = segment_map[
                segment_id
            ]

            print(
                f"  → [{segment.segment_id}] "
                f"{segment.speaker}: "
                f"{segment.text}"
            )


def print_analysis_json(result):
    print("\n" + "=" * 70)
    print("4. FINAL PIPELINE RESULT")
    print("=" * 70)

    print(
        json.dumps(
            result.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )


def print_warnings(result):
    print("\n" + "=" * 70)
    print("5. WARNINGS")
    print("=" * 70)

    if not result.analysis.warnings:
        print(
            "없음"
        )
        return

    for warning in (
        result.analysis.warnings
    ):
        print(
            f"- {warning}"
        )


def main():
    transcript = aihub_to_transcript(
        SAMPLE
    )

    print_transcript(
        transcript
    )

    # 실제 OpenAI 호출 대신
    # summarize_consultation() 결과를 Mock 처리
    with patch(
        "ai.services.analysis_pipeline."
        "summarize_consultation",
        return_value=MOCK_LLM_RESULT,
    ):
        result = run_analysis_pipeline(
            transcript
        )

    print_summary(
        result
    )

    print_evidence(
        result,
        transcript,
    )

    print_analysis_json(
        result
    )

    print_warnings(
        result
    )


if __name__ == "__main__":
    main()