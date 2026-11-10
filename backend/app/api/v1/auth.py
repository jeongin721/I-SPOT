# /auth
#
# 계정은 관리자가 만들거나(POST /auth/users), 회원가입 신청을 관리자가 승인할 때 생긴다(/auth/signup-requests, 2026-11-02).
# 신청만으로는 계정이 생기지 않는다 — 승인 전에는 로그인할 수 없다(API_CONTRACT 3절 '회원가입').

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Query, Request, status

from app.api.v1.cases import PageQuery, PageSizeQuery
from app.core.config import settings
from app.core.deps import AdminUser, CurrentUser, DbSession, client_ip, user_agent
from app.core.enums import AuditAction, SignupRequestStatus
from app.core.responses import DataResponse, PagedItems, paged
from app.core.security import create_access_token, token_expires_in_seconds
from app.schemas.auth import (
    AuditLogResponse,
    LoginRequest,
    LoginResponse,
    PasswordChangeRequest,
    TemporaryPasswordResponse,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.schemas.common import StorableQueryText
from app.schemas.signup import (
    SignupApproveRequest,
    SignupCodeSendRequest,
    SignupCodeSendResponse,
    SignupCodeVerifyRequest,
    SignupCodeVerifyResponse,
    SignupRequestCreate,
    SignupRequestCreated,
    SignupRequestResponse,
    SignupSettingsResponse,
)
from app.services import account_service, signup_service, user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _temporary_password_response(temporary: str) -> TemporaryPasswordResponse:
    return TemporaryPasswordResponse(
        temporary_password=temporary,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.TEMP_PASSWORD_VALID_HOURS),
    )


@router.post("/login", response_model=DataResponse[LoginResponse])
def login(
    payload: LoginRequest,
    request: Request,
    db: DbSession,
) -> DataResponse[LoginResponse]:
    user = user_service.authenticate(
        db,
        payload.email,
        payload.password,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )

    token = create_access_token(
        subject=str(user.id),
        role=user.role.value,
        token_version=user.token_version,
    )

    return DataResponse(
        data=LoginResponse(
            access_token=token,
            token_type="bearer",
            expires_in=token_expires_in_seconds(),
            user=UserResponse.model_validate(user),
        )
    )


@router.get("/me", response_model=DataResponse[UserResponse])
def get_me(current_user: CurrentUser) -> DataResponse[UserResponse]:
    return DataResponse(data=UserResponse.model_validate(current_user))


@router.post(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="내 비밀번호 변경",
)
def change_my_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    user_service.change_password(
        db,
        current_user,
        payload,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )


