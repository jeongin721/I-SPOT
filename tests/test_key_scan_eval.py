# experiments/key_scan_eval.py — 1차 핵심 발화 스캔 정밀도 측정(0단계). 모델 없이 시트 · 라벨 · 되감기(replay) · 지표만 본다.
# 데이터는 모두 지어낸 것이다.

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("key_scan_eval", ROOT / "experiments" / "key_scan_eval.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

kr = ev.kr


def _p(**labels):
    return {label: {"probability": value, "detected": value >= 0.5, "threshold": 0.5} for label, value in labels.items()}


CONTRACT = {
    "segments": [
        {"segment_id": "seg_001", "speaker": "COUNSELOR", "start_ms": 0, "end_ms": 1000, "text": "요즘 어때?"},
        {"segment_id": "seg_002", "speaker": "CHILD", "start_ms": 46_000, "end_ms": 51_000, "text": "네, 없어요."},
        {"segment_id": "seg_003", "speaker": "CHILD", "start_ms": 69_000, "end_ms": 77_000, "text": "컵을 던졌어요."},
        {"segment_id": "seg_004", "speaker": "GUARDIAN", "start_ms": 80_000, "end_ms": 81_000, "text": "아니에요."},
        {"segment_id": "seg_005", "speaker": "CHILD", "start_ms": 90_000, "end_ms": 91_000, "text": "  "},
    ],
}

# 덩어리 하나: 신체학대가 덩어리에서 걸렸고 줄 단위로는 seg_003(0.45) 가 가장 높다. seg_002 는 0.1.
RECORD = {
    "transcript_id": "t1",
    "scan_seconds": 1.5,
    "seconds": {"chunk": 1.0, "line": 0.5},
    "scored_lines": 2,
    "chunks": [
        {
            "chunk_index": 1,
            "prediction": _p(신체학대=0.9, 정서학대=0.1),
            "child_segment_ids": ["seg_002", "seg_003"],
            "line_predictions": [["seg_002", _p(신체학대=0.1)], ["seg_003", _p(신체학대=0.45)]],
        }
    ],
}


# ---------------------------------------------------------------------------
# 전사본 · 시트 · 라벨
# ---------------------------------------------------------------------------


def test_transcript_from_json_accepts_contract_and_backend_response():
    assert ev.transcript_from_json(CONTRACT, "file") == ("file", CONTRACT)
    assert ev.transcript_from_json({"session_id": "s-1", "transcript": CONTRACT}, "file") == ("s-1", CONTRACT)

    with pytest.raises(ValueError):
        ev.transcript_from_json({"transcript": None}, "file")


def test_sheet_lists_child_lines_only_with_clock_and_empty_gold(tmp_path):
    out = tmp_path / "labels.csv"

    assert ev.write_sheet([("t1", CONTRACT)], out) == 2

    with out.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["segment_id"] for row in rows] == ["seg_002", "seg_003"]  # 상담사 · 보호자 · 빈 줄은 없음
    assert rows[0]["start"] == "00:46" and rows[0]["text"] == "네, 없어요." and rows[0]["gold_types"] == ""
    assert list(rows[0]) == ev.SHEET_COLUMNS


def test_parse_types_accepts_english_korean_and_unsure():
    assert ev.parse_types("PHYSICAL|EMOTIONAL") == {"PHYSICAL", "EMOTIONAL"}
    assert ev.parse_types("신체학대, 방임") == {"PHYSICAL", "NEGLECT"}
    assert ev.parse_types("정서 / sexual") == {"EMOTIONAL", "SEXUAL"}
    assert ev.parse_types("") == set()
    assert ev.parse_types("?") is None

    with pytest.raises(ValueError):
        ev.parse_types("기타")


