"""
개인정보 탐지 및 비식별화 레이어.

상담 텍스트를 외부 LLM(second_stage_llm.py, checklist_llm.py)에 보내기 전에
이름·기관명(학교/병원)·지역명·주민등록번호·전화번호 등 개인 식별 정보를
정규식 + 개체명 인식(NER)으로 탐지해 대체 토큰([PERSON_01] 등)으로 치환한다.

entity_map(토큰 -> 원문)은 외부로 전송하지 않고 호출 측(로컬)에서만
보관한다 — 외부 LLM에는 masked_text만 전달한다.
"""

import re
from typing import Dict, List, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification


# ============================================================
# 1. 정규식 기반 — 형식이 고정된 개인정보
# ============================================================
# 주민등록번호/전화번호/이메일은 NER보다 정규식이 더 정확하고 빠르다.

_RRN_PATTERN = re.compile(r"\d{6}[-\s]?[1-4]\d{6}")
_PHONE_PATTERN = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

_REGEX_RULES: List[Tuple[str, re.Pattern]] = [
    ("RRN", _RRN_PATTERN),
    ("PHONE", _PHONE_PATTERN),
    ("EMAIL", _EMAIL_PATTERN),
]


# ============================================================
# 2. NER 기반 — 형식이 고정되지 않은 개인정보 (이름/기관명/지명)
# ============================================================
# 별도 파인튜닝 없이 공개 체크포인트를 그대로 사용한다.
# 도메인 특화(가족관계 표현 등) 확장은 필요성이 확인되면 추후 진행한다.

# monologg/koelectra-base-v3-naver-ner(뉴스 도메인 학습)에서 교체함 —
# 상담 도메인 실사용 중 "아동"을 지명(LOC)으로, "선생님"/"밤"을 반쪽만
# 잘라 오탐하는 문제를 확인했다(pii_masking.py 관련 이슈 확인, 2026-09-30).
# Leo97/KoELECTRA-small-v3-modu-ner(국립국어원 모두의 말뭉치 학습,
# 다운로드 수 최상위권)로 바꾸니 같은 문장에서 이런 오탐이 없었고,
# 실제 이름·기관명·지명은 그대로 잘 잡았다(직접 비교 테스트로 확인).
NER_MODEL_NAME = "Leo97/KoELECTRA-small-v3-modu-ner"

_ner_tokenizer = AutoTokenizer.from_pretrained(NER_MODEL_NAME)
_ner_model = AutoModelForTokenClassification.from_pretrained(NER_MODEL_NAME)
_ner_model.eval()

# 마스킹 대상은 사람이름(PS)/기관명(OG)/지역명(LC)뿐이다. 이 모델은
# 모두의 말뭉치 태그 체계(PS/OG/LC/DT/TI/QT/CV/AF/FD/TR/EV/AM/PT/MT/TM)를
# 쓴다 — 날짜/시간/수량 등 나머지 태그는 개인 식별 정보가 아니므로
# 건드리지 않는다. 토큰 이름(PERSON/ORG/LOCATION)은 기존과 동일하게
# 유지해서, 이 값을 쓰는 다른 코드(복원 로직 등)는 안 건드려도 된다.
_NER_LABEL_TO_TOKEN_PREFIX = {
    "PS": "PERSON",
    "OG": "ORG",
    "LC": "LOCATION",
}

_SCHOOL_KEYWORDS = ("학교", "유치원", "어린이집")
_HOSPITAL_KEYWORDS = ("병원", "의원", "센터")


def _refine_org_prefix(entity_text: str) -> str:
    """ORG 태그 중 학교/병원 이름은 더 구체적인 토큰으로 구분한다."""

    if any(keyword in entity_text for keyword in _SCHOOL_KEYWORDS):
        return "SCHOOL"

    if any(keyword in entity_text for keyword in _HOSPITAL_KEYWORDS):
        return "HOSPITAL"

    return "ORG"


