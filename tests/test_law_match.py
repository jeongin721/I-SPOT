# ai/modeling/abuse/law_match.py — 1차 임시 핵심 발화의 임시 조문을 문장과 닮은 호에만 붙이기. 모델 없이 규칙만 본다(가짜 임베딩).
# 데이터는 모두 지어낸 것이다.

import json

import numpy as np
import pytest

from ai.modeling.abuse import law_match as lm


def _unit(*values):
    vector = np.asarray(values, dtype=float)
    return vector / np.linalg.norm(vector)


# 가짜 임베딩: 낱말이 들어 있으면 그 유형 축으로. 앵커 문장과 줄이 같은 축이면 유사도 1, 아니면 0 에 가깝다.
_AXES = (("때", "맞", "멍"), ("욕", "소리", "쫓아"), ("만졌", "속옷"), ("밥", "혼자", "병원"))


def fake_embed(texts):
    rows = []
    for text in texts:
        weights = [1.0 if any(word in text for word in words) else 0.0 for words in _AXES]
        # 어느 축의 낱말도 없으면 영벡터 — 무엇과도 닮지 않음(코사인 0).
        rows.append(_unit(*weights) if any(weights) else np.zeros(len(_AXES)))
    return np.vstack(rows)


@pytest.fixture
def matcher():
    lm.reset_matcher()
    return lm.LawMatcher(lm.LawMatchConfig(min_similarity=0.5), embed_fn=fake_embed)


@pytest.fixture(autouse=True)
def _no_law_cache(monkeypatch):
    # 캐시가 있는 환경에서도 내장 문구로 시험한다.
    lm._statute_from_cache.cache_clear()
    monkeypatch.setattr(lm, "_statute_from_cache", dict)


# ---------------------------------------------------------------------------
# 조문 · 앵커
# ---------------------------------------------------------------------------


def test_every_type_has_a_statute_item_and_anchors():
    for korean, english in lm.TYPE_TO_ENGLISH.items():
        reference = lm.statute_reference(korean)
        assert reference["abuse_type"] == english and reference["law_name"] == "아동복지법" and reference["article"] == "제17조"
        assert reference["item_label"].startswith("제") and reference["text"] and reference["portal_url"].startswith("https://www.law.go.kr/")
        assert len(lm.ANCHORS[korean]) >= 8


def test_statute_items_match_the_screen_table():
    assert lm.statute_reference("신체학대")["item_label"] == "제3호"
    assert lm.statute_reference("정서학대")["item_label"] == "제5호"
    assert lm.statute_reference("성학대")["item_label"] == "제2호"
    assert lm.statute_reference("방임")["item_label"] == "제6호"
    assert lm.statute_reference("기타") is None


def test_cache_text_and_article_url_override_builtin(monkeypatch):
    monkeypatch.setattr(lm, "_statute_from_cache", lambda: {"3": ("캐시의 현행 문구", "https://www.law.go.kr/lsInfoP.do?x=17")})

    assert lm.statute_reference("신체학대")["text"] == "캐시의 현행 문구"
    assert lm.statute_reference("신체학대")["portal_url"] == "https://www.law.go.kr/lsInfoP.do?x=17"
    assert lm.statute_reference("방임")["portal_url"] == lm.LAW_PORTAL_FALLBACK  # 캐시에 없는 호는 내장


def test_extra_anchors_from_json_file(tmp_path):
    path = tmp_path / "anchors.json"
    path.write_text(json.dumps({"PHYSICAL": ["매뉴얼 예시 문장", "아빠가 때렸어요"], "모르는유형": ["x"], "방임": "문자열"}), encoding="utf-8")

    anchors = lm.load_anchors(str(path))

    assert "매뉴얼 예시 문장" in anchors["신체학대"]
    assert anchors["신체학대"].count("아빠가 때렸어요") == 1  # 중복은 한 번
    assert anchors["방임"] == list(lm.ANCHORS["방임"])

    assert lm.load_anchors(str(tmp_path / "없음.json")) == {k: list(v) for k, v in lm.ANCHORS.items()}


# ---------------------------------------------------------------------------
# 매칭
# ---------------------------------------------------------------------------


def test_reference_is_attached_only_when_the_line_resembles_that_types_examples(matcher):
    physical = matcher.references_for("허리띠로 맞았어요", ["신체학대"])
    assert [r["item_label"] for r in physical] == ["제3호"]
    assert physical[0]["excerpt"] in lm.ANCHORS["신체학대"] and physical[0]["score"] >= 0.5
    assert physical[0]["abuse_type"] == "PHYSICAL"

    # 1차가 신체로 봤지만 "네, 없어요" 는 어느 예시와도 안 닮았다 → 조문 없음(줄은 핵심 발화로 남는다).
    assert matcher.references_for("네, 없어요.", ["신체학대"]) == []

    # 유형이 둘이면 닮은 쪽만.
    both = matcher.references_for("밥을 안 줘요", ["신체학대", "방임"])
    assert [r["abuse_type"] for r in both] == ["NEGLECT"]


