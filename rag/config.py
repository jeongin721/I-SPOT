from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load project .env before reading any RAG/law environment variables.
load_dotenv(BASE_DIR / ".env")

RAG_DATA_DIR = Path(os.getenv("RAG_DATA_DIR", BASE_DIR / "rag_data"))
VECTOR_DB_DIR = Path(
    os.getenv(
        "RAG_VECTOR_DB_DIR",
        BASE_DIR / "rag_storage" / "chroma",
    )
)

EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
ANALYZER_MODEL = os.getenv("RAG_ANALYZER_MODEL", "gpt-5.6-luna")
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "ispot_child_abuse")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

# 국가법령정보센터 Open API
LAW_API_OC = os.getenv("LAW_API_OC", "").strip()
LAW_SEARCH_URL = os.getenv(
    "LAW_SEARCH_URL",
    "https://www.law.go.kr/DRF/lawSearch.do",
)
LAW_SERVICE_URL = os.getenv(
    "LAW_SERVICE_URL",
    "https://www.law.go.kr/DRF/lawService.do",
)
LAW_CACHE_DIR = Path(os.getenv("LAW_CACHE_DIR", BASE_DIR / "law_cache"))
LAW_TIMEOUT_SECONDS = int(os.getenv("LAW_TIMEOUT_SECONDS", "15"))
LAW_CACHE_MAX_AGE_HOURS = int(os.getenv("LAW_CACHE_MAX_AGE_HOURS", "24"))
LAW_TARGET_LAWS = tuple(
    law_name.strip()
    for law_name in os.getenv(
        "LAW_TARGET_LAWS",
        "아동복지법,아동학대범죄의 처벌 등에 관한 특례법",
    ).split(",")
    if law_name.strip()
)

SOURCE_TYPE_MAP = {
    "guidelines": "guideline",
    "manuals": "manual",
    "checklists": "checklist",
    "precedents": "precedent",
    "research": "research",
    "forms": "form",
}
