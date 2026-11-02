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
    with_questions: bool = True,
    with_manual_references: bool = True,
    link_questions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """STT 검수가 끝난 Transcript 로 근거자료 · 법령 · 판례 · 화면별 매뉴얼 근거 · 다음 상담 질문을 만든다.

    abuse_type 이 없으면(감지된 학대 유형 없음) 근거자료 분석은 건너뛰고 화면별 매뉴얼 근거만 만든다.
    두 분석 모두 아동 발화를 비식별한 뒤 OpenAI 로 보낸다.
    session_no · previous_sessions · child_app_responses 를 주면 다음 상담 질문
    (rag_analysis.next_session_checklist)이 이번 회차 아동 발화와 함께 이전 회차 기록 · 아이 앱 응답을 근거로 쓴다.
    speaker_check_items 는 화자 미확정 발화를 '확인할 사항'으로 만든 것으로, 외부로 보내지 않고 로컬에서 만든다.
    session_id(Backend 회차 ID)는 근거 링크용으로 결과에만 싣고 외부로 보내지 않는다.

    privacy_blocked · privacy_reasons: 어느 쪽(근거자료 분석 · 화면별 매뉴얼 근거)이든 비식별 검증에 막혀 외부로 보내지 않았으면
    True 와 막힌 사유(원문 없음). 학대 유형이 없어 근거자료 분석은 돌지 않고 매뉴얼 근거만 막힌 경우도 여기서 알 수 있다 —
    호출하는 쪽은 rag_analysis 만 보지 말고 이 값을 본다.

    Backend 연동(backend API_CONTRACT 19절)은 with_questions=False · with_manual_references=False 로 부른다:
    질문은 만들지 않고(추가 질문은 #118 초안 하나에서만 — 팀장님 10/29 결정 ②) 화면별 매뉴얼 근거도 만들지 않는다.
    link_questions(#118 초안 [{draft_index, text, reason?}])를 주면 검토를 통과한 공식 근거만 붙여
    rag_analysis.next_session_checklist.question_evidence 로 돌려준다(official_evidence.attach_official_evidence).
    기본값이면 지금까지와 같다.
    """
    child = child_text_from_transcript(transcript)
    result: dict[str, Any] = {
        "child_segment_ids": child["child_segment_ids"],
        "excluded_speakers": child["excluded_speakers"],
        "speaker_check_items": speaker_check_items(transcript, session_no=session_no, session_id=session_id),
        "rag_analysis": None,
        "manual_screen_references": None,
        "privacy_blocked": False,
        "privacy_reasons": [],
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
                with_questions=with_questions,
                link_questions=link_questions,
            )
            if abuse_type
            else None
        )
        manual_future = (
            pool.submit(
                build_screen_references,
                child["text"],
                known_identifiers=known_identifiers,
            )
            if with_manual_references
            else None
        )

        # 한 쪽이 실패해도 다른 쪽 결과는 돌려준다. 실패는 원문 없는 오류 칸으로 바꾼다(_error_payload).
        if rag_future is not None:
            try:
                result["rag_analysis"] = rag_future.result()
            except Exception as error:  # noqa: BLE001
                result["rag_analysis"] = _error_payload("RAG 근거자료 분석", error)

        if manual_future is not None:
            try:
                result["manual_screen_references"] = manual_future.result()
            except Exception as error:  # noqa: BLE001
                result["manual_screen_references"] = _error_payload("화면별 매뉴얼 근거 분석", error)

    blocked = [
        part
        for part in (result["rag_analysis"], result["manual_screen_references"])
        if isinstance(part, dict) and part.get("privacy_blocked")
    ]
    result["privacy_blocked"] = bool(blocked)
    result["privacy_reasons"] = list(dict.fromkeys(reason for part in blocked for reason in part.get("reasons") or []))
    return result
