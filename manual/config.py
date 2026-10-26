"""2026년 아동학대 대응 업무 매뉴얼(서식·참고자료) 설정.

law/config.py와 같은 이유로(jeongin의 feature/rag, 아직 main에 없고 계속
바뀌는 중) 별도 패키지로 둔다 — rag/ 네임스페이스와 겹치지 않는다.

매뉴얼 원본은 PDF가 아니라 실물 책자를 촬영한 사진(카카오톡 전송본)이라
텍스트 레이어가 없다. 이미지 파일 자체는 (1) 용량이 크고 (2) 저작권이
있는 정부 발간물 원본이라, law_cache/나 참고용 PDF들과 같은 규칙으로
git에 커밋하지 않는다(.gitignore 참고) — 이 폴더는 로컬에만 있으면
된다.
"""

from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

MANUAL_IMAGE_DIR = Path(
    os.getenv("MANUAL_IMAGE_DIR", BASE_DIR / "사례관리_업무")
)
