# 아이 앱(콩콩) API(API_CONTRACT 24절).
#   /child-app/*          아이 기기. 상담사 로그인이 아니라 기기 토큰으로 인증한다.
#   /cases/{id}/child-app 상담사 웹. 담당 상담사 · 관리자만.

import uuid
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.deps import CurrentUser, DbSession, bearer_scheme, client_ip
from app.core.errors import unauthorized
from app.core.responses import DataResponse
from app.models.child_app import ChildAppLink
from app.schemas.child_app import (
    ChildAiApprovalRequest,
    ChildAiDraftResponse,
    ChildAiNoteUpdateRequest,
    ChildAiQuestionUpdateRequest,
    ChildAnswersRequest,
    ChildAlertReceived,
    ChildAnswersResponse,
    ChildAppCaseResponse,
    ChildAppCaseRow,
    ChildAppInviteResponse,
    ChildHomeResponse,
    ChildLinkRequest,
    ChildLinkResponse,
    ChildOpenAlert,
    ChildQuestionSendRequest,
)
from app.services import child_app_ai_service, child_app_service
from app.services.access import get_case_or_404

_enabled = [Depends(child_app_service.ensure_enabled)]
device_router = APIRouter(prefix="/child-app", tags=["child-app"], dependencies=_enabled)
case_router = APIRouter(prefix="/cases", tags=["child-app"], dependencies=_enabled)
staff_router = APIRouter(prefix="/child-app-alerts", tags=["child-app"], dependencies=_enabled)
list_router = APIRouter(prefix="/child-app-cases", tags=["child-app"], dependencies=_enabled)


def _current_link(
    db: DbSession,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)] = None,
) -> ChildAppLink:
    if credentials is None or not credentials.credentials:
        raise unauthorized("앱을 다시 연결해 주세요.")

    return child_app_service.get_link_by_token(db, credentials.credentials)


CurrentChildLink = Annotated[ChildAppLink, Depends(_current_link)]


@device_router.post("/link", response_model=DataResponse[ChildLinkResponse])
def link_device(payload: ChildLinkRequest, request: Request, db: DbSession) -> DataResponse[ChildLinkResponse]:
    token = child_app_service.link_device(db, payload.code, client_ip(request))

    return DataResponse(data=ChildLinkResponse(device_token=token))


@device_router.get("/home", response_model=DataResponse[ChildHomeResponse])
def get_home(db: DbSession, link: CurrentChildLink) -> DataResponse[ChildHomeResponse]:
    return DataResponse(data=child_app_service.get_home(db, link))


@device_router.post(
    "/question-sets/{question_set_id}/answers",
    response_model=DataResponse[ChildAnswersResponse],
)
def submit_answers(
    question_set_id: uuid.UUID,
    payload: ChildAnswersRequest,
    db: DbSession,
    link: CurrentChildLink,
) -> DataResponse[ChildAnswersResponse]:
    child_app_service.submit_answers(db, link, question_set_id, payload.answers)

    return DataResponse(data=ChildAnswersResponse(ticket_awarded=1))


@device_router.post("/alerts", response_model=DataResponse[ChildAlertReceived])
def send_alert(db: DbSession, link: CurrentChildLink) -> DataResponse[ChildAlertReceived]:
    child_app_service.send_alert(db, link)

    return DataResponse(data=ChildAlertReceived())


@list_router.get("", response_model=DataResponse[List[ChildAppCaseRow]], summary="아이 연계 목록")
def list_child_app_cases(db: DbSession, current_user: CurrentUser) -> DataResponse[List[ChildAppCaseRow]]:
    return DataResponse(data=child_app_service.list_cases(db, current_user))


@staff_router.get("/open", response_model=DataResponse[List[ChildOpenAlert]])
def list_open_alerts(db: DbSession, current_user: CurrentUser) -> DataResponse[List[ChildOpenAlert]]:
    return DataResponse(data=child_app_service.list_open_alerts(db, current_user))


@case_router.post("/{case_id}/child-app/alerts/{alert_id}/ack", status_code=status.HTTP_204_NO_CONTENT)
def acknowledge_alert(
    case_id: uuid.UUID,
    alert_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    child_app_service.acknowledge_alert(db, case, current_user, alert_id, client_ip(request))


@case_router.get("/{case_id}/child-app", response_model=DataResponse[ChildAppCaseResponse])
def get_case_child_app(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildAppCaseResponse]:
    case = get_case_or_404(db, case_id, current_user)

    return DataResponse(data=child_app_service.get_case_view(db, case, current_user))


@case_router.post(
    "/{case_id}/child-app/invite",
    response_model=DataResponse[ChildAppInviteResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    case_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildAppInviteResponse]:
    case = get_case_or_404(db, case_id, current_user)
    result = child_app_service.create_invite(db, case, current_user, client_ip(request))

    return DataResponse(data=ChildAppInviteResponse(**result))


@case_router.post("/{case_id}/child-app/question-sets", status_code=status.HTTP_204_NO_CONTENT)
def send_questions(
    case_id: uuid.UUID,
    payload: ChildQuestionSendRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    child_app_service.send_questions(db, case, current_user, payload.question_ids, client_ip(request))


@case_router.post("/{case_id}/child-app/ai-draft", response_model=DataResponse[ChildAiDraftResponse])
def create_ai_draft(case_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[ChildAiDraftResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = child_app_ai_service.create_draft(db, case, current_user)

    return DataResponse(data=child_app_ai_service.to_response(db, row))


@case_router.patch(
    "/{case_id}/child-app/ai-draft/{draft_id}/notes/{question_id}",
    response_model=DataResponse[ChildAiDraftResponse],
)
def update_ai_note(
    case_id: uuid.UUID,
    draft_id: uuid.UUID,
    question_id: str,
    payload: ChildAiNoteUpdateRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildAiDraftResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = child_app_ai_service.update_note(db, case, current_user, draft_id, question_id, payload.text, client_ip(request))

    return DataResponse(data=child_app_ai_service.to_response(db, row))


@case_router.patch(
    "/{case_id}/child-app/ai-draft/{draft_id}/questions/{question_id}",
    response_model=DataResponse[ChildAiDraftResponse],
)
def update_ai_question(
    case_id: uuid.UUID,
    draft_id: uuid.UUID,
    question_id: str,
    payload: ChildAiQuestionUpdateRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildAiDraftResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = child_app_ai_service.update_question(db, case, current_user, draft_id, question_id, payload, client_ip(request))

    return DataResponse(data=child_app_ai_service.to_response(db, row))


@case_router.put(
    "/{case_id}/child-app/ai-draft/{draft_id}/questions/{question_id}/approval",
    response_model=DataResponse[ChildAiDraftResponse],
)
def set_ai_question_approval(
    case_id: uuid.UUID,
    draft_id: uuid.UUID,
    question_id: str,
    payload: ChildAiApprovalRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildAiDraftResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = child_app_ai_service.set_approval(db, case, current_user, draft_id, question_id, payload.approved, client_ip(request))

    return DataResponse(data=child_app_ai_service.to_response(db, row))
