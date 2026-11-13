# 고령자 건강상담(2026-11-13, API_CONTRACT 27절) — 기본정보 · 건강측정 · 추이 · 요약과 다음 상담 확인사항.
#
# 모두 대상 종류가 SENIOR 인 사례에서만 쓴다(아동 사례는 409 INVALID_CASE_STATE).
# 서버는 값과 그 변화만 계산하고 '정상 · 위험' 기준을 붙이지 않는다. 확인사항은 저장하지 않고 부를 때마다 만든다.

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.enums import (
    AuditAction,
    GlucoseTiming,
    NextCheckOrigin,
    NextCheckStatus,
    ReviewStatus,
    SessionStatus,
    SubjectType,
)
from app.core.errors import APIError, ErrorCode, bad_request, conflict, not_found
from app.models.case import Case
from app.models.senior import HealthMeasurement, NextCheck, SeniorProfile
from app.models.session import ConsultationSession
from app.models.summary import ConsultationSummary
from app.models.user import User
from app.schemas.senior import (
    VALUE_FIELDS,
    BriefBasis,
    BriefCheckItem,
    HealthMeasurementCreateRequest,
    HealthMeasurementResponse,
    HealthMeasurementUpdateRequest,
    HealthTrendResponse,
    MetricTrend,
    NextCheckResponse,
    NextChecksSaveRequest,
    NextCheckUpdateRequest,
    HistoryEntry,
    HistorySummary,
    SeniorBriefResponse,
    SeniorHistoryResponse,
    SeniorProfileResponse,
    SeniorProfileUpdateRequest,
    TrendPoint,
)
from app.services import audit_service, personal_info_service

logger = logging.getLogger(__name__)

MODULE = "ai.modeling.senior.senior_brief_llm"

#: 한 사례에서 한 번에 돌려주는 측정 수 상한(목록 · 추이). 오래된 것부터 잘린다.
MAX_MEASUREMENTS = 500

#: (이름, 화면 이름, 단위). 추이 · 확인사항이 이 순서를 쓴다.
METRICS: Tuple[Tuple[str, str, str], ...] = (
    ("systolic", "수축기 혈압", "mmHg"),
    ("diastolic", "이완기 혈압", "mmHg"),
    ("pulse", "맥박", "회/분"),
    ("blood_glucose_fasting", "공복 혈당", "mg/dL"),
    ("blood_glucose_post_meal", "식후 혈당", "mg/dL"),
    ("blood_glucose_random", "혈당(그 밖)", "mg/dL"),
    ("weight_kg", "체중", "kg"),
    ("body_temp_c", "체온", "℃"),
)
_GLUCOSE_METRIC = {
    GlucoseTiming.FASTING: "blood_glucose_fasting",
    GlucoseTiming.POST_MEAL: "blood_glucose_post_meal",
    GlucoseTiming.RANDOM: "blood_glucose_random",
}

NOT_SENIOR_MESSAGE = "고령자 사례에서만 쓸 수 있습니다."


# ---------------------------------------------------------------- 공통


def ensure_senior(case: Case) -> None:
    if case.subject_type != SubjectType.SENIOR:
        raise conflict(ErrorCode.INVALID_CASE_STATE, NOT_SENIOR_MESSAGE)


def _check_session(db: Session, case: Case, session_id: Optional[uuid.UUID]) -> None:
    if session_id is None:
        return
    found = db.scalar(select(ConsultationSession.case_id).where(ConsultationSession.id == session_id))
    if found != case.id:
        # 다른 사례의 회차인지 알려 주지 않는다(없는 회차와 같은 답).
        raise not_found(ErrorCode.SESSION_NOT_FOUND, "이 사례의 상담 회차를 찾을 수 없습니다.")


# ---------------------------------------------------------------- 기본정보


def get_profile(db: Session, case: Case) -> SeniorProfileResponse:
    ensure_senior(case)
    row = db.scalar(select(SeniorProfile).where(SeniorProfile.case_id == case.id))
    if row is None:
        return SeniorProfileResponse(case_id=case.id)
    return _profile_out(row)


def _profile_out(row: SeniorProfile) -> SeniorProfileResponse:
    return SeniorProfileResponse(
        case_id=row.case_id,
        living_arrangement=row.living_arrangement,
        care_grade=row.care_grade,
        health_notes=row.health_notes,
        care_notes=row.care_notes,
        updated_at=row.updated_at,
    )


