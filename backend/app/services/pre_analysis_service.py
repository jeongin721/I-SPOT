# 원문 확정 전 AI 전체 분석(2026-11-24, ANALYZE_BEFORE_CONFIRM — 팀장님 확인: 확정 전에도 이름을 가린 원문 전체를 외부 AI 로).
#
# 흐름:
#   1) STT 작업(transcript_service.process_stt)이 전사 뒤 같은 작업에서 run() 으로 AI 전체 분석을 돌린다 — 지금 분석과 같은
#      어댑터 · 사례 정보 · 등록 이름 · 이름 가리기. 회차는 그동안 STT_PROCESSING 이라 화면은 '변환 중' 이다(분석이 끝나야 원문이 보임).
#   2) 결과 가운데 위험 발화(risk_utterances)로 '먼저 들어볼 곳'(transcripts.key_scan, model=ai_analysis)을 채운다 — as_key_scan.
#      key_scan 은 암호화하지 않는 칸이라 발화 번호 · 유형 · 공개 조문 · 세부 유형 이름 · 근거 직접성만 넣는다(원문 글 · 이유 글 X).
#   3) 결과 전체(AIAnalysisBundle)는 그 전사 판의 pre_analysis 에 암호문으로 둔다 — dump.
#   4) 상담사가 원문을 확정하고 첫 분석이 돌 때(analysis_service.process_analysis) cached_bundle() 이, 근거로 쓰인 줄의 글 · 화자가
#      확정 판에서도 그대로면 그 결과를 다시 쓴다(외부 AI 를 다시 부르지 않음). 근거 줄을 하나라도 고쳤으면 None → 새로 분석.
#      재분석(두 번째 분석부터)은 늘 새로 한다.
# 실패(시간 초과 · 어댑터 오류)하면 None — STT 는 1차 스캔(key_scan_service.scan)으로 돌아가 그대로 성공한다.

import re
import time
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ai_adapter import AIAnalysisBundle, drop_ungrounded_risk_items
from app.core.concurrency import run_with_timeout
from app.core.config import settings
from app.core.enums import AnalysisStatus
from app.core.logging import get_logger
from app.models.analysis import AIAnalysis
from app.models.session import ConsultationSession
from app.models.transcript import Transcript
from app.schemas.contracts import AIAnalysisResult, SummaryEvidenceItem

logger = get_logger(__name__)

#: '먼저 들어볼 곳' 을 이 분석으로 채웠다는 표시(key_scan.model). 화면 덧말 · 원문 수정 뒤 다시 스캔 여부가 이 값을 본다.
KEY_SCAN_MODEL = "ai_analysis"

_ABUSE_TYPES = {"PHYSICAL", "EMOTIONAL", "SEXUAL", "NEGLECT"}
_STRENGTH_LABELS = {"HIGH": "높음", "MEDIUM": "중간", "LOW": "낮음"}
_REFERENCE_KEYS = ("law_name", "article", "item_label", "text", "portal_url")
_REFERENCE_LIMITS = {"law_name": 100, "article": 50, "item_label": 50, "text": 1000, "portal_url": 500}
#: 발화 하나에 붙이는 조문 수 상한(key_scan_service 와 같은 뜻).
MAX_REFERENCES_PER_SEGMENT = 3


def enabled() -> bool:
    return bool(settings.ANALYZE_BEFORE_CONFIRM) and settings.AI_PROVIDER == "modeling"


# 성 + 이름 2~3글자(세 글자 이상) 한글 이름. 두 글자 이름의 비슷한 표기는 너무 많이 걸려 보지 않는다.
_HANGUL_NAME = re.compile(r"^[가-힣]{3,4}$")


def similar_name_variants(text: str, names: List[str]) -> List[str]:
    """등록 이름과 성이 같고 이름 한 글자만 다른 표기 — 확정 전 STT 오인식(김수아 → 김수하)도 가리려고(민규 #191 · 11/24).
    더 가리는 쪽으로만 틀린다(같은 성의 다른 사람 이름을 가려도 안전)."""

    variants: List[str] = []
    seen = set(names)

    for name in names:
        if not _HANGUL_NAME.match(name):
            continue

        size = len(name)

        for start in range(len(text) - size + 1):
            word = text[start : start + size]

            if word in seen or word[0] != name[0] or not _HANGUL_NAME.match(word):
                continue

            if sum(1 for a, b in zip(word, name, strict=True) if a != b) == 1:
                variants.append(word)
                seen.add(word)

    return variants


