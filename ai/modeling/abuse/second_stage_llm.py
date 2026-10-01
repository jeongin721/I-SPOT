"""
I-SPOT 2차 세부유형 판정 LLM 모듈.
1차 대분류 결과를 받아 세부 위험신호와 여러 근거 발화를 구조화한다.
"""

import difflib
import json
import os
import queue
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ============================================================
# 1. 세부유형 정의
# ============================================================

# 경계 규칙은 '2020-2022 아동학대사건 판례연구' 일반론(vii~xi쪽)과 실제 상담
# 원문 대조를 근거로 했다. 15개 세부유형은 자체 분류라서 평가 CSV의 세부 라벨은
# AI-Hub 19라벨을 합쳐 만든 대용값일 뿐 정답이 아니다(F1을 맞추려고 조이지 말 것).
SUBTYPE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "신체학대": {
        "직접 신체 가해": (
            "아동을 때리거나 차거나 밀치거나 꼬집거나 물어뜯거나 조르는 등 "
            "신체에 직접적인 위해를 가한 경우. "
            "손·발뿐 아니라 도구를 이용해 때린 경우에도 이 유형에 해당할 수 있으며, "
            "도구가 사용된 경우에는 '도구·위험수단 사용'과 동시에 선택할 수 있다. "
            "밀친 경우에는 '신체적 강압·제압'과 동시에 선택할 수 있다."
        ),
        "도구·위험수단 사용": (
            "막대기, 벨트, 흉기, 뜨거운 물질, 화학물질 등 "
            "도구나 위험한 수단을 사용하여 아동에게 위해를 가한 경우. "
            "도구를 이용해 직접 신체 위해를 가했다면 "
            "'직접 신체 가해'와 동시에 선택할 수 있다."
        ),
        "신체적 강압·제압": (
            "아동을 붙잡거나 누르거나 묶거나 밀치거나 움직이지 못하게 하는 등 "
            "신체적인 힘으로 강압하거나 제압한 경우. 밀친 경우에는 '직접 신체 가해'와 "
            "동시에 선택할 수 있다."
        ),
    },

    "정서학대": {
        "폭언·모욕": (
            "욕설, 혐오성 발언, 모욕, 비난, 인격·외모·신체 비하, 수치심을 주는 "
            "말 등으로 아동의 정서에 해를 가하는 경우. "
            "가해자가 실제로 한 욕설·비하·모욕의 말이 원문에 나올 때만 선택한다. "
            "폭행·협박·강요·가둠만 있고 그런 말이 없으면 선택하지 않는다"
            "(협박하는 말은 '폭언·모욕'이 아니라 '위협·공포 유발'이다). "
            "아동이 자기 감정·상태를 말한 것('죽고 싶어요', '무서웠어요')이나 "
            "부모가 아동을 무시하거나 말을 안 하는 것은 가해자의 폭언이 아니므로 "
            "이 유형의 근거가 아니다."
        ),
        "위협·공포 유발": (
            "'죽여버린다', '손가락 잘라버린다' 같은 해악 고지, 흉기를 들고 하는 "
            "협박, '신고하면 죽인다' 같은 입막음 협박, 집에서 쫓아내겠다·"
            "버리겠다는 위협 등으로 아동에게 공포나 두려움을 유발하는 경우. "
            "아동 본인을 향한 구체적인 해악 고지가 있어야 하며, 단순히 "
            "혼내거나 꾸짖는 말은 포함하지 않는다."
        ),
        "통제·강요·고립": (
            "아동의 행동이나 인간관계를 과도하게 통제하거나, 원하지 않는 행동을 "
            "강요하거나, 격리·고립·차별하는 경우. 예: 억지로 먹게 하거나 토한 것을 "
            "다시 먹게 하는 행위, 강제로 재우는 행위, 술을 따르게·마시게 하는 행위, "
            "또래와 어울리지 못하게 막는 행위, 방·화장실·베란다 등에 가두고 "
            "'못 나오게' 한 행위. "
            "일반적인 훈육이나 규칙 설정(예: '숙제 먼저 해라', '외출 시간 지켜라', "
            "청소 당번, '친구들에게 먼저 다가가라'는 조언)은 포함하지 않는다 — "
            "합리적 범위의 지도이고 계속적인 훈육의 일환이면 학대가 아니며, "
            "방이나 화장실에 '가서 생각하고 오라'고 한 정도는 아동이 나오지 "
            "못하게 막혔다고 진술하지 않으면 해당하지 않는다. "
            "위협하는 말만 있고 실제로 행동을 제한·강요한 내용이 없으면 "
            "'위협·공포 유발'만 선택한다. 협박과 통제가 각각 별개의 행위로 "
            "원문에 있을 때만 두 유형을 함께 선택한다. "
            "원문에 구체적인 통제·강요·고립 행위가 명시돼 있지 않다면, 다른 "
            "정서학대 세부유형이 있다고 해서 같이 선택하지 않는다."
        ),
        "가정폭력·폭력상황 노출": (
            "부모 또는 보호자 간의 폭행, 부부싸움, 심한 언쟁, 폭력적 상황 등을 "
            "아동이 직접 보거나 듣게 되는 경우. 아동 본인이 폭행을 당한 것은 "
            "이 유형이 아니라 신체학대에 해당한다."
        ),
    },

    "성학대": {
        "성적 노출·성희롱": (
            "신체 접촉 없이 이루어지는 성적 행위. 예: 성기·신체를 아동에게 "
            "노출하거나 아동 앞에서 자위행위를 하는 것, 아동에게 옷을 벗으라고 "
            "시키는 것, 음란물을 보여주는 것, 성적 발언·성적 조롱(신체·생리에 "
            "대한 성적 언급 등), 아동의 신체 부위 사진·영상을 찍어 보내라고 "
            "요구하는 것(온라인·메신저 포함). 접촉이 없어도 성적 학대로 본다. "
            "신체 접촉이 있으면 '성적 접촉·추행'을 선택하고, 접촉과 별개로 "
            "위와 같은 비접촉 행위가 원문에 따로 있을 때만 이 유형도 함께 선택한다."
        ),
        "성적 접촉·추행": (
            "아동의 가슴, 성기, 엉덩이, 허벅지 등을 성적인 목적으로 만지거나, "
            "옷·속옷을 벗기거나, 몸을 눌러 밀착시키거나 끌어안는 등 성적 신체접촉을 "
            "하거나 아동에게 강요한 경우. "
            "아동이 '만졌다' 또는 위 행위를 구체적으로 진술했을 때만 선택한다. "
            "상담사 질문에 '만지거나 보여달라고'처럼 여러 행위가 함께 묶여 있고 "
            "아동이 '네'라고만 답했다면 접촉 여부가 특정되지 않으므로, 아동이 "
            "이어서 실제로 진술한 행위에 해당하는 유형만 선택한다."
        ),
        "성교·유사성행위": (
            "성기 결합, 구강성교, 손가락·물건을 성기나 항문에 넣는 삽입 등 "
            "성교 또는 이에 준하는 유사성행위를 아동에게 행하거나 강요한 경우. "
            "예: '팬티 안으로 손을 넣어 손가락을 넣었다'. 삽입이 실제로 있었다는 "
            "진술이 있어야 하며, 옷을 벗기거나 시도했지만 '하려다 못했다'는 "
            "경우는 '성적 접촉·추행'을 선택한다."
        ),
        "성적 착취": (
            "성매매, 대가를 조건으로 한 성적 행위, 성적 사진·영상 제작·전송·판매, "
            "또는 촬영물을 유포하겠다고 협박하는 경우 등 아동을 성적으로 "
            "이용하거나 착취한 경우. "
            "'성적 착취'는 다음 중 하나가 원문에 명시돼 있을 때만 선택한다: "
            "(1) 돈·물건 등 대가 지급이 실제로 언급됨, "
            "(2) 이미 보낸 사진·영상을 유포하겠다고 협박하는 내용이 있음. "
            "단순히 사진·영상을 보내달라고 요청받았다는 사실만으로는 선택하지 "
            "않는다 — 대가나 유포 협박이 실제로 원문에 있는지 반드시 확인한다. "
            "아동이 '돈 얘기는 없었다', '유포된 적 없다'처럼 대가·유포 요소를 "
            "직접 부정하는 경우 이 유형을 선택하지 않는다. 대가·유포 요소가 "
            "없으면 '성교·유사성행위'나 '성적 접촉·추행' 쪽이 맞을 가능성이 높다."
        ),
    },

    "방임": {
        "기본적 보호·양육 방임": (
            "식사, 의복, 위생, 안전한 보호, 감독 등 기본적인 양육과 보호를 "
            "적절히 제공하지 않는 경우. 보호자가 아동을 버리고 떠나거나(유기) "
            "장기간 홀로 방치해 사실상 보호관계를 중단한 경우, 더러운 환경에 "
            "방치한 경우도 이 유형에 포함한다."
        ),
        "교육적 방임": (
            "정당한 사유 없이 '아동 본인'을 학교에 보내지 않거나 "
            "지속적인 결석·미취학 상태를 방치하는 경우. 아동이 직접 "
            "'학교에 안 다닌다', '결석했다' 등 본인의 등교·재학 상태가 "
            "방치되고 있다고 말하는 경우에만 선택한다. "
            "부모·보호자가 참관수업·학부모 상담 같은 학교 '행사'에 "
            "오지 않았다는 내용은 아동 본인의 결석·미취학이 아니므로 "
            "이 유형에 해당하지 않는다 — '학교' 단어가 원문에 있어도 "
            "아동 본인의 등교 방치를 가리키는 게 아니면 선택하지 않는다. "
            "원문에 아동 본인의 결석·미취학을 가리키는 내용이 전혀 없으면 "
            "이 유형은 절대 선택하지 않는다 — 식사·의복·위생·의료 등 다른 "
            "영역의 방임 정황만으로는 교육적 방임을 추론하지 않는다. "
            "다른 방임 유형(기본적 보호, 의료적 방임 등)이 있다고 해서 자동으로 "
            "같이 선택하지 않는다."
        ),
        "의료적 방임": (
            "질병, 부상, 치료 필요가 있음에도 필요한 의료기관 방문이나 "
            "치료를 제공하지 않는 경우"
        ),
    },
}

