# Privacy Gateway(ai/modeling/abuse/privacy_gateway.py)가 잔존 검사에
# 걸렸을 때 바로 막지 않고 몇 번 더 가려보고 그래도 남으면 막는지
# 테스트한다(2026-10-21 Mingyu 지적 — 1차 마스킹(mask_pii)이 실명을
# 놓쳤다가 잔존 검사에서만 잡히는 경우가 실제 모델로 흔했고, 그때마다
# 바로 막으면 실제 상담처럼 이름이 거의 늘 있는 긴 회기는 분석 대부분이
# 실패한다).
#
# torch/transformers가 필요해 backend CI(최상위 tests/는 애초에 backend
# CI 대상이 아님)와 무관하게, 이 모델링 코드가 실제로 돌아가는 환경에서만
# 의미 있는 테스트다.

import pytest

import ai.modeling.abuse.privacy_gateway as privacy_gateway
from ai.modeling.abuse.pii_masking import (
    _is_within_structural_prefix,
    _structural_prefix_zones,
)
from ai.modeling.abuse.privacy_gateway import (
    PrivacyGatewayBlocked,
    _mask_residual_once,
    mask_for_outbound,
)


def test_exact_sweep_skips_partial_overlap_with_mask_token(monkeypatch):
    # 2026-10-21 Mingyu 지적(가짜 판정으로만 재현): 지금까지는 토큰
    # 범위 안에 완전히 들어간 일치만 건너뛰었다. 원문에 대괄호가 섞인
    # 값("민수[")이 토큰과 한쪽만 겹치면, 완전 포함이 아니라서
    # 걸러지지 않고 그대로 바꿔치기돼 토큰 괄호 구조가 깨질 수 있다.
    # 조금이라도 겹치면 건너뛰어야 한다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"수[PERSON": "[ORG_01]"}
    global_counters = {"ORG": 1}

    text = "민수[PERSON_02]가 다녀갔다."

    new_text, changed = _mask_residual_once(
        text, [], global_original_to_token, global_counters
    )

    # "수[PERSON"이 기존 토큰 "[PERSON_02]"와 겹치므로 건너뛰어야
    # 하고, 그 토큰은 깨지지 않은 채 그대로 남아야 한다.
    assert "[PERSON_02]" in new_text
    assert changed is False


def test_exact_sweep_skips_already_masked_token_zone(monkeypatch):
    # 2026-10-21 Mingyu 지적(가짜 판정으로 재현): "CH"가 본문에서 한
    # 번 기관으로 잘못 잡혀 global_original_to_token에 들어가면,
    # 정확 매칭이 이미 가린 토큰("[SCHOOL_01]") 안의 "CH"까지 바꿔서
    # "[S[ORG_01]OOL_01]"처럼 토큰 자체가 깨진다. 이미 가린 토큰
    # 범위 안의 일치는 건너뛰어야 한다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"CH": "[ORG_01]", "서울대학교병원": "[SCHOOL_01]"}
    global_counters = {"ORG": 1, "SCHOOL": 1}

    text = "[SCHOOL_01]에 다녀왔다. CH 수업도 들었다."

    new_text, changed = _mask_residual_once(
        text, [], global_original_to_token, global_counters
    )

    assert changed is True
    # 기존 토큰은 안 깨지고 그대로 남아야 한다.
    assert "[SCHOOL_01]" in new_text
    # 구조 표식·기존 토큰 밖의 "CH"는 가려져야 한다.
    assert "[ORG_01] 수업도" in new_text


def test_exact_sweep_skips_structural_prefix_zone(monkeypatch):
    # 2026-10-21 Mingyu 지적: "UN"이 (줄 머리가 아닌 자리에서) 기관으로
    # 한 번 잘못 잡혀 global_original_to_token에 들어가면, 정확 매칭이
    # 글 전체의 "UN"을 다 바꿔서 정상적인 "UNKNOWN:" 화자표시까지
    # 깨진다. 1단계(NER)는 비워서 2단계(정확 매칭)만 본다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"UN": "[ORG_01]"}
    global_counters = {"ORG": 1}

    text = "[seg_001] UNKNOWN: 안녕하세요.\nUN이 여기선 그냥 낱말이다."

    new_text, changed = _mask_residual_once(
        text, [], global_original_to_token, global_counters
    )

    assert changed is True
    # 줄 머리 구조 표식 "UNKNOWN:"은 그대로 남아야 한다.
    assert "] UNKNOWN:" in new_text
    # 구조 표식이 아닌 자리의 "UN"은 가려져야 한다.
    assert "[ORG_01]이 여기선" in new_text