def test_english_types_are_accepted_and_unknown_types_skipped(matcher):
    assert [r["item_label"] for r in matcher.references_for("밥을 안 줘요", ["NEGLECT", "기타"])] == ["제6호"]
    assert matcher.references_for("밥을 안 줘요", ["기타"]) == []
    assert matcher.references_for("", ["방임"]) == []


def test_similarities_report_best_anchor_per_type(matcher):
    similarity = matcher.similarities("아빠가 소리 지르고 욕해요")

    assert set(similarity) == set(lm.TYPE_TO_ENGLISH)
    assert similarity["정서학대"]["score"] == pytest.approx(1.0, abs=1e-6)
    assert similarity["정서학대"]["excerpt"] == "소리 지르고 욕을 해요"
    assert similarity["성학대"]["score"] == pytest.approx(0.0, abs=1e-6)


def test_threshold_from_config_gates_the_reference():
    strict = lm.LawMatcher(lm.LawMatchConfig(min_similarity=0.99), embed_fn=fake_embed)
    loose = lm.LawMatcher(lm.LawMatchConfig(min_similarity=0.0), embed_fn=fake_embed)

    assert strict.references_for("맞아서 멍이 들었어요", ["신체학대"])  # 같은 축 → 1.0
    assert strict.references_for("네", ["신체학대"]) == []
    assert [r["item_label"] for r in loose.references_for("네", ["신체학대"])] == ["제3호"]  # τ=0 이면 늘 붙는다


# ---------------------------------------------------------------------------
# 모델이 없거나 꺼졌을 때 — 예전처럼 유형 조문을 근거 없이
# ---------------------------------------------------------------------------


def test_disabled_matcher_returns_default_references_without_excerpt():
    off = lm.LawMatcher(lm.LawMatchConfig(enabled=False), embed_fn=fake_embed)

    references = off.references_for("네, 없어요.", ["신체학대", "정서학대"])

    assert [r["item_label"] for r in references] == ["제3호", "제5호"]
    assert all(r["excerpt"] == "" and r["score"] is None for r in references)
    assert off.similarities("아빠가 때렸어요") is None


def test_model_load_failure_falls_back_and_does_not_retry_forever():
    calls = []

    def failing(texts):
        calls.append(len(texts))
        raise RuntimeError("no model files")

    broken = lm.LawMatcher(lm.LawMatchConfig(), embed_fn=failing)

    assert [r["item_label"] for r in broken.references_for("아빠가 때렸어요", ["신체학대"])] == ["제3호"]
    assert broken.references_for("밥을 안 줘요", ["방임"])[0]["score"] is None
    assert len(calls) == 1  # 한 번 실패하면 다시 올리려 하지 않는다
    assert broken.ready() is False


# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------


def test_config_reads_environment_with_safe_defaults():
    assert lm.law_match_config({}) == lm.LawMatchConfig()
    assert lm.law_match_config({"KEY_SCAN_LAW_MATCH": "off"}).enabled is False
    assert lm.law_match_config({"KEY_SCAN_LAW_MATCH": "0"}).enabled is False
    config = lm.law_match_config(
        {
            "KEY_SCAN_LAW_EMBED_MODEL": "org/model",
            "KEY_SCAN_LAW_EMBED_LOCAL_ONLY": "true",
            "KEY_SCAN_LAW_MIN_SIMILARITY": "0.6",
            "KEY_SCAN_LAW_ANCHORS": "/srv/anchors.json",
        }
    )
    assert config == lm.LawMatchConfig(True, "org/model", True, 0.6, "/srv/anchors.json")
    assert lm.law_match_config({"KEY_SCAN_LAW_MIN_SIMILARITY": "high"}).min_similarity == lm.DEFAULT_MIN_SIMILARITY
    assert lm.law_match_config({"KEY_SCAN_LAW_MIN_SIMILARITY": "2"}).min_similarity == lm.DEFAULT_MIN_SIMILARITY


def test_start_preload_does_nothing_when_disabled(monkeypatch):
    monkeypatch.setenv("KEY_SCAN_LAW_MATCH", "off")
    lm.reset_matcher()

    assert lm.start_preload() is None
    assert lm.is_available() is False
    lm.reset_matcher()
