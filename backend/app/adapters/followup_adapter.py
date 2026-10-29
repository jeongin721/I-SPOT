# 다음 상담 체크리스트 Adapter — 추가 확인 · 질문 화면 (API_CONTRACT 18절, 2026-10-29).
#
# rag/session.analyze_reviewed_transcript(공식 근거 RAG)를 부른다. 분석 어댑터(ai_adapter)와 같은 모양
# (Protocol + mock + module + provider 스위치)이다.
#  - mock  : OpenAI 없이 이번 회차 아동 발화로 고정 문구 결과를 만든다. 화면 개발 · CI 용. 학대 유형은 보지 않는다.
#  - module: rag 패키지를 import 해 부른다. 아동 발화 · 이전 회차 기록은 rag 가 privacy_gateway 로 가린 뒤 OpenAI 로
#            보낸다. 가린 뒤 재검사를 통과하지 못하면 보내지 않고 AI_PRIVACY_BLOCKED 로 끝난다.
# 실패는 예외 **종류**로 코드를 정하고 문구는 버린다 — 예외 문구에 상담 발화 · 인증값이 섞일 수 있다(map_ai_error 와 같은 원칙).

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from app.adapters.ai_adapter import export_llm_env
from app.adapters.law_qa_adapter import export_law_env
from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.errors import ErrorCode

SCHEMA_VERSION = "1.0"

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


class FollowupError(Exception):
    """다음 상담 체크리스트 만들기 실패. 문구는 코드별 고정 문구이고 원인은 예외 종류 이름(cause_name)만 남긴다."""

    def __init__(self, code: ErrorCode, cause_name: str = "") -> None:
        super().__init__(FOLLOWUP_MESSAGES[code])
        self.code = code
        self.cause_name = cause_name

    @property
    def message(self) -> str:
        return FOLLOWUP_MESSAGES[self.code]


def map_followup_error(error: Exception) -> FollowupError:
    if isinstance(error, FollowupError):
        return error

    name = type(error).__name__

    if isinstance(error, TimeoutError):
        return FollowupError(ErrorCode.AI_TIMEOUT, name)

    if name == "RagPrivacyBlocked":
        return FollowupError(ErrorCode.AI_PRIVACY_BLOCKED, name)

    return FollowupError(ErrorCode.AI_FAILED, name)


@dataclass
class FollowupInput:
    """rag.session.analyze_reviewed_transcript 에 넘기는 값(rag/README.md 8-3)."""

    # 이번 회차 확정 전사본(STT Contract). rag 는 CHILD 발화만 쓴다.
    transcript: Dict[str, Any]
    # physical · emotional · sexual · neglect · multiple. None 이면 rag 가 질문을 만들지 않는다.
    abuse_type: Optional[str]
    session_no: Optional[int]
    # 근거 링크용 회차 ID. 외부로 보내지 않는다.
    session_id: str
    previous_sessions: List[Dict[str, Any]] = field(default_factory=list)
    child_app_responses: List[Dict[str, Any]] = field(default_factory=list)


class FollowupAdapter(Protocol):
    name: str

    def build(self, payload: FollowupInput) -> Dict[str, Any]: ...


def empty_result(notice: Optional[str] = None) -> Dict[str, Any]:
    return {
        "check_items": [],
        "items": [],
        "validation": {},
        "speaker_check_items": [],
        "manual_screen_references": None,
        "notice": notice,
    }


# =========================================================
# Mock
# =========================================================

MOCK_NOTICE = "예시(mock) 결과입니다. 실제 질문은 FOLLOWUP_PROVIDER=module 에서 공식 근거를 찾아 만듭니다."

MOCK_MANUAL_BASIS: Dict[str, Any] = {
    "ref": "manual:1",
    "type": "manual",
    "label": "(예시) 아동보호서비스 업무 매뉴얼 · 상담·조사·사정",
    "excerpt": "아동 면담 시에는 개방형 질문을 먼저 사용하고, 특정 답을 암시하는 질문은 피한다. (mock 고정 문구)",
}


def _format_time(start_ms: Any) -> str:
    total = max(int(start_ms or 0), 0) // 1000
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def _session_label(session_no: Optional[int]) -> str:
    return f"{session_no}회차" if session_no else "이번 회차"


