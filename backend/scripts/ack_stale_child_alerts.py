# 아이 앱 '확인 전' 알림 정리 script. 서버에서만 실행한다(2026-11-16).
#
# 아이 앱 기능을 켜기 전에, 시험 · 시연하며 쌓인 확인 안 된 알림(긴급 알림 · 바로 확인 답 · 연락 요청)을 확인 처리한다.
# 그대로 두면 켜자마자 '확인 전' 알림이 모든 상담사 · 관리자 화면 위에 뜨고, 10분 넘기기(#179)가 다른 상담사에게도 보낸다.
#
# 기본은 목록만 보인다(읽기만 함). --apply 를 붙여야 확인 처리한다. 지우지 않는다 — 피드 기록은 그대로 남고
# acknowledged_at 만 채운다. 한 일은 감사 로그 CHILD_APP_ALERT_ACKED 에 행동한 사람(actor) 없이 detail.via 로 남는다.
# 화면 '확인했어요' 와 같은 칸을 쓰므로, 이미 누가 확인한 알림은 건드리지 않는다.
#
# --before(필수, YYYY-MM-DD, 한국 날짜): 그날 0시 전에 생긴 알림만. 오늘 들어온 진짜 알림을 함께 치우지 않게.
# --case(여러 번 가능): 그 사례 번호의 알림만.
# --expect N: --apply 때 대상 수가 N 이 아니면 아무것도 하지 않는다(목록을 본 뒤 그사이 바뀌었으면 멈추게).
# 목록에는 사례 번호 · 종류 · 단계 · 생긴 시각만 나온다(아동 이름 · 아이가 쓴 글은 찍지 않는다).
#
# 사용 예:
#   python -m scripts.ack_stale_child_alerts --before 2026-11-17
#   python -m scripts.ack_stale_child_alerts --before 2026-11-17 --apply --expect 12

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import List, Optional, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.models.case import Case
from app.models.child_app import ChildAppEvent
from app.services import audit_service

VIA = "ack_stale_child_alerts script"
LOCAL_TZ = ZoneInfo("Asia/Seoul")


class CleanupError(Exception):
    """처리하지 않는 경우. 메시지를 그대로 출력한다."""


@dataclass
class StaleAlert:
    id: str
    case_number: str
    kind: str
    level: str
    created_at: datetime


def _cutoff(before: date) -> datetime:
    """한국 날짜 before 의 0시(UTC)."""

    return datetime.combine(before, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def _query(before: date, case_numbers: Sequence[str]):
    query = (
        select(ChildAppEvent, Case.case_number)
        .join(Case, Case.id == ChildAppEvent.case_id)
        .where(
            ChildAppEvent.needs_ack.is_(True),
            ChildAppEvent.acknowledged_at.is_(None),
            ChildAppEvent.created_at < _cutoff(before),
        )
        .order_by(ChildAppEvent.created_at, ChildAppEvent.id)
    )

    if case_numbers:
        query = query.where(Case.case_number.in_(list(case_numbers)))

    return query


def find_stale_alerts(db: Session, before: date, case_numbers: Sequence[str] = ()) -> List[StaleAlert]:
    return [
        StaleAlert(
            id=str(event.id),
            case_number=case_number,
            kind=event.kind.value,
            level=event.level.value,
            created_at=event.created_at,
        )
        for event, case_number in db.execute(_query(before, case_numbers)).all()
    ]


def ack_stale_alerts(
    db: Session,
    before: date,
    case_numbers: Sequence[str] = (),
    *,
    expect: Optional[int] = None,
) -> int:
    """대상 알림을 확인 처리하고 commit 한다. 처리한 수를 돌려준다."""

    rows = db.execute(_query(before, case_numbers).with_for_update(of=ChildAppEvent)).all()

    if expect is not None and len(rows) != expect:
        db.rollback()
        raise CleanupError(f"대상이 {len(rows)}건이라 --expect {expect} 와 다릅니다. 목록을 다시 보고 실행해 주세요.")

    now = datetime.now(timezone.utc)

    for event, _ in rows:
        event.acknowledged_at = now
        event.acknowledged_by_id = None
        audit_service.record(
            db,
            action=AuditAction.CHILD_APP_ALERT_ACKED,
            entity_type="child_app_event",
            entity_id=event.id,
            case_id=event.case_id,
            detail={"via": VIA, "before": before.isoformat()},
        )

    db.commit()

    return len(rows)


def _local(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="아이 앱 '확인 전' 알림 정리 (서버에서만 실행)")
    parser.add_argument("--before", required=True, help="이 한국 날짜 0시 전에 생긴 알림만 (YYYY-MM-DD)")
    parser.add_argument("--case", action="append", default=[], help="이 사례 번호만 (여러 번 가능)")
    parser.add_argument("--apply", action="store_true", help="목록만 보지 않고 확인 처리한다.")
    parser.add_argument("--expect", type=int, default=None, help="--apply 때 대상 수가 이 값일 때만 처리한다.")
    args = parser.parse_args(argv)

    try:
        before = date.fromisoformat(args.before)
    except ValueError:
        print(f"--before 는 YYYY-MM-DD 로 적어 주세요: {args.before}", file=sys.stderr)
        return 2

    session = SessionLocal()

    try:
        if not args.apply:
            alerts = find_stale_alerts(session, before, args.case)
            print(f"확인 전 알림 {len(alerts)}건 ({before.isoformat()} 0시 전, 한국 시각)")

            for alert in alerts:
                print(f"  {alert.case_number}  {alert.kind:<8} {alert.level:<5} {_local(alert.created_at)}  {alert.id[:8]}")

            if alerts:
                print(f"\n처리하려면 같은 명령 끝에 --apply --expect {len(alerts)} 를 붙여 다시 실행하세요.")

            return 0

        count = ack_stale_alerts(session, before, args.case, expect=args.expect)
    except CleanupError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        session.close()

    print(f"확인 처리 {count}건 (감사 로그 via '{VIA}')")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