def update_profile(
    db: Session, case: Case, current_user: User, payload: SeniorProfileUpdateRequest
) -> SeniorProfileResponse:
    ensure_senior(case)
    data = payload.model_dump(exclude_unset=True)

    row = db.scalar(select(SeniorProfile).where(SeniorProfile.case_id == case.id).with_for_update())
    if row is None:
        row = SeniorProfile(case_id=case.id)
        db.add(row)

    changed = []
    for field, value in data.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed.append(field)
    row.updated_by_id = current_user.id

    try:
        db.flush()
    except IntegrityError as error:  # 처음 저장이 겹침(사례 하나에 한 줄)
        db.rollback()
        raise conflict(ErrorCode.DUPLICATE_RESOURCE, "다른 요청이 먼저 저장했습니다. 새로고침해 주세요.") from error

    if changed:
        audit_service.record(
            db,
            action=AuditAction.SENIOR_PROFILE_UPDATED,
            entity_type="SeniorProfile",
            entity_id=row.id,
            actor_id=current_user.id,
            case_id=case.id,
            detail={"changed_fields": sorted(changed)},
        )
    db.commit()
    db.refresh(row)
    return _profile_out(row)


# ---------------------------------------------------------------- 측정


def _measurements(db: Session, case: Case) -> List[HealthMeasurement]:
    """오래된 것부터, 최근 MAX_MEASUREMENTS 개."""

    rows = list(
        db.scalars(
            select(HealthMeasurement)
            .where(HealthMeasurement.case_id == case.id)
            .order_by(HealthMeasurement.measured_at.desc(), HealthMeasurement.created_at.desc())
            .limit(MAX_MEASUREMENTS)
        )
    )
    rows.reverse()
    return rows


def list_measurements(db: Session, case: Case) -> List[HealthMeasurementResponse]:
    """최근 것부터."""

    ensure_senior(case)
    return [HealthMeasurementResponse.model_validate(row) for row in reversed(_measurements(db, case))]


def get_measurement_or_404(db: Session, case: Case, measurement_id: uuid.UUID) -> HealthMeasurement:
    row = db.scalar(
        select(HealthMeasurement).where(HealthMeasurement.id == measurement_id, HealthMeasurement.case_id == case.id)
    )
    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "측정 기록을 찾을 수 없습니다.")
    return row


def _filled(row_or_payload: Any) -> List[str]:
    names = [name for name in VALUE_FIELDS if getattr(row_or_payload, name) is not None]
    if getattr(row_or_payload, "extra_results", None):
        names.append("extra_results")
    return names


def _extras(items: Any) -> List[Dict[str, Any]]:
    """그 밖 결과를 저장 모양(dict 목록)으로. None 이면 빈 목록."""

    return [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in items or []]


def create_measurement(
    db: Session, case: Case, current_user: User, payload: HealthMeasurementCreateRequest
) -> HealthMeasurementResponse:
    ensure_senior(case)
    _check_session(db, case, payload.session_id)

    data = payload.model_dump()
    data["extra_results"] = _extras(payload.extra_results)
    if isinstance(data.get("note"), str):
        data["note"] = data["note"].strip() or None
    row = HealthMeasurement(case_id=case.id, created_by_id=current_user.id, **data)
    db.add(row)
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.HEALTH_MEASUREMENT_CREATED,
        entity_type="HealthMeasurement",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=case.id,
        session_id=row.session_id,
        detail={"fields": _filled(row)},
    )
    db.commit()
    db.refresh(row)
    return HealthMeasurementResponse.model_validate(row)


