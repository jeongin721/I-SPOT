# 다음 상담 체크리스트 Adapter — FollowupQ '다음 상담 전 확인할 사항' · 추가 질문 공식 근거
# (API_CONTRACT 19절, specs followup-rag-checklist, 2026-10-30). 닫힌 #117 의 followup_adapter 를 바탕으로 했다.
#
# rag/session.analyze_reviewed_transcript(팀장님 공식 근거 RAG)를 부른다. 분석 어댑터(ai_adapter)와 같은 모양
# (Protocol + mock + module + provider 스위치)이다.
#  - mock  : OpenAI 없이 이번 회차 첫 아동 발화로 '(예시)' 결과를 만든다. 화면 개발 · CI 용.
#  - module: rag 를 with_questions=False · with_manual_references=False 로 부른다. 추가 질문은 #118 초안 하나에서만
#            만들므로(팀장님 10/29 결정 ②) rag 는 질문을 만들지 않고, 확인할 사항과 넘겨준 초안에 검토를 통과한
#            공식 근거만 붙인다(rag/official_evidence.py). 아동 발화 · 이전 회차 기록 · 초안은 rag 가 가린 뒤 OpenAI 로
#            보낸다. 가린 뒤 재검사를 통과하지 못하면 보내지 않고 AI_PRIVACY_BLOCKED 로 끝난다.
#
# 결과는 normalize_result 로 schemas.followup_checklist.ChecklistResult 모양으로 정리한다. 모양이 틀린 항목 · 근거가 없는 항목 ·
# 판정 · 단정 표현이 있는 항목은 빼고 dropped 에 센다. 실패는 예외 **종류**로 코드를 정하고 문구는 버린다 — 예외 문구에
# 상담 발화 · 인증값이 섞일 수 있다(map_ai_error 와 같은 원칙).

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol

from pydantic import ValidationError

from app.adapters.ai_adapter import export_llm_env
from app.adapters.law_qa_adapter import export_law_env
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode
from app.schemas.followup_checklist import ChecklistBasis, ChecklistItem, ChecklistResult, QuestionEvidence

# 코드별 고정 문구. 행(error_message)과 화면으로 나가므로 발화 · 예외 원문을 넣지 않는다.
FOLLOWUP_MESSAGES: Dict[ErrorCode, str] = {
    ErrorCode.AI_TIMEOUT: "다음 상담 체크리스트를 제한 시간 안에 만들지 못했습니다. 다시 만들어 주세요.",
    ErrorCode.AI_PRIVACY_BLOCKED: (
        "비식별 검증을 통과하지 못해 외부로 보내지 않았습니다. "
        "상담 기록에 이름 · 학교 · 연락처가 남아 있는지 확인해 주세요."
    ),
    ErrorCode.AI_INVALID_OUTPUT: "다음 상담 체크리스트 결과 형식이 올바르지 않습니다.",
    ErrorCode.AI_FAILED: "다음 상담 체크리스트를 만들지 못했습니다. 잠시 후 다시 만들어 주세요.",
}

NOTICE_NO_ABUSE_TYPE = "감지된 학대 유형 신호가 없어 확인 사항을 만들지 않았습니다."
NOTICE_NO_CHILD_SPEECH = "이번 회차에 아동 발화가 없어 확인 사항을 만들지 않았습니다."
NOTICE_MOCK = "예시(mock) 결과입니다. 실제 분석 · 공식 근거가 아닙니다."

# rag validation 의 사유 칸 → 화면 안내(고정 문구). rag 가 싣는 사유 문장은 쓰지 않는다.
VALIDATION_NOTICES = (
    ("official_review_error", "공식 근거 검토를 하지 못해 공식 근거를 빼고 보였습니다."),
    ("question_link_error", "추가 질문에 공식 근거를 잇지 못했습니다."),
    ("official_skipped", "찾은 공식 근거가 없어 공식 근거 없이 보였습니다."),
)
# rag 가 결과 맨 위에 다는 안내(고정 문구). 문장에 상담 내용이 없다.
RAG_WARNING_NOTICES = {
    "case_context_warning": "이전 회차 기록이 비식별 검증을 통과하지 못해 이번 회차 아동 발화만 썼습니다.",
    "question_link_warning": "추가 질문 문장이 비식별 검증을 통과하지 못해 질문에 공식 근거를 붙이지 않았습니다.",
}
# rag validation 에서 옮겨 세는 수
RAG_DROPPED_COUNTS = ("official_unlinked", "official_review_rejected")


class FollowupChecklistError(Exception):
    """다음 상담 체크리스트 만들기 실패. 문구는 코드별 고정 문구이고 원인은 예외 종류 이름(cause_name)만 남긴다."""

    def __init__(self, code: ErrorCode, cause_name: str = "") -> None:
        super().__init__(FOLLOWUP_MESSAGES[code])
        self.code = code
        self.cause_name = cause_name

    @property
    def message(self) -> str:
        return FOLLOWUP_MESSAGES[self.code]


