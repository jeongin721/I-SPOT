"""
"회차 경과" 화면의 "감소 진술"/"악화 진술" 표시에 쓸 LLM 모듈 초안이다.

**검수 전 초안이다.** protective_factor_llm.py와 마찬가지로 아직
infer_audio_session.py/case_store.py/API 라우트 어디에도 연결 안 돼
있다 — 프롬프트 자체만 먼저 만들고 검수한다.

[이 모듈이 하는 일]

같은 세부유형에 대해, 이전 승인 회기의 근거 발화와 이번 회기의 근거
발화를 LLM에 같이 주고 "다시 언급 / 감소 / 악화 / 불명확" 중 하나로
분류하게 한다. case_store.get_case_trend()는 "이번 세션에 이 대분류가
탐지됐는지"만 보는 순수 집계라 이 비교를 못 한다 — 발화 두 개의
의미를 견줘야 하는 일이라 여기서만 LLM이 필요하다.

[가장 중요한 설계 원칙 — 왜 "감소"가 "호전"이 아닌가]

진술이 줄었다고 실제 위험이 줄었다는 뜻이 아니다. 이유는 여러 가지일
수 있다: 실제로 상황이 나아졌을 수도 있고, 보복이 두려워 축소
보고했을 수도 있고, 상담사를 아직 신뢰하지 않아 말을 아꼈을 수도
있고, 단순히 이번 회기에 그 화제가 깊게 안 나왔을 수도 있다. 이
모듈은 "텍스트가 이렇게 다르다"는 관찰만 하지, 왜 다른지는 추측하지
않는다. case_store.get_case_trend()의 설계 원칙(해석은 상담사 몫)을
그대로 따른다.

같은 이유로 "악화" 범주를 새로 추가했다 — 원래 _3.html 목업 디자인엔
"감소 진술"만 있었는데, 진술이 더 심해진 경우를 놓치면 안 되고
오히려 그쪽이 임상적으로 더 중요할 수 있다(2026-10-12 설계 논의).

[설계 결정 — 왜 "새로 언급"/"미언급"은 여기서 안 다루는가]

이전 회기에 그 세부유형 자체가 전혀 없었거나(새로 언급), 이번
회기에 전혀 안 나왔다면(미언급) 비교할 발화 쌍이 없다 — 이건 그냥
존재 여부 비교라 코드로 끝나고 LLM이 필요 없다(case_store.py 참고).
이 모듈은 "이전에도 있었고 이번에도 있는" 경우에만 호출한다.

2026-10-12 1차 검수(AI-Hub 실제 상담 텍스트에서 "예전엔 vs 지금은"
대조 발화 35건 중 3건으로 테스트): 방임 사례에서 "예전에는 그냥
참았는데 계속 안 줘서 요즘엔 소리 지르고 물건도 막 던져요"를
"악화"로 판정했는데, reason이 방임 행위 자체가 아니라 **아동의
반응**(소리 지름, 물건 던짐)을 근거로 들고 있었다 — 아동이 화를
더 낸다고 가해 행위 자체가 심해진 건 아니므로 원칙 7(가해 행위
자체만 비교, 아동 반응은 근거 아님)을 추가했다.

2026-10-12 2차 검수(가상의 4회차 사례 1~4회차 연속 비교 8건에서
"등을 몇 대 맞았어요" → "등이랑 팔을 몇 번 맞았어요"처럼 신체 부위
하나만 더 언급된 사소한 차이도 "악화"로 과민 반응하는 걸 발견) —
원칙 8(빈도·강도·도구·새 피해·지속 여부 중 뚜렷한 변화가 있어야
악화/감소로 판단)과 원칙 9("악화" vs "다시_언급" 사이 애매하면
"악화" 쪽으로, "감소" vs "다시_언급" 사이는 비대칭 적용 안 함 —
악화를 놓치는 게 거짓 경보보다 위험하다는 비대칭적 리스크 판단)를
추가했다. 기존 테스트 중 대표 6건(사소한 디테일 추가 1건 + 명백한
악화 2건 + 명백한 감소 1건 + 애매한 불명확 1건 + 다시_언급 1건)으로
수정 전후 A/B 비교한 결과, 문제였던 1건만 "다시_언급"으로 바로잡히고
나머지 5건은 전혀 안 바뀌어서(회귀 없음) 원칙 8·9를 채택했다.
"""

