"""
STT 검수 '1차 임시 핵심 발화'(quick_risk_scan) 줄 고르기(2026-10-30).

[왜]
1차 RoBERTa 는 여러 문답을 묶은 덩어리(chunk) 단위로 판정한다. 예전 스캔은 덩어리 하나가 걸리면 그 안의 발화를
전부 표시해서 "네" · "몰라요" 같은 줄까지 핵심 발화로 잡혔다(경진 10/30 데모 확인).

[어떻게]
덩어리 안의 아동 발화를 줄마다(바로 앞 상담사 질문과 묶어) 다시 모델에 넣는다.
- 줄에서 걸린 유형은 그 줄에만 표시한다. 덩어리 판정이 놓친 유형도 살린다(10/30 실제 모델 확인: 한 덩어리에서 '방임' 만
  걸렸지만 줄 단위로는 '때려요' · '허리띠로 맞았어요' 가 신체학대로 걸렸다).
- 덩어리에서는 걸렸는데 어느 줄에서도 다시 걸리지 않은 유형은 예전처럼 그 덩어리 아동 발화 전체에 표시한다
  (여러 줄에 걸친 진술일 수 있어 버리지 않는다 — 예전보다 나빠지지 않게). 1차 QA 경로는 확률을 주지 않아 '가장 높은 줄' 은 고를 수 없다.

이 모듈은 고르기 규칙만 둔다(모델 · torch 를 부르지 않는다 — backend/tests 에서 시험한다). 모델 호출은 infer_audio_session.
"""

from typing import Any, Dict, Iterable, List, Optional, Tuple

#: 줄마다 모델을 다시 부르는 수의 상한(스캔 제한 시간 KEY_SCAN_TIMEOUT_SECONDS 기본 30초 안에 끝나게).
#: 넘으면 남은 덩어리는 예전처럼 덩어리 안 아동 발화를 모두 표시한다.
MAX_LINE_PREDICTIONS = 80

CHILD_LABEL = "아동"
COUNSELOR_LABEL = "상담사"


def child_line_inputs(chunk: Iterable[Tuple[str, str, Dict[str, Any]]]) -> List[Tuple[str, str]]:
    """덩어리 → [(segment_id, 모델 입력 글)]. 아동 줄마다 바로 앞 상담사 줄(덩어리 안)과 묶는다."""

    inputs: List[Tuple[str, str]] = []
    last_question: Optional[str] = None

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


def pick_segments(
    chunk_labels: List[str],
    line_predictions: List[Tuple[str, Dict[str, Any]]],
) -> Dict[str, List[str]]:
    """
    덩어리에서 걸린 유형(chunk_labels)과 줄마다 다시 판정한 결과([(segment_id, 예측)]) → {segment_id: [유형]}.

    줄에서 detected 인 유형은 그 줄에(어느 유형이든). 덩어리 유형 중 어느 줄에서도 다시 걸리지 않은 것은 모든 줄에.
    """

    picked: Dict[str, List[str]] = {}

    def add(segment_id: str, label: str) -> None:
        labels = picked.setdefault(segment_id, [])
        if label not in labels:
            labels.append(label)

    confirmed = set()

    for segment_id, prediction in line_predictions:
        if not isinstance(prediction, dict):
            continue
        for label, info in prediction.items():
            if isinstance(info, dict) and info.get("detected", False):
                add(segment_id, label)
                confirmed.add(label)

    for label in chunk_labels:
        if label not in confirmed:
            for segment_id, _ in line_predictions:
                add(segment_id, label)

    return picked