VALID_MAJOR_TYPES = set(SUBTYPE_DEFINITIONS.keys())

VALID_EVIDENCE_STRENGTH = {
    "높음",
    "중간",
    "낮음",
}


# ============================================================
# 2. 프롬프트
# ============================================================

SYSTEM_PROMPT_TEMPLATE = """
너는 아동 상담 원문에서 세부 위험신호를 구조화하는 2차 분석기다.

1차 모델이 탐지한 대분류 안에서만 세부유형을 판단한다.

[중요 원칙]

1. 제시된 세부유형 후보 안에서만 선택한다.
2. 원문에서 직접 확인 가능한 근거가 있는 항목만 선택한다.
3. 1차 모델이 탐지했더라도 실제 관련 신호가 없으면 해당 대분류의 subtypes는 빈 배열로 반환한다.
4. 상담사의 질문에 학대 표현이 있어도 아동이 명확히 부정한 경우 양성 근거로 사용하지 않는다.
5. evidence는 반드시 원문에 실제 존재하는 연속된 텍스트를 그대로 복사한다.
6. 같은 세부유형에 근거가 여러 군데 존재하면 evidences 배열에 모두 넣는다.
7. evidence_strength는 예측 확률이 아니라 근거의 직접성을 의미한다.

- 높음: 행위 또는 상황이 원문에 직접적으로 명확히 진술됨
- 중간: 문맥상 비교적 명확하지만 일부 정보가 생략됨
- 낮음: 간접적 위험신호이며 사람 확인이 필요함

8. action은 원문에서 확인되는 행위만 작성한다.
9. instrument는 원문에 명시된 도구나 수단만 작성한다.
10. target_body_part는 원문에 명시된 신체 부위만 작성한다.
11. 추론이 필요한 값은 null로 둔다.
12. 하나의 대분류 안에서 여러 세부유형이 동시에 해당될 수 있다.
13. 세부유형은 상호배타적이지 않다.
    하나의 행위가 둘 이상의 세부유형 정의를 동시에 만족하면 모두 선택한다.
    예: "막대기로 때렸다" → "직접 신체 가해" + "도구·위험수단 사용"
14. 세부유형마다 각자의 직접적인 근거가 따로 있어야 한다.
    "이 대분류가 탐지됐으니 관련 세부유형을 하나쯤 더 추가하자"는 식으로
    판단하지 않는다 — 다른 세부유형의 근거를 재사용해서 또 다른 세부유형을
    같이 선택하지 않는다. 특히 "통제·강요·고립", "성적 착취", "교육적 방임"은
    정의가 넓어 보여도 원문에 그 유형만의 구체적인 행위·정황이 명시돼
    있을 때만 선택한다 — 다른 세부유형이 이미 있다고 확장하지 않는다.
15. 두 세부유형 사이에서 애매하면(예: 접촉이 있었는지 불확실) 더 좁고
    구체적인 근거를 요구하는 쪽 대신, 원문 표현에 더 정확히 맞는 하나만
    선택한다. 둘 다 확신이 없으면 더 보수적인(약한) 쪽 하나만 선택한다.
16. borderline은 선택한 세부유형의 근거는 있지만 인접한 다른 세부유형과 구별이
    애매하거나(예: 위협↔통제, 노출↔접촉) 진술이 간접적이어서 상담사가 직접
    확인해야 할 때 true, 근거가 명확하면 false로 표시한다. 애매하다는 이유로
    세부유형을 빼지 말고, 고른 뒤 borderline만 true로 표시한다.

[이번 요청에서 판단할 세부유형]

{subtype_definitions}

반드시 아래 JSON 형식으로만 답한다.

{{
  "results": [
    {{
      "major_type": "대분류명",
      "subtypes": [
        {{
          "type": "세부유형명",
          "borderline": false,
          "evidences": [
            {{
              "evidence": "원문에서 그대로 발췌한 근거 표현",
              "evidence_strength": "높음|중간|낮음",
              "action": "행위 또는 null",
              "instrument": "도구/수단 또는 null",
              "target_body_part": "신체 부위 또는 null"
            }}
          ]
        }}
      ]
    }}
  ]
}}

세부유형이 없으면 "subtypes": [] 로 반환한다.
"""

