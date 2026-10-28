# STT 검수 '1차 임시 핵심 발화' 스캔(API_CONTRACT 7절, I-SPOT_DOCS/docs/PROPOSAL_stt_key_scan.md).
#
# process_stt 가 전사 결과를 저장하기 직전, 같은 작업 안에서 부른다. AI 함수
# ai/modeling/abuse/contract_adapter.key_scan_as_contract(stt_result) 가 1차 분류기(로컬 모델)만 돌려
# {model, segments[{segment_id, abuse_types}]} 를 주고, 여기서 status 를 붙인다.
#  - DONE    : 스캔 성공(segments 가 비어도 DONE)
#  - FAILED  : 시간 초과 · 예외 · 모양이 다름. STT 는 그대로 성공이다(실패는 서버 로그에만, 원문 · 예외 문구는 남기지 않음).
#  - SKIPPED : AI_PROVIDER 가 modeling 이 아니다(모듈을 부르지 않음).
# 판정이 아니라 '먼저 들어볼 곳' 이다(05_RULES §1). 원문이 서버 밖으로 나가지 않고 감사 기록은 두지 않는다(STT 작업의 일부).

from typing import Any, Callable, Dict, Iterable, List, Optional

from app.adapters.module_loader import ModuleLoadError, load_callable
from app.core.concurrency import OperationTimeout, run_with_timeout
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

KEY_SCAN_MODULE = "ai.modeling.abuse.contract_adapter"
KEY_SCAN_FUNCTION = "key_scan_as_contract"

STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"

ABUSE_TYPES = ("PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT")


def _result(status: str, model: Optional[str] = None, segments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {"status": status, "model": model, "segments": segments or []}


def _load_scanner() -> Callable[[Dict[str, Any]], Any]:
    """시험은 이 함수를 바꿔 가짜 스캐너를 넣는다."""

    return load_callable(KEY_SCAN_MODULE, KEY_SCAN_FUNCTION)


def _clean(raw: Any, known_ids: Iterable[str]) -> Optional[Dict[str, Any]]:
    """모듈 결과를 저장할 모양으로 다듬는다. 모양이 틀리면 None(→ FAILED).

    원문에 없는 segment_id · 모르는 유형은 버리고, 같은 발화가 두 번 오면 처음 것만 둔다. 유형이 남지 않은 발화는 뺀다.
    순서는 원문 순서로 맞춘다.
    """

    if not isinstance(raw, dict) or not isinstance(raw.get("segments"), list):
        return None

    model = raw.get("model")
    order = {segment_id: index for index, segment_id in enumerate(known_ids)}
    picked: Dict[str, List[str]] = {}

    for item in raw["segments"]:
        if not isinstance(item, dict):
            return None

        segment_id = item.get("segment_id")
        abuse_types = item.get("abuse_types")

        if not isinstance(segment_id, str) or not isinstance(abuse_types, list):
            return None

        if segment_id not in order or segment_id in picked:
            continue

        kept = [value for value in dict.fromkeys(abuse_types) if value in ABUSE_TYPES]

        if kept:
            picked[segment_id] = kept

    segments = [
        {"segment_id": segment_id, "abuse_types": picked[segment_id]}
        for segment_id in sorted(picked, key=order.__getitem__)
    ]

    return _result(STATUS_DONE, model if isinstance(model, str) else None, segments)


def scan(stt_contract: Dict[str, Any]) -> Dict[str, Any]:
    """전사 결과(STT Contract dict)를 1차 스캔한다. 어떤 실패든 예외를 올리지 않고 FAILED 를 돌려준다."""

    if settings.AI_PROVIDER != "modeling":
        return _result(STATUS_SKIPPED)

    known_ids = [
        str(segment.get("segment_id"))
        for segment in stt_contract.get("segments") or []
        if isinstance(segment, dict)
    ]

    try:
        scanner = _load_scanner()
    except ModuleLoadError as error:
        logger.warning("1차 핵심 발화 스캔 모듈을 불러오지 못했습니다. type=%s", type(error).__name__)
        return _result(STATUS_FAILED)

    try:
        raw = run_with_timeout(lambda: scanner(stt_contract), settings.KEY_SCAN_TIMEOUT_SECONDS)
    except OperationTimeout:
        logger.warning("1차 핵심 발화 스캔이 제한 시간(%.0f초)을 넘겼습니다.", settings.KEY_SCAN_TIMEOUT_SECONDS)
        return _result(STATUS_FAILED)
    except Exception as error:
        logger.warning("1차 핵심 발화 스캔 중 오류. type=%s", type(error).__name__)
        return _result(STATUS_FAILED)

    cleaned = _clean(raw, known_ids)

    if cleaned is None:
        logger.warning("1차 핵심 발화 스캔 결과가 기대한 모양이 아닙니다. type=%s", type(raw).__name__)
        return _result(STATUS_FAILED)

    logger.info("1차 핵심 발화 스캔 완료 count=%s", len(cleaned["segments"]))

    return cleaned


def copy_for_new_version(previous: Optional[Dict[str, Any]], removed_segment_ids: Iterable[str]) -> Optional[Dict[str, Any]]:
    """원문 수정으로 새 version 을 만들 때 직전 값을 복사한다. 지운 발화만 빼고 문장이 바뀐 발화도 다시 스캔하지 않는다."""

    if not isinstance(previous, dict):
        return None

    removed = set(removed_segment_ids)
    segments = previous.get("segments") if isinstance(previous.get("segments"), list) else []

    return {
        **previous,
        "segments": [
            item for item in segments if isinstance(item, dict) and item.get("segment_id") not in removed
        ],
    }
