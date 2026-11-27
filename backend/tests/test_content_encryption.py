# 상담 본문 앱 암호화 1 · 2단계(2026-11-16, 민규님과 합의).
#
# 1단계: documents.content · transcript_segments.text · consultation_summaries.overview · key_points · counselor_note ·
#        consultation_sessions.memo · ai_analyses.result
# 2단계: session_source_documents · cases(사례연계 경위 · 초기면접 글 · 메모) · 추가 질문 · 종결 검토 · 기관 서식 값 ·
#        아동 앱 답 · 긴급 알림 · AI 초안 · 문서함 preview_text
#
# 옛 평문 칸은 옮기기 뒤 migration b2c3d4e5f6a8 로 지웠다(2026-11-27) — 평문을 쓸 칸이 DB 에 없다.
#
# - DB 에는 *_enc 암호문만 있다. API 응답은 예전 모양 그대로다.
# - 묶음 값(AAD)이 표 · 칸 · 행 ID 라 다른 행으로 옮겨 붙이면 풀리지 않는다.
# - 키 바꾸기 script 가 본문 칸도 맨 앞 키로 다시 암호화한다.

import json
import uuid
from typing import Dict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.config import settings
from app.core.pii_crypto import PersonalInfoCryptoError
from app.models import (
    AIAnalysis,
    ConsultationSession,
    ConsultationSummary,
    Document,
    TranscriptSegment,
)
from app.models.encrypted_field import ENCRYPTED_COLUMNS
from scripts.reencrypt_personal_info import reencrypt_content
from tests.conftest import upload_audio
from tests.test_case_personal_info import NEW_KEY, OLD_KEYS

MEMO = "보호자 귀가 시간 확인 필요(가상 메모)"
NOTE = "상담사 추가 의견 — 가상 문장"
OVERVIEW = "가상 요약: 아동이 학교 생활을 이야기함"
KEY_POINTS = ["가상 핵심 1", "가상 핵심 2"]
EDITED_SEGMENT = "상담사가 고친 가상 발화입니다."
RECORD = "가상 상담일지 본문"

EXPECTED_COLUMNS = {
    "documents": {"content"},
    "transcript_segments": {"text"},
    "consultation_summaries": {"overview", "key_points", "counselor_note"},
    "consultation_sessions": {"memo"},
    "ai_analyses": {"result"},
}
STAGE_TWO_COLUMNS = {
    "session_source_documents": {"text", "note_draft", "followup_draft"},
    "cases": {
        "linked_background",
        "intake_guardian_relation",
        "intake_problem",
        "intake_attitude",
        "intake_environment",
        "intake_opinion",
        "notes",
    },
    "session_followup_questions": {"questions"},
    "case_closure_reviews": {"summary", "edits", "report"},
    "case_forms": {"values"},
    "child_app_events": {"payload"},
    "child_app_ai_drafts": {"items"},
    "child_session_question_drafts": {"items"},  # 2026-11-24 새 표 — 처음부터 암호문
    "docbox_files": {"preview_text"},
}
# 처음부터 암호문으로만 두는 칸(옮길 옛 평문이 없음): 원문 확정 전 AI 전체 분석(2026-11-24, pre_analysis_service).
NEW_ENCRYPTED_COLUMNS = {
    "transcripts": {"pre_analysis"},
}


def _run_flow(client: TestClient, headers: Dict[str, str], case_id: str) -> str:
    session = client.post(
        f"/api/v1/cases/{case_id}/sessions", json={"title": "1회기", "memo": MEMO}, headers=headers
    ).json()["data"]
    session_id = session["id"]

    assert session["memo"] == MEMO

    assert upload_audio(client, headers, session_id)[0] == 201
    assert client.post(f"/api/v1/sessions/{session_id}/transcript", headers=headers).status_code == 202

    segments = client.get(f"/api/v1/sessions/{session_id}/transcript", headers=headers).json()["data"]["transcript"][
        "segments"
    ]
    edited = client.patch(
        f"/api/v1/sessions/{session_id}/transcript",
        json={"segments": [{"segment_id": segments[0]["segment_id"], "text": EDITED_SEGMENT}]},
        headers=headers,
    )

    assert edited.status_code == 200, edited.text
    assert client.post(f"/api/v1/sessions/{session_id}/transcript/confirm", headers=headers).status_code == 200
    assert client.post(f"/api/v1/sessions/{session_id}/analysis", headers=headers).status_code == 202

    summary = client.patch(
        f"/api/v1/sessions/{session_id}/summary",
        json={"overview": OVERVIEW, "key_points": KEY_POINTS, "counselor_note": NOTE},
        headers=headers,
    )

    assert summary.status_code == 200, summary.text

    document = client.post(
        f"/api/v1/sessions/{session_id}/documents", json={"title": "상담 기록", "content": RECORD}, headers=headers
    )

    assert document.status_code == 201, document.text

    return session_id


