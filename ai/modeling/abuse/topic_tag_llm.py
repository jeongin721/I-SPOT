"""
회차 대화 주제 분류 LLM 모듈(2026-10-29). 상담 이력 '지금까지 상담' 의 **주제 비중** · '덜 다룬 부분' 과
상담 전 브리핑 '먼저 볼 것' 의 **처음 나온 이야기**(10/29 디자인)의 재료다.

[무엇을 하나]

이번 회차의 **아동 발화**(speaker CHILD)를 정해 둔 주제 목록(TOPICS) 안에서 나눈다. 결과는 주제마다
근거 발화 segment_ids 다. 비중 · 첫 언급은 회차 사이 계산이라 Backend(signal-history) · 화면이 한다 —
이 모듈은 회차 하나만 본다.

[왜 주제 목록을 고정하나]

회차 사이에서 같은 주제를 맞춰 세야 비중 · '처음 나온 이야기' 가 나온다. 2차 모델의 세부 유형처럼
LLM 이 매번 문구를 지으면 회차 간 줄을 맞추기 어렵다(signal-history 세부 신호 행렬 때 겪은 문제).
그래서 LLM 은 TOPICS 의 이름만 고르고, 목록 밖 이름은 코드가 버린다.

[코드 검사(_clean_tags)]
- topic 이 TOPICS 에 없다 → 버림
- segment_ids 가 아동 발화 목록에 없다 → 그 ID 만 버림, 남는 게 없으면 그 주제 버림
- 같은 주제가 여러 번 오면 합친다. 결과는 TOPICS 순서.
- 대표 발화(quote): 그 주제의 첫 근거 발화 원문(마스킹 전) 앞 80자와 start_ms. 화면이 그대로 보인다.

[개인정보]
아동 발화를 mask_for_outbound 로 가린 글만 LLM 에 보낸다(infer_audio_session 이 마스킹해서 넘김).
LLM 답에는 주제 이름 · segment_id 만 쓰므로 복원할 것이 없다. quote 는 원본 발화에서 꺼낸다 —
다른 결과 필드(risk_utterances 등)와 같이 분석 결과에만 남는다.

[실패]
아래는 모두 None — '분류하지 못함' 이다(빈 목록 [] 은 '분류했지만 해당 주제 없음'). 분석 전체를 멈추지 않는다.
- 아동 발화 마스킹이 막히거나 실패함(mask_child_lines — 아동 줄만 모은 글은 앞 단계 글과 입력이 달라 비식별 검사 결과가
  다를 수 있다. 민규 #122 리뷰: 이 하나 때문에 요약 · 확인 메모까지 된 분석이 실패하면 안 된다)
- LLM 이 실패하거나 마감 전에 못 끝냄
- LLM 이 주제를 냈는데 검사에서 하나도 남지 않음(목록 밖 이름뿐 · 아동 발화가 아닌 번호뿐) — 분류 실패에 가깝다

openai 는 CI 에 없다. 검사 함수를 backend/tests 에서 시험할 수 있게 LLM 호출 쪽 import 는 함수 안에 둔다.
"""

import time
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI

#: 대화 주제(화면에 그대로 보이는 이름). 순서가 결과 순서다. 바꾸면 이전 회차와 비교가 끊기니 이름은 고치지 말고 더한다.
TOPICS = (
    "학교생활",
    "친구 관계",
    "보호자 관계",
    "형제 · 가족",
    "신체 체벌 경험",
    "두려움 · 정서",
    "식사 · 돌봄",
    "성 관련 경험",
    "건강 · 병원",
    "놀이 · 일상",
)

#: LLM 에 보내는 아동 발화 글 최대 길이. 넘으면 뒤를 자른다(한 회차 상담은 보통 이 안에 든다).
MAX_INPUT_CHARS = 12000
#: 대표 발화 길이.
QUOTE_CHARS = 80
#: 마감 직전 이만큼은 남겨 두고 포기한다(followup_question_llm 과 같은 값).
DEADLINE_MARGIN_SECONDS = 1.0

CHILD_SPEAKER = "CHILD"


SYSTEM_PROMPT = """너는 아동보호전문기관 상담 기록에서 **아동이 한 말의 주제**를 나누는 도우미다.
결과는 상담사가 회차별 대화 흐름(어떤 이야기를 얼마나 했는지)을 보는 참고 자료다. 학대 여부를 판단하지 않는다.

[주제 목록 — 이 이름만 쓴다]
{topics}

[규칙]
1. 아래 입력의 아동 발화 줄마다, 그 줄이 다루는 주제를 위 목록에서 고른다. 한 줄에 주제는 최대 2개.
2. 인사 · 대답만 하는 말("네", "몰라요", "응")처럼 주제가 없는 줄은 어디에도 넣지 않는다.
3. 줄에 실제로 나온 내용으로만 고른다. 짐작하거나 숨은 뜻을 읽지 않는다.
   예: "밥도 안 줄 때가 있어요" → 식사 · 돌봄. "아빠가 화났어요" → 보호자 관계.
   "때렸어요" 처럼 맞은 이야기는 신체 체벌 경험, "무서웠어요" 처럼 감정은 두려움 · 정서.
4. 목록에 맞는 주제가 없으면 그 줄은 넣지 않는다. 새 주제 이름을 만들지 않는다.
5. 줄 앞의 [seg_001] 같은 segment_id 를 정확히 인용한다.

[입력 — 이번 상담의 아동 발화]
{child_lines}

반드시 아래 JSON 형식으로만 답한다:
{{
  "tags": [
    {{"topic": "주제 이름", "segment_ids": ["seg_001", "seg_004"]}}
  ]
}}
"""


