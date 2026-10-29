from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .case_context import (
    RAG_INPUT_SPEAKERS,
    build_case_records,
    sorted_segments,
    speaker_check_items,
    speaker_of,
)
from .pipeline import analyze_consultation_evidence
from .privacy import RagPrivacyBlocked
from .screen_manual import build_screen_references


def child_text_from_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """검수된 Transcript 에서 아동 발화만 시간순으로 이어 붙인다.

    반환: text(아동 발화), child_segment_ids, excluded_speakers({화자: 뺀 발화 수})
    """
    texts: list[str] = []
    child_segment_ids: list[str] = []
    excluded: Counter[str] = Counter()

    for segment in sorted_segments(transcript):
        speaker = speaker_of(segment)
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        if speaker not in RAG_INPUT_SPEAKERS:
            excluded[speaker] += 1
            continue
        texts.append(text)
        child_segment_ids.append(str(segment.get("segment_id", "")))

    return {
        "text": " ".join(texts),
        "child_segment_ids": child_segment_ids,
        "excluded_speakers": dict(excluded),
    }


def _error_payload(name: str, error: Exception) -> dict[str, Any]:
    # 예외 문구에 상담 발화가 섞일 수 있어 비식별 차단 사유 외에는 예외 종류만 싣는다.
    if isinstance(error, RagPrivacyBlocked):
        return {
            "error": f"{name}: 비식별 검증을 통과하지 못해 외부 전송을 하지 않았습니다.",
            "privacy_blocked": True,
            "reasons": error.reasons,
        }
    return {"error": f"{name} 중 오류가 발생했습니다: {type(error).__name__}"}


def analyze_reviewed_transcript(
    transcript: dict[str, Any],
    abuse_type: str | None,
    *,
    known_identifiers: list[str] | None = None,
    session_no: int | None = None,
    session_id: str | None = None,
    previous_sessions: list[dict[str, Any]] | None = None,
    child_app_responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """STT 검수가 끝난 Transcript 로 근거자료 · 법령 · 판례 · 화면별 매뉴얼 근거 · 다음 상담 질문을 만든다.

    abuse_type 이 없으면(감지된 학대 유형 없음) 근거자료 분석은 건너뛰고 화면별 매뉴얼 근거만 만든다.
    두 분석 모두 아동 발화를 비식별한 뒤 OpenAI 로 보낸다.
    session_no · previous_sessions · child_app_responses 를 주면 다음 상담 질문
    (rag_analysis.next_session_checklist)이 이번 회차 아동 발화와 함께 이전 회차 기록 · 아이 앱 응답을 근거로 쓴다.
    speaker_check_items 는 화자 미확정 발화를 '확인할 사항'으로 만든 것으로, 외부로 보내지 않고 로컬에서 만든다.
    session_id(Backend 회차 ID)는 근거 링크용으로 결과에만 싣고 외부로 보내지 않는다.
    """
    child = child_text_from_transcript(transcript)
    result: dict[str, Any] = {
        "child_segment_ids": child["child_segment_ids"],
        "excluded_speakers": child["excluded_speakers"],
        "speaker_check_items": speaker_check_items(transcript, session_no=session_no, session_id=session_id),
        "rag_analysis": None,
        "manual_screen_references": None,
    }
    if not child["text"]:
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        rag_future = (
            pool.submit(
                analyze_consultation_evidence,
                text=child["text"],
                abuse_type=abuse_type,
                known_identifiers=known_identifiers,
                case_records=build_case_records(
                    transcript,
                    session_no=session_no,
                    session_id=session_id,
                    previous_sessions=previous_sessions,
                    child_app_responses=child_app_responses,
                ),
            )
            if abuse_type
            else None
        )
        manual_future = pool.submit(
            build_screen_references,
            child["text"],
            known_identifiers=known_identifiers,
        )

        if rag_future is not None:
            try:
                result["rag_analysis"] = rag_future.result()
            except Exception as error:
                result["rag_analysis"] = _error_payload("RAG 근거자료 분석", error)

        try:
            result["manual_screen_references"] = manual_future.result()
        except Exception as error:
            result["manual_screen_references"] = _error_payload("화면별 매뉴얼 근거 분석", error)

    return result
