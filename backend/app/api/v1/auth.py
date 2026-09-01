# /auth
#
# 자유 회원가입 endpoint 는 제공하지 않는다. 계정 생성은 관리자 전용이다.

from typing import List

from fastapi import APIRouter, status

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.core.responses import DataResponse
from app.core.security import create_access_token, token_expires_in_seconds
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    UserCreateRequest,
    UserResponse,
)
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=DataResponse[LoginResponse])
def login(payload: LoginRequest, db: DbSession) -> DataResponse[LoginResponse]:
    user = user_service.authenticate(db, payload.email, payload.password)

    token = create_access_token(subject=str(user.id), role=user.role.value)

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