USER_PROMPT_TEMPLATE = """
[상담 원문]

{text}
"""


def build_subtype_definition_text(
    major_types: List[str],
) -> str:
    lines: List[str] = []

    for major_type in major_types:
        if major_type not in SUBTYPE_DEFINITIONS:
            continue

        lines.append("■ {}".format(major_type))

        for subtype, definition in SUBTYPE_DEFINITIONS[
            major_type
        ].items():
            lines.append(
                "  - {}: {}".format(
                    subtype,
                    definition,
                )
            )

    return "\n".join(lines)


# ============================================================
# 3. Evidence 검증
# ============================================================

def _normalize_whitespace(text: str) -> str:
    """
    모든 공백을 제거해 비교용 문자열을 만든다.
    예:
    '막대기로 제 팔' → '막대기로제팔'
    """
    return re.sub(r"\s+", "", text)


def _normalize_with_index_map(
    text: str,
) -> Tuple[str, List[int]]:
    normalized_chars: List[str] = []
    index_map: List[int] = []

    for index, char in enumerate(text):
        if char.isspace():
            continue

        normalized_chars.append(char)
        index_map.append(index)

    return "".join(normalized_chars), index_map


def _exact_match(
    evidence: str,
    source_text: str,
) -> Optional[Tuple[int, int]]:
    start = source_text.find(evidence)

    if start == -1:
        return None

    return start, start + len(evidence)