def _raw_rows(db, model):
    """ORM 속성을 거치지 않은 DB 값(평문 칸 · 암호문 칸)."""

    return [row._mapping for row in db.execute(select(model.__table__)).all()]


def test_registered_columns_are_stage_one_and_two() -> None:
    found: Dict[str, set] = {}

    for model, columns in ENCRYPTED_COLUMNS.items():
        found.setdefault(model.__tablename__, set()).update(column.column for column in columns)

    assert found == {**EXPECTED_COLUMNS, **STAGE_TWO_COLUMNS, **NEW_ENCRYPTED_COLUMNS}


def test_encrypted_tables_have_no_plaintext_column() -> None:
    # 옛 평문 칸(DB 이름 = 속성 이름)은 지웠다. 남아 있으면 그 칸에 평문을 쓰는 길이 다시 생길 수 있다.
    for model, columns in ENCRYPTED_COLUMNS.items():
        for column in columns:
            assert column.column not in model.__table__.c, f"{column.table}.{column.column}"
            assert f"{column.column}_enc" in model.__table__.c


def test_db_holds_only_ciphertext_and_api_shape_is_unchanged(
    client: TestClient, counselor_headers, case: dict, db
) -> None:
    session_id = _run_flow(client, counselor_headers, case["id"])

    # API 는 예전처럼 평문을 준다.
    session = client.get(f"/api/v1/sessions/{session_id}", headers=counselor_headers).json()["data"]
    summary = client.get(f"/api/v1/sessions/{session_id}/summary", headers=counselor_headers).json()["data"]["summary"]
    transcript = client.get(f"/api/v1/sessions/{session_id}/transcript", headers=counselor_headers).json()["data"][
        "transcript"
    ]
    documents = client.get(f"/api/v1/sessions/{session_id}/documents", headers=counselor_headers).json()["data"]
    analysis = client.get(f"/api/v1/sessions/{session_id}/analysis", headers=counselor_headers).json()["data"][
        "analysis"
    ]

    assert session["memo"] == MEMO
    assert (summary["overview"], summary["key_points"], summary["counselor_note"]) == (OVERVIEW, KEY_POINTS, NOTE)
    assert transcript["segments"][0]["text"] == EDITED_SEGMENT
    assert RECORD in json.dumps(documents, ensure_ascii=False)
    assert analysis["result"]["summary"]["overview"]

    # DB 에는 평문이 없다.
    raw = {
        "documents": _raw_rows(db, Document),
        "transcript_segments": _raw_rows(db, TranscriptSegment),
        "consultation_summaries": _raw_rows(db, ConsultationSummary),
        "consultation_sessions": _raw_rows(db, ConsultationSession),
        "ai_analyses": _raw_rows(db, AIAnalysis),
    }
    for table, columns in EXPECTED_COLUMNS.items():
        assert raw[table], table

        for row in raw[table]:
            for column in columns:
                assert column not in row, f"{table}.{column}"
                assert row[f"{column}_enc"] is None or row[f"{column}_enc"].startswith("v1.test1."), f"{table}.{column}"

    dumped = json.dumps([[dict(row) for row in rows] for rows in raw.values()], ensure_ascii=False, default=str)
    analysis_overview = analysis["result"]["summary"]["overview"]

    for secret in (MEMO, NOTE, OVERVIEW, *KEY_POINTS, EDITED_SEGMENT, RECORD, analysis_overview):
        assert secret not in dumped

    # 모든 원문 조각이 암호문이다(원문 새 버전 포함).
    assert all(row["text_enc"] for row in raw["transcript_segments"])
    assert all(row["result_enc"] for row in raw["ai_analyses"] if row["status"] == "COMPLETED")


def test_new_transcript_version_reencrypts_copied_segments(
    client: TestClient, counselor_headers, case: dict, db
) -> None:
    _run_flow(client, counselor_headers, case["id"])

    segments = db.scalars(select(TranscriptSegment)).all()
    by_segment: Dict[str, list] = {}

    for segment in segments:
        by_segment.setdefault(segment.segment_id, []).append(segment)

    unchanged = [rows for rows in by_segment.values() if len(rows) == 2 and rows[0].text == rows[1].text]

    assert unchanged
    # 같은 글을 복사했어도 새 행 ID 로 다시 암호화해 암호문이 다르다.
    for first, second in unchanged:
        assert first.text_enc != second.text_enc


