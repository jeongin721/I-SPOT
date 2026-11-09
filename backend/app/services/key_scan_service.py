# STT 검수 '1차 임시 핵심 발화' 스캔(API_CONTRACT 7절, I-SPOT_DOCS/docs/PROPOSAL_stt_key_scan.md · PROPOSAL_stt_law_match.md).
#
# process_stt 가 전사 결과를 저장하기 직전, 같은 작업 안에서 scan() 을 부른다. AI 함수
# ai/modeling/abuse/contract_adapter.key_scan_as_contract(stt_result) 가 1차 분류기(로컬 모델)와 로컬 조문 매칭을 돌려
# {model, segments[{segment_id, abuse_types, legal_references}]} 를 주고, 여기서 status 를 붙인다.
#  - DONE       : 스캔 성공(segments 가 비어도 DONE)
#  - FAILED     : 시간 초과 · 예외 · 모양이 다름. STT 는 그대로 성공이다(실패는 서버 로그에만, 원문 · 예외 문구는 남기지 않음).
#                 원문 수정 뒤 다시 스캔하다 실패하면 저장 전 결과(segments · scanned_version)는 그대로 둔다.
#  - SKIPPED    : AI_PROVIDER 가 modeling 이 아니다(모듈을 부르지 않음).
#  - REFRESHING : 원문 수정(PATCH)으로 새 version 이 생겨 **저장한 원문으로 다시 스캔하는 중**(2026-11-09, 비동기 — 팀장 결정).
#                 그동안 segments 는 직전 version 의 것(지운 발화만 뺌)이고 scanned_version 이 그 version 이다. 끝나면 DONE · FAILED.
#                 제한 시간 + 여유를 넘긴 REFRESHING 은 조회 때 FAILED 로 마감한다(작업이 사라진 경우 — expire_stale).
# scanned_version: segments 를 만든 원문 version(없으면 모름). started_at: REFRESHING 시작 시각(ISO, 멈춤 판정용).
# 판정이 아니라 '먼저 들어볼 곳' 이다(05_RULES §1). 원문이 서버 밖으로 나가지 않고 감사 기록은 두지 않는다(STT 작업의 일부).

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.transcript import Transcript

logger = get_logger(__name__)

KEY_SCAN_MODULE = "ai.modeling.abuse.contract_adapter"
KEY_SCAN_FUNCTION = "key_scan_as_contract"

STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUS_REFRESHING = "REFRESHING"

ABUSE_TYPES = ("PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT")

#: 발화 하나에 저장하는 조문 수 상한 · 글자 수 상한(저장 크기를 묶는다. AI 쪽은 유형당 하나를 준다).
MAX_REFERENCES_PER_SEGMENT = 8
_REFERENCE_TEXT_LIMITS = {
    "law_name": 100,
    "article": 50,
    "item_label": 50,
    "text": 1000,
    "portal_url": 500,
    "excerpt": 300,
}

#: 멈춤 판정 여유(초). 살아 있는 작업은 KEY_SCAN_TIMEOUT_SECONDS 안에 끝나므로, 그 뒤로 이만큼 더 지난 REFRESHING 만 마감한다.
STALE_GRACE_SECONDS = 60


class _Limits:
    """다시 스캔 동시 실행 자리(서버 전체 KEY_SCAN_MAX_CONCURRENCY). 모델이 GPU 하나라 기본 1."""

    def __init__(self) -> None:
        self.slots = threading.BoundedSemaphore(settings.KEY_SCAN_MAX_CONCURRENCY)


_limits = _Limits()


