"""
"유형별 위험도"(RiskProfile) 화면의 1~5단계 심각도 판정 LLM 모듈 초안이다.

**검수 전 초안이다 — 다른 어떤 모듈보다도 이 라벨이 중요하다.** 다른
모듈(보호 요인, 감소/악화 진술)은 "참고 신호"지만, 이건 숫자 하나로
심각도를 매기는 거라 실제 개입 판단에 더 직접적으로 영향을 줄 수 있다.
반드시 상담사가 매 건 확인하고 고치는 걸 전제로 한다 — UI에서도
"검수 전 초안 · 실무자 검토 필요"를 숨기지 않는다.

[출처 — 2026-10-13 설계 결정]

I-SPOT 팀이 초안으로 만든 1~5단계 정의(docs 폴더 바깥, `유형별 위험도.pdf`
비교 문서 참고)는 원본인 Barnett, Manly & Cicchetti(1993)의 Maltreatment
Classification System을 요약 번역한 것인데, 자체 비교 결과 신체학대·
성학대 두 유형에서 원본과 한 단계씩 어긋나는 게 발견됐다(비교 문서
7번 항목, "원본에 맞추는 것 권장"이라고 스스로 적어둠). 그래서:

- **신체학대·성학대**: 아래 SEVERITY_DEFINITIONS는 원본(Barnett et al.
  1993)을 직접 번역해서 썼다 — I-SPOT 초안이 아니라 원본 기준.
- **정서학대·방임**: I-SPOT 초안을 그대로 썼다 — 원본과 구조가 더 크게
  달라서(정서학대는 "단발성" 개념 자체가 원본에 없음, 방임은 원본이
  기본돌봄/감독소홀 두 척도로 나누는데 I-SPOT은 하나로 합침) 지금은
  정렬 작업을 보류했다. 나중에 실무자 검토 때 다시 볼 부분.
- 원본의 "도덕·법적/교육적 학대"는 쓰지 않는다 — 우리 분류에서는
  교육적 방임이 이미 방임 세부유형(교육적 방임)으로 들어가 있다.
- 원본 Appendix B(ACE 설문, Felitti et al. 1998)는 전혀 다른 도구라
  (사건 하나의 심각도가 아니라 평생 누적 노출 점수) 이번 범위에 안
  넣었다.

[설계 결정 — 다른 모듈과 같은 이유로 분리]

second_stage_llm.py(위험신호 탐지)와 독립된 별도 호출이다. 이미 튜닝된
탐지 프롬프트에 심각도 판정까지 끼워 넣지 않는다(이 프로젝트에서
반복된 교훈 — 하나의 프롬프트에 책임을 늘리면 기존 성능이 흔들린다).
이 모듈은 2차 분석이 이미 찾아낸 근거(action/instrument/target_body_part
포함)를 입력으로만 받고, 유형 분류 자체는 다시 하지 않는다 — "이미
이 대분류로 분류된 근거들 중 제일 심각한 걸 기준으로 몇 단계인지"만
판단한다.

2026-10-13 1차 검수(AI-Hub 실제 상담 텍스트를 실제 2차 분석까지 통째로
돌려서 테스트): 정서학대 4단계 판정에서 "엄마랑 아저씨랑도 가끔
싸우고 전에 엄마랑 아빠는 매일 싸웠어요"를 근거로 썼는데, "매일"
(심한 수준)은 과거 다른 보호자(아빠) 얘기고 현재(아저씨)는 "가끔"
(약한 수준)이었다 — 서로 다른 시점·대상을 하나로 합쳐서 심각도를
끌어올린 사례. 원칙 7(시점·대상이 다른 근거를 섞지 않음) 추가.

risk_signal_points(record_draft_llm.py가 만드는 단순화된 버전)가 아니라
subtype_analysis의 원본 evidence 구조를 입력으로 쓴다 — 심각도 판정에는
도구/신체부위/행위 같은 세부 정보가 꼭 필요한데, risk_signal_points는
그 필드들을 이미 버린 뒤라서 못 쓴다.
"""

from typing import Any, Dict, List

from openai import OpenAI

