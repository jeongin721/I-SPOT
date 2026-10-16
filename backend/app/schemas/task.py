# 처리 대기 업무 Schema.

import uuid
from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel

from app.core.enums import SessionStatus, TaskType


class TaskItem(BaseModel):
    """
    사람이 처리할 차례인 Session 하나.

    아동은 별칭(child_alias)만 내려준다. 상담 원문과 오류 메시지 원문은 넣지 않는다.
    """

    session_id: uuid.UUID
    case_id: uuid.UUID
    case_number: str
    child_alias: str
    session_number: int
    session_title: Optional[str]
    session_status: SessionStatus
    task_type: TaskType

    # 이 상태로 기다리기 시작한 시각(UTC). 오래된 것부터 정렬한다.
    waiting_since: datetime

    # waiting_since 로부터 TASK_OVERDUE_HOURS 가 지났는지
    is_overdue: bool

    counselor_id: uuid.UUID
    counselor_name: Optional[str]

    # RETRY_* 업무에만 값이 있다. 메시지는 Session 상세에서 본다.
    last_error_code: Optional[str]


class TaskSummary(BaseModel):
    """대시보드 숫자. by_type 에는 업무 종류를 항상 모두 넣고, 없으면 0 이다."""

    total: int
    overdue: int
    by_type: Dict[TaskType, int]
