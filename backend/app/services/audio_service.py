# Audio Upload.
#
# 검증 항목(03_BACKEND_PROMPT.md §7): 확장자 / MIME / 크기 / 빈 파일 / Path Traversal
# 파일 내용은 Local Storage 에, metadata 는 DB 에 저장한다.
#
# 외부 native 의존성(libmagic 등)을 추가하지 않기 위해
# container signature(magic bytes)를 직접 확인한다.

import struct
from pathlib import PurePosixPath
from typing import BinaryIO, Iterator, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.core.enums import AuditAction, SessionStatus
from app.core.errors import ErrorCode, bad_request, not_found
from app.core.state_machine import assert_transition
from app.models.audio import AudioFile
from app.models.session import ConsultationSession
from app.models.user import User
from app.services import audit_service

_HEADER_READ_BYTES = 8192
_STREAM_CHUNK_BYTES = 1024 * 1024

# 확장자별로 허용되는 container signature
_EXTENSION_FORMATS = {
    ".wav": {"wav"},
    ".mp3": {"mp3"},
    ".m4a": {"mp4"},
    ".mp4": {"mp4"},
    ".ogg": {"ogg"},
    ".flac": {"flac"},
    ".webm": {"webm", "matroska"},
}

# 브라우저 MediaRecorder / 일반 업로드에서 나오는 MIME 만 허용한다.
_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/vnd.wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/x-flac",
    "audio/webm",
    "video/mp4",
    "video/webm",
    # 일부 클라이언트는 타입을 특정하지 못한다. 내용 검증으로 보완한다.
    "application/octet-stream",
}


# =========================================================
# 검증 helper
# =========================================================

def detect_audio_format(header: bytes) -> Optional[str]:
    """Container signature 로 실제 파일 종류를 판별한다."""

    if len(header) < 12:
        return None

    if header[0:4] == b"RIFF" and header[8:12] == b"WAVE":
        return "wav"

    if header[0:4] == b"OggS":
        return "ogg"

    if header[0:4] == b"fLaC":
        return "flac"

    if header[0:4] == b"\x1a\x45\xdf\xa3":
        # EBML. webm 과 matroska 를 구분하려면 DocType 을 확인해야 한다.
        window = header[:512]

        if b"webm" in window:
            return "webm"

        return "matroska"

    if header[4:8] == b"ftyp":
        return "mp4"

    if header[0:3] == b"ID3":
        return "mp3"

    # MPEG audio frame sync (0xFFEx / 0xFFFx)
    if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
        return "mp3"

    return None


def _validate_extension(filename: str) -> str:
    safe_name = storage.sanitize_filename(filename)
    extension = PurePosixPath(safe_name).suffix.lower()

    allowed = {ext.lower() for ext in settings.AUDIO_ALLOWED_EXTENSIONS}

    if extension not in allowed:
        raise bad_request(
            ErrorCode.AUDIO_UNSUPPORTED_TYPE,
            f"지원하지 않는 확장자입니다. 허용: {', '.join(sorted(allowed))}",
        )

    return extension


def _validate_mime(content_type: Optional[str]) -> str:
    normalized = (content_type or "").split(";")[0].strip().lower()

    if not normalized:
        raise bad_request(
            ErrorCode.AUDIO_UNSUPPORTED_TYPE,
            "Content-Type 이 없습니다.",
        )

    if normalized not in _ALLOWED_MIME_TYPES:
        raise bad_request(
            ErrorCode.AUDIO_UNSUPPORTED_TYPE,
            f"지원하지 않는 MIME type 입니다: {normalized}",
        )

    return normalized


def _validate_header(header: bytes, extension: str) -> None:
    if not header:
        raise bad_request(ErrorCode.AUDIO_EMPTY_FILE, "빈 음성 파일은 업로드할 수 없습니다.")

    detected = detect_audio_format(header)

    if detected is None:
        raise bad_request(
            ErrorCode.AUDIO_CORRUPTED,
            "음성 파일 형식을 확인할 수 없습니다. 파일이 손상되었을 수 있습니다.",
        )

    expected: Set[str] = _EXTENSION_FORMATS.get(extension, set())

    if expected and detected not in expected:
        raise bad_request(
            ErrorCode.AUDIO_UNSUPPORTED_TYPE,
            f"확장자({extension})와 실제 파일 형식({detected})이 일치하지 않습니다.",
        )