def _known_identifiers(db: Session, session: ConsultationSession, adapter, stt_contract: Dict[str, Any]) -> Any:
    """가리기에 넘길 등록 이름 + 한 글자 다른 표기. 이름을 받지 않는 어댑터면 None. **등록 이름을 못 읽으면 False** — 보내지 않는다
    (확정 전 원문은 아무도 읽지 않은 STT 결과라 실명을 놓치면 그대로 나간다, 민규 11/24)."""

    from app.adapters.ai_adapter import accepts_keyword
    from app.services import personal_info_service

    if not accepts_keyword(adapter.analyze, "known_identifiers"):
        return None

    names = personal_info_service.known_identifiers(db, session.case_id, strict=True)

    if names is None:
        return False

    text = "\n".join(str(segment.get("text") or "") for segment in stt_contract.get("segments") or [] if isinstance(segment, dict))

    return sorted(dict.fromkeys(names + similar_name_variants(text, names)), key=len, reverse=True)


def run(db: Session, session: ConsultationSession, stt_contract: Dict[str, Any]) -> Optional[AIAnalysisBundle]:
    """확정 전 원문(STT 결과)으로 AI 전체 분석을 돌린다. 어떤 실패든 None(로그만) — STT 를 실패시키지 않는다."""

    # analysis_service 가 transcript_service 를 import 해서 여기서 늦게 부른다.
    from app.services import analysis_service

    try:
        adapter = analysis_service.get_ai_adapter()
        deadline = time.monotonic() + analysis_service.PREPARE_TIMEOUT_SECONDS + settings.AI_TIMEOUT_SECONDS
        case_context = analysis_service._build_case_context(db, session)
        known_identifiers = _known_identifiers(db, session, adapter, stt_contract)

        if known_identifiers is False:
            logger.warning("등록 이름을 읽지 못해 원문 확정 전 AI 분석을 보내지 않고 1차 스캔으로 돌아갑니다. session_id=%s", session.id)
            return None
        analysis_service._prepare_adapter(adapter, deadline)
        limit = analysis_service._time_limit(deadline, settings.AI_TIMEOUT_SECONDS)
        bundle = run_with_timeout(
            lambda: analysis_service._analyze(adapter, stt_contract, limit, case_context, known_identifiers),
            limit,
        )
    except Exception as error:  # noqa: BLE001 — 확정 전 분석은 STT 를 실패시키지 않는다
        logger.warning("원문 확정 전 AI 분석을 하지 못해 1차 스캔으로 돌아갑니다. session_id=%s type=%s", session.id, type(error).__name__)
        return None

    if not isinstance(bundle, AIAnalysisBundle):
        logger.warning("원문 확정 전 AI 분석 결과가 기대한 모양이 아닙니다. session_id=%s", session.id)
        return None

    logger.info("원문 확정 전 AI 분석 완료 session_id=%s risk=%s", session.id, len(bundle.result.risk_utterances))

    return bundle


def as_key_scan(bundle: AIAnalysisBundle, stt_contract: Dict[str, Any]) -> Dict[str, Any]:
    """위험 발화를 '먼저 들어볼 곳' 모양으로(원문 순서). 암호화하지 않는 칸이라 글은 넣지 않는다."""

    order = [str(segment.get("segment_id")) for segment in stt_contract.get("segments") or [] if isinstance(segment, dict)]
    known = set(order)
    by_segment: Dict[str, Dict[str, Any]] = {}

    for utterance in bundle.result.risk_utterances:
        if not isinstance(utterance, dict):
            continue

        abuse_type = utterance.get("abuse_type")

        if abuse_type not in _ABUSE_TYPES:
            continue

        why = " · ".join(
            part
            for part in (
                utterance.get("subtype") if isinstance(utterance.get("subtype"), str) else "",
                f"근거 직접성 {_STRENGTH_LABELS[utterance.get('evidence_strength')]}"
                if utterance.get("evidence_strength") in _STRENGTH_LABELS
                else "",
            )
            if part
        )[:300]

        for segment_id in utterance.get("segment_ids") or []:
            if not isinstance(segment_id, str) or segment_id not in known:
                continue

            entry = by_segment.setdefault(segment_id, {"segment_id": segment_id, "abuse_types": [], "legal_references": []})

            if abuse_type not in entry["abuse_types"]:
                entry["abuse_types"].append(abuse_type)

            for reference in utterance.get("legal_references") or []:
                if not isinstance(reference, dict) or len(entry["legal_references"]) >= MAX_REFERENCES_PER_SEGMENT:
                    continue

                cleaned = {
                    key: (reference.get(key) or "")[:limit] if isinstance(reference.get(key), str) else ""
                    for key, limit in _REFERENCE_LIMITS.items()
                }

                if not cleaned["law_name"] or not cleaned["article"]:
                    continue

                cleaned.update({"abuse_type": abuse_type, "excerpt": why, "score": None})

                if not any(
                    (item["abuse_type"], item["law_name"], item["article"], item["item_label"])
                    == (abuse_type, cleaned["law_name"], cleaned["article"], cleaned["item_label"])
                    for item in entry["legal_references"]
                ):
                    entry["legal_references"].append(cleaned)

    segments = [by_segment[segment_id] for segment_id in order if segment_id in by_segment]

    return {"status": "DONE", "model": KEY_SCAN_MODEL, "segments": segments}


