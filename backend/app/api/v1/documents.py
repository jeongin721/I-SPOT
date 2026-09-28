# /sessions/{session_id}/documents

import uuid
from typing import List

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.document import (
    DocumentCreateRequest,
    DocumentResponse,
    DocumentUpdateRequest,
)
from app.services import document_service
from app.services.access import get_session_or_404

router = APIRouter(prefix="/sessions", tags=["documents"])


@router.get(
    "/{session_id}/documents",
    response_model=DataResponse[List[DocumentResponse]],
)
def list_documents(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[List[DocumentResponse]]:
    session = get_session_or_404(db, session_id, current_user)
    documents = document_service.list_documents(db, session.id)

    return DataResponse(
        data=[DocumentResponse.model_validate(document) for document in documents]
    )


@router.post(
    "/{session_id}/documents",
    response_model=DataResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    session_id: uuid.UUID,
    payload: DocumentCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[DocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    document = document_service.create_document(db, session, current_user, payload)

    return DataResponse(data=DocumentResponse.model_validate(document))


@router.patch(
    "/{session_id}/documents/{document_id}",
    response_model=DataResponse[DocumentResponse],
)
def update_document(
    session_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentUpdateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[DocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    document = document_service.get_document_or_404(db, session.id, document_id)
    updated = document_service.update_document(
        db, session, document, current_user, payload
    )

    return DataResponse(data=DocumentResponse.model_validate(updated))


@router.post(
    "/{session_id}/documents/{document_id}/approve",
    response_model=DataResponse[DocumentResponse],
)
def approve_document(
    session_id: uuid.UUID,
    document_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> DataResponse[DocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    document = document_service.get_document_or_404(db, session.id, document_id)
    approved = document_service.approve_document(db, session, document, current_user)

    return DataResponse(data=DocumentResponse.model_validate(approved))