def test_ciphertext_moved_to_another_row_does_not_open(
    client: TestClient, counselor_headers, case: dict, db
) -> None:
    session_id = _run_flow(client, counselor_headers, case["id"])
    other = client.post(
        f"/api/v1/sessions/{session_id}/documents", json={"title": "둘째", "content": "다른 본문"}, headers=counselor_headers
    ).json()["data"]
    first = db.scalars(select(Document).where(Document.id != uuid.UUID(other["id"]))).one()

    db.execute(update(Document.__table__).where(Document.id == uuid.UUID(other["id"])).values(content_enc=first.content_enc))
    db.commit()
    db.expire_all()

    with pytest.raises(PersonalInfoCryptoError):
        _ = db.get(Document, uuid.UUID(other["id"])).content

    # 같은 행의 다른 칸(요약 overview → counselor_note)으로 옮겨도 풀리지 않는다.
    summary = db.scalars(select(ConsultationSummary)).one()
    db.execute(update(ConsultationSummary.__table__).values(counselor_note_enc=summary.overview_enc))
    db.commit()
    db.expire_all()

    with pytest.raises(PersonalInfoCryptoError):
        _ = db.scalars(select(ConsultationSummary)).one().counselor_note


def test_new_row_gets_id_before_encryption_whatever_the_argument_order(
    client: TestClient, counselor_headers, session: dict, db
) -> None:
    row_id = uuid.uuid4()
    # content 를 id 보다 먼저 넣어도 INSERT 직전에 정한 ID 로 암호화한다.
    document = Document(content=RECORD, session_id=uuid.UUID(session["id"]), title="t", id=row_id)
    no_id = Document(content="ID 없이 만든 행", session_id=uuid.UUID(session["id"]), title="t2")

    assert document.content == RECORD
    db.add_all([document, no_id])
    db.commit()
    db.expire_all()

    assert db.get(Document, row_id).content == RECORD
    assert db.get(Document, no_id.id).content == "ID 없이 만든 행"


def test_setting_none_clears_both_columns(client: TestClient, counselor_headers, session: dict, db) -> None:
    response = client.patch(f"/api/v1/sessions/{session['id']}", json={"memo": MEMO}, headers=counselor_headers)

    assert response.status_code == 200, response.text

    row = db.get(ConsultationSession, uuid.UUID(session["id"]))

    assert row.memo_enc and row.memo == MEMO

    row.memo = None
    db.commit()
    db.expire_all()
    row = db.get(ConsultationSession, uuid.UUID(session["id"]))

    assert (row.memo, row.memo_enc) == (None, None)


def test_same_value_does_not_rewrite_the_row(client: TestClient, counselor_headers, session: dict, db) -> None:
    assert client.patch(f"/api/v1/sessions/{session['id']}", json={"memo": MEMO}, headers=counselor_headers).status_code == 200

    row = db.get(ConsultationSession, uuid.UUID(session["id"]))
    token = row.memo_enc
    row.memo = MEMO

    assert row.memo_enc == token
    assert row not in db.dirty

    row.memo = MEMO + "!"

    assert row.memo_enc != token and row.memo == MEMO + "!"


# =========================================================
# 옮기기 script
# =========================================================


def _without_updated_at(value):
    # 다시 암호화는 행을 고치므로 updated_at 만 달라진다.
    if isinstance(value, dict):
        return {key: _without_updated_at(item) for key, item in value.items() if key != "updated_at"}

    if isinstance(value, list):
        return [_without_updated_at(item) for item in value]

    return value


def _api_snapshot(client: TestClient, headers, session_id: str) -> dict:
    paths = ("", "/summary", "/transcript", "/documents", "/analysis")

    return {
        path: _without_updated_at(client.get(f"/api/v1/sessions/{session_id}{path}", headers=headers).json()["data"])
        for path in paths
    }


# =========================================================
# 키 바꾸기 script
# =========================================================


def test_reencrypt_content_moves_to_new_key(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = _run_flow(client, counselor_headers, case["id"])
    before = _api_snapshot(client, counselor_headers, session_id)
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")

    dry = reencrypt_content(db, dry_run=True)

    assert dry.changed_rows == dry.rows > 0
    assert _raw_rows(db, ConsultationSession)[0]["memo_enc"].startswith("v1.test1.")

    result = reencrypt_content(db)

    assert (result.changed_rows, result.failed) == (dry.rows, [])
    assert _raw_rows(db, ConsultationSession)[0]["memo_enc"].startswith("v1.new2.")

    # 옛 키를 빼도 풀린다.
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)
    db.expire_all()
    assert _api_snapshot(client, counselor_headers, session_id) == before
    assert reencrypt_content(db).changed_rows == 0