def _normalized_match(
    evidence: str,
    source_text: str,
) -> Optional[Tuple[int, int]]:
    norm_evidence, _ = _normalize_with_index_map(
        evidence
    )

    norm_source, source_index_map = (
        _normalize_with_index_map(
            source_text
        )
    )

    if not norm_evidence:
        return None

    norm_start = norm_source.find(
        norm_evidence
    )

    if norm_start == -1:
        return None

    norm_end = (
        norm_start
        + len(norm_evidence)
        - 1
    )

    if norm_end >= len(source_index_map):
        return None

    original_start = source_index_map[
        norm_start
    ]

    original_end = (
        source_index_map[norm_end]
        + 1
    )

    return original_start, original_end


def _fuzzy_match(
    evidence: str,
    source_text: str,
    max_search_chars: int = 3000,
) -> Optional[Tuple[int, int, float]]:
    """
    fuzzy matching은 exact/normalized exact 실패 시에만 사용한다.

    긴 전체 세션을 그대로 반복 탐색하면 느려질 수 있으므로
    max_search_chars 상한을 둔다.

    통과 기준(threshold) 판단은 호출부(verify_evidence)에서 한다 —
    여기서는 가장 비슷했던 후보를 비율과 함께 그대로 돌려준다.
    기준 미달이어도 "원문에서 제일 비슷한 부분"을 상담사에게 참고용으로
    보여줄 수 있어야 하기 때문이다.
    """

    evidence = evidence.strip()

    if not evidence:
        return None

    # --------------------------------------------------------
    # fuzzy 탐색 대상 길이 제한
    # --------------------------------------------------------

    search_text = source_text[:max_search_chars]

    evidence_length = len(evidence)

    if evidence_length == 0:
        return None

    min_window = max(
        1,
        int(evidence_length * 0.80),
    )

    max_window = min(
        len(search_text),
        int(evidence_length * 1.20) + 1,
    )

    if min_window > max_window:
        return None

    best_ratio = 0.0
    best_start = None
    best_end = None

    # 지나치게 촘촘한 검색 방지
    step = max(
        1,
        evidence_length // 4,
    )

    norm_evidence = re.sub(
        r"\s+",
        "",
        evidence,
    )

    for start in range(
        0,
        len(search_text),
        step,
    ):
        for window_size in range(
            min_window,
            max_window + 1,
        ):
            end = start + window_size

            if end > len(search_text):
                break

            candidate = search_text[
                start:end
            ]

            norm_candidate = re.sub(
                r"\s+",
                "",
                candidate,
            )

            ratio = difflib.SequenceMatcher(
                None,
                norm_evidence,
                norm_candidate,
            ).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_start = start
                best_end = end

    if (
        best_start is not None
        and best_end is not None
    ):
        return (
            best_start,
            best_end,
            best_ratio,
        )

    return None


# fuzzy 유사도가 이 밑이면 참고용으로도 보여줄 가치가 없다고 본다
# (엉뚱한 구간을 "비슷한 원문"이라며 보여주면 오히려 혼란만 준다).
_MIN_REFERENCE_RATIO = 0.5