def test_load_labels_reads_the_sheet_back(tmp_path):
    path = tmp_path / "labels.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ev.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerow({"transcript_id": "t1", "segment_id": "seg_002", "gold_types": ""})
        writer.writerow({"transcript_id": "t1", "segment_id": "seg_003", "gold_types": "신체"})
        writer.writerow({"transcript_id": "t1", "segment_id": "seg_009", "gold_types": "?"})

    assert ev.load_labels(path) == {("t1", "seg_002"): set(), ("t1", "seg_003"): {"PHYSICAL"}, ("t1", "seg_009"): None}


# ---------------------------------------------------------------------------
# 되감기 — 저장한 점수로 규칙을 바꿔 다시 고른다
# ---------------------------------------------------------------------------


def test_replay_follows_the_fallback_rule():
    assert ev.replay(RECORD, kr.ScanConfig(chunk_fallback="top1")) == {"seg_003": ["신체학대"]}
    assert ev.replay(RECORD, kr.ScanConfig(chunk_fallback="none")) == {}
    assert ev.replay(RECORD, kr.ScanConfig(chunk_fallback="all")) == {"seg_002": ["신체학대"], "seg_003": ["신체학대"]}
    assert ev.replay(RECORD, kr.ScanConfig(line_threshold=0.4)) == {"seg_003": ["신체학대"]}


def test_replay_simulates_the_line_budget_from_stored_scores():
    # 상한 1줄: 덩어리(2줄)가 통째로 못 들어가 → all 이면 예전 방식(아동 줄 전체), top1 · none 이면 아무것도 없음.
    assert ev.replay(RECORD, kr.ScanConfig(chunk_fallback="all", max_line_predictions=1)) == {
        "seg_002": ["신체학대"],
        "seg_003": ["신체학대"],
    }
    assert ev.replay(RECORD, kr.ScanConfig(chunk_fallback="top1", max_line_predictions=1)) == {}


# ---------------------------------------------------------------------------
# 지표
# ---------------------------------------------------------------------------

LABELS = {
    ("t1", "seg_002"): set(),
    ("t1", "seg_003"): {"PHYSICAL"},
    ("t1", "seg_007"): {"EMOTIONAL"},  # 아무 규칙도 못 고른 발화 → FN
    ("t1", "seg_009"): None,  # 모름 → 제외
}


def test_metrics_count_pairs_and_utterances():
    picks = {"t1": {"seg_002": ["신체학대"], "seg_003": ["신체학대"], "seg_011": ["방임"]}}

    metrics = ev.compute_metrics(picks, LABELS)

    assert metrics["labeled"] == 3 and metrics["positive"] == 2
    assert metrics["chips"] == 2 and metrics["unlabeled_chips"] == 1  # seg_011 은 라벨이 없다
    assert (metrics["micro"]["tp"], metrics["micro"]["fp"], metrics["micro"]["fn"]) == (1, 1, 1)
    assert metrics["micro"]["precision"] == 0.5 and metrics["micro"]["recall"] == 0.5
    assert metrics["per_type"]["PHYSICAL"]["precision"] == 0.5 and metrics["per_type"]["EMOTIONAL"]["recall"] == 0.0
    assert (metrics["any"]["tp"], metrics["any"]["fp"], metrics["any"]["fn"]) == (1, 1, 1)


