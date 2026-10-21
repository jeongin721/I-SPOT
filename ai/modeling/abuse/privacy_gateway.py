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
  3) 마스킹 후 텍스트를 같은 정규식/NER로 다시 검사한다. 걸리면
     막는 대신, 걸린 자리를 한 번 더 가리고 다시 검사한다(최대
     _MAX_RESIDUAL_MASK_ROUNDS번 — 2026-10-21 Mingyu 요청). NER이
     처음엔 놓쳤다가 재검사에서는 잡는 경우가 실제로 흔해서(긴
     상담에는 거의 항상 이름이 있음), 한 번 걸렸다고 바로 막으면
     긴 회기 분석이 대부분 실패한다. 반복해도 남으면 그때 막는다 —
     "탐지는 됐는데 치환이 안 된" 경우(재검사 1회면 바로 사라짐)와
     "재검사라야 보이는" 경우(반복 가리기로 사라짐) 둘 다 구제하고,
     그래도 남는 건 여전히 차단한다.
  4) 위 반복 끝에도 남아 있으면 PrivacyGatewayBlocked를 던진다. 예외
     메시지에는 실제 내용이 아니라 막힌 필드 경로와 사유만 담는다.
  5) 통과/차단 여부와 필드 개수만 로그로 남긴다. 원문·마스킹된 텍스트
     어느 쪽도 로그에 남기지 않는다.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ai.modeling.abuse.pii_masking import (
    _NER_LABEL_TO_TOKEN_PREFIX,
    _REGEX_RULES,
    _STRUCTURAL_PREFIX_RE,
    _decode_ner_spans,
    _is_within_structural_prefix,
    _refine_org_prefix,
    _select_non_overlapping_spans,
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


# 잔존 검사에 걸린 뒤, 바로 막지 않고 몇 번 더 가려보고 그래도 남으면
# 막는다. 처음 마스킹(mask_pii) 1번 + 이 상수만큼 추가 시도 = 최대
# 1+_MAX_RESIDUAL_MASK_ROUNDS번(2026-10-21 Mingyu 요청 — "최대 2~3번,
# 그래도 남으면 그때 막기". 아래 _mask_residual_once가 "이미 아는 값
# 정확 매칭"을 먼저 하도록 바꾼 뒤에는 2~3번으로도 실제로 수렴한다 —
# 바꾸기 전에는 같은 이름이 반복되는 긴 글에서 라운드가 더 필요했다,
# 아래 설명 참고).
_MAX_RESIDUAL_MASK_ROUNDS = 3

# 정확 매칭으로 훑을 때 이 길이 미만인 값은 건너뛴다. 한 글자짜리
# 조각("희", "g" 등 — NER이 창 경계에서 이름을 반쪽만 잡은 결과가
# global_original_to_token에 섞여 들어올 수 있다)을 그대로 문자열
# 치환하면 무관한 단어 속에서도 그 글자를 먹어버려 본문이 망가진다
# (2026-10-21, 디버그 중 발견).
_MIN_EXACT_SWEEP_LENGTH = 2

# 상담 도메인 고정 표현 — NER이 한 번이라도 사람/기관으로 잘못 잡아
# global_original_to_token에 들어가더라도, 정확 매칭 훑기 대상에서는
# 아예 뺀다. 이 낱말들은 "아동학대"·"아동보호전문기관"·화자표시
# "아동:"처럼 더 큰 낱말/구조 표식의 일부로 아주 자주 나와서, 문자열
# 그대로 훑으면 그 안의 글자만 잘라 가린다(2026-10-21 Mingyu 지적 —
# 실제 모델로 "아동"이 한 번 PS로 잘못 잡히자 본문의 "아동학대"·
# "아동보호전문기관"까지 깨졌음).
_SWEEP_TARGET_BLOCKLIST = {"아동", "상담사", "보호자"}


def _mask_residual_once(
    masked_text: str,
    known_identifiers: List[str],
    global_original_to_token: Dict[str, str],
    global_counters: Dict[str, int],
) -> Tuple[str, bool]:
    """
    이미 마스킹된 텍스트에 남은 개체를 찾아 한 번 더 가린다. 두 단계로
    한다 — global_original_to_token/global_counters는 그대로 이어 써서,
    같은 원문은 앞 단계와 같은 전역 토큰 규칙을 따르고 토큰 번호도 앞
    단계와 겹치지 않는다(2026-10-21 Mingyu 요청).

    1) NER/정규식으로 이 라운드에 새로 보이는 개체를 먼저 찾아 가린다
       (기존 로직).
    2) 그러고 나서 남은 자리에, known_identifiers와 지금까지 이
       payload에서 이미 찾아낸 원문(global_original_to_token의 키) 중
       2글자 이상인 것을 정확 매칭으로 훑어 가린다. 같은 이름이 긴
       글에서 여러 번 나오면, 창(window) 경계 위치에 따라 어떤
       자리에서는 NER이 전체를 잡고 어떤 자리에서는 조각만 잡는다
       (2026-10-21 실제 모델로 확인 — "김철수"가 20번 나오는 글에서
       일부는 "김철수", 일부는 "김철"만 잡힘). NER을 몇 번이고 다시
       돌리는 것보다, 이미 안전하게 확인된 문자열을 직접 찾는 쪽이
       더 빠르고 확실하게 수렴한다.

       NER을 먼저 하는 이유: 순서를 반대로 하면 짧은 조각("김철")을
       먼저 정확 매칭으로 치환하다가, 그 조각이 접두어로 들어간 더
       긴 이름("김철수")의 일부까지 잘라 먹는다(2026-10-21 테스트로
       발견 — "김철수"가 "[기존 김철 토큰]수"로 망가짐). NER을 먼저
       돌려 그 라운드에 "김철수"를 통째로 잡을 기회를 먼저 준 뒤,
       그래도 못 잡은 자리만 정확 매칭으로 보강하면 이 사고가 줄어든다
       (완전히 없어지진 않는다 — NER이 그 라운드에도 "김철수"를 못
       잡으면 여전히 "김철"에 먼저 걸릴 수 있다. 짧은 조각 자체를
       남기지 않는 게 근본 해결이라 당장은 급한 요청 범위 밖으로
       남겨 둔다).

       정확 매칭은 _SWEEP_TARGET_BLOCKLIST에 있는 상담 고정 표현은
       아예 빼고, 그 외의 값도 줄 머리 구조 표식 범위 안의 일치는
       건너뛴다 — 한 번이라도 문맥 없이 잘못 잡힌 짧은 값("UN" 등)이
       글 전체의 같은 글자(화자표시 포함)를 몽땅 바꿔버리는 걸
       막는다(2026-10-21 Mingyu 지적, 실제 모델로 확인 — "UN" 하나
       오탐이 "UNKNOWN:" 119곳을 깨뜨렸음).

    1단계(NER/정규식)에서 찾은 범위가 이미 가린 토큰 자리(scan_text의
    ●)까지 걸치면, ● 앞까지만 남기고 자른다 — 안 그러면 실제 글자와
    토큰 괄호 일부가 섞인 값("박정[P" 등)으로 새 토큰을 만들면서 기존
    토큰이 깨진다(2026-10-21 Mingyu 지적, 가짜 판정으로 재현).

    반환: (다시 가린 텍스트, 이번 라운드에서 뭔가 더 가렸는지 여부).
    더 가릴 게 없으면 (masked_text, False) — 호출부가 더 반복해도
    소용없다는 걸 알고 멈출 수 있게 한다.
    """

    changed = False

    scan_text = _blank_out_mask_tokens(masked_text)

    spans: List[Tuple[int, int, str]] = []

    for tag, pattern in _REGEX_RULES:
        for match in pattern.finditer(scan_text):
            spans.append((match.start(), match.end(), tag))

    spans.extend(_decode_ner_spans(scan_text))

    selected = _select_non_overlapping_spans(spans)

    if selected:
        resolved: List[Tuple[int, int, str]] = []

        for start, end, tag in selected:
            # 이미 가린 토큰 자리는 scan_text에서 ●로 바뀌어 있다(같은
            # 글자 수 유지). NER이 실제 글자("박정")에서 시작해 그
            # ● 구간까지 걸치는 범위를 잡으면, masked_text에서 그
            # 자리를 그대로 잘라낼 때 토큰 괄호 일부("[P")까지 섞여
            # 들어가 기존 토큰이 깨진다(2026-10-21 Mingyu 지적,
            # 가짜 판정으로 재현 — entity_map에 "박정[P" 같은 값이
            # 생기고 복원 결과가 원문과 달라짐). ● 앞까지만 남기고,
            # ●로 시작하면(실제 글자가 하나도 없으면) 통째로 버린다.
            bullet_index = scan_text.find("●", start, end)
            if bullet_index != -1:
                end = bullet_index
            if end <= start:
                continue

            original = masked_text[start:end]
            mapped = _NER_LABEL_TO_TOKEN_PREFIX.get(tag, tag)
            prefix = (
                _refine_org_prefix(original) if mapped == "ORG" else mapped
            )

            token = global_original_to_token.get(original)

            if token is None:
                global_counters[prefix] = global_counters.get(prefix, 0) + 1
                token = f"[{prefix}_{global_counters[prefix]:02d}]"
                global_original_to_token[original] = token

            resolved.append((start, end, token))

        if resolved:
            for start, end, token in sorted(resolved, key=lambda s: -s[0]):
                masked_text = masked_text[:start] + token + masked_text[end:]

            changed = True

    exact_targets = sorted(
        {
            name
            for name in set(known_identifiers) | set(global_original_to_token)
            if len(name) >= _MIN_EXACT_SWEEP_LENGTH
            and name not in _SWEEP_TARGET_BLOCKLIST
        },
        key=len,
        reverse=True,  # 긴 문자열(“김철수”)부터 찾아야 그 안에 포함된
        # 짧은 조각(“김철”)이 먼저 걸려 나머지 글자(“수”)만 덩그러니
        # 남는 일이 없다.
    )

    for name in exact_targets:
        if name not in masked_text:
            continue

        # 줄 머리 구조 표식 범위와 이미 가린 토큰(예: "[SCHOOL_01]")
        # 범위 안의 일치는 건너뛴다. 전자는 그 범위를 벗어나는 글자가
        # 한 번이라도 잘못 잡혀 global_original_to_token에 들어가면
        # (예: "UNKNOWN:"과 무관한 자리에서 "UN"이 기관으로 오탐),
        # 문자열 그대로 바꿔치기할 때 올바른 자리의 "UNKNOWN:"까지
        # 전부 깨진다(2026-10-21 Mingyu 지적 — 실제 모델로 화자표시
        # 299개 중 119개가 이렇게 깨짐). 후자는 "CH"가 한 번 기관으로
        # 잘못 잡히면 그 뒤로 이미 가린 "[SCHOOL_01]" 안의 "CH"까지
        # 바꿔서 "[S[ORG_01]OOL_01]"처럼 토큰 자체가 깨진다(2026-10-21
        # Mingyu 지적, 가짜 판정으로 재현).
        protected_zones = [
            (match.start(), match.end())
            for match in _STRUCTURAL_PREFIX_RE.finditer(masked_text)
        ] + [
            (match.start(), match.end())
            for match in _MASK_TOKEN_PATTERN.finditer(masked_text)
        ]

        matches: List[Tuple[int, int]] = []
        search_start = 0
        while True:
            index = masked_text.find(name, search_start)
            if index == -1:
                break
            end_index = index + len(name)
            if not _is_within_structural_prefix(
                (index, end_index), protected_zones
            ):
                matches.append((index, end_index))
            search_start = end_index

        if not matches:
            continue

        token = global_original_to_token.get(name)

        if token is None:
            global_counters["KNOWN"] = global_counters.get("KNOWN", 0) + 1
            token = f"[KNOWN_{global_counters['KNOWN']:02d}]"
            global_original_to_token[name] = token

        for start, end in sorted(matches, key=lambda s: -s[0]):
            masked_text = masked_text[:start] + token + masked_text[end:]

        changed = True

    return masked_text, changed


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

        # 잔존이 잡히면 바로 막지 않고, 잡힌 자리를 한 번 더 가리고
        # 다시 검사한다(_MAX_RESIDUAL_MASK_ROUNDS번까지 — 모듈 docstring
        # 3번 항목, 2026-10-21 Mingyu 요청).
        rounds = 0
        while reasons and rounds < _MAX_RESIDUAL_MASK_ROUNDS:
            masked, changed = _mask_residual_once(
                masked,
                known_identifiers,
                global_original_to_token,
                global_counters,
            )
            rounds += 1

            if not changed:
                # 더 가릴 게 없는데 reasons가 남아 있으면(이론상 드묾,
                # 예: NER 재검사 자체가 실패) 반복해도 소용없으니 멈춘다.
                break

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


def mask_for_outbound(
    text: str,
    known_identifiers: Optional[List[str]] = None,
) -> Tuple[str, Dict[str, str]]:
    """
    외부(OpenAI) LLM 호출 직전에 쓰는 전용 진입점 —
    llm_backend.build_openai_client_and_model()로 만든 client에 보낼
    텍스트에 쓴다. review()의 차단형 검증을 거쳐 (masked_text,
    entity_map)을 반환한다.

    2026-10-02부터 실제 서비스 경로(2차 세부유형 분석, 상담 요약/
    상담일지/체크리스트 초안, note 모드 1차 보완 체크)와 합성 데이터
    검수 도구(review_modelB_labels.py, eval_modelA_qa_llm_verify.py)까지
    전부 OpenAI로 나가므로 이 함수를 쓴다. make_note_multitype_v1.py처럼
    build_llm_client_and_model()로 로컬 Ollama를 쓰는 경우만
    pii_masking.mask_pii()를 직접 쓰면 된다.

    known_identifiers가 없으면(케이스에 등록된 실명을 모르면) review()는
    NER/정규식 재검사만 적용한다 — 그래도 mask_pii() 단독보다 안전하다
    (예: 마스킹 토큰 자체가 NER에 다시 걸려 치환이 씹히는 실수를 잡아냄).

    PrivacyGatewayBlocked가 나면 그대로 위로 던진다 — 호출부(웹 핸들러)가
    이미 다른 예외처럼 오류 화면으로 보여주므로 여기서 따로 잡지 않는다.
    전송을 막아야 할 상황에서 조용히 로컬로 돌아가 버리면 상담사가
    무엇이 왜 막혔는지 알 수 없기 때문이다.
    """

    result = review({"text": text}, known_identifiers=known_identifiers)

    return result.payload["text"], result.entity_map


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