def test_exact_sweep_blocklist_protects_compound_words(monkeypatch):
    # 2026-10-21 Mingyu 지적: "아동"이 한 번 사람으로 잘못 잡히면,
    # 정확 매칭이 "아동:" 화자표시와 "아동학대"·"아동보호전문기관"
    # 같은 합성어 속 "아동"까지 전부 바꿔버린다. _SWEEP_TARGET_BLOCKLIST
    # 에 있는 낱말은 정확 매칭 대상에서 아예 빠져야 한다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"아동": "[PERSON_99]"}
    global_counters = {"PERSON": 99}

    text = "아동: 저는 괜찮아요.\n아동학대 예방 교육을 받았다. 아동보호전문기관에 연락했다."

    new_text, changed = _mask_residual_once(
        text, [], global_original_to_token, global_counters
    )

    assert changed is False
    assert new_text == text
    assert "아동:" in new_text
    assert "아동학대" in new_text
    assert "아동보호전문기관" in new_text


def test_ner_span_overlapping_mask_token_is_truncated_at_bullet(monkeypatch):
    # 2026-10-21 Mingyu 지적(가짜 판정으로 재현): NER이 실제 글자
    # ("박정")에서 시작해 이미 가린 토큰 자리(scan_text의 ●)까지
    # 걸치는 범위를 잡으면, 그 범위를 그대로 잘라 쓸 때 토큰 괄호
    # 일부("[P")가 섞여 들어가 기존 토큰("[PERSON_01]")이 깨진다.
    # ● 앞까지만 남기고 잘라야 한다.
    text = "박정[PERSON_01]이 다녀갔다."
    # "박정[P"처럼 실제 글자 2개 + 가린 자리 일부까지 걸치는 범위를
    # 모델이 돌려준 것처럼 흉내낸다(아래 scan_text 기준 offset).
    bullet_start = text.index("[PERSON_01]")

    def fake_decode(scan_text):
        # scan_text는 "박정"+"●"*11(토큰과 같은 길이)+"이 다녀갔다."
        assert scan_text[bullet_start] == "●"
        return [(0, bullet_start + 2, "PS")]  # "박정" + ● 2개까지 걸침

    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", fake_decode)

    # PERSON_01은 이미 다른 원문("훈" 등, 이 테스트에서는 중요하지
    # 않음)에 쓰인 토큰이라고 가정한다 — 안 그러면 "박정"에 새로
    # 매기는 번호가 우연히 PERSON_01과 겹쳐 이 테스트 자체가
    # 모호해진다.
    global_original_to_token = {"훈": "[PERSON_01]"}
    global_counters = {"PERSON": 1}

    new_text, changed = _mask_residual_once(
        text, [], global_original_to_token, global_counters
    )

    # 기존 토큰 "[PERSON_01]"이 깨지지 않고 그대로 남아야 한다.
    assert "[PERSON_01]" in new_text
    # "박정"은 새 토큰(PERSON_02)으로 가려지고, 괄호가 섞인 값이
    # entity_map에 들어가면 안 된다.
    assert global_original_to_token.get("박정") == "[PERSON_02]"
    for original in global_original_to_token:
        assert "[" not in original and "]" not in original


def test_ner_runs_before_exact_sweep_so_fresh_full_name_wins(monkeypatch):
    # 짧은 조각("김철")이 이미 알려진 상태에서, 같은 라운드에 NER이
    # 더 긴 이름("김철수")을 통째로 잡으면 그 결과가 먼저 적용돼야
    # 한다 — 정확 매칭을 먼저 하면 "김철"이 "김철수" 앞부분을 잘라
    # 먹어 "수"만 남는 사고가 났다(2026-10-21 테스트로 발견). NER을
    # 먼저 돌리는 순서로 고친 뒤에는, 이 라운드에 NER이 "김철수"를
    # 잡아주는 한 정확 매칭이 끼어들기 전에 통째로 가려진다.
    monkeypatch.setattr(
        privacy_gateway,
        "_decode_ner_spans",
        lambda text: [(text.index("김철수"), text.index("김철수") + 3, "PS")],
    )

    global_original_to_token = {"김철": "[PERSON_01]"}
    global_counters = {"PERSON": 1}

    new_text, changed = _mask_residual_once(
        "김철만 먼저 가려졌고, 김철수는 아직 안 가려졌다.",
        [],
        global_original_to_token,
        global_counters,
    )

    assert changed is True
    assert "김철수" not in new_text
    assert global_original_to_token["김철수"] != global_original_to_token["김철"]


