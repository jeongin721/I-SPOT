# rag/config.py 의 환경변수 읽기를 테스트한다. 모듈이 import 할 때 값을 읽어 굳히므로 따로 띄운 파이썬에서 읽는다.

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

READ_CONFIG = (
    "import json, rag.config as c; "
    "print(json.dumps({'db': str(c.VECTOR_DB_DIR), 'data': str(c.RAG_DATA_DIR), 'model': c.ANALYZER_MODEL, "
    "'embedding': c.EMBEDDING_MODEL, 'top_k': c.TOP_K, 'chunk': c.CHUNK_SIZE}))"
)


def read_config(tmp_path, **env):
    names = ("RAG_VECTOR_DB_DIR", "RAG_DATA_DIR", "RAG_ANALYZER_MODEL", "RAG_EMBEDDING_MODEL", "RAG_TOP_K", "RAG_CHUNK_SIZE")
    base = {key: value for key, value in os.environ.items() if key not in names}
    base["PYTHONPATH"] = str(REPO_ROOT)
    # 실행 위치를 저장소 밖으로 둔다(상대경로가 실행 위치로 풀리면 드러나게).
    output = subprocess.run(
        [sys.executable, "-c", READ_CONFIG],
        cwd=tmp_path,
        env={**base, **env},
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(output.strip().splitlines()[-1])


def test_blank_values_use_defaults(tmp_path):
    # Docker --env-file 의 `RAG_VECTOR_DB_DIR=` 처럼 빈 값 · 공백만 든 값.
    config = read_config(
        tmp_path,
        RAG_VECTOR_DB_DIR="",
        RAG_DATA_DIR="   ",
        RAG_ANALYZER_MODEL="",
        RAG_EMBEDDING_MODEL=" ",
        RAG_TOP_K="",
        RAG_CHUNK_SIZE="",
    )

    assert config["db"] == str(REPO_ROOT / "rag_storage" / "chroma")
    assert config["data"] == str(REPO_ROOT / "rag_data")
    assert config["model"] == "gpt-5.6-luna"
    assert config["embedding"] == "text-embedding-3-small"
    assert config["top_k"] == 5
    assert config["chunk"] == 900


def test_relative_paths_resolve_against_repo_root(tmp_path):
    config = read_config(tmp_path, RAG_VECTOR_DB_DIR="rag_storage/other", RAG_DATA_DIR=str(tmp_path / "data"))

    assert config["db"] == str(REPO_ROOT / "rag_storage" / "other")
    assert config["data"] == str(tmp_path / "data")


def test_set_values_are_used(tmp_path):
    config = read_config(tmp_path, RAG_ANALYZER_MODEL="custom-model", RAG_TOP_K="8")

    assert config["model"] == "custom-model"
    assert config["top_k"] == 8
