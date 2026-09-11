# 상담 기록 문서 CRUD 및 승인.

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AuditAction, ReviewStatus
from app.core.errors import ErrorCode, conflict, not_found
from app.models.document import Document
from app.models.session import ConsultationSession
from app.models.user import User
from app.schemas.document import DocumentCreateRequest, DocumentUpdateRequest
from app.services import audit_service


def list_documents(db: Session, session_id: uuid.UUID) -> List[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.session_id == session_id)
            .order_by(Document.created_at.asc())
        )
    )


def get_document_or_404(
    db: Session,
    session_id: uuid.UUID,
    document_id: uuid.UUID,
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.session_id == session_id,
        )
    )

    if document is None:
        raise not_found(ErrorCode.DOCUMENT_NOT_FOUND, "문서를 찾을 수 없습니다.")

    return document


def create_document(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    payload: DocumentCreateRequest,
) -> Document:
    document = Document(
        session_id=session.id,
        doc_type=payload.doc_type,
        title=payload.title,
        content=payload.content,
        status=ReviewStatus.DRAFT,
        created_by_id=current_user.id,
    )

    db.add(document)
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.DOCUMENT_CREATED,
        entity_type="Document",
        entity_id=document.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={"doc_type": document.doc_type},
    )

    db.commit()
    db.refresh(document)

    return document


def update_document(
    db: Session,
    session: ConsultationSession,
    document: Document,
    current_user: User,
    payload: DocumentUpdateRequest,
) -> Document:
    if document.status == ReviewStatus.APPROVED:
        raise conflict(
            ErrorCode.ALREADY_APPROVED,
            "승인이 완료된 문서는 수정할 수 없습니다.",
        )

    data = payload.model_dump(exclude_unset=True)
    changed_fields = []

    if "title" in data and data["title"] is not None:
        document.title = data["title"]
        changed_fields.append("title")

    if "content" in data and data["content"] is not None:
        document.content = data["content"]
        changed_fields.append("content")

    if changed_fields:
        audit_service.record(
            db,
            action=AuditAction.DOCUMENT_UPDATED,
            entity_type="Document",
            entity_id=document.id,
            actor_id=current_user.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={"changed_fields": changed_fields},
        )

    db.commit()
    db.refresh(document)

    return document


def approve_document(
    db: Session,
    session: ConsultationSession,
    document: Document,
    current_user: User,
) -> Document:
    if document.status == ReviewStatus.APPROVED:
        raise conflict(ErrorCode.ALREADY_APPROVED, "이미 승인된 문서입니다.")

    document.status = ReviewStatus.APPROVED
    document.approved_at = datetime.now(timezone.utc)
    document.approved_by_id = current_user.id

    audit_service.record(
        db,
        action=AuditAction.DOCUMENT_APPROVED,
        entity_type="Document",
        entity_id=document.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
    )

    db.commit()
    db.refresh(document)

    return document
