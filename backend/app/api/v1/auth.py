# /auth
#
# 자유 회원가입 endpoint 는 제공하지 않는다. 계정 생성은 관리자 전용이다.

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Query, Request, status

from app.api.v1.cases import PageQuery, PageSizeQuery
from app.core.config import settings
from app.core.deps import AdminUser, CurrentUser, DbSession, client_ip, user_agent
from app.core.enums import AuditAction
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
from app.services import account_service, user_service

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
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    user_service.change_password(db, current_user, payload)


@router.post(
    "/users",
    response_model=DataResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="계정 생성 (관리자 전용)",
)
def create_user(
    payload: UserCreateRequest,
    db: DbSession,
    _: AdminUser,
) -> DataResponse[UserResponse]:
    user = user_service.create_user(db, payload)

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
    status_filter: Annotated[
        Optional[str], Query(alias="status", pattern="^(SUCCESS|FAILURE)$")
    ] = None,
    actor_id: Annotated[Optional[uuid.UUID], Query(description="행동한 사용자")] = None,
    since: Annotated[Optional[datetime], Query(description="이 시각부터")] = None,
    until: Annotated[Optional[datetime], Query(description="이 시각까지")] = None,
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

    items = [AuditLogResponse.model_validate(row) for row in rows]

    return DataResponse(data=paged(items, total, page, page_size))
