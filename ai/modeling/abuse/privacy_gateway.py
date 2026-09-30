"""
Privacy Gateway — 조직 밖(외부 LLM API, 예: GPT)으로 나가는 마지막 관문.

pii_masking.mask_pii()는 로컬 2차 LLM(Ollama 등)에 넘기기 전 "최선을 다해
가리기" 용도로 설계됐다. 이 모듈은 그것과 기준이 다르다 — 조직 경계를
넘어가는 마지막 지점이라, 가려서 보내는 게 아니라 확신이 서지 않으면
아예 전송을 막는다("통과/차단" 방식).

이 모듈이 검사하는 대상은 로컬 1차 처리(예: Ollama 구조화 출력)가 만든
summary/risk_factors/evidence/need_confirmation 같은 JSON 전체다. 문자열
하나만 보지 않고 모든 필드를 재귀적으로 순회해서 검사한다.

단계:
  1) 필드마다 mask_pii()로 정규식(주민번호/전화번호/이메일)+NER(이름/
     기관명/지역명)을 적용한다.
  2) known_identifiers(사례에 등록된 실제 이름 등)가 주어지면, 마스킹된
     텍스트에서 그 문자열을 정확 매칭으로 한 번 더 지운다. 이건 NER의
     추측이 아니라 이미 아는 값과의 정확 대조라 놓칠 일이 없다.
     KLUE-NER 5,000문장 기준 NER의 사람이름 미탐률이 36.8%(2026-09-30
     측정)라 이 단계가 실질적인 안전망 역할을 한다. 값은
     case_store.get_known_identifiers(case_id)로 가져와 넘기면 된다
     (case_store.set_known_identifiers로 등록/갱신).
  3) 마스킹 후 텍스트를 같은 정규식/NER로 다시 검사한다. 이 재검사는
     NER이 애초에 놓친 표현(NER의 근본적인 사각지대)까지 잡아주진
     못한다 — 어차피 같은 탐지기이기 때문이다. 대신 "탐지는 됐는데
     실제로 치환이 안 된" 구현상의 실수를 잡는 안전망 역할을 한다.
     known_identifiers 쪽은 정확 매칭이라 이 재검사가 실질적인 효과가
     있다.
  4) 위 검사 중 하나라도 걸리면 PrivacyGatewayBlocked를 던진다. 예외
     메시지에는 실제 내용이 아니라 막힌 필드 경로와 사유만 담는다.
  5) 통과/차단 여부와 필드 개수만 로그로 남긴다. 원문·마스킹된 텍스트
     어느 쪽도 로그에 남기지 않는다.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ai.modeling.abuse.pii_masking import (
    _REGEX_RULES,
    _decode_ner_spans,
    mask_pii,
)
from ai.modeling.abuse.second_stage_llm import SUBTYPE_DEFINITIONS

logger = logging.getLogger("privacy_gateway")

# NER은 문맥 없는 짧은 단어를 사람/기관명으로 오탐하기 쉽다 — 예를 들어
# "방임"(학대 유형 라벨) 한 단어만 있으면 사람 이름으로, "정서학대"는
# 기관명으로 오탐한다(직접 확인함, 2026-09-30). evidence[i].type처럼
# 구조화된 필드에 이런 고정 어휘가 그대로 들어오면 개인정보가 아닌데도
# 마스킹되거나 차단돼 데이터가 깨진다. 이 파이프라인의 학대 유형
# 대분류/세부유형은 개인 식별 정보가 될 수 없는 고정된 분류 체계이므로,
# second_stage_llm.SUBTYPE_DEFINITIONS(단일 진실 공급원)에서 그대로
# 가져와 마스킹 대상에서 제외한다.
_NON_PII_LABELS = {
    major_type
    for major_type in SUBTYPE_DEFINITIONS
} | {
    subtype
    for subtypes in SUBTYPE_DEFINITIONS.values()
    for subtype in subtypes
}


class PrivacyGatewayBlocked(Exception):
    """
    외부 전송 직전 검증에 실패해 전송을 막을 때 발생시킨다.
    reasons에는 실제 내용이 아니라 막힌 필드 경로와 사유만 담는다.
    """

    def __init__(self, reasons: List[str]):
        self.reasons = reasons
        super().__init__(
            "Privacy Gateway 차단 — 아래 필드를 확인하세요: "
            + "; ".join(reasons)
        )


@dataclass
class GatewayResult:
    payload: Any
    # 로컬 전용 복원 맵(마스킹 토큰 -> 원문). 외부로 절대 전송하지 않는다.
    entity_map: Dict[str, str]
    field_count: int
    masked_field_count: int


# ============================================================
# 1. JSON 순회 유틸
# ============================================================

def _walk_strings(value: Any, path: str = ""):
    """dict/list 어디에 문자열이 있든 (경로, 문자열) 쌍으로 순회한다."""

    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, sub_value in value.items():
            yield from _walk_strings(sub_value, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")


def _rebuild(value: Any, replacements: Dict[str, str], path: str = "") -> Any:
    if isinstance(value, str):
        return replacements.get(path, value)
    if isinstance(value, dict):
        return {
            key: _rebuild(sub_value, replacements, f"{path}.{key}" if path else key)
            for key, sub_value in value.items()
        }
    if isinstance(value, list):
        return [
            _rebuild(item, replacements, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    return value


# ============================================================
# 2. 마스킹 후 재검사(잔존 여부만 확인, 실제 내용은 반환하지 않음)
# ============================================================

# 마스킹 토큰 자체("[PERSON_01]" 등)를 그대로 NER에 다시 넣으면, 토큰
# 안의 영어 단어(PERSON/ORG/LOCATION 등)를 NER이 또 이름·기관명으로
# 오인해서 항상 걸린다(직접 확인함 — 이러면 개인정보가 하나라도 있는
# payload는 전부 차단되어 Gateway가 무용지물이 된다). 재검사 전에 토큰
# 자리를 동일한 길이의 중립 문자(●)로 바꿔서, 순수하게 "마스킹되지
# 않고 남은 부분"만 검사한다. 길이를 유지하는 이유는 regex 재검사(주민
# 번호 등)의 위치 판단에 영향이 없게 하기 위함이다.
_MASK_TOKEN_PATTERN = re.compile(r"\[[A-Z_]+_\d+\]")


def _blank_out_mask_tokens(text: str) -> str:
    return _MASK_TOKEN_PATTERN.sub(lambda m: "●" * len(m.group()), text)


_TOKEN_PARTS_PATTERN = re.compile(r"^\[([A-Z]+)_(\d+)\]$")


def _globalize_tokens(
    masked_text: str,
    local_entity_map: Dict[str, str],
    global_original_to_token: Dict[str, str],
    global_counters: Dict[str, int],
) -> str:
    """
    mask_pii()는 필드(문자열) 하나마다 독립적으로 번호를 매긴다(각자
    PERSON_01부터 다시 시작). 그래서 payload 전체를 필드별로 따로
    처리하면, 서로 다른 필드의 PERSON_01이 실제로는 다른 사람을
    가리키는 채로 같은 토큰명을 쓰게 된다 — 나중에 restore_pii로
    복원할 때 한쪽이 다른 쪽 이름으로 잘못 복원되는 사고로 이어진다
    (실제로 확인함: summary의 [PERSON_01]=김민수, evidence의
    [PERSON_01]=박영희가 같은 키로 덮어써짐).

    이 함수는 필드별 로컬 토큰을 "같은 원문 값은 항상 같은 전역
    토큰, 다른 원문 값은 절대 같은 토큰을 안 씀" 규칙으로 payload
    전체에서 통일한다.
    """

    for local_token, original in local_entity_map.items():
        global_token = global_original_to_token.get(original)

        if global_token is None:
            match = _TOKEN_PARTS_PATTERN.match(local_token)
            prefix = match.group(1) if match else "ENTITY"
            global_counters[prefix] = global_counters.get(prefix, 0) + 1
            global_token = f"[{prefix}_{global_counters[prefix]:02d}]"
            global_original_to_token[original] = global_token

        if local_token != global_token:
            masked_text = masked_text.replace(local_token, global_token)

    return masked_text


def _residual_reasons(text: str, known_identifiers: List[str]) -> List[str]:
    reasons = []
    scan_text = _blank_out_mask_tokens(text)

    for tag, pattern in _REGEX_RULES:
        if pattern.search(scan_text):
            reasons.append(f"{tag} 패턴 잔존")

    try:
        ner_spans = _decode_ner_spans(scan_text)
    except Exception:
        # NER 재검사 자체가 실패하면 안전하지 않다고 보고 차단한다.
        reasons.append("NER 재검사 실패")
        ner_spans = []

    if ner_spans:
        tags = sorted({tag for _, _, tag in ner_spans})
        reasons.append(f"NER 개체 잔존({','.join(tags)})")

    for name in known_identifiers:
        if name in text:
            reasons.append("등록된 실명 잔존")
            break

    return reasons


# ============================================================
# 3. 외부 공개 함수
# ============================================================

def review(
    payload: Dict[str, Any],
    known_identifiers: Optional[List[str]] = None,
) -> GatewayResult:
    """
    payload(로컬 1차 처리가 만든 요약/위험요인/근거 등 JSON)를 검사해서,
    안전하다고 확인되면 마스킹된 payload를 돌려주고, 하나라도 확신이 서지
    않으면 PrivacyGatewayBlocked를 던진다(이 경우 호출부는 외부 전송을
    하지 않고 사람이 확인하도록 넘겨야 한다).

    known_identifiers: 사례에 등록된 아동/보호자 실명 등.
    case_store.get_known_identifiers(case_id)의 반환값을 그대로 넘기면 된다.
    """

    known_identifiers = [
        name.strip()
        for name in (known_identifiers or [])
        if name and name.strip()
    ]

    fields = list(_walk_strings(payload))

    replacements: Dict[str, str] = {}
    # 원문 값 -> 전역 토큰. 같은 사람/기관이 여러 필드에 나와도 항상
    # 같은 토큰을 쓰게 하는 payload 전체 공유 상태다.
    global_original_to_token: Dict[str, str] = {}
    global_counters: Dict[str, int] = {}
    blocked: List[str] = []

    for path, text in fields:
        if not text or not text.strip():
            replacements[path] = text
            continue

        if text.strip() in _NON_PII_LABELS:
            replacements[path] = text
            continue

        try:
            masked, local_entity_map = mask_pii(text)
        except Exception:
            blocked.append(f"{path}: 마스킹 처리 실패")
            continue

        # 사례에 등록된 실명은 mask_pii가 못 잡았을 수 있으니 정확
        # 매칭으로 보강한다. 로컬 토큰 형식을 mask_pii 출력과 맞춰
        # 두면 바로 아래 _globalize_tokens에서 같이 처리된다.
        for index, name in enumerate(
            (n for n in known_identifiers if n in masked),
            start=1,
        ):
            local_token = f"[KNOWN_{index:02d}]"
            masked = masked.replace(name, local_token)
            local_entity_map[local_token] = name

        masked = _globalize_tokens(
            masked,
            local_entity_map,
            global_original_to_token,
            global_counters,
        )

        reasons = _residual_reasons(masked, known_identifiers)

        if reasons:
            blocked.append(f"{path}: {', '.join(reasons)}")
            continue

        replacements[path] = masked

    if blocked:
        logger.warning(
            "Privacy Gateway 차단 — 전체 %d개 필드 중 %d개 문제",
            len(fields),
            len(blocked),
        )
        raise PrivacyGatewayBlocked(blocked)

    combined_entity_map = {
        token: original
        for original, token in global_original_to_token.items()
    }

    logger.info(
        "Privacy Gateway 통과 — 필드 %d개 전부 통과, 마스킹 토큰 %d개",
        len(fields),
        len(combined_entity_map),
    )

    return GatewayResult(
        payload=_rebuild(payload, replacements),
        entity_map=combined_entity_map,
        field_count=len(fields),
        masked_field_count=len(combined_entity_map),
    )


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    sample_payload = {
        "summary": "아동은 엄마 김민수씨와 함께 살고 있으며 은평초등학교에 재학 중이다.",
        "risk_factors": ["신체학대", "방임"],
        "evidence": [
            {"type": "신체학대", "quote": "아빠가 저를 때렸어요. 이번 주 월요일에요."},
            {"type": "방임", "quote": "이모 박영희 이모가 가끔 밥을 챙겨줘요."},
        ],
        "need_confirmation": ["아빠와의 접촉 빈도 확인 필요"],
    }

    print("=== 정상 케이스(등록된 실명 없이) ===")
    result = review(sample_payload)
    print(result.payload)
    print("entity_map(로컬 전용):", result.entity_map)

    print()
    print("=== 등록된 실명 매칭까지 포함 ===")
    result2 = review(sample_payload, known_identifiers=["김민수", "박영희"])
    print(result2.payload)
    print("entity_map(로컬 전용):", result2.entity_map)
