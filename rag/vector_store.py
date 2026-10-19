from __future__ import annotations

import sys

# chromadb는 sqlite3 >= 3.35.0을 요구하는데, 이 프로젝트가 돌아가는
# 환경(Ubuntu 20.04 등)의 시스템 sqlite3는 더 낮은 버전일 수 있다
# (2026-10-19, ai-modeling 포팅 중 발견 — pip install pysqlite3-binary
# 필요). chromadb가 import되기 전에 표준 우회로 sqlite3 모듈 자체를
# pysqlite3로 바꿔치기한다(Chroma 공식 문서 권장 방법).
try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .config import COLLECTION_NAME, EMBEDDING_MODEL, VECTOR_DB_DIR


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def get_vector_store() -> Chroma:
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(VECTOR_DB_DIR),
    )
