from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import SOURCE_TYPE_MAP


def infer_source_type(file_path: Path) -> str:
    for part in file_path.parts:
        if part in SOURCE_TYPE_MAP:
            return SOURCE_TYPE_MAP[part]
    return "reference"


def infer_organization(filename: str) -> str:
    name = filename.lower()
    if "교육부" in filename:
        return "교육부"
    if "범죄수사규칙" in filename or "현장조사 체크리스트" in filename:
        return "경찰청"
    if "아동권리보장원" in filename or "판례" in filename:
        return "아동권리보장원"
    if "아동보호서비스 업무 매뉴얼" in filename:
        return "보건복지부·아동권리보장원"
    return "unknown"


def build_base_metadata(file_path: Path) -> dict[str, Any]:
    stem = file_path.stem
    document_id = stem.lower().replace(" ", "_")

    return {
        "document_id": document_id,
        "source": file_path.name,
        "organization": infer_organization(file_path.name),
        "source_type": infer_source_type(file_path),
        "category": "unknown",
        "abuse_type": "none",
        "section": "",
        "subsection": "",
        "year": 0,
        "authority_level": "official" if infer_source_type(file_path) in {"guideline", "manual", "checklist"} else "reference",
    }


def make_chunk_id(document_id: str, page: int, index: int) -> str:
    return f"{document_id}_p{page:04d}_{index:04d}"