def _segment_basis(segment: Dict[str, Any], payload: FollowupInput, ref: str) -> Dict[str, Any]:
    return {
        "ref": ref,
        "type": "case",
        "source": "transcript",
        "label": f"{_session_label(payload.session_no)} {_format_time(segment.get('start_ms'))}",
        "session_no": payload.session_no,
        "session_id": payload.session_id,
        "segment_id": segment.get("segment_id"),
        "start_ms": segment.get("start_ms"),
        "response_id": None,
        "excerpt": segment.get("text", ""),
    }


class MockFollowupAdapter:
    """이번 회차 첫 아동 발화를 근거로 고정 문구 확인 사항 · 질문을 만든다. 발화 내용은 근거 발췌에만 그대로 싣는다."""

    name = "mock"

    def build(self, payload: FollowupInput) -> Dict[str, Any]:
        segments = sorted(
            (s for s in payload.transcript.get("segments") or [] if isinstance(s, dict)),
            key=lambda s: int(s.get("start_ms") or 0),
        )
        child = [s for s in segments if s.get("speaker") == "CHILD" and str(s.get("text") or "").strip()]
        unknown = [s for s in segments if s.get("speaker") == "UNKNOWN" and str(s.get("text") or "").strip()]

        speaker_items = [
            {
                "id": "speaker:1",
                "item": f"{_format_time(unknown[0].get('start_ms'))} 발화의 화자",
                "kind": "uncertain_speaker",
                "priority": "medium",
                "reason": "STT 검수 후에도 화자가 확정되지 않아 질문 생성 근거에서 뺀 발화입니다.",
                "basis": [
                    {
                        **_segment_basis(unknown[0], payload, "speaker:1"),
                        "label": f"{_session_label(payload.session_no)} {_format_time(unknown[0].get('start_ms'))} · 화자 불확실",
                        "excerpt": None,
                    }
                ],
            }
        ] if unknown else []

        if not child:
            result = empty_result("검수된 아동 발화가 없어 다음 상담 질문을 만들지 않았습니다.")
            result["speaker_check_items"] = speaker_items
            return result

        first = _segment_basis(child[0], payload, "case:1")
        check_items: List[Dict[str, Any]] = [
            {
                "id": "check:1",
                "item": "(예시) 아동이 말한 일의 시기 · 빈도를 확인했는지",
                "kind": "info_gap",
                "priority": "high",
                "reason": "mock 고정 문구입니다.",
                "case_refs": ["case:1"],
                "knowledge_refs": [],
                "basis": [first],
            }
        ]

        previous = sorted(
            (p for p in payload.previous_sessions if isinstance(p, dict)),
            key=lambda p: int(p.get("session_no") or 0),
            reverse=True,
        )
        if previous:
            latest = previous[0]
            check_items.append(
                {
                    "id": "check:2",
                    "item": f"(예시) {latest.get('session_no')}회차에 정한 내용이 지켜졌는지",
                    "kind": "plan_followup",
                    "priority": "medium",
                    "reason": "mock 고정 문구입니다.",
                    "case_refs": ["case:2"],
                    "knowledge_refs": [],
                    "basis": [
                        {
                            "ref": "case:2",
                            "type": "case",
                            "source": "summary",
                            "label": f"{latest.get('session_no')}회차 상담 요약",
                            "session_no": latest.get("session_no"),
                            "session_id": latest.get("session_id"),
                            "segment_id": None,
                            "start_ms": None,
                            "response_id": None,
                            "excerpt": latest.get("summary") or "",
                        }
                    ],
                }
            )

        def question(text: str, audience: str, priority: str) -> Dict[str, Any]:
            refs = ["case:1", "manual:1"]
            return {
                "question": text,
                "audience": audience,
                "question_type": "open",
                "priority": priority,
                "rationale": "mock 고정 문구입니다.",
                "check_item_id": "check:1",
                "case_refs": ["case:1"],
                "knowledge_refs": ["manual:1"],
                "basis_refs": refs,
                "basis": [first, dict(MOCK_MANUAL_BASIS)],
                "review_status": "passed",
            }

        items = [
            question("그때 있었던 일을 조금 더 이야기해 줄래?", "counselor", "high"),
            question("그 이야기를 하고 나서 마음이 어땠어?", "counselor", "medium"),
            question("요즘 기분은 어때?", "child_app", "medium"),
        ]

        return {
            "check_items": check_items,
            "items": items,
            "validation": {"generated": 3, "rule_rejected": 0, "review_rejected": 0, "rounds": 1, "reviewed": True},
            "speaker_check_items": speaker_items,
            "manual_screen_references": None,
            "notice": MOCK_NOTICE,
        }


