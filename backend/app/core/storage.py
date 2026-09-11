# Local Audio Storage.
#
# 저장 경로 규칙 (03_BACKEND_PROMPT.md):
#     storage/audio/{case_id}/{session_id}/
#
# DB 에는 파일이 아니라 metadata 만 저장한다.
# Path Traversal 을 방지하기 위해 사용자 입력 filename 을 그대로 쓰지 않는다.

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

from app.core.config import settings
from app.core.errors import ErrorCode, bad_request

_SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_MAX_STEM_LENGTH = 60


@dataclass(frozen=True)
class StoredAudio:
    """저장 결과 metadata."""

    relative_path: str
    absolute_path: Path
    size_bytes: int
    checksum_sha256: str


def storage_root() -> Path:
    return Path(settings.AUDIO_STORAGE_ROOT).resolve()


def sanitize_filename(filename: Optional[str]) -> str:
    """
    업로드된 filename 에서 경로 요소를 제거하고 안전한 이름만 남긴다.

    "../../etc/passwd" 나 "C:\\windows\\system32\\x.wav" 같은 입력은
    경로가 아니라 단순 이름으로 축소된다.
    """

    if not filename or not filename.strip():
        raise bad_request(
            ErrorCode.AUDIO_INVALID_FILENAME,
            "파일 이름이 없습니다.",
        )

    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    base = PurePosixPath(normalized).name

    if base in {"", ".", ".."}:
        raise bad_request(
            ErrorCode.AUDIO_INVALID_FILENAME,
            "허용되지 않는 파일 이름입니다.",
        )

    # Windows drive prefix(예: "C:file.wav") 제거
    if ":" in base:
        base = base.split(":")[-1]

    suffix = PurePosixPath(base).suffix.lower()
    stem = PurePosixPath(base).stem

    safe_stem = _SAFE_NAME_PATTERN.sub("_", stem).strip("._-")[:_MAX_STEM_LENGTH]

    if not safe_stem:
        safe_stem = "audio"

    safe_suffix = _SAFE_NAME_PATTERN.sub("", suffix)

    if not safe_suffix.startswith("."):
        safe_suffix = f".{safe_suffix}" if safe_suffix else ""

    if not safe_suffix:
        raise bad_request(
            ErrorCode.AUDIO_INVALID_FILENAME,
            "확장자가 없는 파일은 업로드할 수 없습니다.",
        )

    return f"{safe_stem}{safe_suffix}"


def session_directory(case_id: uuid.UUID, session_id: uuid.UUID) -> Path:
    """
    storage/audio/{case_id}/{session_id} 를 반환한다.

    case_id/session_id 는 UUID 타입만 받으므로 경로 조작이 불가능하다.
    """

    directory = (storage_root() / str(case_id) / str(session_id)).resolve()

    _assert_inside_storage(directory)
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def _assert_inside_storage(path: Path) -> None:
    root = storage_root()

    if not path.is_relative_to(root):
        raise bad_request(
            ErrorCode.AUDIO_INVALID_FILENAME,
            "저장 경로가 허용된 범위를 벗어났습니다.",
        )


def save_audio_chunks(
    case_id: uuid.UUID,
    session_id: uuid.UUID,
    filename: str,
    chunks: Iterable[bytes],
    max_bytes: int,
) -> StoredAudio:
    """
    음성 파일을 Local Storage 에 streaming 으로 저장한다.

    전체를 메모리에 올리지 않고 크기 제한을 초과하면 즉시 중단·삭제한다.
    """

    safe_name = sanitize_filename(filename)
    directory = session_directory(case_id, session_id)

    # 같은 Session 에 재업로드해도 덮어쓰지 않도록 prefix 를 붙인다.
    unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    target = (directory / unique_name).resolve()

    _assert_inside_storage(target)

    digest = hashlib.sha256()
    total = 0

    try:
        with target.open("wb") as file:
            for chunk in chunks:
                if not chunk:
                    continue

                total += len(chunk)

                if total > max_bytes:
                    raise bad_request(
                        ErrorCode.AUDIO_TOO_LARGE,
                        f"음성 파일이 최대 허용 크기({max_bytes // (1024 * 1024)}MB)를 초과했습니다.",
                    )

                digest.update(chunk)
                file.write(chunk)
    except OSError as error:
        target.unlink(missing_ok=True)

        raise bad_request(
            ErrorCode.AUDIO_STORAGE_ERROR,
            "음성 파일 저장에 실패했습니다.",
        ) from error
    except Exception:
        target.unlink(missing_ok=True)
        raise

    return StoredAudio(
        relative_path=str(target.relative_to(storage_root())).replace("\\", "/"),
        absolute_path=target,
        size_bytes=total,
        checksum_sha256=digest.hexdigest(),
    )


def resolve_stored_path(relative_path: str) -> Path:
    """DB 에 저장된 상대 경로를 절대 경로로 변환한다."""

    candidate = (storage_root() / relative_path).resolve()
    _assert_inside_storage(candidate)

    return candidate


def delete_stored_audio(relative_path: str) -> None:
    try:
        target = resolve_stored_path(relative_path)
    except Exception:
        return

    if target.is_file():
        target.unlink(missing_ok=True)
