from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from .config import LAW_PORTAL_URL


def _pad_number(value: Any, width: int) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits.zfill(width) if digits else ""


def build_portal_url(
    law_serial_no: Any,
    *,
    article_number: Any = "",
    article_branch: Any = "",
) -> str:
    """국가법령정보센터 법령 본문 화면을 해당 조문 위치로 여는 주소를 만든다.

    lsInfoP.do는 포털의 법령 본문 화면(목차·연혁·3단비교 메뉴 포함)이며,
    joNo를 주면 본문을 불러온 뒤 그 조문으로 이동한다.
    포털은 joBrNo를 무시하므로 '제10조의2' 같은 가지조문은 본조(제10조) 위치에서 열린다.

    API 응답의 법령상세링크에는 OC 인증값이 들어 있어 화면에 내려보내지 않는다.
    대신 같은 응답의 법령일련번호(MST)를 써서 화면에 보여준 조문과 같은 시행 버전을 연다.
    """
    serial_no = str(law_serial_no or "").strip()
    if not serial_no:
        return ""

    params = {"lsiSeq": serial_no}
    article_no = _pad_number(article_number, 4)
    if article_no:
        params["joNo"] = article_no
        params["joBrNo"] = _pad_number(article_branch, 2) or "00"
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
            ),
        }
        for article in articles
    ]
