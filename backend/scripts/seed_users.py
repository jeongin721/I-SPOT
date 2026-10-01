# 초기 계정 생성 script.
#
# 자유 회원가입이 없기 때문에 첫 관리자/상담사 계정은 이 script 로 만든다.
# 비밀번호는 인자 또는 환경변수로 받고, 코드에 하드코딩하지 않는다.
# 직접 준 비밀번호도 API 와 같은 비밀번호 규칙(app/core/password_policy.py)을 거친다.
# 맞지 않으면 계정을 만들지 않고 사유를 출력한 뒤 종료 코드 1 로 끝난다.
# 이미 있는 계정은 건드리지 않는다(비밀번호도 그대로다). 그래서 비밀번호는 계정을 새로 만들었을 때만
# 출력하고, 건너뛴 계정이 있으면 비밀번호를 모를 때 푸는 방법을 안내한다.
#
# 사용 예:
#   python -m scripts.seed_users --email admin@example.com --name 관리자 --role ADMIN
#   python -m scripts.seed_users --demo        # 개발용 데모 계정 일괄 생성

import argparse
import os
import sys
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.enums import AuditAction, UserRole
from app.core.errors import APIError
from app.core.password_policy import generate_password, validate_password
from app.core.security import hash_password
from app.models.user import User
from app.services import audit_service

DEMO_ACCOUNTS: List[Tuple[str, str, UserRole]] = [
    ("admin@ispot.example.com", "데모 관리자", UserRole.ADMIN),
    ("counselor@ispot.example.com", "데모 상담사", UserRole.COUNSELOR),
]


EXISTING_ACCOUNT_NOTICE = (
    "이미 있는 계정의 비밀번호는 바뀌지 않았습니다. 모르면 DB 를 지우고(backend/README.md 부록 A.7) "
    "다시 만들거나 python -m scripts.unlock_user --email <이메일> --reset-password 를 쓰세요."
)


def upsert_user(email: str, name: str, role: UserRole, password: str) -> Tuple[str, bool]:
    """
    계정이 없으면 만든다. (출력할 문구, 새로 만들었는지)를 돌려준다.

    이미 있는 계정은 아무것도 바꾸지 않는다. 비밀번호도 그대로다.
    """

    session = SessionLocal()

    try:
        existing = session.scalar(select(User).where(User.email == email.lower()))

        if existing is not None:
            return f"이미 존재하는 계정입니다: {email} (role={existing.role.value})", False

        user = User(
            email=email.lower(),
            name=name,
            role=role,
            hashed_password=hash_password(password),
            is_active=True,
        )

        session.add(user)
        session.flush()

        # 서버에서 직접 만든 계정이라 행동한 사람(actor)이 없다. API 로 만든 계정과 구분되게 남긴다.
        audit_service.record(
            session,
            action=AuditAction.USER_CREATED,
            entity_type="User",
            entity_id=user.id,
            detail={"role": role.value, "via": "seed_users script"},
        )
        session.commit()

        return f"생성 완료: {email} (role={role.value})", True
    finally:
        session.close()


def report_password(
    password: str,
    generated: bool,
    created: List[str],
    skipped: List[str],
    *,
    label: str,
    dev_only: bool = False,
) -> None:
    """
    비밀번호 안내를 출력한다. 계정을 새로 만들었을 때만 그 비밀번호를 알려 준다.

    이미 있는 계정은 비밀번호가 바뀌지 않으므로, 새로 만든 값을 출력하면 쓸 수 없는 값을 알려 주게 된다.
    그 값으로 5번 틀리면 계정이 잠긴다(unlock_user 로 푼다).
    """

    if created and generated:
        print(f"\n{label}: {password}")

        if dev_only:
            print("이 비밀번호는 개발 환경에서만 사용하세요.")

    if created and skipped:
        source = "위" if generated else "--password · SEED_USER_PASSWORD 로 준"
        print(f"{source} 비밀번호는 새로 만든 계정에만 적용됐습니다: {', '.join(created)}")

    if skipped:
        print(EXISTING_ACCOUNT_NOTICE)


def resolve_password(provided: Optional[str]) -> Tuple[str, bool]:
    """
    비밀번호 우선순위: --password → SEED_USER_PASSWORD → 임의 생성
    """

    if provided:
        return provided, False

    from_env = os.getenv("SEED_USER_PASSWORD")

    if from_env:
        return from_env, False

    return generate_password(), True


def check_given_password(password: str, accounts: Iterable[Tuple[str, str]]) -> bool:
    """
    직접 준 비밀번호가 규칙에 맞는지 본다. 맞지 않으면 사유를 출력하고 False.

    --demo 는 계정 여러 개에 같은 비밀번호를 쓰므로 계정마다 이메일 · 이름 기준으로 본다.
    비밀번호 원문은 출력하지 않는다.
    """

    for email, name in accounts:
        try:
            validate_password(password, email=email, name=name)
        except APIError as error:
            reasons = (error.details or {}).get("reasons", [])

            print(f"비밀번호가 규칙에 맞지 않습니다({email}).", file=sys.stderr)

            for reason in reasons:
                print(f"  - {reason}", file=sys.stderr)

            return False

    return True


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
        accounts = list(DEMO_ACCOUNTS)
        label = "생성된 공용 데모 비밀번호"
    else:
        accounts = [(args.email, args.name, UserRole(args.role))]
        label = "생성된 비밀번호"

    password, generated = resolve_password(args.password)

    if not generated and not check_given_password(
        password, [(email, name) for email, name, _ in accounts]
    ):
        return 1

    created: List[str] = []
    skipped: List[str] = []

    for email, name, role in accounts:
        message, was_created = upsert_user(email, name, role, password)
        print(message)
        (created if was_created else skipped).append(email)

    report_password(password, generated, created, skipped, label=label, dev_only=args.demo)

    return 0


if __name__ == "__main__":
    sys.exit(main())
