# 상담 기록 문서 회차(POST/GET /sessions/{id}/source-document, …/followups, API_CONTRACT 21절, 2026-11-02). 데이터는 모두 가상이다.
# CI 의 AI_PROVIDER 는 mock 이라 머리줄 나누기(HEADINGS) 경로를 본다. modeling 경로는 가짜 모듈로.

import io
import sys
import types
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.module_loader import ensure_repo_root_on_path
from app.core.config import settings
from app.core.enums import AuditAction
from app.core.errors import APIError
from app.models.audit_log import AuditLog
from app.services import source_document_service
from tests.conftest import create_session, make_wav_bytes, upload_audio

ensure_repo_root_on_path()

from ai.modeling.abuse import document_note_llm as dn  # noqa: E402

RECORD = """상담 개요: 가정 방문 상담.
[아동 진술]
등이랑 팔이 아팠다고 함.
[대상자 태도]
보호자는 협조적이었음.
[위험요인]
부의 음주 뒤 체벌이 반복됨.
[강점과 자원]
조모에게 연락하는 방법을 앎.
[소견]
다음 회차에 치료 여부 확인 필요.
"""


def _url(session_id: str, tail: str = "") -> str:
    return f"/api/v1/sessions/{session_id}/source-document{tail}"


def _upload(client: TestClient, headers, session_id: str, name: str = "기록.txt", data: bytes = RECORD.encode()):
    return client.post(_url(session_id), files={"file": (name, data, "application/octet-stream")}, headers=headers)