from ai.modeling.abuse.second_stage_llm import _call_llm_with_retry

DEFAULT_MODEL = "gpt-5.6-luna"


VALID_SEVERITY_LEVELS = {1, 2, 3, 4, 5}


# ============================================================
# 1. 단계 정의 (검수 전 초안 — 2026-10-13 설계 결정 참고)
# ============================================================

SEVERITY_DEFINITIONS: Dict[str, Dict[str, str]] = {
    # 원본(Barnett, Manly & Cicchetti, 1993) 직접 번역 — I-SPOT 초안과
    # 한 단계씩 어긋났던 걸 발견해서 원본 기준으로 교체함(검수 전).
    "신체학대": {
        "1": "체벌로 생긴 가벼운 자국(목·머리 제외), 또는 자국은 없지만 "
             "위험한 행동. 비사고성 상해라는 정황은 있으나 구체적 정보가 "
             "부족한 경우도 포함.",
        "2": "여러 군데거나 가볍지 않은 자국. 자국이 남을 만한 물건"
             "(머리빗, 벨트 버클, 전선 등)으로 때림. 목 아래를 주먹·발로 "
             "가격해 자국이 남음.",
        "3": "머리·얼굴·목에 자국(예: 눈 멍). 심한 멍이나 봉합이 필요한 "
             "경미한 열상. 경미한 화상(담뱃불 등).",
        "4": "심각한 상해를 낼 수 있는 물건(야구방망이, 전화기 등)으로 "
             "때리거나 벽에 던짐(입원까지는 불필요). 목을 조르거나 "
             "질식시키려 함(응급 치료까지는 불필요). 2도 화상이지만 "
             "입원은 불필요. 응급실 치료가 필요했지만 입원은 24시간 "
             "미만(봉합, 골절 등).",
        "5": "입원이 필요한 상해(심하거나 다발적인 화상, 내부 장기 손상). "
             "영구적 손상이나 흉터(뇌손상, 심한 흉터, 불구). 사망.",
    },
    "성학대": {
        "1": "아동을 직접 관여시키지 않고 성적 자료·행위에 노출시키거나, "
             "그런 노출을 막지 않음(음란물 노출, 교육 목적이 아닌 성적 "
             "대화를 아동 앞에서 함 등).",
        "2": "성적 접촉을 직접 요구함. 또는 성인이 자신의 성기를 "
             "아동에게 노출하거나 자위 행위를 보여줌.",
        "3": "성적 만족을 위한 상호 신체 접촉 — 아동을 만지거나, "
             "아동이 성인을 만지게 하거나, 서로 만지게 함(쓰다듬기, "
             "상호 자위 등).",
        "4": "삽입을 시도하거나 실제로 삽입함(성교, 구강성교, 항문성교 "
             "등 유사성행위 포함).",
        "5": "신체 제압·무기·폭력 등 강제력을 동반한 삽입. 또는 "
             "성매매·성착취물 제작·다른 성인과의 성행위 알선.",
    },
    # I-SPOT 팀 초안 그대로(검수 전) — 원본과 구조 차이가 커서 지금은
    # 정렬 보류.
    "정서학대": {
        "1": "단발성 고성·꾸중, 아동의 반응이 거의 없음.",
        "2": "반복적 고성·비하, 또는 함구 요구가 1회 있었음.",
        "3": "위협이나 \"버리겠다\"는 말이 반복됨, 또는 아동이 두려움·"
             "위축을 직접 말로 표현함.",
        "4": "지속적인 위협·고립, 가정폭력에 반복 노출, 등교 거부·"
             "수면 문제 등 일상 기능 손상이 나타남.",
        "5": "생명을 위협하는 수준, 극단적 공포, 자해·자살 언급.",
    },
    "방임": {
        "1": "일시적이고 가벼운 돌봄 소홀.",
        "2": "식사·위생 소홀이 반복되지만 건강에 영향은 없음.",
        "3": "식사·위생 방치가 지속됨, 결석을 방치함, 학령기 아동을 "
             "장시간 혼자 둠.",
        "4": "건강에 영향이 나타남(체중 미달 등), 필요한 치료를 "
             "방치함, 영유아를 혼자 둠.",
        "5": "유기, 생명을 위협하는 수준의 영양 결핍이나 의료 방치.",
    },
}

