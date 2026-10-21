# 내보내기 전 검사(Privacy Gateway)가 남은 개체를 다시 가릴 때 줄 머리 표식 · 가린 토큰 · 상담 고정 표현을 깨지 않는지 고정하는 테스트.
#
# ai/modeling/abuse/privacy_gateway.review 는 가린 글을 같은 탐지기로 다시 검사해 무엇이 남으면 막는다. 긴 글은 첫 가리기에서 놓친
# 이름이 다시 검사할 때 잡히는 일이 흔해 대부분 막혔다. 이경진 님이 잡힌 자리를 한 번 더 가리고 다시 검사하게 했다(ai-modeling
# c1745a7). 그 판은 이미 찾은 값을 글 전체에서 정확 매칭으로 바꿔서, 한 번 잘못 잡힌 "아동" · "UN" · "CH" 가 줄 머리 화자 표시와
# 다른 낱말, 이미 가린 토큰 안까지 바꿨다. 다시 검사가 가린 자리(●)까지 한 범위로 잡으면 토큰이 깨졌다. 9e6fa7d 가 줄 머리 표식
# 범위 안의 일치를 건너뛰고 "아동" · "상담사" · "보호자" 를 정확 매칭에서 빼며, ● 에 걸친 범위는 ● 앞에서 자른다.
#
# 아직 안 고쳐진 두 가지는 xfail 로 둔다(고쳐지면 strict 라 실패로 알려 준다): 정확 매칭이 가린 토큰 안의 일치를 건너뛰지 않는 것,
# 줄 머리 표식 정규식(pii_masking._STRUCTURAL_PREFIX_RE)이 대괄호 안 아무 글자나 받아 그 안의 이름이 모든 탐지에서 빠지는 것
# (0ad9eb8 부터, 실제 모델로 재현 — 이 PR 전 main 에도 있다).
#
# CI 에는 torch · transformers · NER 모델이 없어서 tests/test_modeling_ner_windows.py 의 가짜 tokenizer · 모델을 쓴다. 판정은 글
# 내용으로 정한다: 가린 자리(●, privacy_gateway._blank_out_mask_tokens)가 없는 글은 첫 가리기, 있는 글은 다시 검사다.
# 아래 글은 모두 가상 데이터다.

import contextlib
import importlib
import re
import sys
import types
from typing import Callable, Dict, Optional

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path
from tests.test_modeling_ner_windows import _FakeModel, _FakeTokenizer, _State

PACKAGE = "ai.modeling.abuse"
# 가짜 torch · openai 로 새로 import 할 모듈. privacy_gateway 는 pii_masking 의 함수를 이름으로 가져가므로 같이 새로 import 한다.
MODULES = ("pii_masking", "second_stage_llm", "privacy_gateway")

MASKED = "●"
VALID_TOKEN = re.compile(r"\[[A-Z]+_\d{2}\]")

# 글 -> {글자 위치: 태그}
Rule = Callable[[str], Dict[int, str]]


class _RuleState(_State):
    def __init__(self) -> None:
        super().__init__()
        self.rule: Rule = lambda text: {}


class _RuleTokenizer(_FakeTokenizer):
    """부를 때마다 그 글에 rule 을 적용해 가짜 모델의 판정을 정한다."""

    def __call__(self, text: str, **kwargs):
        tags = self.state.rule(text)
        self.state.labeler = lambda window_start, char_index: tags.get(char_index)
        return super().__call__(text, **kwargs)


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch):
    ensure_repo_root_on_path()
    state = _RuleState()

    fake_torch = types.ModuleType("torch")
    fake_torch.tensor = lambda value: value
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.argmax = lambda logits, dim=-1: logits

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda name: _RuleTokenizer(state))
    fake_transformers.AutoModelForTokenClassification = types.SimpleNamespace(
        from_pretrained=lambda name: _FakeModel(state)
    )

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    if importlib.util.find_spec("openai") is None:
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = object
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

    # 가짜로 import 한 모듈이 다른 시험에 남지 않게, sys.modules 와 부모 패키지 속성을 비운 뒤 새로 import 하고
    # 끝나면 원래대로 되돌린다.
    package = importlib.import_module(PACKAGE)
    saved = {name: (sys.modules.pop(f"{PACKAGE}.{name}", None), package.__dict__.pop(name, None)) for name in MODULES}

    pii = importlib.import_module(f"{PACKAGE}.pii_masking")
    gw = importlib.import_module(f"{PACKAGE}.privacy_gateway")

    yield gw, pii, state

    for name, (saved_module, saved_attr) in saved.items():
        sys.modules.pop(f"{PACKAGE}.{name}", None)
        package.__dict__.pop(name, None)

        if saved_module is not None:
            sys.modules[f"{PACKAGE}.{name}"] = saved_module

        if saved_attr is not None:
            setattr(package, name, saved_attr)