def _decode_ner_spans(text: str) -> List[Tuple[int, int, str]]:
    """
    NER 모델 출력을 (시작, 끝, 태그) 형태의 원문 char span으로 복원한다.
    subword(##) 경계는 offset_mapping으로 보정한다.
    """

    encoded = _ner_tokenizer(
        text,
        return_offsets_mapping=True,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    offsets = encoded.pop("offset_mapping")[0].tolist()

    with torch.no_grad():
        logits = _ner_model(**encoded).logits

    pred_ids = torch.argmax(logits, dim=-1)[0].tolist()
    id2label = _ner_model.config.id2label

    # 체크포인트마다 라벨 표기 방식이 다르다("B-PS"처럼 앞에 B/I를
    # 붙이는 표준 방식도 있고, 예전에 쓰던 모델처럼 "PER-B"처럼 뒤에
    # 붙이는 방식도 있었다). 어느 쪽이든 태그 이름은 "B"/"I"가 아닌
    # 나머지 부분이므로, 그 부분만 골라내면 모델이 바뀌어도 안전하다.
    # 또한 한 단어 내 연속된 음절에도 "B"를 반복해서 매기는 체크포인트가
    # 있어(예: "김민"=B, "##수"=B), B/I 구분보다 "같은 태그 + 문자
    # 위치가 이어짐(공백 없이 인접)"을 기준으로 병합해야 실제 단어
    # 단위 span이 정확히 복원된다.

    spans: List[Tuple[int, int, str]] = []
    current_start = None
    current_end = None
    current_tag = None

    def _flush():
        if current_tag is not None:
            spans.append((current_start, current_end, current_tag))

    def _extract_tag(label: str):
        if label in ("O", "0"):
            return None
        parts = [p for p in label.split("-") if p not in ("B", "I")]
        return parts[0] if parts else None

    for (start, end), pred_id in zip(offsets, pred_ids):
        # 특수 토큰([CLS], [SEP], padding)은 offset이 (0, 0)이다.
        if start == end:
            continue

        label = id2label[pred_id]
        tag = _extract_tag(label)

        if tag is None or tag not in _NER_LABEL_TO_TOKEN_PREFIX:
            _flush()
            current_start = current_end = current_tag = None
            continue

        if current_tag == tag and start <= current_end:
            current_end = end
        else:
            _flush()
            current_start, current_end, current_tag = start, end, tag

    _flush()

    return spans


# ============================================================
# 3. 마스킹
# ============================================================

def _select_non_overlapping_spans(
    spans: List[Tuple[int, int, str]],
) -> List[Tuple[int, int, str]]:
    """
    겹치는 span 중 먼저 시작하는(동률이면 더 긴) 것을 우선 채택한다.
    정규식 결과를 NER 결과보다 앞에 넣어 호출하면 정규식이 우선된다.
    """

    ordered = sorted(spans, key=lambda span: (span[0], -span[1]))

    selected: List[Tuple[int, int, str]] = []
    last_end = -1

    for start, end, tag in ordered:
        if start < last_end:
            continue
        selected.append((start, end, tag))
        last_end = end

    return selected


def mask_pii(text: str) -> Tuple[str, Dict[str, str]]:
    """
    텍스트에서 개인정보를 탐지해 대체 토큰으로 치환한다.

    동일한 원문 문자열은 항상 같은 토큰으로 치환되어, 외부 LLM이
    같은 대상을 문맥 전체에서 같은 토큰으로 일관되게 인식할 수 있다.

    Returns:
        masked_text: 비식별화된 텍스트 (외부 LLM 전송용)
        entity_map: {토큰: 원문} 매핑 (로컬 전용, 외부 전송 금지)
    """

    if not text or not text.strip():
        return text, {}

    spans: List[Tuple[int, int, str]] = []

    for tag, pattern in _REGEX_RULES:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end(), tag))

    spans.extend(_decode_ner_spans(text))

    selected_spans = _select_non_overlapping_spans(spans)

    # 1) 정방향으로 훑으며 등장 순서대로 토큰 번호를 매긴다.
    text_to_token: Dict[str, str] = {}
    token_counters: Dict[str, int] = {}
    entity_map: Dict[str, str] = {}

    resolved_spans: List[Tuple[int, int, str]] = []

    for start, end, tag in selected_spans:
        original = text[start:end]

        # tag는 모델의 원본 라벨(RRN/PHONE/EMAIL 또는 PS/OG/LC 등)이라
        # 모델을 바꾸면 문자열이 달라진다. "ORG로 매핑되는 태그인가"는
        # 원본 문자열이 아니라 _NER_LABEL_TO_TOKEN_PREFIX 매핑 결과로
        # 판단해야, NER 모델을 교체해도 학교/병원 세분화가 계속 동작한다
        # (Leo97로 교체하며 "OG" != "ORG"라 이 분기가 조용히 죽어있던
        # 것을 확인해 고쳤다).
        mapped = _NER_LABEL_TO_TOKEN_PREFIX.get(tag, tag)

        prefix = (
            _refine_org_prefix(original)
            if mapped == "ORG"
            else mapped
        )

        token = text_to_token.get(original)

        if token is None:
            token_counters[prefix] = token_counters.get(prefix, 0) + 1
            token = f"[{prefix}_{token_counters[prefix]:02d}]"
            text_to_token[original] = token
            entity_map[token] = original

        resolved_spans.append((start, end, token))

    # 2) 뒤에서부터 치환해 앞쪽 char offset이 밀리지 않게 한다.
    masked_text = text

    for start, end, token in sorted(resolved_spans, key=lambda s: -s[0]):
        masked_text = masked_text[:start] + token + masked_text[end:]

    return masked_text, entity_map


def restore_pii(value, entity_map: Dict[str, str]):
    """
    LLM 응답(str/dict/list 어떤 형태든)에 남아있는 비식별화 토큰을
    entity_map을 이용해 원문으로 되돌린다.

    외부 LLM에는 masked_text만 전달하지만, 상담사 화면에는 실제
    이름/기관명이 보여야 하므로 응답을 반환하기 직전에 항상 호출한다.
    """

    if isinstance(value, str):
        for token, original in entity_map.items():
            value = value.replace(token, original)
        return value

    if isinstance(value, dict):
        return {
            key: restore_pii(sub_value, entity_map)
            for key, sub_value in value.items()
        }

    if isinstance(value, list):
        return [restore_pii(item, entity_map) for item in value]

    return value


# ============================================================
# 데모
# ============================================================

if __name__ == "__main__":
    sample = (
        "상담사: 집에서 주로 누가 돌봐줘?\n"
        "아동: 엄마 김민수씨가 돌봐주는데, 요즘 은평초등학교 끝나면 "
        "이모 박영희 이모가 데리러 와요. 서울시 강남구 역삼동에 살아요.\n"
        "상담사: 아빠 연락처 알아?\n"
        "아동: 010-1234-5678번이요."
    )

    masked, entities = mask_pii(sample)

    print("--- 비식별화 결과 ---")
    print(masked)
    print()
    print("--- entity_map (로컬 전용) ---")
    for token, original in entities.items():
        print(f"{token} -> {original}")