def verify_evidence(
    source_text,
    evidence,
    fuzzy_threshold: float = 0.88,
    max_fuzzy_search_chars: int = 3000,
):
    """
    LLM이 반환한 evidence가 실제 원문에 존재하는지 검증한다.
    exact → normalized → fuzzy 순서로 확인한다.

    fuzzy 유사도가 fuzzy_threshold 미달이라도 _MIN_REFERENCE_RATIO
    이상이면 evidence_verified는 False로 유지하되 closest_source_snippet에
    원문에서 가장 비슷했던 구간을 담아 돌려준다 — 검증에는 실패했지만
    상담사가 원문의 어디를 봐야 할지 참고할 수 있게 하기 위함이다.
    """

    if not source_text or not evidence:
        return {
            "evidence_verified": False,
            "evidence_match_method": "unverified",
            "evidence_start": None,
            "evidence_end": None,
            "matched_evidence": None,
            "closest_source_snippet": None,
        }

    # ============================================================
    # 1. Exact match
    # ============================================================

    exact_start = source_text.find(evidence)

    if exact_start != -1:
        exact_end = exact_start + len(evidence)

        return {
            "evidence_verified": True,
            "evidence_match_method": "exact",
            "evidence_start": exact_start,
            "evidence_end": exact_end,
            "matched_evidence": source_text[exact_start:exact_end],
            "closest_source_snippet": None,
        }

    # ============================================================
    # 2. Whitespace-normalized match
    # ============================================================

    normalized_source, source_index_map = _normalize_with_index_map(source_text)
    normalized_evidence = _normalize_whitespace(evidence)

    normalized_start = normalized_source.find(normalized_evidence)

    if normalized_start != -1:
        normalized_end = normalized_start + len(normalized_evidence)

        # 정규화 문자열 위치를 실제 원문 위치로 복구
        original_start = source_index_map[normalized_start]
        original_end = source_index_map[normalized_end - 1] + 1

        matched_text = source_text[original_start:original_end]

        return {
            "evidence_verified": True,
            "evidence_match_method": "normalized",
            "evidence_start": original_start,
            "evidence_end": original_end,
            "matched_evidence": matched_text,
            "closest_source_snippet": None,
        }

    # ============================================================
    # 3. Fuzzy match
    # ============================================================

    fuzzy_result = _fuzzy_match(
        source_text=source_text,
        evidence=evidence,
        max_search_chars=max_fuzzy_search_chars,
    )

    if fuzzy_result is not None:
        fuzzy_start, fuzzy_end, fuzzy_ratio = fuzzy_result

        if fuzzy_ratio >= fuzzy_threshold:
            return {
                "evidence_verified": True,
                "evidence_match_method": "fuzzy",
                "evidence_start": fuzzy_start,
                "evidence_end": fuzzy_end,
                "matched_evidence": source_text[fuzzy_start:fuzzy_end],
                "closest_source_snippet": None,
            }

        if fuzzy_ratio >= _MIN_REFERENCE_RATIO:
            return {
                "evidence_verified": False,
                "evidence_match_method": "unverified",
                "evidence_start": None,
                "evidence_end": None,
                "matched_evidence": None,
                "closest_source_snippet": source_text[fuzzy_start:fuzzy_end],
            }

    # ============================================================
    # 4. Match failed
    # ============================================================

    return {
        "evidence_verified": False,
        "evidence_match_method": "unverified",
        "evidence_start": None,
        "evidence_end": None,
        "matched_evidence": None,
        "closest_source_snippet": None,
    }


# ============================================================
# 4. 보조 필드 검증
# ============================================================

def _clean_optional_string(
    value: Any,
) -> Optional[str]:
    if value is None:
        return None

    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    if value.lower() in {
        "null",
        "none",
    }:
        return None

    return value


def _is_value_supported_by_text(
    value: Optional[str],
    source_text: str,
) -> bool:
    """
    instrument / target_body_part가 원문에 직접 존재하는지 검사한다.
    """

    if value is None:
        return True

    normalized_value = re.sub(
        r"\s+",
        "",
        value,
    )

    normalized_source = re.sub(
        r"\s+",
        "",
        source_text,
    )

    return (
        normalized_value
        in normalized_source
    )


# ============================================================
# 5. LLM 출력 검증
# ============================================================

