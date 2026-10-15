"""
상담일지(note) 형식 텍스트를 1차/2차 모델에 그대로 통과시켜 보는
평가용 테스트 웹.

1차 모델은 원래 qa/child_only 태깅([COUNSELOR]/[CHILD])에 맞춰 학습됐다.
여기서는 태깅 없이 상담일지 원문을 그대로 넣어서, 실제 상담일지 문체에서도
v3가 학대유형을 잡아내는지 확인한다 — 프로덕션 경로가 아니라 평가용이다.

datasets/counseling_note_v1_sample_final.csv에 있는, LLM으로 생성한
상담일지 샘플(정답 라벨 포함)을 그대로 불러와서 비교해볼 수 있다.
"""

import csv
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

from ai.modeling.abuse.infer_abuse_v3_adapter import _engine
from ai.modeling.abuse.infer_abuse_qa_v3 import (
    predict_abuse as predict_abuse_raw,
)
from ai.modeling.abuse.second_stage_llm import analyze_subtypes


# ============================================================
# 1. 샘플 데이터 로드
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SAMPLE_CSV_PATH = (
    BASE_DIR
    / "datasets"
    / "counseling_note_v1_sample_final.csv"
)


def load_sample_cases():
    if not SAMPLE_CSV_PATH.exists():
        return []

    with SAMPLE_CSV_PATH.open(
        encoding="utf-8-sig",
    ) as f:
        return list(
            csv.DictReader(f)
        )


SAMPLE_CASES = load_sample_cases()

SAMPLE_CASES_BY_ID = {
    case["case_id"]: case
    for case in SAMPLE_CASES
}


# ============================================================
# 2. FastAPI 앱
# ============================================================

app = FastAPI(
    title="I-SPOT 상담일지 평가 테스트",
)


# ============================================================
# 3. 1차 판정 실행 (raw, 태깅 없이)
# ============================================================

def run_major_type_eval(
    text: str,
):
    raw_result = predict_abuse_raw(
        _engine,
        text,
    )

    return raw_result


# ============================================================
# 4. HTML 렌더링
# ============================================================