VALID_MAJOR_TYPES = set(SEVERITY_DEFINITIONS.keys())


# ============================================================
# 2. 프롬프트
# ============================================================

SYSTEM_PROMPT_TEMPLATE = """너는 아동학대 상담 녹취에서 이미 탐지된 근거를 보고,
유형별로 1~5단계 심각도를 매기는 분석기다. 유형 분류 자체는 이미
끝났다 — 너는 "이미 이 대분류로 분류된 근거들 중 가장 심각한 것"을
기준으로 몇 단계인지만 판단한다.

[공통 원칙]

1. 원문에 명시된 정보만 근거로 삼는다 — 행위, 도구, 신체 부위, 상해·
   결과 정도, 의료 처치 여부, 반복성. 원문에 없는 정보를 추정해서
   채우지 않는다.
2. 여러 근거가 있으면 그중 **가장 심각한 것**을 기준으로 단계를
   매긴다. 가벼운 근거가 섞여 있다고 전체 단계를 낮추지 않는다.
3. 판단할 만큼 구체적인 정보가 없으면(예: "맞았어요"만 있고 도구·
   부위·결과가 전혀 없음) 억지로 단계를 매기지 않고 "정보 부족"으로
   표시한다. 애매하게 추측해서 숫자를 채우지 않는다.
4. 보호 요인이나 긍정적인 정황이 있다고 해서 심각도를 낮추지
   않는다 — 심각도는 가해 행위 자체에 대한 판단이고, 보호 요인은
   다른 축이다.
5. reason에는 어떤 표현(행위·도구·부위·결과)이 왜 그 단계에
   해당하는지 한 문장으로 구체적으로 쓴다. "근거가 충분함" 같은
   동어반복은 쓰지 않는다.
6. 이건 참고용 초안이지 확정 판정이 아니다 — 상담사가 반드시
   다시 확인한다는 전제로, 판단이 애매한 경우 낮은 쪽보다는
   "정보 부족"을 선택하는 게 안전하다(거짓으로 낮게 보이는 것보다
   상담사가 직접 보게 하는 게 낫다).
7. 서로 다른 시점이나 서로 다른 사람(예: "예전 아빠는 매일 싸웠다" vs
   "지금 아저씨는 가끔 싸운다")을 가리키는 근거를 하나로 합쳐서 더
   심각한 쪽 수준으로 끌어올리지 않는다. 과거·다른 대상의 일을
   현재 상황의 심각도 근거로 섞어 쓰지 않는다 — 지금 이 가해자·
   이 시기에 해당하는 근거만 기준으로 삼는다.

[유형별 단계 정의]

{severity_definitions}

[출력 형식]

반드시 아래 JSON 형식으로만 답한다:
{{
  "ratings": [
    {{
      "major_type": "대분류명",
      "level": 1-5 사이 정수 또는 null(정보 부족일 때),
      "reason": "이 단계로 판단한 구체적 이유 한 문장",
      "matched_evidence": "판단의 근거가 된 원문 발췌"
    }}
  ]
}}
"""


def build_severity_definition_text(
    major_types: List[str],
) -> str:
    lines: List[str] = []

    for major_type in major_types:
        if major_type not in SEVERITY_DEFINITIONS:
            continue

        lines.append(f"■ {major_type}")

        for level, definition in SEVERITY_DEFINITIONS[
            major_type
        ].items():
            lines.append(f"  {level}단계: {definition}")

    return "\n".join(lines)