def validate_and_enrich_results(
    parsed: Dict[str, Any],
    source_text: str,
    requested_major_types: List[str],
    fuzzy_threshold: float,
    max_fuzzy_search_chars: int,
) -> Dict[str, Any]:
    final_results: List[
        Dict[str, Any]
    ] = []

    raw_results = parsed.get(
        "results",
        [],
    )

    if not isinstance(raw_results, list):
        raw_results = []

    requested_major_set = set(
        requested_major_types
    )

    raw_by_major: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for block in raw_results:
        if not isinstance(block, dict):
            continue

        major_type = block.get(
            "major_type"
        )

        if major_type not in requested_major_set:
            continue

        raw_by_major[
            major_type
        ] = block

    for major_type in requested_major_types:
        allowed_subtypes = (
            SUBTYPE_DEFINITIONS[
                major_type
            ]
        )

        raw_block = raw_by_major.get(
            major_type,
            {},
        )

        raw_subtypes = raw_block.get(
            "subtypes",
            [],
        )

        if not isinstance(
            raw_subtypes,
            list,
        ):
            raw_subtypes = []

        # 같은 subtype이 여러 번 나온 경우 evidences를 합치기 위한 dict
        subtype_map: Dict[
            str,
            List[Dict[str, Any]]
        ] = {}
        borderline_map: Dict[str, bool] = {}

        for subtype_item in raw_subtypes:
            if not isinstance(
                subtype_item,
                dict,
            ):
                continue

            subtype_name = subtype_item.get(
                "type"
            )

            if subtype_name not in allowed_subtypes:
                continue

            if str(subtype_item.get("borderline")).lower() == "true":
                borderline_map[subtype_name] = True

            raw_evidences = subtype_item.get(
                "evidences",
                [],
            )

            # 모델이 실수로 evidence 단일 필드를 반환한 경우도 수용
            if not raw_evidences:
                single_evidence = subtype_item.get(
                    "evidence"
                )

                if single_evidence:
                    raw_evidences = [
                        {
                            "evidence":
                                single_evidence,

                            "evidence_strength":
                                subtype_item.get(
                                    "evidence_strength"
                                ),

                            "action":
                                subtype_item.get(
                                    "action"
                                ),

                            "instrument":
                                subtype_item.get(
                                    "instrument"
                                ),

                            "target_body_part":
                                subtype_item.get(
                                    "target_body_part"
                                ),
                        }
                    ]

            if not isinstance(
                raw_evidences,
                list,
            ):
                continue

            if subtype_name not in subtype_map:
                subtype_map[
                    subtype_name
                ] = []

            for evidence_item in raw_evidences:
                if not isinstance(
                    evidence_item,
                    dict,
                ):
                    continue

                evidence = evidence_item.get(
                    "evidence",
                    "",
                )

                if not isinstance(
                    evidence,
                    str,
                ):
                    evidence = ""

                evidence_result = (
                    verify_evidence(
                        evidence=evidence,
                        source_text=source_text,
                        fuzzy_threshold=fuzzy_threshold,
                        max_fuzzy_search_chars=max_fuzzy_search_chars,
                    )
                )

                evidence_strength = (
                    evidence_item.get(
                        "evidence_strength"
                    )
                )

                if (
                    evidence_strength
                    not in VALID_EVIDENCE_STRENGTH
                ):
                    evidence_strength = "낮음"

                action = (
                    _clean_optional_string(
                        evidence_item.get(
                            "action"
                        )
                    )
                )

                instrument = (
                    _clean_optional_string(
                        evidence_item.get(
                            "instrument"
                        )
                    )
                )

                target_body_part = (
                    _clean_optional_string(
                        evidence_item.get(
                            "target_body_part"
                        )
                    )
                )

                instrument_supported = (
                    _is_value_supported_by_text(
                        value=instrument,
                        source_text=source_text,
                    )
                )

                if not instrument_supported:
                    instrument = None

                body_part_supported = (
                    _is_value_supported_by_text(
                        value=target_body_part,
                        source_text=source_text,
                    )
                )

                if not body_part_supported:
                    target_body_part = None

                needs_review = False

                if not evidence_result[
                    "evidence_verified"
                ]:
                    needs_review = True

                if not instrument_supported:
                    needs_review = True

                if not body_part_supported:
                    needs_review = True

                cleaned_evidence = {
                    "evidence":
                        evidence,

                    "evidence_verified":
                        evidence_result[
                            "evidence_verified"
                        ],

                    "evidence_match_method":
                        evidence_result[
                            "evidence_match_method"
                        ],

                    "evidence_start":
                        evidence_result[
                            "evidence_start"
                        ],

                    "evidence_end":
                        evidence_result[
                            "evidence_end"
                        ],

                    "matched_evidence":
                        evidence_result[
                            "matched_evidence"
                        ],

                    "closest_source_snippet":
                        evidence_result.get(
                            "closest_source_snippet"
                        ),

                    "evidence_strength":
                        evidence_strength,

                    "action":
                        action,

                    "instrument":
                        instrument,

                    "target_body_part":
                        target_body_part,

                    "needs_review":
                        needs_review,
                }

                # 동일 근거 문장 중복 방지
                already_exists = any(
                    existing.get(
                        "evidence"
                    )
                    == evidence
                    for existing in subtype_map[
                        subtype_name
                    ]
                )

                if not already_exists:
                    subtype_map[
                        subtype_name
                    ].append(
                        cleaned_evidence
                    )

        cleaned_subtypes: List[
            Dict[str, Any]
        ] = []

        for subtype_name, evidences in subtype_map.items():
            subtype_needs_review = any(
                evidence.get(
                    "needs_review",
                    False,
                )
                for evidence in evidences
            )

            cleaned_subtypes.append(
                {
                    "type":
                        subtype_name,

                    "evidences":
                        evidences,

                    "needs_review":
                        subtype_needs_review,

                    "borderline":
                        borderline_map.get(
                            subtype_name,
                            False,
                        ),
                }
            )

        final_results.append(
            {
                "major_type":
                    major_type,

                "subtypes":
                    cleaned_subtypes,
            }
        )

    return {
        "results":
            final_results,
    }


# ============================================================
# 5-1. 저신뢰 예측 필터링
# ============================================================
# 2026-09-22 평가(60건, subtype_labeled_valid_v4_refined.csv 기준):
# 세부유형 Macro F1 0.450 — Recall은 대부분 높은데(자주 1.0) Precision이
# 낮은 패턴이 뚜렷했다(예: 교육적 방임 P=0.000, 9번 예측해서 9번 다 오탐).
# 근거 강도가 "낮음"이거나 원문에서 근거를 아예 못 찾은(evidence_verified
# =False, 즉 evidence_match_method="unverified") 예측을 걸러내면, recall을
# 크게 해치지 않으면서 precision을 끌어올릴 수 있을 것으로 보고 추가했다.

