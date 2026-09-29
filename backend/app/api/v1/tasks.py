# /tasks — 처리 대기 업무 목록

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Query

from app.api.v1.cases import PageQuery, PageSizeQuery
from app.core.deps import CurrentUser, DbSession
from app.core.enums import TaskType
from app.core.responses import DataResponse, PagedItems, paged
from app.schemas.task import TaskItem, TaskSummary
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])

CounselorQuery = Annotated[
    Optional[uuid.UUID],
    Query(description="담당 상담사로 거르기. 관리자만 쓸 수 있고, 상담사는 본인 id 만 허용한다."),
]


@router.get("", response_model=DataResponse[PagedItems[TaskItem]])
def list_tasks(
    db: DbSession,
    current_user: CurrentUser,
    page: PageQuery = 1,
    page_size: PageSizeQuery = 20,
    task_type: Optional[TaskType] = None,
    overdue_only: bool = False,
    counselor_id: CounselorQuery = None,
) -> DataResponse[PagedItems[TaskItem]]:
    """
    사람이 처리할 차례인 Session 을 오래 기다린 순서로 돌려준다.

    상담사는 담당 사례의 Session 만, 관리자는 전체를 본다. 종결된 사례는 뺀다.
    """

    items, total = task_service.list_tasks(
        db,
        current_user,
        offset=(page - 1) * page_size,
        limit=page_size,
        task_type=task_type,
        overdue_only=overdue_only,
        counselor_id=counselor_id,
    )

    return DataResponse(data=paged(items, total, page, page_size))


@router.get("/summary", response_model=DataResponse[TaskSummary])
def summarize_tasks(
    db: DbSession,
    current_user: CurrentUser,
    counselor_id: CounselorQuery = None,
) -> DataResponse[TaskSummary]:
    """대시보드 숫자. 목록과 같은 권한 · 범위로 센다."""

    return DataResponse(
        data=task_service.summarize_tasks(db, current_user, counselor_id=counselor_id)
    )
