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

    conn.commit()
    conn.close()


init_db()


# ============================================================
# 2. 사례 생성
# ============================================================

def create_case_if_missing(
    case_id: str,
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
            status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?)
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
