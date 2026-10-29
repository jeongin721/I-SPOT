# /sessions/{session_id}/followup-questions — 승인한 추가 질문 목록(18절)

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.followup_question import FollowupQuestionsResponse, FollowupQuestionsSaveRequest
from app.services import followup_question_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["followup-questions"])


@router.get(
    "/{session_id}/followup-questions",
    response_model=DataResponse[FollowupQuestionsResponse],
)
def get_followup_questions(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupQuestionsResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = followup_question_service.get_row(db, session.id)

    return DataResponse(data=followup_question_service.to_response(session.id, row))


@router.put(
    "/{session_id}/followup-questions",
    response_model=DataResponse[FollowupQuestionsResponse],
)
def save_followup_questions(
    session_id: uuid.UUID,
    payload: FollowupQuestionsSaveRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[FollowupQuestionsResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = followup_question_service.save_questions(db, session, current_user, payload)

    return DataResponse(data=followup_question_service.to_response(session.id, row))
