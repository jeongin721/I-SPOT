"""
OpenAI API 없이 사례관리 승인 워크플로(승인→저장→사례조회→문서출력)만
테스트하는 간단한 웹.

실제 1차/2차/LLM 분석은 전혀 호출하지 않고, 그 자리에 가짜(mock)
analysis 데이터를 채워서 바로 승인 화면으로 넘어간다.
API 크레딧이 없을 때 다운스트림(case_store, case_workflow_routes)
동작만 확인하는 용도다.
"""

from html import escape

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

from ai.modeling.abuse import case_store
from ai.modeling.abuse.case_workflow_routes import (
    register_case_workflow_routes,
)
from ai.modeling.abuse.test_pipeline_web import (
    build_major_types_html,
    build_subtypes_html,
    build_approval_form_html,
)


ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]


# ============================================================
# 1. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT 사례관리 단계 테스트 (Mock)",
)

register_case_workflow_routes(
    app
)


# ============================================================
# 2. 가짜 분석 결과 생성
# ============================================================

def build_mock_analysis(
    detected_label: str,
) -> dict:
    major_types = {
        label: {
            "detected": label == detected_label
        }
        for label in ABUSE_LABELS
    }

    if detected_label == "해당없음":
        subtype_analysis = {
            "results": [],
            "note": "탐지된 대분류 없음",
        }
    else:
        subtype_analysis = {
            "results": [
                {
                    "major_type": detected_label,
                    "subtypes": [
                        {
                            "type": "예시 세부유형",
                            "evidences": [
                                {
                                    "evidence": "[테스트 근거] 예시 발화입니다.",
                                    "evidence_verified": True,
                                    "evidence_match_method": "exact",
                                    "matched_evidence": "[테스트 근거] 예시 발화입니다.",
                                    "evidence_strength": "높음",
                                    "action": "예시 행위",
                                    "instrument": None,
                                    "target_body_part": None,
                                    "needs_review": False,
                                }
                            ],
                            "needs_review": False,
                        }
                    ],
                }
            ],
            "model": "mock",
        }

    checklist = []

    checklist_candidates = {
        "가정상황": [
            "배우자폭력",
            "경제적어려움",
            "부부및가족갈등",
        ],
        "아동 특성": [
            "불안",
            "우울",
            "학교부적응",
        ],
    }

    suggested_items = {
        "배우자폭력",
        "불안",
    }

    for category, items in checklist_candidates.items():
        for item in items:
            suggested = item in suggested_items

            evidence = (
                [
                    {
                        "evidence": f"[테스트 근거] {item} 관련 예시 발화",
                        "evidence_verified": True,
                        "evidence_match_method": "exact",
                        "matched_evidence": f"[테스트 근거] {item} 관련 예시 발화",
                    }
                ]
                if suggested
                else []
            )

            checklist.append(
                {
                    "category": category,
                    "item": item,
                    "suggested": suggested,
                    "evidence": evidence,
                }
            )

    checklist_draft = {
        "checklist": checklist,
        "safety_assessment_evidence": [
            {
                "category": "피해아동",
                "item": "아동의 위험상황 인지 및 대처능력",
                "evidence": [
                    {
                        "evidence": "[테스트 근거] 무섭다고 진술함",
                        "evidence_verified": True,
                        "evidence_match_method": "exact",
                        "matched_evidence": "[테스트 근거] 무섭다고 진술함",
                    }
                ],
            },
        ],
        "environment_key_person": {
            "item": "조부모, 친구, 이웃 등 신뢰할만한 주위 사람(Key Person)",
            "status": "있음",
            "evidence": [
                {
                    "evidence": "[테스트 근거] 할머니에게 이야기함",
                    "evidence_verified": True,
                    "evidence_match_method": "exact",
                    "matched_evidence": "[테스트 근거] 할머니에게 이야기함",
                }
            ],
        },
        "problem_history_draft": (
            "[테스트용 문제력 초안] 실제 분석이 아니라 "
            "승인 워크플로 테스트를 위한 예시 텍스트입니다."
        ),
        "counselor_opinion_draft": (
            "[테스트용 상담원 소견 초안] 이 내용도 마찬가지로 "
            "테스트 예시입니다."
        ),
    }

    return {
        "major_types": major_types,
        "detected_major_types": (
            [detected_label]
            if detected_label != "해당없음"
            else []
        ),
        "subtype_analysis": subtype_analysis,
        "counseling_summary": (
            "[테스트용 상담 요약] 실제 LLM 호출 없이 만든 예시 텍스트입니다."
        ),
        "counseling_note": (
            "[테스트용 상담일지] 실제 LLM 호출 없이 만든 예시 텍스트입니다."
        ),
        "counseling_record_model": "mock",
        "checklist_draft": checklist_draft,
    }


