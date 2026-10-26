"""국가법령정보센터 Open API 설정.

jeongin의 RAG(`feature/rag`, 판례 유사사례 검색)는 아직 main에 없고 계속
바뀌는 중이라(2026-10-20 기준), 그쪽 `rag/config.py`를 가져다 쓰지 않고
`law/` 전용 설정을 따로 둔다 — 나중에 `feature/rag`가 머지될 때 같은
이름(`rag/`)끼리 충돌하지 않게 하려는 목적이다. `rag/` 패키지 자체를
만들지 않는다.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 프로젝트 .env를 law 환경변수 읽기 전에 불러온다.
load_dotenv(BASE_DIR / ".env")

# 국가법령정보센터 Open API
LAW_API_OC = os.getenv("LAW_API_OC", "").strip()
LAW_SEARCH_URL = os.getenv(
    "LAW_SEARCH_URL",
    "https://www.law.go.kr/DRF/lawSearch.do",
)
LAW_SERVICE_URL = os.getenv(
    "LAW_SERVICE_URL",
    "https://www.law.go.kr/DRF/lawService.do",
)

# 상담사 화면의 '원문보기'가 여는 국가법령정보센터 포털 (OC 인증값 없이 열람)
LAW_PORTAL_URL = os.getenv(
    "LAW_PORTAL_URL",
    "https://www.law.go.kr/LSW",
).rstrip("/")
# 상대경로(.env의 LAW_CACHE_DIR=law_cache 등)는 실행 위치가 아니라 프로젝트
# 루트 기준으로 푼다 — 다른 폴더에서 실행해도 같은 캐시를 쓰게 하려는 목적.
LAW_CACHE_DIR = Path(os.getenv("LAW_CACHE_DIR", "law_cache")).expanduser()
if not LAW_CACHE_DIR.is_absolute():
    LAW_CACHE_DIR = BASE_DIR / LAW_CACHE_DIR
LAW_TIMEOUT_SECONDS = int(os.getenv("LAW_TIMEOUT_SECONDS", "15"))
LAW_CACHE_MAX_AGE_HOURS = int(os.getenv("LAW_CACHE_MAX_AGE_HOURS", "24"))
LAW_TARGET_LAWS = tuple(
    law_name.strip()
    for law_name in os.getenv(
        "LAW_TARGET_LAWS",
        "아동복지법,아동학대범죄의 처벌 등에 관한 특례법",
    ).split(",")
    if law_name.strip()
)
