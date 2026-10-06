# 계정 복구 script. 서버에서만 실행한다.
#
# 관리자가 한 명뿐인데 그 계정이 잠기면 관리자 화면으로는 풀 방법이 없다.
# 로그인 실패 잠금은 이메일만 알면 누구든 5번 틀려서 걸 수 있다.
# 그때 서버에 접속해 이 script 로 푼다. 같은 일을 하는 API 는 만들지 않는다.
#
# 기본 동작: 실패 잠금 해제, 휴면이면 휴면 해제.
# 비활성 계정은 --activate 를 줄 때만 활성화한다. 관리자가 일부러 정지했을 수 있다.
# --reset-password 를 주면 임시 비밀번호를 새로 발급해 한 번만 출력한다.
# 바꾼 것은 모두 감사 로그에 행동한 사람(actor) 없이 detail.via 로 남는다.
#
# 사용 예:
#   python -m scripts.unlock_user --email admin@example.com
#   python -m scripts.unlock_user --email admin@example.com --reset-password
#   python -m scripts.unlock_user --email admin@example.com --activate

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.models.user import User
from app.services import account_service, audit_service

VIA = "unlock_user script"


class RecoveryError(Exception):
    """복구하지 않는 경우. 메시지를 그대로 출력한다."""


@dataclass
class RecoveryResult:
    role: str
    done: List[str] = field(default_factory=list)
    notices: List[str] = field(default_factory=list)
    temporary_password: Optional[str] = None


def recover_user(
    db: Session,
    email: str,
    *,
    activate: bool = False,
    reset_password: bool = False,
) -> RecoveryResult:
    """
    계정을 다시 로그인할 수 있게 만든다. commit 까지 한다.

    퇴사 처리(비식별)된 계정은 되살리지 않는다.
    """

    user = db.scalar(select(User).where(User.email == email.lower()))

    if user is None:
        raise RecoveryError(f"계정을 찾을 수 없습니다: {email}")

    if user.anonymized_at is not None:
        raise RecoveryError(f"퇴사 처리된 계정은 복구하지 않습니다: {email}")

    now = datetime.now(timezone.utc)
    result = RecoveryResult(role=user.role.value)

    def record(action: AuditAction, detail: Optional[Dict[str, Any]] = None) -> None:
        audit_service.record(
            db,
            action=action,
            entity_type="User",
            entity_id=user.id,
            detail={"via": VIA, **(detail or {})},
        )

    # 1. 실패 잠금 — 잠겨 있지 않아도 실패 횟수를 비운다(관리자 화면의 잠금 해제와 같다).
    was_locked = user.is_locked_at(now)

    user.failed_login_count = 0
    user.locked_until = None
    record(AuditAction.ACCOUNT_UNLOCKED)
    result.done.append("실패 잠금 해제" if was_locked else "실패 횟수 초기화(잠겨 있지 않았음)")

    # 2. 휴면 — 푸는 것 자체를 활동으로 본다. 비워 두면 다음 로그인에 곧바로 다시 휴면이 된다.
    if user.dormant_at is not None:
        user.dormant_at = None
        user.last_login_at = now
        record(AuditAction.ACCOUNT_REACTIVATED)
        result.done.append("휴면 해제")

        if not reset_password:
            result.notices.append(
                "관리자 화면의 휴면 해제와 달리 비밀번호는 그대로입니다. "
                "새로 받으려면 --reset-password 를 붙이세요."
            )

    # 3. 비활성 — 관리자가 일부러 정지했을 수 있어 --activate 가 있을 때만 켠다.
    if not user.is_active:
        if activate:
            user.is_active = True
            # 관리자 화면에서 활성 상태를 바꿀 때와 같이 이전 Token 을 무효로 만든다.
            user.token_version += 1
            record(AuditAction.USER_UPDATED, {"changed_fields": ["is_active"]})
            result.done.append("활성화")
        else:
            result.notices.append("비활성 계정입니다. 활성화하려면 --activate 를 붙이세요.")

    # 4. 임시 비밀번호 — 이전 비밀번호 이력 규칙은 발급 함수가 지킨다.
    if reset_password:
        result.temporary_password = account_service.issue_temporary_password(db, user)
        record(AuditAction.PASSWORD_RESET)
        result.done.append("임시 비밀번호 발급")

    db.commit()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="I-SPOT 계정 복구 (서버에서만 실행)")
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--activate",
        action="store_true",
        help="비활성 계정이면 활성화한다.",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="임시 비밀번호를 새로 발급해 한 번만 출력한다.",
    )

    args = parser.parse_args()

    session = SessionLocal()

    try:
        result = recover_user(
            session,
            args.email,
            activate=args.activate,
            reset_password=args.reset_password,
        )
    except RecoveryError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        session.close()

    print(f"복구 완료: {args.email} (role={result.role})")

    for line in result.done:
        print(f"  - {line}")

    for line in result.notices:
        print(f"  ! {line}")

    if result.temporary_password:
        print(f"\n임시 비밀번호: {result.temporary_password}")
        print(
            f"이 값은 다시 볼 수 없습니다. {settings.TEMP_PASSWORD_VALID_HOURS}시간 안에 "
            "로그인해 새 비밀번호로 바꿔야 합니다."
        )
        print(
            "바꾸기 전에는 내 정보 확인 · 비밀번호 변경 말고는 모두 403 PASSWORD_CHANGE_REQUIRED 입니다"
            "(seed_demo_data 포함). 바꾸는 방법은 backend/README.md 2.5."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
