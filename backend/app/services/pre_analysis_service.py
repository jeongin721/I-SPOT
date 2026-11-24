# 원문 확정 전 AI 전체 분석(2026-11-24, ANALYZE_BEFORE_CONFIRM — 팀장님 확인: 확정 전에도 이름을 가린 원문 전체를 외부 AI 로).
#
# 흐름:
#   1) STT 작업(transcript_service.process_stt)이 전사 뒤 같은 작업에서 run() 으로 AI 전체 분석을 돌린다 — 지금 분석과 같은
#      어댑터 · 사례 정보 · 등록 이름 · 이름 가리기. 회차는 그동안 STT_PROCESSING 이라 화면은 '변환 중' 이다(분석이 끝나야 원문이 보임).
#   2) 결과 가운데 위험 발화(risk_utterances)로 '먼저 들어볼 곳'(transcripts.key_scan, model=ai_analysis)을 채운다 — as_key_scan.
#      key_scan 은 암호화하지 않는 칸이라 발화 번호 · 유형 · 공개 조문 · 세부 유형 이름 · 근거 직접성만 넣는다(원문 글 · 이유 글 X).
#   3) 결과 전체(AIAnalysisBundle)는 그 전사 판의 pre_analysis 에 암호문으로 둔다 — dump.
#   4) 상담사가 원문을 확정하고 첫 분석이 돌 때(analysis_service.process_analysis) cached_bundle() 이, 확정한 원문의 모든 발화가
#      확정 판 바로 앞 STT 판과 같으면 그 결과를 다시 쓴다(외부 AI 를 다시 부르지 않음, 2단계 경고 · 감사 기록에 판 번호).
#      하나라도 고쳤으면 None → 새로 분석(민규 #195 리뷰 — 근거가 아닌 줄을 바로잡은 것도 반영). 재분석은 늘 새로 한다.
#   확정 전 외부 전송은 감사 기록(PRE_ANALYSIS_SENT)에 남긴다.
# 실패(시간 초과 · 어댑터 오류)하면 None — STT 는 1차 스캔(key_scan_service.scan)으로 돌아가 그대로 성공한다.

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.ai_adapter import AIAnalysisBundle, drop_ungrounded_risk_items
from app.core.concurrency import run_with_timeout
from app.core.config import settings
from app.core.enums import AnalysisStatus, AuditAction, TranscriptSource
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


def _jamo(char: str) -> tuple:
    """한글 음절 → (첫소리, 모음, 받침) 번호."""

    code = ord(char) - 0xAC00
    return code // 588, (code % 588) // 28, code % 28


def _sounds_alike(a: str, b: str) -> bool:
    """두 음절이 첫소리만 다르다(모음 · 받침이 같다) — STT 가 흔히 헷갈리는 꼴(수아 → 수하, ㅇ ↔ ㅎ)."""

    first_a, vowel_a, final_a = _jamo(a)
    first_b, vowel_b, final_b = _jamo(b)
    return first_a != first_b and (vowel_a, final_a) == (vowel_b, final_b)


def _is_hangul(char: str) -> bool:
    return "가" <= char <= "힣"


def similar_name_variants(text: str, names: List[str]) -> List[str]:
    """등록 이름과 성이 같고 이름 한 글자만 **첫소리가 다른** 표기 — 확정 전 STT 오인식(김수아 → 김수하)도 가리려고(민규 #191 · 11/24).

    일반 낱말을 가리지 않게(민규 #195 리뷰 — '하지원' → '하지만', '고민지' → '고민이'):
    - 다른 한 글자는 모음 · 받침이 같고 첫소리만 달라야 한다(소리가 비슷한 오인식만).
    - 앞 글자가 한글이면(더 긴 낱말의 가운데) 보지 않는다. 뒤가 한글이면 조사(가 · 는 · 이 · 야 · 랑 · 한테 등)일 때만.
    그래도 남는 오탐은 더 가리는 쪽이다(같은 성의 다른 사람 이름을 가려도 안전)."""

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

            if start > 0 and _is_hangul(text[start - 1]):
                continue

            rest = text[start + size :]

            if rest and _is_hangul(rest[0]) and not rest.startswith(_PARTICLES):
                continue

            differ = [(a, b) for a, b in zip(word, name, strict=True) if a != b]

            # 마지막 글자가 바뀌어 조사가 된 꼴('고민지' → '고민' + '이')은 낱말 + 조사로 본다.
            if word[-1] != name[-1] and word[-1] in _ONE_CHAR_PARTICLES:
                continue

            if len(differ) == 1 and _sounds_alike(*differ[0]):
                variants.append(word)
                seen.add(word)

    return variants


# 이름 바로 뒤에 붙는 조사 · 부름말. 뒤가 한글인데 이것으로 시작하지 않으면 더 긴 낱말로 본다.
_ONE_CHAR_PARTICLES = set("가는은이야아도를을의")
_PARTICLES = ("이가", "이는", "이랑", "이도", "이를", "이한테", "한테", "에게", "랑", "가", "는", "은", "이", "야", "아", "도", "를", "을", "의", "씨", "님")


