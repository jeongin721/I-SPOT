# 회차 번호 빈 곳 메우기. 서버에서만 실행한다(2026-11-20).
#
# 잘못 올린 회차를 '번호를 비워 두기'로 지웠거나(또는 당기기 기능이 생기기 전에 지워) 1, 2, 5 처럼 번호가 빈 사례를
# 1, 2, 3 으로 다시 맞춘다. 순서는 그대로(작은 번호부터), 회차는 ID 로 묶여 있어 원문 · 분석 · 확인 사항은 따라간다.
# 이미 내려받은 문서 · 폰 녹음 파일 이름의 번호는 바뀌지 않는다.
#
# 기본은 보기만 한다(무엇이 바뀔지 출력). --apply 를 주면 바꾸고 감사 로그(SESSION_RENUMBERED, detail.via)에 남긴다.
#
# 사용 예:
#   python -m scripts.renumber_sessions --case C-2026-0005
#   python -m scripts.renumber_sessions --case C-2026-0005 --apply

import argparse
import sys
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.models.case import Case
from app.models.session import ConsultationSession
from app.services import audit_service

VIA = "renumber_sessions script"


class RenumberError(Exception):
    """바꾸지 않는 경우. 메시지를 그대로 출력한다."""


def plan(db: Session, case_number: str) -> tuple[Case, List[ConsultationSession], List[List[int]]]:
    case = db.scalar(select(Case).where(Case.case_number == case_number))

    if case is None:
        raise RenumberError(f"사례를 찾을 수 없습니다: {case_number}")

    rows = list(
        db.scalars(
            select(ConsultationSession)
            .where(ConsultationSession.case_id == case.id)
            .order_by(ConsultationSession.session_number.asc())
            .with_for_update()
        )
    )
    moves = [[row.session_number, index] for index, row in enumerate(rows, start=1) if row.session_number != index]

    return case, rows, moves


def renumber(db: Session, case_number: str, *, apply: bool = False) -> List[List[int]]:
    """[[옛 번호, 새 번호], …]. apply 면 바꾸고 commit 한다. 작은 번호부터 줄이므로 중간에 번호가 겹치지 않는다."""

    case, rows, moves = plan(db, case_number)

    if not apply or not moves:
        db.rollback()
        return moves

    for index, row in enumerate(rows, start=1):
        if row.session_number != index:
            row.session_number = index
            db.flush()

    audit_service.record(
        db,
        action=AuditAction.SESSION_RENUMBERED,
        entity_type="Case",
        entity_id=case.id,
        case_id=case.id,
        detail={"via": VIA, "renumbered": moves},
    )
    db.commit()

    return moves


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="사례의 비어 있는 회차 번호를 1, 2, 3… 으로 당긴다.")
    parser.add_argument("--case", required=True, help="사례 번호(예: C-2026-0005)")
    parser.add_argument("--apply", action="store_true", help="실제로 바꾼다. 빼면 보기만 한다.")
    args = parser.parse_args(argv)

    db = SessionLocal()

    try:
        moves = renumber(db, args.case.strip(), apply=args.apply)
    except RenumberError as error:
        print(error)
        return 1
    finally:
        db.close()

    if not moves:
        print("비어 있는 번호가 없습니다. 바꿀 것이 없습니다.")
        return 0

    for old, new in moves:
        print(f"{old}회차 → {new}회차")

    print("바꿨습니다(감사 로그에 남음)." if args.apply else "보기만 했습니다. 바꾸려면 --apply 를 붙여 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