def filter_low_confidence_subtypes(
    validated: Dict[str, Any],
) -> Dict[str, Any]:
    """
    evidence_strength가 "낮음"인 근거는 제거한다. 근거가 하나도 안
    남은 세부유형/대분류는 통째로 제거한다.

    예전에는 evidence_verified가 False인 근거도 같이 제거했는데,
    로컬 LLM(qwen2.5:14b)이 원문을 한 글자도 안 틀리고 그대로
    인용하지 못하고 살짝 요약해서 인용하는 경우가 꽤 있어서(특히
    문장이 길고 서술식인 note 모드), AI가 맞게 탐지했어도 항목
    자체가 통째로 사라지는 부작용이 있었다. 이제는 검증 실패한
    근거도 남기되 evidence_verified=False로 표시해서, 상담사가
    "원문 재확인 필요" 상태로 직접 확인하게 한다.
    """

    filtered_results: List[Dict[str, Any]] = []

    for major_block in validated.get("results", []):
        filtered_subtypes = []

        for subtype in major_block.get("subtypes", []):
            kept_evidences = [
                evidence
                for evidence in subtype.get("evidences", [])
                if evidence.get("evidence_strength") != "낮음"
            ]

            if not kept_evidences:
                continue

            filtered_subtypes.append(
                {
                    **subtype,
                    "evidences": kept_evidences,
                    "needs_review": any(
                        evidence.get("needs_review", False)
                        for evidence in kept_evidences
                    ),
                }
            )

        if not filtered_subtypes:
            continue

        filtered_results.append(
            {
                **major_block,
                "subtypes": filtered_subtypes,
            }
        )

    return {
        **validated,
        "results": filtered_results,
    }


# ============================================================
# 6. OpenAI 호출 + retry
# ============================================================

