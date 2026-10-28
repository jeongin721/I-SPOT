# 구간별 음성 참고 표시(stt/voice_marks, 정담원 님) 호출 · 저장 · 조회.
#
# STT 결과를 저장한 직후 같은 백그라운드 작업에서 analyze_voice_marks(audio_path, segments) 를 부르고,
# 결과 dict 를 audio_features 에 새 행(extractor "stt.voice_marks")으로 저장한다. 상담사가 원문을 확정할 때
# 확정본의 아동 구간이 STT 직후와 다르면 한 번 더 돌려 새 행으로 저장한다(행은 쌓고, 조회는 가장 최근 행).
# 설계와 결정은 I-SPOT_DOCS/docs/PROPOSAL_voice_marks.md §7-0 · API_CONTRACT.md 16절.
#
# 이 표시는 상담사가 다시 들어 볼 구간을 알려 주는 참고 정보이며 학대 · 위험을 판정하지 않는다.
# 여기서 하는 일이 실패해도 회차 상태(STT_REVIEW_REQUIRED · STT_CONFIRMED)에는 영향을 주지 않는다.
# 로그에는 식별자와 예외 종류만 남기고 상담 발화 · 파일 경로는 남기지 않는다.

import threading
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core import storage
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import Speaker
from app.core.logging import get_logger
from app.models.audio_feature import AudioFeature
from app.models.transcript import Transcript
from app.services import audio_service

logger = get_logger(__name__)

EXTRACTOR = "stt.voice_marks"
SCHEMA_VERSION = "1.0"

# 분석 모듈이 쓰는 상태 · 이유 값(stt/voice_marks.md 4절 · 5절). Backend 가 실패 행을 만들 때도 같은 값을 쓴다.
STATUS_UNDETERMINED = "UNDETERMINED"
REASON_ANALYSIS_ERROR = "ANALYSIS_ERROR"

Analyzer = Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]

_override: Optional[Analyzer] = None


def set_voice_marks_analyzer_override(analyzer: Optional[Analyzer]) -> None:
    """테스트에서 분석 함수를 주입하는 hook. 주입돼 있으면 VOICE_MARKS_PROVIDER 와 상관없이 켜진 것으로 본다."""

    global _override
    _override = analyzer


def is_enabled() -> bool:
    return _override is not None or settings.VOICE_MARKS_PROVIDER == "module"


def _load_analyzer() -> Analyzer:
    if _override is not None:
        return _override

    return load_callable(settings.VOICE_MARKS_MODULE, settings.VOICE_MARKS_FUNCTION)


def segment_inputs(transcript: Transcript) -> List[Dict[str, Any]]:
    """분석 함수에 넘기는 구간 목록. 순서는 전사본 순서, 값은 Contract 그대로(화자는 문자열, 시각은 정수 ms)."""

    ordered = sorted(transcript.segments, key=lambda segment: segment.order_index)

    return [
        {
            "segment_id": segment.segment_id,
            "speaker": segment.speaker.value,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
        }
        for segment in ordered
    ]


def error_result(
    segments: List[Dict[str, Any]], reason: str = REASON_ANALYSIS_ERROR
) -> Dict[str, Any]:
    """Backend 쪽 실패(시간 초과 · 예외 · 모듈 없음 · 형식 어긋남)를 분석 모듈과 같은 모양의 UNDETERMINED 결과로 만든다.

    행이 없으면 화면이 '분석 전' 과 '분석 불가' 를 구분하지 못하므로 결과 없이 끝내지 않는다. 기준값(thresholds)은
    모듈이 돌지 않았으니 비워 둔다(화면은 flag 가 있을 때만 기준값을 읽는다).
    """

    child_total = sum(1 for segment in segments if segment.get("speaker") == Speaker.CHILD.value)

    return {
        "schema_version": SCHEMA_VERSION,
        "analyzer": EXTRACTOR,
        "analyzer_version": None,
        "status": STATUS_UNDETERMINED,
        "reason": reason,
        "reference": {
            "child_segments_total": child_total,
            "child_segments_used": 0,
            "min_required": None,
            "note": "Backend 에서 분석을 끝내지 못해 비교 기준이 없습니다.",
        },
        "thresholds": {
            "tremor_z_above": None,
            "mumble_z_below": None,
            "soft_z_below": None,
            "basis": "분석을 끝내지 못해 기준값이 없습니다.",
        },
        "segments": [
            {
                "segment_id": segment.get("segment_id"),
                "speaker": segment.get("speaker"),
                "start_ms": segment.get("start_ms"),
                "end_ms": segment.get("end_ms"),
                "status": STATUS_UNDETERMINED,
                "reason": reason,
                "tremor": None,
                "mumble": None,
                "soft": None,
                "flag_any": None,
            }
            for segment in segments
        ],
    }


def _looks_like_result(value: Any) -> bool:
    """모듈 결과의 최소 모양만 본다(dict · status · segments 목록). 세부 칸은 모듈 문서가 보장한다."""

    return (
        isinstance(value, dict)
        and isinstance(value.get("status"), str)
        and isinstance(value.get("segments"), list)
    )


