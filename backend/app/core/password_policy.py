# 비밀번호 규칙.
#
# 규칙은 "새로 정하는 비밀번호" 에만 적용한다. 로그인 요청에는 적용하지 않는다.
# 이미 있는 계정이 전부 잠기기 때문이다.

import re
import secrets
import string
import unicodedata
from typing import Iterable, List, Optional

from app.core.config import settings
from app.core.errors import APIError, ErrorCode

# bcrypt 는 72 byte 를 넘는 입력을 조용히 잘라낸다.(app/core/security.py)
# 잘린 뒤쪽은 검증에 쓰이지 않으므로 애초에 거부한다.
MAX_BYTES = 72

_REPEATED = re.compile(r"(.)\1{3,}")
_TOKEN_SPLIT = re.compile(r"[^0-9A-Za-z]+")

# 최소 길이. 이보다 짧은 이메일 아이디 · 이름 조각은 비교하지 않는다.
_TOKEN_MIN_LENGTH = 4

# 연속 문자로 볼 길이. "abc" 는 통과하고 "abcd" 는 막는다.
_SEQUENCE_RUN = 4

# 흔한 비밀번호와 서비스 이름. 부분 문자열로 들어 있어도 거부한다.
# 사람들이 뒤에 숫자만 붙이기 때문에 정확히 일치만 보면 막지 못한다.
_BANNED_WORDS = (
    "ispot",
    "password",
    "passwd",
    "qwerty",
    "iloveyou",
    "letmein",
    "welcome",
    "admin",
    "root",
    "master",
    "dragon",
    "monkey",
    "football",
    "baseball",
    "sunshine",
    "princess",
    "trustno1",
    "changeme",
    "secret",
    "login",
    "hello",
    "freedom",
    "whatever",
    "samsung",
    "korea",
    "seoul",
    "computer",
    "internet",
    "abc123",
)

_SEQUENCES = (
    string.ascii_lowercase,
    string.digits,
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
    "1qaz2wsx",
)


def _character_classes(password: str) -> int:
    """
    섞여 있는 글자 종류 수. 글자 · 숫자 · 특수문자 3가지로 센다.

    팀 회의 결정(2026-09-18)이 "영문 · 숫자 · 특수문자를 포함" 이므로
    대문자와 소문자를 나누지 않는다. 나누면 `Abcdefgh1` 처럼
    특수문자가 없어도 3종류가 되어 결정과 어긋난다.

    한글도 글자로 센다. 안 세면 한글 비밀번호는 20자 미만에서 모두 거부된다.
    """

    letter = digit = symbol = False

    for char in password:
        if char.isalpha():
            letter = True
        elif char.isdigit():
            digit = True
        else:
            symbol = True

    return sum((letter, digit, symbol))


def _tokens(*values: Optional[str]) -> Iterable[str]:
    for value in values:
        if not value:
            continue

        lowered = value.lower()

        # 한글 이름은 아래 정규식에서 구분자로 잘려 사라진다.
        # 영문·숫자가 아닌 조각은 따로 통째로 비교한다.
        for part in lowered.split():
            if len(part) >= 2 and not part.isascii():
                yield part

        for token in _TOKEN_SPLIT.split(lowered):
            if len(token) >= _TOKEN_MIN_LENGTH:
                yield token


def _has_sequence(lowered: str) -> bool:
    for index in range(len(lowered) - _SEQUENCE_RUN + 1):
        chunk = lowered[index : index + _SEQUENCE_RUN]

        for sequence in _SEQUENCES:
            if chunk in sequence or chunk in sequence[::-1]:
                return True

    return False


def check_password(
    password: str,
    *,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> List[str]:
    """위반 사유 목록을 돌려준다. 빈 목록이면 통과다."""

    reasons: List[str] = []

    # 저장될 형태와 같은 표기로 본다.(app/core/security.py 와 같은 규칙)
    password = unicodedata.normalize("NFC", password)
    byte_length = len(password.encode("utf-8"))

    if password != password.strip():
        reasons.append("앞이나 뒤에 공백을 넣을 수 없습니다.")

    if byte_length > MAX_BYTES:
        reasons.append(
            f"{MAX_BYTES}바이트(한글 24자)를 넘을 수 없습니다. 지금 {byte_length}바이트입니다."
        )

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        reasons.append(f"{settings.PASSWORD_MIN_LENGTH}자 이상이어야 합니다.")

    if (
        len(password) < settings.PASSWORD_PASSPHRASE_LENGTH
        and _character_classes(password) < settings.PASSWORD_MIN_CLASSES
    ):
        reasons.append(
            f"영문(한글도 됩니다) · 숫자 · 특수문자 중 {settings.PASSWORD_MIN_CLASSES}종류 이상을 "
            f"섞어야 합니다. {settings.PASSWORD_PASSPHRASE_LENGTH}자 이상이면 섞지 않아도 됩니다."
        )

    lowered = password.lower()

    if any(word in lowered for word in _BANNED_WORDS):
        reasons.append("쉽게 짐작할 수 있는 단어가 들어 있습니다.")

    email_id = email.split("@")[0] if email else None

    if any(token in lowered for token in _tokens(email_id, name)):
        reasons.append("이메일 아이디나 이름을 비밀번호에 넣을 수 없습니다.")

    if _REPEATED.search(lowered):
        reasons.append("같은 문자를 4번 이상 반복할 수 없습니다.")

    if _has_sequence(lowered):
        reasons.append("연속된 문자(1234 · qwer 같은 것)를 넣을 수 없습니다.")

    return reasons


def validate_password(
    password: str,
    *,
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> None:
    """규칙에 맞지 않으면 WEAK_PASSWORD 로 거부한다. 비밀번호 원문은 오류에 담지 않는다."""

    reasons = check_password(password, email=email, name=name)

    if reasons:
        raise APIError(
            ErrorCode.WEAK_PASSWORD,
            "비밀번호가 규칙에 맞지 않습니다.",
            status_code=422,
            details={"reasons": reasons},
        )


def generate_password(length: int = 16) -> str:
    """규칙을 통과하는 임의 비밀번호. 임시 비밀번호 발급과 seed script 가 쓴다."""

    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+?"

    # 설정 최소 길이가 기본값보다 크면 그 길이로 만든다. 안 맞추면 영원히 실패한다.
    length = max(length, settings.PASSWORD_MIN_LENGTH)

    for _ in range(100):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))

        if not check_password(candidate):
            return candidate

    raise RuntimeError("규칙을 통과하는 비밀번호를 만들지 못했습니다. 설정값을 확인해 주세요.")
