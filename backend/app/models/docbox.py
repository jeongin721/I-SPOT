# 문서함(2026-11-05, 11/05 디자인 '문서함 · 폴더 · 문서 올리기 · 내려받기 · 정렬 · 첫 페이지 미리보기', API_CONTRACT 23절).
# 기관 서식 · 참고 문서를 팀이 함께 보관한다(사례와 상관없는 공용 보관함). 파일 본체는 저장소(storage/docbox)에 두고 표에는 정보만.
import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

DOCBOX_FOLDER_NAME_MAX_LENGTH = 40
DOCBOX_FILE_NAME_MAX_LENGTH = 200


class DocboxFolder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "docbox_folders"

    name: Mapped[str] = mapped_column(String(DOCBOX_FOLDER_NAME_MAX_LENGTH), nullable=False, unique=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class DocboxFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "docbox_files"

    # 없으면 '폴더 없음'. 폴더를 지우는 기능은 없지만 지워지면 폴더 없음으로 남긴다.
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("docbox_folders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(DOCBOX_FILE_NAME_MAX_LENGTH), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # 저장소 기준 상대 경로(docbox/<uuid>). 응답에는 내보내지 않는다.
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'text'(첫 페이지 글) · 'image'(그림 그대로) · 'other'(미리보기 없음).
    preview_kind: Mapped[str] = mapped_column(String(10), nullable=False)
    # 첫 페이지 글(앞부분만). txt · md · csv · docx · hwpx · pdf 에서 뽑는다.
    preview_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
