# 상담사 앱(폰) 알림 — 웹 푸시(API_CONTRACT 27절, 2026-11-19).

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.push import PUSH_ENDPOINT_MAX_LENGTH
from app.schemas.common import RequestModel
from app.services import webpush


class PushConfigResponse(BaseModel):
    enabled: bool
    # 브라우저 pushManager.subscribe 의 applicationServerKey(base64url). 꺼져 있으면 null.
    public_key: Optional[str] = None
    before_session_minutes: int


class PushKeys(RequestModel):
    p256dh: str = Field(min_length=80, max_length=200)
    auth: str = Field(min_length=16, max_length=100)


class PushSubscriptionRequest(RequestModel):
    """브라우저 PushSubscription.toJSON() 의 endpoint · keys 에 이 폰의 알림 설정을 더한 것. 같은 endpoint 면 덮어쓴다."""

    endpoint: str = Field(min_length=10, max_length=PUSH_ENDPOINT_MAX_LENGTH)
    keys: PushKeys
    before_session: bool = True
    upload_failed: bool = True

    @field_validator("endpoint")
    @classmethod
    def _https(cls, value: str) -> str:
        value = value.strip()

        if not webpush.is_push_endpoint(value):
            raise ValueError("알려진 푸시 서비스 주소가 아닙니다.")

        return value


class PushUnsubscribeRequest(RequestModel):
    endpoint: str = Field(min_length=10, max_length=PUSH_ENDPOINT_MAX_LENGTH)


class PushSubscriptionResponse(BaseModel):
    before_session: bool
    upload_failed: bool


class PushTestResponse(BaseModel):
    # 보낸 기기 수 · 보내지 못한 기기 수(없어진 구독은 지웠다).
    sent: int
    failed: int
