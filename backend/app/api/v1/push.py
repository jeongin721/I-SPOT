# /push — 상담사 앱(폰) 알림(웹 푸시, API_CONTRACT 27절, 2026-11-19)
from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.push import (
    PushConfigResponse,
    PushSubscriptionRequest,
    PushSubscriptionResponse,
    PushTestResponse,
    PushUnsubscribeRequest,
)
from app.services import push_service

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/config", response_model=DataResponse[PushConfigResponse])
def get_push_config(current_user: CurrentUser) -> DataResponse[PushConfigResponse]:
    return DataResponse(data=push_service.get_config())


@router.put("/subscription", response_model=DataResponse[PushSubscriptionResponse])
def put_push_subscription(
    payload: PushSubscriptionRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[PushSubscriptionResponse]:
    return DataResponse(data=push_service.subscribe(db, current_user, payload))


@router.post("/unsubscribe", response_model=DataResponse[dict])
def post_push_unsubscribe(payload: PushUnsubscribeRequest, db: DbSession, current_user: CurrentUser) -> DataResponse[dict]:
    push_service.unsubscribe(db, current_user, payload.endpoint)

    return DataResponse(data={"ok": True})


@router.post("/test", response_model=DataResponse[PushTestResponse])
def post_push_test(db: DbSession, current_user: CurrentUser) -> DataResponse[PushTestResponse]:
    return DataResponse(data=push_service.send_test(db, current_user))
