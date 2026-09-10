from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
RAG_DATA_DIR = Path(os.getenv("RAG_DATA_DIR", BASE_DIR / "rag_data"))
VECTOR_DB_DIR = Path(os.getenv("RAG_VECTOR_DB_DIR", BASE_DIR / "rag_storage" / "chroma"))

EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "ispot_child_abuse")

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

SOURCE_TYPE_MAP = {
    "guidelines": "guideline",
    "manuals": "manual",
    "checklists": "checklist",
    "precedents": "precedent",
    "research": "research",
    "forms": "form",
}
