"""
STT 검수 '1차 임시 핵심 발화'(quick_risk_scan) 줄 고르기(2026-10-30, 정밀도 개선 2026-11-06).

[왜]
1차 RoBERTa 는 여러 문답을 묶은 덩어리(chunk) 단위로 판정한다. 예전 스캔은 덩어리 하나가 걸리면 그 안의 발화를
전부 표시해서 "네" · "몰라요" 같은 줄까지 핵심 발화로 잡혔다(경진 10/30 데모 확인). 10/30 부터 줄마다 다시 판정하지만,
덩어리에서 걸린 유형이 어느 줄에서도 다시 안 걸리면 **덩어리 안 아동 발화 전체**에 붙이는 되돌림 규칙이 남아 있었다.
11/03 화면이 그 유형으로 '임시' 관련 조문을 보이기 시작하면서, 이 규칙이 "네, 없어요" 같은 줄에 조문을 붙이는 가장 큰
원인이 됐다(11/06 데모 화면). 모델은 회기 단위 라벨로 학습돼 줄 하나의 판정은 흔들리는데, 정식 분석과 달리 이 스캔은
1차 결과를 거르는 2차 LLM 없이 그대로 화면에 가므로 더 엄격해야 한다.

[어떻게]
덩어리 안의 아동 발화를 줄마다(바로 앞 상담사 질문과 묶어) 다시 모델에 넣고 **확률**을 받는다
(infer_abuse_v3_adapter.predict_major_types_detail — 외부 Contract 에는 여전히 유형만 나간다).
- 줄의 확률이 줄 임계값 이상이면 그 줄에 그 유형을 붙인다(어느 유형이든 — 덩어리 판정이 놓친 유형도 살린다. 10/30 실제
  모델 확인: 한 덩어리에서 '방임' 만 걸렸지만 줄 단위로는 '때려요' · '허리띠로 맞았어요' 가 신체학대로 걸렸다).
  줄 임계값은 기본으로 모델 checkpoint 의 유형별 임계값(정식 분석과 같음)이고 KEY_SCAN_LINE_THRESHOLD 로 더 높인다.
  부정 응답 필터(filtered_reason)가 내린 유형은 확률이 높아도 붙이지 않는다.
- 덩어리에서는 걸렸는데 어느 줄도 임계값을 넘지 않은 유형(KEY_SCAN_CHUNK_FALLBACK):
  top1(기본) — 그 유형 확률이 가장 높은 줄 하나에만, 그 확률이 KEY_SCAN_FALLBACK_MIN_PROBABILITY 이상일 때.
  none — 붙이지 않는다. all — 예전처럼 덩어리 아동 발화 전체(10/30 규칙).
- 줄 판정 수 상한(KEY_SCAN_MAX_LINE_PREDICTIONS, 기본 400): 걸린 덩어리부터 먼저 쓴다. 상한에 못 든 덩어리는 줄 확률이
  없으므로 all 이면 예전 방식(걸린 덩어리의 아동 발화 전체), top1 · none 이면 붙이지 않고 경고 로그만 남긴다.
  10/30 의 80 은 줄마다 512 토큰으로 채워 한 번씩 부르던 때의 값이다. 지금은 여러 줄을 한 번에 넣고 묶음 안에서 가장 긴
  줄까지만 채우므로(동적 패딩) 줄 판정이 덩어리 판정보다 싸다. 서버에서 시간을 재고 조정한다(experiments/key_scan_eval.py).

값은 재서 고른다: experiments/key_scan_eval.py 가 같은 점수로 규칙 · 임계값 조합의 정밀도 · 재현율을 비교한다.

이 모듈은 고르기 규칙만 둔다(모델 · torch 를 부르지 않는다 — backend/tests/test_key_scan_refine.py 에서 시험한다).
모델 호출은 infer_audio_session.quick_risk_scan.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

CHILD_LABEL = "아동"
COUNSELOR_LABEL = "상담사"

#: 덩어리에서 걸렸는데 어느 줄도 임계값을 넘지 않은 유형을 어디에 붙일지.
CHUNK_FALLBACKS = ("top1", "none", "all")

DEFAULT_CHUNK_FALLBACK = "top1"
DEFAULT_FALLBACK_MIN_PROBABILITY = 0.2
#: 줄 판정 수 상한(스캔 제한 시간 KEY_SCAN_TIMEOUT_SECONDS 기본 30초 안에 끝나게). 묶음 판정 기준 — 모듈 docstring 참고.
DEFAULT_MAX_LINE_PREDICTIONS = 400

ENV_LINE_THRESHOLD = "KEY_SCAN_LINE_THRESHOLD"
ENV_CHUNK_FALLBACK = "KEY_SCAN_CHUNK_FALLBACK"
ENV_FALLBACK_MIN_PROBABILITY = "KEY_SCAN_FALLBACK_MIN_PROBABILITY"
ENV_MAX_LINE_PREDICTIONS = "KEY_SCAN_MAX_LINE_PREDICTIONS"

Chunk = Sequence[tuple[str, str, dict[str, Any]]]
#: 유형별 판정 — {유형: {"detected": bool, "probability": float, "threshold": float, "filtered_reason"?: str}}.
Prediction = dict[str, Any]
LinePrediction = tuple[str, Prediction]


@dataclass(frozen=True)
class ScanConfig:
    """고르기 규칙 설정. None 인 line_threshold 는 '판정에 든 threshold(모델 checkpoint 값)를 그대로' 다."""

    line_threshold: float | None = None
    chunk_fallback: str = DEFAULT_CHUNK_FALLBACK
    fallback_min_probability: float = DEFAULT_FALLBACK_MIN_PROBABILITY
    max_line_predictions: int = DEFAULT_MAX_LINE_PREDICTIONS

    def __post_init__(self) -> None:
        if self.chunk_fallback not in CHUNK_FALLBACKS:
            raise ValueError(f"chunk_fallback 은 {CHUNK_FALLBACKS} 중 하나다: {self.chunk_fallback!r}")


def _env_float(environ: Mapping[str, str], name: str, default: float | None, low: float, high: float) -> float | None:
    raw = (environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("%s 가 숫자가 아니라 기본값을 씁니다.", name)
        return default
    if not low <= value <= high:
        logger.warning("%s 는 %s~%s 사이여야 해서 기본값을 씁니다.", name, low, high)
        return default
    return value


def scan_config(environ: Mapping[str, str] | None = None) -> ScanConfig:
    """환경 변수에서 설정을 읽는다. 빈 값 · 잘못된 값은 경고를 남기고 기본값(설정 때문에 스캔이 통째로 실패하지 않게)."""

    environ = os.environ if environ is None else environ

    fallback = (environ.get(ENV_CHUNK_FALLBACK) or "").strip().lower() or DEFAULT_CHUNK_FALLBACK
    if fallback not in CHUNK_FALLBACKS:
        logger.warning("%s 는 %s 중 하나여야 해서 기본값(%s)을 씁니다.", ENV_CHUNK_FALLBACK, CHUNK_FALLBACKS, DEFAULT_CHUNK_FALLBACK)
        fallback = DEFAULT_CHUNK_FALLBACK

    max_lines = _env_float(environ, ENV_MAX_LINE_PREDICTIONS, float(DEFAULT_MAX_LINE_PREDICTIONS), 0, 100_000)

    return ScanConfig(
        line_threshold=_env_float(environ, ENV_LINE_THRESHOLD, None, 0.0, 1.0),
        chunk_fallback=fallback,
        fallback_min_probability=_env_float(environ, ENV_FALLBACK_MIN_PROBABILITY, DEFAULT_FALLBACK_MIN_PROBABILITY, 0.0, 1.0),
        max_line_predictions=int(max_lines if max_lines is not None else DEFAULT_MAX_LINE_PREDICTIONS),
    )


def child_line_inputs(chunk: Iterable[tuple[str, str, dict[str, Any]]]) -> list[tuple[str, str]]:
    """덩어리 → [(segment_id, 모델 입력 글)]. 아동 줄마다 바로 앞 상담사 줄(덩어리 안)과 묶는다."""

    inputs: list[tuple[str, str]] = []
    last_question: str | None = None

    for speaker, text, segment in chunk:
        if speaker == COUNSELOR_LABEL:
            last_question = text
            continue

        if speaker != CHILD_LABEL:
            continue

        segment_id = str(segment.get("segment_id", "")) if isinstance(segment, dict) else ""

        if not segment_id:
            continue

        body = f"{CHILD_LABEL}: {text}"
        inputs.append((segment_id, f"{COUNSELOR_LABEL}: {last_question}\n{body}" if last_question else body))

    return inputs


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def detected_labels(prediction: Any) -> list[str]:
    """판정에서 걸린 유형(순서 유지). 걸린 유형 목록을 그대로 주면 그대로, 모양이 다르면 빈 목록."""

    if isinstance(prediction, (list, tuple)):
        return [label for label in prediction if isinstance(label, str)]
    if not isinstance(prediction, dict):
        return []
    return [label for label, info in prediction.items() if isinstance(info, dict) and bool(info.get("detected", False))]


def _line_passes(info: Any, config: ScanConfig) -> bool:
    """줄 판정 하나가 '이 줄에 붙일' 기준을 넘는가. 확률 · 임계값이 없는 예전 모양이면 detected 를 그대로 믿는다."""

    if not isinstance(info, dict):
        return False
    if info.get("filtered_reason"):
        return False

    probability = _number(info.get("probability"))
    threshold = config.line_threshold if config.line_threshold is not None else _number(info.get("threshold"))

    if probability is None or threshold is None:
        return bool(info.get("detected", False))

    return probability >= threshold


def _best_line(label: str, line_predictions: Sequence[LinePrediction]) -> tuple[str, float] | None:
    """그 유형 확률이 가장 높은 줄(같으면 앞 줄). 확률이 없거나 필터가 내린 줄은 뺀다."""

    best: tuple[str, float] | None = None

    for segment_id, prediction in line_predictions:
        info = prediction.get(label) if isinstance(prediction, dict) else None
        if not isinstance(info, dict) or info.get("filtered_reason"):
            continue
        probability = _number(info.get("probability"))
        if probability is None:
            continue
        if best is None or probability > best[1]:
            best = (segment_id, probability)

    return best


def pick_segments(
    chunk_prediction: Any,
    line_predictions: Sequence[LinePrediction],
    config: ScanConfig | None = None,
) -> dict[str, list[str]]:
    """
    덩어리 판정(유형별 판정 dict, 또는 걸린 유형 목록)과 줄마다 다시 판정한 결과([(segment_id, 판정)]) → {segment_id: [유형]}.

    줄 임계값을 넘는 유형은 그 줄에(어느 유형이든). 덩어리 유형 중 어느 줄도 넘지 못한 것은 config.chunk_fallback 대로
    (top1: 확률 가장 높은 줄 하나 — fallback_min_probability 이상일 때 / none: 안 붙임 / all: 모든 줄).
    """

    config = config or scan_config()
    picked: dict[str, list[str]] = {}

    def add(segment_id: str, label: str) -> None:
        labels = picked.setdefault(segment_id, [])
        if label not in labels:
            labels.append(label)

    confirmed = set()

    for segment_id, prediction in line_predictions:
        if not isinstance(prediction, dict):
            continue
        for label, info in prediction.items():
            if _line_passes(info, config):
                add(segment_id, label)
                confirmed.add(label)

    for label in detected_labels(chunk_prediction):
        if label in confirmed:
            continue
        if config.chunk_fallback == "all":
            for segment_id, _ in line_predictions:
                add(segment_id, label)
        elif config.chunk_fallback == "top1":
            best = _best_line(label, line_predictions)
            if best is not None and best[1] >= config.fallback_min_probability:
                add(best[0], label)

    return picked


def plan_line_scoring(
    chunks: Sequence[Chunk],
    chunk_predictions: Sequence[Any],
    max_line_predictions: int,
) -> tuple[dict[int, list[tuple[str, str]]], list[int]]:
    """
    줄 판정 계획 → ({덩어리 번호: [(segment_id, 모델 입력 글)]}, 상한에 못 든 덩어리 번호).

    걸린 덩어리부터(원문 순서), 그다음 안 걸린 덩어리를 상한 안에서 통째로 넣는다(한 덩어리의 줄 일부만 판정하지 않음).
    아동 줄이 없는 덩어리는 판정할 것이 없어 어느 쪽에도 넣지 않는다.
    """

    detected = [index for index, prediction in enumerate(chunk_predictions) if detected_labels(prediction)]
    order = detected + [index for index in range(len(chunks)) if index not in set(detected)]

    inputs_by_chunk: dict[int, list[tuple[str, str]]] = {}
    skipped: list[int] = []
    used = 0

    for index in order:
        inputs = child_line_inputs(chunks[index])
        if not inputs:
            continue
        if used + len(inputs) <= max_line_predictions:
            inputs_by_chunk[index] = inputs
            used += len(inputs)
        else:
            skipped.append(index)

    return dict(sorted(inputs_by_chunk.items())), sorted(skipped)


def chunk_wide_pick(chunk: Chunk, labels: Iterable[str]) -> dict[str, list[str]]:
    """예전 방식(10/30 이전) — 덩어리의 아동 줄 전체에 걸린 유형을 붙인다. 줄 판정 상한에 못 든 덩어리에만 쓴다."""

    labels = [label for label in labels if isinstance(label, str)]
    if not labels:
        return {}

    return {segment_id: list(labels) for segment_id, _ in child_line_inputs(chunk)}


def merge_picks(target: dict[str, list[str]], picked: Mapping[str, Iterable[str]]) -> None:
    """고른 결과를 합친다(발화마다 유형 순서 유지 · 중복 없음)."""

    for segment_id, labels in picked.items():
        merged = target.setdefault(segment_id, [])
        for label in labels:
            if label not in merged:
                merged.append(label)
