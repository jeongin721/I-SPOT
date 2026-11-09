"""
STT 검수 '1차 임시 핵심 발화'의 임시 관련 조문 — 문장과 맞는 호(號) 고르기(2026-11-09, PROPOSAL_stt_law_match.md).

[왜]
11/03 부터 STT 검수 화면은 1차 유형 → 아동복지법 제17조 해당 호를 고정 표로 보였다. 유형이 맞아도 "네, 없어요" 같은 줄에
조문이 붙으면 상담원은 왜 붙었는지 알 수 없다. 여기서는 (1) 아동 발화가 그 호의 **행위 예시(앵커)와 닮았을 때만** 조문을
붙이고 (2) 닮은 예시를 근거로 같이 준다. 1차 모델(유형)과 독립된 둘째 신호가 일치할 때만 붙이므로 오탐이 준다.

[어떻게 — 서버 로컬, 외부 전송 없음(검수 전 원문은 서버 밖으로 나가지 않는다 — 팀장 결정 11/09)]
- 문장 임베딩: 로컬 모델(기본 jhgan/ko-sroberta-multitask, Hugging Face 캐시). transformers 만 쓴다(mean pooling).
- 앵커: 호마다 아이 말투의 행위 예시 문장(내장 ANCHORS) + KEY_SCAN_LAW_ANCHORS(JSON 파일, 선택 — 기관 매뉴얼 발췌처럼
  저장소에 올리지 않을 문구는 서버에만 둔다).
- 줄 ↔ 그 유형 앵커의 코사인 유사도 최대값이 KEY_SCAN_LAW_MIN_SIMILARITY(기본 0.45) 이상이면 그 유형의 조문 + 닮은 예시
  (excerpt) + 점수. 넘지 못하면 그 유형의 조문은 붙이지 않는다(발화는 '먼저 들어볼 곳'으로 남는다).
- 조문 본문 · 조문 링크: law_cache 의 아동복지법 제17조(캐시만 읽음 — 네트워크 없음)에서 호를 찾고, 캐시가 없으면 내장
  문구 · 법령 전체 링크.
- 모델을 못 올리면(파일 없음 · torch 없음) 예전처럼 유형의 조문을 근거 없이 붙인다(score null, excerpt 빈 값) — 스캔은
  실패하지 않는다. KEY_SCAN_LAW_MATCH=off 면 매칭을 끈다(시험 · 모델 없는 개발 환경).

값은 재서 고른다: experiments/key_scan_eval.py 가 줄마다 유사도를 적고 τ 별 조문 정밀도를 비교한다.
판정이 아니다 — 화면 문구는 '임시 · 참고 조문' 이고 법 위반을 확정하지 않는다(05_RULES).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LAW_NAME = "아동복지법"
ARTICLE = "제17조"
LAW_PORTAL_FALLBACK = "https://www.law.go.kr/법령/아동복지법"

TYPE_TO_ENGLISH = {"신체학대": "PHYSICAL", "정서학대": "EMOTIONAL", "성학대": "SEXUAL", "방임": "NEGLECT"}
ENGLISH_TO_TYPE = {english: korean for korean, english in TYPE_TO_ENGLISH.items()}

#: 유형 → 제17조 호 번호 · 본문. 본문은 화면 고정 표(counselor-web sttReview.ts KEY_SCAN_ARTICLES)와 같은 문구이고,
#: law_cache 가 있으면 캐시의 현행 문구 · 조문 링크로 바꾼다(_statute_from_cache).
STATUTE_ITEMS: dict[str, tuple[str, str]] = {
    "성학대": ("2", "아동에게 음란한 행위를 시키거나 이를 매개하는 행위 또는 아동을 대상으로 하는 성희롱 등의 성적 학대행위"),
    "신체학대": ("3", "아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위"),
    "정서학대": ("5", "아동의 정신건강 및 발달에 해를 끼치는 정서적 학대행위"),
    "방임": ("6", "자신의 보호 · 감독을 받는 아동을 유기하거나 의식주를 포함한 기본적 보호 · 양육 · 치료 및 교육을 소홀히 하는 방임행위"),
}

#: 호마다 아이 말투의 행위 예시(앵커). 법령 문장이 아니라 아이가 실제로 하는 말에 가깝게 쓴다 — 법률 어휘와 아이 말은
#: 어휘가 달라 호 본문과 직접 비교하면 유사도가 낮다. 기관 매뉴얼의 유형별 행위 예시는 KEY_SCAN_LAW_ANCHORS 로 더한다.
ANCHORS: dict[str, tuple[str, ...]] = {
    "신체학대": (
        "아빠가 때렸어요",
        "엄마한테 많이 맞았어요",
        "손으로 뺨을 때렸어요",
        "주먹으로 머리를 때렸어요",
        "발로 찼어요",
        "허리띠로 맞았어요",
        "회초리로 종아리를 맞았어요",
        "옷걸이로 때렸어요",
        "물건을 저한테 던졌어요",
        "밀쳐서 넘어졌어요",
        "꼬집어서 멍이 들었어요",
        "머리채를 잡아당겼어요",
        "목을 졸랐어요",
        "뜨거운 것에 데였어요",
        "맞아서 피가 났어요",
        "멍이 들고 많이 아팠어요",
    ),
    "정서학대": (
        "소리 지르고 욕을 해요",
        "쓸모없는 애라고 했어요",
        "너 때문에 망했다고 해요",
        "죽여 버린다고 했어요",
        "집에서 쫓아낸다고 했어요",
        "말을 안 걸고 없는 사람 취급해요",
        "동생만 예뻐하고 저는 미워해요",
        "방에 가둬 놓고 못 나오게 했어요",
        "엄마 아빠가 싸우면서 물건을 던지는 걸 봤어요",
        "아빠가 엄마를 때리는 걸 봤어요",
        "무서워서 숨어 있었어요",
        "바보라고 놀리고 창피를 줘요",
        "밤에 밖에 세워 뒀어요",
    ),
    "성학대": (
        "제 몸을 만졌어요",
        "속옷 안에 손을 넣었어요",
        "옷을 벗으라고 했어요",
        "이상한 동영상을 보여 줬어요",
        "자기 몸을 보여 줬어요",
        "같이 자자고 하면서 만졌어요",
        "사진을 찍어서 보내라고 했어요",
        "가슴이나 엉덩이를 만졌어요",
        "뽀뽀를 하라고 시켰어요",
        "만진 다음에 아무한테도 말하지 말라고 했어요",
    ),
    "방임": (
        "밥을 안 줘요",
        "며칠 굶은 적도 있어요",
        "밤에 집에 혼자 있어요",
        "엄마가 며칠씩 집에 안 들어와요",
        "아픈데 병원에 안 데려가요",
        "학교에 안 보내요",
        "옷을 안 빨아 줘서 더러워요",
        "씻지 못해요",
        "라면만 끓여 먹어요",
        "동생을 제가 돌봐요",
        "겨울인데 난방을 안 해요",
        "집에 아무도 없어서 문을 못 열어요",
    ),
}

DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"
DEFAULT_MIN_SIMILARITY = 0.45
MAX_TEXT_TOKENS = 128

ENV_MATCH = "KEY_SCAN_LAW_MATCH"
ENV_MODEL = "KEY_SCAN_LAW_EMBED_MODEL"
ENV_LOCAL_ONLY = "KEY_SCAN_LAW_EMBED_LOCAL_ONLY"
ENV_MIN_SIMILARITY = "KEY_SCAN_LAW_MIN_SIMILARITY"
ENV_ANCHORS = "KEY_SCAN_LAW_ANCHORS"

_ITEM_LINE_RE = re.compile(r"^(\d+(?:의\d+)?)\.\s*(.+)$")

EmbedFn = Callable[[Sequence[str]], Any]


@dataclass(frozen=True)
class LawMatchConfig:
    enabled: bool = True
    model_name: str = DEFAULT_MODEL
    local_only: bool = False
    min_similarity: float = DEFAULT_MIN_SIMILARITY
    anchors_path: str = ""


def _flag(raw: str | None, default: bool) -> bool:
    value = (raw or "").strip().lower()
    if not value:
        return default
    return value not in ("0", "off", "false", "no")


def law_match_config(environ: Mapping[str, str] | None = None) -> LawMatchConfig:
    """환경 변수에서 설정을 읽는다. 잘못된 값은 경고를 남기고 기본값."""

    environ = os.environ if environ is None else environ
    min_similarity = DEFAULT_MIN_SIMILARITY
    raw = (environ.get(ENV_MIN_SIMILARITY) or "").strip()
    if raw:
        try:
            value = float(raw)
            if 0.0 <= value <= 1.0:
                min_similarity = value
            else:
                logger.warning("%s 는 0~1 사이여야 해서 기본값을 씁니다.", ENV_MIN_SIMILARITY)
        except ValueError:
            logger.warning("%s 가 숫자가 아니라 기본값을 씁니다.", ENV_MIN_SIMILARITY)

    return LawMatchConfig(
        enabled=_flag(environ.get(ENV_MATCH), True),
        model_name=(environ.get(ENV_MODEL) or "").strip() or DEFAULT_MODEL,
        local_only=_flag(environ.get(ENV_LOCAL_ONLY), False),
        min_similarity=min_similarity,
        anchors_path=(environ.get(ENV_ANCHORS) or "").strip(),
    )


# ---------------------------------------------------------------------------
# 조문 본문 · 링크
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _statute_from_cache() -> dict[str, tuple[str, str]]:
    """law_cache 의 아동복지법 제17조 → {호 번호: (본문, 조문 링크)}. 캐시가 없거나 못 읽으면 빈 dict(네트워크는 부르지 않는다)."""

    try:
        from law import LawApiClient, extract_articles
        from law.portal import attach_portal_urls

        cached = LawApiClient().get_law_by_name(LAW_NAME, cache_only=True)
        articles = attach_portal_urls(
            extract_articles(cached.get("body", {}), fallback_law_name=LAW_NAME),
            cached.get("search_item", {}),
        )
    except Exception as error:  # noqa: BLE001 — 캐시가 없으면 내장 문구를 쓴다
        logger.info("아동복지법 법령 캐시를 쓰지 못해 내장 조문 문구를 씁니다. type=%s", type(error).__name__)
        return {}

    items: dict[str, tuple[str, str]] = {}
    for article in articles:
        if str(article.get("article", "")).strip() != ARTICLE:
            continue
        portal_url = str(article.get("portal_url") or "")
        for line in str(article.get("content", "")).splitlines():
            match = _ITEM_LINE_RE.match(line.strip())
            if match:
                items[match.group(1)] = (match.group(2).strip(), portal_url)
    return items


def statute_reference(korean_type: str) -> dict[str, Any] | None:
    """유형의 제17조 호 — 캐시 문구 · 조문 링크가 있으면 그것, 없으면 내장 문구 · 법령 전체 링크."""

    item = STATUTE_ITEMS.get(korean_type)
    if item is None:
        return None
    item_no, builtin_text = item
    cached_text, portal_url = _statute_from_cache().get(item_no, ("", ""))
    return {
        "abuse_type": TYPE_TO_ENGLISH[korean_type],
        "law_name": LAW_NAME,
        "article": ARTICLE,
        "item_label": f"제{item_no}호",
        "text": cached_text or builtin_text,
        "portal_url": portal_url or LAW_PORTAL_FALLBACK,
    }


def default_reference(korean_type: str) -> dict[str, Any] | None:
    """매칭 없이 유형만으로 붙이는 조문(11/06 이전과 같은 뜻). 근거 발췌 없음 · 점수 없음."""

    reference = statute_reference(korean_type)
    if reference is None:
        return None
    return {**reference, "excerpt": "", "score": None}


# ---------------------------------------------------------------------------
# 앵커
# ---------------------------------------------------------------------------


def load_anchors(path: str = "") -> dict[str, list[str]]:
    """내장 앵커 + (있으면) JSON 파일의 앵커. 파일 모양은 {"신체학대": ["…"], …} 이고 영문 유형 이름도 받는다."""

    anchors = {korean: list(phrases) for korean, phrases in ANCHORS.items()}
    if not path:
        return anchors
    try:
        extra = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("%s 파일을 읽지 못해 내장 앵커만 씁니다. type=%s", ENV_ANCHORS, type(error).__name__)
        return anchors
    if not isinstance(extra, dict):
        logger.warning("%s 파일은 {유형: [문장]} 모양이어야 합니다. 내장 앵커만 씁니다.", ENV_ANCHORS)
        return anchors
    for key, phrases in extra.items():
        korean = ENGLISH_TO_TYPE.get(str(key), str(key))
        if korean not in anchors or not isinstance(phrases, list):
            continue
        for phrase in phrases:
            if isinstance(phrase, str) and phrase.strip() and phrase.strip() not in anchors[korean]:
                anchors[korean].append(phrase.strip())
    return anchors


# ---------------------------------------------------------------------------
# 로컬 임베딩
# ---------------------------------------------------------------------------


class LocalEmbedder:
    """transformers 로 문장 임베딩(mean pooling · 정규화). torch · 모델은 처음 쓸 때 올린다."""

    def __init__(self, model_name: str, local_only: bool) -> None:
        self.model_name = model_name
        self.local_only = local_only
        self._tokenizer = None
        self._model = None
        self._device = None

    def load(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=self.local_only)
        self._model = AutoModel.from_pretrained(self.model_name, local_files_only=self.local_only)
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model.to(self._device)
        self._model.eval()

    def __call__(self, texts: Sequence[str]):
        import torch

        if self._model is None:
            self.load()
        vectors = []
        for start in range(0, len(texts), 32):
            batch = list(texts[start : start + 32])
            encoded = self._tokenizer(batch, padding=True, truncation=True, max_length=MAX_TEXT_TOKENS, return_tensors="pt")
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            with torch.no_grad():
                hidden = self._model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors.append(pooled.cpu())
        return torch.cat(vectors, dim=0).numpy()


# ---------------------------------------------------------------------------
# 매칭
# ---------------------------------------------------------------------------


class LawMatcher:
    """줄 ↔ 유형별 앵커 유사도로 조문을 고른다. embed_fn 을 주면(시험) 모델 대신 쓴다."""

    def __init__(self, config: LawMatchConfig | None = None, embed_fn: EmbedFn | None = None) -> None:
        self.config = config or law_match_config()
        self.anchors = load_anchors(self.config.anchors_path)
        self._embed = embed_fn
        self._anchor_vectors: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._failed = False
        self._ready = False

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def ready(self) -> bool:
        """모델 · 앵커 임베딩을 올린다(한 번). 못 올리면 False — 이후 default_reference 로 간다."""

        if not self.config.enabled or self._failed:
            return False
        if self._ready:
            return True
        with self._lock:
            if self._ready or self._failed:
                return self._ready
            try:
                if self._embed is None:
                    self._embed = LocalEmbedder(self.config.model_name, self.config.local_only)
                for korean, phrases in self.anchors.items():
                    self._anchor_vectors[korean] = self._embed(phrases)
                self._ready = True
            except Exception as error:  # noqa: BLE001 — 모델이 없어도 스캔은 계속된다
                self._failed = True
                logger.warning(
                    "임시 조문 매칭 모델을 올리지 못해 유형 조문을 근거 없이 붙입니다(%s=%s). type=%s",
                    ENV_MODEL,
                    self.config.model_name,
                    type(error).__name__,
                )
        return self._ready

    def similarities(self, text: str) -> dict[str, dict[str, Any]] | None:
        """유형마다 가장 닮은 앵커와 점수. 모델이 없으면 None."""

        if not text.strip() or not self.ready():
            return None
        import numpy as np

        vector = np.asarray(self._embed([text]))[0]
        result: dict[str, dict[str, Any]] = {}
        for korean, matrix in self._anchor_vectors.items():
            scores = np.asarray(matrix) @ vector
            index = int(scores.argmax())
            result[korean] = {"score": round(float(scores[index]), 3), "excerpt": self.anchors[korean][index]}
        return result

    def references_for(self, text: str, types: Sequence[str]) -> list[dict[str, Any]]:
        """발화 글과 1차 유형(한글) → 붙일 조문 목록. 매칭이 안 되면(모델 없음 · 꺼짐) 유형 조문을 근거 없이."""

        korean_types = [ENGLISH_TO_TYPE.get(label, label) for label in types]
        korean_types = [label for label in korean_types if label in STATUTE_ITEMS]
        if not korean_types or not text.strip():
            return []

        similarity = self.similarities(text)
        if similarity is None:
            return [reference for reference in (default_reference(label) for label in korean_types) if reference]

        references: list[dict[str, Any]] = []
        for label in korean_types:
            best = similarity.get(label)
            if best is None or best["score"] < self.config.min_similarity:
                continue
            reference = statute_reference(label)
            if reference is None:
                continue
            references.append({**reference, "excerpt": best["excerpt"], "score": best["score"]})
        return references


_matcher: LawMatcher | None = None
_matcher_lock = threading.Lock()


def get_matcher() -> LawMatcher:
    global _matcher
    with _matcher_lock:
        if _matcher is None:
            _matcher = LawMatcher()
        return _matcher


def reset_matcher() -> None:
    """시험용 — 설정 · 환경 변수를 바꾼 뒤 다시 만들게 한다."""

    global _matcher
    with _matcher_lock:
        _matcher = None
    # 시험이 _statute_from_cache 를 보통 함수로 바꿔 둔 경우도 있다.
    getattr(_statute_from_cache, "cache_clear", lambda: None)()


def references_for(text: str, types: Sequence[str]) -> list[dict[str, Any]]:
    return get_matcher().references_for(text, types)


def similarities(text: str) -> dict[str, dict[str, Any]] | None:
    return get_matcher().similarities(text)


def is_available() -> bool:
    return get_matcher().ready()


def start_preload() -> threading.Thread | None:
    """서버 시작 때 모델 · 앵커 임베딩을 미리 올린다(첫 STT 가 모델 로드 시간 때문에 30초를 넘기지 않게). 꺼져 있으면 None."""

    matcher = get_matcher()
    if not matcher.enabled:
        return None
    thread = threading.Thread(target=matcher.ready, name="key-scan-law-match-preload", daemon=True)
    thread.start()
    return thread
