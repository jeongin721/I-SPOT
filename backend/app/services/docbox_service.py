# 문서함(API_CONTRACT 23절, 2026-11-05, 11/05 디자인 '문서함').
#
# 기관 서식 · 참고 문서를 팀이 함께 보관한다. 사례 · 회차와 상관없는 공용 보관함이라 로그인한 상담원 · 관리자 모두 보고 올린다.
#  - 폴더: 이름만(겹치면 409). 지우기 · 이름 바꾸기는 디자인에 없어 만들지 않는다.
#  - 파일: 한 번에 MAX_FILES 개, 파일마다 MAX_FILE_BYTES 까지. 정해 둔 확장자만 받는다(실행 파일 · 스크립트를 막는다).
#    본체는 저장소 storage/docbox/<uuid> 에 두고, 내려받기는 늘 첨부(attachment)로 · nosniff 로 준다.
#  - 첫 페이지 미리보기: 그림은 그대로, txt · md · csv 는 앞부분 글, docx · hwpx · pdf 는 document_text 로 뽑은 앞부분 글.
#    뽑지 못하면(손상 · 너무 김 · 시간 초과) 미리보기 없음(other)으로 둔다 — 올리기는 막지 않는다.
# 감사 기록에는 파일 수 · 형식 · 크기 · 폴더 id 만 남긴다(파일 이름 · 내용은 넣지 않는다).
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import storage
from app.core.concurrency import run_with_timeout
from app.core.enums import AuditAction
from app.core.errors import APIError, ErrorCode, conflict, not_found
from app.models.docbox import DOCBOX_FILE_NAME_MAX_LENGTH, DocboxFile, DocboxFolder
from app.models.user import User
from app.schemas.docbox import DocboxFileResponse, DocboxFolderResponse, DocboxListResponse
from app.services import audit_service
from app.services.document_text import extract_text

logger = logging.getLogger(__name__)

MAX_FILES = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
#: 미리보기 글 앞부분 길이.
PREVIEW_CHARS = 1500
PREVIEW_TIMEOUT_SECONDS = 10.0

IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
PLAIN_TEXT = {"txt", "md", "csv"}
EXTRACTABLE = {"docx", "hwpx", "pdf"}
OTHER = {"hwp", "doc", "xlsx", "xls", "pptx", "ppt"}
ALLOWED = set(IMAGE_TYPES) | PLAIN_TEXT | EXTRACTABLE | OTHER


def _invalid(message: str) -> APIError:
    return APIError(ErrorCode.VALIDATION_ERROR, message, status_code=422)


def _extension(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _clean_name(filename: Optional[str]) -> str:
    """경로 · 제어 문자를 뺀 파일 이름. 길면 확장자를 살려 자른다."""

    name = "".join(ch for ch in Path((filename or "").replace("\\", "/")).name if ch >= " " and ch != "\x7f").strip()
    if not name or name in {".", ".."}:
        raise _invalid("파일 이름이 없습니다.")
    if len(name) > DOCBOX_FILE_NAME_MAX_LENGTH:
        ext = _extension(name)
        keep = DOCBOX_FILE_NAME_MAX_LENGTH - len(ext) - 1
        name = f"{name[:keep]}.{ext}" if ext and keep > 0 else name[:DOCBOX_FILE_NAME_MAX_LENGTH]
    return name


def _decode(data: bytes) -> Optional[str]:
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _preview(name: str, data: bytes) -> Tuple[str, Optional[str]]:
    ext = _extension(name)
    if ext in IMAGE_TYPES:
        return "image", None
    text: Optional[str] = None
    if ext in PLAIN_TEXT:
        text = _decode(data[: PREVIEW_CHARS * 4])
    elif ext in EXTRACTABLE:
        try:
            text = run_with_timeout(lambda: extract_text(name, data), PREVIEW_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 — 미리보기는 덤이다. 뽑지 못하면 미리보기 없이 올린다.
            text = None
    if text is None:
        return "other", None
    text = text.replace("\r\n", "\n").replace("\x00", "").strip()
    return ("text", text[:PREVIEW_CHARS]) if text else ("other", None)


def _folder_or_404(db: Session, folder_id: Optional[uuid.UUID]) -> Optional[DocboxFolder]:
    if folder_id is None:
        return None
    folder = db.get(DocboxFolder, folder_id)
    if folder is None:
        raise not_found(ErrorCode.NOT_FOUND, "폴더를 찾을 수 없습니다.")
    return folder


def _store(data: bytes) -> str:
    relative = f"docbox/{uuid.uuid4().hex}"
    target = (storage.storage_root() / relative).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative


def to_response(row: DocboxFile, names: Dict[uuid.UUID, str]) -> DocboxFileResponse:
    return DocboxFileResponse(
        id=row.id,
        folder_id=row.folder_id,
        name=row.name,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        preview_kind=row.preview_kind,
        preview_text=row.preview_text,
        uploaded_by_name=names.get(row.uploaded_by_id) if row.uploaded_by_id else None,
        created_at=row.created_at,
    )


def _user_names(db: Session, rows: List[DocboxFile]) -> Dict[uuid.UUID, str]:
    ids = {row.uploaded_by_id for row in rows if row.uploaded_by_id}
    if not ids:
        return {}
    return {user_id: name for user_id, name in db.execute(select(User.id, User.name).where(User.id.in_(ids)))}


def list_all(db: Session) -> DocboxListResponse:
    folders = list(db.scalars(select(DocboxFolder).order_by(DocboxFolder.created_at.asc(), DocboxFolder.id.asc())))
    counts = dict(db.execute(select(DocboxFile.folder_id, func.count()).group_by(DocboxFile.folder_id)).all())
    files = list(db.scalars(select(DocboxFile).order_by(DocboxFile.created_at.desc(), DocboxFile.id.desc())))
    names = _user_names(db, files)
    return DocboxListResponse(
        folders=[DocboxFolderResponse(id=f.id, name=f.name, count=int(counts.get(f.id, 0))) for f in folders],
        files=[to_response(row, names) for row in files],
    )


def create_folder(db: Session, user: User, name: str) -> DocboxFolder:
    if db.scalar(select(DocboxFolder.id).where(DocboxFolder.name == name)) is not None:
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "같은 이름의 폴더가 있습니다.")
    folder = DocboxFolder(name=name, created_by_id=user.id)
    db.add(folder)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "같은 이름의 폴더가 있습니다.") from error
    audit_service.record(
        db, action=AuditAction.DOCBOX_FOLDER_CREATED, entity_type="DocboxFolder", entity_id=folder.id, actor_id=user.id
    )
    db.commit()
    db.refresh(folder)
    return folder


