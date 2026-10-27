from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .config import (
    LAW_API_OC,
    LAW_CACHE_DIR,
    LAW_CACHE_MAX_AGE_HOURS,
    LAW_SEARCH_URL,
    LAW_SERVICE_URL,
    LAW_TIMEOUT_SECONDS,
)


class LawApiError(RuntimeError):
    """국가법령정보센터 API 호출 또는 응답 처리 실패."""


_OC_PARAM_RE = re.compile(r"(?i)([?&]OC=)[^&\s]*")


def _redact_oc(text: str) -> str:
    """요청 URL의 OC(인증값) 쿼리 파라미터를 ***로 가린다.

    2026-10-26 민규 교차검증으로 발견: requests.RequestException을
    그대로 str()로 찍으면(예: ConnectionError) 실패한 요청의 전체 URL이
    메시지에 들어가는데, 그 URL에 OC=<실제 인증값>이 그대로 박혀 있다.
    이 LawApiError 메시지가 law_qa_llm.py의 답변 텍스트로 그대로
    나가거나 어딘가에 로그로 남으면 인증값이 유출된다. 예외 메시지를
    만드는 시점(여기)에서 한 번만 가리면, 쓰는 쪽에서 매번 신경 쓰지
    않아도 된다.
    """

    return _OC_PARAM_RE.sub(r"\1***", text)


def _redact_secret(text: str, secret: str) -> str:
    """OC 쿼리 파라미터에 더해, 인증값 자체가 어떤 모양으로든(본문 · "OC":"…" · 경로) 나오면 가린다.

    2026-10-27 민규 교차검증 R2: 국가법령정보센터가 JSON 이 아닌 본문을 돌려줄 때 그 본문이
    인증값을 ?OC= 가 아닌 모양으로 담을 수 있다. _redact_oc 의 정규식만으로는 못 가린다.
    """

    text = _redact_oc(text)

    if secret:
        text = text.replace(secret, "***")

    return text


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
            # from None: 원인 예외(요청 URL 에 OC=<인증값>)가 __cause__ 로 이어지면 traceback ·
            # logger.exception 이 그 문구를 그대로 찍는다(2026-10-27 민규 교차검증 R2).
            # 대신 가린 문구와 예외 종류만 남긴다.
            raise LawApiError(
                f"국가법령정보센터 API 요청 실패({type(exc).__name__}): "
                f"{_redact_secret(str(exc), self.oc)}"
            ) from None

        try:
            payload = response.json()
        except ValueError:
            # from None: JSONDecodeError 는 받은 본문 전체(.doc)를 들고 있어 체인으로 남기지 않는다(R2).
            if "미신청" in response.text:
                raise LawApiError(
                    f"국가법령정보센터 OPEN API에서 '{params.get('target')}' 사용 신청이 되어 있지 않습니다. "
                    "open.law.go.kr → OPEN API 신청에서 해당 항목을 체크하세요."
                ) from None
            # 가린 뒤에 자른다 — 먼저 자르면 300자 경계에 걸친 인증값 앞부분이 남는다(민규 교차검증).
            preview = _redact_secret(response.text.replace("\n", " "), self.oc)[:300]
            raise LawApiError(
                f"국가법령정보센터가 JSON이 아닌 응답을 반환했습니다: {preview}"
            ) from None

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

    def search_precedents(
        self,
        query: str,
        *,
        search: int = 2,
        display: int = 5,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        """판례 목록을 검색한다(search=1 사건명, 2 본문). 판례 API 사용 신청이 따로 필요하다."""
        payload = self._get_json(
            LAW_SEARCH_URL,
            {
                "OC": self.oc,
                "target": "prec",
                "type": "JSON",
                "search": search,
                "query": query,
                "display": display,
                "page": page,
            },
        )
        return [
            item
            for item in _walk_dicts(payload)
            if str(item.get("판례일련번호", "")).strip() and item.get("사건명")
        ]

    def get_precedent(self, prec_id: str, *, refresh: bool = False) -> dict[str, Any]:
        """판례 본문(판시사항·판결요지·참조조문)을 조회해 캐시한다. 판례는 바뀌지 않으므로 기한 없이 쓴다."""
        cache_path = self.cache_dir / "precedents" / f"{_safe_filename(prec_id)}.json"
        if not refresh and cache_path.exists():
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        payload = self._get_json(
            LAW_SERVICE_URL,
            {"OC": self.oc, "target": "prec", "type": "JSON", "ID": prec_id},
        )
        body = next(
            (item for item in _walk_dicts(payload) if item.get("사건명") or item.get("판결요지")),
            None,
        )
        if body is None:
            raise LawApiError(f"판례 본문 응답에 내용이 없습니다: {prec_id}")

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        return body

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
        cache_only: bool = False,
    ) -> dict[str, Any]:
        """법령 목록 조회 → 본문 조회 → 로컬 캐시 저장을 한 번에 수행한다.

        cache_only=True 면 네트워크를 부르지 않고 캐시만 읽는다(오래됐어도). 캐시가 없으면 LawApiError.
        회차 분석 도중(STT 검수 관련 조문)에 쓴다 — 국가법령정보센터 요청은 분석 마감(deadline)을
        보지 않아 법령 2개 × (검색 + 본문) × 15초까지 분석이 늘 수 있다(2026-10-27 민규 리뷰).
        캐시 갱신은 분석 밖에서 python -m law.refresh_cache 로 한다.
        """
        cache_path = self._cache_path(law_name)

        if cache_only:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LawApiError(f"법령 캐시를 읽지 못했습니다: {law_name}") from exc

        if not refresh and self._is_cache_fresh(cache_path):
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        try:
            search_item = self.find_law(law_name)
            law_id = str(search_item.get("법령ID", "")).strip() or None
            mst = str(search_item.get("법령일련번호", "")).strip() or None

            body = self.fetch_law_body(law_id=law_id, mst=mst)
        except LawApiError:
            # 새로 받지 못하면(OC 없음 · API 장애) 오래된 캐시라도 쓴다. 법령은 자주 바뀌지 않고,
            # 데모 서버처럼 OC 없이 캐시만 붙여 둔 곳에서 24시간 뒤 조문이 사라지지 않게 한다(2026-10-27).
            # refresh=True 로 일부러 새로 받으려 한 경우와 캐시가 없는 경우는 그대로 실패시킨다.
            if refresh or not cache_path.exists():
                raise
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise
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
