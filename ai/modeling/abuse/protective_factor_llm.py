"""
"회차 경과" 화면(상담사 웹 목업 _3.html, 2026-10-08)의 "보호 요인" 행에 쓸
LLM 모듈 초안이다.

**검수 전 초안이다.** 아래 PROTECTIVE_FACTOR_DEFINITIONS 5개 범주는
`docs/subtype_rubric_v1.md`의 위험신호 14종처럼 판례집 같은 외부 근거가
없다 — 법원 판례는 피해 사실을 다루지, 보호 요인을 분류해 놓지 않기
때문이다. 그래서 전부 "우리 분류 정의"이고, 도메인 지식이 있는 쪽(모델링
팀)이 범주 자체를 검수해야 실제로 쓸 수 있다.

2026-10-12 1차 검수에서 4개 범주 → 5개로 조정됨(결정 내역):
- "안전 대처 행동"을 "사건 중 대처"(학대 도중의 즉각적 저항·도피)와
  "평소 대처 자원"(사건과 무관한 일상적 자기 진정 방법)으로 분리했다 —
  성학대 사건 도중의 저항 행동을 일반적인 "대처 자원"과 같이 묶으면
  사건의 심각성이 희석돼 보일 위험이 있다는 지적에 따른 것.
- "지지적 관계"에 가해자로 의심되는 대상 제외 규칙을 추가했다 —
  양가감정은 위험 평가 쪽에서 다룰 신호이지 보호 요인이 아니다.
- "정서적 자원"에 탈출·고통 맥락과 묶인 희망 진술 제외 규칙을
  추가했다 — 실제 테스트에서 "어른 되면 자유롭게 살고 싶다"가
  "집에 있기 싫다"와 함께 나왔는데 이걸 단순 희망으로 잘못 분류했다.
- "도움 요청·개방성"은 완전 자발적 진술만 인정하면 범주가 거의 항상
  비어 있을 수 있어서, 상담사의 열린 질문에 대한 적극적 응답까지
  포함하도록 완화했다(닫힌 질문 단답은 여전히 제외).

2026-10-12 2차 검수(AI-Hub 실제 상담 텍스트 3건으로 재테스트) — 2건 추가 수정:
- "도움 요청·개방성"이 1차 수정 후에도 너무 헐거웠다: 상담사의 표준
  문진 질문("맞은 적 있어?")에 사실대로 답한 것까지 전부 "개방성"으로
  잡아서, 사실상 모든 상담에서 항상 채워지는 의미 없는 범주가 됐다.
  "요청받지 않은 내용을 스스로 덧붙인 경우"로 다시 좁혔다.
- 실제 사례(1063)에서 아동이 "상담 요청했는데 이상한 애 취급당했다"고
  말한 게 "담임교사에게 상담을 요청한 적이 있다"는 깨끗한 긍정 문장
  으로만 나왔다 — 거부당한 맥락이 통째로 빠져서 위험하게 왜곡됨.
  상대방이 무시·거부한 경우는 그 결과를 함께 적지 않으면 아예
  포함하지 않도록 규칙 추가.

[설계 결정 — 왜 위험신호(second_stage_llm.py)와 다른 방식인가]

위험신호는 evidence_strength(법적/임상적 판단 강도)가 핵심이라
verify_evidence()로 원문 offset까지 정확히 맞춰 검증한다. 보호 요인은
그렇게 무거운 검증이 필요한 영역이 아니라고 판단해서, 대신 record_draft_llm.py의
"아동 진술 요지"와 같은 방식(LLM이 segment_id를 직접 인용 → 실제 segment
목록에 있는 id만 남기고 나머지는 버림)을 썼다. 이쪽이 더 가볍고, 이미
record_draft_llm.py에서 검증된 패턴이다.

[설계 결정 — 왜 위험 신호와 섞지 않고 별도 LLM 호출인가]

second_stage_llm.py의 SYSTEM_PROMPT_TEMPLATE은 이미 F1 튜닝이 끝난
프롬프트다. 여기에 "보호 요인도 같이 찾아줘"를 끼워 넣으면 위험신호
탐지 자체가 흔들릴 위험이 있다(이 프로젝트에서 _verify_major_types_qa를
기존 분석에 끼워 넣었다가 Macro F1이 0.90→0.57로 떨어진 전례가 있음 —
infer_abuse_pipeline.py 참고). 그래서 record_draft_llm.py처럼 완전히
분리된 모듈/호출로 만들었다.
"""

from typing import Any, Dict, List, Optional

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


# ============================================================
# 1. 보호 요인 범주 정의 (초안 — 모델링 팀 검수 필요)
# ============================================================

