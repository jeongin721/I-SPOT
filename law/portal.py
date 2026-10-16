from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from rag.config import LAW_PORTAL_URL


def _pad_number(value: Any, width: int) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits.zfill(width) if digits else ""


def build_portal_url(
    law_serial_no: Any,
    *,
    article_number: Any = "",
    article_branch: Any = "",
    effective_date: Any = "",
) -> str:
    """국가법령정보센터 포털에서 조문(없으면 법령 본문)을 여는 주소를 만든다.

    API 응답의 법령상세링크에는 OC 인증값이 들어 있어 화면에 내려보내지 않는다.
    대신 같은 응답의 법령일련번호(MST)로 인증값 없는 포털 주소를 만든다.
    법령명 대신 일련번호를 쓰므로 화면에 보여준 조문과 같은 시행 버전이 열린다.
    """
    serial_no = str(law_serial_no or "").strip()
    if not serial_no:
        return ""

    article_no = _pad_number(article_number, 4)
    if article_no:
        params = {
            "lsiSeq": serial_no,
            "joNo": article_no,
            "joBrNo": _pad_number(article_branch, 2) or "00",
            "docCls": "jo",
            "urlMode": "lsScJoRltInfoR",
        }
        return f"{LAW_PORTAL_URL}/lsSideInfoP.do?{urlencode(params)}"

    params = {"lsiSeq": serial_no}
    effective = _pad_number(effective_date, 8)
    if effective:
        params["efYd"] = effective
    return f"{LAW_PORTAL_URL}/lsInfoP.do?{urlencode(params)}"


def attach_portal_urls(
    articles: list[dict[str, Any]],
    search_item: dict[str, Any],
) -> list[dict[str, Any]]:
    """조문 목록 각 항목에 portal_url을 붙인다. 원본 목록은 수정하지 않는다."""
    serial_no = search_item.get("법령일련번호", "")
    return [
        {
            **article,
            "portal_url": build_portal_url(
                serial_no,
                article_number=article.get("article_number", ""),
                article_branch=article.get("article_branch", ""),
                effective_date=article.get("effective_date", ""),
            ),
        }
        for article in articles
    ]
