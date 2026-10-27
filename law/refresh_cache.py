"""법령 캐시(law_cache/) 갱신 명령 — 회차 분석 밖에서 돌린다.

    python -m law.refresh_cache

회차 분석(STT 검수 '관련 조문')은 캐시만 읽고 국가법령정보센터를 부르지 않는다
(law/client.get_law_by_name 의 cache_only, 2026-10-27 민규 리뷰). 그래서 법령이 개정되면
LAW_API_OC 가 있는 곳에서 이 명령으로 캐시를 새로 받는다. 데모 서버 컨테이너에서는

    docker exec ispot-backend python -m law.refresh_cache

로 붙여 둔 /law_cache 를 갱신한다(backend.env 에 LAW_API_OC 가 있어야 함).
"""

from __future__ import annotations

import sys

from .client import LawApiClient, LawApiError
from .config import LAW_CACHE_DIR, LAW_TARGET_LAWS


def main() -> int:
    client = LawApiClient()

    if not client.configured:
        print("LAW_API_OC 가 없어 갱신하지 않습니다(분석은 지금 캐시를 그대로 씁니다).")
        return 1

    failed = 0

    for law_name in LAW_TARGET_LAWS:
        try:
            client.get_law_by_name(law_name, refresh=True)
            print(f"갱신: {law_name}")
        except LawApiError as error:
            failed += 1
            print(f"실패: {law_name} ({error})")

    print(f"캐시 위치: {LAW_CACHE_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
