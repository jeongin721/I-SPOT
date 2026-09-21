"""
I-SPOT 2차 세부유형 판정 LLM 모듈.
1차 대분류 결과를 받아 세부 위험신호와 여러 근거 발화를 구조화한다.
"""

import difflib
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ============================================================
# 1. 세부유형 정의
# ============================================================

SUBTYPE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "신체학대": {
        "직접 신체 가해": (
            "아동을 때리거나 차거나 꼬집거나 물어뜯거나 조르는 등 "
            "신체에 직접적인 위해를 가한 경우. "
            "손·발뿐 아니라 도구를 이용해 때린 경우에도 이 유형에 해당할 수 있으며, "
            "도구가 사용된 경우에는 '도구·위험수단 사용'과 동시에 선택할 수 있다."
        ),
        "도구·위험수단 사용": (
            "막대기, 벨트, 흉기, 뜨거운 물질, 화학물질 등 "
            "도구나 위험한 수단을 사용하여 아동에게 위해를 가한 경우. "
            "도구를 이용해 직접 신체 위해를 가했다면 "
            "'직접 신체 가해'와 동시에 선택할 수 있다."
        ),
        "신체적 강압·제압": (
            "아동을 붙잡거나 누르거나 묶거나 밀치거나 움직이지 못하게 하는 등 "
            "신체적인 힘으로 강압하거나 제압한 경우"
        ),
    },

    "정서학대": {
        "폭언·모욕": (
            "욕설, 모욕, 비난, 인격 비하, 수치심을 주는 말 등으로 "
            "아동의 정서에 해를 가하는 경우"
        ),
        "위협·공포 유발": (
            "죽이겠다는 말, 때리겠다는 협박, 버리겠다는 위협 등으로 "
            "아동에게 공포나 두려움을 유발하는 경우"
        ),
        "통제·강요·고립": (
            "아동의 행동이나 인간관계를 과도하게 통제하거나, 원하지 않는 행동을 "
            "강요하거나, 격리·고립·차별하는 경우"
        ),
        "가정폭력·폭력상황 노출": (
            "부모 또는 보호자 간의 폭행, 심한 언쟁, 폭력적 상황 등을 "
            "아동이 직접 보거나 듣게 되는 경우"
        ),
    },

    "성학대": {
        "성적 노출·성희롱": (
            "아동에게 성적인 신체 노출을 보이거나, 음란물을 보여주거나, "
            "성적 발언·성희롱 등 비접촉 성적 행위를 한 경우"
        ),
        "성적 접촉·추행": (
            "아동의 가슴, 성기, 엉덩이 등 신체를 성적인 목적으로 만지거나 "
            "아동에게 성적 신체접촉을 강요한 경우"
        ),
        "성교·유사성행위": (
            "성교, 삽입, 구강성교 등 성교 또는 이에 준하는 유사성행위를 "
            "아동에게 행하거나 강요한 경우"
        ),
        "성적 착취": (
            "성매매, 대가를 조건으로 한 성적 행위, 성적 사진·영상 제작·전송·판매 등 "
            "아동을 성적으로 이용하거나 착취한 경우"
        ),
    },

    "방임": {
        "기본적 보호·양육 방임": (
            "식사, 의복, 위생, 안전한 보호, 감독 등 기본적인 양육과 보호를 "
            "적절히 제공하지 않는 경우"
        ),
        "교육적 방임": (
            "정당한 사유 없이 아동을 학교에 보내지 않거나 "
            "지속적인 결석·미취학 상태를 방치하는 경우"
        ),
        "의료적 방임": (
            "질병, 부상, 치료 필요가 있음에도 필요한 의료기관 방문이나 "
            "치료를 제공하지 않는 경우"
        ),
        "유기": (
            "보호자가 아동을 버리고 떠나거나 장기간 방치하여 "
            "사실상 보호관계를 중단한 경우"
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
    threshold: float = 0.88,
    max_search_chars: int = 3000,
) -> Optional[Tuple[int, int, float]]:
    """
    fuzzy matching은 exact/normalized exact 실패 시에만 사용한다.

    긴 전체 세션을 그대로 반복 탐색하면 느려질 수 있으므로
    max_search_chars 상한을 둔다.
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
        and best_ratio >= threshold
    ):
        return (
            best_start,
            best_end,
            best_ratio,
        )

    return None


def verify_evidence(
    source_text,
    evidence,
    fuzzy_threshold: float = 0.88,
    max_fuzzy_search_chars: int = 3000,
):
    """
    LLM이 반환한 evidence가 실제 원문에 존재하는지 검증한다.
    exact → normalized → fuzzy 순서로 확인한다.
    """

    if not source_text or not evidence:
        return {
            "evidence_verified": False,
            "evidence_match_method": "unverified",
            "evidence_start": None,
            "evidence_end": None,
            "matched_evidence": None,
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
        }

    # ============================================================
    # 3. Fuzzy match
    # ============================================================

    fuzzy_result = _fuzzy_match(
        source_text=source_text,
        evidence=evidence,
        threshold=fuzzy_threshold,
        max_search_chars=max_fuzzy_search_chars,
    )

    if fuzzy_result is not None:
        fuzzy_start, fuzzy_end, _fuzzy_ratio = fuzzy_result

        return {
            "evidence_verified": True,
            "evidence_match_method": "fuzzy",
            "evidence_start": fuzzy_start,
            "evidence_end": fuzzy_end,
            "matched_evidence": source_text[fuzzy_start:fuzzy_end],
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

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            response = (
                client.chat.completions.create(
                    model=model,
                    timeout=timeout_seconds,
                    response_format={
                        "type":
                            "json_object"
                    },
                    messages=[
                        {
                            "role":
                                "system",
                            "content":
                                system_prompt,
                        },
                        {
                            "role":
                                "user",
                            "content":
                                user_prompt,
                        },
                    ],
                )
            )

            raw_content = (
                response
                .choices[0]
                .message
                .content
            )

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
) -> Dict[str, Any]:
    """
    1차 모델에서 탐지된 major_types만 대상으로
    세부 위험신호를 분석한다.

    timeout_seconds 기본값은 로컬 Ollama 호출(수십~백여 초) 기준으로
    잡았다 — 예전 OpenAI 전용(30초) 그대로 두면 응답 전에 타임아웃되어
    처음부터 재시도만 반복하다 실패하는 경우가 있었다.
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