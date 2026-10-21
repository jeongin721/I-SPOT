"""
개인정보 탐지 및 비식별화 레이어.

상담 텍스트를 외부 LLM(second_stage_llm.py, checklist_llm.py)에 보내기 전에
이름·기관명(학교/병원)·지역명·주민등록번호·전화번호 등 개인 식별 정보를
정규식 + 개체명 인식(NER)으로 탐지해 대체 토큰([PERSON_01] 등)으로 치환한다.

entity_map(토큰 -> 원문)은 외부로 전송하지 않고 호출 측(로컬)에서만
보관한다 — 외부 LLM에는 masked_text만 전달한다.
"""

import logging
import re
from typing import Dict, List, Tuple

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification

# "Token indices sequence length is longer than..." 경고를 끈다 — 긴
# 입력을 겹치는 창으로 나눠 처리하도록 설계했으니(_decode_ner_spans
# 참고) 이 경고에 쓰인 "indexing errors가 날 것" 문구는 우리 상황에는
# 해당하지 않는다. 실제 처리에는 영향 없음(2026-10-20, 512 토큰 초과
# 입력 처리 추가 때 확인).
logging.getLogger("transformers.tokenization_utils_base").setLevel(
    logging.ERROR
)


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

# 줄 머리의 "구조 표식"(화자 코드)은 PII가 아니다 — infer_audio_session
# .build_full_transcript_text가 매 줄 앞에 붙이는 "아동: "/"상담사: "와,
# record_draft_llm.build_transcript_citation_text가 붙이는
# "[seg_001] CHILD: " 둘 다. 모델이 가끔 이 안의 조각을 사람·기관으로
# 잘못 본다 — "아동"/"상담사" 전체뿐 아니라 "UNKNOWN"의 "UN"·"UNK",
# "CHILD"의 "CH"·"ILD", "[seg_280]"의 "g"처럼 글자 일부만 잡히기도
# 한다(2026-10-20 T4 30분 분량, 2026-10-21 Mingyu가 인용 글 300발화로
# 재현·보고).
#
# 처음엔 "아동"·"상담사" 정확히 일치하는 경우만 걸러냈는데 두 가지
# 한계가 있었다: (1) "UN"처럼 단어가 아닌 조각 오탐은 못 거른다. (2)
# 본문에 그 단어를 포함하는 진짜 이름이 있을 때(예: "김아동") 모델이
# "아동"만 잡으면, 그 걸러내기 때문에 "김아동" 전체가 하나도 안
# 가려진 채 남는다(2026-10-21 Mingyu 지적, 가짜 모델로 재현 — 실제
# 모델에선 아직 안 나타남). 그래서 단어 내용이 아니라 "줄 머리 구조
# 표식의 글자 범위" 자체를 찾아서, 그 범위 안에 완전히 들어가는
# 판정만 거른다 — 범위를 한 글자라도 벗어나면(예: 화자 코드 바로
# 뒤에 실제 이름이 공백 없이 붙어 하나의 범위로 잡히면) 거르지 않고
# 그대로 마스킹한다.
#
# 대괄호 안은 "\[seg_\d+\]"로 좁힌다 — segment_id는 어디서나 "seg_숫자"
# 꼴이다(backend/app/adapters/stt_adapter.py:77,
# ai/adapters/aihub_transcript.py:59). 처음엔 "\[[^\]\n]*\]"로 대괄호
# 안 아무 글자나 받았는데, 그러면 상담사가 고친 줄에 "[메모: 보호자
# 박영희] GUARDIAN: ..."처럼 대괄호 안에 실제 이름이 들어가도 그
# 대괄호 전체가 "구조 표식"으로 오인돼 마스킹·잔존 검사·정확 매칭이
# 전부 건너뛰어 이름이 그대로 나갔다(2026-10-21 Mingyu 지적 — 0ad9eb8
# 에서 생겨 main에 들어가 있었음, 운영 잠금 중이라 실제로 나간 적은
# 없음).
_STRUCTURAL_PREFIX_RE = re.compile(
    r"^(?:\[seg_\d+\][ \t]+(?:COUNSELOR|CHILD|GUARDIAN|OTHER|UNKNOWN)|상담사|아동):",
    re.MULTILINE,
)


def _refine_org_prefix(entity_text: str) -> str:
    """ORG 태그 중 학교/병원 이름은 더 구체적인 토큰으로 구분한다."""

    if any(keyword in entity_text for keyword in _SCHOOL_KEYWORDS):
        return "SCHOOL"

    if any(keyword in entity_text for keyword in _HOSPITAL_KEYWORDS):
        return "HOSPITAL"

    return "ORG"