def build_page(
    case_id="",
    text="",
    reference_label=None,
    reference_crisis=None,
    major_result=None,
    subtype_result=None,
    error=None,
):
    options_html = "".join(
        f'<option value="{escape(case["case_id"])}" '
        f'{"selected" if case["case_id"] == case_id else ""}>'
        f'{escape(case["case_id"])} '
        f'(만 {escape(case["age"])}세, 정답: '
        f'{escape(case["reference_abuse_label"])})'
        f'</option>'
        for case in SAMPLE_CASES
    )

    result_html = ""

    if error:
        result_html = f"""
        <section class="panel error-panel">
            <h2>오류</h2>
            <pre>{escape(str(error))}</pre>
        </section>
        """

    elif major_result:
        reference_html = ""

        if reference_label is not None:
            reference_html = f"""
            <div class="reference-box">
                <b>정답 라벨(reference_abuse_label)</b>: {escape(reference_label)}
                &nbsp;|&nbsp;
                <b>위기단계(reference_crisis_level)</b>: {escape(reference_crisis or "")}
            </div>
            """

        rows = []

        for label, prediction in major_result.items():
            detected = prediction.get(
                "detected",
                False,
            )

            probability = prediction.get(
                "probability",
                0,
            )

            match_html = ""

            if reference_label is not None:
                is_reference_positive = (
                    label in reference_label
                )

                is_match = (
                    detected == is_reference_positive
                )

                match_html = (
                    '<span class="match-ok">일치</span>'
                    if is_match
                    else '<span class="match-fail">불일치</span>'
                )

            row_class = (
                "detected"
                if detected
                else ""
            )

            rows.append(
                f"""
                <tr class="{row_class}">
                    <td>{escape(label)}</td>
                    <td>{probability:.3f}</td>
                    <td>{"탐지" if detected else "미탐지"}</td>
                    <td>{match_html}</td>
                </tr>
                """
            )

        subtype_html = ""

        if subtype_result:
            results = subtype_result.get(
                "results",
                [],
            )

            if not results:
                subtype_html = f"""
                <div class="empty">
                    {escape(subtype_result.get("note", "탐지된 세부 위험신호가 없습니다."))}
                </div>
                """
            else:
                blocks = []

                for major in results:
                    for subtype in major.get(
                        "subtypes",
                        [],
                    ):
                        evidences = "".join(
                            f'<div>"{escape(e.get("evidence", ""))}"'
                            f' <span class="meta">({e.get("evidence_match_method", "")})</span></div>'
                            for e in subtype.get(
                                "evidences",
                                [],
                            )
                        )

                        blocks.append(
                            f"""
                            <div class="subtype-block">
                                <b>{escape(major.get("major_type", ""))}</b>
                                → {escape(subtype.get("type", ""))}
                                <div class="evidence-box">{evidences}</div>
                            </div>
                            """
                        )

                subtype_html = "".join(blocks)

        result_html = f"""
        <section class="panel">
            <h2>입력 텍스트 (상담일지 원문, 태깅 없음)</h2>
            <div class="text-box">{escape(text)}</div>
        </section>

        <section class="panel">
            <h2>1차 RoBERTa v3 판정 (raw, note 문체 그대로 입력)</h2>
            {reference_html}
            <table>
                <tr><th>학대유형</th><th>확률</th><th>판정</th><th>정답과 비교</th></tr>
                {''.join(rows)}
            </table>
        </section>

        <section class="panel">
            <h2>2차 세부유형 (1차에서 탐지된 유형만)</h2>
            {subtype_html}
        </section>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>I-SPOT 상담일지 평가 테스트</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0; background: #f5f7fb;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #1f2937;
            }}
            .container {{ max-width: 1000px; margin: 40px auto; padding: 0 24px 80px; }}
            .header p {{ color: #6b7280; }}
            .panel {{
                background: white; border: 1px solid #e5e7eb; border-radius: 16px;
                padding: 24px; margin-bottom: 20px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.04);
            }}
            .panel h2 {{ margin-top: 0; font-size: 19px; }}
            select {{ width: 100%; padding: 10px; border-radius: 8px; border: 1px solid #d1d5db; margin-bottom: 12px; }}
            textarea {{
                width: 100%; min-height: 180px; resize: vertical;
                border: 1px solid #d1d5db; border-radius: 12px; padding: 14px;
                font-size: 14px; line-height: 1.6;
            }}
            button {{
                margin-top: 14px; border: none; border-radius: 10px; padding: 12px 22px;
                font-size: 15px; font-weight: 600; cursor: pointer;
                background: #111827; color: white;
            }}
            button:hover {{ opacity: 0.9; }}
            .text-box {{
                white-space: pre-wrap; line-height: 1.7; background: #f9fafb;
                padding: 16px; border-radius: 10px; font-size: 14px;
            }}
            .reference-box {{
                background: #eff6ff; border: 1px solid #93c5fd; border-radius: 8px;
                padding: 10px 14px; margin-bottom: 14px; font-size: 14px;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }}
            tr.detected {{ background: #fef2f2; }}
            .match-ok {{ color: #15803d; font-weight: 700; }}
            .match-fail {{ color: #b91c1c; font-weight: 700; }}
            .subtype-block {{ border-top: 1px solid #e5e7eb; padding: 10px 0; }}
            .subtype-block:first-child {{ border-top: none; }}
            .evidence-box {{ font-size: 13px; color: #374151; margin-top: 4px; }}
            .meta {{ color: #9ca3af; }}
            .empty {{ color: #6b7280; }}
            .error-panel {{ border-color: #fca5a5; background: #fef2f2; }}
            pre {{ white-space: pre-wrap; word-break: break-word; }}
            .note {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>I-SPOT 상담일지(note) 평가 테스트</h1>
                <p>
                    상담일지 문체 텍스트를 태깅 없이 1차/2차 모델에 그대로 넣어
                    v3가 실제로 얼마나 잘 탐지하는지 확인하는 평가용 도구입니다.
                    프로덕션 경로가 아닙니다.
                </p>
            </div>

            <section class="panel">
                <form method="post" action="/analyze">
                    <h2>샘플 케이스 선택 (또는 아래 직접 입력)</h2>
                    <select name="case_id" onchange="this.form.text.value=''">
                        <option value="">-- 직접 입력한 텍스트 사용 --</option>
                        {options_html}
                    </select>

                    <textarea name="text" placeholder="샘플을 고르거나 상담일지 텍스트를 직접 붙여넣으세요.">{escape(text)}</textarea>

                    <button type="submit">분석하기</button>
                </form>
            </section>

            {result_html}
        </div>
    </body>
    </html>
    """


# ============================================================
# 5. Routes
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def index():
    return build_page()


@app.post(
    "/analyze",
    response_class=HTMLResponse,
)
def analyze(
    case_id: str = Form(""),
    text: str = Form(""),
):
    try:
        reference_label = None
        reference_crisis = None

        if case_id and case_id in SAMPLE_CASES_BY_ID:
            case = SAMPLE_CASES_BY_ID[case_id]
            text = case["full_session_note"]
            reference_label = case["reference_abuse_label"]
            reference_crisis = case["reference_crisis_level"]

        if not text.strip():
            raise ValueError(
                "분석할 텍스트가 없습니다. 샘플을 고르거나 텍스트를 입력하세요."
            )

        major_result = run_major_type_eval(
            text
        )

        detected_major_types = [
            label
            for label, prediction in major_result.items()
            if prediction.get(
                "detected",
                False,
            )
        ]

        if detected_major_types:
            subtype_result = analyze_subtypes(
                text=text,
                major_types=detected_major_types,
            )
        else:
            subtype_result = {
                "results": [],
                "note": "탐지된 대분류 없음",
            }

        return build_page(
            case_id=case_id,
            text=text,
            reference_label=reference_label,
            reference_crisis=reference_crisis,
            major_result=major_result,
            subtype_result=subtype_result,
        )

    except Exception as exc:
        return build_page(
            case_id=case_id,
            text=text,
            error=exc,
        )


# ============================================================
# 6. 실행
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7865,
    )