# =========================================================
# Module (rag/)
# =========================================================


def export_rag_env() -> None:
    """rag/config.py 는 import 할 때 os.getenv 로 읽는다. backend/.env 에만 적으면 못 보므로 process 환경으로 넘긴다.
    이미 환경에 있으면 그 값을 우선한다(ai_adapter.export_llm_env 와 같음)."""

    for name in ("RAG_VECTOR_DB_DIR", "RAG_ANALYZER_MODEL"):
        value = getattr(settings, name, "")

        if value and not os.getenv(name):
            os.environ[name] = value


class ModuleFollowupAdapter:
    """rag.session.analyze_reviewed_transcript 를 부르고, 화면이 읽을 칸만 골라 돌려준다."""

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
            raise FollowupError(ErrorCode.AI_FAILED, type(error).__name__) from error

        return analyze_reviewed_transcript

    def build(self, payload: FollowupInput) -> Dict[str, Any]:
        analyze = self._load()

        try:
            output = analyze(
                payload.transcript,
                payload.abuse_type,
                known_identifiers=[],
                session_no=payload.session_no,
                session_id=payload.session_id,
                previous_sessions=payload.previous_sessions,
                child_app_responses=payload.child_app_responses,
            )
        except Exception as error:
            raise map_followup_error(error) from error

        rag = output.get("rag_analysis") if isinstance(output, dict) else None

        if isinstance(rag, dict) and rag.get("error"):
            # rag/session._error_payload: 비식별 차단이면 privacy_blocked, 그 밖은 예외 종류만 든 고정 문구.
            if rag.get("privacy_blocked"):
                raise FollowupError(ErrorCode.AI_PRIVACY_BLOCKED, "RagPrivacyBlocked")
            raise FollowupError(ErrorCode.AI_FAILED, "RagAnalysisError")

        if not isinstance(output, dict):
            raise FollowupError(ErrorCode.AI_INVALID_OUTPUT, type(output).__name__)

        checklist = (rag or {}).get("next_session_checklist") or {}
        notices = []
        if rag is None:
            notices.append("감지된 학대 유형이 없어 다음 상담 질문을 만들지 않았습니다.")
        for key in ("case_context_warning",):
            if isinstance(rag, dict) and rag.get(key):
                notices.append(str(rag[key]))

        manual = output.get("manual_screen_references")
        result = {
            "check_items": list(checklist.get("check_items") or []),
            "items": list(checklist.get("items") or []),
            "validation": dict(checklist.get("validation") or {}),
            "speaker_check_items": list(output.get("speaker_check_items") or []),
            # 화면별 매뉴얼 근거(추가 확인 · 질문 / 상담 전 브리핑 / 종결 검토). 오류 칸(errors)은 예외 문구가 섞일 수 있어 뺀다.
            "manual_screen_references": manual.get("references") if isinstance(manual, dict) else None,
            "notice": " ".join(notices) or None,
        }

        try:
            json.dumps(result, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise FollowupError(ErrorCode.AI_INVALID_OUTPUT, type(error).__name__) from error

        return result


# =========================================================
# Factory
# =========================================================

_override: Optional[FollowupAdapter] = None


def set_followup_adapter_override(adapter: Optional[FollowupAdapter]) -> None:
    """테스트에서 성공 · 실패 · 시간 초과를 주입하는 hook. 주입돼 있으면 FOLLOWUP_PROVIDER 가 off 여도 켜진 것으로 본다."""

    global _override
    _override = adapter


def is_enabled() -> bool:
    return _override is not None or settings.FOLLOWUP_PROVIDER != "off"


def get_followup_adapter() -> FollowupAdapter:
    if _override is not None:
        return _override

    if settings.FOLLOWUP_PROVIDER == "module":
        return ModuleFollowupAdapter()

    return MockFollowupAdapter()


__all__ = [
    "FOLLOWUP_MESSAGES",
    "SCHEMA_VERSION",
    "FollowupAdapter",
    "FollowupError",
    "FollowupInput",
    "MockFollowupAdapter",
    "ModuleFollowupAdapter",
    "empty_result",
    "get_followup_adapter",
    "is_enabled",
    "map_followup_error",
    "set_followup_adapter_override",
]
