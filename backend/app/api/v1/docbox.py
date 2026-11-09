# /docbox — 문서함(23절, 2026-11-05)
import uuid
from typing import Annotated, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.core.deps import CurrentUser, DbSession
from app.core.responses import DataResponse
from app.schemas.docbox import (
    DocboxFileMoveRequest,
    DocboxFileResponse,
    DocboxFolderCreateRequest,
    DocboxFolderResponse,
    DocboxListResponse,
    DocboxUploadResponse,
)
from app.services import docbox_service

router = APIRouter(prefix="/docbox", tags=["docbox"])


@router.get("", response_model=DataResponse[DocboxListResponse], summary="문서함 폴더 · 문서 목록")
def list_docbox(db: DbSession, current_user: CurrentUser) -> DataResponse[DocboxListResponse]:
    return DataResponse(data=docbox_service.list_all(db))


@router.post("/folders", response_model=DataResponse[DocboxFolderResponse], status_code=status.HTTP_201_CREATED)
def create_docbox_folder(
    payload: DocboxFolderCreateRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[DocboxFolderResponse]:
    folder = docbox_service.create_folder(db, current_user, payload.name)

    return DataResponse(data=DocboxFolderResponse(id=folder.id, name=folder.name, count=0))


@router.post("/files", response_model=DataResponse[DocboxUploadResponse], status_code=status.HTTP_201_CREATED)
def upload_docbox_files(
    db: DbSession,
    current_user: CurrentUser,
    files: Annotated[List[UploadFile], File(description="올릴 문서(여러 개)")],
    folder_id: Annotated[Optional[uuid.UUID], Form()] = None,
) -> DataResponse[DocboxUploadResponse]:
    # 파일마다 상한보다 1바이트 더 읽어 넘는지 본다(큰 파일을 통째로 메모리에 올리지 않는다).
    items = [(item.filename, item.file.read(docbox_service.MAX_FILE_BYTES + 1)) for item in files[: docbox_service.MAX_FILES + 1]]
    rows = docbox_service.upload(db, current_user, items, folder_id)
    names = docbox_service.names_for(db, rows)

    return DataResponse(data=DocboxUploadResponse(files=[docbox_service.to_response(row, names) for row in rows]))


@router.patch("/files/{file_id}", response_model=DataResponse[DocboxFileResponse], summary="문서 폴더 옮기기")
def move_docbox_file(
    file_id: uuid.UUID, payload: DocboxFileMoveRequest, db: DbSession, current_user: CurrentUser
) -> DataResponse[DocboxFileResponse]:
    row = docbox_service.move(db, current_user, docbox_service.get_file_or_404(db, file_id), payload.folder_id)

    return DataResponse(data=docbox_service.to_response(row, docbox_service.names_for(db, [row])))


@router.get("/files/{file_id}/download", summary="문서 내려받기(늘 첨부로)")
def download_docbox_file(file_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> FileResponse:
    row = docbox_service.get_file_or_404(db, file_id)
    path = docbox_service.file_path(row)
    docbox_service.record_download(db, current_user, row)

    return FileResponse(
        path,
        media_type=row.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.name)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
