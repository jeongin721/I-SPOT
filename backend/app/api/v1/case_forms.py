# /cases/{case_id}/forms — 기관 서식 작성 기록(22절, 2026-11-02)

import uuid
from typing import Optional

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession
from app.core.enums import CaseFormType
from app.core.responses import DataResponse
from app.schemas.case_form import (
    CaseFormConfirmRequest,
    CaseFormCreateRequest,
    CaseFormListResponse,
    CaseFormResponse,
    CaseFormUpdateRequest,
)
from app.services import case_form_service
from app.services.access import get_case_or_404

router = APIRouter(prefix="/cases", tags=["case-forms"])


@router.get("/{case_id}/forms", response_model=DataResponse[CaseFormListResponse])
def list_case_forms(
    case_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    form_type: Optional[CaseFormType] = Query(default=None),
) -> DataResponse[CaseFormListResponse]:
    case = get_case_or_404(db, case_id, current_user)
    rows = case_form_service.list_forms(db, case, form_type)

    return DataResponse(data=CaseFormListResponse(items=[case_form_service.to_response(row) for row in rows]))


@router.post(
    "/{case_id}/forms",
    response_model=DataResponse[CaseFormResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_case_form(
    case_id: uuid.UUID,
    payload: CaseFormCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseFormResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = case_form_service.create_form(db, current_user, case, payload)

    return DataResponse(data=case_form_service.to_response(row))


@router.get("/{case_id}/forms/{form_id}", response_model=DataResponse[CaseFormResponse])
def get_case_form(
    case_id: uuid.UUID,
    form_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseFormResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = case_form_service.get_form_or_404(db, case, form_id)

    return DataResponse(data=case_form_service.to_response(row))


@router.patch("/{case_id}/forms/{form_id}", response_model=DataResponse[CaseFormResponse])
def update_case_form(
    case_id: uuid.UUID,
    form_id: uuid.UUID,
    payload: CaseFormUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseFormResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = case_form_service.get_form_or_404(db, case, form_id)
    row = case_form_service.update_form(db, current_user, row, payload.values, payload.version)

    return DataResponse(data=case_form_service.to_response(row))


@router.post("/{case_id}/forms/{form_id}/confirm", response_model=DataResponse[CaseFormResponse])
def confirm_case_form(
    case_id: uuid.UUID,
    form_id: uuid.UUID,
    payload: CaseFormConfirmRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[CaseFormResponse]:
    case = get_case_or_404(db, case_id, current_user)
    row = case_form_service.get_form_or_404(db, case, form_id)
    row = case_form_service.confirm_form(db, current_user, row, payload.version)

    return DataResponse(data=case_form_service.to_response(row))
