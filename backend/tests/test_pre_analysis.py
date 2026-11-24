# 원문 확정 전 AI 전체 분석(ANALYZE_BEFORE_CONFIRM, 2026-11-24, app/services/pre_analysis_service.py).
#
# 켜면 STT 작업이 1차 스캔 대신 AI 전체 분석으로 '먼저 들어볼 곳'(key_scan, model=ai_analysis)을 채우고, 결과 전체를
# 그 전사 판에 암호문으로 둔다. 원문을 확정하고 첫 분석을 하면 근거 줄을 고치지 않았을 때 그 결과를 다시 쓴다.
# AI 어댑터 · 1차 스캐너는 가짜다. 데이터는 모두 가상이다.

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.adapters.ai_adapter import AIAnalysisBundle, MockAIAdapter
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.enums import AuditAction
from app.models.audit_log import AuditLog
from app.models.transcript import Transcript
from app.services import analysis_service, key_scan_service
from tests.test_stt_transcript import transcribed_session

REFERENCE = {
    "law_name": "아동복지법",
    "article": "제17조",
    "item_label": "제3호",
    "text": "아동의 신체에 손상을 주거나 신체의 건강 및 발달을 해치는 신체적 학대행위",
    "portal_url": "https://www.law.go.kr/법령/아동복지법",
}


class FakeAdapter:
    """MockAIAdapter 결과에 위험 발화 하나(두 번째 발화, 신체학대)를 더한다. 부를 때마다 calls 에 쌓는다."""

    name = "modeling"

    def __init__(self, calls: List[Dict[str, Any]], fail: bool = False) -> None:
        self.calls = calls
        self.fail = fail

    def analyze(self, transcript_payload: Dict[str, Any]) -> AIAnalysisBundle:
        self.calls.append(transcript_payload)

        if self.fail:
            raise RuntimeError("가상 오류")

        bundle = MockAIAdapter().analyze(transcript_payload)
        target = transcript_payload["segments"][1]["segment_id"]
        utterance = {
            "text": "가상 근거 문장",
            "segment_ids": [target],
            "abuse_type": "PHYSICAL",
            "subtype": "직접 신체 가해",
            "evidence_strength": "HIGH",
            "reason": "가상 이유",
            "evidence_verified": True,
            "legal_references": [REFERENCE],
        }
        result = bundle.result.model_copy(
            update={
                "risk_utterances": [utterance],
                "abuse_signals": [
                    {"abuse_type": "PHYSICAL", "detected": True, "segment_ids": [target], "detection_source": "MODEL", "filtered_reason": None}
                ],
            }
        )

        return AIAnalysisBundle(result=result, summary_evidence=bundle.summary_evidence, provider="modeling", model="fake-model")


@pytest.fixture
def calls() -> List[Dict[str, Any]]:
    return []


@pytest.fixture
def scans() -> List[Dict[str, Any]]:
    return []


@pytest.fixture
def before_confirm(monkeypatch, calls, scans) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "modeling")
    monkeypatch.setattr(settings, "ANALYZE_BEFORE_CONFIRM", True)
    monkeypatch.setattr(analysis_service, "get_ai_adapter", lambda: FakeAdapter(calls))

    def scanner(contract: Dict[str, Any]) -> Dict[str, Any]:
        scans.append(contract)
        return {"status": "DONE", "model": "roberta_test", "segments": []}

    monkeypatch.setattr(key_scan_service, "_load_scanner", lambda: scanner)


def _confirm_and_analyze(client: TestClient, headers, session_id: str) -> Dict[str, Any]:
    assert client.post(f"/api/v1/sessions/{session_id}/transcript/confirm", headers=headers).status_code == 200
    response = client.post(f"/api/v1/sessions/{session_id}/analysis", headers=headers)
    assert response.status_code == 202, response.text
    analysis = client.get(f"/api/v1/sessions/{session_id}/analysis", headers=headers)
    assert analysis.status_code == 200, analysis.text
    return analysis.json()["data"]


