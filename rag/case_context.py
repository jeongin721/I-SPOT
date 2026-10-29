from __future__ import annotations

from datetime import date, datetime
from typing import Any

# RAG 입력으로 쓰는 화자. 보호자(GUARDIAN) 진술은 아이에게 할 질문의 근거로 쓰지 않는다(화면 원칙 6).
# 상담원 · 기타 · 미확정(UNKNOWN) 발화도 넣지 않는다. 화자 확인은 STT 검수에서 끝난 상태여야 한다.
RAG_INPUT_SPEAKERS = frozenset({"CHILD"})

# 프롬프트가 너무 길어지지 않게 사례 기록을 자른다.
MAX_RECORD_CHARS = 600
MAX_PREVIOUS_SESSIONS = 3
MAX_PREVIOUS_SEGMENTS = 40
MAX_APP_RESPONSES = 10
MAX_SPEAKER_CHECK_ITEMS = 3


def sorted_segments(transcript: dict[str, Any] | None) -> list[dict[str, Any]]:
    segments = [
        segment
        for segment in (transcript or {}).get("segments") or []
        if isinstance(segment, dict)
    ]
    segments.sort(key=lambda segment: int(segment.get("start_ms") or 0))
    return segments


def speaker_of(segment: dict[str, Any]) -> str:
    return str(segment.get("speaker") or "UNKNOWN").upper()


def format_time(start_ms: Any) -> str:
    """화면 근거 표기용 시각(01:08, 1:02:03)."""
    total = max(int(start_ms or 0), 0) // 1000
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _session_label(session_no: int | None, current: bool) -> str:
    if session_no:
        return f"{session_no}회차"
    return "이번 회차" if current else "이전 회차"


def _shorten(text: str, limit: int = MAX_RECORD_CHARS) -> str:
    normalized = " ".join((text or "").split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1].rstrip() + "…"


def _date_label(value: Any) -> str:
    """'2026-10-07' → '10/7'. 못 읽으면 빈 문자열."""
    if isinstance(value, (date, datetime)):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
        except ValueError:
            return ""
    return f"{parsed.month}/{parsed.day}"


