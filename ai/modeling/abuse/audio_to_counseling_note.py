"""
STT 결과를 LLM에 전달해 상담 요약과 상담일지를 생성한다.

[2026-10-16: CLI 제거 — Mingyu 리뷰]

원래 이 파일은 음성 파일→STT(OpenAI)→상담 요약/일지까지 한 번에
돌리는 로컬 CLI(transcribe_audio, main)도 겸하고 있었다. 그 CLI는
STT 원문을 콘솔에 그대로 찍고(print(transcript)) mask_for_outbound
없이 바로 LLM에 넘겨, 실제 녹음으로 돌리면 원문이 터미널 기록과
OpenAI 양쪽으로 그대로 나간다. backend 서버 경로는 이 파일의
generate_counseling_records()만 쓰고(호출 전에 이미
mask_for_outbound를 거친 글을 받는다) STT를 직접 하지 않으므로,
main에 올라가는 이 버전에서는 CLI 전체를 뺐다. CLI가 필요하면
ai-modeling 브랜치의 원본을 쓰면 된다.
"""

import json
import os
import threading
from typing import Dict, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import (
    _call_llm_with_retry,
)


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
# 상담 요약 + 상담일지 생성
# ============================================================

def generate_counseling_records(
    client: OpenAI,
    transcript: str,
    model: str,
    deadline: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
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

    result = _call_llm_with_retry(
        client=client,
        model=model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        deadline=deadline,
        stop_event=stop_event,
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