"""
사례(case) 단위로 회기별 분석 결과를 저장하는 간단한 SQLite 저장소.

핵심 원칙:
1. AI가 만든 초안(ai_*)과 상담사가 확정한 최종본(final_*)을 분리 저장한다.
2. 승인 시점에 AI 초안 대비 무엇이 바뀌었는지 edit_log로 남긴다
   (상담사 메모의 "AI 초안과 최종본을 분리 저장, 수정·승인 감사 로그" 원칙).
3. 승인 전(draft)에는 사례관리/문서 출력에 노출하지 않는다.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DB_PATH = (
    Path(__file__).resolve().parent
    / "case_store.db"
)


# ============================================================
# 1. 연결 / 스키마
# ============================================================

def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "PRAGMA foreign_keys = ON"
    )
    return conn


def init_db() -> None:
    conn = _get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES cases(case_id),
            input_mode TEXT NOT NULL,
            source_type TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            major_types TEXT NOT NULL,
            subtype_analysis TEXT NOT NULL,
            ai_counseling_summary TEXT,
            ai_counseling_note TEXT,
            ai_checklist TEXT,
            final_counseling_summary TEXT,
            final_counseling_note TEXT,
            final_checklist TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            approved_at TEXT,
            edit_log TEXT
        );
        """
    )

    # Privacy Gateway의 Tier 2(등록된 실명 정확매칭) 단계에서 쓸 필드.
    # 기존 DB에는 없는 컬럼이라 ALTER TABLE로 추가한다 — CREATE TABLE
    # IF NOT EXISTS는 이미 있는 테이블의 컬럼을 늘려주지 않는다. 이미
    # 컬럼이 있으면(재실행) OperationalError가 나므로 무시한다.
    try:
        conn.execute(
            "ALTER TABLE cases ADD COLUMN known_identifiers TEXT"
        )
    except sqlite3.OperationalError:
        pass

    # "상담 전 브리핑"(PreBriefing)의 "확인할 사항"이 쓸 필드. 분석
    # 시점에 만든 followup_check_llm.py 결과를 세션에 같이 저장해 둬야
    # 나중에(다음 상담 전) 다시 분석을 돌리지 않고도 그대로 보여줄 수
    # 있다(2026-10-14 추가).
    try:
        conn.execute(
            "ALTER TABLE sessions ADD COLUMN followup_check_points TEXT"
        )
    except sqlite3.OperationalError:
        pass

    # "유형별 위험도" 화면에서 상담원이 직접 고르는 상/중/하 판단.
    # AI가 매기지 않는다 — 상담원 판단을 그대로 저장만 한다(2026-10-15
    # 추가, 이전엔 화면 state에만 있다가 새로고침하면 사라졌다).
    try:
        conn.execute(
            "ALTER TABLE sessions ADD COLUMN counselor_risk_level TEXT"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


init_db()


# ============================================================
# 2. 사례 생성
# ============================================================

def create_case_if_missing(
    case_id: str,
    known_identifiers: Optional[List[str]] = None,
) -> None:
    conn = _get_connection()

    conn.execute(
        "INSERT OR IGNORE INTO cases (case_id, created_at) VALUES (?, ?)",
        (
            case_id,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    # known_identifiers는 사례가 이미 있던 경우(재상담 회기)에도 새로
    # 등록/추가될 수 있으므로, INSERT OR IGNORE와 별개로 항상 반영한다.
    if known_identifiers is not None:
        set_known_identifiers(case_id, known_identifiers)


def set_known_identifiers(
    case_id: str,
    known_identifiers: List[str],
) -> None:
    """
    Privacy Gateway Tier 2(정확 매칭)에 쓸 아동/보호자 실명 등을 저장한다.
    NER은 재현율이 100%가 아니므로(KLUE-NER 5,000문장 기준 사람이름
    미탐률 36.8%, 2026-09-30 측정), 이미 알고 있는 실명은 NER 탐지에
    기대지 않고 정확 문자열 대조로 항상 걸러낸다.
    """

    cleaned = sorted(
        {
            name.strip()
            for name in known_identifiers
            if name and name.strip()
        }
    )

    conn = _get_connection()

    # 이 함수가 create_case_if_missing보다 먼저 불릴 수도 있다(예: 텍스트
    # 탭에서 실명을 분석 직전에 먼저 등록하는 흐름). 사례 행이 아직 없으면
    # UPDATE는 조용히 0행에 적용돼 값이 사라지므로, 먼저 있는지 보장한다.
    conn.execute(
        "INSERT OR IGNORE INTO cases (case_id, created_at) VALUES (?, ?)",
        (
            case_id,
            datetime.now().isoformat(),
        ),
    )

    conn.execute(
        "UPDATE cases SET known_identifiers = ? WHERE case_id = ?",
        (
            json.dumps(cleaned, ensure_ascii=False),
            case_id,
        ),
    )

    conn.commit()
    conn.close()


def get_known_identifiers(case_id: str) -> List[str]:
    conn = _get_connection()

    row = conn.execute(
        "SELECT known_identifiers FROM cases WHERE case_id = ?",
        (case_id,),
    ).fetchone()

    conn.close()

    if row is None or not row["known_identifiers"]:
        return []

    return json.loads(row["known_identifiers"])


# ============================================================
# 3. 회기(session) 초안 저장 — analyze_session 직후 호출
# ============================================================

def save_draft_session(
    case_id: str,
    input_mode: str,
    source_type: str,
    raw_text: str,
    analysis: Dict[str, Any],
) -> int:
    create_case_if_missing(
        case_id
    )

    checklist_draft = (
        analysis.get(
            "checklist_draft"
        )
        or {}
    )

    conn = _get_connection()

    cursor = conn.execute(
        """
        INSERT INTO sessions (
            case_id, input_mode, source_type, raw_text,
            major_types, subtype_analysis,
            ai_counseling_summary, ai_counseling_note, ai_checklist,
            followup_check_points,
            status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
        """,
        (
            case_id,
            input_mode,
            source_type,
            raw_text,
            json.dumps(
                analysis.get(
                    "major_types",
                    {},
                ),
                ensure_ascii=False,
            ),
            json.dumps(
                analysis.get(
                    "subtype_analysis",
                    {},
                ),
                ensure_ascii=False,
            ),
            analysis.get(
                "counseling_summary",
                "",
            ),
            analysis.get(
                "counseling_note",
                "",
            ),
            json.dumps(
                checklist_draft,
                ensure_ascii=False,
            ),
            json.dumps(
                analysis.get(
                    "followup_check_points",
                    [],
                ),
                ensure_ascii=False,
            ),
            datetime.now().isoformat(),
        ),
    )

    session_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return session_id


# ============================================================
# 4. 승인 — 상담사가 확정한 최종본 저장 + 감사 로그
# ============================================================

def approve_session(
    session_id: int,
    final_counseling_summary: str,
    final_counseling_note: str,
    final_checklist: Dict[str, Any],
) -> List[Dict[str, Any]]:
    conn = _get_connection()

    row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    if row is None:
        conn.close()

        raise ValueError(
            f"세션을 찾을 수 없습니다: {session_id}"
        )

    edit_log: List[Dict[str, Any]] = []

    if (
        (row["ai_counseling_summary"] or "")
        != final_counseling_summary
    ):
        edit_log.append(
            {
                "field": "counseling_summary",
                "before": row["ai_counseling_summary"],
                "after": final_counseling_summary,
            }
        )

    if (
        (row["ai_counseling_note"] or "")
        != final_counseling_note
    ):
        edit_log.append(
            {
                "field": "counseling_note",
                "before": row["ai_counseling_note"],
                "after": final_counseling_note,
            }
        )

    ai_checklist = json.loads(
        row["ai_checklist"] or "{}"
    )

    if ai_checklist != final_checklist:
        edit_log.append(
            {
                "field": "checklist",
                "before": ai_checklist,
                "after": final_checklist,
            }
        )

    conn.execute(
        """
        UPDATE sessions
        SET final_counseling_summary = ?,
            final_counseling_note = ?,
            final_checklist = ?,
            status = 'approved',
            approved_at = ?,
            edit_log = ?
        WHERE session_id = ?
        """,
        (
            final_counseling_summary,
            final_counseling_note,
            json.dumps(
                final_checklist,
                ensure_ascii=False,
            ),
            datetime.now().isoformat(),
            json.dumps(
                edit_log,
                ensure_ascii=False,
            ),
            session_id,
        ),
    )

    conn.commit()
    conn.close()

    return edit_log


_VALID_RISK_LEVELS = {"상", "중", "하", ""}


def set_counselor_risk_level(
    session_id: int,
    level: str,
) -> None:
    """
    "유형별 위험도" 화면에서 상담원이 고른 상/중/하를 그대로 저장한다.
    AI가 만드는 값이 아니다 — 상담원이 버튼을 누른 결과만 받아서
    저장하는 함수라, 여기서 level을 판단하거나 바꾸지 않는다.
    level=""는 "선택 취소"를 뜻한다.
    """

    if level not in _VALID_RISK_LEVELS:
        raise ValueError(
            f"알 수 없는 위험도 값입니다: {level!r}"
        )

    conn = _get_connection()

    cursor = conn.execute(
        "UPDATE sessions SET counselor_risk_level = ? WHERE session_id = ?",
        (level, session_id),
    )

    if cursor.rowcount == 0:
        conn.close()

        raise ValueError(
            f"세션을 찾을 수 없습니다: {session_id}"
        )

    conn.commit()
    conn.close()


# ============================================================
# 5. 조회
# ============================================================

def get_session(
    session_id: int,
) -> Optional[Dict[str, Any]]:
    conn = _get_connection()

    row = conn.execute(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,),
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def list_cases() -> List[Dict[str, Any]]:
    conn = _get_connection()

    rows = conn.execute(
        """
        SELECT
            c.case_id,
            c.created_at,
            COUNT(s.session_id) AS session_count,
            MAX(s.created_at) AS last_session_at
        FROM cases c
        LEFT JOIN sessions s ON s.case_id = c.case_id
        GROUP BY c.case_id
        ORDER BY last_session_at DESC
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def list_sessions_for_case(
    case_id: str,
) -> List[Dict[str, Any]]:
    conn = _get_connection()

    rows = conn.execute(
        "SELECT * FROM sessions WHERE case_id = ? ORDER BY created_at ASC",
        (case_id,),
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 6. 회차별 추이 — 사례관리 "추이 보기" 화면용
# ============================================================
# 2026-10-08: 아직 실사용 다회차 데이터가 없어서(배포 전) 알고리즘만
# 먼저 만들어 둔다 — 상담사들이 실제로 쓰기 시작해서 같은 case_id로
# 세션이 여러 개 쌓이면, 이 함수는 코드 수정 없이 그대로 작동한다.
# 더미 데이터로 "미리 학습"시킬 ML 모델이 아니다 — 이미 있는 1차/2차
# 분석 결과를 세션 축으로 모아서 보여주는 순수 집계 로직이라, 데이터가
# 쌓인다고 이 함수 자체가 똑똑해지지는 않는다. 쌓인 데이터는 상담사가
# 직접 회차별 변화를 해석하는 데 쓰인다 — 이 함수가 "개선/악화"를
# 판단하지는 않는다(그 판단을 AI가 내리면 안 된다는 설계 원칙 때문).

_TREND_LABELS = ["신체학대", "정서학대", "성학대", "방임"]
_TREND_STRENGTH_RANK = {"높음": 3, "중간": 2, "낮음": 1}


def get_case_trend(
    case_id: str,
) -> List[Dict[str, Any]]:
    """
    사례의 "승인된"(approved) 회기만 시간순으로 모아, 회차별 탐지
    신호(탐지 유형, 세부유형 개수, 최고 근거강도)를 그대로 나열한다.

    draft(상담사가 아직 확인 안 한 AI 초안) 세션은 제외한다 — 검증
    안 된 걸 사례관리 추이에 섞으면 안 된다(이 파일 머리말의 원칙 3과
    동일).

    반환값은 raw 시계열이다. "1회차보다 나아짐/나빠짐" 같은 해석
    문구는 여기서 만들지 않는다 — 회차마다 상담 주제가 다를 수 있고
    분석에 쓰인 모델 버전도 다를 수 있어서, 탐지 빈도 변화만으로
    상태 변화를 단정하면 안 된다. 해석은 상담사가 한다.
    """

    sessions = [
        session
        for session in list_sessions_for_case(case_id)
        if session.get("status") == "approved"
    ]

    trend = []

    for session in sessions:
        try:
            major_types = json.loads(
                session.get("major_types") or "{}"
            )
        except (TypeError, ValueError):
            major_types = {}

        try:
            subtype_analysis = json.loads(
                session.get("subtype_analysis") or "{}"
            )
        except (TypeError, ValueError):
            subtype_analysis = {}

        detected_labels = [
            label
            for label in _TREND_LABELS
            if major_types.get(label, {}).get("detected", False)
        ]

        subtypes_by_major = {
            result.get("major_type"): result.get("subtypes", [])
            for result in subtype_analysis.get("results", [])
        }

        type_signals = []

        for label in detected_labels:
            subtypes = subtypes_by_major.get(label, [])

            strengths = [
                evidence.get("evidence_strength")
                for subtype in subtypes
                for evidence in subtype.get("evidences", [])
                if evidence.get("evidence_strength")
                in _TREND_STRENGTH_RANK
            ]

            top_strength = (
                max(
                    strengths,
                    key=lambda s: _TREND_STRENGTH_RANK[s],
                )
                if strengths
                else None
            )

            type_signals.append(
                {
                    "label": label,
                    "subtype_count": len(subtypes),
                    "top_strength": top_strength,
                }
            )

        trend.append(
            {
                "session_id": session.get("session_id"),
                "approved_at": session.get("approved_at"),
                "detected_count": len(detected_labels),
                "types": type_signals,
            }
        )

    return trend


# ============================================================
# 7. 회차별 세부 신호 — "사례 상세 · 상담 이력" 화면용
# ============================================================
# get_case_trend()와 같은 원칙(승인된 세션만, "좋아짐/나빠짐" 같은
# 해석은 안 만든다)인데 대분류가 아니라 세부유형(14종) 단위까지
# 내려간다(2026-10-14 추가). "상담 회차" 목록과 "회차별 세부 신호"
# 표 둘 다 이 함수 하나로 채운다.

def get_case_sessions_detail(
    case_id: str,
) -> List[Dict[str, Any]]:
    sessions = [
        session
        for session in list_sessions_for_case(case_id)
        if session.get("status") == "approved"
    ]

    result = []

    for index, session in enumerate(sessions, start=1):
        try:
            subtype_analysis = json.loads(
                session.get("subtype_analysis") or "{}"
            )
        except (TypeError, ValueError):
            subtype_analysis = {}

        try:
            followup_check_points = json.loads(
                session.get("followup_check_points") or "[]"
            )
        except (TypeError, ValueError):
            followup_check_points = []

        subtype_counts = []

        for major_result in subtype_analysis.get("results", []):
            major_type = major_result.get("major_type")

            for subtype_entry in major_result.get(
                "subtypes", []
            ):
                evidences = subtype_entry.get(
                    "evidences", []
                )

                # evidence_strength가 전부 "낮음"이면 "보류"(화자 확인
                # 중) 표시로 쓴다 — SignalReview/NoteWrite가 이미 쓰는
                # 같은 기준(evidence_strength!='낮음'=채택)을 그대로
                # 재사용한다.
                low_only = bool(evidences) and all(
                    e.get("evidence_strength") == "낮음"
                    for e in evidences
                )

                subtype_counts.append(
                    {
                        "major_type": major_type,
                        "subtype": subtype_entry.get(
                            "type"
                        ),
                        "count": len(evidences),
                        "low_confidence_only": low_only,
                    }
                )

        result.append(
            {
                "session_id": session.get("session_id"),
                "round_label": f"{index}회차",
                "created_at": session.get("created_at"),
                "status": session.get("status"),
                "followup_check_points": followup_check_points,
                "subtype_counts": subtype_counts,
                "counseling_summary": session.get(
                    "final_counseling_summary"
                )
                or session.get("ai_counseling_summary")
                or "",
                "counselor_risk_level": session.get(
                    "counselor_risk_level"
                )
                or "",
            }
        )

    return result
