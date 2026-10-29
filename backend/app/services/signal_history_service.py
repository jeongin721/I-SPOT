# 사례 단위 신호 이력 — GET /cases/{case_id}/signal-history (API_CONTRACT 4절, 2026-10-28).
#
# 화면(회차별 추이 · 상담 이력의 회차 카드 신호 · 세부 신호 행렬)이 회차마다 GET …/analysis 와
# GET …/risk-assessments 를 부르면 요청이 회차 수 × 2 로 늘어난다. 여기서 한 번에 모은다
# (이경진 님 제안 2026-10-27, PROPOSAL_signal_history_api.md). AI 를 새로 돌리지 않고 저장된 값만 읽는다.
#
# 값 규칙은 기존 창구와 같다.
#  - detected: 최신 분석 결과 abuse_signals[].detected(같은 유형 첫 항목, 참/거짓만, 아니면 None)
#  - ai_level: severity_ratings[].level 1~5 — risk_assessment_service.ai_level_for 와 같은 규칙(같은 유형 첫 항목이 정함)
#  - counselor_level · assessed_at: session_risk_assessments(11절)
# 처리 중 회기의 작업 유실 마감(expire_stale_processing)은 여기서 하지 않는다 — 회차 목록 · 상세가 이미 하고,
# 이 창구는 읽기만 한다.
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AbuseType, AnalysisStatus, abuse_type_from_label
from app.models.analysis import AIAnalysis
from app.models.case import Case
from app.models.risk_assessment import SessionRiskAssessment
from app.models.session import ConsultationSession
from app.schemas.signal_history import (
    SignalHistoryResponse,
    SignalHistorySession,
    SignalHistoryType,
)


def build_signal_history(db: Session, case: Case) -> SignalHistoryResponse:
    """사례의 모든 회차를 session_number 오름차순으로, 회차마다 최신 분석 결과와 상담원 판단을 붙여 돌려준다."""

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

    rows = [
        _session_row(session, latest_analysis.get(session.id), judged.get(session.id, {}))
        for session in sessions
    ]

    return SignalHistoryResponse(case_id=case.id, sessions=rows)


def _session_row(
    session: ConsultationSession,
    analysis: Optional[AIAnalysis],
    judged: Dict[AbuseType, SessionRiskAssessment],
) -> SignalHistorySession:
    completed = analysis is not None and analysis.status == AnalysisStatus.COMPLETED
    result = analysis.result if completed and isinstance(analysis.result, dict) else {}

    # 분석이 끝나지도 않았고 판단도 없으면 보일 값이 없다 — 빈 목록으로 '분석 전' 을 나타낸다.
    types = _type_rows(result, judged) if completed or judged else []

    return SignalHistorySession(
        session_id=session.id,
        session_number=session.session_number,
        consulted_at=session.consulted_at,
        status=session.status,
        analysis_status=analysis.status if analysis is not None else None,
        types=types,
    )


def _type_rows(
    result: Dict[str, Any], judged: Dict[AbuseType, SessionRiskAssessment]
) -> List[SignalHistoryType]:
    detected = _detected_by_type(result.get("abuse_signals"))
    levels = _ai_level_by_type(result.get("severity_ratings"))
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


def _ai_level_by_type(ratings: Any) -> Dict[AbuseType, Optional[int]]:
    """severity_ratings → 유형별 level(1~5). risk_assessment_service.ai_level_for 와 같은 규칙이다."""

    found: Dict[AbuseType, Optional[int]] = {}

    if not isinstance(ratings, list):
        return found

    for rating in ratings:
        if not isinstance(rating, dict):
            continue

        abuse_type = abuse_type_from_label(rating.get("major_type"))

        if abuse_type is None or abuse_type in found:
            continue

        level = rating.get("level")

        # bool 은 int 의 하위 형이라 따로 막는다(True 가 1 로 읽히지 않게).
        if isinstance(level, int) and not isinstance(level, bool) and 1 <= level <= 5:
            found[abuse_type] = level
        else:
            found[abuse_type] = None

    return found
