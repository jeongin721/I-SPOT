# 이름 인식(NER) 마스킹이 모델 한계(512토큰)보다 긴 글도 끝까지 가리는지 고정하는 테스트.
#
# ai/modeling/abuse/pii_masking._decode_ner_spans 는 예전에 앞 512토큰만 모델에 넣어서, 긴 상담 축어록 뒷부분의
# 이름 · 기관 · 지역이 가려지지 않은 채 OpenAI 로 나갔다. 이경진 님이 글을 겹치는 창(window)으로 나눠 전부 훑게
# 고쳤고(ai-modeling 367beaf), 두 창의 판정이 어긋나게 겹치면 합집합으로 합치게 했다(91bfbeb).
#
# CI 에는 torch · transformers · NER 모델이 없어서 둘 다 가짜로 바꾼다.
#   - 가짜 tokenizer: 공백이 아닌 글자 하나가 토큰 하나다. return_overflowing_tokens · stride 를 HF 빠른 tokenizer
#     처럼 흉내 낸다(창마다 [CLS] 내용 [SEP], 다음 창은 앞 창 끝에서 stride 만큼 겹쳐 시작, offset 은 원문 기준,
#     특수 토큰 offset 은 (0, 0)). 넘기지 않으면 예전처럼 앞 창 하나만 돌려준다.
#   - 가짜 모델: 시험마다 정한 글자만 개체명으로 판정한다. 창마다 다르게 판정하게 해서 경계 어긋남도 만든다.
# 실제 모델로 긴 글의 이름이 가려지는지는 최상위 tests/test_pii_masking_long_text.py(모델 있는 환경 전용)가 본다.
# 아래 글은 모두 가상 데이터다.

import contextlib
import importlib
import sys
import types
from typing import Any, Callable, Dict, List, Optional

import pytest

from app.adapters.module_loader import ensure_repo_root_on_path

PACKAGE = "ai.modeling.abuse"
PII_MASKING = "ai.modeling.abuse.pii_masking"

MAX_LENGTH = 512
STRIDE = 128
CONTENT = MAX_LENGTH - 2  # [CLS] · [SEP] 를 뺀 창 하나의 내용 토큰 수
SECOND_WINDOW_START = CONTENT - STRIDE  # 둘째 창이 시작하는 토큰 위치(382)

TOKEN_ID_BASE = 10
LABEL_IDS = {None: 0, "PS": 1, "LC": 2, "OG": 3}
ID2LABEL = {0: "O", 1: "PS-B", 2: "LC-B", 3: "OG-B"}

# (그 창의 첫 토큰 위치, 글자 위치) -> 태그 또는 None
Labeler = Callable[[int, int], Optional[str]]


class _Row(list):
    def tolist(self) -> list:
        return list(self)


class _State:
    def __init__(self) -> None:
        self.token_chars: List[int] = []
        self.labeler: Labeler = lambda window_start, char_index: None
        self.model_calls = 0


class _FakeTokenizer:
    def __init__(self, state: _State):
        self.state = state

    def __call__(self, text: str, **kwargs: Any) -> Dict[str, _Row]:
        token_chars = [index for index, char in enumerate(text) if not char.isspace()]
        self.state.token_chars = token_chars

        max_length = kwargs.get("max_length", MAX_LENGTH)
        content = max_length - 2
        windows = []
        start = 0

        while True:
            end = min(start + content, len(token_chars))
            windows.append((start, end))

            if end >= len(token_chars) or not kwargs.get("return_overflowing_tokens"):
                break

            start = end - kwargs.get("stride", 0)

        input_ids, attention_mask, offsets = _Row(), _Row(), _Row()

        for start, end in windows:
            positions = range(start, end)
            input_ids.append(_Row([1] + [TOKEN_ID_BASE + p for p in positions] + [2]))
            attention_mask.append(_Row([1] * (end - start + 2)))
            offsets.append(
                _Row([(0, 0)] + [(token_chars[p], token_chars[p] + 1) for p in positions] + [(0, 0)])
            )

        return {"input_ids": input_ids, "attention_mask": attention_mask, "offset_mapping": offsets}


class _FakeModel:
    def __init__(self, state: _State):
        self.state = state
        self.config = types.SimpleNamespace(id2label=ID2LABEL)

    def eval(self) -> None:
        return None

    def __call__(self, input_ids: list, attention_mask: Any = None, **kwargs: Any) -> Any:
        self.state.model_calls += 1
        row = input_ids[0]
        window_start = row[1] - TOKEN_ID_BASE
        labels = []

        for token_id in row:
            if token_id < TOKEN_ID_BASE:
                labels.append(0)
                continue

            char_index = self.state.token_chars[token_id - TOKEN_ID_BASE]
            labels.append(LABEL_IDS[self.state.labeler(window_start, char_index)])

        return types.SimpleNamespace(logits=_Row([_Row(labels)]))