def test_metrics_with_nothing_picked_are_zero_not_an_error():
    metrics = ev.compute_metrics({"t1": {}}, LABELS)

    assert metrics["micro"] == {"tp": 0, "fp": 0, "fn": 2, "precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_report_compares_the_rules_on_the_same_scores(tmp_path):
    report = ev.evaluate([RECORD], LABELS, thresholds=(0.4,), production=kr.ScanConfig())

    assert "전사본 1개, 라벨 발화 3개(모름 1개 제외)" in report
    # 10/30 규칙은 seg_002(음성)에도 붙여 FP 1, top1 은 seg_003 만 골라 FP 0.
    assert "| 10/30 규칙(되돌림 all · 80줄) | 2 | 1 | 1 | 1 |" in report
    assert "| 지금 설정(환경 변수) | 1 | 1 | 0 | 1 |" in report
    assert "| 줄 0.4 · none | 1 | 1 | 0 | 1 |" in report
    assert "## 유형별 — 지금 설정(환경 변수)" in report
    assert "KEY_SCAN_LINE_THRESHOLD=" in report

    # CLI 로도 같은 보고서가 나온다.
    scores = tmp_path / "scores.jsonl"
    scores.write_text(json.dumps(RECORD, ensure_ascii=False) + "\n", encoding="utf-8")
    labels = tmp_path / "labels.csv"
    with labels.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ev.SHEET_COLUMNS)
        writer.writeheader()
        for (transcript_id, segment_id), gold in LABELS.items():
            writer.writerow({"transcript_id": transcript_id, "segment_id": segment_id, "gold_types": "?" if gold is None else "|".join(sorted(gold))})
    out = tmp_path / "report.md"

    assert ev.main(["evaluate", "--scores", str(scores), "--labels", str(labels), "--thresholds", "0.4", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == report


def test_law_gate_keeps_only_pairs_over_the_similarity():
    picks = {"seg_002": ["신체학대"], "seg_003": ["신체학대", "방임"], "seg_004": ["정서학대"]}
    similarity = {
        "seg_002": {"신체학대": {"score": 0.2, "excerpt": "x"}},
        "seg_003": {"신체학대": {"score": 0.7, "excerpt": "허리띠로 맞았어요"}, "방임": {"score": 0.4, "excerpt": "y"}},
    }

    assert ev.apply_law_gate(picks, similarity, 0.45) == {"seg_003": ["신체학대"]}
    assert ev.apply_law_gate(picks, similarity, 0.0) == {"seg_002": ["신체학대"], "seg_003": ["신체학대", "방임"]}  # 유사도 없는 발화(seg_004)는 뺀다
    assert ev.apply_law_gate(picks, {}, 0.45) == {}


def test_report_adds_law_gate_rows_when_similarity_was_recorded():
    # 지금 설정(top1)은 seg_003 에 신체를 붙인다. 유사도가 0.3 이면 게이트 0.45 에서 조문이 빠져 TP 0 · FN 2 가 된다.
    record = {**RECORD, "law_similarity": {"seg_003": {"신체학대": {"score": 0.3, "excerpt": "x"}}}}

    report = ev.evaluate([record], LABELS, thresholds=(0.4,), production=kr.ScanConfig(), law_thresholds=(0.25, 0.45))

    assert "| 지금 설정 + 조문 게이트 0.25 | 1 | 1 | 0 | 1 |" in report
    assert "| 지금 설정 + 조문 게이트 0.45 | 0 | 0 | 0 | 2 |" in report
    assert "유사도가 있는 전사본 1/1개" in report

    # 유사도를 적지 않은 점수면 게이트 행이 없다.
    assert "조문 게이트" not in ev.evaluate([RECORD], LABELS, thresholds=(0.4,), production=kr.ScanConfig())


def test_score_record_drops_the_utterance_text():
    collected = {
        "seconds": {"chunk": 1.0, "line": 0.2},
        "chunks": [
            {
                "chunk_index": 1,
                "segment_ids": ["seg_001", "seg_002"],
                "prediction": _p(신체학대=0.9),
                "inputs": [("seg_002", "상담사: 요즘 어때?\n아동: 네, 없어요.")],
                "line_predictions": [("seg_002", _p(신체학대=0.1))],
                "budget_skipped": False,
            }
        ],
    }

    record = ev.score_record("t1", CONTRACT, collected, 1.234)

    assert record["scored_lines"] == 1 and record["scan_seconds"] == 1.234
    assert record["chunks"][0]["child_segment_ids"] == ["seg_002"]
    assert "없어요" not in json.dumps(record, ensure_ascii=False)
