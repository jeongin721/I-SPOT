# /sessions/{session_id}/source-document — 상담 기록 문서 회차(21절, 2026-11-02)

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.source_document import SourceDocumentResponse
from app.services import source_document_service
from app.services.access import get_session_or_404
from app.services.document_text import MAX_DOCUMENT_BYTES

router = APIRouter(prefix="/sessions", tags=["source-document"])


@router.post(
    "/{session_id}/source-document",
    response_model=DataResponse[SourceDocumentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="상담 기록 문서 올리기(3 · 4단계만 쓰는 회차)",
)
def upload_source_document(
    session_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    file: Annotated[UploadFile, File(description="상담 기록 문서(.txt · .docx · .hwpx · .pdf)")],
    background_tasks: BackgroundTasks,
) -> DataResponse[SourceDocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    # 상한보다 1바이트 더 읽어 넘는지 본다(큰 파일을 통째로 메모리에 올리지 않는다).
    data = file.file.read(MAX_DOCUMENT_BYTES + 1)
    row = source_document_service.upload(db, session, current_user, filename=file.filename or "", data=data)
    # 학대 신호 · 대화 주제(상담 이력 · 브리핑)는 응답 뒤에 만든다.
    analysis_id = source_document_service.start_document_signals(db, session)
    if analysis_id is not None:
        background_tasks.add_task(source_document_service.process_document_signals, session.id, analysis_id)

    return DataResponse(data=source_document_service.to_response(row))


@router.get("/{session_id}/source-document", response_model=DataResponse[SourceDocumentResponse])
def get_source_document(session_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[SourceDocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)

    return DataResponse(data=source_document_service.to_response(source_document_service.require_row(db, session)))


@router.post(
    "/{session_id}/source-document/followups",
    response_model=DataResponse[SourceDocumentResponse],
    summary="문서 회차의 4단계 초안(확인 사항 · 추가 질문) 만들기",
)
def draft_document_followups(session_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> DataResponse[SourceDocumentResponse]:
    session = get_session_or_404(db, session_id, current_user)
    row = source_document_service.draft_followups(db, session, current_user)

    return DataResponse(data=source_document_service.to_response(row))
