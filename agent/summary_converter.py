# ai-modeling 분석 결과를 서버 요약 응답 모양으로 바꾸는 변환기.
#
# 설계 근거: setting/specs/I-SPOT/ai-analysis-connect-research-1013.md 4절 안 B
#            '요약 변환기' 표 (10/13 사용자 결정 3)
#
# 이경진 님 analyze_audio_session 은 요약을 문자열(counseling_summary)로 주고,
# 근거가 붙은 문장은 기록 초안의 child_statement_points[{text, segment_ids}]
# 뿐이다. 서버 응답은 summary{overview, key_points: List[str]} +
# summary_evidence[{key_point, segment_ids, score}] 라서 그대로 꽂을 수 없다.
#
#   summary.overview       ← counseling_summary
#   summary.key_points     ← record_draft.child_statement_points[].text
#   summary_evidence       ← 같은 항목의 text · segment_ids, score 는 로컬 단어 유사도
#
# 근거 발화는 함께 받은 원문(STT 계약의 segments)으로 다시 대조한다.
# 기록 초안은 모든 화자의 발화를 입력으로 받고 segment_id 가 있는지만 본다.
# 그래서 보호자 발화가 '아동 진술 요지' 의 근거로 들어올 수 있다
# (counselor-web/README.md 원칙 6 "보호자 진술은 근거로 쓰지 않음").
# 여기서 아동(CHILD) 발화만 남기고, 근거가 다 빠진 항목은 요지에서도 뺀다.
#
# 이 파일은 순수 함수만 둔다.
#   - 이경진 님 모듈을 import 하지 않는다(torch · 가중치 · OpenAI 없이 돌아야 함)
#   - LLM 을 부르지 않는다. 원문이 밖으로 나가지 않는다
#   - 입력이 비거나 형식이 틀려도 예외를 던지지 않고 빈 값 + 경고를 돌려준다
#   - 위험 3필드는 다루지 않는다(build_risk_fields 쪽, 다음 차례)
#
# 반환값은 AgentState 의 summary · summary_evidence · warnings 와 같은 모양이다.
# AIAnalysisResult 검증은 LangGraphAIAdapter._to_bundle 이 마지막에 한다.

from typing import Any, Dict, Iterable, List

from ai.services.evidence_linker import calculate_similarity

KEY_POINTS_EMPTY_WARNING = "요약 항목을 만들지 못했습니다. 원문을 직접 확인해 주세요."
OVERVIEW_EMPTY_WARNING = "상담 요약을 만들지 못했습니다. 원문을 직접 확인해 주세요."

CHILD_SPEAKER = "CHILD"


def convert_summary(
    session_result: Any,
    transcript: Any,
) -> Dict[str, Any]:
    """analyze_audio_session 결과를 summary · summary_evidence · warnings 로 바꾼다.

    session_result: analyze_audio_session 이 돌려준 dict.
                    counseling_summary 와 record_draft 만 읽는다.
    transcript:     분석에 넘긴 STT 계약 dict({"segments": [...]}).
                    근거 발화의 화자 · 존재 확인에만 쓴다.
                    session_result 안의 segments 는 쓰지 않는다
                    (모듈이 돌려준 값으로 모듈을 검사하면 관문이 되지 않는다).
    """

    result = session_result if isinstance(session_result, dict) else {}
    child_texts = _child_segment_texts(transcript)

    overview = _clean_text(result.get("counseling_summary"))

    key_points: List[str] = []
    evidence: List[Dict[str, Any]] = []
    evidence_by_text: Dict[str, Dict[str, Any]] = {}
    raw_point_count = 0

    for point in _statement_points(result.get("record_draft")):
        raw_point_count += 1

        text = _clean_text(point.get("text"))

        if not text:
            continue

        segment_ids = [
            segment_id
            for segment_id in _segment_ids(point.get("segment_ids"))
            if segment_id in child_texts
        ]

        if not segment_ids:
            continue

        # 같은 문장이 두 번 나오면 하나로 합치고 근거만 더한다.
        # 화면에 같은 요지가 두 줄 보이지 않게 한다.
        existing = evidence_by_text.get(text)

        if existing is not None:
            for segment_id in segment_ids:
                if segment_id not in existing["segment_ids"]:
                    existing["segment_ids"].append(segment_id)

            existing["score"] = _score(text, existing["segment_ids"], child_texts)
            continue

        item = {
            "key_point": text,
            "segment_ids": segment_ids,
            "score": _score(text, segment_ids, child_texts),
        }
        key_points.append(text)
        evidence.append(item)
        evidence_by_text[text] = item

    warnings: List[str] = []

    if not overview:
        warnings.append(OVERVIEW_EMPTY_WARNING)

    # 기록 초안은 LLM 실패를 삼키고 빈 목록을 돌려준다(record_draft_llm.py).
    # "아동이 한 말이 없음" 과 "만들지 못함" 을 상담사가 구분할 수 있게,
    # 아동 발화가 있거나 요지가 왔는데 다 걸러졌으면 경고를 단다.
    if not key_points and (child_texts or raw_point_count):
        warnings.append(KEY_POINTS_EMPTY_WARNING)

    return {
        "summary": {"overview": overview, "key_points": key_points},
        "summary_evidence": evidence,
        "warnings": warnings,
    }