from typing import Any, Dict, List

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


VALID_CHANGE_LABELS = {
    "다시_언급",
    "감소",
    "악화",
    "불명확",
}


SYSTEM_PROMPT = """너는 같은 아동의 서로 다른 회기 사이에서, 같은 세부유형에
대한 진술이 어떻게 달라졌는지 관찰하는 분석기다. 판정이나 평가를
하는 게 아니라 텍스트 차이만 기술한다.

[공통 원칙]

1. 비교는 같은 세부유형 쌍 안에서만 한다. 다른 세부유형끼리는
   비교하지 않는다.
2. 원문에 없는 원인·의도·동기를 추측하지 않는다. "보복이 두려워서
   줄였다", "상태가 나아져서 줄었다" 같은 이유는 절대 쓰지 않는다
   — 왜 달라졌는지는 상담사가 판단할 몫이다.
3. "감소"는 "상황이 좋아졌다"는 뜻이 아니다. 단지 이번 회기의 진술이
   이전 회기보다 덜 구체적이거나, 심각성이 낮게 표현되거나, 더 이상
   일어나지 않는다고 말한 경우를 가리킨다. 반대로 "악화"는 이번 회기의
   진술이 이전보다 더 구체적이거나, 빈도·강도가 높아지거나, 새로운
   피해가 추가된 경우다.
4. 판단이 애매하면(예: 화제 자체가 다르거나, 비교할 만큼 구체적이지
   않은 경우) 억지로 "감소"나 "악화"로 정하지 말고 "불명확"으로
   분류한다.
5. "다시_언급"은 이전과 비슷한 수준·내용으로 반복해서 나온 경우다.
6. reason은 한 문장으로, 두 발화의 어떤 표현이 어떻게 다른지만
   사실 그대로 쓴다. 원인 추측이나 평가(좋아짐/나빠짐 등 가치
   판단)를 담지 않는다.
7. 비교 대상은 반드시 가해 행위·방임 상황 **자체**에 대한 진술이어야
   한다. 아동의 반응(화를 냄, 소리 지름, 울음, 체념 등 감정·행동
   반응)이 달라진 것만으로는 "악화"나 "감소"로 판단하지 않는다 —
   가해 행위 자체(빈도·강도·새로운 피해·지속 여부)가 어떻게
   달라졌는지에만 근거한다. 두 발화 중 하나라도 가해 행위 자체가
   아니라 아동의 반응만 담고 있다면 "불명확"으로 분류한다.
8. "악화"나 "감소"로 판단하려면 빈도, 강도, 사용된 도구·수단, 새로운
   신체 부위·피해, 지속 기간 중 최소 하나에서 뚜렷한 변화가 있어야
   한다. 신체 부위가 한 곳 더 언급되거나 표현이 조금 더 구체적인
   정도의 사소한 차이만으로는 "다시_언급"으로 분류한다.
9. "악화"와 "다시_언급" 사이에서 판단이 애매하면(뚜렷한 변화인지
   확신이 없으면) "악화" 쪽으로 분류한다 — 실제 악화를 놓치는 것이
   거짓 경보보다 더 위험하다. 단, "감소"와 "다시_언급" 사이에서
   애매할 때는 이 비대칭을 적용하지 않는다(그냥 "다시_언급"으로).

[비교할 세부유형 쌍]

{comparison_list}

[출력 형식]

반드시 아래 JSON 형식으로만 답한다:
{{
  "comparisons": [
    {{
      "subtype": "세부유형명",
      "change": "다시_언급|감소|악화|불명확",
      "reason": "두 발화의 표현 차이를 사실 그대로 한 문장으로"
    }}
  ]
}}
"""


