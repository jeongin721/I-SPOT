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

from typing import Any, Dict, Iterable, List, Tuple

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
    child_ids, child_texts = _child_segments(transcript)

    overview = _clean_text(result.get("counseling_summary"))

    # 문장 → 근거 segment_id(원문 표기 그대로). 같은 문장이 두 번 나오면
    # 하나로 합치고 근거만 더한다. 화면에 같은 요지가 두 줄 보이지 않게 한다.
    # dict 는 넣은 순서를 지키므로 key_points 순서도 처음 나온 순서다.
    grouped: Dict[str, Dict[str, None]] = {}
    raw_point_count = 0

    for point in _statement_points(result.get("record_draft")):
        raw_point_count += 1

        text = _clean_text(point.get("text"))

        if not text:
            continue

        segment_ids = [
            child_ids[key]
            for key in _segment_ids(point.get("segment_ids"))
            if key in child_ids
        ]

        if not segment_ids:
            continue

        bucket = grouped.setdefault(text, {})

        for segment_id in segment_ids:
            bucket.setdefault(segment_id, None)

    # 점수는 합친 뒤 한 번만 계산한다. 합칠 때마다 다시 계산하면
    # 같은 문장이 많을 때 근거 수의 제곱만큼 느려진다.
    key_points = list(grouped)
    evidence = [
        {
            "key_point": text,
            "segment_ids": list(segment_ids),
            "score": _score(text, segment_ids, child_texts),
        }
        for text, segment_ids in grouped.items()
    ]

    warnings: List[str] = []

    if not overview:
        warnings.append(OVERVIEW_EMPTY_WARNING)

    # 기록 초안은 LLM 실패를 삼키고 빈 목록을 돌려준다(record_draft_llm.py).
    # "아동이 한 말이 없음" 과 "만들지 못함" 을 상담사가 구분할 수 있게,
    # 아동 발화가 있거나 요지가 왔는데 다 걸러졌으면 경고를 단다.
    # child_texts 는 근거로 쓸 수 있는 발화만 담는다(id 가 겹치면 빠짐).
    # 그래서 "원문에 아동 발화가 있는가" 는 따로 본다(10/16 Codex 재검증).
    if not key_points and (_has_child_speech(transcript) or raw_point_count):
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
    돌려주는 값은 대조용 키(_id_key)다. 원문 표기는 _child_segments 가 되돌린다.
    """

    if not isinstance(value, (list, tuple)):
        return []

    keys: Dict[str, None] = {}

    for raw in value:
        if isinstance(raw, bool) or not isinstance(raw, (str, int)):
            continue

        try:
            key = _id_key(str(raw))
        except ValueError:
            # 4300자리를 넘는 정수는 파이썬이 문자열로 바꾸지 않는다.
            # 정상 segment_id 는 50자 이하라 근거가 될 수 없다.
            continue

        if key:
            keys.setdefault(key, None)

    return list(keys)


def _id_key(segment_id: str) -> str:
    """원문 · 인용 양쪽에 같게 쓰는 segment_id 대조 규칙.

    한쪽만 공백을 지우면 원문의 보호자 " s1 " 을 인용한 근거가
    아동 "s1" 으로 바뀐다(10/15 Codex 교차검증). 그래서 양쪽 모두 이 함수로 비교한다.
    str.strip() 은 탭 · 줄바꿈 · NBSP · 전각 공백도 지운다.
    """

    return segment_id.strip()


def _child_segments(transcript: Any) -> Tuple[Dict[str, str], Dict[str, str]]:
    """원문에서 근거로 쓸 수 있는 아동 발화를 모은다.

    돌려주는 값
      child_ids    대조용 키 → 원문 segment_id(표기 그대로. 응답에는 이 값을 싣는다)
      child_texts  원문 segment_id → 발화 text

    대조용 키가 원문에서 두 번 이상 나오면(완전히 같은 id 든, 공백만 다른 id 든)
    인용이 어느 발화를 가리키는지 확정할 수 없으므로 그 키는 근거로 쓰지 않는다.
    화자가 같아도 뺀다. STT 계약은 공백만 다른 id 를 막지 않으므로 이 때문에
    맞는 근거를 잃을 수도 있다. 일반 STT 가 만드는 seg_NNN 에서는 생기지 않는
    입력이라, 보호자 발화가 아동 근거로 붙는 길을 막는 쪽을 택했다.
    """

    segments = transcript.get("segments") if isinstance(transcript, dict) else None

    if not isinstance(segments, list):
        return {}, {}

    candidates: Dict[str, List[Dict[str, Any]]] = {}

    for segment in segments:
        if not isinstance(segment, dict):
            continue

        segment_id = segment.get("segment_id")

        if not isinstance(segment_id, str):
            continue

        key = _id_key(segment_id)

        if key:
            candidates.setdefault(key, []).append(segment)

    child_ids: Dict[str, str] = {}
    child_texts: Dict[str, str] = {}

    for key, matched in candidates.items():
        if len(matched) != 1:
            continue

        segment = matched[0]
        text = _clean_text(segment.get("text"))

        if segment.get("speaker") == CHILD_SPEAKER and text:
            child_ids[key] = segment["segment_id"]
            child_texts[segment["segment_id"]] = text

    return child_ids, child_texts


def _has_child_speech(transcript: Any) -> bool:
    """원문에 내용이 있는 아동 발화가 하나라도 있는가. id 가 근거로 쓸 수 있는지와는 따로 본다."""

    segments = transcript.get("segments") if isinstance(transcript, dict) else None

    if not isinstance(segments, list):
        return False

    return any(
        isinstance(segment, dict)
        and segment.get("speaker") == CHILD_SPEAKER
        and bool(_clean_text(segment.get("text")))
        for segment in segments
    )


def _score(
    key_point: str,
    segment_ids: Iterable[str],
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