def dump(bundle: Optional[AIAnalysisBundle]) -> Optional[Dict[str, Any]]:
    if bundle is None:
        return None

    return {
        "result": bundle.result.model_dump(mode="json"),
        "summary_evidence": [item.model_dump(mode="json") for item in bundle.summary_evidence],
        "provider": bundle.provider,
        "model": bundle.model,
    }


def _load(data: Any) -> Optional[AIAnalysisBundle]:
    if not isinstance(data, dict):
        return None

    try:
        return AIAnalysisBundle(
            result=AIAnalysisResult.model_validate(data.get("result")),
            summary_evidence=[SummaryEvidenceItem.model_validate(item) for item in data.get("summary_evidence") or []],
            provider=str(data.get("provider") or "modeling"),
            model=data.get("model"),
        )
    except Exception as error:  # noqa: BLE001 — 저장한 값을 못 읽으면 새로 분석한다
        logger.warning("저장한 확정 전 분석을 읽지 못해 새로 분석합니다. type=%s", type(error).__name__)
        return None


def evidence_segment_ids(bundle: AIAnalysisBundle) -> Set[str]:
    """결과가 근거로 든 발화 번호 전부 — 결과 어디든 segment_ids · segment_id 칸(위험 3필드 · 심각도 · 보호 요인 · 확인사항 ·
    요약 판단 · 안전 플래그 · 주제 등)과 요약 근거(summary_evidence)."""

    ids: Set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "segment_ids" and isinstance(item, list):
                    ids.update(segment_id for segment_id in item if isinstance(segment_id, str))
                elif key == "segment_id" and isinstance(item, str):
                    ids.add(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(bundle.result.model_dump(mode="json"))
    walk([item.model_dump(mode="json") for item in bundle.summary_evidence])

    return ids


def _texts(transcript: Transcript) -> Dict[str, tuple]:
    return {segment.segment_id: (segment.speaker.value, segment.text) for segment in transcript.segments}


def cached_bundle(db: Session, session: ConsultationSession, transcript: Transcript) -> Optional[AIAnalysisBundle]:
    """확정한 원문(transcript)으로 첫 분석을 할 때, 확정 전 분석의 근거 줄이 그대로면 그 결과. 아니면 None(새로 분석)."""

    # 첫 분석일 때만 — 끝난 분석이 이미 있으면(재분석) 늘 새로 한다.
    finished = db.scalar(
        select(AIAnalysis.id).where(
            AIAnalysis.session_id == session.id,
            AIAnalysis.status == AnalysisStatus.COMPLETED,
        )
    )

    if finished is not None:
        return None

    source = db.scalar(
        select(Transcript)
        .where(
            Transcript.session_id == session.id,
            Transcript.version <= transcript.version,
            Transcript.pre_analysis_enc.is_not(None),
        )
        .order_by(Transcript.version.desc())
    )

    if source is None:
        return None

    bundle = _load(source.pre_analysis)

    if bundle is None:
        return None

    before = _texts(source)
    after = _texts(transcript)
    changed = [segment_id for segment_id in evidence_segment_ids(bundle) if before.get(segment_id) != after.get(segment_id)]

    if changed:
        logger.info(
            "근거 줄을 고쳐 확정 전 분석을 다시 쓰지 않고 새로 분석합니다. session_id=%s changed=%s", session.id, len(changed)
        )
        return None

    # 근거가 아닌 줄을 지웠을 수 있어 확정 판으로 근거 검사를 한 번 더 한다(없는 번호를 가리키는 항목은 뺌).
    from app.services import transcript_service

    result, _ = drop_ungrounded_risk_items(bundle.result, transcript_service.transcript_to_contract(transcript))
    logger.info("근거 줄이 그대로라 확정 전 분석 결과를 다시 씁니다. session_id=%s from_version=%s", session.id, source.version)

    return AIAnalysisBundle(result=result, summary_evidence=bundle.summary_evidence, provider=bundle.provider, model=bundle.model)
