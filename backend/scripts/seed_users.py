# 초기 계정 생성 script.
#
# 자유 회원가입이 없기 때문에 첫 관리자/상담사 계정은 이 script 로 만든다.
# 비밀번호는 인자 또는 환경변수로 받고, 코드에 하드코딩하지 않는다.
#
# 사용 예:
#   python -m scripts.seed_users --email admin@example.com --name 관리자 --role ADMIN
#   python -m scripts.seed_users --demo        # 개발용 데모 계정 일괄 생성

import argparse
import os
import secrets
import sys
from typing import List, Optional, Tuple

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.user import User

DEMO_ACCOUNTS: List[Tuple[str, str, UserRole]] = [
    ("admin@ispot.example.com", "데모 관리자", UserRole.ADMIN),
    ("counselor@ispot.example.com", "데모 상담사", UserRole.COUNSELOR),
]


def upsert_user(email: str, name: str, role: UserRole, password: str) -> str:
    session = SessionLocal()

    try:
        existing = session.scalar(select(User).where(User.email == email.lower()))

        if existing is not None:
            return f"이미 존재하는 계정입니다: {email} (role={existing.role.value})"

        session.add(
            User(
                email=email.lower(),
                name=name,
                role=role,
                hashed_password=hash_password(password),
                is_active=True,
            )
        )
        session.commit()

        return f"생성 완료: {email} (role={role.value})"
    finally:
        session.close()


def resolve_password(provided: Optional[str]) -> Tuple[str, bool]:
    """
    비밀번호 우선순위: --password → SEED_USER_PASSWORD → 임의 생성
    """

    if provided:
        return provided, False

    from_env = os.getenv("SEED_USER_PASSWORD")

    if from_env:
        return from_env, False

    return secrets.token_urlsafe(12), True


def main() -> int:
    parser = argparse.ArgumentParser(description="I-SPOT 초기 계정 생성")
    parser.add_argument("--email")
    parser.add_argument("--name")
    parser.add_argument(
        "--role",
        choices=[role.value for role in UserRole],
        default=UserRole.COUNSELOR.value,
    )
    parser.add_argument(
        "--password",
        help="미지정 시 SEED_USER_PASSWORD 환경변수 또는 임의 생성값을 사용한다.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="개발용 데모 관리자/상담사 계정을 함께 생성한다.",
    )

    args = parser.parse_args()

    if not args.demo and not (args.email and args.name):
        parser.error("--email 과 --name 을 지정하거나 --demo 를 사용하세요.")

    if args.demo:
        password, generated = resolve_password(args.password)

        for email, name, role in DEMO_ACCOUNTS:
            print(upsert_user(email, name, role, password))

        if generated:
            print(f"\n생성된 공용 데모 비밀번호: {password}")
            print("이 비밀번호는 개발 환경에서만 사용하세요.")

        return 0

    password, generated = resolve_password(args.password)

    print(upsert_user(args.email, args.name, UserRole(args.role), password))

    if generated:
        print(f"\n생성된 비밀번호: {password}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
