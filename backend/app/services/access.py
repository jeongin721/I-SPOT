# Case/Session 조회 + 권한 검사 공통 helper.
#
# counselor 는 담당 Case 만 접근할 수 있고, admin 은 전체를 접근할 수 있다.
# 모든 하위 리소스(Audio/Transcript/Analysis/Summary/Document)는
# 반드시 이 helper 를 통해 Session 을 얻은 뒤 처리한다.

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ErrorCode, forbidden, not_found
from app.models.case import Case
from app.models.session import ConsultationSession
from app.models.user import User


def ensure_case_access(user: User, case: Case) -> None:
    if user.is_admin:
        return

    if case.counselor_id != user.id:
        raise forbidden("담당 상담사만 접근할 수 있는 사례입니다.")


def get_case_or_404(db: Session, case_id: uuid.UUID, user: User) -> Case:
    case = db.scalar(select(Case).where(Case.id == case_id))

    if case is None:
        raise not_found(ErrorCode.CASE_NOT_FOUND, "사례를 찾을 수 없습니다.")

    ensure_case_access(user, case)

    return case


def get_session_or_404(
    db: Session,
    session_id: uuid.UUID,
    user: User,
) -> ConsultationSession:
    session = db.scalar(
        select(ConsultationSession)
        .options(selectinload(ConsultationSession.case))
        .where(ConsultationSession.id == session_id)
    )

    if session is None:
        raise not_found(ErrorCode.SESSION_NOT_FOUND, "상담 Session 을 찾을 수 없습니다.")

    ensure_case_access(user, session.case)

    return session


def get_session_for_worker(db: Session, session_id: uuid.UUID) -> ConsultationSession:
    """
    Background worker 전용 조회.

    권한 검사는 요청 시점에 이미 완료되었으므로 여기서는 존재 여부만 확인한다.
    """

    session = db.scalar(
        select(ConsultationSession).where(ConsultationSession.id == session_id)
    )

    if session is None:
        raise not_found(ErrorCode.SESSION_NOT_FOUND, "상담 Session 을 찾을 수 없습니다.")

    return session
