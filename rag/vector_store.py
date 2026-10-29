from __future__ import annotations

import threading

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from .config import COLLECTION_NAME, EMBEDDING_MODEL, VECTOR_DB_DIR

# Chroma 클라이언트는 여러 스레드가 동시에 처음 만들면 내부 등록이 엇갈려 KeyError 가 난다.
# 근거자료 분석과 화면별 매뉴얼 검색이 동시에 돌기 때문에, 한 번만 만들어 함께 쓴다.
_lock = threading.Lock()
_vector_store: Chroma | None = None


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def get_vector_store() -> Chroma:
    global _vector_store
    with _lock:
        if _vector_store is None:
            VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            _vector_store = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=get_embeddings(),
                persist_directory=str(VECTOR_DB_DIR),
            )
        return _vector_store
