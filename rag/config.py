import os
from pathlib import Path

from dotenv import load_dotenv

# 국가법령정보센터 Open API 설정은 law/config.py 하나만 쓴다(빈 값 · 상대경로 처리가 그쪽에 있다).
# rag/ 에서 쓰는 값만 다시 내보낸다.
from law.config import LAW_CACHE_DIR, LAW_TARGET_LAWS  # noqa: F401

BASE_DIR = Path(__file__).resolve().parent.parent

# Load project .env before reading any RAG/law environment variables.
load_dotenv(BASE_DIR / ".env")


# 빈 값(Docker --env-file 의 `RAG_VECTOR_DB_DIR=`, .env.example 을 그대로 복사한 칸)은 기본값을 쓴다.
# os.getenv(이름, 기본값) 은 빈 문자열이 있으면 기본값 대신 빈 문자열을 돌려줘, 색인 폴더가 '.' 이 되고 모델 이름이 빈다.
def _env_str(name: str, default: str) -> str:
    return os.getenv(name, "").strip() or default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


def _env_path(name: str, default: Path) -> Path:
    """상대경로(.env 의 rag_storage/chroma 등)는 실행 위치가 아니라 프로젝트 루트 기준으로 푼다(law/config.py 와 같음)."""
    value = os.getenv(name, "").strip()
    if not value:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


RAG_DATA_DIR = _env_path("RAG_DATA_DIR", BASE_DIR / "rag_data")
VECTOR_DB_DIR = _env_path("RAG_VECTOR_DB_DIR", BASE_DIR / "rag_storage" / "chroma")

EMBEDDING_MODEL = _env_str("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
ANALYZER_MODEL = _env_str("RAG_ANALYZER_MODEL", "gpt-5.6-luna")
COLLECTION_NAME = _env_str("RAG_COLLECTION_NAME", "ispot_child_abuse")

CHUNK_SIZE = _env_int("RAG_CHUNK_SIZE", 900)
CHUNK_OVERLAP = _env_int("RAG_CHUNK_OVERLAP", 120)
TOP_K = _env_int("RAG_TOP_K", 5)

SOURCE_TYPE_MAP = {
    "guidelines": "guideline",
    "manuals": "manual",
    "checklists": "checklist",
    "precedents": "precedent",
    "research": "research",
    "forms": "form",
}