def build_evidence_block_text(
    subtype_analysis: Dict[str, Any],
) -> Dict[str, str]:
    """
    major_type별로 subtype_analysis의 원본 evidence(행위/도구/부위
    포함)를 텍스트 블록으로 묶는다. risk_signal_points가 아니라 이
    원본 구조를 쓰는 이유는 모듈 docstring 참고.
    """

    blocks: Dict[str, List[str]] = {}

    for major_result in (subtype_analysis or {}).get(
        "results", []
    ):
        major_type = major_result.get("major_type")

        if major_type not in VALID_MAJOR_TYPES:
            continue

        lines = blocks.setdefault(major_type, [])

        for subtype_entry in major_result.get("subtypes", []):
            subtype_name = subtype_entry.get("type", "")

            for evidence in subtype_entry.get("evidences", []):
                text = evidence.get("evidence", "")
                action = evidence.get("action")
                instrument = evidence.get("instrument")
                body_part = evidence.get("target_body_part")

                detail_parts = []

                if action:
                    detail_parts.append(f"행위: {action}")

                if instrument:
                    detail_parts.append(f"도구: {instrument}")

                if body_part:
                    detail_parts.append(f"부위: {body_part}")

                detail = (
                    " (" + ", ".join(detail_parts) + ")"
                    if detail_parts
                    else ""
                )

                lines.append(
                    f"- [{subtype_name}] \"{text}\"{detail}"
                )

    return {
        major_type: "\n".join(lines)
        for major_type, lines in blocks.items()
        if lines
    }


# ============================================================
# 3. 검증 및 정리
# ============================================================

def _clean_ratings(
    raw_ratings: Any,
    valid_major_types: set,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_ratings, list):
        return []

    cleaned = []

    for item in raw_ratings:
        if not isinstance(item, dict):
            continue

        major_type = item.get("major_type")

        if major_type not in valid_major_types:
            continue

        level = item.get("level")

        if level is not None:
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = None

            if level not in VALID_SEVERITY_LEVELS:
                level = None

        reason = item.get("reason")

        if not isinstance(reason, str) or not reason.strip():
            reason = ""

        matched_evidence = item.get("matched_evidence")

        if not isinstance(matched_evidence, str):
            matched_evidence = None

        cleaned.append(
            {
                "major_type": major_type,
                "level": level,
                "reason": reason.strip(),
                "matched_evidence": matched_evidence,
                "reviewed": False,
            }
        )

    return cleaned


# ============================================================
# 4. 진입점
# ============================================================

def rate_severity(
    client: OpenAI,
    model: str,
    subtype_analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    탐지된 대분류별로 1~5단계 심각도를 매긴다. 전부 "검수 전 초안"이다
    — 반환값에 reviewed: False를 항상 포함시켜서, 호출부/화면이 이걸
    빠뜨리지 않고 "검수 전" 표시를 하도록 강제한다.
    """

    evidence_blocks = build_evidence_block_text(subtype_analysis)

    if not evidence_blocks:
        return []

    major_types = list(evidence_blocks.keys())

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        severity_definitions=build_severity_definition_text(
            major_types
        )
    )

    user_prompt = "\n\n".join(
        f"[{major_type}]\n{block}"
        for major_type, block in evidence_blocks.items()
    )

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=2,
            timeout_seconds=180.0,
        )
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        parsed = {}

    return _clean_ratings(
        parsed.get("ratings"),
        set(major_types),
    )


# ============================================================
# 5. 데모
# ============================================================

if __name__ == "__main__":
    import json

    from ai.modeling.abuse.llm_backend import (
        build_openai_client_and_model,
    )

    demo_subtype_analysis = {
        "results": [
            {
                "major_type": "신체학대",
                "subtypes": [
                    {
                        "type": "직접 신체 가해",
                        "evidences": [
                            {
                                "evidence": "아빠가 허리띠로 등이랑 팔을 때렸어요. 멍이 많이 들었어요.",
                                "action": "때림",
                                "instrument": "허리띠",
                                "target_body_part": "등, 팔",
                            }
                        ],
                    }
                ],
            },
            {
                "major_type": "방임",
                "subtypes": [
                    {
                        "type": "기본적 보호·양육 방임",
                        "evidences": [
                            {
                                "evidence": "엄마가 늦게 들어오셔서 오실 때까지 굶었어요.",
                                "action": None,
                                "instrument": None,
                                "target_body_part": None,
                            }
                        ],
                    }
                ],
            },
        ]
    }

    client, model = build_openai_client_and_model(DEFAULT_MODEL)

    result = rate_severity(
        client=client,
        model=model,
        subtype_analysis=demo_subtype_analysis,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