def _segment_records(
    transcript: dict[str, Any] | None,
    session_no: int | None,
    *,
    current: bool,
    session_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for segment in sorted_segments(transcript):
        text = str(segment.get("text") or "").strip()
        if not text or speaker_of(segment) not in RAG_INPUT_SPEAKERS:
            continue
        records.append(
            {
                "source": "transcript",
                "current": current,
                "session_no": session_no,
                "session_id": session_id,
                "segment_id": str(segment.get("segment_id", "")),
                "start_ms": int(segment.get("start_ms") or 0),
                "label": f"{_session_label(session_no, current)} {format_time(segment.get('start_ms'))}",
                "text": _shorten(text),
            }
        )
    # 이전 회차 발화가 너무 많으면 뒤쪽(최근)만 남긴다.
    return records[-limit:] if limit else records


def _previous_session_records(session: dict[str, Any]) -> list[dict[str, Any]]:
    session_no = session.get("session_no")
    prefix = _session_label(session_no, current=False)
    base = {"current": False, "session_no": session_no, "session_id": session.get("session_id")}
    records: list[dict[str, Any]] = []

    if str(session.get("summary") or "").strip():
        records.append({**base, "source": "summary", "label": f"{prefix} 상담 요약", "text": _shorten(session["summary"])})

    if str(session.get("safety_plan") or "").strip():
        records.append({**base, "source": "safety_plan", "label": f"{prefix} 안전 계획", "text": _shorten(session["safety_plan"])})

    for item in session.get("check_items") or []:
        if not isinstance(item, dict) or not str(item.get("item") or "").strip():
            continue
        text = str(item["item"]).strip()
        if str(item.get("note") or "").strip():
            text = f"{text} — {item['note']}"
        records.append(
            {
                **base,
                "source": "check_item",
                "status": "confirmed" if item.get("status") == "confirmed" else "open",
                "label": f"{prefix} 확인 사항",
                "text": _shorten(text),
            }
        )

    records.extend(
        _segment_records(
            session.get("transcript"),
            session_no,
            current=False,
            session_id=session.get("session_id"),
            limit=MAX_PREVIOUS_SEGMENTS,
        )
    )
    return records


def _app_response_records(responses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = [
        response
        for response in responses or []
        if isinstance(response, dict) and str(response.get("answer") or "").strip()
    ]
    usable.sort(key=lambda response: str(response.get("answered_at") or ""), reverse=True)

    records: list[dict[str, Any]] = []
    for response in usable[:MAX_APP_RESPONSES]:
        day = _date_label(response.get("answered_at"))
        question = str(response.get("question") or "").strip()
        answer = str(response["answer"]).strip()
        records.append(
            {
                "source": "app_response",
                "current": False,
                "response_id": str(response.get("response_id") or ""),
                "label": f"{day} 아이 앱 응답" if day else "아이 앱 응답",
                "text": _shorten(f"질문: {question} / 답: {answer}" if question else answer),
            }
        )
    return records


def build_case_records(
    transcript: dict[str, Any] | None,
    *,
    session_no: int | None = None,
    session_id: str | None = None,
    previous_sessions: list[dict[str, Any]] | None = None,
    child_app_responses: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """다음 상담 질문의 근거가 되는 사례 기록을 case:N 으로 번호 매겨 모은다.

    - 이번 회차: 검수된 Transcript 의 아동(CHILD) 발화만. 발화마다 근거 시각을 단다.
    - 이전 회차: 확정 요약 · 안전 계획 · 확인 사항(처리 상태) · 아동 발화. 최근 회차부터 MAX_PREVIOUS_SESSIONS 개.
    - 아이 앱 응답: 최근 MAX_APP_RESPONSES 개.
    session_id(Backend 회차 ID)는 LLM 에 보내지 않고 근거 링크(STT 검수 · 회차 상세)를 만들 때만 쓴다.
    text 는 아직 원문이다. 외부로 보내기 전에 pipeline 이 비식별한다.
    """
    records = _segment_records(transcript, session_no, current=True, session_id=session_id)

    previous = [session for session in previous_sessions or [] if isinstance(session, dict)]
    previous.sort(key=lambda session: int(session.get("session_no") or 0), reverse=True)
    for session in previous[:MAX_PREVIOUS_SESSIONS]:
        records.extend(_previous_session_records(session))

    records.extend(_app_response_records(child_app_responses or []))

    for index, record in enumerate(records, start=1):
        record["ref"] = f"case:{index}"
    return records


def speaker_check_items(
    transcript: dict[str, Any] | None,
    *,
    session_no: int | None = None,
    session_id: str | None = None,
    limit: int = MAX_SPEAKER_CHECK_ITEMS,
) -> list[dict[str, Any]]:
    """검수 후에도 화자가 미확정(UNKNOWN)인 발화를 '확인할 사항'으로 만든다.

    발화 내용은 질문 생성 입력에 넣지 않으므로(CHILD 발화만) 외부로 보내지 않고 여기서 바로 만든다.
    """
    items: list[dict[str, Any]] = []
    for segment in sorted_segments(transcript):
        if speaker_of(segment) != "UNKNOWN" or not str(segment.get("text") or "").strip():
            continue
        label = f"{_session_label(session_no, current=True)} {format_time(segment.get('start_ms'))}"
        items.append(
            {
                "id": f"speaker:{len(items) + 1}",
                "item": f"{format_time(segment.get('start_ms'))} 발화의 화자",
                "kind": "uncertain_speaker",
                "priority": "medium",
                "reason": "STT 검수 후에도 화자가 확정되지 않아 질문 생성 근거에서 뺀 발화입니다.",
                "basis": [
                    {
                        "type": "case",
                        "source": "transcript",
                        "label": f"{label} · 화자 불확실",
                        "session_no": session_no,
                        "session_id": session_id,
                        "segment_id": str(segment.get("segment_id", "")),
                        "start_ms": int(segment.get("start_ms") or 0),
                    }
                ],
            }
        )
        if len(items) >= limit:
            break
    return items