def upload(db: Session, user: User, files: List[Tuple[Optional[str], bytes]], folder_id: Optional[uuid.UUID]) -> List[DocboxFile]:
    """files: (파일 이름, 내용). 하나라도 규칙에 어긋나면 아무것도 저장하지 않는다(422)."""

    if not files:
        raise _invalid("올릴 문서를 골라 주세요.")
    if len(files) > MAX_FILES:
        raise _invalid(f"한 번에 {MAX_FILES}개까지 올릴 수 있습니다.")
    _folder_or_404(db, folder_id)

    checked = []
    for filename, data in files:
        name = _clean_name(filename)
        ext = _extension(name)
        if ext not in ALLOWED:
            raise _invalid(f"올릴 수 없는 형식입니다(.{ext or '?'}). 문서 · 표 · 그림 파일만 올릴 수 있습니다.")
        if not data:
            raise _invalid("빈 파일은 올릴 수 없습니다.")
        if len(data) > MAX_FILE_BYTES:
            raise _invalid("파일 하나는 10 MB 까지 올릴 수 있습니다.")
        checked.append((name, ext, data))

    rows: List[DocboxFile] = []
    stored: List[str] = []
    try:
        for name, ext, data in checked:
            kind, text = _preview(name, data)
            relative = _store(data)
            stored.append(relative)
            row = DocboxFile(
                folder_id=folder_id,
                name=name,
                content_type=IMAGE_TYPES.get(ext, "application/octet-stream"),
                size_bytes=len(data),
                path=relative,
                preview_kind=kind,
                preview_text=text,
                uploaded_by_id=user.id,
            )
            db.add(row)
            rows.append(row)
        db.flush()
        audit_service.record(
            db,
            action=AuditAction.DOCBOX_FILE_UPLOADED,
            entity_type="DocboxFile",
            actor_id=user.id,
            detail={
                "count": len(rows),
                "formats": sorted({ext for _, ext, _ in checked}),
                "bytes": sum(len(data) for _, _, data in checked),
                "folder_id": str(folder_id) if folder_id else None,
            },
        )
        db.commit()
    except BaseException:
        db.rollback()
        for relative in stored:
            (storage.storage_root() / relative).unlink(missing_ok=True)
        raise
    for row in rows:
        db.refresh(row)
    return rows


def get_file_or_404(db: Session, file_id: uuid.UUID) -> DocboxFile:
    row = db.get(DocboxFile, file_id)
    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "문서를 찾을 수 없습니다.")
    return row


def move(db: Session, user: User, row: DocboxFile, folder_id: Optional[uuid.UUID]) -> DocboxFile:
    _folder_or_404(db, folder_id)
    row.folder_id = folder_id
    audit_service.record(
        db,
        action=AuditAction.DOCBOX_FILE_MOVED,
        entity_type="DocboxFile",
        entity_id=row.id,
        actor_id=user.id,
        detail={"folder_id": str(folder_id) if folder_id else None},
    )
    db.commit()
    db.refresh(row)
    return row


def file_path(row: DocboxFile) -> Path:
    root = storage.storage_root()
    target = (root / row.path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise not_found(ErrorCode.NOT_FOUND, "문서 파일을 찾을 수 없습니다.")
    return target


def record_download(db: Session, user: User, row: DocboxFile) -> None:
    audit_service.record(
        db, action=AuditAction.DOCBOX_FILE_DOWNLOADED, entity_type="DocboxFile", entity_id=row.id, actor_id=user.id
    )
    db.commit()


def names_for(db: Session, rows: List[DocboxFile]) -> Dict[uuid.UUID, str]:
    return _user_names(db, rows)
