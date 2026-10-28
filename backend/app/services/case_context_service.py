# AI 분석에 넘기는 사례 정보(case_context).
#
# 설계: I-SPOT_DOCS/docs/PROPOSAL_case_context_analysis.md §3(합의 2026-10-28) · PROPOSAL_ai_suggestions_case_context.md §1.
# analysis_service 가 분석 작업에서 만들어, case_context 를 받는 어댑터(ModelingAIAdapter)에만 키워드로 넘긴다.
# STT Contract(Transcript payload)는 바꾸지 않는다.
#
# 넘기는 것(OpenAI 까지 갈 수 있는 값이라 최소로):
#   child_age_band   출생연도로 센 나이를 나이대로만(정확한 나이 · 출생연도는 넘기지 않음)
#   child_gender · guardian_type · intake_child_traits · intake_family_situations(서식 4 단어)
#   previous_session 같은 사례에서 이 회차보다 앞선 '승인 완료' 회차 중 가장 최근 것의 요약 4칸 문장(상담원 확정본)
# 넘기지 않는 것: 아동 가명(child_alias) · 사건번호 · 제목 · 메모 · 보호자 메모(guardian_note) · 상담원 정보.
# 지난 회차 문장은 상담원이 쓴 글이라 이름이 섞일 수 있다 — AI 쪽이 원문과 같은 마스킹을 거쳐 보낸다(case_context.py).

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ReviewStatus, SessionStatus
from app.models.case import Case
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary

#: (시작 나이, 끝 나이, 이름). 끝이 None 이면 그 나이 이상.
AGE_BANDS = (
    (0, 5, "만 0~5세"),
    (6, 9, "만 6~9세"),
    (10, 13, "만 10~13세"),
    (14, 17, "만 14~17세"),
    (18, None, "만 18세 이상"),
)

ASSESSMENT_KEYS = ("safety_changes", "strengths_resources", "safety_risks", "desired_changes")


def age_band(birth_year: Optional[int], this_year: int) -> Optional[str]:
    """출생연도 → 나이대(연도 기준이라 만 나이와 한 살 다를 수 있다). 모르거나 맞지 않으면 None."""

    if birth_year is None:
        return None

    age = this_year - birth_year

    if age < 0:
        return None

    for start, end, label in AGE_BANDS:
        if age >= start and (end is None or age <= end):
            return label

    return None


def _previous_session(db: Session, session: ConsultationSession) -> Optional[Dict[str, Any]]:
    """이 회차보다 앞선 승인 완료 회차 중 가장 최근 것의 확정 요약 4칸. 없으면 None."""

    previous = db.scalar(
        select(ConsultationSession)
        .where(
            ConsultationSession.case_id == session.case_id,
            ConsultationSession.session_number < session.session_number,
            ConsultationSession.status == SessionStatus.APPROVED,
        )
        .order_by(ConsultationSession.session_number.desc())
        .limit(1)
    )

    if previous is None:
        return None

    summary = db.scalar(
        select(ConsultationSummary).where(
            ConsultationSummary.session_id == previous.id,
            ConsultationSummary.status == ReviewStatus.APPROVED,
        )
    )
    stored = summary.assessment if summary is not None and isinstance(summary.assessment, dict) else {}
    assessment = {}

    for key in ASSESSMENT_KEYS:
        field = stored.get(key)
        text = field.get("text") if isinstance(field, dict) else None
        if isinstance(text, str) and text.strip():
            assessment[key] = text.strip()

    return {
        "session_label": f"{previous.session_number}회차",
        "consulted_on": previous.consulted_at.date().isoformat() if previous.consulted_at else None,
        "assessment": assessment,
    }


def build_case_context(
    db: Session,
    session: ConsultationSession,
    *,
    now: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """회차의 사례 정보. 사례를 찾지 못하면 None."""

    case = db.get(Case, session.case_id)

    if case is None:
        return None

    this_year = (now or datetime.now(timezone.utc)).year

    return {
        "child_age_band": age_band(case.child_birth_year, this_year),
        "child_gender": case.child_gender,
        "guardian_type": case.guardian_type.value if case.guardian_type else None,
        "intake_child_traits": list(case.intake_child_traits or []),
        "intake_family_situations": list(case.intake_family_situations or []),
        "previous_session": _previous_session(db, session),
    }
