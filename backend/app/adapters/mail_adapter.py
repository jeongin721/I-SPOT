# 메일 발송기 — 회원가입 인증번호(2026-11-02, API_CONTRACT 3절 '회원가입'). 비밀번호 찾기(9/18 회의)도 이것을 쓰면 된다.
#
# MAIL_PROVIDER 로 고른다.
#  - fake: 보내지 않고 프로세스 메모리(outbox)에 담는다. 시험이 읽는다. 로그에는 받는 주소 · 본문을 남기지 않는다.
#  - console: 받는 주소 · 본문을 표준 출력에 찍는다. 로컬에서 화면을 붙여 볼 때만 쓴다(인증번호가 보인다).
#    ENV=production 이면 서버가 뜨지 않는다(config._block_console_mail_in_production).
#  - ses: AWS SES v2 send_email(글자만, UTF-8). 자격은 boto3 가 EC2 역할(인스턴스 메타데이터)에서 받는다 — 접근 키를
#    설정에 두지 않는다. boto3 는 처음 보낼 때 import 한다(시험 · 로컬은 boto3 없이도 돈다).
#
# 실패는 MailSendError 하나로 올리고 원래 예외 문구는 버린다. SES 의 거절 문구에는 받는 주소가 들어 있다
# (샌드박스에서 인증 안 된 받는 주소 등). 남기는 것은 SES 오류 코드나 예외 종류 이름뿐이다.

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from app.core.config import settings

# SES 호출 제한 시간(초)과 시도 횟수(처음 + 재시도 2번). 메일은 응답을 보낸 뒤 보내므로 화면을 붙잡지 않는다.
SES_CONNECT_TIMEOUT_SECONDS = 5
SES_READ_TIMEOUT_SECONDS = 10
SES_TOTAL_ATTEMPTS = 3

# 남길 SES 오류 코드 모양(MessageRejected · Throttling 등). 이 모양이 아니면 예외 종류 이름만 남긴다.
_ERROR_CODE = re.compile(r"^[A-Za-z][A-Za-z0-9.]{0,63}$")


@dataclass(frozen=True)
class MailMessage:
    to: str
    subject: str
    body: str


class MailSendError(Exception):
    """보내기 실패. cause 는 SES 오류 코드나 예외 종류 이름이다(주소 · 본문 · 원래 문구 없음)."""

    def __init__(self, cause: str) -> None:
        super().__init__(cause)
        self.cause = cause


class MailSender(Protocol):
    name: str

    def send(self, message: MailMessage) -> None:
        ...


def failure_cause(error: BaseException) -> str:
    """감사 기록 · 로그에 남길 실패 이유. 예외 문구(str(error))는 쓰지 않는다."""

    if isinstance(error, MailSendError):
        return error.cause

    response: Any = getattr(error, "response", None)

    if isinstance(response, dict):
        code = (response.get("Error") or {}).get("Code")

        if isinstance(code, str) and _ERROR_CODE.match(code):
            return code

    return type(error).__name__


def _quiet_aws_loggers() -> None:
    """
    botocore · boto3 로거를 WARNING 이상으로 올린다.

    서버 로그 수준은 LOG_LEVEL 을 루트 로거에 그대로 쓴다(app/core/logging.py). DEBUG 로 두면 botocore 가 보내는 요청 내용
    (받는 주소 · 본문의 인증번호)을 찍는다. 이미 더 높게 잡혀 있으면 그대로 둔다.
    """

    for name in ("botocore", "boto3"):
        aws_logger = logging.getLogger(name)

        if aws_logger.getEffectiveLevel() < logging.WARNING:
            aws_logger.setLevel(logging.WARNING)


class FakeMailSender:
    """보내지 않는다. 시험이 outbox 를 읽는다."""

    name = "fake"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._outbox: List[MailMessage] = []

    def send(self, message: MailMessage) -> None:
        with self._lock:
            self._outbox.append(message)

    def outbox(self) -> List[MailMessage]:
        with self._lock:
            return list(self._outbox)

    def clear(self) -> None:
        with self._lock:
            self._outbox.clear()


class ConsoleMailSender:
    """표준 출력에 찍는다(로컬 전용). logging 을 쓰지 않는다 — 로그 모음에 인증번호가 섞이지 않게."""

    name = "console"

    def send(self, message: MailMessage) -> None:
        print(
            f"[메일 · console] 받는 주소: {message.to}\n제목: {message.subject}\n\n{message.body}",
            flush=True,
        )


class SesMailSender:
    """AWS SES v2. client 는 시험에서 가짜를 넣을 때만 준다."""

    name = "ses"

    def __init__(self, client: Any = None) -> None:
        self._lock = threading.Lock()
        self._client = client

    def _get_client(self) -> Any:
        # boto3 의 client 만들기는 스레드에 안전하지 않다(기본 Session 을 함께 쓴다). 만든 client 는 함께 써도 된다.
        with self._lock:
            if self._client is None:
                _quiet_aws_loggers()

                import boto3
                from botocore.config import Config

                self._client = boto3.client(
                    "sesv2",
                    region_name=settings.SES_REGION,
                    config=Config(
                        connect_timeout=SES_CONNECT_TIMEOUT_SECONDS,
                        read_timeout=SES_READ_TIMEOUT_SECONDS,
                        retries={"total_max_attempts": SES_TOTAL_ATTEMPTS, "mode": "standard"},
                    ),
                )

            return self._client

    def send(self, message: MailMessage) -> None:
        try:
            self._get_client().send_email(
                FromEmailAddress=settings.SES_FROM_ADDRESS,
                Destination={"ToAddresses": [message.to]},
                Content={
                    "Simple": {
                        "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": message.body, "Charset": "UTF-8"}},
                    }
                },
            )
        except Exception as error:
            # from None: 원래 예외(문구에 받는 주소가 든)를 이어 붙이지 않는다. 누가 traceback 을 찍어도 남지 않게.
            raise MailSendError(failure_cause(error)) from None


# =========================================================
# Factory
# =========================================================

_fake = FakeMailSender()
_ses: Optional[SesMailSender] = None
_ses_lock = threading.Lock()
_override: Optional[MailSender] = None


def set_mail_sender_override(sender: Optional[MailSender]) -> None:
    """시험에서 실패하는 발송기 등을 넣는 hook. None 이면 MAIL_PROVIDER 를 따른다."""

    global _override
    _override = sender


def fake_outbox() -> List[MailMessage]:
    """fake 발송기가 받은 메일(시험용)."""

    return _fake.outbox()


def clear_fake_outbox() -> None:
    _fake.clear()


def get_mail_sender() -> MailSender:
    global _ses

    if _override is not None:
        return _override

    if settings.MAIL_PROVIDER == "ses":
        with _ses_lock:
            if _ses is None:
                _ses = SesMailSender()

            return _ses

    if settings.MAIL_PROVIDER == "console":
        return ConsoleMailSender()

    return _fake


__all__ = [
    "ConsoleMailSender",
    "FakeMailSender",
    "MailMessage",
    "MailSendError",
    "MailSender",
    "SesMailSender",
    "clear_fake_outbox",
    "failure_cause",
    "fake_outbox",
    "get_mail_sender",
    "set_mail_sender_override",
]