def _tags(text: str, word: str, tag: str, nth: Optional[int] = None) -> Dict[int, str]:
    """text 안의 word 를 tag 로 판정한다. nth 를 주면 그 번째(0부터) 하나만, 안 주면 전부."""

    starts = [match.start() for match in re.finditer(re.escape(word), text)]

    if nth is not None:
        starts = starts[nth : nth + 1]

    return {index: tag for start in starts for index in range(start, start + len(word))}


def _review(gw, text: str):
    result = gw.review({"text": text})
    return result.payload["text"], result.entity_map


def _assert_tokens_intact(pii, masked: str, entity_map: Dict[str, str], original: str) -> None:
    # entity_map 에 있는 토큰을 빼면 대괄호는 원문에 있던 만큼만 남아야 하고, 가려진 원문에 토큰 조각 · 가린 자리가 섞이면 안 된다.
    rest = VALID_TOKEN.sub(lambda m: "" if m.group() in entity_map else m.group(), masked)

    assert (rest.count("["), rest.count("]")) == (original.count("["), original.count("]")), rest
    assert all(not set(value) & set("[]" + MASKED) for value in entity_map.values()), entity_map
    assert pii.restore_pii(masked, entity_map) == original


def test_name_seen_only_on_recheck_is_masked_and_passes(gateway) -> None:
    # 첫 가리기는 "이영희" 를 놓치고 다시 검사에서야 본다. c1745a7 전에는 여기서 막혀 긴 회기 분석이 실패했다.
    gw, pii, state = gateway
    text = "아동: 어제 김민수랑 이영희랑 놀았어요.\n상담사: 그랬구나."
    state.rule = lambda t: _tags(t, "이영희", "PS") if MASKED in t else _tags(t, "김민수", "PS")

    masked, entity_map = _review(gw, text)

    assert masked == "아동: 어제 [PERSON_01]랑 [PERSON_02]랑 놀았어요.\n상담사: 그랬구나."
    assert entity_map == {"[PERSON_01]": "김민수", "[PERSON_02]": "이영희"}


def test_label_word_misread_once_does_not_spread(gateway) -> None:
    # 첫 가리기에서 본문의 "아동" 한 곳을 사람으로 잘못 보고, 다시 검사에서 이름을 새로 본다. 다시 가릴 때 "아동" 을 글 전체에서
    # 정확 매칭으로 바꾸면 화자 표시 "아동:" 과 "아동학대" · "아동보호전문기관" 까지 토큰이 된다.
    gw, pii, state = gateway
    text = (
        "아동: 아동학대 신고는 어떻게 해요?\n"
        "상담사: 아동보호전문기관에 알려요.\n"
        "아동: 친구 아동이랑 김민수랑 놀았어요."
    )
    state.rule = lambda t: _tags(t, "김민수", "PS") if MASKED in t else _tags(t, "아동", "PS", nth=4)

    masked, entity_map = _review(gw, text)

    assert "김민수" not in masked
    assert len(pii._STRUCTURAL_PREFIX_RE.findall(masked)) == 3
    assert "아동학대" in masked and "아동보호전문기관" in masked
    _assert_tokens_intact(pii, masked, entity_map, text)


def test_speaker_code_fragment_misread_once_keeps_line_heads(gateway) -> None:
    # 인용 글 본문의 "UN" 한 곳을 기관으로 잘못 본 뒤(실제 모델 long-06), 다시 가릴 때 정확 매칭이 "UNKNOWN:" · "COUNSELOR:" 안의
    # "UN" 까지 바꾸면 줄 머리 화자 코드가 깨진다(실제 모델에서 299줄 중 119줄).
    gw, pii, state = gateway
    speakers = ["COUNSELOR", "CHILD", "UNKNOWN"]
    lines = [f"[seg_{i:03d}] {speakers[i % 3]}: 오늘은좋았어요." for i in range(1, 10)]
    text = "\n".join(lines) + "\n[seg_010] CHILD: UN 캠프에서 김민수를 만났어요."
    heads = len(pii._STRUCTURAL_PREFIX_RE.findall(text))

    def rule(t: str) -> Dict[int, str]:
        if MASKED in t:
            return _tags(t, "김민수", "PS")

        start = t.index("UN 캠프")
        return {start: "OG", start + 1: "OG"}

    state.rule = rule

    masked, entity_map = _review(gw, text)

    assert "김민수" not in masked
    assert len(pii._STRUCTURAL_PREFIX_RE.findall(masked)) == heads
    _assert_tokens_intact(pii, masked, entity_map, text)


