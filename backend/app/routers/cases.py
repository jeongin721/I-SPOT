from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AppError
from app.models import Case, ConsultSession
from app.schemas import (
    CaseCreate,
    CaseOut,
    DataEnvelope,
    SessionCreate,
    SessionOut,
)

router = APIRouter(prefix="/cases", tags=["cases"])


def _get_case_or_404(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise AppError("CASE_NOT_FOUND", f"Case {case_id} not found", status_code=404)
    return case


@router.get("", response_model=DataEnvelope[list[CaseOut]])
def list_cases(db: Session = Depends(get_db)) -> DataEnvelope[list[CaseOut]]:
    cases = db.scalars(select(Case).order_by(Case.created_at.desc())).all()
    return DataEnvelope(data=[CaseOut.model_validate(c) for c in cases])


@router.post("", response_model=DataEnvelope[CaseOut], status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)) -> DataEnvelope[CaseOut]:
    case = Case(title=payload.title, description=payload.description)
    db.add(case)
    db.commit()
    db.refresh(case)
    return DataEnvelope(data=CaseOut.model_validate(case))


@router.get("/{case_id}", response_model=DataEnvelope[CaseOut])
def get_case(case_id: str, db: Session = Depends(get_db)) -> DataEnvelope[CaseOut]:
    case = _get_case_or_404(db, case_id)
    return DataEnvelope(data=CaseOut.model_validate(case))


@router.get("/{case_id}/sessions", response_model=DataEnvelope[list[SessionOut]])
def list_sessions(case_id: str, db: Session = Depends(get_db)) -> DataEnvelope[list[SessionOut]]:
    _get_case_or_404(db, case_id)
    sessions = db.scalars(
        select(ConsultSession)
        .where(ConsultSession.case_id == case_id)
        .order_by(ConsultSession.created_at.desc())
    ).all()
    return DataEnvelope(data=[SessionOut.model_validate(s) for s in sessions])


@router.post(
    "/{case_id}/sessions",
    response_model=DataEnvelope[SessionOut],
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    case_id: str, payload: SessionCreate, db: Session = Depends(get_db)
) -> DataEnvelope[SessionOut]:
    _get_case_or_404(db, case_id)
    session = ConsultSession(case_id=case_id, title=payload.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return DataEnvelope(data=SessionOut.model_validate(session))
