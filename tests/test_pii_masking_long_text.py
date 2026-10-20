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

from ai.modeling.abuse.pii_masking import _ner_tokenizer, mask_pii


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