def _risk(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    data = analysis.get("analysis") or analysis
    return data["result"]["risk_utterances"]


def test_stt_fills_first_listen_from_full_analysis(client: TestClient, counselor_headers, session: dict, before_confirm, calls, scans) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    second = envelope["transcript"]["segments"][1]["segment_id"]
    key_scan = envelope["transcript"]["key_scan"]

    assert len(calls) == 1 and scans == []
    assert key_scan["status"] == "DONE" and key_scan["model"] == "ai_analysis" and key_scan["scanned_version"] == 1
    assert [(item["segment_id"], item["abuse_types"]) for item in key_scan["segments"]] == [(second, ["PHYSICAL"])]
    reference = key_scan["segments"][0]["legal_references"][0]
    assert (reference["item_label"], reference["excerpt"], reference["abuse_type"]) == ("제3호", "직접 신체 가해 · 근거 직접성 높음", "PHYSICAL")
    # 암호화하지 않는 key_scan 에는 원문 · 이유 글을 넣지 않는다.
    assert "가상 근거 문장" not in str(key_scan) and "가상 이유" not in str(key_scan)

    with SessionLocal() as db:
        row = db.scalar(select(Transcript).where(Transcript.version == 1))
        assert row.pre_analysis_plain is None and row.pre_analysis_enc
        assert row.pre_analysis["result"]["risk_utterances"][0]["text"] == "가상 근거 문장"


def test_confirm_without_editing_reuses_result(client: TestClient, counselor_headers, session: dict, before_confirm, calls) -> None:
    transcribed_session(client, counselor_headers, session["id"])
    analysis = _confirm_and_analyze(client, counselor_headers, session["id"])

    assert len(calls) == 1
    assert [item["subtype"] for item in _risk(analysis)] == ["직접 신체 가해"]
    # 다시 쓴 것은 2단계 경고와 감사 기록에 판 번호로 남는다(민규 #195 리뷰 3).
    assert "원문 확정 전 AI 분석(원문 1판)을 그대로 썼습니다" in " ".join((analysis.get("analysis") or analysis)["result"]["warnings"])
    with SessionLocal() as db:
        sent = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.PRE_ANALYSIS_SENT)).all()
        reused = db.scalars(select(AuditLog).where(AuditLog.action == AuditAction.PRE_ANALYSIS_REUSED)).all()
        assert len(sent) == 1 and sent[0].detail["segments"] > 0
        assert [row.detail["from_version"] for row in reused] == [1]

    # 재분석(두 번째 분석)은 새로 한다.
    response = client.post(f"/api/v1/sessions/{session['id']}/analysis", headers=counselor_headers)
    assert response.status_code == 202, response.text
    assert len(calls) == 2


def test_editing_any_line_analyzes_again(client: TestClient, counselor_headers, session: dict, before_confirm, calls, scans) -> None:
    # 근거가 아닌 줄을 고쳐도(모델이 놓친 위험 발화를 바로잡았을 수 있음) 확정 원문으로 새로 분석한다(민규 #195 리뷰 1).
    envelope = transcribed_session(client, counselor_headers, session["id"])
    first = envelope["transcript"]["segments"][0]

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript", json={"segments": [{**first, "text": "고친 가상 문장"}]}, headers=counselor_headers
    )
    assert response.status_code == 200, response.text
    # 분석으로 채운 '먼저 들어볼 곳' 은 1차 스캔으로 다시 고르지 않고 복사한다.
    assert response.json()["data"]["key_scan"]["model"] == "ai_analysis" and response.json()["data"]["key_scan"]["status"] == "DONE"
    assert scans == []

    analysis = _confirm_and_analyze(client, counselor_headers, session["id"])
    assert len(calls) == 2 and calls[1]["segments"][0]["text"] == "고친 가상 문장"
    assert not any("그대로 썼습니다" in warning for warning in (analysis.get("analysis") or analysis)["result"]["warnings"])


def test_editing_an_evidence_line_analyzes_again(client: TestClient, counselor_headers, session: dict, before_confirm, calls) -> None:
    envelope = transcribed_session(client, counselor_headers, session["id"])
    second = envelope["transcript"]["segments"][1]

    response = client.patch(
        f"/api/v1/sessions/{session['id']}/transcript", json={"segments": [{**second, "text": "근거 문장을 고침"}]}, headers=counselor_headers
    )
    assert response.status_code == 200, response.text

    _confirm_and_analyze(client, counselor_headers, session["id"])
    assert len(calls) == 2
    assert calls[1]["segments"][1]["text"] == "근거 문장을 고침"


def test_failed_pre_analysis_falls_back_to_first_scan(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls, scans) -> None:
    monkeypatch.setattr(analysis_service, "get_ai_adapter", lambda: FakeAdapter(calls, fail=True))

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert len(calls) == 1 and len(scans) == 1
    assert envelope["transcript"]["key_scan"]["model"] == "roberta_test"

    with SessionLocal() as db:
        assert db.scalar(select(Transcript.pre_analysis_enc).where(Transcript.version == 1)) is None


def test_switch_off_keeps_first_scan(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls, scans) -> None:
    monkeypatch.setattr(settings, "ANALYZE_BEFORE_CONFIRM", False)

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert calls == [] and len(scans) == 1
    assert envelope["transcript"]["key_scan"]["model"] == "roberta_test"


class NamedAdapter(FakeAdapter):
    """등록 이름을 받는 어댑터(ModelingAIAdapter 처럼)."""

    def analyze(self, transcript_payload: Dict[str, Any], known_identifiers=None) -> AIAnalysisBundle:  # type: ignore[override]
        self.names = known_identifiers
        return super().analyze(transcript_payload)