def reset_limits() -> None:
    """시험용 — 설정을 바꾼 뒤 자리를 다시 만든다."""

    global _limits
    _limits = _Limits()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _result(
    status: str,
    model: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    *,
    scanned_version: Optional[int] = None,
    started_at: Optional[str] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": status, "model": model, "segments": segments or []}
    if scanned_version is not None:
        result["scanned_version"] = scanned_version
    if started_at is not None:
        result["started_at"] = started_at
    return result


def _load_scanner() -> Callable[[Dict[str, Any]], Any]:
    """시험은 이 함수를 바꿔 가짜 스캐너를 넣는다."""

    return load_callable(KEY_SCAN_MODULE, KEY_SCAN_FUNCTION)


def _clean_reference(item: Any) -> Optional[Dict[str, Any]]:
    """조문 하나를 저장할 모양으로. 법령 이름 · 조문이 없거나 유형이 모르는 값이면 None(그 항목만 버린다)."""

    if not isinstance(item, dict):
        return None

    abuse_type = item.get("abuse_type")
    if abuse_type is not None and abuse_type not in ABUSE_TYPES:
        return None

    cleaned: Dict[str, Any] = {"abuse_type": abuse_type}
    for key, limit in _REFERENCE_TEXT_LIMITS.items():
        value = item.get(key)
        cleaned[key] = value[:limit] if isinstance(value, str) else ""

    if not cleaned["law_name"] or not cleaned["article"]:
        return None

    score = item.get("score")
    cleaned["score"] = round(float(score), 3) if isinstance(score, (int, float)) and not isinstance(score, bool) else None

    return cleaned


def _clean_references(raw: Any) -> List[Dict[str, Any]]:
    """발화의 legal_references — 없거나 목록이 아니면 빈 목록(모양 오류로 STT 를 실패시키지 않는다)."""

    if not isinstance(raw, list):
        return []

    cleaned = [reference for reference in (_clean_reference(item) for item in raw) if reference is not None]

    return cleaned[:MAX_REFERENCES_PER_SEGMENT]


def _clean(raw: Any, known_ids: Iterable[str]) -> Optional[Dict[str, Any]]:
    """모듈 결과를 저장할 모양으로 다듬는다. 모양이 틀리면 None(→ FAILED).

    원문에 없는 segment_id · 모르는 유형은 버린다. 같은 발화가 두 번 오면 **유형이 남는 첫 것**만 둔다 — 첫 것의 유형이
    모두 걸러지면(예: ["UNKNOWN"]) 다음 것을 본다(민규 #114 R5). 유형이 남지 않은 발화는 뺀다.
    legal_references 는 남은 유형의 것만 두고(없으면 빈 목록) 글자 수 · 개수를 묶는다. 순서는 원문 순서로 맞춘다.
    """

    if not isinstance(raw, dict) or not isinstance(raw.get("segments"), list):
        return None

    model = raw.get("model")
    order = {segment_id: index for index, segment_id in enumerate(known_ids)}
    picked: Dict[str, Tuple[List[str], List[Dict[str, Any]]]] = {}

    for item in raw["segments"]:
        if not isinstance(item, dict):
            return None

        segment_id = item.get("segment_id")
        abuse_types = item.get("abuse_types")

        # 유형 목록 안도 문자열만이다. list · dict 같은 값은 모양 오류다(dict.fromkeys 의 TypeError 로 STT 까지
        # 실패하지 않게 — 민규 #114).
        if (
            not isinstance(segment_id, str)
            or not isinstance(abuse_types, list)
            or not all(isinstance(value, str) for value in abuse_types)
        ):
            return None

        if segment_id not in order or segment_id in picked:
            continue

        kept = [value for value in dict.fromkeys(abuse_types) if value in ABUSE_TYPES]

        if kept:
            references = [
                reference
                for reference in _clean_references(item.get("legal_references"))
                if reference["abuse_type"] is None or reference["abuse_type"] in kept
            ]
            picked[segment_id] = (kept, references)

    segments = [
        {"segment_id": segment_id, "abuse_types": picked[segment_id][0], "legal_references": picked[segment_id][1]}
        for segment_id in sorted(picked, key=order.__getitem__)
    ]

    return _result(STATUS_DONE, model if isinstance(model, str) else None, segments)


def scan(stt_contract: Dict[str, Any], *, scanned_version: Optional[int] = None) -> Dict[str, Any]:
    """전사 결과(STT Contract dict)를 1차 스캔한다. 어떤 실패든 예외를 올리지 않고 FAILED 를 돌려준다."""

    if settings.AI_PROVIDER != "modeling":
        return _result(STATUS_SKIPPED)

    known_ids = [
        str(segment.get("segment_id"))
        for segment in stt_contract.get("segments") or []
        if isinstance(segment, dict)
    ]

    # 모듈 불러오기도 같은 제한 시간 안에서 한다 — 첫 STT 는 import 시간이 제한에 들어간다(제안서 §4, 민규 #114 R2).
    # ImportError 가 아닌 예외(모델 파일 · CUDA 초기화의 OSError · RuntimeError 등)도 STT 를 실패시키지 않게
    # 모두 FAILED 로 받는다(민규 #114 R1).
    try:
        raw = run_with_timeout(lambda: _load_scanner()(stt_contract), settings.KEY_SCAN_TIMEOUT_SECONDS)
    except OperationTimeout:
        logger.warning("1차 핵심 발화 스캔이 제한 시간(%.0f초)을 넘겼습니다.", settings.KEY_SCAN_TIMEOUT_SECONDS)
        return _result(STATUS_FAILED)
    except ModuleLoadError as error:
        logger.warning("1차 핵심 발화 스캔 모듈을 불러오지 못했습니다. type=%s", type(error).__name__)
        return _result(STATUS_FAILED)
    except Exception as error:
        logger.warning("1차 핵심 발화 스캔 중 오류. type=%s", type(error).__name__)
        return _result(STATUS_FAILED)

    # 다듬기에서 뜻밖의 예외가 나도 STT 는 성공으로 두고 FAILED 로 떨어뜨린다.
    try:
        cleaned = _clean(raw, known_ids)
    except Exception as error:
        logger.warning("1차 핵심 발화 스캔 결과를 다듬지 못했습니다. type=%s", type(error).__name__)
        return _result(STATUS_FAILED)

    if cleaned is None:
        logger.warning("1차 핵심 발화 스캔 결과가 기대한 모양이 아닙니다. type=%s", type(raw).__name__)
        return _result(STATUS_FAILED)

    # scanned_version 은 segments 를 만든 원문 version 이라 DONE 에만 붙인다(FAILED 는 segments 가 없다).
    if scanned_version is not None:
        cleaned["scanned_version"] = scanned_version

    logger.info("1차 핵심 발화 스캔 완료 count=%s", len(cleaned["segments"]))

    return cleaned


def copy_for_new_version(previous: Optional[Dict[str, Any]], removed_segment_ids: Iterable[str]) -> Optional[Dict[str, Any]]:
    """원문 수정으로 새 version 을 만들 때 직전 값을 복사한다(지운 발화만 뺌). modeling 이 아니면 이것이 새 version 의 값이다."""

    if not isinstance(previous, dict):
        return None

    removed = set(removed_segment_ids)
    segments = previous.get("segments") if isinstance(previous.get("segments"), list) else []

    copied = {
        **previous,
        "segments": [
            item for item in segments if isinstance(item, dict) and item.get("segment_id") not in removed
        ],
    }
    # 직전 version 이 아직 다시 스캔하는 중이었더라도 새 version 의 복사본은 그 작업과 무관하다.
    if copied.get("status") == STATUS_REFRESHING:
        copied["status"] = STATUS_DONE if copied["segments"] else STATUS_FAILED
    copied.pop("started_at", None)

    return copied


def should_refresh() -> bool:
    """원문 수정 뒤 다시 스캔하는가 — AI_PROVIDER=modeling 일 때만(스캔 자체가 그때만 돈다)."""

    return settings.AI_PROVIDER == "modeling"


def begin_refresh(previous: Optional[Dict[str, Any]], removed_segment_ids: Iterable[str]) -> Dict[str, Any]:
    """원문 수정으로 만든 새 version 의 key_scan 시작 값 — 직전 결과를 복사해 두고 REFRESHING 으로 표시한다.
    직전 값이 없으면(이 기능 전 전사본) 빈 segments 로 시작한다. 실제 스캔은 schedule_refresh 가 띄우는 작업이 한다."""

    copied = copy_for_new_version(previous, removed_segment_ids) or _result(STATUS_FAILED)

    return {
        **copied,
        "status": STATUS_REFRESHING,
        "started_at": _now().isoformat(),
    }


def schedule_refresh(background_tasks: BackgroundTasks, transcript: Transcript) -> bool:
    """PATCH 응답 뒤 다시 스캔 작업을 띄운다. 새 version 이 REFRESHING 으로 시작했을 때만. 띄웠으면 True."""

    key_scan = transcript.key_scan if isinstance(transcript.key_scan, dict) else None

    if key_scan is None or key_scan.get("status") != STATUS_REFRESHING or not isinstance(key_scan.get("started_at"), str):
        return False

    background_tasks.add_task(refresh, transcript.id, key_scan["started_at"])

    return True


def _contract_of(transcript: Transcript) -> Dict[str, Any]:
    """다시 스캔할 STT Contract(transcript_service.transcript_to_contract 와 같은 모양 — 순환 import 를 피해 여기서 만든다)."""

    segments = sorted(transcript.segments, key=lambda item: item.order_index)

    return {
        "schema_version": transcript.schema_version,
        "segments": [
            {
                "segment_id": segment.segment_id,
                "speaker": segment.speaker.value,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": segment.text,
                "confidence": segment.confidence,
            }
            for segment in segments
        ],
    }


def _is_latest(db: Session, transcript: Transcript) -> bool:
    latest_id = db.scalar(
        select(Transcript.id)
        .where(Transcript.session_id == transcript.session_id)
        .order_by(Transcript.version.desc())
        .limit(1)
    )
    return latest_id == transcript.id


def _refresh_target(transcript: Optional[Transcript], started_at: str) -> bool:
    """이 작업이 맡은 REFRESHING 이 아직 그대로인가(다른 저장 · 멈춤 판정이 먼저 손대지 않았는가)."""

    key_scan = transcript.key_scan if transcript is not None and isinstance(transcript.key_scan, dict) else None

    return key_scan is not None and key_scan.get("status") == STATUS_REFRESHING and key_scan.get("started_at") == started_at


def _load_for_refresh(transcript_id: uuid.UUID, started_at: str) -> Optional[Tuple[Dict[str, Any], int, Dict[str, Any]]]:
    """(스캔할 Contract, version, 시작 값) — 행이 바뀌었거나 더 새 version 이 있으면 None(일은 하지 않는다)."""

    db = SessionLocal()
    try:
        transcript = db.get(Transcript, transcript_id)
        if not _refresh_target(transcript, started_at) or not _is_latest(db, transcript):
            return None
        return _contract_of(transcript), transcript.version, dict(transcript.key_scan)
    finally:
        db.close()


def _finish_refresh(transcript_id: uuid.UUID, started_at: str, result: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    """행이 아직 이 작업의 REFRESHING 일 때만 결과를 쓴다. 실패(FAILED)면 저장 전 결과(segments · scanned_version)는 남긴다."""

    db = SessionLocal()
    try:
        transcript = db.execute(select(Transcript).where(Transcript.id == transcript_id).with_for_update()).scalar_one_or_none()
        if not _refresh_target(transcript, started_at):
            db.rollback()
            return False
        if result["status"] == STATUS_FAILED:
            result = {
                **result,
                "model": previous.get("model"),
                "segments": previous.get("segments") or [],
            }
            if previous.get("scanned_version") is not None:
                result["scanned_version"] = previous["scanned_version"]
            else:
                result.pop("scanned_version", None)
        transcript.key_scan = result
        db.commit()
        return True
    finally:
        db.close()


def refresh(transcript_id: uuid.UUID, started_at: str) -> None:
    """원문 수정으로 만든 version 을 저장한 원문으로 다시 스캔한다(BackgroundTasks). 어떤 예외도 밖으로 내지 않는다.

    더 새 version 이 생겼으면(연이어 저장) 일을 하지 않는다 — 그 version 의 작업이 따로 돈다. 모델은 자리를 얻은 뒤 한 번만 돌린다.
    """

    try:
        loaded = _load_for_refresh(transcript_id, started_at)
        if loaded is None:
            return
        contract, version, previous = loaded

        with _limits.slots:
            # 자리를 기다리는 사이 또 저장됐으면 모델을 돌리지 않는다.
            db = SessionLocal()
            try:
                transcript = db.get(Transcript, transcript_id)
                if not _refresh_target(transcript, started_at) or not _is_latest(db, transcript):
                    return
            finally:
                db.close()
            result = scan(contract, scanned_version=version)

        _finish_refresh(transcript_id, started_at, result, previous)
    except Exception as error:  # noqa: BLE001 — 백그라운드 작업이라 예외를 밖으로 내지 않는다
        logger.warning("1차 핵심 발화 다시 스캔 중 오류. type=%s", type(error).__name__)


def _stale_cutoff() -> datetime:
    return _now() - timedelta(seconds=settings.KEY_SCAN_TIMEOUT_SECONDS + STALE_GRACE_SECONDS)


def expire_stale(db: Session, transcript: Transcript) -> bool:
    """제한 시간 + 여유를 넘긴 REFRESHING 을 FAILED 로 마감한다(작업이 사라진 경우 — 서버 재시작 등). 저장 전 결과는 남긴다.
    조회(GET /transcript) 때 최신 version 에 대해 부른다. 마감했으면 True."""

    key_scan = transcript.key_scan if isinstance(transcript.key_scan, dict) else None

    if key_scan is None or key_scan.get("status") != STATUS_REFRESHING:
        return False

    started_raw = key_scan.get("started_at")
    try:
        started = datetime.fromisoformat(started_raw) if isinstance(started_raw, str) else None
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
    except ValueError:
        started = None

    if started is not None and started >= _stale_cutoff():
        return False

    expired = {key: value for key, value in key_scan.items() if key != "started_at"}
    expired["status"] = STATUS_FAILED
    transcript.key_scan = expired
    db.commit()

    logger.warning("1차 핵심 발화 다시 스캔이 끝나지 않아 FAILED 로 마감했습니다(저장 전 결과는 둠).")

    return True