def test_reencrypt_content_reports_rows_it_cannot_read(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_flow(client, counselor_headers, case["id"])
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)

    result = reencrypt_content(db)

    assert result.changed_rows == 0
    assert {name for name, _ in result.failed} >= {
        f"{table}.{column}" for table, columns in EXPECTED_COLUMNS.items() for column in columns
    }


# =========================================================
# 2단계
# =========================================================

INTAKE = {
    "linked_background": "가상 사례연계 경위",
    "intake_guardian_relation": "가상 보호자 관계",
    "intake_problem": "가상 문제력",
    "intake_attitude": "가상 태도",
    "intake_environment": "가상 환경",
    "intake_opinion": "가상 소견",
    "notes": "가상 사례 메모",
}
FORM_VALUES = {"place": "가상 면담실", "checks": ["NO", "YES"] + [None] * 7, "opinion": "가상 서식 소견", "plan": "가상 계획"}


def test_case_text_and_form_values_are_ciphertext_and_round_trip(
    client: TestClient, counselor_headers, case: dict, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models import Case, CaseForm

    patched = client.patch(f"/api/v1/cases/{case['id']}", json=INTAKE, headers=counselor_headers)

    assert patched.status_code == 200, patched.text
    assert {key: patched.json()["data"][key] for key in INTAKE} == INTAKE

    form_url = f"/api/v1/cases/{case['id']}/forms"
    created = client.post(form_url, json={"form_type": "MANAGEMENT_CHECKLIST", "values": {}}, headers=counselor_headers)
    form_id = created.json()["data"]["id"]
    # 기관 서식은 판 번호 대조 조건부 UPDATE 로 저장한다(ORM 속성을 거치지 않는 길).
    saved = client.patch(f"{form_url}/{form_id}", json={"values": FORM_VALUES, "version": 1}, headers=counselor_headers)

    assert saved.status_code == 200, saved.text

    reopened = client.get(f"/api/v1/cases/{case['id']}", headers=counselor_headers).json()["data"]
    forms = client.get(form_url, headers=counselor_headers).json()["data"]["items"]

    assert {key: reopened[key] for key in INTAKE} == INTAKE
    assert forms[0]["values"] == FORM_VALUES

    case_row = _raw_rows(db, Case)[0]
    (form_row,) = _raw_rows(db, CaseForm)
    dumped = json.dumps([dict(case_row), dict(form_row)], ensure_ascii=False, default=str)

    for key in INTAKE:
        assert key not in case_row and case_row[f"{key}_enc"].startswith("v1.test1.")

    assert "values" not in form_row and form_row["values_enc"].startswith("v1.test1.")

    for secret in (*INTAKE.values(), "가상 서식 소견", "가상 계획", "가상 면담실"):
        assert secret not in dumped

    # 기관 서식 암호문도 행 ID 에 묶여 있다 — 다른 행으로 옮기면 풀리지 않는다.
    second = client.post(form_url, json={"form_type": "RISK_SCALE", "values": {}}, headers=counselor_headers).json()["data"]
    db.execute(update(CaseForm.__table__).where(CaseForm.id == uuid.UUID(second["id"])).values(values_enc=form_row["values_enc"]))
    db.commit()

    with pytest.raises(PersonalInfoCryptoError):
        _ = db.get(CaseForm, uuid.UUID(second["id"])).values

    # 키 바꾸기 script 가 2단계 칸도 맨 앞 키로 옮긴다(옮겨 붙인 행은 못 푼 행으로 보고).
    db.execute(update(CaseForm.__table__).where(CaseForm.id == uuid.UUID(second["id"])).values(values_enc=None))
    db.commit()
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", f"{NEW_KEY},{OLD_KEYS}")
    result = reencrypt_content(db)

    assert result.failed == []
    assert _raw_rows(db, Case)[0]["notes_enc"].startswith("v1.new2.")
    first_form = next(row for row in _raw_rows(db, CaseForm) if str(row["id"]) == form_id)

    assert first_form["values_enc"].startswith("v1.new2.")
    monkeypatch.setattr(settings, "PII_ENCRYPTION_KEYS", NEW_KEY)
    db.expire_all()
    assert client.get(form_url, headers=counselor_headers).json()["data"]["items"][0]["values"] == FORM_VALUES


