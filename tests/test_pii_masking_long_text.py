# NER 기반 PII 마스킹(ai/modeling/abuse/pii_masking.py)이 512 토큰을
# 넘는 긴 상담 축어록에서도 끝부분까지 이름/기관명/지역명을 가리는지
# 테스트한다. 전엔 tokenizer가 512 토큰에서 한 번만 자르고 끝나서(그냥
# truncation=True), 그 뒤는 NER을 한 번도 안 거쳐 그대로 노출됐다
# (2026-10-20 Mingyu 지적). 겹치는 창(window)으로 나눠 전체를 훑도록
# 고친 뒤 이 동작을 고정한다.
#
# torch/transformers가 필요해 backend CI(최상위 tests/는 애초에
# backend CI 대상이 아님)와 무관하게, 이 모델링 코드가 실제로 돌아가는
# 환경에서만 의미 있는 테스트다.

from ai.modeling.abuse.privacy_gateway import PrivacyGatewayBlocked, mask_for_outbound
from ai.modeling.abuse.pii_masking import (
    _is_within_structural_prefix,
    _merge_overlapping_spans,
    _ner_tokenizer,
    mask_pii,
)


def _make_long_transcript() -> str:
    filler = (
        "상담사: 오늘 학교에서는 어땠어? 아동: 그냥 그랬어요 별일 없었어요.\n"
    ) * 60

    return (
        "상담사: 처음 뵙겠습니다. 성함이 어떻게 되시나요?\n"
        "아동: 김철수예요.\n"
        + filler
        + "상담사: 마지막으로 보호자 성함도 알려줄래?\n"
        "아동: 엄마는 이영희이고, 아빠는 박정훈이에요. "
        "저희는 대구광역시 수성구에 살아요.\n"
    )


def test_long_transcript_exceeds_512_tokens():
    # 이 테스트 자체가 512 토큰을 넘는 입력을 전제하므로, 먼저 그
    # 전제가 맞는지 확인한다(아니면 아래 테스트들이 의미가 없어진다).
    text = _make_long_transcript()
    token_count = len(_ner_tokenizer(text)["input_ids"])
    assert token_count > 512


def test_names_near_the_end_are_masked():
    text = _make_long_transcript()
    masked, entity_map = mask_pii(text)

    for original in ("김철수", "이영희", "박정훈", "대구광역시", "수성구"):
        assert original not in masked

    assert set(entity_map.values()) == {
        "김철수",
        "이영희",
        "박정훈",
        "대구광역시",
        "수성구",
    }


def test_short_text_still_works_unchanged():
    text = "엄마 김민수씨가 역삼동에 살아요."
    masked, entity_map = mask_pii(text)

    assert "김민수" not in masked
    assert "역삼동" not in masked
    assert entity_map == {
        "[PERSON_01]": "김민수",
        "[LOCATION_01]": "역삼동",
    }


# 서로 다른 창(window)이 같은 개체명의 경계를 다르게 보는 경우를
# 모델 없이 직접 재현한다(2026-10-20 Mingyu 지적 — 예: 앞 창은
# "대구광역시"까지만 보고, 뒤 창은 "광역시 수성구"로 봐서 겹치면, 전엔
# 둘 중 하나만 남기고 나머지를 버려 "수성구"가 안 가려졌다).


def test_overlapping_spans_from_different_windows_are_unioned():
    spans = [(0, 5, "LC"), (2, 9, "LC")]

    assert _merge_overlapping_spans(spans) == [(0, 9, "LC")]


def test_non_overlapping_spans_are_untouched():
    spans = [(0, 3, "PS"), (10, 15, "LC")]

    assert _merge_overlapping_spans(spans) == spans


def test_fully_contained_span_is_absorbed():
    spans = [(0, 10, "PS"), (2, 5, "PS")]

    assert _merge_overlapping_spans(spans) == [(0, 10, "PS")]


def test_adjacent_but_not_overlapping_spans_stay_separate():
    # start < cur_end(겹칠 때만 합침)이어야 한다 — start <= cur_end면
    # 맞닿기만 한(겹치지 않는) 서로 다른 개체까지 하나로 합쳐진다
    # (2026-10-21 Mingyu 지적, 실제 모델로 짧은 글 28개 중 4개에서
    # 이름+학교 이름이 한 덩어리로 합쳐짐을 확인).
    spans = [(0, 5, "PS"), (5, 12, "ORG")]

    assert _merge_overlapping_spans(spans) == spans


# "아동: ...", "상담사: ..." 화자표시(infer_audio_session.SPEAKER_LABEL_KO)가
# 매 줄 앞에 반복되는 긴 축어록에서, 모델이 가끔 "아동"이라는 단어
# 자체를 사람이름(PS)으로 오탐해 Privacy Gateway의 잔존 검사가 막는
# 문제를 재현한다(2026-10-20, T4에서 30분 분량 합성 축어록으로 실제
# 재현됨). 창이 하나뿐인 짧은 글에서는 거의 안 보이던 문제라, 여러
# 창으로 나뉠 만큼 긴 글로 재현한다.