def update_measurement(
    db: Session,
    case: Case,
    measurement_id: uuid.UUID,
    current_user: User,
    payload: HealthMeasurementUpdateRequest,
) -> HealthMeasurementResponse:
    ensure_senior(case)
    row = get_measurement_or_404(db, case, measurement_id)
    data = payload.model_dump(exclude_unset=True)

    if "measured_at" in data and data["measured_at"] is None:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "측정 시각은 비울 수 없습니다.")
    if "session_id" in data:
        _check_session(db, case, data["session_id"])

    merged = {name: getattr(row, name) for name in HealthMeasurementCreateRequest.model_fields}
    merged["measured_at"] = _as_aware(row.measured_at)
    merged.update(data)
    try:
        # 바꾼 뒤 값이 만들기 규칙(값 하나 이상 · 혈압 짝 · 혈당 잰 때 · 시간대)을 지키는지 본다.
        checked = HealthMeasurementCreateRequest.model_validate(merged)
    except ValidationError as error:
        first = error.errors()[0].get("msg", "") if error.errors() else ""
        message = first.removeprefix("Value error, ") or "측정값이 올바르지 않습니다."
        raise bad_request(ErrorCode.VALIDATION_ERROR, message) from error

    changed = []
    for field in data:
        value = getattr(checked, field)
        if field == "note" and isinstance(value, str):
            value = value.strip() or None
        if field == "extra_results":
            value = _extras(value)
        if getattr(row, field) != value:
            setattr(row, field, value)
            changed.append(field)

    if changed:
        audit_service.record(
            db,
            action=AuditAction.HEALTH_MEASUREMENT_UPDATED,
            entity_type="HealthMeasurement",
            entity_id=row.id,
            actor_id=current_user.id,
            case_id=case.id,
            session_id=row.session_id,
            detail={"changed_fields": sorted(changed)},
        )
    db.commit()
    db.refresh(row)
    return HealthMeasurementResponse.model_validate(row)


def delete_measurement(db: Session, case: Case, measurement_id: uuid.UUID, current_user: User) -> None:
    ensure_senior(case)
    row = get_measurement_or_404(db, case, measurement_id)
    audit_service.record(
        db,
        action=AuditAction.HEALTH_MEASUREMENT_DELETED,
        entity_type="HealthMeasurement",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=case.id,
        session_id=row.session_id,
        detail={"fields": _filled(row)},
    )
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------- 추이


def _metric_value(row: HealthMeasurement, metric: str) -> Optional[float]:
    if metric.startswith("blood_glucose_"):
        if row.blood_glucose is None or _GLUCOSE_METRIC.get(row.glucose_timing) != metric:
            return None
        return float(row.blood_glucose)
    value = getattr(row, metric)
    return None if value is None else float(value)


def _as_aware(value: datetime) -> datetime:
    # SQLite 시험 DB 는 시간대를 떼고 돌려준다. 저장은 늘 시간대를 붙여 하므로 UTC 로 본다.
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _trend(metric: str, label: str, unit: str, points: List[TrendPoint], **extra: Any) -> MetricTrend:
    latest = points[-1]
    previous = points[-2] if len(points) >= 2 else None
    values = [point.value for point in points]
    return MetricTrend(
        metric=metric,
        label=label,
        unit=unit,
        count=len(points),
        latest=latest,
        previous=previous,
        change=round(latest.value - previous.value, 1) if previous else None,
        min=min(values),
        max=max(values),
        points=points,
        **extra,
    )


def _trends(rows: List[HealthMeasurement]) -> List[MetricTrend]:
    result = []
    for metric, label, unit in METRICS:
        points = [
            TrendPoint(measurement_id=row.id, measured_at=_as_aware(row.measured_at), value=value)
            for row in rows
            if (value := _metric_value(row, metric)) is not None
        ]
        if points:
            result.append(_trend(metric, label, unit, points))

    # 그 밖 결과(치매 조기검사 등)는 종류 · 이름이 같은 것끼리 묶는다(처음 나온 순).
    extras: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        for item in row.extra_results or []:
            key = (item.get("kind"), item.get("name"))
            group = extras.setdefault(key, {"points": [], "unit": None, "max_value": None})
            group["points"].append(
                TrendPoint(measurement_id=row.id, measured_at=_as_aware(row.measured_at), value=float(item["value"]))
            )
            group["unit"] = item.get("unit")
            group["max_value"] = item.get("max_value")
    for (kind, name), group in extras.items():
        unit = group["unit"] or (f"/{group['max_value']:g}" if group["max_value"] else "")
        result.append(
            _trend(f"{kind}:{name}", name, unit, group["points"], kind=kind, max_value=group["max_value"])
        )
    return result


def get_trend(db: Session, case: Case) -> HealthTrendResponse:
    ensure_senior(case)
    rows = _measurements(db, case)
    return HealthTrendResponse(
        case_id=case.id,
        measurement_count=len(rows),
        first_measured_at=_as_aware(rows[0].measured_at) if rows else None,
        last_measured_at=_as_aware(rows[-1].measured_at) if rows else None,
        metrics=_trends(rows),
    )