def _zip(entries: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return buffer.getvalue()


DOCX = _zip(
    {
        "word/document.xml": (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            "<w:p><w:r><w:t>[위험요인]</w:t></w:r></w:p><w:p><w:r><w:t>부의 음주 뒤 </w:t></w:r><w:r><w:t>체벌</w:t></w:r></w:p>"
            "</w:body></w:document>"
        )
    }
)
def _corrupt(data: bytes) -> bytes:
    """압축 본문 바이트를 뒤집은 zip(여는 것은 되고 읽을 때 zlib · CRC 오류 — 민규 #137 낮음 1)."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for info in source.infolist():
            archive.writestr(info.filename, source.read(info.filename))
    raw = bytearray(buffer.getvalue())
    start = 30 + len(zipfile.ZipFile(io.BytesIO(raw)).infolist()[0].filename.encode())
    for index in range(start + 2, start + 12):
        raw[index] ^= 0xFF
    return bytes(raw)


HWPX = _zip(
    {
        "Contents/section0.xml": (
            '<hs:sec xmlns:hs="h" xmlns:hp="p"><hp:p><hp:run><hp:t>[소견]</hp:t></hp:run></hp:p>'
            "<hp:p><hp:run><hp:t>치료 여부 확인</hp:t><hp:tbl><hp:p><hp:run><hp:t>표 안</hp:t></hp:run></hp:p></hp:tbl></hp:run></hp:p></hs:sec>"
        )
    }
)


def test_txt_upload_fills_summary_and_note_draft(client: TestClient, counselor_headers, session: dict) -> None:
    response = _upload(client, counselor_headers, session["id"])

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["fill_source"] == "HEADINGS" and data["file_format"] == "txt" and data["char_count"] == len(RECORD.strip())
    assert data["note_draft"]["statement"] == "등이랑 팔이 아팠다고 함."
    assert data["note_draft"]["opinion"] == "다음 회차에 치료 여부 확인 필요."
    assert data["followup_draft"] is None
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED" and detail["source"] == "DOCUMENT"
    summary = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers).json()["data"]["summary"]
    assert summary["assessment"]["safety_risks"]["text"] == "부의 음주 뒤 체벌이 반복됨."
    assert summary["assessment"]["strengths_resources"]["text"] == "조모에게 연락하는 방법을 앎."
    assert summary["overview"] == "가정 방문 상담."


@pytest.mark.parametrize(("name", "data", "field", "text"), [("a.docx", DOCX, "safety_risks", "부의 음주 뒤 체벌"), ("a.hwpx", HWPX, None, None)])
def test_docx_and_hwpx_are_read(client: TestClient, counselor_headers, session: dict, name, data, field, text) -> None:
    response = _upload(client, counselor_headers, session["id"], name, data)

    assert response.status_code == 201, response.text
    body = response.json()["data"]
    if field:
        summary = client.get(f"/api/v1/sessions/{session['id']}/summary", headers=counselor_headers).json()["data"]["summary"]
        assert summary["assessment"][field]["text"] == text
    else:
        # 표 안 문단은 바깥 문단과 겹치지 않고 한 번만 나온다.
        assert body["text"].count("표 안") == 1 and body["note_draft"]["opinion"].startswith("치료 여부 확인")


@pytest.mark.parametrize(
    ("name", "data", "needle"),
    [
        ("a.hwp", b"HWP Document File", "HWPX"),
        ("a.png", b"x", ".txt"),
        ("a.txt", b"", "빈 파일"),
        ("a.txt", b"\x00", "글자를 찾지"),
        ("a.txt", ("가" * 30001).encode(), "30,000"),
        ("a.docx", b"not a zip", "손상"),
        ("a.docx", "CORRUPT_DOCX", "손상"),
        ("a.hwpx", "CORRUPT_HWPX", "손상"),
        ("a.pdf", b"%PDF-1.4 broken", "PDF"),
        ("a.hwpx", "LONG_SECTION_NUMBER", "한글"),
    ],
    # 매개변수(긴 bytes)가 시험 이름이 되면 Windows 의 PYTEST_CURRENT_TEST 한도(32,767자)를 넘는다(민규 #137 R6).
    ids=["hwp", "png", "empty", "nul", "too-long", "not-zip", "corrupt-docx", "corrupt-hwpx", "broken-pdf", "long-section-no"],
)
def test_bad_files_are_rejected(client: TestClient, counselor_headers, session: dict, name, data, needle) -> None:
    data = {
        "CORRUPT_DOCX": _corrupt(DOCX),
        "CORRUPT_HWPX": _corrupt(HWPX),
        # section 번호가 아주 길면 정수로 바꾸다 500 이 났다(민규 #137 R8).
        "LONG_SECTION_NUMBER": _zip({"Contents/section" + "9" * 5000 + ".xml": "<hs:sec/>"}),
    }.get(data, data)
    response = _upload(client, counselor_headers, session["id"], name, data)

    assert response.status_code == 422, response.text
    assert needle in response.json()["error"]["message"]
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED" and detail["source"] == "AUDIO"


def test_too_big_file_is_rejected(client: TestClient, counselor_headers, session: dict) -> None:
    response = _upload(client, counselor_headers, session["id"], "a.txt", b"a" * (10 * 1024 * 1024 + 1))

    # 요청 본문 한도(main.py 미들웨어, 문서 경로는 10MB + 머리글 1MB) 또는 서비스 검사가 막는다.
    assert response.status_code in (400, 413, 422) and "10 MB" in response.json()["error"]["message"]


def test_only_new_sessions_take_a_document(client: TestClient, counselor_headers, case: dict) -> None:
    doc_session = create_session(client, counselor_headers, case["id"])
    audio_session = create_session(client, counselor_headers, case["id"])
    upload_audio(client, counselor_headers, audio_session["id"])

    first = _upload(client, counselor_headers, doc_session["id"])
    again = _upload(client, counselor_headers, doc_session["id"])
    on_audio = _upload(client, counselor_headers, audio_session["id"])
    audio_on_doc = client.post(
        f"/api/v1/sessions/{doc_session['id']}/audio",
        files={"file": ("a.wav", make_wav_bytes(), "audio/wav")},
        headers=counselor_headers,
    )

    assert first.status_code == 201
    assert again.status_code == 409 and on_audio.status_code == 409
    assert audio_on_doc.status_code == 409


def test_summary_edit_and_approve_work_on_document_sessions(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])
    url = f"/api/v1/sessions/{session['id']}/summary"

    patched = client.patch(url, json={"assessment": {"desired_changes": "학교 적응"}}, headers=counselor_headers)
    approved = client.post(f"{url}/approve", headers=counselor_headers)

    assert patched.status_code == 200, patched.text
    assert approved.status_code == 200, approved.text
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "APPROVED"


def test_followups_without_llm_are_empty(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])

    response = client.post(_url(session["id"], "/followups"), headers=counselor_headers)

    assert response.status_code == 200, response.text
    draft = response.json()["data"]["followup_draft"]
    assert draft["source"] == "NONE" and draft["checks"] == [] and draft["questions"] == []


def test_followups_need_a_document_session_with_content(client: TestClient, counselor_headers, case: dict) -> None:
    plain = create_session(client, counselor_headers, case["id"])
    empty = create_session(client, counselor_headers, case["id"])
    _upload(client, counselor_headers, empty["id"], "a.txt", "머리줄 없는 글".encode())

    assert client.post(_url(plain["id"], "/followups"), headers=counselor_headers).status_code == 409
    response = client.post(_url(empty["id"], "/followups"), headers=counselor_headers)
    assert response.status_code == 409 and "3단계" in response.json()["error"]["message"]
    assert client.get(_url(plain["id"]), headers=counselor_headers).status_code == 404


def test_other_counselor_is_forbidden(client: TestClient, counselor_headers, other_counselor_headers, session: dict) -> None:
    assert _upload(client, other_counselor_headers, session["id"]).status_code == 403
    _upload(client, counselor_headers, session["id"])
    assert client.get(_url(session["id"]), headers=other_counselor_headers).status_code == 403


def test_audit_has_no_document_text(client: TestClient, counselor_headers, session: dict, db) -> None:
    _upload(client, counselor_headers, session["id"])
    client.post(_url(session["id"], "/followups"), headers=counselor_headers)

    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_type == "SessionSourceDocument")))
    assert {log.action for log in logs} == {AuditAction.SOURCE_DOCUMENT_UPLOADED, AuditAction.DOCUMENT_FOLLOWUPS_DRAFTED}
    assert all("체벌" not in str(log.detail) and "아팠" not in str(log.detail) for log in logs)


def test_task_list_carries_document_source(client: TestClient, counselor_headers, session: dict) -> None:
    _upload(client, counselor_headers, session["id"])

    items = client.get("/api/v1/tasks", headers=counselor_headers).json()["data"]["items"]

    assert [(item["session_source"], item["task_type"]) for item in items] == [("DOCUMENT", "REVIEW_ANALYSIS")]


@pytest.fixture
def modeling(monkeypatch):
    calls = {}
    module = types.ModuleType("ai.modeling.abuse.document_note_llm")
    module.note_input_text = dn.note_input_text
    module.rule_based_note = dn.rule_based_note

    def fill_note(text, known_identifiers=None, deadline=None):
        calls["fill"] = (text, known_identifiers)
        if calls.get("raise"):
            raise calls["raise"]
        return {"assessment": {"safety_risks": "부의 음주 뒤 체벌이 반복됨."}, "note": {"statement": "등이랑 팔이 아팠다고 함."}, "overview": "", "model": "m"}

    def draft_followups(text, known_identifiers=None, deadline=None):
        calls["draft"] = text
        return {"checks": [{"text": "치료 여부 확인 필요."}], "questions": [{"text": "등은 지금 어때?", "reason": "통증 뒤가 안 나옴"}], "model": "m"}

    module.fill_note = fill_note
    module.draft_followups = draft_followups
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.document_note_llm", module)
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    return calls


def test_modeling_path_uses_ai_module(client: TestClient, counselor_headers, case: dict, session: dict, modeling) -> None:
    data = _upload(client, counselor_headers, session["id"]).json()["data"]

    assert data["fill_source"] == "AI" and data["fill_model"] == "m"
    assert modeling["fill"][1] == [case["child_alias"]]
    draft = client.post(_url(session["id"], "/followups"), headers=counselor_headers).json()["data"]["followup_draft"]
    assert draft["source"] == "AI" and draft["questions"][0]["text"] == "등은 지금 어때?"
    # 4단계 입력은 3단계 칸(요약 4칸 + 일지 초안)이다 — 문서 원문 전체가 아니다.
    assert "위험요인: 부의 음주 뒤 체벌이 반복됨." in modeling["draft"] and "상담 개요" not in modeling["draft"]


def test_modeling_masks_registered_names_too(client: TestClient, counselor_headers, case: dict, session: dict, modeling) -> None:
    """올린 문서에는 실명이 들어 있기 쉽다 — 3단계 채우기 · 4단계 초안 모두 등록 실명까지 가린다(민규 #137, #138 과 같게)."""

    body = {"child_name": "한가람", "target_person": {"name": "한누리", "relation": "부"}}
    assert client.put(f"/api/v1/cases/{case['id']}/personal-info", json=body, headers=counselor_headers).status_code == 200
    seen = {}
    real_draft = sys.modules["ai.modeling.abuse.document_note_llm"].draft_followups

    def draft_followups(text, known_identifiers=None, deadline=None):
        seen["draft"] = known_identifiers
        return real_draft(text, known_identifiers=known_identifiers, deadline=deadline)

    sys.modules["ai.modeling.abuse.document_note_llm"].draft_followups = draft_followups

    _upload(client, counselor_headers, session["id"])
    client.post(_url(session["id"], "/followups"), headers=counselor_headers)

    for known in (modeling["fill"][1], seen["draft"]):
        assert {"한가람", "가람", "한누리", "누리", case["child_alias"]} <= set(known)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [(TimeoutError(), 504, "AI_TIMEOUT"), (type("DocumentNoteOutputError", (Exception,), {})("원문"), 502, "AI_INVALID_OUTPUT"), (RuntimeError("원문"), 502, "AI_FAILED")],
)
def test_modeling_errors_keep_session_new(client: TestClient, counselor_headers, session: dict, modeling, error, status, code) -> None:
    modeling["raise"] = error

    response = _upload(client, counselor_headers, session["id"])

    assert response.status_code == status and response.json()["error"]["code"] == code and "원문" not in response.text
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED"
    assert source_document_service.get_row is not None


# ---------------- document_note_llm 검사 함수 ----------------


def test_copied_from_source_drops_invented_text() -> None:
    source = "부의 음주 뒤 체벌이 반복됨. 조모에게 연락하는 방법을 앎."

    assert dn.copied_from_source("부의 음주 뒤 체벌이 반복됨.", source)
    assert dn.copied_from_source("조모에게  연락하는 방법을 앎", source)
    assert not dn.copied_from_source("아동이 학교에서 따돌림을 당했다고 진술함.", source)


def test_keep_copied_drops_sentences_with_flipped_meaning() -> None:
    """부정어가 빠지거나 낱말이 바뀐 문장은 원문 복사로 보지 않는다(민규 #137 R1)."""

    source = "보호자가 방문하지 않음.\n- 아동은 집에서 밥을 먹지 못함. 학교는 다님."

    assert not dn.copied_from_source("보호자가 방문함.", source)
    assert dn.keep_copied("보호자가 방문함.", source) == ""
    assert dn.keep_copied("보호자가 방문하지 않음. 아동은 집에서 밥을 먹음.", source) == "보호자가 방문하지 않음."
    assert dn.keep_copied("아동은 집에서 밥을 먹지 못함.\n학교는 다님", source) == "아동은 집에서 밥을 먹지 못함.\n학교는 다님"
    raw = {"note": {"attitude": "보호자가 방문함.", "statement": "아동은  집에서 밥을 먹지 못함"}}
    cleaned = dn.clean_note(raw, source)
    assert cleaned["note"]["attitude"] == "" and cleaned["note"]["statement"] == "아동은 집에서 밥을 먹지 못함"


def test_keep_copied_needs_a_whole_source_sentence() -> None:
    """원문 문장 앞부분만 자르거나 숫자 사이 기호를 바꾼 것은 버리고, 칸 이름 · 글머리표만 뗀 것은 남긴다(민규 #137 보완)."""

    source = "[아동 진술]\n아동은 맞았다고 말하지 않았다.\n- 보호자가 방문하지 않음.\n출결: 주 3~4회 결석함."

    assert dn.keep_copied("아동은 맞았다.", source) == ""
    assert dn.keep_copied("보호자가 방문.", source) == ""
    assert dn.keep_copied("주 34회 결석함.", source) == ""
    assert dn.keep_copied("주 3~4회 결석함.", source) == "주 3~4회 결석함."
    assert dn.keep_copied("출결: 주 3~4회 결석함", source) == "출결: 주 3~4회 결석함"
    assert dn.keep_copied("보호자가 방문하지 않음", source) == "보호자가 방문하지 않음"
    assert dn.keep_copied("아동은  맞았다고 말하지 않았다.", source) == "아동은  맞았다고 말하지 않았다."


def test_clean_note_keeps_only_copied_fields() -> None:
    source = "보호자는 협조적이었음. 다음 회차에 치료 여부 확인 필요."
    raw = {
        "assessment": {"safety_risks": "아동이 학교에서 따돌림을 당함.", "unknown": "x"},
        "note": {"attitude": "보호자는 협조적이었음.", "opinion": "치료 ব্যবস্থা 확인"},
        "overview": "",
    }

    cleaned = dn.clean_note(raw, source)

    assert cleaned["assessment"]["safety_risks"] == "" and cleaned["note"]["attitude"] == "보호자는 협조적이었음."
    assert cleaned["note"]["opinion"] == "" and "unknown" not in cleaned["assessment"]
    with pytest.raises(dn.DocumentNoteOutputError):
        dn.clean_note({"note": {"attitude": "지어낸 문장입니다"}}, source)


def test_clean_followups_drops_leading_and_closed_questions() -> None:
    source = "- 아동 진술: 등이랑 팔이 아팠다고 함."
    raw = {
        "checks": [{"text": "치료 여부 확인 필요."}, {"text": "치료 여부 확인 필요."}],
        "questions": [
            {"text": "등이랑 팔은 지금 어때?", "reason": "통증 이후"},
            {"text": "아빠가 때렸어?", "reason": "x"},
            {"text": "많이 아팠지?", "reason": "x"},
            {"text": "아빠는 어떻게 했어?", "reason": "x"},
        ],
    }

    cleaned = dn.clean_followups(raw, source)

    assert cleaned["checks"] == [{"text": "치료 여부 확인 필요."}]
    assert [q["text"] for q in cleaned["questions"]] == ["등이랑 팔은 지금 어때?"]


def test_rule_based_note_reads_headings_and_colons() -> None:
    note = dn.rule_based_note("위험요인: 부의 음주\n강점: 조모 연락\n[소견]\n첫 줄\n둘째 줄")

    assert note["assessment"]["safety_risks"] == "부의 음주" and note["assessment"]["strengths_resources"] == "조모 연락"
    assert note["note"]["opinion"] == "첫 줄\n둘째 줄"
    # 칸 이름 그대로('위험 신호 검토 결과')인 머리줄도 그 칸이다.
    assert dn.rule_based_note("[위험 신호 검토 결과]\n상처 없음")["note"]["signals"] == "상처 없음"
    plain = dn.rule_based_note("머리줄 없는 글")
    assert plain["overview"] == "머리줄 없는 글" and not any(plain["note"].values())


def _pdf(pages: int) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "needle"),
    [
        (_pdf(51), "50쪽"),  # 쪽이 아주 많은 PDF
        (_pdf(1), "글자를 찾지"),  # 글자 없는(스캔) PDF
        (b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF", "PDF"),  # 깨진 구조
        (b"%PDF-1.4\n" + b"\x00" * 2048, "PDF"),
    ],
    ids=["51-pages", "no-text", "broken-structure", "nul-body"],
)
def test_pdf_limits_and_broken_files(client: TestClient, counselor_headers, session: dict, data, needle) -> None:
    response = _upload(client, counselor_headers, session["id"], "a.pdf", data)

    assert response.status_code == 422, response.text
    assert needle in response.json()["error"]["message"]