def _wav_duration_ms(header: bytes) -> Optional[int]:
    """
    WAV 는 header 만으로 길이를 계산할 수 있다.
    다른 형식은 외부 도구가 필요하므로 클라이언트 값에 의존한다.
    """

    if header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
        return None

    cursor = 12
    byte_rate = None

    while cursor + 8 <= len(header):
        chunk_id = header[cursor : cursor + 4]
        (chunk_size,) = struct.unpack("<I", header[cursor + 4 : cursor + 8])

        if chunk_id == b"fmt " and cursor + 8 + 16 <= len(header):
            (byte_rate,) = struct.unpack("<I", header[cursor + 8 + 8 : cursor + 8 + 12])

        if chunk_id == b"data" and byte_rate:
            if byte_rate <= 0:
                return None

            return int(chunk_size / byte_rate * 1000)

        cursor += 8 + chunk_size + (chunk_size % 2)

    return None


def _stream_chunks(header: bytes, file: BinaryIO) -> Iterator[bytes]:
    yield header

    while True:
        chunk = file.read(_STREAM_CHUNK_BYTES)

        if not chunk:
            break

        yield chunk


# =========================================================
# Upload
# =========================================================

def upload_audio(
    db: Session,
    session: ConsultationSession,
    current_user: User,
    *,
    filename: Optional[str],
    content_type: Optional[str],
    file: BinaryIO,
    duration_ms: Optional[int] = None,
) -> AudioFile:
    """
    음성 파일을 저장하고 Session 상태를 AUDIO_UPLOADED 로 전이한다.

    재업로드를 허용하되 이전 파일 record 는 이력으로 남긴다.
    """

    assert_transition(session.status, SessionStatus.AUDIO_UPLOADED)

    # 1) 이름/확장자 (Path Traversal 방지 포함)
    extension = _validate_extension(filename or "")

    # 2) MIME
    mime_type = _validate_mime(content_type)

    # 3) 내용 (빈 파일 / 손상 파일)
    header = file.read(_HEADER_READ_BYTES)
    _validate_header(header, extension)

    # 4) 크기: streaming 저장 중 초과 시 중단
    stored = storage.save_audio_chunks(
        case_id=session.case_id,
        session_id=session.id,
        filename=filename or f"audio{extension}",
        chunks=_stream_chunks(header, file),
        max_bytes=settings.audio_max_size_bytes,
    )

    resolved_duration = _wav_duration_ms(header) or duration_ms

    audio = AudioFile(
        session_id=session.id,
        path=stored.relative_path,
        original_filename=storage.sanitize_filename(filename or f"audio{extension}"),
        mime_type=mime_type,
        size_bytes=stored.size_bytes,
        duration_ms=resolved_duration,
        checksum_sha256=stored.checksum_sha256,
        uploaded_by_id=current_user.id,
    )

    db.add(audio)

    session.status = SessionStatus.AUDIO_UPLOADED
    session.clear_error()

    audit_service.record(
        db,
        action=AuditAction.AUDIO_UPLOADED,
        entity_type="AudioFile",
        entity_id=audio.id,
        actor_id=current_user.id,
        case_id=session.case_id,
        session_id=session.id,
        detail={
            "size_bytes": stored.size_bytes,
            "mime_type": mime_type,
            "duration_ms": resolved_duration,
        },
    )

    db.commit()
    db.refresh(audio)

    return audio


def get_latest_audio(db: Session, session_id) -> AudioFile:
    audio = db.scalar(
        select(AudioFile)
        .where(AudioFile.session_id == session_id)
        .order_by(AudioFile.created_at.desc(), AudioFile.id.desc())
        .limit(1)
    )

    if audio is None:
        raise not_found(
            ErrorCode.AUDIO_NOT_FOUND,
            "업로드된 음성 파일이 없습니다.",
        )

    return audio