# ============================================================
# 3. Routes
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def index():
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>사례관리 단계 테스트 (Mock)</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: #f5f7fb;
                margin: 0;
                padding: 40px 24px;
                color: #1f2937;
            }
            .panel {
                max-width: 640px;
                margin: 0 auto;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 28px;
            }
            label {
                display: block;
                font-weight: 600;
                margin-bottom: 6px;
                margin-top: 14px;
            }
            input, select {
                width: 100%;
                padding: 12px 14px;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                font-size: 14px;
            }
            button {
                margin-top: 20px;
                border: none;
                border-radius: 10px;
                padding: 12px 22px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                background: #111827;
                color: white;
            }
            .warning {
                background: #fffbeb;
                border: 1px solid #fcd34d;
                color: #92400e;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 13px;
                margin-bottom: 12px;
            }
            a { color: #2563eb; }
        </style>
    </head>
    <body>
        <div class="panel">
            <h1>사례관리 단계 테스트 (Mock)</h1>

            <div class="warning">
                OpenAI API 크레딧 소진 중이라 실제 1차/2차/LLM 분석은
                호출하지 않습니다. 아래에서 만드는 결과는 전부 가짜
                데이터이며, 승인 → 저장 → 사례조회 → 문서출력 단계만
                확인하는 용도입니다.
            </div>

            <form method="post" action="/mock-analyze">
                <label>사례 ID</label>
                <input
                    type="text"
                    name="case_id"
                    placeholder="예: CASE-MOCK-001"
                    required
                >

                <label>가짜로 탐지시킬 학대유형</label>
                <select name="detected_label">
                    <option value="신체학대">신체학대</option>
                    <option value="정서학대">정서학대</option>
                    <option value="성학대">성학대</option>
                    <option value="방임">방임</option>
                    <option value="해당없음">해당없음 (탐지 없음)</option>
                </select>

                <button type="submit">가짜 분석 결과 생성</button>
            </form>

            <p style="margin-top: 20px;">
                <a href="/cases">저장된 사례 목록 보기</a>
            </p>
        </div>
    </body>
    </html>
    """


@app.post(
    "/mock-analyze",
    response_class=HTMLResponse,
)
def mock_analyze(
    case_id: str = Form(...),
    detected_label: str = Form(...),
):
    result = build_mock_analysis(
        detected_label
    )

    session_id = case_store.save_draft_session(
        case_id=case_id,
        input_mode="mock",
        source_type="mock",
        raw_text="(테스트용 가짜 데이터 — 실제 상담 원문 없음)",
        analysis=result,
    )

    major_html = build_major_types_html(
        result["major_types"]
    )

    subtype_html = build_subtypes_html(
        result["subtype_analysis"]
    )

    approval_html = build_approval_form_html(
        session_id,
        result,
    )

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>가짜 분석 결과 — 승인 테스트</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                background: #f5f7fb;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #1f2937;
            }}
            .container {{
                max-width: 1100px;
                margin: 40px auto;
                padding: 0 24px 80px;
            }}
            .header {{ margin-bottom: 24px; }}
            .header p {{ margin: 0; color: #6b7280; }}
            .panel {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 20px;
                box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
            }}
            .panel h2 {{ margin-top: 0; font-size: 20px; }}
            textarea {{
                width: 100%;
                min-height: 140px;
                resize: vertical;
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.6;
            }}
            textarea.editable {{
                background: white;
                border-color: #93c5fd;
            }}
            button {{
                margin-top: 16px;
                border: none;
                border-radius: 10px;
                padding: 12px 22px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                background: #111827;
                color: white;
            }}
            .major-grid {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 12px;
            }}
            .major-card {{
                padding: 20px 14px;
                border-radius: 12px;
                border: 1px solid #d1d5db;
                text-align: center;
                background: #f9fafb;
                color: #6b7280;
                font-weight: 700;
            }}
            .major-card.detected {{
                background: #fee2e2;
                border-color: #f87171;
                color: #991b1b;
            }}
            .subtype-block {{
                border-top: 1px solid #e5e7eb;
                padding-top: 18px;
                margin-top: 18px;
            }}
            .subtype-block:first-child {{
                border-top: none; padding-top: 0; margin-top: 0;
            }}
            .subtype-title {{ font-size: 17px; font-weight: 700; margin-bottom: 10px; }}
            .major-label {{
                display: inline-block; margin-bottom: 12px; padding: 6px 10px;
                border-radius: 8px; background: #eef2ff; color: #3730a3; font-weight: 700;
            }}
            .evidence {{
                background: #f9fafb; border-left: 4px solid #9ca3af;
                padding: 12px 14px; margin-top: 10px; border-radius: 8px;
            }}
            .evidence-quote {{ font-weight: 600; margin-bottom: 8px; }}
            .meta {{ font-size: 13px; color: #6b7280; line-height: 1.6; }}
            .empty {{ color: #6b7280; }}
            .ai-banner {{
                background: #eff6ff; border: 1px solid #93c5fd; color: #1e3a8a;
                padding: 10px 14px; border-radius: 8px; font-size: 13px;
                font-weight: 600; margin-bottom: 18px;
            }}
            .checklist-category {{ font-size: 15px; font-weight: 700; margin: 18px 0 10px; }}
            .checklist-category:first-child {{ margin-top: 0; }}
            .checklist-edit-grid {{
                display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;
            }}
            .checklist-edit-item {{
                display: inline-flex; flex-direction: column;
                border: 1px solid #d1d5db; border-radius: 10px; padding: 8px 12px;
                font-size: 13px; background: #f9fafb; cursor: pointer;
            }}
            .checklist-edit-item.has-evidence {{
                border-color: #f87171; background: #fee2e2;
            }}
            .checklist-edit-item input[type="checkbox"] {{ margin-right: 6px; }}
            .checklist-edit-item .checklist-evidence-box {{ margin: 6px 0 0; background: white; }}
            .checklist-evidence-box {{
                margin: 0 14px 10px; padding: 10px 12px; background: white;
                border-radius: 8px; font-size: 13px; color: #374151; line-height: 1.6;
            }}
            .checklist-evidence-box div {{ margin-bottom: 4px; }}
            .safety-item {{ border-top: 1px solid #e5e7eb; padding: 10px 0; }}
            .safety-item:first-child {{ border-top: none; }}
            .safety-item-title {{ font-weight: 600; margin-bottom: 4px; }}
            .safety-item-evidence {{
                font-size: 13px; color: #374151; background: #f9fafb;
                border-radius: 8px; padding: 8px 12px; margin-top: 4px;
            }}
            .safety-item-empty {{ font-size: 13px; color: #9ca3af; }}
            @media (max-width: 760px) {{
                .major-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>가짜 분석 결과 — 승인 테스트</h1>
                <p>사례 ID: {escape(case_id)} · 아래 내용은 전부 테스트용 가짜 데이터입니다.</p>
            </div>

            <section class="panel">
                <h2>1차 학대 위험신호 (가짜)</h2>
                {major_html}
            </section>

            <section class="panel">
                <h2>2차 세부 위험신호 (가짜)</h2>
                {subtype_html}
            </section>

            {approval_html}
        </div>
    </body>
    </html>
    """


# ============================================================
# 4. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7867,
    )