def test_speaker_label_words_are_not_treated_as_pii():
    counselor_lines = [
        "오늘 기분은 어때?",
        "요즘 집에서는 어떻게 지내?",
        "학교에서 친구들하고는 잘 지내니?",
    ]
    child_lines = [
        "그냥 그랬어요.",
        "친구들하고는 잘 지내요.",
        "할머니 댁에서 지낼 때도 있어요.",
    ]

    lines = []
    for i in range(150):
        lines.append(f"상담사: {counselor_lines[i % len(counselor_lines)]}")
        lines.append(f"아동: {child_lines[i % len(child_lines)]}")
    text = "\n".join(lines)

    assert len(_ner_tokenizer(text)["input_ids"]) > 512

    masked, entity_map = mask_pii(text)

    assert "아동" not in entity_map.values()
    assert "상담사" not in entity_map.values()
    # 화자표시는 전부 그대로 남아 있어야 한다(지워지거나 토큰으로
    # 바뀌면 안 됨).
    assert masked.count("아동:") == 150
    assert masked.count("상담사:") == 150


# record_draft_llm.build_transcript_citation_text가 만드는
# "[seg_001] CHILD: ..." 형식(화자가 영문 코드)에서, 모델이 그 코드
# 조각(UNKNOWN의 "UN"·"UNK", CHILD의 "CH"·"ILD", "[seg_280]"의 "g" 등)
# 을 사람·기관으로 오탐해 Privacy Gateway가 분석 전체를 막던 문제를
# 재현한다(2026-10-21 Mingyu가 실제 모델·300발화로 재현·보고). 단어
# 단위 거르기("아동"/"상담사"만 정확히 일치)로는 이 조각 단위 오탐을
# 못 막아서, 줄 머리 "구조 표식" 범위 자체를 거르는 방식으로 바꿨다.


def test_citation_format_speaker_codes_are_not_treated_as_pii():
    counselor_lines = [
        "오늘 있었던 일을 천천히 이야기해 줄래?",
        "친구와 함께 시간을 보내면서 기억에 남은 일이 있니?",
    ]
    child_lines = [
        "책을 읽고 퍼즐을 맞추니까 마음이 편안했어요.",
        "함께 이야기를 나누고 서로 도와주었어요.",
    ]
    pattern = [
        ("COUNSELOR", counselor_lines),
        ("CHILD", child_lines),
        ("GUARDIAN", ["요즘 학교생활은 어떤가요?"]),
        ("OTHER", ["다 같이 즐거운 시간을 보냈어요."]),
        ("UNKNOWN", ["이번 주에 즐겁게 지낸 순간을 이야기해 줄래?"]),
    ]

    lines = []
    seg = 1
    while len(lines) < 300:
        for code, texts in pattern:
            lines.append(f"[seg_{seg:03d}] {code}: {texts[seg % len(texts)]}")
            seg += 1

    citation_text = "\n".join(lines[:300])

    assert len(_ner_tokenizer(citation_text)["input_ids"]) > 512

    # 전엔 여기서 PrivacyGatewayBlocked가 났다(구조 표식 조각이 사람·
    # 기관으로 오탐되고, 잔존 검사가 그 조각을 다시 잡았음).
    masked, entity_map = mask_for_outbound(citation_text)

    for code, _ in pattern:
        assert f"] {code}:" in masked


def test_structural_prefix_filter_does_not_swallow_longer_span():
    # 줄 머리의 "아동:"만 구조 표식 범위다. 본문 중간에 등장하는
    # "아동"(줄 머리가 아님)은 구조 표식이 아니므로 거르지 않는다 —
    # 단어 단위 거르기였다면 "아동"이라는 글자만 보고 걸렀겠지만,
    # 범위 단위 거르기는 span 전체가 구조 표식 범위 안에 있어야만
    # 거른다(2026-10-21 Mingyu 지적 — "김아동"처럼 그 단어를 포함하는
    # 실제 이름이 있을 때 이름 전체가 안 가려지는 위험을 막음).
    text = "아동: 네 이름이 뭐니?\n아동김말하는사람이 대답했다"
    zones = [(0, 3)]  # "아동:" 범위만 구조 표식으로 가정

    head_start = text.index("아동")
    body_start = text.index("아동", head_start + 1)

    assert _is_within_structural_prefix(
        (head_start, head_start + 2), zones
    ) is True  # 줄 머리 "아동"(구조 표식 안)
    assert _is_within_structural_prefix(
        (body_start, body_start + 2), zones
    ) is False  # 본문 속 "아동"(구조 표식 밖)
