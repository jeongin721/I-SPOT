# /sessions/{session_id}/followup-suggestions — 다음 상담 체크리스트(추가 확인 · 질문 화면). API_CONTRACT.md 19절.
#
# AI 분석이 끝나면 Backend 가 같은 백그라운드 작업에서 만들어 저장한다(followup_service.generate_after_analysis).
# 여기서는 가장 최근 행을 읽고, 상담사가 누른 '다시 만들기'를 받는다. AI 제안이며 상담사가 확인 · 승인한다.

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.followup import FollowupSuggestionResponse
from app.services import followup_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["followup"])


@router.get(
    "/{session_id}/followup-suggestions",
    response_model=DataResponse[Optional[FollowupSuggestionResponse]],
    summary="다음 상담 체크리스트 조회(가장 최근 행, Polling)",
)
def get_followup_suggestions(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[Optional[FollowupSuggestionResponse]]:
    """가장 최근 행 하나를 준다. 아직 만들기 전이면 `data: null`(정상 상태라 404 가 아니다).

    만드는 중이면 `status: PROCESSING` 이고, 실패하면 `status: FAILED` 와 `error` 가 온다.
    """

    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=followup_service.get_latest_response(db, session))


@router.post(
    "/{session_id}/followup-suggestions",
    response_model=DataResponse[FollowupSuggestionResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="다음 상담 체크리스트 다시 만들기",
)
def request_followup_suggestions(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> DataResponse[FollowupSuggestionResponse]:
    """AI 분석이 끝난 회차에서만 받는다(아니면 409). 꺼져 있으면 503 FOLLOWUP_DISABLED.

    이미 만드는 중이면 새로 시작하지 않고 그 행을 돌려준다.
    """

    session = get_session_or_404(db, session_id, current_user)
    row, created = followup_service.request_generation(db, session)

    if created:
        background_tasks.add_task(followup_service.process_followup, row.id)

    return DataResponse(data=followup_service.to_response(row))