@router.post(
    "/users",
    response_model=DataResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="계정 생성 (관리자 전용)",
)
def create_user(
    payload: UserCreateRequest,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[UserResponse]:
    user = user_service.create_user(db, payload, actor=admin)

    return DataResponse(data=UserResponse.model_validate(user))


@router.get(
    "/users",
    response_model=DataResponse[List[UserResponse]],
    summary="계정 목록 (관리자 전용)",
)
def list_users(db: DbSession, _: AdminUser) -> DataResponse[List[UserResponse]]:
    users = user_service.list_users(db)

    return DataResponse(data=[UserResponse.model_validate(user) for user in users])


@router.patch(
    "/users/{user_id}",
    response_model=DataResponse[UserResponse],
    summary="계정 수정 — 활성화 · 비활성화, 역할, 이름 (관리자 전용)",
)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[UserResponse]:
    user = account_service.get_user_or_404(db, user_id)
    updated = account_service.update_user(db, admin, user, payload)

    return DataResponse(data=UserResponse.model_validate(updated))


@router.post(
    "/users/{user_id}/password-reset",
    response_model=DataResponse[TemporaryPasswordResponse],
    summary="임시 비밀번호 재발급 (관리자 전용)",
)
def reset_password(
    user_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[TemporaryPasswordResponse]:
    user = account_service.get_user_or_404(db, user_id)
    temporary = account_service.reset_password(db, admin, user)

    return DataResponse(data=_temporary_password_response(temporary))


@router.post(
    "/users/{user_id}/unlock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그인 실패 잠금 해제 (관리자 전용)",
)
def unlock_user(
    user_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
) -> None:
    user = account_service.get_user_or_404(db, user_id)
    account_service.unlock(db, admin, user)


@router.post(
    "/users/{user_id}/reactivate",
    response_model=DataResponse[TemporaryPasswordResponse],
    summary="휴면 해제 + 임시 비밀번호 재발급 (관리자 전용)",
)
def reactivate_user(
    user_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[TemporaryPasswordResponse]:
    user = account_service.get_user_or_404(db, user_id)
    temporary = account_service.reactivate(db, admin, user)

    return DataResponse(data=_temporary_password_response(temporary))


@router.post(
    "/users/{user_id}/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="강제 로그아웃 — 발급된 Token 전부 무효 (관리자 전용)",
)
def logout_all(
    user_id: uuid.UUID,
    db: DbSession,
    admin: AdminUser,
) -> None:
    user = account_service.get_user_or_404(db, user_id)
    account_service.logout_all(db, admin, user)


@router.get(
    "/audit-logs",
    response_model=DataResponse[PagedItems[AuditLogResponse]],
    summary="감사 로그 조회 (관리자 전용)",
)
def list_audit_logs(
    db: DbSession,
    _: AdminUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    action: Optional[AuditAction] = None,
    # 형식으로 이미 막히지만, 글자 쿼리는 모두 같은 검사를 붙인다(tests/test_request_model_guard.py).
    # StorableQueryText 는 Query(...) 뒤에 둔다(common.py). 앞에 두면 OpenAPI 에서 pattern 이 빠진다.
    status_filter: Annotated[
        Optional[str], Query(alias="status", pattern="^(SUCCESS|FAILURE)$"), StorableQueryText
    ] = None,
    actor_id: Annotated[Optional[uuid.UUID], Query(description="행동한 사용자")] = None,
    since: Annotated[Optional[datetime], Query(description="이 시각부터(포함). ISO 8601, 시간대 표시 없으면 UTC")] = None,
    until: Annotated[Optional[datetime], Query(description="이 시각까지(포함). ISO 8601, 시간대 표시 없으면 UTC")] = None,
) -> DataResponse[PagedItems[AuditLogResponse]]:
    rows, total = account_service.list_audit_logs(
        db,
        offset=(page - 1) * page_size,
        limit=page_size,
        action=action,
        status=status_filter,
        actor_id=actor_id,
        since=since,
        until=until,
    )

    items = []

    for row, actor_name in rows:
        item = AuditLogResponse.model_validate(row)
        item.actor_name = actor_name
        items.append(item)

    return DataResponse(data=paged(items, total, page, page_size))


# =========================================================
# 회원가입 (이메일 인증번호 → 대기 신청 → 관리자 승인, 2026-11-02, API_CONTRACT 3절 '회원가입')
# =========================================================
# 공개 창구 셋(보내기 · 확인 · 신청)은 SIGNUP_ENABLED 가 꺼져 있으면 503 이다. 설정 조회와 관리자 창구는 늘 동작한다.

def _signup_request_response(
    request, decided_by_name: Optional[str] = None
) -> SignupRequestResponse:
    item = SignupRequestResponse.model_validate(request)
    item.expires_at = signup_service.expires_at(request)
    item.decided_by_name = decided_by_name

    return item


@router.get(
    "/signup-requests/settings",
    response_model=DataResponse[SignupSettingsResponse],
    summary="회원가입 설정 — 켜짐 여부 · 받는 이메일 도메인(로그인 없이)",
)
def get_signup_settings() -> DataResponse[SignupSettingsResponse]:
    return DataResponse(
        data=SignupSettingsResponse(
            enabled=settings.SIGNUP_ENABLED,
            allowed_email_domains=list(settings.SIGNUP_ALLOWED_EMAIL_DOMAINS),
        )
    )


@router.post(
    "/signup-requests/send-code",
    response_model=DataResponse[SignupCodeSendResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="회원가입 인증번호 보내기(로그인 없이)",
)
def send_signup_code(
    payload: SignupCodeSendRequest,
    request: Request,
    db: DbSession,
) -> DataResponse[SignupCodeSendResponse]:
    ip_address, agent = client_ip(request), user_agent(request)
    result = signup_service.send_code(db, payload.email, ip_address=ip_address, user_agent=agent)

    # 메일은 전용 스레드에 넣고 바로 답한다. 계정이 이미 있는 이메일은 보내지 않는데(result.mail 이 None), 그 차이가 이 요청과
    # 같은 연결의 다음 요청 시간에 섞이지 않게 BackgroundTasks 를 쓰지 않는다(signup_service 의 '메일 보내기' 머리말).
    signup_service.queue_code_mail(result, ip_address=ip_address, user_agent=agent)

    return DataResponse(
        data=SignupCodeSendResponse(
            resend_after_seconds=int(signup_service.RESEND_INTERVAL.total_seconds()),
            expires_in_seconds=int(signup_service.CODE_TTL.total_seconds()),
        )
    )


@router.post(
    "/signup-requests/verify-code",
    response_model=DataResponse[SignupCodeVerifyResponse],
    summary="회원가입 인증번호 확인 — 맞으면 확인 토큰(로그인 없이)",
)
def verify_signup_code(
    payload: SignupCodeVerifyRequest,
    request: Request,
    db: DbSession,
) -> DataResponse[SignupCodeVerifyResponse]:
    result = signup_service.verify_code(
        db,
        payload.email,
        payload.code,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )

    return DataResponse(
        data=SignupCodeVerifyResponse(
            verification_token=result.token,
            expires_in_seconds=result.expires_in_seconds,
        )
    )


@router.post(
    "/signup-requests",
    response_model=DataResponse[SignupRequestCreated],
    status_code=status.HTTP_201_CREATED,
    summary="회원가입 대기 신청 — 관리자 승인 뒤 로그인(로그인 없이)",
)
def create_signup_request(
    payload: SignupRequestCreate,
    request: Request,
    db: DbSession,
) -> DataResponse[SignupRequestCreated]:
    created = signup_service.submit_request(
        db,
        payload.verification_token,
        payload.name,
        payload.password,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )

    return DataResponse(data=SignupRequestCreated(status=created.status))


@router.get(
    "/signup-requests",
    response_model=DataResponse[PagedItems[SignupRequestResponse]],
    summary="회원가입 신청 목록 (관리자 전용)",
)
def list_signup_requests(
    db: DbSession,
    _: AdminUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    status_filter: Annotated[
        SignupRequestStatus, Query(alias="status", description="기본 PENDING")
    ] = SignupRequestStatus.PENDING,
) -> DataResponse[PagedItems[SignupRequestResponse]]:
    rows, total = signup_service.list_requests(
        db,
        status=status_filter,
        offset=(page - 1) * page_size,
        limit=page_size,
    )

    items = [_signup_request_response(row, decided_by_name) for row, decided_by_name in rows]

    return DataResponse(data=paged(items, total, page, page_size))


@router.post(
    "/signup-requests/{request_id}/approve",
    response_model=DataResponse[SignupRequestResponse],
    summary="회원가입 승인 — 역할을 정해 계정 생성 (관리자 전용)",
)
def approve_signup_request(
    request_id: uuid.UUID,
    payload: SignupApproveRequest,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[SignupRequestResponse]:
    approved = signup_service.approve(
        db,
        admin,
        request_id,
        payload.role,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )

    return DataResponse(data=_signup_request_response(approved, admin.name))


@router.post(
    "/signup-requests/{request_id}/reject",
    response_model=DataResponse[SignupRequestResponse],
    summary="회원가입 거절 (관리자 전용)",
)
def reject_signup_request(
    request_id: uuid.UUID,
    request: Request,
    db: DbSession,
    admin: AdminUser,
) -> DataResponse[SignupRequestResponse]:
    rejected = signup_service.reject(
        db,
        admin,
        request_id,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    )

    return DataResponse(data=_signup_request_response(rejected, admin.name))