def test_known_limitation_short_fragment_can_still_split_longer_name(monkeypatch):
    # 알려진 한계를 그대로 기록해 둔다: 그 라운드에 NER이 더 긴 이름을
    # 못 잡으면(여기서는 아예 비워서 흉내), 짧은 조각("김철")을 향한
    # 정확 매칭이 그보다 긴 이름("김철수")의 앞부분을 잘라 먹어
    # "[토큰]수"가 된다. 정보가 새는 건 아니지만(여전히 가려짐) 이름이
    # 깔끔하게 하나로 안 잡힌다 — 짧은 조각 자체를 안 남기는 게
    # 근본 해결이라 지금은 이 상태를 그대로 고정해 둔다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"김철": "[PERSON_01]"}
    global_counters = {"PERSON": 1}

    new_text, changed = _mask_residual_once(
        "김철수는 아직 안 가려졌다.",
        [],
        global_original_to_token,
        global_counters,
    )

    assert changed is True
    assert new_text == "[PERSON_01]수는 아직 안 가려졌다."


def test_exact_match_sweep_skips_single_character_fragments(monkeypatch):
    # 한 글자짜리 조각을 그대로 정확 매칭하면 무관한 단어 속 같은
    # 글자까지 먹어버린다(2026-10-21 디버그 중 발견 — NER이 창 경계
    # 에서 이름을 "희"처럼 한 글자로 잘못 잡아 global_original_to_token
    # 에 들어간 적이 있으면, 그 뒤로 "희망" 같은 무관한 단어까지
    # 정확매칭에 걸리면 안 된다). 이 테스트는 정확 매칭 단계만 보려고
    # NER 쪽(2단계)은 비워둔다 — 그래야 모델이 "희망"을 독자적으로
    # 사람이름으로 오탐하는지와 섞이지 않는다.
    monkeypatch.setattr(privacy_gateway, "_decode_ner_spans", lambda text: [])

    global_original_to_token = {"희": "[PERSON_01]"}
    global_counters = {"PERSON": 1}

    new_text, changed = _mask_residual_once(
        "아이는 희망을 잃지 않았다.", [], global_original_to_token, global_counters
    )

    assert changed is False
    assert "[PERSON_01]" not in new_text
    assert "희망" in new_text


def test_mask_residual_once_continues_token_numbering():
    # 토큰 번호가 앞 단계(PERSON_01)와 안 겹치고 이어져야 한다
    # (2026-10-21 Mingyu 요청).
    global_original_to_token = {"기존이름": "[PERSON_01]"}
    global_counters = {"PERSON": 1}

    new_text, changed = _mask_residual_once(
        "그 뒤 김철수가 등장했다.",
        [],
        global_original_to_token,
        global_counters,
    )

    assert changed is True
    assert "김철수" not in new_text
    assert global_counters["PERSON"] == 2
    assert global_original_to_token["김철수"] == "[PERSON_02]"


def test_mask_residual_once_returns_unchanged_when_nothing_found():
    new_text, changed = _mask_residual_once(
        "가릴 게 없는 문장입니다.", [], {}, {}
    )

    assert changed is False
    assert new_text == "가릴 게 없는 문장입니다."


def test_first_pass_miss_is_rescued_by_residual_retry(monkeypatch):
    # mask_pii가 아무것도 못 찾은 상황(1차 마스킹이 실명을 놓친 경우)을
    # 흉내낸다 — 실제 NER 잔존 검사가 잡아서 반복 가리기로 구제돼야
    # 한다(막히면 안 됨).
    monkeypatch.setattr(privacy_gateway, "mask_pii", lambda text: (text, {}))

    masked, entity_map = mask_for_outbound("김철수가 저를 때려요.")

    assert "김철수" not in masked
    assert "김철수" in entity_map.values()