@pytest.mark.xfail(strict=True, reason="정확 매칭이 이미 가린 토큰 안의 일치를 아직 건너뛰지 않는다(9e6fa7d 기준)")
def test_recheck_does_not_rewrite_inside_masked_tokens(gateway) -> None:
    # 본문의 "CH" 를 기관으로 잘못 가린 뒤 다시 가릴 때, 정확 매칭이 이미 가린 "[SCHOOL_01]" 안의 "CH" 까지 바꾸면
    # "[S[ORG_01]OOL_01]" 처럼 토큰이 깨진다.
    gw, pii, state = gateway
    text = "아동: CH 선생님은 서울초등학교에 계세요. 친구 김민수도요."

    def rule(t: str) -> Dict[int, str]:
        if MASKED in t:
            return _tags(t, "김민수", "PS")

        return {**_tags(t, "CH", "OG"), **_tags(t, "서울초등학교", "OG")}

    state.rule = rule

    masked, entity_map = _review(gw, text)

    assert "김민수" not in masked
    _assert_tokens_intact(pii, masked, entity_map, text)


def test_recheck_span_reaching_into_masked_token_is_cut(gateway) -> None:
    # 첫 가리기가 "박정훈" 의 "훈" 만 가려 "박정[PERSON_01]" 이 됐다. 다시 검사가 "박정" 과 뒤의 가린 자리(●)까지 한 범위로 보면,
    # 그 범위를 그대로 바꿀 때 "[PERSON_02]ERSON_01]" 처럼 토큰이 깨지고 entity_map 에 "박정[P" 가 들어간다.
    gw, pii, state = gateway
    text = "아동: 제 친구는 박정훈이에요."

    def rule(t: str) -> Dict[int, str]:
        if MASKED not in t:
            return {t.index("박정훈") + 2: "PS"}

        start = t.find("박정" + MASKED)
        return {} if start < 0 else {index: "PS" for index in range(start, start + 4)}

    state.rule = rule

    masked, entity_map = _review(gw, text)

    assert "박정" not in masked
    _assert_tokens_intact(pii, masked, entity_map, text)


@pytest.mark.parametrize(
    "text",
    [
        # 상담사가 고친 구간 글에 줄바꿈과 대괄호 메모가 들어가 인용 글 줄 머리 꼴이 된 경우
        "[seg_001] CHILD: 오늘은 좋았어요.\n[seg_002] GUARDIAN: 집에 가자.\n[메모: 보호자 박영희] GUARDIAN: 네.",
        # 전체 글(아동: · 상담사: 줄) 속에 같은 꼴의 줄이 들어간 경우
        "아동: 오늘은 좋았어요.\n상담사: 그랬구나.\n[보호자 박영희] GUARDIAN: 네.",
    ],
)
@pytest.mark.xfail(strict=True, reason="줄 머리 표식 정규식이 대괄호 안 아무 글자나 받는다(0ad9eb8 부터)")
def test_name_inside_line_head_brackets_is_not_exempt(gateway, text: str) -> None:
    # 줄 머리 표식 정규식이 대괄호 안 아무 글자나 받으면, 그 안의 이름은 첫 가리기 · 다시 검사 · 정확 매칭이 모두 건너뛰어
    # 그대로 나간다(0ad9eb8 부터, 실제 모델로 재현). segment_id 는 늘 "seg_숫자" 라 대괄호 안은 그 꼴만 표식으로 본다.
    gw, pii, state = gateway
    state.rule = lambda t: _tags(t, "박영희", "PS")

    try:
        masked, entity_map = _review(gw, text)
    except gw.PrivacyGatewayBlocked:
        return

    assert "박영희" not in masked
    _assert_tokens_intact(pii, masked, entity_map, text)