def _run_analyzer(audio_path: str, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """분석 함수를 제한 시간 안에 부른다. 어떤 실패든 UNDETERMINED · ANALYSIS_ERROR 결과로 바꾼다."""

    try:
        analyzer = _load_analyzer()
    except ModuleLoadError as error:
        logger.warning("음성 참고 표시 모듈을 불러오지 못했습니다. type=%s", type(error).__name__)
        return error_result(segments)

    try:
        result = run_with_timeout(
            lambda: analyzer(audio_path, segments),
            settings.VOICE_MARKS_TIMEOUT_SECONDS,
        )
    except OperationTimeout:
        logger.warning(
            "음성 참고 표시 분석이 제한 시간(%.0f초)을 넘겼습니다.",
            settings.VOICE_MARKS_TIMEOUT_SECONDS,
        )
        return error_result(segments)
    except Exception as error:
        logger.warning("음성 참고 표시 분석 중 오류. type=%s", type(error).__name__)
        return error_result(segments)

    if not _looks_like_result(result):
        logger.warning(
            "음성 참고 표시 결과가 기대한 모양이 아닙니다. type=%s", type(result).__name__
        )
        return error_result(segments)

    return result


def analyze_for_transcript(session_id: uuid.UUID, transcript_id: uuid.UUID) -> None:
    """STT 저장 직후(process_stt 안) 또는 확정 뒤(BackgroundTasks)에 부른다.

    별도 DB Session 을 쓰고, 어떤 예외도 밖으로 내지 않는다(회차 상태는 여기서 바꾸지 않는다).
    """

    if not is_enabled():
        return

    db = SessionLocal()

    try:
        transcript = db.scalar(
            select(Transcript)
            .options(selectinload(Transcript.segments))
            .where(Transcript.id == transcript_id, Transcript.session_id == session_id)
        )

        if transcript is None:
            logger.warning("음성 참고 표시 대상 Transcript 가 없습니다. session_id=%s", session_id)
            return

        audio = audio_service.get_latest_audio(db, session_id)
        audio_path = storage.resolve_stored_path(audio.path)
        segments = segment_inputs(transcript)

        result = _run_analyzer(str(audio_path), segments)

        db.add(
            AudioFeature(
                session_id=session_id,
                audio_file_id=audio.id,
                transcript_id=transcript.id,
                transcript_version=transcript.version,
                schema_version=SCHEMA_VERSION,
                extractor=EXTRACTOR,
                features=result,
            )
        )
        db.commit()

        logger.info(
            "음성 참고 표시 저장 session_id=%s version=%s status=%s",
            session_id,
            transcript.version,
            result.get("status"),
        )
    except Exception as error:
        db.rollback()
        logger.warning(
            "음성 참고 표시를 저장하지 못했습니다. session_id=%s type=%s",
            session_id,
            type(error).__name__,
        )
    finally:
        db.close()


def latest_for_session(db: Session, session_id: uuid.UUID) -> Optional[AudioFeature]:
    """가장 최근 voice_marks 행. 없으면 None(아직 계산 전 — 화면은 '분석 전')."""

    return db.scalar(
        select(AudioFeature)
        .where(AudioFeature.session_id == session_id, AudioFeature.extractor == EXTRACTOR)
        .order_by(AudioFeature.created_at.desc(), AudioFeature.id.desc())
        .limit(1)
    )


def _child_keys(segments: List[Dict[str, Any]]) -> Set[Tuple[Any, Any, Any]]:
    return {
        (segment.get("segment_id"), segment.get("start_ms"), segment.get("end_ms"))
        for segment in segments
        if isinstance(segment, dict) and segment.get("speaker") == Speaker.CHILD.value
    }


def needs_reanalysis_after_confirm(db: Session, transcript: Transcript) -> bool:
    """확정본의 아동 구간(segment_id · start_ms · end_ms)이 마지막 분석 때와 다르면 True.

    STT 직후엔 화자 역할이 UNKNOWN 이어서 아동 구간이 0개였다가 상담사가 검수에서 화자를 정하는 경우가
    대표적이다. 행이 없으면(STT 때 꺼져 있었거나 저장 실패) 한 번 돌린다.
    """

    if not is_enabled():
        return False

    latest = latest_for_session(db, transcript.session_id)

    if latest is None:
        return True

    previous = latest.features.get("segments", []) if isinstance(latest.features, dict) else []

    return _child_keys(previous) != _child_keys(segment_inputs(transcript))


def start_voice_marks_warmup() -> Optional[threading.Thread]:
    """서버 시작 때 numba 컴파일을 미리 끝낸다(stt/voice_marks.warm_up). 기다리지 않고, 실패해도 서버는 뜬다."""

    if settings.VOICE_MARKS_PROVIDER != "module":
        return None

    def run() -> None:
        try:
            warm_up = load_callable(settings.VOICE_MARKS_MODULE, "warm_up")
            ok = warm_up()
        except Exception as error:
            logger.warning(
                "음성 참고 표시 모듈을 미리 준비하지 못했습니다. type=%s", type(error).__name__
            )
        else:
            logger.info("음성 참고 표시 모듈 준비 %s", "완료" if ok else "실패(첫 분석 때 다시 시도)")

    thread = threading.Thread(target=run, name="voice-marks-warmup", daemon=True)
    thread.start()

    return thread
