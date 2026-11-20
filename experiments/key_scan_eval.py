"""STT 검수 '1차 임시 핵심 발화' 정밀도 측정(0단계, 2026-11-06).

원문 확정 전 STT 검수 화면은 1차 모델(key_scan)이 고른 아동 발화 아래에 그 유형의 '임시' 관련 조문을 보인다.
관련 없는 발화에 조문이 붙는 일을 줄이려면 먼저 **어느 발화에 붙여야 맞는지**를 사람이 적고, 지금 규칙과 바꿀 규칙
(ai/modeling/abuse/key_scan_refine.py — 줄 임계값 · 되돌림 · 줄 판정 상한)을 같은 점수로 비교해야 한다.

흐름(모델 · 녹취 전사본이 있는 서버에서):
  1) sheet     전사본 → 라벨 시트(CSV). 아동 발화마다 gold_types 를 사람이 채운다.
               PHYSICAL · EMOTIONAL · SEXUAL · NEGLECT 를 | 로 이어 적는다(한글 신체학대 · 신체 도 됨).
               비우면 '조문 붙일 것 없음', ? 는 모름(측정에서 뺌).
  2) score     전사본 → 점수(JSONL). 1차 모델을 한 번만 돌려 덩어리 · 줄 확률을 모두 적는다(줄 판정 상한 없이).
               --self-check N 은 처음 N 줄을 한 줄씩 다시 판정해 묶음 판정과 확률이 같은지 확인한다.
               임시 조문 매칭 모델(law_match)이 있으면 아동 줄마다 유형별 유사도(닮은 예시)도 적는다.
  3) evaluate  점수 + 라벨 → 규칙 · 임계값 조합별 정밀도 · 재현율(마크다운 표). 모델 없이 어디서나 돈다.
               유사도가 있으면 '조문 게이트 τ'(--law-thresholds) 행 — 유형은 남기고 유사도 τ 미만인 조문만 뺀 셈이다.

실행:
  python experiments/key_scan_eval.py sheet    --transcripts results/key_scan/transcripts/ --out results/key_scan/labels.csv
  python experiments/key_scan_eval.py score    --transcripts results/key_scan/transcripts/ --out results/key_scan/scores.jsonl --self-check 20
  python experiments/key_scan_eval.py evaluate --scores results/key_scan/scores.jsonl --labels results/key_scan/labels.csv \
      --thresholds 0.5,0.6,0.7,0.8,0.9 --out results/key_scan/report.md

전사본 파일은 STT Contract({"segments": [...]}) 또는 Backend 의 GET /sessions/{id}/transcript 응답(JSON)이다.
transcript_id 는 응답의 session_id, 없으면 파일 이름이다.

- 시트 · 점수 · 보고서에는 상담 원문이 들어갈 수 있다. results/ 는 .gitignore 라 그 아래에 두고, 저장소에 올리지 않는다.
- 측정은 지금 모델의 '줄 고르기' 만 본다. 모델 자체를 바꾸지 않는다.
- 정밀도 = 붙인 조문 가운데 맞은 것, 재현율 = 붙였어야 할 것 가운데 붙인 것. 발화 단위는 유형을 보지 않고 '조문이 붙었나' 만 본다.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import time
from collections import Counter
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 고르기 규칙(모델 · torch 없이 import 된다). 모델 모듈은 score 에서만 부른다.
kr = importlib.import_module("ai.modeling.abuse.key_scan_refine")

TYPE_TO_ENGLISH = {"신체학대": "PHYSICAL", "정서학대": "EMOTIONAL", "성학대": "SEXUAL", "방임": "NEGLECT"}
ENGLISH_TYPES = tuple(TYPE_TO_ENGLISH.values())
LABEL_ALIASES = {
    **{english: english for english in ENGLISH_TYPES},
    **TYPE_TO_ENGLISH,
    "신체": "PHYSICAL",
    "정서": "EMOTIONAL",
    "성": "SEXUAL",
}
#: 스캔이 고를 수 있는 화자. quick_risk_scan 은 아동 · 상담사 줄만 덩어리에 넣으므로 시트도 아동 발화만 적는다.
SHEET_SPEAKERS = ("CHILD",)
SHEET_COLUMNS = ["transcript_id", "segment_id", "start", "speaker", "text", "gold_types", "note"]
UNSURE = "?"
#: 점수 단계는 줄 판정 상한 없이 모든 아동 줄을 적는다(evaluate 가 상한을 흉내 낼 수 있게).
UNLIMITED = 10**9
DEFAULT_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9)
#: 임시 조문 매칭(law_match) 유사도 게이트 후보(KEY_SCAN_LAW_MIN_SIMILARITY).
DEFAULT_LAW_THRESHOLDS = (0.35, 0.45, 0.55)


# ---------------------------------------------------------------------------
# 전사본 · 라벨 읽기
# ---------------------------------------------------------------------------


def transcript_from_json(data: Any, fallback_id: str) -> tuple[str, dict]:
    """JSON 파일 내용 → (transcript_id, STT Contract). 모양이 다르면 ValueError."""

    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        return str(data.get("session_id") or fallback_id), data

    transcript = data.get("transcript") if isinstance(data, dict) else None
    if isinstance(transcript, dict) and isinstance(transcript.get("segments"), list):
        return str(data.get("session_id") or fallback_id), transcript

    raise ValueError(f"{fallback_id}: segments 가 없는 파일입니다(STT Contract 또는 transcript 응답이어야 함)")


def load_transcripts(paths: Iterable[str]) -> list[tuple[str, dict]]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        else:
            files.append(path)

    transcripts = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        transcripts.append(transcript_from_json(data, path.stem))
    return transcripts


def format_clock(milliseconds: Any) -> str:
    try:
        total = max(0, int(milliseconds) // 1000)
    except (TypeError, ValueError):
        return ""
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_types(raw: str) -> set[str] | None:
    """시트의 gold_types 칸 → 영문 유형 집합. 비면 빈 집합(음성), ? 면 None(모름). 모르는 낱말은 ValueError."""

    text = (raw or "").strip()
    if text == UNSURE:
        return None

    types: set[str] = set()
    for token in text.replace(",", "|").replace("/", "|").replace(" ", "|").split("|"):
        token = token.strip()
        if not token:
            continue
        english = LABEL_ALIASES.get(token) or LABEL_ALIASES.get(token.upper())
        if english is None:
            raise ValueError(f"모르는 유형 표기입니다: {token!r} (PHYSICAL · EMOTIONAL · SEXUAL · NEGLECT 또는 한글 이름)")
        types.add(english)
    return types


def load_labels(path: Path) -> dict[tuple[str, str], set[str] | None]:
    labels: dict[tuple[str, str], set[str] | None] = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"transcript_id", "segment_id", "gold_types"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"라벨 시트에 칸이 없습니다: {sorted(missing)}")
        for row in reader:
            key = (str(row["transcript_id"]).strip(), str(row["segment_id"]).strip())
            if not key[0] or not key[1]:
                continue
            try:
                labels[key] = parse_types(row.get("gold_types") or "")
            except ValueError as error:
                raise ValueError(f"{key[0]} {key[1]}: {error}") from error
    return labels


# ---------------------------------------------------------------------------
# 1) 라벨 시트
# ---------------------------------------------------------------------------


def sheet_rows(transcript_id: str, contract: dict) -> list[dict[str, str]]:
    rows = []
    for segment in contract.get("segments") or []:
        if not isinstance(segment, dict) or segment.get("speaker") not in SHEET_SPEAKERS:
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        rows.append(
            {
                "transcript_id": transcript_id,
                "segment_id": str(segment.get("segment_id") or ""),
                "start": format_clock(segment.get("start_ms")),
                "speaker": str(segment.get("speaker")),
                "text": text,
                "gold_types": "",
                "note": "",
            }
        )
    return rows


def write_sheet(transcripts: Iterable[tuple[str, dict]], out: Path) -> int:
    rows = [row for transcript_id, contract in transcripts for row in sheet_rows(transcript_id, contract)]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ---------------------------------------------------------------------------
# 2) 점수 — 모델을 한 번만 돌린다
# ---------------------------------------------------------------------------


def score_record(
    transcript_id: str,
    contract: dict,
    collected: dict,
    scan_seconds: float,
    law_similarity: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict:
    """quick_risk_scan 의 collect 결과 → 저장할 기록(원문 글은 뺀다 — 시트와 발화 번호로 잇는다).
    law_similarity: {발화 번호: {유형: {"score", "excerpt"}}} — excerpt 는 앵커 문장이지 원문이 아니다."""

    return {
        "transcript_id": transcript_id,
        "scan_seconds": round(scan_seconds, 3),
        "seconds": collected.get("seconds", {}),
        "scored_lines": sum(len(chunk.get("inputs") or []) for chunk in collected.get("chunks", [])),
        "law_similarity": law_similarity or {},
        "chunks": [
            {
                "chunk_index": chunk["chunk_index"],
                "prediction": chunk["prediction"],
                "child_segment_ids": [segment_id for segment_id, _ in chunk.get("inputs") or []],
                "line_predictions": chunk.get("line_predictions"),
            }
            for chunk in collected.get("chunks", [])
        ],
    }


def _law_matcher():
    """임시 조문 매칭(law_match) — 모델을 올릴 수 있으면 매처, 아니면 None(유사도 없이 진행)."""

    from ai.modeling.abuse import law_match

    matcher = law_match.get_matcher()
    if not matcher.enabled:
        print("임시 조문 매칭이 꺼져 있어(KEY_SCAN_LAW_MATCH=off) 유사도는 적지 않습니다.")
        return None
    if not matcher.ready():
        print("임시 조문 매칭 모델을 올리지 못해 유사도는 적지 않습니다(KEY_SCAN_LAW_EMBED_MODEL · HF 캐시 확인).")
        return None
    return matcher


def law_similarity_for(contract: dict, matcher) -> dict[str, dict[str, dict[str, Any]]]:
    """아동 발화마다 유형별 최고 유사도 · 닮은 예시(앵커 문장). 매처가 없으면 빈 dict."""

    if matcher is None:
        return {}
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for segment in contract.get("segments") or []:
        if not isinstance(segment, dict) or segment.get("speaker") not in SHEET_SPEAKERS:
            continue
        text = str(segment.get("text") or "").strip()
        similarity = matcher.similarities(text) if text else None
        if similarity:
            result[str(segment.get("segment_id") or "")] = similarity
    return result


def score_transcripts(transcripts: list[tuple[str, dict]], out: Path, self_check: int) -> None:
    # 모델(torch)은 여기서만 부른다 — sheet · evaluate 는 모델 없이 돈다.
    from ai.modeling.abuse.infer_abuse_v3_adapter import predict_major_types_detail
    from ai.modeling.abuse.infer_audio_session import quick_risk_scan

    config = replace(kr.scan_config(), max_line_predictions=UNLIMITED)
    out.parent.mkdir(parents=True, exist_ok=True)
    worst_gap = 0.0
    checked = 0
    matcher = _law_matcher()

    with out.open("w", encoding="utf-8") as handle:
        for transcript_id, contract in transcripts:
            collected: dict = {}
            started = time.monotonic()
            quick_risk_scan(contract, config=config, collect=collected.update)
            elapsed = time.monotonic() - started

            record = score_record(transcript_id, contract, collected, elapsed, law_similarity_for(contract, matcher))
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(
                f"{transcript_id}: 덩어리 {len(record['chunks'])}개 · 줄 {record['scored_lines']}개 · "
                f"{elapsed:.1f}초(덩어리 {record['seconds'].get('chunk', 0)}초 · 줄 {record['seconds'].get('line', 0)}초)"
            )

            # 묶음 판정(동적 패딩)과 한 줄씩 판정한 확률이 같은지 — 처음 self_check 줄만.
            for chunk in collected.get("chunks", []):
                batch = dict(chunk.get("line_predictions") or [])
                for segment_id, text in chunk.get("inputs") or []:
                    if checked >= self_check:
                        break
                    single = predict_major_types_detail(text)
                    for label, info in single.items():
                        gap = abs(float(info["probability"]) - float(batch[segment_id][label]["probability"]))
                        worst_gap = max(worst_gap, gap)
                    checked += 1

    if self_check:
        print(f"묶음 판정 확인: {checked}줄, 한 줄씩 판정과 확률 차이 최대 {worst_gap:.4f} (0.001 보다 크면 알려 주세요)")
    print(f"점수 저장: {out} (원문 글은 들어 있지 않음)")


# ---------------------------------------------------------------------------
# 3) 평가 — 같은 점수로 규칙 · 임계값을 바꿔 가며 다시 고른다
# ---------------------------------------------------------------------------


def replay(record: dict, config: kr.ScanConfig) -> dict[str, list[str]]:
    """저장한 점수로 quick_risk_scan 의 고르기(줄 판정 상한 계획 포함)를 그대로 다시 한다."""

    chunks = record["chunks"]
    pseudo = [[("아동", "", {"segment_id": segment_id}) for segment_id in chunk["child_segment_ids"]] for chunk in chunks]
    predictions = [chunk["prediction"] for chunk in chunks]
    inputs_by_chunk, skipped = kr.plan_line_scoring(pseudo, predictions, config.max_line_predictions)

    picks: dict[str, list[str]] = {}
    for index, chunk in enumerate(chunks):
        lines = [(segment_id, detail) for segment_id, detail in chunk.get("line_predictions") or []]
        if index in inputs_by_chunk and lines:
            picked = kr.pick_segments(chunk["prediction"], lines, config)
        elif index in skipped and config.chunk_fallback == "all":
            picked = kr.chunk_wide_pick(pseudo[index], kr.detected_labels(chunk["prediction"]))
        else:
            continue
        kr.merge_picks(picks, picked)
    return picks


def apply_law_gate(
    picks: dict[str, list[str]],
    law_similarity: dict[str, dict[str, dict[str, Any]]],
    threshold: float,
) -> dict[str, list[str]]:
    """조문 게이트 — 유형은 남지만 화면 조문은 유사도 ≥ τ 인 (발화, 유형)에만 붙는다. 그 조문만 '붙인 것'으로 센다."""

    gated: dict[str, list[str]] = {}
    for segment_id, types in picks.items():
        scores = law_similarity.get(segment_id) or {}
        kept = [label for label in types if float((scores.get(label) or {}).get("score", -1.0)) >= threshold]
        if kept:
            gated[segment_id] = kept
    return gated


def _rates(counts: Counter) -> dict[str, float]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def compute_metrics(picks_by_transcript: dict[str, dict[str, list[str]]], labels: dict[tuple[str, str], set[str] | None]) -> dict:
    """(발화, 유형) 쌍 단위 · 발화 단위('조문이 붙었나') 정밀도 · 재현율. 라벨 없는 발화에 붙은 것은 따로 센다."""

    predicted: dict[tuple[str, str], set[str]] = {}
    for transcript_id, picks in picks_by_transcript.items():
        for segment_id, types in picks.items():
            predicted[(transcript_id, segment_id)] = {TYPE_TO_ENGLISH.get(label, label) for label in types}

    per_type = {english: Counter() for english in ENGLISH_TYPES}
    any_level: Counter = Counter()
    chips = labeled = positive = 0

    for key, gold in labels.items():
        if gold is None:
            continue
        labeled += 1
        positive += bool(gold)
        found = predicted.get(key, set())
        chips += len(found)
        for english in ENGLISH_TYPES:
            per_type[english]["tp"] += english in found and english in gold
            per_type[english]["fp"] += english in found and english not in gold
            per_type[english]["fn"] += english not in found and english in gold
        any_level["tp"] += bool(found) and bool(gold)
        any_level["fp"] += bool(found) and not gold
        any_level["fn"] += not found and bool(gold)

    micro: Counter = Counter()
    for counts in per_type.values():
        micro.update(counts)

    unlabeled_chips = sum(len(types) for key, types in predicted.items() if labels.get(key, None) is None)

    return {
        "labeled": labeled,
        "positive": positive,
        "chips": chips,
        "unlabeled_chips": unlabeled_chips,
        "micro": _rates(micro),
        "any": _rates(any_level),
        "per_type": {english: _rates(counts) for english, counts in per_type.items()},
    }


def variants(production: kr.ScanConfig, thresholds: Iterable[float]) -> list[tuple[str, kr.ScanConfig]]:
    """비교할 규칙 — 지금 서버 설정 · 10/30 규칙(전체 되돌림 · 80줄) · 임계값 × 되돌림 조합(상한 없이)."""

    rows = [
        ("지금 설정(환경 변수)", production),
        ("10/30 규칙(되돌림 all · 80줄)", kr.ScanConfig(chunk_fallback="all", max_line_predictions=80)),
    ]
    for threshold in (None, *thresholds):
        for fallback in ("top1", "none"):
            rows.append(
                (
                    f"줄 {'모델' if threshold is None else threshold} · {fallback}",
                    kr.ScanConfig(line_threshold=threshold, chunk_fallback=fallback, max_line_predictions=UNLIMITED),
                )
            )
    return rows


def _pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def evaluate(
    records: list[dict],
    labels: dict[tuple[str, str], set[str] | None],
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
    production: kr.ScanConfig | None = None,
    law_thresholds: Iterable[float] = DEFAULT_LAW_THRESHOLDS,
) -> str:
    production = production or kr.scan_config()
    unsure = sum(1 for gold in labels.values() if gold is None)
    lines_scored = [record.get("scored_lines", 0) for record in records]
    seconds = [record.get("scan_seconds", 0.0) for record in records]

    out = [
        f"# 1차 핵심 발화 스캔 측정 — 전사본 {len(records)}개, 라벨 발화 {len(labels) - unsure}개(모름 {unsure}개 제외)",
        "",
        (
            f"- 스캔 시간(줄 판정 상한 없이): 평균 {sum(seconds) / len(seconds) if seconds else 0:.1f}초, 최대 {max(seconds) if seconds else 0:.1f}초, "
            f"전사본당 줄 평균 {sum(lines_scored) / len(lines_scored) if lines_scored else 0:.0f}개(최대 {max(lines_scored) if lines_scored else 0}개) "
            f"— KEY_SCAN_MAX_LINE_PREDICTIONS(지금 {production.max_line_predictions}) 를 정할 때 본다."
        ),
        (
            f"- 지금 설정: 줄 임계값 {production.line_threshold if production.line_threshold is not None else '모델(checkpoint)'} · "
            f"되돌림 {production.chunk_fallback}(최소 확률 {production.fallback_min_probability}) · 상한 {production.max_line_predictions}줄"
        ),
        "",
        "| 규칙 | 조문 수 | TP | FP | FN | 정밀도 | 재현율 | F1 | 발화 정밀도 | 발화 재현율 | 라벨 없는 발화의 조문 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    results = []
    for name, config in variants(production, thresholds):
        picks = {record["transcript_id"]: replay(record, config) for record in records}
        metrics = compute_metrics(picks, labels)
        results.append((name, config, metrics))
        micro, any_level = metrics["micro"], metrics["any"]
        out.append(
            f"| {name} | {metrics['chips']} | {micro['tp']} | {micro['fp']} | {micro['fn']} | {_pct(micro['precision'])} | "
            f"{_pct(micro['recall'])} | {_pct(micro['f1'])} | {_pct(any_level['precision'])} | {_pct(any_level['recall'])} | "
            f"{metrics['unlabeled_chips']} |"
        )

    # 조문 게이트(law_match 유사도) — 점수에 유사도가 있는 전사본이 하나라도 있을 때. 유사도가 없는 전사본은 게이트 없이 그대로.
    with_similarity = [record for record in records if record.get("law_similarity")]
    if with_similarity:
        base = {record["transcript_id"]: replay(record, production) for record in records}
        for threshold in law_thresholds:
            picks = {
                transcript_id: apply_law_gate(base[transcript_id], record.get("law_similarity") or {}, threshold)
                if record.get("law_similarity")
                else base[transcript_id]
                for transcript_id, record in ((record["transcript_id"], record) for record in records)
            }
            metrics = compute_metrics(picks, labels)
            micro, any_level = metrics["micro"], metrics["any"]
            out.append(
                f"| 지금 설정 + 조문 게이트 {threshold} | {metrics['chips']} | {micro['tp']} | {micro['fp']} | {micro['fn']} | "
                f"{_pct(micro['precision'])} | {_pct(micro['recall'])} | {_pct(micro['f1'])} | {_pct(any_level['precision'])} | "
                f"{_pct(any_level['recall'])} | {metrics['unlabeled_chips']} |"
            )
        out.append("")
        out.append(
            f"- 조문 게이트: 유형(먼저 들어볼 곳)은 그대로 두고 유사도(law_match)가 τ 미만인 조문만 뺀 것으로 셈 — "
            f"KEY_SCAN_LAW_MIN_SIMILARITY 후보. 유사도가 있는 전사본 {len(with_similarity)}/{len(records)}개."
        )

    name, _, metrics = results[0]
    out += ["", f"## 유형별 — {name}", "", "| 유형 | TP | FP | FN | 정밀도 | 재현율 | F1 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for english, rates in metrics["per_type"].items():
        out.append(
            f"| {english} | {rates['tp']} | {rates['fp']} | {rates['fn']} | {_pct(rates['precision'])} | {_pct(rates['recall'])} | {_pct(rates['f1'])} |"
        )

    best = max(results[2:], key=lambda item: item[2]["micro"]["f1"], default=None)
    if best is not None:
        out += [
            "",
            (
                f"F1 이 가장 높은 조합: **{best[0]}** — KEY_SCAN_LINE_THRESHOLD="
                f"{'' if best[1].line_threshold is None else best[1].line_threshold} · KEY_SCAN_CHUNK_FALLBACK={best[1].chunk_fallback}. "
                "정밀도를 우선하면 같은 재현율에서 FP 가 적은 줄을 고른다. 라벨이 100줄 미만이면 숫자 차이를 크게 믿지 않는다."
            ),
        ]
    return "\n".join(out) + "\n"


def load_records(path: Path) -> list[dict]:
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _thresholds(raw: str) -> tuple[float, ...]:
    values = tuple(float(token) for token in raw.split(",") if token.strip())
    for value in values:
        if not 0.0 <= value <= 1.0:
            raise argparse.ArgumentTypeError(f"임계값은 0~1 사이여야 합니다: {value}")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="STT 검수 1차 핵심 발화 스캔 정밀도 측정")
    commands = parser.add_subparsers(dest="command", required=True)

    sheet = commands.add_parser("sheet", help="전사본 → 라벨 시트(CSV)")
    sheet.add_argument("--transcripts", nargs="+", required=True, help="전사본 JSON 파일 또는 폴더")
    sheet.add_argument("--out", required=True, type=Path)

    score = commands.add_parser("score", help="전사본 → 덩어리 · 줄 확률(JSONL). 모델이 필요하다")
    score.add_argument("--transcripts", nargs="+", required=True)
    score.add_argument("--out", required=True, type=Path)
    score.add_argument("--self-check", type=int, default=0, help="처음 N 줄을 한 줄씩 다시 판정해 묶음 판정과 비교")

    evaluate_cmd = commands.add_parser("evaluate", help="점수 + 라벨 → 규칙별 정밀도 · 재현율(마크다운)")
    evaluate_cmd.add_argument("--scores", required=True, type=Path)
    evaluate_cmd.add_argument("--labels", required=True, type=Path)
    evaluate_cmd.add_argument("--thresholds", type=_thresholds, default=DEFAULT_THRESHOLDS, help="쉼표로 나눈 줄 임계값들")
    evaluate_cmd.add_argument(
        "--law-thresholds", type=_thresholds, default=DEFAULT_LAW_THRESHOLDS, help="쉼표로 나눈 조문 게이트 유사도 후보"
    )
    evaluate_cmd.add_argument("--out", type=Path, default=None, help="보고서 파일(없으면 화면에만)")

    args = parser.parse_args(argv)

    if args.command == "sheet":
        count = write_sheet(load_transcripts(args.transcripts), args.out)
        print(f"라벨 시트 {args.out}: 아동 발화 {count}줄. gold_types 칸을 채운 뒤 evaluate 에 넘깁니다(원문이 들어 있으니 올리지 않기).")
        return 0

    if args.command == "score":
        score_transcripts(load_transcripts(args.transcripts), args.out, args.self_check)
        return 0

    report = evaluate(load_records(args.scores), load_labels(args.labels), args.thresholds, law_thresholds=args.law_thresholds)
    print(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"보고서 저장: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