@pytest.fixture
def ner(monkeypatch: pytest.MonkeyPatch):
    ensure_repo_root_on_path()
    state = _State()

    fake_torch = types.ModuleType("torch")
    fake_torch.tensor = lambda value: value
    fake_torch.no_grad = contextlib.nullcontext
    fake_torch.argmax = lambda logits, dim=-1: logits

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = types.SimpleNamespace(from_pretrained=lambda name: _FakeTokenizer(state))
    fake_transformers.AutoModelForTokenClassification = types.SimpleNamespace(
        from_pretrained=lambda name: _FakeModel(state)
    )

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    # 가짜 torch 로 import 한 모듈이 다른 시험에 남지 않게, sys.modules 와 부모 패키지 속성을
    # 비운 뒤 새로 import 하고 끝나면 원래대로 되돌린다.
    package = importlib.import_module(PACKAGE)
    saved_module = sys.modules.pop(PII_MASKING, None)
    saved_attr = package.__dict__.pop("pii_masking", None)

    module = importlib.import_module(PII_MASKING)

    yield module, state

    sys.modules.pop(PII_MASKING, None)
    package.__dict__.pop("pii_masking", None)

    if saved_module is not None:
        sys.modules[PII_MASKING] = saved_module

    if saved_attr is not None:
        package.pii_masking = saved_attr


def _labeler_for(text: str, entities: Dict[str, str]) -> Labeler:
    """어느 창에서든 entities 의 글자를 그 태그로 판정한다."""

    tags: Dict[int, str] = {}

    for word, tag in entities.items():
        start = text.index(word)

        for index in range(start, start + len(word)):
            tags[index] = tag

    return lambda window_start, char_index: tags.get(char_index)


def test_entity_after_first_window_is_masked(ner) -> None:
    module, state = ner
    text = "아" * 1200 + " 엄마는 이영희예요."
    state.labeler = _labeler_for(text, {"이영희": "PS"})

    masked, entity_map = module.mask_pii(text)

    assert "이영희" not in masked
    assert entity_map == {"[PERSON_01]": "이영희"}
    # 내용 토큰 1209개를 510개 창 · 128개 겹침으로 나누면 창 3개(0 · 382 · 764 에서 시작, 마지막은 1209 까지)다.
    assert state.model_calls == 3


def test_entity_cut_by_window_end_is_fully_masked(ner) -> None:
    # 첫 창은 토큰 509("박")에서 끝나고, 둘째 창(382 부터)에는 "박정훈" 이 다 들어 있다.
    module, state = ner
    text = "아" * (CONTENT - 1) + "박정훈" + "아" * 400
    name_start = text.index("박정훈")
    state.labeler = lambda window_start, char_index: (
        "PS" if name_start <= char_index < name_start + 3 else None
    )

    masked, entity_map = module.mask_pii(text)

    assert "박" not in masked and "정훈" not in masked
    assert entity_map == {"[PERSON_01]": "박정훈"}


def test_mismatched_window_predictions_are_merged(ner) -> None:
    # 두 창이 겹치는 구간에서 첫 창은 "대구광역시" 까지만, 둘째 창은 "광역시수성구" 를 지역으로 본다.
    # 먼저 시작한 쪽만 남기면 "수성구" 가 가려지지 않는다(창이 하나일 때는 생길 수 없던 경우).
    module, state = ner
    place = "대구광역시수성구"
    text = "아" * (SECOND_WINDOW_START + 50) + place + "아" * 600
    start = text.index(place)

    def labeler(window_start: int, char_index: int) -> Optional[str]:
        if window_start == 0 and start <= char_index < start + 5:
            return "LC"

        if window_start == SECOND_WINDOW_START and start + 2 <= char_index < start + len(place):
            return "LC"

        return None

    state.labeler = labeler

    masked, entity_map = module.mask_pii(text)

    assert "수성구" not in masked and "대구" not in masked
    assert entity_map == {"[LOCATION_01]": place}


def test_short_text_uses_one_window_as_before(ner) -> None:
    module, state = ner
    text = "엄마 김민수씨가 역삼동에 살아요."
    state.labeler = _labeler_for(text, {"김민수": "PS", "역삼동": "LC"})

    masked, entity_map = module.mask_pii(text)

    assert masked == "엄마 [PERSON_01]씨가 [LOCATION_01]에 살아요."
    assert entity_map == {"[PERSON_01]": "김민수", "[LOCATION_01]": "역삼동"}
    assert state.model_calls == 1