PROTECTIVE_FACTOR_DEFINITIONS: Dict[str, str] = {
    "지지적 관계": (
        "가족 안팎(형제, 조부모, 친척)이나 또래, 교사 등 아동이 "
        "긍정적으로 느끼는 관계가 구체적으로 언급된 경우. 예: "
        "'동생이 깨면 같이 있어 줘요', '민지가 잘 그렸다고 했어요'. "
        "단순히 그 사람이 존재한다는 사실만으로는 선택하지 않는다 — "
        "아동이 그 관계를 긍정적으로 느낀다는 표현이 있어야 한다. "
        "원문에서 아동을 때리거나 위협하거나 학대했다고 진술된 바로 "
        "그 대상에 대한 긍정적 언급(예: '가끔 잘해줄 때도 있어요')은 "
        "이 범주에 넣지 않는다 — 가해자로 의심되는 대상과의 양가적 "
        "감정은 보호 요인이 아니라 위험 평가 쪽에서 별도로 다뤄야 한다."
    ),
    "도움 요청·개방성": (
        "아동이 **요청받지 않은** 내용을 스스로 꺼내서 어려움을 "
        "말하려는 의지를 보이거나, 실제로 상담사·보호자·또래에게 "
        "먼저 털어놓은 경우. 예: '선생님한테 말하고 싶은데 말이 안 "
        "나와', 상담 중 스스로 먼저 어려운 이야기를 꺼낸 경우, 또는 "
        "상담사의 열린 질문('더 하고 싶은 말 있어?')에 질문이 요구한 "
        "범위를 넘어서는 새로운 내용을 적극적으로 덧붙인 경우. "
        "상담사가 학대·위험 여부를 직접 묻는 표준 문진 질문(예: "
        "'맞은 적 있어?', '힘든 점이 뭐야?', '그때 기분이 어땠어?')에 "
        "사실대로 답한 것은 — 그 답이 아무리 상세하고 솔직해도 — "
        "그 자체만으로는 포함하지 않는다. 이건 상담 프로토콜에 따른 "
        "정상적인 응답이지 아동이 자발적으로 보인 개방성이 아니다. "
        "'네'/'아니요' 같은 단답은 당연히 포함하지 않는다. 아동이 "
        "말했지만 상대방이 무시하거나 거부·비난한 경우(예: '찾아갔는데 "
        "이상한 애 취급당했어요')는 그 결과를 text에 함께 적지 않는 "
        "한 포함하지 않는다 — 거부당한 시도를 깨끗한 긍정 신호처럼 "
        "보이게 왜곡해서는 안 된다."
    ),
    "사건 중 대처": (
        "학대·위협 상황이 벌어지는 바로 그 순간에 아동이 취한 즉각적인 "
        "자기 보호 행동. 예: '동생 이름 부르고 발로 찼어요', 소리를 "
        "지른 행동, 그 자리에서 도망치거나 밀어낸 행동. 사건이 끝난 "
        "뒤에 한 행동(신고, 대처, 털어놓기 등)은 여기 넣지 않고 "
        "'도움 요청·개방성'이나 '평소 대처 자원' 쪽에서 다룬다. 이 "
        "범주는 아동이 수동적으로 당하지만은 않았다는 사실만 기록하는 "
        "것이며, 대처가 효과적이었는지나 아동이 '잘 대처했다'는 평가를 "
        "담지 않는다 — 이 범주가 사건의 심각성을 낮춰 보이게 해서는 "
        "안 된다."
    ),
    "평소 대처 자원": (
        "학대·위협 상황과 무관하게, 아동이 평소 힘들 때 스스로를 "
        "다스리는 방법. 예: '일기를 써요', '혼자 음악을 들어요'. "
        "다른 사람에게 말하는 방식이면 '도움 요청·개방성'으로 분류하고, "
        "이 범주는 사람에게 말하지 않고 혼자 하는 방법에 한정한다."
    ),
    "정서적 자원": (
        "아동이 즐거움·몰입을 느끼는 활동이나, 긍정적인 자기 인식을 "
        "구체적으로 말한 경우. 예: '만화책 읽을 때 시간이 빨리 가요', "
        "'친구 네 명이랑 공기놀이를 많이 해요'. 상담사의 유도성 질문"
        "(예: '요즘 괜찮아?')에 대한 단답('네')만으로는 선택하지 않는다. "
        "미래에 대한 희망적 진술('어른 되면 자유롭게 살고 싶다' 등)은 "
        "바로 앞뒤에 '집에 있기 싫다', '여기서 벗어나고 싶다' 같은 "
        "현재 상황에 대한 고통·회피 맥락이 함께 있으면 선택하지 않는다 "
        "— 그런 진술은 희망이 아니라 고통의 표현일 수 있다. 그런 맥락 "
        "없이 순수하게 긍정적인 미래상·꿈을 말한 경우에만 선택한다."
    ),
}

VALID_PROTECTIVE_FACTOR_TYPES = set(
    PROTECTIVE_FACTOR_DEFINITIONS.keys()
)


# ============================================================
# 2. 프롬프트
# ============================================================

