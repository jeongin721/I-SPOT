# Logging 설정.
#
# docs/05_RULES.md 절대 금지: "상담 원문 전체를 일반 로그에 출력".
# 따라서 로그에는 식별자/개수/길이 등 metadata 만 남기고,
# 발화 텍스트는 redact_text() 를 거친 형태만 허용한다.

import logging
import sys
from typing import Optional

from app.core.config import settings

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED

    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL.upper())

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def redact_text(text: Optional[str]) -> str:
    """
    상담 발화 텍스트를 로그에 남겨야 할 때 반드시 이 함수를 거친다.
    내용은 남기지 않고 길이만 남긴다.
    """

    if text is None:
        return "<none>"

    return f"<redacted len={len(text)}>"
