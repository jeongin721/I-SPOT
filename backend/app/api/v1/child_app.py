# 아이 앱(콩콩) API(API_CONTRACT 24절).
#   /child-app/*          아이 기기. 상담사 로그인이 아니라 기기 토큰으로 인증한다.
#   /cases/{id}/child-app 상담사 웹. 담당 상담사 · 관리자만.

import uuid
from datetime import date
from typing import Annotated, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.deps import AdminUser, CurrentUser, DbSession, bearer_scheme, client_ip
from app.core.errors import ErrorCode, bad_request, unauthorized
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
    ChildAppStats,
    ChildAppInviteResponse,
    ChildHomeResponse,
    ChildLinkRequest,
    ChildLinkResponse,
    ChildMoodRequest,
    ChildNoteRequest,
    ChildScheduleRequest,
    ChildSessionQuestions,
    ChildSessionQuestionUpdateRequest,
    ChildSilentDaysRequest,
    ChildOpenAlert,
    ChildQuestionSendRequest,
    ChildRecentAlert,
    ChildWelfareCheckRequest,
)
from app.services import child_app_ai_service, child_app_service, child_session_question_service, push_service
from app.services.access import get_case_or_404

_enabled = [Depends(child_app_service.ensure_enabled)]
device_router = APIRouter(prefix="/child-app", tags=["child-app"], dependencies=_enabled)
case_router = APIRouter(prefix="/cases", tags=["child-app"], dependencies=_enabled)
staff_router = APIRouter(prefix="/child-app-alerts", tags=["child-app"], dependencies=_enabled)
list_router = APIRouter(prefix="/child-app-cases", tags=["child-app"], dependencies=_enabled)
stats_router = APIRouter(prefix="/child-app-stats", tags=["child-app"], dependencies=_enabled)


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


@device_router.post("/unlink", status_code=status.HTTP_204_NO_CONTENT, summary="아이 앱 연결 해지(기기에서)")
def unlink_device(request: Request, db: DbSession, link: CurrentChildLink) -> None:
    child_app_service.unlink_device(db, link, client_ip(request))


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
def send_alert(db: DbSession, link: CurrentChildLink, background: BackgroundTasks) -> DataResponse[ChildAlertReceived]:
    case_id = link.case_id
    alert_id = child_app_service.send_alert(db, link)

    # 새 긴급 알림이면 담당 상담사 폰에 알린다(응답을 보낸 뒤 — 아이 쪽은 기다리지 않는다).
    if alert_id is not None:
        background.add_task(push_service.notify_child_alert, case_id, alert_id)

    return DataResponse(data=ChildAlertReceived())


@device_router.post("/moods", status_code=status.HTTP_204_NO_CONTENT, summary="지금 기분 기록하기")
def record_mood(payload: ChildMoodRequest, db: DbSession, link: CurrentChildLink) -> None:
    child_app_service.record_mood(db, link, payload.mood, payload.why)


@device_router.post("/notes", status_code=status.HTTP_204_NO_CONTENT, summary="선생님께 메시지 보내기")
def send_note(payload: ChildNoteRequest, db: DbSession, link: CurrentChildLink) -> None:
    child_app_service.send_note(db, link, payload.text, payload.chip)


@device_router.post("/schedule-requests", status_code=status.HTTP_204_NO_CONTENT, summary="다음 상담 참석이 어려워요")
def request_reschedule(payload: ChildScheduleRequest, db: DbSession, link: CurrentChildLink) -> None:
    child_app_service.request_reschedule(db, link, payload.reason, payload.etc)


@stats_router.get("", response_model=DataResponse[ChildAppStats], summary="아이 앱 응답률(관리자)")
def child_app_stats(date_from: date, date_to: date, db: DbSession, _: AdminUser) -> DataResponse[ChildAppStats]:
    if date_to < date_from:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "기간의 끝이 시작보다 앞입니다.")

    return DataResponse(data=child_app_service.stats(db, date_from, date_to))