SYSTEM_PROMPT = """너는 아동 상담 축어록에서 "보호 요인"을 구조화하는 분석기다.

[공통 원칙 — 위험신호 분석과 동일한 기준을 따른다]

1. 아동 본인이 직접 진술한 내용만 근거로 삼는다. 상담사 질문에 들어
   있는 내용을 아동이 확인(동의)하지 않았으면 근거가 아니다.
2. 원문에 없는 사실, 정도, 효과를 추가하지 않는다 — 과장하지 않는다.
3. 아동이 명확히 부인하거나 부정적으로 말한 내용은 보호 요인으로
   쓰지 않는다.
4. 문장마다 그 내용이 나온 축어록 줄의 segment_id를 정확히 인용한다.
   여러 줄에 걸쳐 있으면 segment_id를 여러 개 적어도 된다. 근거 없는
   문장은 만들지 않는다.
5. 하나의 진술이 여러 범주에 동시에 해당할 수 있다 — 각 범주마다
   독립된 근거가 있어야 한다.

[매우 중요 — 위험 신호와의 관계]

보호 요인이 있다고 해서 위험 신호가 없어지거나 약해지는 것이 아니다.
이 둘은 서로 다른 축이다. "아이가 또래 관계가 좋으니 학대가 심각하지
않다" 같은 식으로 해석되게 쓰지 않는다 — 보호 요인은 상담 계획에 쓸
자원일 뿐, 위험 평가를 상쇄하는 근거가 아니다.

[판단할 범주]

{category_definitions}

[출력 형식]

반드시 아래 JSON 형식으로만 답한다:
{{
  "protective_factor_points": [
    {{
      "category": "범주명",
      "text": "아동이 실제로 말한 내용을 요약한 짧은 문장",
      "segment_ids": ["seg_001"]
    }}
  ]
}}

해당하는 내용이 없으면 "protective_factor_points": [] 로 반환한다.
"""


def build_category_definition_text() -> str:
    lines: List[str] = []

    for category, definition in (
        PROTECTIVE_FACTOR_DEFINITIONS.items()
    ):
        lines.append(f"- {category}: {definition}")

    return "\n".join(lines)


# ============================================================
# 3. 검증 및 정리
# ============================================================

def _clean_points(
    raw_points: Any,
    valid_segment_ids: set,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_points, list):
        return []

    cleaned = []

    for item in raw_points:
        if not isinstance(item, dict):
            continue

        text = item.get("text")
        category = item.get("category")

        if not isinstance(text, str) or not text.strip():
            continue

        if category not in VALID_PROTECTIVE_FACTOR_TYPES:
            continue

        segment_ids = [
            str(sid)
            for sid in (item.get("segment_ids") or [])
            if isinstance(sid, (str, int))
            and str(sid) in valid_segment_ids
        ]

        if not segment_ids:
            # 근거 없는 보호 요인은 버린다 — record_draft_llm.py의
            # child_statement_points는 이 체크가 없지만, 보호 요인은
            # "위험 신호를 상쇄하는 근거"로 오해될 소지가 있어 더
            # 엄격하게 segment_id 없는 항목은 제외한다.
            continue

        cleaned.append(
            {
                "category": category,
                "text": text.strip(),
                "segment_ids": segment_ids,
            }
        )

    return cleaned


# ============================================================
# 4. 진입점
# ============================================================

def generate_protective_factors(
    client: OpenAI,
    model: str,
    masked_transcript_text: str,
    segments: List[Dict[str, Any]],
    deadline: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    masked_transcript_text: record_draft_llm.build_transcript_citation_text()로
    만들고 호출부가 mask_for_outbound()로 마스킹한 문자열을 그대로 재사용한다
    (새 포맷을 또 만들지 않는다).
    segments: 원본 segment 목록 — segment_id 검증에만 쓴다.
    """

    valid_segment_ids = {
        str(segment.get("segment_id", "")) for segment in segments
    }

    if not masked_transcript_text.strip():
        return []

    system_prompt = SYSTEM_PROMPT.format(
        category_definitions=build_category_definition_text()
    )
    user_prompt = f"[축어록]\n\n{masked_transcript_text}"

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=2,
            timeout_seconds=180.0,
            deadline=deadline,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return _clean_points(
        parsed.get("protective_factor_points"),
        valid_segment_ids,
    )


# ============================================================
# 5. 데모
# ============================================================

if __name__ == "__main__":
    from ai.modeling.abuse.llm_backend import (
        build_openai_client_and_model,
    )

    text = (
        "[seg_001] CHILD: 민지가 그림 잘 그렸다고 했어요.\n"
        "[seg_002] CHILD: 무서울 때 동생 이름 부르고 발로 찼어요.\n"
        "[seg_003] CHILD: 선생님한테 말하고 싶은데 말이 안 나와요.\n"
    )

    segments = [
        {"segment_id": "seg_001"},
        {"segment_id": "seg_002"},
        {"segment_id": "seg_003"},
    ]

    client, model = build_openai_client_and_model(
        DEFAULT_MODEL
    )

    result = generate_protective_factors(
        client=client,
        model=model,
        masked_transcript_text=text,
        segments=segments,
    )

    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))
