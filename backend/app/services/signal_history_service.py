# 사례 단위 신호 이력 — GET /cases/{case_id}/signal-history (API_CONTRACT 4절, 2026-10-28).
#
# 화면(회차별 추이 · 상담 이력의 회차 카드 신호 · 세부 신호 행렬)이 회차마다 GET …/analysis 와
# GET …/risk-assessments 를 부르면 요청이 회차 수 × 2 로 늘어난다. 여기서 한 번에 모은다
# (이경진 님 제안 2026-10-27, PROPOSAL_signal_history_api.md). AI 를 새로 돌리지 않고 저장된 값만 읽는다.
#
# 값 규칙은 기존 창구와 같다.
#  - detected: 최신 분석 결과 abuse_signals[].detected(같은 유형 첫 항목, 참/거짓만, 아니면 None)
#  - ai_level: severity_ratings[].level 1~5 — risk_assessment_service.ai_level_for 와 같은 규칙(같은 유형 첫 항목이 정함)
#  - types[].counselor_level · assessed_at: session_risk_assessments(11.2절, 유형별)
#  - 회차 줄의 counselor_level · assessed_at: session_overall_risk_assessments(11.1절, 회차 전체. 2026-10-29 추가)
#  - 회차 줄의 topics: 최신 완료 분석 결과 topic_tags(아동 발화 대화 주제, 2026-10-29). 없으면 null
#  - 회차 줄의 subtypes: 최신 완료 분석 결과 risk_utterances 를 (유형, 세부 유형)으로 묶은 근거 발화 수(2026-10-30).
#    pending 은 근거 발화가 모두 화자 미확인(분석이 쓴 전사본의 speaker UNKNOWN)일 때 — 화면 '보류 (화자 확인 중)'.
# 처리 중 회기의 작업 유실 마감(expire_stale_processing)은 여기서 하지 않는다 — 회차 목록 · 상세가 이미 하고,
# 이 창구는 읽기만 한다.
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AbuseType, AnalysisStatus, Speaker, abuse_type_from_label
from app.models.analysis import AIAnalysis
from app.models.case import Case
from app.models.risk_assessment import SessionOverallRiskAssessment, SessionRiskAssessment
from app.models.session import ConsultationSession
from app.models.transcript import TranscriptSegment
from app.services.risk_assessment_service import ai_levels_by_type
from app.schemas.signal_history import (
    SignalHistoryResponse,
    SignalHistorySession,
    SignalHistorySubtype,
    SignalHistoryTopic,
    SignalHistoryType,
)


def build_signal_history(db: Session, case: Case) -> SignalHistoryResponse:
    """사례의 모든 회차를 session_number 오름차순으로, 회차마다 최신 분석 결과와 상담원 판단(회차 전체 · 유형별)을 붙여 돌려준다."""

    sessions = list(
        db.scalars(
            select(ConsultationSession)
            .where(ConsultationSession.case_id == case.id)
            .order_by(ConsultationSession.session_number.asc())
        )
    )
    session_ids = [session.id for session in sessions]

    latest_analysis: Dict[uuid.UUID, AIAnalysis] = {}
    judged: Dict[uuid.UUID, Dict[AbuseType, SessionRiskAssessment]] = defaultdict(dict)
    overall: Dict[uuid.UUID, SessionOverallRiskAssessment] = {}

    if session_ids:
        # 회차별 최신 분석 하나(get_latest_analysis 와 같은 순서: created_at · id 내림차순 첫 행).
        for analysis in db.scalars(
            select(AIAnalysis)
            .where(AIAnalysis.session_id.in_(session_ids))
            .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        ):
            latest_analysis.setdefault(analysis.session_id, analysis)

        for assessment in db.scalars(
            select(SessionRiskAssessment).where(SessionRiskAssessment.session_id.in_(session_ids))
        ):
            judged[assessment.session_id][assessment.abuse_type] = assessment

        # 회차 전체 판단은 회차당 한 행(유니크)이라 한 번에 읽어 session_id 로 찾는다.
        for assessment in db.scalars(
            select(SessionOverallRiskAssessment).where(
                SessionOverallRiskAssessment.session_id.in_(session_ids)
            )
        ):
            overall[assessment.session_id] = assessment

    # 분석이 쓴 전사본의 발화 화자(세부 신호 '보류' 판단용). 완료 분석의 전사본만 한 번에 읽는다.
    speakers: Dict[uuid.UUID, Dict[str, Speaker]] = defaultdict(dict)
    transcript_ids = {
        analysis.transcript_id
        for analysis in latest_analysis.values()
        if analysis.status == AnalysisStatus.COMPLETED and analysis.transcript_id is not None
    }

    if transcript_ids:
        for transcript_id, segment_id, speaker in db.execute(
            select(TranscriptSegment.transcript_id, TranscriptSegment.segment_id, TranscriptSegment.speaker).where(
                TranscriptSegment.transcript_id.in_(transcript_ids)
            )
        ):
            speakers[transcript_id][segment_id] = speaker

    rows = [
        _session_row(
            session,
            latest_analysis.get(session.id),
            judged.get(session.id, {}),
            overall.get(session.id),
            speakers,
        )
        for session in sessions
    ]

    return SignalHistoryResponse(case_id=case.id, sessions=rows)