# 모델의 최대 입력(512 토큰)을 넘는 긴 상담 축어록을 그냥 자르면
# (truncation=True 한 번) 뒷부분 전체가 NER을 한 번도 안 거쳐 이름 등이
# 그대로 노출된다(2026-10-20 Mingyu 지적 — "비식별이 완전하지 않다,
# 긴 상담 뒷부분은 안 가려진다"). stride만큼 겹치는 창(window)으로 나눠
# 전체를 다 돈다 — 겹치는 구간을 두는 이유는, 창 경계에 걸쳐 잘리는
# 개체명이 있어도 그 옆 겹치는 창에서는 온전한 형태로 들어가 잡히게
# 하기 위함이다(사람 이름·기관명은 보통 몇 토큰 안이라 128 겹침이면
# 충분하다).
_NER_MAX_LENGTH = 512
_NER_STRIDE = 128


def _merge_adjacent_same_tag_spans(
    offsets: List[Tuple[int, int]],
    pred_ids: List[int],
) -> List[Tuple[int, int, str]]:
    """
    한 창(window) 안에서 토큰별 예측을 (시작, 끝, 태그) span으로 병합한다.
    subword(##) 경계는 offset_mapping으로 보정한다.
    """

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


def _merge_overlapping_spans(
    spans: List[Tuple[int, int, str]],
) -> List[Tuple[int, int, str]]:
    """
    서로 다른 창(window)이 같은 개체명의 경계를 다르게 보면(예: 앞 창은
    "대구광역시"까지만, 뒤 창은 "광역시 수성구"로) 겹치는 범위를
    합집합으로 합친다. 창이 하나일 때는 생길 수 없던 경우다(2026-10-20
    Mingyu 지적 — 호출부의 _select_non_overlapping_spans는 겹치면
    먼저 시작하는 것만 남기고 나머지를 통째로 버려서, 두 범위 중 한쪽
    범위에만 있던 부분(위 예의 "수성구")이 전혀 마스킹되지 않았다).

    start < cur_end(겹칠 때만 합침)이지 start <= cur_end(맞닿기만
    해도 합침)가 아니다 — 실제 모델로 짧은 글을 돌려보니(2026-10-21
    Mingyu 지적) 안 겹치고 그냥 붙어만 있는 서로 다른 개체(이름 바로
    뒤에 공백 없이 붙은 학교 이름 등)까지 하나로 합쳐지는 문제가
    있었다. 둘 다 이미 가려지므로 새로 노출되는 건 없지만, 화면에
    "김민수서울초등학교"처럼 한 덩어리로 보이는 건 맞지 않다.
    """

    if not spans:
        return []

    ordered = sorted(spans, key=lambda span: span[0])

    merged: List[Tuple[int, int, str]] = []
    cur_start, cur_end, cur_tag = ordered[0]

    for start, end, tag in ordered[1:]:
        if start < cur_end:
            if (end - start) > (cur_end - cur_start):
                cur_tag = tag
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end, cur_tag))
            cur_start, cur_end, cur_tag = start, end, tag

    merged.append((cur_start, cur_end, cur_tag))

    return merged


def _is_within_structural_prefix(
    span: Tuple[int, int],
    zones: List[Tuple[int, int]],
) -> bool:
    start, end = span
    return any(
        zone_start <= start and end <= zone_end
        for zone_start, zone_end in zones
    )


def _decode_ner_spans(text: str) -> List[Tuple[int, int, str]]:
    """
    NER 모델 출력을 (시작, 끝, 태그) 형태의 원문 char span으로 복원한다.
    512 토큰을 넘는 입력은 겹치는 여러 창으로 나눠 전체를 훑는다(모듈
    상수 _NER_MAX_LENGTH/_NER_STRIDE 참고). return_overflowing_tokens이
    돌려주는 offset_mapping은 각 창이 원문 전체에서 어디였는지를 이미
    반영하고 있어 따로 보정할 필요가 없다. 창끼리 겹치는 구간에서 경계가
    어긋나게 검출되면 _merge_overlapping_spans가 합집합으로 합친다.

    줄 머리 구조 표식("아동: ", "[seg_001] CHILD: " 등) 안에 완전히
    들어가는 판정은 PII가 아니므로 거른다(_STRUCTURAL_PREFIX_RE 선언부
    참고).
    """

    structural_zones = [
        (match.start(), match.end())
        for match in _STRUCTURAL_PREFIX_RE.finditer(text)
    ]

    encoded = _ner_tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=_NER_MAX_LENGTH,
        stride=_NER_STRIDE,
        return_overflowing_tokens=True,
        padding=False,
    )

    spans: List[Tuple[int, int, str]] = []

    for chunk_index in range(len(encoded["input_ids"])):
        chunk_input_ids = torch.tensor([encoded["input_ids"][chunk_index]])
        chunk_attention_mask = torch.tensor(
            [encoded["attention_mask"][chunk_index]]
        )
        offsets = encoded["offset_mapping"][chunk_index]

        with torch.no_grad():
            logits = _ner_model(
                input_ids=chunk_input_ids,
                attention_mask=chunk_attention_mask,
            ).logits

        pred_ids = torch.argmax(logits, dim=-1)[0].tolist()
        chunk_spans = _merge_adjacent_same_tag_spans(offsets, pred_ids)
        spans.extend(
            span
            for span in chunk_spans
            if not _is_within_structural_prefix(
                (span[0], span[1]), structural_zones
            )
        )

    return _merge_overlapping_spans(spans)


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