@list_router.get("", response_model=DataResponse[List[ChildAppCaseRow]], summary="아이 연계 목록")
def list_child_app_cases(db: DbSession, current_user: CurrentUser) -> DataResponse[List[ChildAppCaseRow]]:
    return DataResponse(data=child_app_service.list_cases(db, current_user))


@staff_router.get("/recent", response_model=DataResponse[List[ChildRecentAlert]], summary="관리자 홈 긴급 알림 현황")
def list_recent_alerts(db: DbSession, current_user: AdminUser) -> DataResponse[List[ChildRecentAlert]]:
    return DataResponse(data=child_app_service.recent_urgent_alerts(db, current_user))


@case_router.post("/{case_id}/child-app/welfare-checks", status_code=status.HTTP_204_NO_CONTENT, summary="장기 무응답 안부 연락 처리")
def record_welfare_check(
    case_id: uuid.UUID,
    payload: ChildWelfareCheckRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    child_app_service.record_welfare_check(db, case, current_user, payload.status, payload.note, client_ip(request))


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


@case_router.put("/{case_id}/child-app/silent-days", status_code=status.HTTP_204_NO_CONTENT, summary="응답 상태 기준 일수")
def set_silent_days(
    case_id: uuid.UUID, payload: ChildSilentDaysRequest, request: Request, db: DbSession, current_user: CurrentUser
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    child_app_service.set_silent_days(db, case, current_user, payload.days, client_ip(request))


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


@case_router.delete("/{case_id}/child-app/link", status_code=status.HTTP_204_NO_CONTENT, summary="아이 앱 연결 해지(상담사)")
def unlink_case_child_app(
    case_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """아이 상세 '해지하기'. 담당 상담사만. 연결이 없으면 204(재시도 안전)."""

    case = get_case_or_404(db, case_id, current_user)
    child_app_service.unlink_by_counselor(db, case, current_user, client_ip(request))


@case_router.post("/{case_id}/child-app/question-sets", status_code=status.HTTP_204_NO_CONTENT)
def send_questions(
    case_id: uuid.UUID,
    payload: ChildQuestionSendRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    case = get_case_or_404(db, case_id, current_user)
    child_app_service.send_questions(
        db, case, current_user, payload.question_ids, client_ip(request), deliver=payload.deliver
    )


@case_router.delete("/{case_id}/child-app/question-sets/{question_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_question_set(
    case_id: uuid.UUID,
    question_set_id: uuid.UUID,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """발송 예약 취소(예약 시각 전에만)."""

    case = get_case_or_404(db, case_id, current_user)
    child_app_service.cancel_question_set(db, case, current_user, question_set_id, client_ip(request))


@case_router.post("/{case_id}/child-app/session-questions", response_model=DataResponse[ChildSessionQuestions])
def create_session_questions(
    case_id: uuid.UUID, db: DbSession, current_user: CurrentUser, regenerate: bool = False
) -> DataResponse[ChildSessionQuestions]:
    """가장 최근 분석 회차로 아이 앱 맞춤 질문 초안을 만든다(있으면 그대로, regenerate 면 새로)."""

    case = get_case_or_404(db, case_id, current_user)

    return DataResponse(
        data=child_session_question_service.create_draft(db, case, current_user, regenerate=regenerate)
    )


@case_router.patch(
    "/{case_id}/child-app/session-questions/{question_id}", response_model=DataResponse[ChildSessionQuestions]
)
def update_session_question(
    case_id: uuid.UUID,
    question_id: str,
    payload: ChildSessionQuestionUpdateRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[ChildSessionQuestions]:
    """맞춤 질문 문장 · 보기 · 살펴볼 답 고치기(가장 최근 분석 회차 초안만)."""

    case = get_case_or_404(db, case_id, current_user)

    return DataResponse(
        data=child_session_question_service.update_question(
            db, case, current_user, question_id, payload.text, payload.options, client_ip(request)
        )
    )


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