def child_segments(segments: Any) -> List[Dict[str, Any]]:
    """발화 목록에서 아동 발화(글이 있는 것)만."""

    if not isinstance(segments, list):
        return []

    return [
        segment
        for segment in segments
        if isinstance(segment, dict)
        and segment.get("speaker") == CHILD_SPEAKER
        and str(segment.get("segment_id") or "").strip()
        and str(segment.get("text") or "").strip()
    ]


def format_child_lines(segments: Any) -> str:
    """LLM 입력(마스킹 전): 아동 발화를 '[seg_001] 글' 줄로. MAX_INPUT_CHARS 를 넘으면 뒤 줄을 뺀다."""

    lines: List[str] = []
    total = 0

    for segment in child_segments(segments):
        line = f"[{segment['segment_id']}] {' '.join(str(segment['text']).split())}"

        if total + len(line) + 1 > MAX_INPUT_CHARS:
            break

        lines.append(line)
        total += len(line) + 1

    return "\n".join(lines)


def mask_child_lines(mask_fn: Any, segments: Any, known_identifiers: Any = None) -> Optional[str]:
    """아동 발화 줄(format_child_lines)을 mask_fn(privacy_gateway.mask_for_outbound)으로 가린 글. 막히거나 실패하면 None.

    mask_fn 을 받아 쓰는 까닭: privacy_gateway 는 NER 모델을 불러와 CI 에서 import 할 수 없다. 이 함수를 가짜 함수로 시험한다.
    """

    try:
        masked, _ = mask_fn(format_child_lines(segments), known_identifiers=known_identifiers)
    except Exception:
        return None

    return masked if isinstance(masked, str) else None


def _clean_tags(raw_tags: Any, segments: Any) -> List[Dict[str, Any]]:
    """LLM 이 낸 주제를 모듈 docstring 의 검사로 거른다."""

    if not isinstance(raw_tags, list):
        return []

    child_by_id = {str(segment["segment_id"]): segment for segment in child_segments(segments)}
    order = {segment_id: index for index, segment_id in enumerate(child_by_id)}
    merged: Dict[str, List[str]] = {}

    for item in raw_tags:
        if not isinstance(item, dict):
            continue

        topic = item.get("topic")

        if not isinstance(topic, str) or topic.strip() not in TOPICS:
            continue

        topic = topic.strip()
        raw_ids = item.get("segment_ids")

        if not isinstance(raw_ids, list):
            continue

        ids = merged.setdefault(topic, [])

        for segment_id in raw_ids:
            if isinstance(segment_id, str) and segment_id in child_by_id and segment_id not in ids:
                ids.append(segment_id)

    tags: List[Dict[str, Any]] = []

    for topic in TOPICS:
        ids = sorted(merged.get(topic, []), key=lambda segment_id: order[segment_id])

        if not ids:
            continue

        first = child_by_id[ids[0]]
        quote = " ".join(str(first.get("text") or "").split())
        start_ms = first.get("start_ms")

        tags.append(
            {
                "topic": topic,
                "segment_ids": ids,
                "quote": quote if len(quote) <= QUOTE_CHARS else quote[:QUOTE_CHARS] + "…",
                "start_ms": start_ms if isinstance(start_ms, int) and not isinstance(start_ms, bool) else None,
            }
        )

    return tags


# ------------------------------------------------------------
# LLM 호출
# ------------------------------------------------------------


def generate_topic_tags_from_masked_text(
    client: "OpenAI",
    model: str,
    masked_child_lines: str,
    segments: Any,
    deadline: Optional[float] = None,
) -> Optional[List[Dict[str, Any]]]:
    """masked_child_lines: format_child_lines → mask_for_outbound 결과. segments: 원본 발화 목록(검사 · 대표 발화).

    아동 발화가 없으면 [](분류할 것 없음), 실패하면 None.
    """

    if not masked_child_lines.strip():
        return []

    system_prompt = SYSTEM_PROMPT.format(
        topics="\n".join(f"- {topic}" for topic in TOPICS),
        child_lines=masked_child_lines,
    )

    try:
        from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 아동 발화를 주제 목록으로 나눠.",
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
        )
    except Exception:
        return None

    if not isinstance(parsed, dict) or not isinstance(parsed.get("tags"), list):
        return None

    raw_tags = parsed.get("tags")

    try:
        tags = _clean_tags(raw_tags, segments)
    except Exception:
        return None

    # 주제를 냈는데 하나도 남지 않으면(목록 밖 이름뿐 등) '해당 주제 없음' 이 아니라 분류 실패로 본다(민규 #122 리뷰).
    return None if raw_tags and not tags else tags


def wait_for_topic_tags(future: "Future", deadline: Optional[float]) -> Optional[List[Dict[str, Any]]]:
    """병렬로 띄운 주제 분류를 마감 전까지만 기다린다. 늦거나 실패하면 None(분류하지 못함)."""

    timeout = None if deadline is None else max(0.0, deadline - time.monotonic() - DEADLINE_MARGIN_SECONDS)

    try:
        result = future.result(timeout=timeout)
    except Exception:
        future.cancel()
        return None

    return result if isinstance(result, list) else None
