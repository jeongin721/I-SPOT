from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from rag.config import (
    LAW_API_OC,
    LAW_CACHE_DIR,
    LAW_CACHE_MAX_AGE_HOURS,
    LAW_SEARCH_URL,
    LAW_SERVICE_URL,
    LAW_TIMEOUT_SECONDS,
)


class LawApiError(RuntimeError):
    """국가법령정보센터 API 호출 또는 응답 처리 실패."""


def _safe_filename(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", value.strip())
    return value.strip("_") or "law"


def _walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _extract_search_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """API JSON 구조 변화에 대비해 법령 검색 결과를 유연하게 추출한다."""
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in _walk_dicts(payload):
        law_id = str(item.get("법령ID", "")).strip()
        mst = str(item.get("법령일련번호", "")).strip()
        law_name = str(
            item.get("법령명한글")
            or item.get("법령명_한글")
            or item.get("법령명")
            or ""
        ).strip()

        if not law_name or not (law_id or mst):
            continue

        key = (law_id, mst)
        if key in seen:
            continue

        items.append(item)
        seen.add(key)

    return items


class LawApiClient:
    def __init__(
        self,
        *,
        oc: str | None = None,
        timeout_seconds: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.oc = (oc if oc is not None else LAW_API_OC).strip()
        self.timeout_seconds = timeout_seconds or LAW_TIMEOUT_SECONDS
        self.cache_dir = cache_dir or LAW_CACHE_DIR

    @property
    def configured(self) -> bool:
        return bool(self.oc)

    def _require_oc(self) -> None:
        if not self.configured:
            raise LawApiError(
                "LAW_API_OC가 설정되지 않았습니다. .env에 국가법령정보센터 OC 인증값을 입력하세요."
            )

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self._require_oc()

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout_seconds,
                headers={"User-Agent": "I-SPOT/1.0"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LawApiError(f"국가법령정보센터 API 요청 실패: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            preview = response.text[:300].replace("\n", " ")
            raise LawApiError(
                f"국가법령정보센터가 JSON이 아닌 응답을 반환했습니다: {preview}"
            ) from exc

        if not isinstance(payload, dict):
            raise LawApiError("국가법령정보센터 JSON 응답 형식이 예상과 다릅니다.")

        return payload

    def search_laws(
        self,
        query: str,
        *,
        search: int = 1,
        display: int = 20,
        page: int = 1,
    ) -> dict[str, Any]:
        return self._get_json(
            LAW_SEARCH_URL,
            {
                "OC": self.oc,
                "target": "law",
                "type": "JSON",
                "search": search,
                "query": query,
                "display": display,
                "page": page,
            },
        )

    def find_law(self, law_name: str) -> dict[str, Any]:
        payload = self.search_laws(law_name, search=1, display=20)
        items = _extract_search_items(payload)

        if not items:
            raise LawApiError(f"법령 검색 결과가 없습니다: {law_name}")

        exact = [
            item
            for item in items
            if str(
                item.get("법령명한글")
                or item.get("법령명_한글")
                or item.get("법령명")
                or ""
            ).strip()
            == law_name
        ]
        if exact:
            return exact[0]

        contains = [
            item
            for item in items
            if law_name
            in str(
                item.get("법령명한글")
                or item.get("법령명_한글")
                or item.get("법령명")
                or ""
            )
        ]
        return (contains or items)[0]

    def fetch_law_body(
        self,
        *,
        law_id: str | None = None,
        mst: str | None = None,
        article_code: str | None = None,
    ) -> dict[str, Any]:
        if not law_id and not mst:
            raise ValueError("law_id 또는 mst 중 하나가 필요합니다.")

        params: dict[str, Any] = {
            "OC": self.oc,
            "target": "law",
            "type": "JSON",
        }
        if mst:
            params["MST"] = mst
        else:
            params["ID"] = law_id

        if article_code:
            params["JO"] = article_code

        return self._get_json(LAW_SERVICE_URL, params)

    def _cache_path(self, law_name: str) -> Path:
        return self.cache_dir / f"{_safe_filename(law_name)}.json"

    def _is_cache_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_seconds = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        return age_seconds <= LAW_CACHE_MAX_AGE_HOURS * 3600

    def get_law_by_name(
        self,
        law_name: str,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """법령 목록 조회 → 본문 조회 → 로컬 캐시 저장을 한 번에 수행한다."""
        cache_path = self._cache_path(law_name)

        if not refresh and self._is_cache_fresh(cache_path):
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        search_item = self.find_law(law_name)
        law_id = str(search_item.get("법령ID", "")).strip() or None
        mst = str(search_item.get("법령일련번호", "")).strip() or None

        body = self.fetch_law_body(law_id=law_id, mst=mst)
        result = {
            "law_name": law_name,
            "search_item": search_item,
            "body": body,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result