def test_long_transcript_with_repeated_names_is_not_blocked():
    # 2026-10-21 Mingyu가 실제 모델로 재현한 시나리오: 긴 축어록
    # (200줄)에 같은 이름이 20번쯤 반복되면, 창 경계 위치에 따라
    # 일부는 전체로 일부는 조각으로 잡혀서 단순 NER 재검사 2~3번
    # 으로는 다 안 지워졌다(디버그로 확인 — 수정 전에는 PrivacyGateway
    # Blocked로 끝까지 막힘). 정확 매칭 선행 스윕을 추가한 뒤 통과하는
    # 것을 고정한다.
    counselor_lines = [
        "오늘 있었던 일을 천천히 이야기해 줄래?",
        "친구와 함께 시간을 보내면서 기억에 남은 일이 있니?",
        "요즘 몸은 좀 어때?",
    ]
    child_lines = [
        "김철수 선생님이 도와주셨어요.",
        "서울대학교병원에 몇 번 갔었어요.",
        "수원시에 있는 할머니댁에 자주 가요.",
        "박영희 이모가 저를 자주 챙겨줘요.",
        "친구들이랑 잘 지내요.",
    ]

    lines = []
    i = 0
    while len(lines) < 200:
        lines.append(f"상담사: {counselor_lines[i % len(counselor_lines)]}")
        lines.append(f"아동: {child_lines[i % len(child_lines)]}")
        i += 1

    text = "\n".join(lines)

    masked, entity_map = mask_for_outbound(text)

    for original in ("김철수", "수원시", "박영희"):
        assert original not in masked


def test_blank_out_mask_tokens_preserves_line_head_id_before_speaker_code():
    # 2026-10-22 Mingyu PR #72 재검증 지적(실제 모델로 재현): 줄 머리
    # ID가 우리가 만드는 마스킹 토큰과 우연히 같은 모양이면(예: STT가
    # "[SEG_001]"처럼 대문자+숫자로 줌), 전에는 이것도 그대로 ●로
    # 지워져서 그 줄의 화자 코드 보호 범위를 _structural_prefix_zones가
    # 전혀 못 찾았다(대괄호 글자 자체가 없어지므로). 이 자리는 지우지
    # 않고 그대로 둬야 한다 — 다른 자리의 진짜 마스킹 토큰은 여전히
    # 지워야 한다.
    text = "[SEG_001] CHILD: 안녕하세요. [PERSON_01]씨가 왔어요."

    scan_text = privacy_gateway._blank_out_mask_tokens(text)

    assert scan_text.startswith("[SEG_001] CHILD:")
    assert "[PERSON_01]" not in scan_text
    assert "●" in scan_text


def test_structural_zone_survives_blanking_when_line_head_id_looks_like_mask_token():
    # 위 수정의 실제 효과: _blank_out_mask_tokens가 내놓은 scan_text를
    # 다시 _structural_prefix_zones에 넣어도 화자 코드가 여전히 구조
    # 표식 범위 안에 있어야 한다 — 그래야 잔존 재시도의 NER 재검출이
    # 그 코드 조각을 PII로 오탐해도 걸러진다.
    text = "[SEG_001] UNKNOWN: 안녕하세요. [PERSON_01]씨가 왔어요."

    scan_text = privacy_gateway._blank_out_mask_tokens(text)
    zones = _structural_prefix_zones(scan_text)

    code_start = scan_text.index("UNKNOWN:")
    assert _is_within_structural_prefix(
        (code_start, code_start + len("UNKNOWN:")), zones
    )


def test_unresolvable_residual_is_blocked_after_max_rounds(monkeypatch):
    # 아무리 가려도 절대 안 사라지는 상황을 흉내낸다 — 무한반복이 아니라
    # 정해진 횟수(1 + _MAX_RESIDUAL_MASK_ROUNDS)만큼만 시도하고 결국
    # 차단돼야 한다.
    call_count = {"n": 0}

    def always_residual(text, known_identifiers):
        call_count["n"] += 1
        return ["NER 개체 잔존(PS)"]

    def fake_mask_once(text, known_identifiers, global_map, global_counters):
        return text, True  # 뭔가 바뀐 척(실제로는 안 바뀜)

    monkeypatch.setattr(privacy_gateway, "_residual_reasons", always_residual)
    monkeypatch.setattr(privacy_gateway, "_mask_residual_once", fake_mask_once)

    with pytest.raises(PrivacyGatewayBlocked):
        mask_for_outbound("테스트 문장")

    assert call_count["n"] == 1 + privacy_gateway._MAX_RESIDUAL_MASK_ROUNDS