def _build_comparison_list_text(
    comparisons: List[Dict[str, Any]],
) -> str:
    lines: List[str] = []

    for item in comparisons:
        subtype = item.get("subtype", "")
        previous_label = item.get("previous_label", "이전 회기")
        current_label = item.get("current_label", "이번 회기")
        previous_evidence = item.get("previous_evidence") or []
        current_evidence = item.get("current_evidence") or []

        lines.append(f"■ {subtype}")
        lines.append(f"  [{previous_label}]")

        for text in previous_evidence:
            lines.append(f"  - {text}")

        lines.append(f"  [{current_label}]")

        for text in current_evidence:
            lines.append(f"  - {text}")

    return "\n".join(lines)


def _clean_comparisons(
    raw_comparisons: Any,
    valid_subtypes: set,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_comparisons, list):
        return []

    cleaned = []

    for item in raw_comparisons:
        if not isinstance(item, dict):
            continue

        subtype = item.get("subtype")
        change = item.get("change")
        reason = item.get("reason")

        if subtype not in valid_subtypes:
            continue

        if change not in VALID_CHANGE_LABELS:
            continue

        if not isinstance(reason, str) or not reason.strip():
            continue

        cleaned.append(
            {
                "subtype": subtype,
                "change": change,
                "reason": reason.strip(),
            }
        )

    return cleaned


def compare_statements_across_sessions(
    client: OpenAI,
    model: str,
    comparisons: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    comparisons: 이전 회기와 이번 회기 모두에 근거가 있는 세부유형만
    담은 리스트. 각 항목은
    {
      "subtype": "직접 신체 가해",
      "previous_label": "1회차 (9/15)",
      "previous_evidence": ["아빠가 소리 질러서 무서워요"],
      "current_label": "3회차 (9/29)",
      "current_evidence": ["요즘엔 아빠가 소리 안 질러요"],
    }
    형태. 이전/이번 둘 다 근거가 없는 세부유형(새로 언급/미언급)은
    호출부가 걸러내고 여기 넣지 않는다 — 모듈 docstring 참고.
    """

    if not comparisons:
        return []

    valid_subtypes = {
        item.get("subtype") for item in comparisons
    }

    system_prompt = SYSTEM_PROMPT.format(
        comparison_list=_build_comparison_list_text(comparisons)
    )

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt="위 세부유형 쌍을 모두 비교해서 출력해.",
            max_retries=2,
            timeout_seconds=180.0,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return _clean_comparisons(
        parsed.get("comparisons"),
        valid_subtypes,
    )


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import (
        build_openai_client_and_model,
    )

    comparisons = [
        {
            "subtype": "위협·공포 유발",
            "previous_label": "1회차 (9/15)",
            "previous_evidence": ["아빠가 소리 질러서 무서워요"],
            "current_label": "3회차 (9/29)",
            "current_evidence": ["요즘엔 아빠가 소리 안 질러요"],
        },
        {
            "subtype": "직접 신체 가해",
            "previous_label": "2회차 (9/22)",
            "previous_evidence": ["가끔 아빠한테 혼나면서 맞아요"],
            "current_label": "3회차 (9/29)",
            "current_evidence": [
                "요즘엔 손 말고 혁대로도 때려요. 전보다 더 세게 때려요."
            ],
        },
        {
            "subtype": "가정폭력·폭력상황 노출",
            "previous_label": "1회차 (9/15)",
            "previous_evidence": ["엄마랑 아빠가 싸우는 소리를 들었어요"],
            "current_label": "3회차 (9/29)",
            "current_evidence": ["거실에서 큰 소리가 나면 깨요"],
        },
    ]

    client, model = build_openai_client_and_model(DEFAULT_MODEL)

    result = compare_statements_across_sessions(
        client=client,
        model=model,
        comparisons=comparisons,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