def map_followup_error(error: Exception) -> FollowupChecklistError:
    if isinstance(error, FollowupChecklistError):
        return error

    name = type(error).__name__

    if isinstance(error, TimeoutError):
        return FollowupChecklistError(ErrorCode.AI_TIMEOUT, name)

    if name == "RagPrivacyBlocked":
        return FollowupChecklistError(ErrorCode.AI_PRIVACY_BLOCKED, name)

    return FollowupChecklistError(ErrorCode.AI_FAILED, name)


@dataclass
class FollowupChecklistInput:
    """rag 에 넘기는 값. 만드는 곳은 followup_checklist_service.build_input."""

    transcript: Dict[str, Any]
    # physical · emotional · sexual · neglect · multiple. 감지된 유형이 없으면 None(module 은 rag 를 부르지 않는다).
    abuse_type: Optional[str]
    session_no: int
    session_id: str
    previous_sessions: List[Dict[str, Any]] = field(default_factory=list)
    # 추가 질문 AI 초안 [{draft_index, text, reason}] — 분석 result.followup_questions 순서 그대로(draft_index = 그 위치).
    drafts: List[Dict[str, Any]] = field(default_factory=list)


class FollowupChecklistAdapter(Protocol):
    name: str

    def build(self, payload: FollowupChecklistInput) -> Dict[str, Any]:
        """ChecklistResult 모양(dict)을 돌려준다. 실패는 FollowupChecklistError(또는 map_followup_error 로 바꿀 예외)."""


# =========================================================
# 결과 정리
# =========================================================

def _judgment_check() -> Callable[[str], Optional[str]]:
    """판정 · 단정 표현 검사(ai/modeling/abuse/question_rules — rag 와 같은 기준). ai/ 는 이미지에 늘 들어 있다."""

    ensure_repo_root_on_path()

    from ai.modeling.abuse.question_rules import judgment_reason

    return judgment_reason


def _bump(dropped: Dict[str, int], key: str, count: int = 1) -> None:
    dropped[key] = dropped.get(key, 0) + count


def _clean_basis(raw: Any) -> List[ChecklistBasis]:
    """근거 목록에서 모양이 맞는 것만 남긴다(틀린 근거 하나 때문에 항목째 버리지 않는다)."""

    if not isinstance(raw, list):
        return []

    basis: List[ChecklistBasis] = []

    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            basis.append(ChecklistBasis.model_validate(entry))
        except ValidationError:
            continue

    return basis


def _clean_check_items(raw_items: List[Any], judgment, dropped: Dict[str, int]) -> List[ChecklistItem]:
    items: List[ChecklistItem] = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            _bump(dropped, "invalid")
            continue

        basis = _clean_basis(raw.get("basis"))

        if not basis:
            # 근거 없는 확인 사항은 보이지 않는다(공식 근거만 있다가 검토에서 다 빠진 경우도 여기로 온다).
            _bump(dropped, "no_basis")
            continue

        try:
            item = ChecklistItem.model_validate(
                {
                    "id": raw.get("id"),
                    # rag 는 item, mock 은 text 로 준다.
                    "text": raw.get("text") if raw.get("text") is not None else raw.get("item"),
                    "kind": raw.get("kind"),
                    "priority": raw.get("priority"),
                    "reason": raw.get("reason") or "",
                    "basis": [entry.model_dump() for entry in basis],
                }
            )
        except ValidationError:
            _bump(dropped, "invalid")
            continue

        if judgment(item.text) or judgment(item.reason):
            _bump(dropped, "judgment")
            continue

        items.append(item)

    return items


def _clean_question_evidence(
    raw_list: List[Any],
    drafts: List[Dict[str, Any]],
    judgment,
    dropped: Dict[str, int],
) -> List[QuestionEvidence]:
    """초안에 붙인 공식 근거. 공식 근거(type ≠ case)이고 이유(why)가 있는 것만, 넘긴 초안 번호에만 붙인다.

    text 는 rag 가 돌려준 문장이 아니라 넘긴 초안 문장 그대로 쓴다(화면이 지금 초안과 똑같은지 대조한다).
    """

    by_index = {draft["draft_index"]: draft for draft in drafts}
    seen: set = set()
    evidence: List[QuestionEvidence] = []

    for raw in raw_list:
        index = raw.get("draft_index") if isinstance(raw, dict) else None

        if not isinstance(index, int) or isinstance(index, bool) or index not in by_index or index in seen:
            _bump(dropped, "invalid")
            continue

        basis = [
            entry
            for entry in _clean_basis(raw.get("basis"))
            if not entry.is_case and entry.why and entry.why.strip() and not judgment(entry.why)
        ]

        if not basis:
            _bump(dropped, "no_basis")
            continue

        seen.add(index)
        evidence.append(QuestionEvidence(draft_index=index, text=by_index[index]["text"], basis=basis))

    return evidence


