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

            rows.append(
                f"""
                <tr>
                    <td>#{s['session_id']}</td>
                    <td>{escape(s['created_at'])}</td>
                    <td><span class="status-badge {status_class}">{status_label}</span></td>
                    <td>{escape(', '.join(detected)) if detected else '-'}</td>
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
                    .panel {{ max-width: 900px; margin: 0 auto; background: white;
                        border: 1px solid #e5e7eb; border-radius: 16px; padding: 28px; }}
                    table {{ width: 100%; border-collapse: collapse; }}
                    th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
                    a {{ color: #2563eb; text-decoration: none; font-weight: 600; }}
                    .status-badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px;
                        font-size: 12px; font-weight: 700; }}
                    .status-badge.approved {{ background: #dcfce7; color: #166534; }}
                    .status-badge.draft {{ background: #fef3c7; color: #92400e; }}
                </style>
            </head>
            <body>
                <div class="panel">
                    <h1>사례 {escape(case_id)} — 회기 목록</h1>
                    <p>회기별로 나열되어 있어 이전 회기와 비교해볼 수 있습니다.</p>
                    <table>
                        <tr><th>회기</th><th>생성 시각</th><th>상태</th><th>탐지된 유형</th><th></th></tr>
                        {''.join(rows) if rows else '<tr><td colspan="5">회기가 없습니다.</td></tr>'}
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
                        <a href="/cases/{escape(session['case_id'], quote=True)}">뒤로</a>
                    </div>
                </div>
            </body>
            </html>
            """
        )