def _known_identifiers(db: Session, session: ConsultationSession, adapter, stt_contract: Dict[str, Any]) -> Any:
    """가리기에 넘길 등록 이름 + 한 글자 다른 표기. 이름을 받지 않는 어댑터면 None. **등록 이름을 못 읽거나 하나도 없으면 False** — 보내지 않는다
    (확정 전 원문은 아무도 읽지 않은 STT 결과라 실명을 놓치면 그대로 나간다, 민규 11/24)."""

    from app.adapters.ai_adapter import accepts_keyword
    from app.services import personal_info_service

    if not accepts_keyword(adapter.analyze, "known_identifiers"):
        return None

    names = personal_info_service.known_identifiers(db, session.case_id, strict=True)

    # 등록 이름이 하나도 없어도 보내지 않는다(민규 #195 리뷰 6, 경진 11/24 — 초기면접지를 늘 먼저 쓰므로 실제로는 늘 있다.
    # 없으면 한 글자 다른 이름까지 가리는 안전장치가 작동하지 않는다).
    if not names:
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
            logger.warning("등록 이름을 읽지 못했거나 없어 원문 확정 전 AI 분석을 보내지 않고 1차 스캔으로 돌아갑니다. session_id=%s", session.id)
            return None

        # 확정 전 원문 전체를 외부 AI 로 보낸다는 기록(민규 #195 리뷰). 글 · 이름은 남기지 않는다(발화 수 · 가린 등록 이름 수만).
        from app.services import audit_service

        audit_service.record(
            db,
            action=AuditAction.PRE_ANALYSIS_SENT,
            entity_type="ConsultationSession",
            entity_id=session.id,
            case_id=session.case_id,
            session_id=session.id,
            detail={
                "segments": len(stt_contract.get("segments") or []),
                "registered_names": len(known_identifiers) if isinstance(known_identifiers, list) else None,
            },
        )
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


def _lines(transcript: Transcript) -> list:
    return [
        (segment.segment_id, segment.speaker.value, segment.text)
        for segment in sorted(transcript.segments, key=lambda item: item.order_index)
    ]


@dataclass
class Reuse:
    bundle: AIAnalysisBundle
    #: 이 결과를 만든 STT 원문 판 번호(2단계 경고 · 감사 기록에 남김).
    from_version: int


def reuse_warning(from_version: int) -> str:
    return f"원문 확정 전 AI 분석(원문 {from_version}판)을 그대로 썼습니다 — 확정한 원문이 그 판과 같아 다시 분석하지 않았습니다."


def cached_bundle(db: Session, session: ConsultationSession, transcript: Transcript) -> Optional[Reuse]:
    """확정한 원문(transcript)으로 첫 분석을 할 때 다시 쓸 확정 전 분석. 아니면 None(새로 분석).

    다시 쓰는 조건(민규 #195 리뷰 11/24):
    - 스위치가 켜져 있고, 이 회차의 첫 분석이다(재분석은 늘 새로).
    - 확정 판 바로 앞의 STT 판(재전사했으면 새 판)에 확정 전 분석이 있다 — 옛 녹음 판 결과는 쓰지 않는다.
    - 확정한 원문의 **모든 발화**(번호 · 화자 · 글 · 개수 · 순서)가 그 STT 판과 같다 — 근거가 아닌 줄(모델이 놓친 위험 발화를 상담사가
      바로잡은 줄)을 고쳐도 새로 분석한다.
    - 저장한 값을 풀지 못하면 새로 분석한다(되풀이 실패 막기)."""

    if not enabled():
        return None

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
            Transcript.source == TranscriptSource.STT,
        )
        .order_by(Transcript.version.desc())
    )

    if source is None or source.pre_analysis_enc is None:
        return None

    if _lines(source) != _lines(transcript):
        logger.info("확정한 원문이 확정 전 분석 판과 달라 새로 분석합니다. session_id=%s from_version=%s", session.id, source.version)
        return None

    try:
        data = source.pre_analysis
    except Exception as error:  # noqa: BLE001 — 못 풀면 새로 분석한다
        logger.warning("저장한 확정 전 분석을 풀지 못해 새로 분석합니다. session_id=%s type=%s", session.id, type(error).__name__)
        return None

    bundle = _load(data)

    if bundle is None:
        return None

    from app.services import transcript_service

    result, _ = drop_ungrounded_risk_items(bundle.result, transcript_service.transcript_to_contract(transcript))
    result = result.model_copy(update={"warnings": [*result.warnings, reuse_warning(source.version)]})
    logger.info("확정한 원문이 같아 확정 전 분석 결과를 다시 씁니다. session_id=%s from_version=%s", session.id, source.version)

    return Reuse(
        bundle=AIAnalysisBundle(result=result, summary_evidence=bundle.summary_evidence, provider=bundle.provider, model=bundle.model),
        from_version=source.version,
    )