# ---------------------------------------------------------------- 요약 · 다음 상담 확인사항


class _Limits:
    """만드는 중인 사례와 서버 전체 동시 실행 자리(종결 요약과 같은 방식)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running: set = set()
        self.slots = threading.BoundedSemaphore(settings.SENIOR_AI_MAX_CONCURRENCY)


_limits = _Limits()


def reset_limits() -> None:
    global _limits
    _limits = _Limits()


def _local_date(value: datetime) -> str:
    # 날짜는 한국 시간으로 끊는다(기관 업무 기준).
    from zoneinfo import ZoneInfo

    return _as_aware(value).astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()


def _approved_sessions(db: Session, case: Case) -> List[Dict[str, Any]]:
    sessions = list(
        db.scalars(
            select(ConsultationSession)
            .where(ConsultationSession.case_id == case.id, ConsultationSession.status == SessionStatus.APPROVED)
            .order_by(ConsultationSession.session_number.asc())
        )
    )
    if not sessions:
        return []
    summaries = {
        row.session_id: row
        for row in db.scalars(
            select(ConsultationSummary).where(
                ConsultationSummary.session_id.in_([session.id for session in sessions]),
                ConsultationSummary.status == ReviewStatus.APPROVED,
            )
        )
    }
    result = []
    for session in sessions:
        summary = summaries.get(session.id)
        if summary is None:
            continue
        result.append(
            {
                "number": session.session_number,
                "date": _local_date(session.consulted_at) if session.consulted_at else "",
                "overview": summary.overview or "",
                "key_points": [point for point in (summary.key_points or []) if isinstance(point, str) and point.strip()],
            }
        )
    return result


def build_brief_input(db: Session, case: Case) -> Dict[str, Any]:
    profile = db.scalar(select(SeniorProfile).where(SeniorProfile.case_id == case.id))
    rows = _measurements(db, case)
    metrics = []
    for trend in _trends(rows):
        metrics.append(
            {
                "metric": trend.metric,
                "label": trend.label,
                "unit": trend.unit,
                "kind": trend.kind,
                "points": [
                    {"id": str(point.measurement_id), "date": _local_date(point.measured_at), "value": point.value}
                    for point in trend.points
                ],
            }
        )
    return {
        "today": _local_date(datetime.now(timezone.utc)),
        "profile": {
            "living_arrangement": profile.living_arrangement.value if profile and profile.living_arrangement else None,
            "care_grade": profile.care_grade.value if profile and profile.care_grade else None,
            "health_notes": profile.health_notes if profile else None,
            "care_notes": profile.care_notes if profile else None,
        },
        "metrics": metrics,
        "sessions": _approved_sessions(db, case),
    }


def _visit_items(row: HealthMeasurement) -> List[Dict[str, Any]]:
    """측정 한 줄을 항목별 값 목록으로(고정 항목 순서, 그다음 그 밖 결과)."""

    items = []
    for metric, label, unit in METRICS:
        value = _metric_value(row, metric)
        if value is not None:
            items.append({"id": str(row.id), "metric": metric, "label": label, "unit": unit, "value": value})
    for extra in row.extra_results or []:
        unit = extra.get("unit") or (f"/{extra['max_value']:g}" if extra.get("max_value") else "")
        items.append(
            {
                "id": str(row.id),
                "metric": f"{extra['kind']}:{extra['name']}",
                "label": extra["name"],
                "unit": unit,
                "value": float(extra["value"]),
            }
        )
    return items


def build_session_input(db: Session, session: ConsultationSession) -> Dict[str, Any]:
    """회차 통합 요약(senior_session_llm)에 넘길 이력: 기본정보 · 측정 추이 · 이 회차보다 앞선 승인 회차 · 이 회차 측정."""

    case = session.case
    data = build_brief_input(db, case)
    data["sessions"] = [item for item in data["sessions"] if item["number"] < session.session_number]
    if session.consulted_at is not None:
        data["today"] = _local_date(session.consulted_at)
    rows = db.scalars(
        select(HealthMeasurement)
        .where(HealthMeasurement.case_id == case.id, HealthMeasurement.session_id == session.id)
        .order_by(HealthMeasurement.measured_at.asc())
    )
    data["visit_measurements"] = [item for row in rows for item in _visit_items(row)]
    return data


def _run_ai(case: Case, data: Dict[str, Any], names: List[str]) -> Dict[str, Any]:
    limits = _limits
    with limits.lock:
        if case.id in limits.running:
            raise APIError(ErrorCode.RATE_LIMITED, "이 사례의 확인사항을 이미 만들고 있습니다. 잠시 후 다시 시도해 주세요.", status_code=429)
        if not limits.slots.acquire(blocking=False):
            raise APIError(ErrorCode.RATE_LIMITED, "다른 확인사항을 만드는 중입니다. 잠시 후 다시 시도해 주세요.", status_code=429)
        limits.running.add(case.id)

    started = threading.Event()
    released: List[bool] = []

    def release() -> None:
        with limits.lock:
            if released:
                return
            released.append(True)
            limits.running.discard(case.id)
        limits.slots.release()

    try:
        deadline = time.monotonic() + settings.SENIOR_AI_TIMEOUT_SECONDS
        run = load_callable(MODULE, "generate_senior_brief")
    except BaseException:
        release()
        raise

    def work() -> Dict[str, Any]:
        started.set()
        try:
            return run(data, known_identifiers=names, deadline=deadline)
        finally:
            release()

    try:
        return run_with_timeout(work, settings.SENIOR_AI_TIMEOUT_SECONDS)
    finally:
        if not started.is_set():
            release()


_AI_ERRORS = {
    ErrorCode.AI_TIMEOUT: (504, "확인사항이 제한 시간 안에 끝나지 않았습니다. 잠시 후 다시 시도해 주세요."),
    ErrorCode.AI_INVALID_OUTPUT: (502, "AI 가 확인사항을 만들지 못했습니다. 다시 시도해 주세요."),
    ErrorCode.AI_PRIVACY_BLOCKED: (422, "개인정보를 다 가리지 못해 AI 로 보내지 않았습니다. 메모에서 실명 · 연락처를 지운 뒤 다시 시도해 주세요."),
    ErrorCode.AI_FAILED: (502, "확인사항을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."),
}


def _ai_error(code: ErrorCode) -> APIError:
    status, message = _AI_ERRORS[code]
    return APIError(code, message, status_code=status)


def _basis(raw: Dict[str, Any], allowed_ids: set) -> Optional[BriefBasis]:
    kind = raw.get("kind")
    if kind == "MEASUREMENT":
        if raw.get("measurement_id") not in allowed_ids:
            return None
        return BriefBasis(kind="MEASUREMENT", metric=raw.get("metric"), measurement_id=uuid.UUID(raw["measurement_id"]))
    if kind == "SESSION":
        return BriefBasis(kind="SESSION", session_number=raw.get("session_number"))
    if kind == "PROFILE":
        return BriefBasis(kind="PROFILE")
    return None


def generate_brief(db: Session, case: Case, current_user: User) -> SeniorBriefResponse:
    ensure_senior(case)
    data = build_brief_input(db, case)
    use_ai = settings.SENIOR_AI_PROVIDER == "modeling"
    started = time.monotonic()

    try:
        if use_ai:
            names = personal_info_service.known_identifiers(db, case.id, extra=[case.child_alias])
            result = _run_ai(case, data, names)
        else:
            result = load_callable(MODULE, "rule_based_brief")(data)
    except APIError:
        raise
    except (OperationTimeout, TimeoutError) as error:
        raise _ai_error(ErrorCode.AI_TIMEOUT) from error
    except ModuleLoadError as error:
        logger.warning("고령자 확인사항 모듈을 불러오지 못했습니다. case_id=%s", case.id)
        raise _ai_error(ErrorCode.AI_FAILED) from error
    except Exception as error:  # noqa: BLE001 — 문구에 원문이 섞일 수 있어 종류 이름만 남긴다
        name = type(error).__name__
        code = {
            "SeniorBriefOutputError": ErrorCode.AI_INVALID_OUTPUT,
            "PrivacyGatewayBlocked": ErrorCode.AI_PRIVACY_BLOCKED,
        }.get(name, ErrorCode.AI_FAILED)
        logger.warning("고령자 확인사항 실패 case_id=%s error=%s", case.id, name)
        raise _ai_error(code) from error

    allowed_ids = {point["id"] for metric in data["metrics"] for point in metric["points"]}
    items = []
    for item in result.get("check_items") or []:
        basis = [b for raw in item.get("basis") or [] if (b := _basis(raw, allowed_ids)) is not None]
        items.append(BriefCheckItem(text=item["text"], basis=basis))

    audit_service.record(
        db,
        action=AuditAction.SENIOR_BRIEF_GENERATED,
        entity_type="Case",
        entity_id=case.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={
            "source": "AI" if use_ai else "RULE",
            "model": result.get("model") if use_ai else None,
            "item_count": len(items),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        },
    )
    db.commit()

    return SeniorBriefResponse(
        case_id=case.id,
        source="AI" if use_ai else "RULE",
        model=result.get("model") if use_ai else None,
        summary=result.get("summary") or "",
        check_items=items,
        generated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------- 다음 상담 확인사항(저장 · 확인 표시)


def _check_basis_measurements(db: Session, case: Case, items: List[Any]) -> None:
    ids = {basis.measurement_id for item in items for basis in item.basis if basis.measurement_id is not None}
    if not ids:
        return
    found = set(
        db.scalars(select(HealthMeasurement.id).where(HealthMeasurement.case_id == case.id, HealthMeasurement.id.in_(ids)))
    )
    if found != ids:
        raise bad_request(ErrorCode.VALIDATION_ERROR, "근거로 단 측정 기록 가운데 이 사례에 없는 것이 있습니다.")


def list_next_checks(db: Session, case: Case, status: Optional[NextCheckStatus] = None) -> List[NextCheckResponse]:
    """만든 순(오래된 것부터)."""

    ensure_senior(case)
    query = select(NextCheck).where(NextCheck.case_id == case.id)
    if status is not None:
        query = query.where(NextCheck.status == status)
    rows = db.scalars(query.order_by(NextCheck.created_at.asc(), NextCheck.id.asc()))
    return [NextCheckResponse.model_validate(row) for row in rows]


def save_next_checks(
    db: Session, case: Case, current_user: User, payload: NextChecksSaveRequest
) -> List[NextCheckResponse]:
    ensure_senior(case)
    _check_session(db, case, payload.source_session_id)
    _check_basis_measurements(db, case, payload.items)

    rows = []
    for item in payload.items:
        text = item.text.strip()
        if not text:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "확인사항 글이 비어 있습니다.")
        row = NextCheck(
            case_id=case.id,
            source_session_id=payload.source_session_id,
            text=text,
            basis=[basis.model_dump(mode="json", exclude_none=True) for basis in item.basis],
            origin=item.origin,
            edited=item.edited and item.origin != NextCheckOrigin.COUNSELOR,
            status=NextCheckStatus.OPEN,
            created_by_id=current_user.id,
        )
        db.add(row)
        rows.append(row)
    db.flush()

    by_origin: Dict[str, int] = {}
    for row in rows:
        by_origin[row.origin.value] = by_origin.get(row.origin.value, 0) + 1
    audit_service.record(
        db,
        action=AuditAction.NEXT_CHECKS_SAVED,
        entity_type="Case",
        entity_id=case.id,
        actor_id=current_user.id,
        case_id=case.id,
        session_id=payload.source_session_id,
        detail={"count": len(rows), "by_origin": by_origin, "edited": sum(1 for row in rows if row.edited)},
    )
    db.commit()
    for row in rows:
        db.refresh(row)
    return [NextCheckResponse.model_validate(row) for row in rows]


def _get_next_check_or_404(db: Session, case: Case, check_id: uuid.UUID) -> NextCheck:
    row = db.scalar(select(NextCheck).where(NextCheck.id == check_id, NextCheck.case_id == case.id).with_for_update())
    if row is None:
        raise not_found(ErrorCode.NOT_FOUND, "확인사항을 찾을 수 없습니다.")
    return row


def update_next_check(
    db: Session, case: Case, check_id: uuid.UUID, current_user: User, payload: NextCheckUpdateRequest
) -> NextCheckResponse:
    ensure_senior(case)
    row = _get_next_check_or_404(db, case, check_id)
    data = payload.model_dump(exclude_unset=True)
    changed = []

    if "text" in data:
        text = (data["text"] or "").strip()
        if not text:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "확인사항 글은 비울 수 없습니다.")
        if text != row.text:
            row.text = text
            if row.origin != NextCheckOrigin.COUNSELOR:
                row.edited = True
            changed.append("text")

    if "status" in data:
        if data["status"] is None:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "상태는 비울 수 없습니다.")
        if data["status"] != row.status:
            row.status = data["status"]
            changed.append("status")
            if row.status == NextCheckStatus.OPEN:
                row.checked_at = None
                row.checked_session_id = None
            else:
                row.checked_at = datetime.now(timezone.utc)

    if "checked_session_id" in data:
        _check_session(db, case, data["checked_session_id"])
        if row.status == NextCheckStatus.OPEN and data["checked_session_id"] is not None:
            raise bad_request(ErrorCode.VALIDATION_ERROR, "확인한 방문은 확인함 · 확인 안 함 상태에서만 적을 수 있습니다.")
        if data["checked_session_id"] != row.checked_session_id:
            row.checked_session_id = data["checked_session_id"]
            changed.append("checked_session_id")

    if "result_note" in data:
        note = (data["result_note"] or "").strip() or None
        if note != row.result_note:
            row.result_note = note
            changed.append("result_note")

    if changed:
        audit_service.record(
            db,
            action=AuditAction.NEXT_CHECK_UPDATED,
            entity_type="NextCheck",
            entity_id=row.id,
            actor_id=current_user.id,
            case_id=case.id,
            detail={"changed_fields": sorted(changed), "status": row.status.value},
        )
    db.commit()
    db.refresh(row)
    return NextCheckResponse.model_validate(row)


def delete_next_check(db: Session, case: Case, check_id: uuid.UUID, current_user: User) -> None:
    ensure_senior(case)
    row = _get_next_check_or_404(db, case, check_id)
    audit_service.record(
        db,
        action=AuditAction.NEXT_CHECK_DELETED,
        entity_type="NextCheck",
        entity_id=row.id,
        actor_id=current_user.id,
        case_id=case.id,
        detail={"origin": row.origin.value, "status": row.status.value},
    )
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------- 상담 이력 조회


def get_history(db: Session, case: Case) -> SeniorHistoryResponse:
    """어르신별 방문 · 측정 · 상담 기록을 시간순(최근 것부터)으로. 회차에 단 측정 · 확인사항은 그 회차 안에 넣는다."""

    ensure_senior(case)
    sessions = list(db.scalars(select(ConsultationSession).where(ConsultationSession.case_id == case.id)))
    summaries = {
        row.session_id: row
        for row in db.scalars(
            select(ConsultationSummary).where(ConsultationSummary.session_id.in_([item.id for item in sessions]))
        )
    } if sessions else {}
    measurements = _measurements(db, case)
    checks = list(db.scalars(select(NextCheck).where(NextCheck.case_id == case.id).order_by(NextCheck.created_at.asc())))

    by_session: Dict[uuid.UUID, List[HealthMeasurement]] = {}
    loose: List[HealthMeasurement] = []
    for row in measurements:
        if row.session_id is None:
            loose.append(row)
        else:
            by_session.setdefault(row.session_id, []).append(row)

    entries: List[HistoryEntry] = []
    for item in sessions:
        summary = summaries.get(item.id)
        entries.append(
            HistoryEntry(
                kind="VISIT",
                at=_as_aware(item.consulted_at or item.created_at),
                session_id=item.id,
                session_number=item.session_number,
                session_title=item.title,
                session_status=item.status,
                summary=HistorySummary(
                    overview=summary.overview or "",
                    key_points=list(summary.key_points or []),
                    status=summary.status,
                )
                if summary is not None
                else None,
                measurements=[HealthMeasurementResponse.model_validate(row) for row in by_session.get(item.id, [])],
                checks_created=[NextCheckResponse.model_validate(c) for c in checks if c.source_session_id == item.id],
                checks_resolved=[NextCheckResponse.model_validate(c) for c in checks if c.checked_session_id == item.id],
            )
        )
    for row in loose:
        entries.append(
            HistoryEntry(
                kind="MEASUREMENT",
                at=_as_aware(row.measured_at),
                measurements=[HealthMeasurementResponse.model_validate(row)],
            )
        )
    entries.sort(key=lambda entry: (entry.at, entry.session_number or 0), reverse=True)

    return SeniorHistoryResponse(
        case_id=case.id,
        entries=entries,
        open_checks=[NextCheckResponse.model_validate(c) for c in checks if c.status == NextCheckStatus.OPEN],
    )
