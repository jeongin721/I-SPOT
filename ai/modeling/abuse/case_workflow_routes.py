"""
사례관리 승인 워크플로 공용 라우트.

텍스트(test_pipeline_web.py) / PDF(test_pdf_web.py) / 음성
(test_audio_pipeline_web.py) 테스트 웹이 모두 같은 승인·사례조회·
문서출력 흐름을 쓰므로, 라우트 자체를 여기 한 곳에 모아두고
`register_case_workflow_routes(app)`로 등록해서 재사용한다.
"""

import json
from html import escape
from typing import List

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_comparison import (
    compare_case_sessions,
)


# ============================================================
# 승인 완료 페이지
# ============================================================

def build_confirmation_page_html(
    case_id: str,
    session_id: int,
    edit_log: list,
) -> str:
    if edit_log:
        edit_items = "".join(
            f"<li>{escape(entry['field'])} — AI 초안에서 수정됨</li>"
            for entry in edit_log
        )
    else:
        edit_items = (
            "<li>AI 초안 그대로 승인됨 (수정 없음)</li>"
        )

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>승인 완료</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: #f5f7fb;
                margin: 0;
                padding: 40px 24px;
                color: #1f2937;
            }}
            .panel {{
                max-width: 640px;
                margin: 0 auto;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 28px;
            }}
            ul {{
                padding-left: 20px;
            }}
            .confirm-links a {{
                display: inline-block;
                margin-top: 16px;
                margin-right: 12px;
                padding: 10px 18px;
                border-radius: 10px;
                background: #111827;
                color: white;
                text-decoration: none;
                font-size: 14px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="panel">
            <h1>승인 완료</h1>
            <p>사례 <b>{escape(case_id)}</b>의 회기 #{session_id}가 저장됐습니다.</p>
            <ul>{edit_items}</ul>
            <div class="confirm-links">
                <a href="/cases/{escape(case_id, quote=True)}">이 사례 회기 목록</a>
                <a href="/sessions/{session_id}/document">문서로 보기 / 인쇄</a>
                <a href="/">새 분석 시작</a>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================
# 라우트 등록
# ============================================================

def register_case_workflow_routes(app: FastAPI) -> None:
    """
    /approve, /cases, /cases/{case_id}, /sessions/{session_id}/document
    라우트를 주어진 FastAPI 앱에 등록한다.
    """

    @app.post(
        "/approve",
        response_class=HTMLResponse,
    )
    def approve(
        session_id: int = Form(...),
        counseling_summary: str = Form(""),
        counseling_note: str = Form(""),
        problem_history_draft: str = Form(""),
        counselor_opinion_draft: str = Form(""),
        checked_items: List[str] = Form([]),
    ):
        session = case_store.get_session(
            session_id
        )

        if session is None:
            return HTMLResponse(
                "<h1>세션을 찾을 수 없습니다.</h1>",
                status_code=404,
            )

        ai_checklist = json.loads(
            session["ai_checklist"] or "{}"
        )

        checked_set = set(
            checked_items
        )

        final_checklist_items = []

        for item in ai_checklist.get(
            "checklist",
            [],
        ):
            key = f"{item['category']}::{item['item']}"

            final_checklist_items.append(
                {
                    **item,
                    "suggested": key in checked_set,
                }
            )

        final_checklist = {
            **ai_checklist,
            "checklist": final_checklist_items,
            "problem_history_draft": problem_history_draft,
            "counselor_opinion_draft": counselor_opinion_draft,
        }

        edit_log = case_store.approve_session(
            session_id=session_id,
            final_counseling_summary=counseling_summary,
            final_counseling_note=counseling_note,
            final_checklist=final_checklist,
        )

        return HTMLResponse(
            build_confirmation_page_html(
                case_id=session["case_id"],
                session_id=session_id,
                edit_log=edit_log,
            )
        )

    @app.get(
        "/cases",
        response_class=HTMLResponse,
    )
    def cases_list():
        cases = case_store.list_cases()

        rows = "".join(
            f"""
            <tr>
                <td><a href="/cases/{escape(c['case_id'], quote=True)}">{escape(c['case_id'])}</a></td>
                <td>{c['session_count']}</td>
                <td>{escape(c['last_session_at'] or '-')}</td>
            </tr>
            """
            for c in cases
        )

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <title>사례 목록</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        background: #f5f7fb; margin: 0; padding: 40px 24px; color: #1f2937; }}
                    .panel {{ max-width: 800px; margin: 0 auto; background: white;
                        border: 1px solid #e5e7eb; border-radius: 16px; padding: 28px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
                    a {{ color: #2563eb; text-decoration: none; font-weight: 600; }}
                </style>
            </head>
            <body>
                <div class="panel">
                    <h1>사례 목록</h1>
                    <table>
                        <tr><th>사례 ID</th><th>회기 수</th><th>최근 회기</th></tr>
                        {rows if rows else '<tr><td colspan="3">저장된 사례가 없습니다.</td></tr>'}
                    </table>
                    <p><a href="/">새 분석 시작</a></p>
                </div>
            </body>
            </html>
            """
        )

    @app.get(
        "/cases/{case_id}",
        response_class=HTMLResponse,
    )
    def case_detail(
        case_id: str,
    ):
        sessions = case_store.list_sessions_for_case(
            case_id
        )

        comparisons = {
            entry["session_id"]: entry
            for entry in compare_case_sessions(
                case_id
            )
        }

        rows = []

        for s in sessions:
            major_types = json.loads(
                s["major_types"] or "{}"
            )

            detected = [
                label
                for label, prediction in major_types.items()
                if prediction.get("detected")
            ]

            status_class = s["status"]

            status_label = (
                "승인됨"
                if s["status"] == "approved"
                else "초안"
            )

            document_link = (
                f'<a href="/sessions/{s["session_id"]}/document">문서보기</a>'
                if s["status"] == "approved"
                else "(미승인)"
            )

            comparison = comparisons.get(
                s["session_id"]
            )

            if comparison is None:
                risk_factor_html = (
                    "-"
                    if s["status"] == "approved"
                    else "(미승인)"
                )
            else:
                parts = []

                if comparison["new_items"]:
                    items_str = ", ".join(
                        f"{cat}::{item}"
                        for cat, item in comparison["new_items"]
                    )
                    parts.append(
                        f'<div class="rf-new">+ 신규: {escape(items_str)}</div>'
                    )

                if comparison["recurring_items"]:
                    items_str = ", ".join(
                        f"{cat}::{item}"
                        for cat, item in comparison["recurring_items"]
                    )
                    parts.append(
                        f'<div class="rf-recurring">= 반복: {escape(items_str)}</div>'
                    )

                if comparison["resolved_items"]:
                    items_str = ", ".join(
                        f"{cat}::{item}"
                        for cat, item in comparison["resolved_items"]
                    )
                    parts.append(
                        f'<div class="rf-resolved">- 해소: {escape(items_str)}</div>'
                    )

                risk_factor_html = (
                    "".join(parts)
                    if parts
                    else "변화 없음"
                )

            rows.append(
                f"""
                <tr>
                    <td>#{s['session_id']}</td>
                    <td>{escape(s['created_at'])}</td>
                    <td><span class="status-badge {status_class}">{status_label}</span></td>
                    <td>{escape(', '.join(detected)) if detected else '-'}</td>
                    <td class="risk-factor-cell">{risk_factor_html}</td>
                    <td>{document_link}</td>
                </tr>
                """
            )

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <title>{escape(case_id)} 회기 목록</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        background: #f5f7fb; margin: 0; padding: 40px 24px; color: #1f2937; }}
                    .panel {{ max-width: 1200px; margin: 0 auto; background: white;
                        border: 1px solid #e5e7eb; border-radius: 16px; padding: 28px;
                        overflow-x: auto; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb;
                        font-size: 14px; vertical-align: top; }}
                    a {{ color: #2563eb; text-decoration: none; font-weight: 600; }}
                    .status-badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
                        font-size: 12px; font-weight: 700; }}
                    .status-badge.approved {{ background: #dcfce7; color: #166534; }}
                    .status-badge.draft {{ background: #fef3c7; color: #92400e; }}
                    .risk-factor-cell {{ font-size: 12px; min-width: 220px; }}
                    .rf-new {{ color: #b91c1c; margin-bottom: 4px; }}
                    .rf-recurring {{ color: #92400e; margin-bottom: 4px; }}
                    .rf-resolved {{ color: #166534; margin-bottom: 4px; }}
                </style>
            </head>
            <body>
                <div class="panel">
                    <h1>사례 {escape(case_id)} — 회기 목록</h1>
                    <p>회기별로 나열되어 있어 이전 회기와 비교해볼 수 있습니다.
                    "Risk Factor 변화"는 직전 승인 회기 대비 체크리스트 변화입니다.</p>
                    <table>
                        <tr><th>회기</th><th>생성 시각</th><th>상태</th><th>탐지된 유형</th><th>Risk Factor 변화</th><th></th></tr>
                        {''.join(rows) if rows else '<tr><td colspan="6">회기가 없습니다.</td></tr>'}
                    </table>
                    <p><a href="/cases">전체 사례 목록</a> · <a href="/">새 분석 시작</a></p>
                </div>
            </body>
            </html>
            """
        )

    @app.get(
        "/sessions/{session_id}/document",
        response_class=HTMLResponse,
    )
    def session_document(
        session_id: int,
    ):
        session = case_store.get_session(
            session_id
        )

        if session is None:
            return HTMLResponse(
                "<h1>세션을 찾을 수 없습니다.</h1>",
                status_code=404,
            )

        if session["status"] != "approved":
            return HTMLResponse(
                f"""
                <h1>아직 승인되지 않은 회기입니다.</h1>
                <p><a href="/cases/{escape(session['case_id'], quote=True)}">뒤로</a></p>
                """
            )

        final_checklist = json.loads(
            session["final_checklist"] or "{}"
        )

        checked_items = [
            item
            for item in final_checklist.get(
                "checklist",
                [],
            )
            if item.get("suggested")
        ]

        checklist_lines = "".join(
            f"<li>[{escape(item['category'])}] {escape(item['item'])}</li>"
            for item in checked_items
        ) or "<li>해당 없음</li>"

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <title>상담 기록 문서 — {escape(session['case_id'])} #{session_id}</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        background: #f5f7fb; margin: 0; padding: 40px 24px; color: #1f2937; }}
                    .doc {{ max-width: 760px; margin: 0 auto; background: white;
                        border: 1px solid #e5e7eb; border-radius: 16px; padding: 40px; }}
                    h1 {{ font-size: 22px; border-bottom: 2px solid #111827; padding-bottom: 12px; }}
                    h2 {{ font-size: 16px; margin-top: 28px; }}
                    .meta {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
                    .text-box {{ white-space: pre-wrap; line-height: 1.75; background: #f9fafb;
                        padding: 16px; border-radius: 10px; }}
                    ul {{ padding-left: 20px; }}
                    .no-print button {{ border: none; border-radius: 10px; padding: 10px 18px;
                        background: #111827; color: white; font-size: 14px; font-weight: 600; cursor: pointer; }}
                    @media print {{
                        .no-print {{ display: none !important; }}
                        body {{ background: white; padding: 0; }}
                        .doc {{ border: none; }}
                    }}
                </style>
            </head>
            <body>
                <div class="doc">
                    <div class="no-print" style="margin-bottom: 20px;">
                        <button onclick="window.print()">인쇄 / PDF로 저장</button>
                    </div>

                    <h1>상담 기록</h1>
                    <div class="meta">
                        사례 ID: {escape(session['case_id'])} ·
                        회기 #{session_id} ·
                        승인 시각: {escape(session['approved_at'] or '')}
                    </div>

                    <h2>상담 요약</h2>
                    <div class="text-box">{escape(session['final_counseling_summary'] or '')}</div>

                    <h2>상담일지</h2>
                    <div class="text-box">{escape(session['final_counseling_note'] or '')}</div>

                    <h2>체크리스트 (상담사 확인 완료)</h2>
                    <ul>{checklist_lines}</ul>

                    <h2>문제력</h2>
                    <div class="text-box">{escape(final_checklist.get('problem_history_draft', ''))}</div>

                    <h2>상담원 소견</h2>
                    <div class="text-box">{escape(final_checklist.get('counselor_opinion_draft', ''))}</div>

                    <div class="no-print" style="margin-top: 24px;">
                        <a href="/cases/{escape(session['case_id'], quote=True)}">뒤로</a> ·
                        <a href="/sessions/{session_id}/assessment-record">사정기록지 초안 보기</a>
                    </div>
                </div>
            </body>
            </html>
            """
        )

    @app.get(
        "/sessions/{session_id}/assessment-record",
        response_class=HTMLResponse,
    )
    def session_assessment_record(
        session_id: int,
    ):
        """
        사정기록지(서식6 등) 초안 — 새로 LLM을 호출하지 않고,
        이미 저장된 final_checklist(가정상황/아동특성/안전영역/문제력/
        소견)를 서식 형태로 조립만 한다.

        신고접수일·대상아동명·가족관계 표·생육사/발달사/교육사·건강정도처럼
        AI가 원문만으로는 채울 수 없는 행정정보는 빈 칸으로 남기고
        상담사/관리자가 직접 입력하도록 표시한다.
        """

        session = case_store.get_session(
            session_id
        )

        if session is None:
            return HTMLResponse(
                "<h1>세션을 찾을 수 없습니다.</h1>",
                status_code=404,
            )

        if session["status"] != "approved":
            return HTMLResponse(
                f"""
                <h1>아직 승인되지 않은 회기입니다.</h1>
                <p><a href="/cases/{escape(session['case_id'], quote=True)}">뒤로</a></p>
                """
            )

        major_types = json.loads(
            session["major_types"] or "{}"
        )

        detected_types = [
            label
            for label, prediction in major_types.items()
            if prediction.get("detected")
        ]

        final_checklist = json.loads(
            session["final_checklist"] or "{}"
        )

        checklist_items = final_checklist.get(
            "checklist",
            [],
        )

        def _checked_list_html(
            category: str,
        ) -> str:
            items = [
                item["item"]
                for item in checklist_items
                if item.get("category") == category
                and item.get("suggested")
            ]

            if not items:
                return (
                    '<div class="blank-field">'
                    "확인된 항목 없음"
                    "</div>"
                )

            return "<ul>" + "".join(
                f"<li>{escape(item)}</li>"
                for item in items
            ) + "</ul>"

        safety_html = "".join(
            f"""
            <div class="safety-row">
                <b>[{escape(entry['category'])}] {escape(entry['item'])}</b>
                {
                    ''.join(
                        f'<div class="safety-evidence">"{escape(e.get("evidence", ""))}"</div>'
                        for e in entry.get('evidence', [])
                    )
                    if entry.get('evidence')
                    else '<div class="blank-field">관련 근거 없음</div>'
                }
            </div>
            """
            for entry in final_checklist.get(
                "safety_assessment_evidence",
                [],
            )
        ) or '<div class="blank-field">해당 없음</div>'

        environment = final_checklist.get(
            "environment_key_person"
        )

        environment_html = (
            f"{escape(environment.get('status', ''))} "
            f"({', '.join(escape(e.get('evidence', '')) for e in environment.get('evidence', []))})"
            if environment
            else '<div class="blank-field">확인 안 됨</div>'
        )

        blank = (
            '<div class="blank-field">상담사/관리자 입력 필요</div>'
        )

        return HTMLResponse(
            f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <title>사정기록지 초안 — {escape(session['case_id'])} #{session_id}</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        background: #f5f7fb; margin: 0; padding: 40px 24px; color: #1f2937; }}
                    .doc {{ max-width: 800px; margin: 0 auto; background: white;
                        border: 1px solid #e5e7eb; border-radius: 16px; padding: 40px; }}
                    h1 {{ font-size: 22px; border-bottom: 2px solid #111827; padding-bottom: 12px; }}
                    h2 {{ font-size: 15px; margin-top: 26px; background: #f3f4f6;
                        padding: 8px 12px; border-radius: 6px; }}
                    .meta {{ color: #6b7280; font-size: 13px; margin-bottom: 20px; }}
                    .text-box {{ white-space: pre-wrap; line-height: 1.75; background: #f9fafb;
                        padding: 16px; border-radius: 10px; }}
                    .blank-field {{ border: 1px dashed #d1d5db; border-radius: 8px;
                        padding: 10px 12px; color: #9ca3af; font-size: 13px; }}
                    ul {{ padding-left: 20px; margin: 6px 0; }}
                    .safety-row {{ margin-bottom: 10px; font-size: 13px; }}
                    .safety-evidence {{ color: #374151; margin-top: 2px; margin-left: 8px; }}
                    .ai-banner {{ background: #eff6ff; border: 1px solid #93c5fd; color: #1e3a8a;
                        padding: 10px 14px; border-radius: 8px; font-size: 13px; font-weight: 600;
                        margin-bottom: 18px; }}
                    .no-print button {{ border: none; border-radius: 10px; padding: 10px 18px;
                        background: #111827; color: white; font-size: 14px; font-weight: 600; cursor: pointer; }}
                    @media print {{
                        .no-print {{ display: none !important; }}
                        body {{ background: white; padding: 0; }}
                        .doc {{ border: none; }}
                    }}
                </style>
            </head>
            <body>
                <div class="doc">
                    <div class="no-print" style="margin-bottom: 20px;">
                        <button onclick="window.print()">인쇄 / PDF로 저장</button>
                    </div>

                    <h1>사정기록지 초안</h1>
                    <div class="meta">
                        사례 ID: {escape(session['case_id'])} ·
                        회기 #{session_id} ·
                        승인 시각: {escape(session['approved_at'] or '')}
                    </div>

                    <div class="ai-banner">
                        AI가 상담 내용에서 확인 가능한 항목만 초안으로 채웠습니다.
                        신고접수일·대상아동명·가족관계·생육사/발달사/교육사·건강정도·
                        안전영역 등급 등 상담사/관리자가 직접 입력·판단해야 하는 항목은
                        빈 칸으로 남겨뒀습니다.
                    </div>

                    <h2>학대유형</h2>
                    <div class="text-box">
                        {escape(', '.join(detected_types)) if detected_types else '탐지된 유형 없음'}
                    </div>

                    <h2>대상아동명 / 생년월일 / 신고접수일</h2>
                    {blank}

                    <h2>가족관계</h2>
                    {blank}

                    <h2>가정상황</h2>
                    {_checked_list_html("가정상황")}

                    <h2>아동 특성</h2>
                    {_checked_list_html("아동 특성")}

                    <h2>생육사 / 발달사 / 교육사</h2>
                    {blank}

                    <h2>건강정도</h2>
                    {blank}

                    <h2>안전영역 관련 근거 (등급은 상담사가 직접 판단)</h2>
                    {safety_html}

                    <h2>환경 — 신뢰할 만한 주위 사람</h2>
                    <div class="text-box">{environment_html}</div>

                    <h2>문제력</h2>
                    <div class="text-box">{escape(final_checklist.get('problem_history_draft', ''))}</div>

                    <h2>대상자 태도 및 관찰내용 / 상담원 소견</h2>
                    <div class="text-box">{escape(final_checklist.get('counselor_opinion_draft', ''))}</div>

                    <h2>사정결과 / 슈퍼비전</h2>
                    {blank}

                    <div class="no-print" style="margin-top: 24px;">
                        <a href="/cases/{escape(session['case_id'], quote=True)}">뒤로</a> ·
                        <a href="/sessions/{session_id}/document">상담 기록 문서로 보기</a>
                    </div>
                </div>
            </body>
            </html>
            """
        )
