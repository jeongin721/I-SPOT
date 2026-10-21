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
from ai.modeling.abuse.privacy_gateway import (
    PrivacyGatewayBlocked,
    _mask_residual_once,
    mask_for_outbound,
)


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