def _call_llm_with_retry(
    client: Any,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 3,
    timeout_seconds: float = 180.0,
) -> Dict[str, Any]:
    """
    일시적 API 오류를 대비해 retry + exponential backoff 적용.
    """

    last_error = None

    # Qwen3 계열처럼 "thinking" 모드가 있는 로컬 모델은 답하기 전에 긴
    # 내부 추론을 생성해서 응답이 10배 넘게 느려질 수 있다(실측: qwen3:14b
    # 172초 -> think:false 시 16초). 우리 작업은 정해진 스키마로 근거를
    # 뽑아내는 구조화 추출이라 깊은 추론이 필요 없어서 꺼도 품질 손해가
    # 거의 없다. think는 Ollama 자체 API 필드라 실제 OpenAI API로 보내면
    # 거부당한다.
    #
    # 호출 종류별로 백엔드가 고정된 뒤로는(llm_backend.py 참고 — 2차는
    # 항상 OpenAI, 요약/체크리스트/note 보완체크는 항상 Ollama) 전역
    # LLM_BACKEND 환경변수로는 "지금 이 호출이 실제로 어느 쪽으로
    # 가는지" 알 수 없다(한 세션 안에서 두 백엔드가 동시에 쓰이므로).
    # 그래서 전달받은 client가 실제로 가리키는 주소(base_url)를 직접
    # 보고 판단한다 — client를 만든 쪽이 아니라 쓰는 쪽에서 사실을
    # 확인하는 셈이라 더 안전하다.
    #
    # temperature를 따로 안 주면 Ollama 기본값(약 0.8)이 쓰여서 같은 프롬프트
    # 인데도 매번 다른 세부유형이 붙거나 빠졌다(60샘플 평가에서 손 안 댄
    # 카테고리 F1이 실행마다 흔들린 원인). 분류·근거 추출은 결정적으로
    # 동작해야 하므로 temperature=0 + seed 고정. OpenAI 백엔드는 모델에
    # 따라 temperature 지정을 거부할 수 있어 건드리지 않는다.
    is_ollama_client = "openai.com" not in str(client.base_url)

    extra_kwargs: Dict[str, Any] = (
        {
            "extra_body": {"think": False},
            "temperature": 0,
            "seed": 42,
        }
        if is_ollama_client
        else {}
    )

    def _request():
        response = client.chat.completions.create(
            model=model,
            timeout=timeout_seconds,
            response_format={"type": "json_object"},
            **extra_kwargs,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            # client.chat.completions.create(timeout=...)만 믿으면 안 된다 —
            # Ollama가 응답을 아주 느리게 나눠 보내면(특정 민감한 내용에서
            # 실측 확인됨: 180초를 넘겨도 안 끝남) SDK의 읽기 타임아웃은
            # "완전히 끊긴 시간"을 기준으로 재서 계속 미뤄질 수 있다. 데몬
            # 스레드에서 호출하고 여기서 직접 마감 시간을 강제한다 — 네트워크
            # 호출 자체를 강제로 죽이지는 못하지만(스레드는 뒤에서 계속
            # 돌다가 나중에 정리된다), 우리 쪽 처리 흐름은 확실히 넘어간다.
            # ThreadPoolExecutor는 워커 스레드가 데몬이 아니라서 프로세스
            # 종료 시 멈춘 요청이 있으면 종료 자체가 막힐 수 있어(테스트 웹
            # 서버처럼 오래 떠 있는 프로세스에서 문제가 됨), daemon=True인
            # threading.Thread를 직접 쓴다.
            result_queue: "queue.Queue" = queue.Queue(maxsize=1)

            def _run():
                try:
                    result_queue.put(("ok", _request()))
                except Exception as thread_exc:
                    result_queue.put(("error", thread_exc))

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()

            try:
                status, payload = result_queue.get(
                    timeout=timeout_seconds + 5
                )
            except queue.Empty:
                raise TimeoutError(
                    f"LLM 호출이 {timeout_seconds + 5:.0f}초 안에 끝나지 않음"
                )

            if status == "error":
                raise payload

            raw_content = payload

            return json.loads(
                raw_content
            )

        except Exception as exc:
            last_error = exc

            if attempt >= max_retries:
                break

            wait_seconds = 2 ** (
                attempt - 1
            )

            time.sleep(
                wait_seconds
            )

    raise RuntimeError(
        "2차 LLM 호출 실패: {}".format(
            last_error
        )
    )


# ============================================================
# 7. 공개 함수
# ============================================================

def analyze_subtypes(
    text: str,
    major_types: List[str],
    model: str = "gpt-5.6-luna",
    client: Any = None,
    fuzzy_threshold: float = 0.88,
    max_fuzzy_search_chars: int = 3000,
    max_retries: int = 3,
    timeout_seconds: float = 180.0,
    filter_low_confidence: bool = True,
) -> Dict[str, Any]:
    """
    1차 모델에서 탐지된 major_types만 대상으로
    세부 위험신호를 분석한다.

    timeout_seconds 기본값은 로컬 Ollama 호출(수십~백여 초) 기준으로
    잡았다 — 예전 OpenAI 전용(30초) 그대로 두면 응답 전에 타임아웃되어
    처음부터 재시도만 반복하다 실패하는 경우가 있었다.

    filter_low_confidence: 근거 강도가 "낮음"이거나 원문에서 검증 안 된
    (unverified) 예측을 결과에서 빼는 옵션.
    2026-09-22 세부유형 정의 프롬프트 개선(통제·강요·고립/성적 착취/
    교육적 방임 등 배제 조건 추가) 전에는 이 필터가 오히려 F1을
    0.457→0.443으로 깎았다(진짜 오탐은 hallucination이 아니라 유형
    오분류였고, 필터는 맞게 예측한 것만 깎았기 때문). 프롬프트 개선
    이후 같은 60건으로 다시 비교하니 원본 0.505 -> 필터 적용 0.520로
    이제는 필터가 도움이 된다(남은 오탐이 진짜 hallucination 위주로
    바뀜) — 그래서 다시 기본값 켬으로 되돌렸다.
    """

    cleaned_major_types: List[str] = []

    for major_type in major_types:
        if (
            major_type in VALID_MAJOR_TYPES
            and major_type not in cleaned_major_types
        ):
            cleaned_major_types.append(
                major_type
            )

    if not cleaned_major_types:
        return {
            "results": [],
            "note": "탐지된 대분류 없음",
        }

    if not text.strip():
        return {
            "results": [],
            "note": "분석할 상담 원문 없음",
        }

    if client is None:
        if not os.environ.get(
            "OPENAI_API_KEY"
        ):
            raise RuntimeError(
                "환경변수 OPENAI_API_KEY가 "
                "설정되어 있지 않습니다."
            )

        client = OpenAI()

    system_prompt = (
        SYSTEM_PROMPT_TEMPLATE.format(
            subtype_definitions=(
                build_subtype_definition_text(
                    cleaned_major_types
                )
            )
        )
    )

    user_prompt = (
        USER_PROMPT_TEMPLATE.format(
            text=text
        )
    )

    parsed = _call_llm_with_retry(
        client=client,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_retries=max_retries,
        timeout_seconds=timeout_seconds,
    )

    validated = (
        validate_and_enrich_results(
            parsed=parsed,
            source_text=text,
            requested_major_types=cleaned_major_types,
            fuzzy_threshold=fuzzy_threshold,
            max_fuzzy_search_chars=max_fuzzy_search_chars,
        )
    )

    if filter_low_confidence:
        validated = filter_low_confidence_subtypes(
            validated
        )

    validated[
        "model"
    ] = model

    return validated


# ============================================================
# 8. 데모
# ============================================================

if __name__ == "__main__":

    text = """
상담사: 아빠가 때린 적 있어?
아동: 아니요. 그런 적 없어요.
"""

    major_types = ["신체학대"]

    result = analyze_subtypes(
        text=text,
        major_types=major_types,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )