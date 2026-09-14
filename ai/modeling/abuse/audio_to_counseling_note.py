"""
음성 파일을 STT로 변환한 뒤 상담 요약과 상담일지를 생성한다.
현재는 STT 결과를 LLM에 전달해 summary/note를 만드는 단일 파일 테스트용 스크립트다.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict

from openai import OpenAI


# ============================================================
# 기본 설정
# ============================================================

DEFAULT_MODEL = os.getenv(
    "COUNSELING_NOTE_MODEL",
    "gpt-5.6-luna",
)


# ============================================================
# 상담 기록 생성 프롬프트
# ============================================================

SYSTEM_PROMPT = """
당신은 아동 상담 대화 기록을 상담사가 활용할 수 있는
'상담 요약'과 '상담 일지'로 정리하는 도우미다.

반드시 입력된 상담 대화에서 확인할 수 있는 사실만 사용한다.

[공통 원칙]

1. 원문에 없는 사건, 감정, 원인, 빈도, 기간, 피해 정도를 추가하지 않는다.
2. 학대 여부나 학대 유형을 판단하지 않는다.
3. "신체학대", "정서학대", "성학대", "방임", "학대 의심",
   "위험도가 높다"와 같은 판정 표현을 사용하지 않는다.
4. 상담사 질문 자체를 사실로 간주하지 않는다.
   내담자의 답변과 실제 진술을 중심으로 작성한다.
5. 부정 진술을 긍정적인 사실로 바꾸지 않는다.
6. 행위자, 시점, 빈도, 피해 결과가 원문에 있다면 가능한 한 유지한다.
7. 서로 다른 사건을 하나의 사건으로 합치지 않는다.

[상담 요약]

- 상담사가 빠르게 전체 상담 내용을 파악할 수 있도록 간결하게 작성한다.
- 주요 가족관계, 학교생활, 정서 상태, 생활환경, 주요 사건 등을 요약한다.
- 중요한 사실을 지나치게 축약하여 의미를 잃지 않는다.
- 3~6문장 정도의 자연스러운 문단으로 작성한다.

[상담 일지]

- 상담사가 상담 종료 후 작성한 객관적인 기록처럼 작성한다.
- 상담 전체의 흐름을 유지한다.
- 일반적인 상담 내용과 주요 사건을 함께 기록한다.
- "~라고 진술함.", "~라고 하였음.", "~라고 답함." 등의 중립적 문체를 사용한다.
- Q&A 형식으로 그대로 나열하지 않는다.

[출력 형식]

반드시 아래 JSON 형식만 반환한다.

{
  "counseling_summary": "...",
  "counseling_note": "..."
}
"""


# ============================================================
# OpenAI 응답 처리
# ============================================================

def parse_json_response(text: str) -> Dict[str, str]:
    """
    LLM 응답을 JSON으로 변환한다.
    """
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return json.loads(text)


# ============================================================
# STT
# ============================================================

def transcribe_audio(
    client: OpenAI,
    audio_path: Path,
) -> str:
    """
    음성 파일을 텍스트로 변환한다.

    현재는 OpenAI STT를 사용한다.
    화자 분리는 다음 단계에서 별도로 붙일 수 있다.
    """
    with audio_path.open("rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )

    return transcript.text.strip()


# ============================================================
# 상담 요약 + 상담일지 생성
# ============================================================

def generate_counseling_records(
    client: OpenAI,
    transcript: str,
    model: str,
) -> Dict[str, str]:
    """
    STT transcript를 상담 요약과 상담일지로 변환한다.
    """

    user_prompt = f"""
다음은 아동 상담 음성을 STT로 변환한 기록이다.

이 기록을 바탕으로
1. 상담 요약
2. 상담 일지

두 가지를 작성하라.

[STT 기록]

{transcript}
"""

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=user_prompt,
    )

    result = parse_json_response(
        response.output_text
    )

    summary = result.get(
        "counseling_summary",
        "",
    ).strip()

    note = result.get(
        "counseling_note",
        "",
    ).strip()

    if not summary:
        raise ValueError(
            "counseling_summary가 비어 있습니다."
        )

    if not note:
        raise ValueError(
            "counseling_note가 비어 있습니다."
        )

    return {
        "counseling_summary": summary,
        "counseling_note": note,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "음성 파일 → STT → 상담 요약 + 상담일지"
        )
    )

    parser.add_argument(
        "--audio",
        required=True,
        help="음성 파일 경로",
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="상담 기록 생성용 LLM 모델",
    )

    args = parser.parse_args()

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY 환경변수가 없습니다."
        )

    audio_path = Path(
        args.audio
    )

    if not audio_path.exists():
        raise FileNotFoundError(
            f"음성 파일을 찾을 수 없습니다: {audio_path}"
        )

    client = OpenAI(
        api_key=api_key
    )

    # ========================================================
    # 1. STT
    # ========================================================

    print("=" * 80)
    print("[1/2] STT 변환 중...")
    print("=" * 80)

    transcript = transcribe_audio(
        client=client,
        audio_path=audio_path,
    )

    print("\n[STT 결과]\n")
    print(transcript)

    # ========================================================
    # 2. 상담 요약 + 상담일지
    # ========================================================

    print("\n" + "=" * 80)
    print("[2/2] 상담 요약 + 상담일지 생성 중...")
    print("=" * 80)

    result = generate_counseling_records(
        client=client,
        transcript=transcript,
        model=args.model,
    )

    print("\n[상담 요약]\n")
    print(
        result["counseling_summary"]
    )

    print("\n" + "=" * 80)
    print("[상담 일지]\n")
    print(
        result["counseling_note"]
    )

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()