class _FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


def _fake_pdf(monkeypatch, pages) -> None:
    import pypdf

    class Reader:
        is_encrypted = False

        def __init__(self, _stream) -> None:
            self.pages = [_FakePage(text) for text in pages]

    monkeypatch.setattr(pypdf, "PdfReader", Reader)


def test_pdf_counts_cleaned_characters_and_never_drops_pages(monkeypatch) -> None:
    """공백이 많은 첫 쪽 뒤의 짧은 쪽이 빠지지 않고, 정리한 글이 상한을 넘으면 앞 쪽만 남기지 않고 422(민규 #137 R2)."""

    from app.services import document_text

    _fake_pdf(monkeypatch, ["첫 쪽" + " " * 31000 + "끝", "마지막 쪽"])
    text = document_text.extract_text("a.pdf", b"%PDF-1.4")
    assert text.endswith("마지막 쪽")

    _fake_pdf(monkeypatch, ["가" * 20000, "나" * 20000, "다"])
    with pytest.raises(APIError) as caught:
        document_text.extract_text("a.pdf", b"%PDF-1.4")
    assert caught.value.status_code == 422 and "30,000" in caught.value.message


def test_pdf_joins_wrapped_lines_so_copy_check_sees_whole_sentences(monkeypatch) -> None:
    """PDF 는 보이는 줄마다 줄을 바꾼다. 꺾인 줄을 이어, 두 줄에 걸친 문장은 남고 꺾인 줄 앞부분만 옮긴 조각은 버린다(민규 #137 보완)."""

    from app.services import document_text

    page = (
        "[아동 진술]\n"
        "아동은 아버지에게 맞았다고 말하지 않았으며 보호자는 가정 방문을\n"
        "거부하였다. 다음 회차에 학교 출결을 다시 확인하기로 하였다. 아동은 맞았다\n"
        "고 말하지 않았다.\n"
        "- 보호자 연락 안 됨\n"
        "출결: 주 3~4회 결석함."
    )
    _fake_pdf(monkeypatch, [page])
    source = document_text.extract_text("a.pdf", b"%PDF-1.4")

    assert source.split("\n") == [
        "[아동 진술]",
        "아동은 아버지에게 맞았다고 말하지 않았으며 보호자는 가정 방문을 거부하였다. 다음 회차에 학교 출결을 다시 확인하기로"
        " 하였다. 아동은 맞았다 고 말하지 않았다.",
        "- 보호자 연락 안 됨",
        "출결: 주 3~4회 결석함.",
    ]
    whole = "아동은 아버지에게 맞았다고 말하지 않았으며 보호자는 가정 방문을 거부하였다."
    assert dn.keep_copied(whole, source) == whole
    assert dn.keep_copied("아동은 맞았다고 말하지 않았다.", source) == "아동은 맞았다고 말하지 않았다."
    assert dn.keep_copied("아동은 맞았다.", source) == ""
    assert dn.keep_copied("아동은 아버지에게 맞았다고 말하지 않았으며 보호자는 가정 방문을", source) == ""
    assert dn.keep_copied("보호자 연락 안 됨", source) == "보호자 연락 안 됨"
    assert dn.keep_copied("주 3~4회 결석함.", source) == "주 3~4회 결석함."

    # 짧은 줄(문단 끝) · 문장이 끝난 줄 · '칸 이름:' 줄은 잇지 않는다.
    joined = document_text._join_wrapped(
        "보호자는 가정 방문을 거부하였고 학교 출결은 다음 회차에 확인\n아동 진술: 맞은 적 없다고 함\n짧은 줄\n다음 문단"
    )
    assert joined.split("\n") == [
        "보호자는 가정 방문을 거부하였고 학교 출결은 다음 회차에 확인",
        "아동 진술: 맞은 적 없다고 함",
        "짧은 줄",
        "다음 문단",
    ]