def normalize_result(
    *,
    check_items: Any,
    question_evidence: Any,
    drafts: List[Dict[str, Any]],
    notices: List[str],
    dropped: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """정리한 결과(ChecklistResult 의 dict). check_items · question_evidence 가 목록이 아니면 AI_INVALID_OUTPUT."""

    if not isinstance(check_items, list) or not isinstance(question_evidence, list):
        raise FollowupChecklistError(ErrorCode.AI_INVALID_OUTPUT, "NotAList")

    judgment = _judgment_check()
    counts: Dict[str, int] = dict(dropped or {})

    result = ChecklistResult(
        check_items=_clean_check_items(check_items, judgment, counts),
        question_evidence=_clean_question_evidence(question_evidence, drafts, judgment, counts),
        notice=" ".join(dict.fromkeys(notice for notice in notices if notice)) or None,
        dropped=counts,
    ).model_dump(mode="json")

    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise FollowupChecklistError(ErrorCode.AI_INVALID_OUTPUT, type(error).__name__) from error

    return result


def empty_result(notice: Optional[str] = None) -> Dict[str, Any]:
    return ChecklistResult(notice=notice).model_dump(mode="json")


def normalize_rag_output(output: Any, payload: FollowupChecklistInput) -> Dict[str, Any]:
    """rag.session.analyze_reviewed_transcript 결과를 정리한다. 실패 · 차단은 FollowupChecklistError."""

    if not isinstance(output, dict):
        raise FollowupChecklistError(ErrorCode.AI_INVALID_OUTPUT, type(output).__name__)

    rag = output.get("rag_analysis")

    if rag is None:
        # 근거자료 분석이 돌지 않았다: 아동 발화가 없거나(rag 가 바로 돌려줌) 위쪽이 비식별에 막혔다.
        if output.get("privacy_blocked"):
            raise FollowupChecklistError(ErrorCode.AI_PRIVACY_BLOCKED, "RagPrivacyBlocked")
        return empty_result(NOTICE_NO_CHILD_SPEECH)

    if not isinstance(rag, dict):
        raise FollowupChecklistError(ErrorCode.AI_INVALID_OUTPUT, type(rag).__name__)

    if rag.get("error"):
        # rag/session._error_payload: 비식별 차단이면 privacy_blocked, 그 밖은 예외 종류만 든 고정 문구.
        if rag.get("privacy_blocked") or output.get("privacy_blocked"):
            raise FollowupChecklistError(ErrorCode.AI_PRIVACY_BLOCKED, "RagPrivacyBlocked")
        raise FollowupChecklistError(ErrorCode.AI_FAILED, "RagAnalysisError")

    checklist = rag.get("next_session_checklist")
    validation = checklist.get("validation", {}) if isinstance(checklist, dict) else None

    if not isinstance(checklist, dict) or not isinstance(validation, dict):
        raise FollowupChecklistError(ErrorCode.AI_INVALID_OUTPUT, "NoChecklist")

    if validation.get("check_error"):
        # 확인할 사항 추출이 실패했다. 빈 목록을 '확인할 사항 없음' 으로 보이지 않게 실패로 마감한다.
        raise FollowupChecklistError(ErrorCode.AI_FAILED, "CheckItemExtractionError")

    notices = [RAG_WARNING_NOTICES[key] for key in RAG_WARNING_NOTICES if rag.get(key)]
    notices += [notice for key, notice in VALIDATION_NOTICES if validation.get(key)]

    dropped: Dict[str, int] = {}
    for key in RAG_DROPPED_COUNTS:
        value = validation.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            dropped[key] = value

    return normalize_result(
        check_items=checklist.get("check_items"),
        question_evidence=checklist.get("question_evidence", []),
        drafts=payload.drafts,
        notices=notices,
        dropped=dropped,
    )


# =========================================================
# Mock
# =========================================================

def _first_child_segment(transcript: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    segments = [
        segment
        for segment in transcript.get("segments") or []
        if isinstance(segment, dict)
        and segment.get("speaker") == "CHILD"
        and isinstance(segment.get("text"), str)
        and segment["text"].strip()
    ]

    return min(segments, key=lambda segment: segment.get("start_ms") or 0) if segments else None


class MockFollowupChecklistAdapter:
    """OpenAI 없이 고정 문구로 만든다. 화면 개발 · CI 용(문구에 '(예시)' 를 단다). 학대 유형은 보지 않는다."""

    name = "mock"

    def build(self, payload: FollowupChecklistInput) -> Dict[str, Any]:
        segment = _first_child_segment(payload.transcript)

        if segment is None:
            return empty_result(NOTICE_NO_CHILD_SPEECH)

        check_item = {
            "id": "check:1",
            "text": "(예시) 이 발화 이후 상황이 어떻게 되었는지",
            "kind": "info_gap",
            "priority": "medium",
            "reason": "(예시) mock 결과입니다.",
            "basis": [
                {
                    "type": "case",
                    "label": f"{payload.session_no}회차",
                    "session_no": payload.session_no,
                    "session_id": payload.session_id,
                    "segment_id": str(segment.get("segment_id") or ""),
                    "start_ms": segment.get("start_ms"),
                    "excerpt": segment["text"].strip(),
                }
            ],
        }
        question_evidence = [
            {
                "draft_index": payload.drafts[0]["draft_index"],
                "basis": [
                    {
                        "type": "manual",
                        "ref": "manual:1",
                        "label": "(예시) 업무 매뉴얼",
                        "excerpt": "(예시) mock 결과라 실제 매뉴얼 발췌가 아닙니다.",
                        "why": "(예시) 화면 확인용",
                    }
                ],
            }
        ] if payload.drafts else []

        return normalize_result(
            check_items=[check_item],
            question_evidence=question_evidence,
            drafts=payload.drafts,
            notices=[NOTICE_MOCK],
        )


# =========================================================
# Module (rag/)
# =========================================================

def export_rag_env() -> None:
    """rag/config.py 는 import 할 때 os.getenv 로 읽는다. backend/.env 에만 적으면 못 보므로 process 환경으로 넘긴다.

    비어 있으면 넘기지 않는다(rag 기본값을 쓴다 — #117 교차검증 R6). 이미 환경에 있으면 그 값을 우선한다.
    """

    for name in ("RAG_VECTOR_DB_DIR", "RAG_ANALYZER_MODEL"):
        value = getattr(settings, name, "")

        if value and not os.getenv(name):
            os.environ[name] = value


class ModuleFollowupChecklistAdapter:
    """rag.session.analyze_reviewed_transcript 를 부르고 결과를 정리한다."""

    name = "module"

    def _load(self):
        ensure_repo_root_on_path()
        export_llm_env()
        export_law_env()
        export_rag_env()

        try:
            from rag.session import analyze_reviewed_transcript
        except ImportError as error:
            # 예외 문구에는 모듈 경로가 섞일 수 있어 종류 이름만 남긴다.
            raise FollowupChecklistError(ErrorCode.AI_FAILED, type(error).__name__) from error

        return analyze_reviewed_transcript

    def build(self, payload: FollowupChecklistInput) -> Dict[str, Any]:
        if payload.abuse_type is None:
            # 학대 유형이 없으면 rag 는 근거자료 분석을 하지 않는다 — 외부로 아무것도 보내지 않고 끝낸다.
            return empty_result(NOTICE_NO_ABUSE_TYPE)

        analyze = self._load()

        try:
            output = analyze(
                payload.transcript,
                payload.abuse_type,
                known_identifiers=[],
                session_no=payload.session_no,
                session_id=payload.session_id,
                previous_sessions=payload.previous_sessions,
                child_app_responses=[],
                with_questions=False,
                with_manual_references=False,
                link_questions=[
                    {"draft_index": draft["draft_index"], "text": draft["text"], "reason": draft.get("reason") or ""}
                    for draft in payload.drafts
                ],
            )
        except Exception as error:
            raise map_followup_error(error) from error

        return normalize_rag_output(output, payload)


# =========================================================
# Factory
# =========================================================

_override: Optional[FollowupChecklistAdapter] = None


def set_followup_checklist_adapter_override(adapter: Optional[FollowupChecklistAdapter]) -> None:
    """테스트에서 성공 · 실패 · 시간 초과를 주입하는 hook. 주입돼 있으면 FOLLOWUP_PROVIDER 가 off 여도 켜진 것으로 본다."""

    global _override
    _override = adapter


def is_enabled() -> bool:
    return _override is not None or settings.FOLLOWUP_PROVIDER != "off"


def get_followup_checklist_adapter() -> FollowupChecklistAdapter:
    if _override is not None:
        return _override

    if settings.FOLLOWUP_PROVIDER == "module":
        return ModuleFollowupChecklistAdapter()

    return MockFollowupChecklistAdapter()


__all__ = [
    "FOLLOWUP_MESSAGES",
    "FollowupChecklistAdapter",
    "FollowupChecklistError",
    "FollowupChecklistInput",
    "MockFollowupChecklistAdapter",
    "ModuleFollowupChecklistAdapter",
    "empty_result",
    "get_followup_checklist_adapter",
    "is_enabled",
    "map_followup_error",
    "normalize_rag_output",
    "normalize_result",
    "set_followup_checklist_adapter_override",
]