def test_unreadable_registered_names_are_not_sent(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls, scans) -> None:
    # 등록 이름을 못 읽으면(None) 확정 전 원문 전체를 보내지 않고 1차 스캔으로 돌아간다(민규 11/24).
    from app.services import personal_info_service

    monkeypatch.setattr(analysis_service, "get_ai_adapter", lambda: NamedAdapter(calls))
    monkeypatch.setattr(personal_info_service, "known_identifiers", lambda db, case_id, **kwargs: None if kwargs.get("strict") else [])

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert calls == [] and len(scans) == 1
    assert envelope["transcript"]["key_scan"]["model"] == "roberta_test"


def test_case_without_registered_names_is_not_sent(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls, scans) -> None:
    # 등록 이름이 하나도 없으면 보내지 않는다(민규 #195 리뷰 6 · 경진 11/24).
    from app.services import personal_info_service

    monkeypatch.setattr(analysis_service, "get_ai_adapter", lambda: NamedAdapter(calls))
    monkeypatch.setattr(personal_info_service, "known_identifiers", lambda db, case_id, **kwargs: [])

    envelope = transcribed_session(client, counselor_headers, session["id"])

    assert calls == [] and len(scans) == 1
    assert envelope["transcript"]["key_scan"]["model"] == "roberta_test"


def test_registered_names_and_one_letter_variants_are_masked(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls) -> None:
    from app.services import personal_info_service, pre_analysis_service

    adapter = NamedAdapter(calls)
    monkeypatch.setattr(analysis_service, "get_ai_adapter", lambda: adapter)
    monkeypatch.setattr(personal_info_service, "known_identifiers", lambda db, case_id, **kwargs: ["김수아", "수아"])
    monkeypatch.setattr(pre_analysis_service, "similar_name_variants", lambda text, names: ["김수하"])

    transcribed_session(client, counselor_headers, session["id"])

    assert len(calls) == 1 and adapter.names == ["김수아", "김수하", "수아"]


def test_similar_name_variants() -> None:
    from app.services.pre_analysis_service import similar_name_variants

    text = "김수하가 왔어요. 김수하 학생. 김민수도 왔고 이수아도 있어요. 김수아는 집에."
    assert similar_name_variants(text, ["김수아", "수아"]) == ["김수하"]
    # 일반 낱말은 가리지 않는다(민규 #195 리뷰 5): 첫소리만 다른 것 · 낱말 경계 · 조사가 된 꼴.
    assert similar_name_variants("하지만 괜찮아요. 고민이 있어요. 오늘하지만", ["하지원", "고민지"]) == []


def test_similar_name_variants_missed_cases_from_review() -> None:
    """민규 #195 리뷰(79d1d466): 고치기 전에는 가렸는데 안 가리게 된 표기(모두 가상 이름)."""

    from app.services.pre_analysis_service import similar_name_variants

    # (가) 틀린 표기의 끝 글자가 조사 꼴 — 이름 앞 두 글자가 흔한 낱말이 아니면 이름으로 본다.
    assert similar_name_variants("김수아가 왔어요. 김수아 학생이", ["김수하"]) == ["김수아"]
    assert similar_name_variants("최유아가 왔어", ["최유하"]) == ["최유아"]
    # (나) 뒤에 붙는 말 · 앞에 붙여 쓴 '우리'.
    for text in ("김수하와", "김수하라고", "김수하예요", "김수하하고", "김수하만", "김수하네", "김수하처럼", "김수하입니다", "우리김수하가"):
        assert similar_name_variants(text, ["김수아"]) == ["김수하"], text
    # (다) 모음 · 받침 하나만 다른 표기.
    pairs = {"박서윤": "박서연", "김민준": "김민중", "이예린": "이예림", "정하윤": "정하율"}
    for name, heard in pairs.items():
        assert similar_name_variants(f"{heard}이 왔어요", [name]) == [heard], name
    # 흔한 낱말 + 조사 · 두 군데 이상 다른 낱말은 그대로 둔다.
    assert similar_name_variants("고민이 있어요. 사람이 많아. 하지만", ["고민지", "사람지", "하지원"]) == []


def test_switch_off_does_not_reuse_saved_result(client: TestClient, counselor_headers, session: dict, before_confirm, monkeypatch, calls) -> None:
    transcribed_session(client, counselor_headers, session["id"])
    monkeypatch.setattr(settings, "ANALYZE_BEFORE_CONFIRM", False)

    _confirm_and_analyze(client, counselor_headers, session["id"])

    assert len(calls) == 2


def test_unreadable_saved_result_analyzes_again(client: TestClient, counselor_headers, session: dict, before_confirm, calls) -> None:
    # 저장한 값을 풀지 못하면 AI_FAILED 를 되풀이하지 않고 새로 분석한다(민규 #195 리뷰 4).
    transcribed_session(client, counselor_headers, session["id"])
    with SessionLocal() as db:
        row = db.scalar(select(Transcript).where(Transcript.version == 1))
        row.pre_analysis_enc = "v1.broken.value"
        db.commit()

    analysis = _confirm_and_analyze(client, counselor_headers, session["id"])

    assert len(calls) == 2 and (analysis.get("analysis") or analysis)["status"] == "COMPLETED"