def test_pdf_reading_leaves_no_file_text_in_logs(client: TestClient, counselor_headers, session: dict, caplog) -> None:
    """pypdf 로그 · 경고에 파일에서 나온 글자(앞 바이트 등)가 서버 로그로 나가지 않는다 — 실패 · 성공 모두(민규 #137 R4)."""

    import logging

    caplog.set_level(logging.DEBUG)
    broken = _upload(client, counselor_headers, session["id"], "a.pdf", b"QZXWV" + b"\x00" * 200)
    blank = _upload(client, counselor_headers, session["id"], "a.pdf", _pdf(1))

    assert broken.status_code == 422 and blank.status_code == 422
    assert "QZXWV" not in caplog.text
    assert not [record for record in caplog.records if record.name.startswith("pypdf")]


def test_control_characters_in_filename_are_dropped(client: TestClient, counselor_headers, session: dict) -> None:
    """파일 이름의 NUL 등 제어 문자는 빼고 저장한다(PostgreSQL 500 막기, 민규 #137 R7)."""

    # 브라우저처럼 파일 이름 바이트를 그대로 보낸다(TestClient 는 % 로 바꿔 보낸다).
    boundary = "ispotboundary"
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="기록\x00\x07.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n{RECORD}\r\n--{boundary}--\r\n"
    ).encode()
    headers = {**counselor_headers, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    response = client.post(_url(session["id"]), content=body, headers=headers)

    assert response.status_code == 201, response.text
    assert response.json()["data"]["filename"] == "기록.txt"


def test_followups_respect_a_note_the_counselor_emptied(client: TestClient, counselor_headers, session: dict, modeling) -> None:
    """일지를 빈 글로 저장하면 문서 일지 초안으로 되돌아가지 않는다. 요약까지 비었으면 409(민규 #137 R3)."""

    assert _upload(client, counselor_headers, session["id"]).status_code == 201
    sid = session["id"]
    emptied = {key: "" for key in ("safety_changes", "strengths_resources", "safety_risks", "desired_changes")}
    patched = client.patch(f"/api/v1/sessions/{sid}/summary", json={"assessment": emptied}, headers=counselor_headers)
    assert patched.status_code == 200, patched.text
    saved = client.post(f"/api/v1/sessions/{sid}/documents", json={"title": "상담 일지", "content": ""}, headers=counselor_headers)
    assert saved.status_code == 201, saved.text

    response = client.post(_url(sid, "/followups"), headers=counselor_headers)

    assert response.status_code == 409, response.text
    assert "draft" not in modeling or modeling["draft"] is None


def test_text_extraction_has_its_own_time_limit(client: TestClient, counselor_headers, session: dict, monkeypatch) -> None:
    """글자 뽑기가 오래 걸리면 LLM 까지 기다리지 않고 422(DOCUMENT_TEXT_TIMEOUT_SECONDS)."""

    import threading as _threading

    gate = _threading.Event()
    monkeypatch.setattr(settings, "DOCUMENT_TEXT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(source_document_service, "extract_text", lambda *_: gate.wait(2) or "")

    response = _upload(client, counselor_headers, session["id"])
    gate.set()

    assert response.status_code == 422 and "오래 걸립니다" in response.json()["error"]["message"]
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED"


@pytest.fixture
def one_text_slot():
    original = settings.DOCUMENT_TEXT_MAX_CONCURRENCY
    settings.DOCUMENT_TEXT_MAX_CONCURRENCY = 1
    source_document_service.reset_text_slots()
    yield
    settings.DOCUMENT_TEXT_MAX_CONCURRENCY = original
    source_document_service.reset_text_slots()


def test_text_extraction_has_a_server_wide_limit(client: TestClient, counselor_headers, case: dict, one_text_slot, monkeypatch) -> None:
    """제한 시간을 넘긴 글자 뽑기도 끝날 때까지 자리를 쓰고, 자리가 없으면 429(민규 #137 낮음 3)."""

    import threading as _threading
    import time as _time

    gate = _threading.Event()
    real = source_document_service.extract_text
    monkeypatch.setattr(settings, "DOCUMENT_TEXT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(source_document_service, "extract_text", lambda *args: gate.wait(5) and real(*args))
    first = create_session(client, counselor_headers, case["id"])
    second = create_session(client, counselor_headers, case["id"])

    assert _upload(client, counselor_headers, first["id"]).status_code == 422  # 제한 시간 — thread 는 아직 돈다
    busy = _upload(client, counselor_headers, second["id"])
    assert busy.status_code == 429 and "다른 문서" in busy.json()["error"]["message"]
    detail = client.get(f"/api/v1/sessions/{second['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "CREATED" and detail["source"] == "AUDIO"

    gate.set()
    for _ in range(100):  # 뒤에서 돌던 글자 뽑기가 끝나면 자리가 돌아온다
        if source_document_service._text_slots.acquire(blocking=False):
            source_document_service._text_slots.release()
            break
        _time.sleep(0.02)
    monkeypatch.setattr(settings, "DOCUMENT_TEXT_TIMEOUT_SECONDS", 5.0)
    assert _upload(client, counselor_headers, second["id"]).status_code == 201


def test_audio_upload_does_not_overwrite_a_document_that_landed_first(
    client: TestClient, counselor_headers, session: dict, db, monkeypatch
) -> None:
    """음성을 저장하는 사이 문서가 먼저 커밋되면 음성은 409 이고 파일도 남기지 않는다(민규 #137 낮음 2)."""

    import uuid as _uuid

    from sqlalchemy import update as _update

    from app.core import storage
    from app.core.enums import SessionSource, SessionStatus
    from app.models.audio import AudioFile
    from app.models.session import ConsultationSession
    from app.services import audio_service

    saved = []
    real_save = storage.save_audio_chunks

    def save_then_document_lands(**kwargs):
        stored = real_save(**kwargs)
        saved.append(stored.relative_path)
        db.execute(
            _update(ConsultationSession)
            .where(ConsultationSession.id == _uuid.UUID(session["id"]))
            .values(status=SessionStatus.AI_REVIEW_REQUIRED, source=SessionSource.DOCUMENT)
        )
        db.commit()
        return stored

    monkeypatch.setattr(audio_service.storage, "save_audio_chunks", save_then_document_lands)
    status, body = upload_audio(client, counselor_headers, session["id"])

    assert status == 409, body
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED" and detail["source"] == "DOCUMENT"
    db.expire_all()
    assert db.scalar(select(AudioFile.id).where(AudioFile.session_id == _uuid.UUID(session["id"]))) is None
    assert saved and not storage.resolve_stored_path(saved[0]).exists()


LEVEL = __import__("app.core.enums", fromlist=["RiskLevel"]).RiskLevel.HIGH.value


def test_document_sessions_refuse_audio_paths(client: TestClient, counselor_headers, session: dict) -> None:
    """문서 회차는 음성 · 전사 · 분석 · 위험도 판단 창구에서 500 이 아니라 404 · 409(민규 의견)."""

    _upload(client, counselor_headers, session["id"])
    base = f"/api/v1/sessions/{session['id']}"

    analysis = client.post(f"{base}/analysis", headers=counselor_headers)
    overall = client.put(f"{base}/risk-assessment", json={"counselor_level": LEVEL, "reason": "가상"}, headers=counselor_headers)
    typed = client.put(f"{base}/risk-assessments/PHYSICAL", json={"counselor_level": LEVEL, "reason": "가상"}, headers=counselor_headers)

    assert analysis.status_code == 409 and "초안 다시 만들기" in analysis.json()["error"]["message"]
    assert overall.status_code == 409 and typed.status_code == 409, (overall.text, typed.text)
    for method, path in [("post", "/transcript"), ("post", "/transcript/confirm"), ("get", "/audio"), ("get", "/audio/file")]:
        assert getattr(client, method)(base + path, headers=counselor_headers).status_code in (404, 409)
    for path in ("/transcript", "/analysis", "/voice-marks", "/risk-assessment", "/risk-assessments"):
        assert client.get(base + path, headers=counselor_headers).status_code == 200


def test_upload_fills_ai_completed_at_for_task_waiting_time(client: TestClient, counselor_headers, session: dict, db) -> None:
    from app.models.session import ConsultationSession

    _upload(client, counselor_headers, session["id"])
    row = db.get(ConsultationSession, __import__("uuid").UUID(session["id"]))
    item = client.get("/api/v1/tasks", headers=counselor_headers).json()["data"]["items"][0]

    assert row.ai_completed_at is not None
    # PostgreSQL 은 세션 시간대(+09)로 돌려준다 — UTC 로 맞춰 비교한다(SQLite 는 시간대 없는 UTC).
    from datetime import timezone

    done = row.ai_completed_at
    done_utc = done.astimezone(timezone.utc) if done.tzinfo else done
    assert item["waiting_since"].startswith(done_utc.strftime("%Y-%m-%dT%H:%M"))


def test_created_to_review_is_not_open_to_audio_paths() -> None:
    """CREATED → AI_REVIEW_REQUIRED 는 전이 표에 없다(문서 업로드 창구만 옮긴다)."""

    from app.core.enums import SessionStatus
    from app.core.state_machine import can_transition

    assert not can_transition(SessionStatus.CREATED, SessionStatus.AI_REVIEW_REQUIRED)


# ---------------- 문서 회차 학대 신호 · 대화 주제(2026-11-04) ----------------

from ai.modeling.abuse import document_signals as ds  # noqa: E402

SIGNALS = {
    "abuse_signals": [
        {"abuse_type": "EMOTIONAL", "detected": True, "segment_ids": ["doc_002"], "detection_source": "MODEL", "filtered_reason": None},
        {"abuse_type": "PHYSICAL", "detected": False, "segment_ids": [], "detection_source": None, "filtered_reason": None},
    ],
    "risk_utterances": [
        {"text": "음주 후 고성이 있었음.", "segment_ids": ["doc_002"], "abuse_type": "EMOTIONAL", "subtype": "가정폭력·폭력상황 노출",
         "evidence_strength": "MEDIUM", "reason": "", "evidence_verified": True, "legal_references": []},
    ],
    "severity_ratings": [{"major_type": "정서학대", "level": 2, "reason": "가상", "matched_evidence": "", "reviewed": False}],
    "topic_tags": [{"topic": "보호자 관계", "segment_ids": ["doc_001", "doc_002"], "quote": "부의 음주가 계속됨.", "start_ms": None}],
    "model": "m",
}


@pytest.fixture
def signals_module(monkeypatch, modeling):
    calls = {}
    module = types.ModuleType("ai.modeling.abuse.document_signals")

    def analyze_document_signals(text, known_identifiers=None, deadline=None):
        calls["text"] = text
        if calls.get("raise"):
            raise calls["raise"]
        return dict(SIGNALS)

    module.analyze_document_signals = analyze_document_signals
    monkeypatch.setitem(sys.modules, "ai.modeling.abuse.document_signals", module)
    return calls


def _history(client: TestClient, headers, case_id: str, session_id: str) -> dict:
    rows = client.get(f"/api/v1/cases/{case_id}/signal-history", headers=headers).json()["data"]["sessions"]
    return next(row for row in rows if row["session_id"] == session_id)


def test_document_upload_fills_signal_history(client: TestClient, counselor_headers, case: dict, session: dict, signals_module) -> None:
    """문서를 올리면 뒤에서 신호 · 주제를 만들어 상담 이력(주제 비중 · 세부 신호)이 녹음 회차처럼 읽는다."""

    assert _upload(client, counselor_headers, session["id"]).status_code == 201

    row = _history(client, counselor_headers, case["id"], session["id"])
    assert row["analysis_status"] == "COMPLETED"
    assert [t["topic"] for t in row["topics"]] == ["보호자 관계"] and row["topics"][0]["count"] == 2
    # 근거가 기록 문장이라 '화자 확인 중' 보류가 아니다.
    assert row["subtypes"] == [
        {"abuse_type": "EMOTIONAL", "subtype": "가정폭력·폭력상황 노출", "count": 1, "segment_ids": ["doc_002"], "pending": False}
    ]
    emotional = next(t for t in row["types"] if t["abuse_type"] == "EMOTIONAL")
    assert emotional["detected"] is True and emotional["ai_level"] == 2
    analysis = client.get(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers).json()["data"]["analysis"]
    assert analysis["provider"] == "document" and analysis["transcript_id"] is None
    # 회차는 3단계 그대로다(분석이 회차 상태를 바꾸지 않는다).
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED" and detail["source"] == "DOCUMENT"
    assert "부의 음주" in signals_module["text"]


def test_document_signal_failure_keeps_the_session(client: TestClient, counselor_headers, case: dict, session: dict, signals_module) -> None:
    signals_module["raise"] = RuntimeError("원문이 섞인 예외")

    assert _upload(client, counselor_headers, session["id"]).status_code == 201

    row = _history(client, counselor_headers, case["id"], session["id"])
    assert row["analysis_status"] == "FAILED" and row["topics"] is None
    analysis = client.get(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers).json()["data"]["analysis"]
    assert "원문" not in (analysis["error"]["message"] or "")
    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=counselor_headers).json()["data"]
    assert detail["status"] == "AI_REVIEW_REQUIRED"


def test_no_document_signals_without_modeling(client: TestClient, counselor_headers, case: dict, session: dict) -> None:
    assert _upload(client, counselor_headers, session["id"]).status_code == 201

    assert _history(client, counselor_headers, case["id"], session["id"])["analysis_status"] is None


def test_document_segments_split_sentences_and_drop_headings() -> None:
    segments = ds.document_segments("[아동 진술]\n아동은 무서웠다고 함. 방에 있었음.\n\n[소견]\n계속 확인 필요.")

    assert [s["text"] for s in segments] == ["아동은 무서웠다고 함.", "방에 있었음.", "계속 확인 필요."]
    assert [s["segment_id"] for s in segments] == ["doc_001", "doc_002", "doc_003"]


def test_risk_utterances_keep_only_linked_evidence() -> None:
    subtype_result = {
        "results": [
            {
                "major_type": "정서학대",
                "subtypes": [
                    {
                        "type": "가정폭력·폭력상황 노출",
                        "evidences": [
                            {"evidence": "고성", "matched_evidence": "음주 후 고성", "evidence_strength": "중간", "evidence_verified": True,
                             "timestamps": {"segment_ids": ["doc_004"]}},
                            {"evidence": "지어낸 근거", "evidence_verified": False, "timestamps": None},
                        ],
                    }
                ],
            }
        ]
    }

    rows = ds.risk_utterances_from(subtype_result)
    signals = ds.abuse_signals_from({"정서학대": {"detected": True}, "방임": {"detected": False}}, rows, ["정서학대", "방임"])

    assert [(r["abuse_type"], r["subtype"], r["segment_ids"], r["evidence_strength"]) for r in rows] == [
        ("EMOTIONAL", "가정폭력·폭력상황 노출", ["doc_004"], "MEDIUM")
    ]
    assert signals[0] == {"abuse_type": "EMOTIONAL", "detected": True, "segment_ids": ["doc_004"], "detection_source": "MODEL", "filtered_reason": None}
    assert signals[1]["detected"] is False and signals[1]["detection_source"] is None