def _session_row(
    session: ConsultationSession,
    analysis: Optional[AIAnalysis],
    judged: Dict[AbuseType, SessionRiskAssessment],
    overall: Optional[SessionOverallRiskAssessment],
    speakers: Dict[uuid.UUID, Dict[str, Speaker]],
) -> SignalHistorySession:
    completed = analysis is not None and analysis.status == AnalysisStatus.COMPLETED
    result = analysis.result if completed and isinstance(analysis.result, dict) else {}

    # 분석이 끝나지도 않았고 유형별 판단도 없으면 보일 값이 없다 — 빈 목록으로 '분석 전' 을 나타낸다.
    # 회차 전체 판단은 이 규칙에 넣지 않는다(회차 줄에 따로 실린다).
    types = _type_rows(result, judged) if completed or judged else []

    return SignalHistorySession(
        session_id=session.id,
        session_number=session.session_number,
        consulted_at=session.consulted_at,
        status=session.status,
        analysis_status=analysis.status if analysis is not None else None,
        counselor_level=overall.counselor_level if overall is not None else None,
        assessed_at=overall.assessed_at if overall is not None else None,
        types=types,
        topics=_topic_rows(result.get("topic_tags")) if completed else None,
        subtypes=(
            _subtype_rows(result.get("risk_utterances"), speakers.get(analysis.transcript_id, {}))
            if completed and analysis is not None
            else None
        ),
    )


def _subtype_rows(utterances: Any, speakers: Dict[str, Speaker]) -> List[SignalHistorySubtype]:
    """risk_utterances → (유형, 세부 유형)마다 근거 발화 수. 유형 · 세부 유형 · 근거 발화가 없는 항목은 뺀다. 처음 나온 순서."""

    grouped: Dict[tuple, List[str]] = {}

    for item in utterances if isinstance(utterances, list) else []:
        if not isinstance(item, dict):
            continue

        abuse_type = abuse_type_from_label(item.get("abuse_type"))
        subtype = item.get("subtype")
        ids = [sid for sid in item.get("segment_ids") or [] if isinstance(sid, str) and sid]

        if abuse_type is None or not isinstance(subtype, str) or not subtype.strip() or not ids:
            continue

        bucket = grouped.setdefault((abuse_type, subtype.strip()), [])
        bucket.extend(sid for sid in ids if sid not in bucket)

    return [
        SignalHistorySubtype(
            abuse_type=abuse_type,
            subtype=subtype,
            count=len(ids),
            segment_ids=ids,
            pending=all(speakers.get(sid, Speaker.UNKNOWN) == Speaker.UNKNOWN for sid in ids),
        )
        for (abuse_type, subtype), ids in grouped.items()
    ]


def _topic_rows(tags: Any) -> Optional[List[SignalHistoryTopic]]:
    """topic_tags → 회차 줄 topics. 목록이 아니면 null(분류 없음). 주제 이름 · 근거 발화가 없는 항목은 뺀다."""

    if not isinstance(tags, list):
        return None

    rows: List[SignalHistoryTopic] = []

    for tag in tags:
        if not isinstance(tag, dict):
            continue

        topic = tag.get("topic")
        segment_ids = [sid for sid in tag.get("segment_ids") or [] if isinstance(sid, str)]

        if not isinstance(topic, str) or not topic.strip() or not segment_ids:
            continue

        start_ms = tag.get("start_ms")
        quote = tag.get("quote")
        rows.append(
            SignalHistoryTopic(
                topic=topic.strip(),
                count=len(segment_ids),
                segment_ids=segment_ids,
                quote=quote if isinstance(quote, str) else "",
                start_ms=start_ms if isinstance(start_ms, int) and not isinstance(start_ms, bool) else None,
            )
        )

    return rows


def _type_rows(
    result: Dict[str, Any], judged: Dict[AbuseType, SessionRiskAssessment]
) -> List[SignalHistoryType]:
    detected = _detected_by_type(result.get("abuse_signals"))
    # 유형별 AI 단계 읽기는 risk_assessment_service.ai_levels_by_type 하나로(11.1 · 11.2 와 같은 규칙).
    levels = ai_levels_by_type(result.get("severity_ratings"))
    rows: List[SignalHistoryType] = []

    # 네 유형을 늘 같은 순서(enum 순서 = 11절 목록 순서)로 준다.
    for abuse_type in AbuseType:
        assessment = judged.get(abuse_type)
        rows.append(
            SignalHistoryType(
                abuse_type=abuse_type,
                detected=detected.get(abuse_type),
                ai_level=levels.get(abuse_type),
                counselor_level=assessment.counselor_level if assessment is not None else None,
                assessed_at=assessment.assessed_at if assessment is not None else None,
            )
        )

    return rows


def _detected_by_type(signals: Any) -> Dict[AbuseType, Optional[bool]]:
    """abuse_signals → 유형별 detected. 같은 유형은 첫 항목이 정하고, 참/거짓이 아니면 None 이다."""

    found: Dict[AbuseType, Optional[bool]] = {}

    if not isinstance(signals, list):
        return found

    for item in signals:
        if not isinstance(item, dict):
            continue

        abuse_type = abuse_type_from_label(item.get("abuse_type"))

        if abuse_type is None or abuse_type in found:
            continue

        value = item.get("detected")
        found[abuse_type] = value if isinstance(value, bool) else None

    return found