# =========================================================
# 내부 helper
# =========================================================

def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _statement_points(record_draft: Any) -> Iterable[Dict[str, Any]]:
    if not isinstance(record_draft, dict):
        return []

    points = record_draft.get("child_statement_points")

    if not isinstance(points, list):
        return []

    return [point for point in points if isinstance(point, dict)]


def _segment_ids(value: Any) -> List[str]:
    """근거 segment_id 목록을 순서를 지키며 중복 없이 꺼낸다.

    문자열 하나("seg_001")를 목록으로 보고 글자마다 쪼개지 않도록
    list · tuple 만 받는다. 정수는 이경진 님 _clean_points 와 같게 문자열로 바꾼다.
    """

    if not isinstance(value, (list, tuple)):
        return []

    segment_ids: List[str] = []

    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            continue

        segment_id = str(raw).strip()

        if segment_id and segment_id not in segment_ids:
            segment_ids.append(segment_id)

    return segment_ids


def _child_segment_texts(transcript: Any) -> Dict[str, str]:
    """원문에서 아동 발화만 segment_id → text 로 모은다.

    segment_id 가 원문에 두 번 나오면 어느 화자의 발화인지 확정할 수 없으므로
    근거로 쓰지 않는다(STT 계약은 중복을 막지만 여기서 다시 믿지 않는다).
    """

    segments = transcript.get("segments") if isinstance(transcript, dict) else None

    if not isinstance(segments, list):
        return {}

    child_texts: Dict[str, str] = {}
    seen: set = set()
    duplicated: set = set()

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        segment_id = segment.get("segment_id")

        if not isinstance(segment_id, str) or not segment_id:
            continue

        if segment_id in seen:
            duplicated.add(segment_id)
            continue

        seen.add(segment_id)

        text = _clean_text(segment.get("text"))

        if segment.get("speaker") == CHILD_SPEAKER and text:
            child_texts[segment_id] = text

    for segment_id in duplicated:
        child_texts.pop(segment_id, None)

    return child_texts


def _score(
    key_point: str,
    segment_ids: List[str],
    child_texts: Dict[str, str],
) -> float:
    """요지 문장과 근거 발화의 연결 강도.

    ai/services/evidence_linker.find_evidence_segments 와 같은 뜻을 쓴다.
    발화마다 단어 겹침 비율을 계산하고 가장 큰 값을 고른다(LLM 쓰지 않음).
    """

    scores = [
        calculate_similarity(target_text=key_point, source_text=child_texts[segment_id])
        for segment_id in segment_ids
        if segment_id in child_texts
    ]

    return max(scores) if scores else 0.0


__all__ = [
    "KEY_POINTS_EMPTY_WARNING",
    "OVERVIEW_EMPTY_WARNING",
    "convert_summary",
]
