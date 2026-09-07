"""
A-only v2 멀티라벨 모델의 학대 관련 신호와 Phrase Occlusion 근거 표현을 웹에서 확인한다.

FastAPI 기반 테스트 페이지에서 상담 텍스트를 입력받아 4개 유형의 예측 확률과
모델 예측에 기여한 주요 표현을 함께 표시한다.
"""

# ============================================================
# XAI 표시 설정
# ============================================================

# 최종 탐지 threshold를 넘지 않더라도
# 이 확률 이상이면 모델이 어떤 표현에 반응했는지 표시
EVIDENCE_DISPLAY_THRESHOLD = 0.20

# ============================================================
# 1. Import
# ============================================================

import html

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

from ai.modeling.abuse.infer_abuse import (
    LABEL_NAMES,
    predict_abuse,
)

from ai.modeling.abuse.explain_abuse import (
    explain_abuse,
)


# ============================================================
# 2. FastAPI 앱 생성
# ============================================================

app = FastAPI(
    title="I-SPOT Abuse Signal Test"
)


# ============================================================
# 3. 화면 스타일
# ============================================================

STYLE = """
<style>

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        background: #f5f6f8;
        font-family:
            Arial,
            "Apple SD Gothic Neo",
            "Noto Sans KR",
            sans-serif;
        color: #222;
    }

    .container {
        width: 900px;
        max-width: calc(100% - 40px);
        margin: 40px auto;
    }

    .card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
    }

    h1 {
        margin-top: 0;
        font-size: 26px;
    }

    h2 {
        font-size: 20px;
        margin-top: 0;
    }

    textarea {
        width: 100%;
        min-height: 180px;
        resize: vertical;
        padding: 15px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        font-size: 16px;
        line-height: 1.6;
    }

    button {
        margin-top: 15px;
        padding: 12px 22px;
        border: 0;
        border-radius: 8px;
        background: #222;
        color: white;
        font-size: 15px;
        cursor: pointer;
    }

    button:hover {
        opacity: 0.85;
    }

    .result-row {
        padding: 15px 0;
        border-bottom: 1px solid #eeeeee;
    }

    .result-row:last-child {
        border-bottom: none;
    }

    .result-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }

    .label-name {
        font-weight: bold;
    }

    .percentage {
        font-size: 18px;
        font-weight: bold;
    }

    .bar-background {
        width: 100%;
        height: 10px;
        background: #eeeeee;
        border-radius: 5px;
        overflow: hidden;
    }

    .bar {
        height: 100%;
        background: #555;
        border-radius: 5px;
    }

    .status {
        margin-top: 7px;
        font-size: 14px;
    }

    .detected {
        font-weight: bold;
    }

    .not-detected {
        color: #777;
    }

    .evidence-section {
        margin-top: 20px;
    }

    .evidence-label {
        font-weight: bold;
        margin-bottom: 10px;
    }

    .evidence-item {
        display: inline-block;
        padding: 7px 11px;
        margin: 4px 5px 4px 0;
        border-radius: 7px;
        background: #f1f3f5;
        border: 1px solid #dddddd;
        font-size: 14px;
    }

    .notice {
        padding: 15px;
        border-radius: 8px;
        background: #f8f9fa;
        font-size: 14px;
        line-height: 1.6;
    }

    .empty {
        color: #888;
        font-size: 14px;
    }

</style>
"""


# ============================================================
# 4. 기본 HTML 페이지
# ============================================================

def page(
    result: str = "",
    text: str = "",
) -> str:
    """
    입력 폼과 분석 결과가 포함된 전체 HTML 페이지를 생성한다.
    """

    safe_text = html.escape(
        text
    )

    return f"""
    <!DOCTYPE html>

    <html lang="ko">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>I-SPOT AI Test</title>

        {STYLE}

    </head>

    <body>

        <div class="container">

            <div class="card">

                <h1>I-SPOT AI 모델 테스트</h1>

                <p>
                    상담 텍스트를 입력하면
                    4개 학대 유형 관련 신호를 분석합니다.
                </p>

                <form method="post">

                    <textarea
                        name="text"
                        placeholder="상담 텍스트를 입력하세요."
                        required
                    >{safe_text}</textarea>

                    <button type="submit">
                        분석하기
                    </button>

                </form>

            </div>

            {result}

        </div>

    </body>

    </html>
    """


# ============================================================
# 5. 예측 결과 HTML 생성
# ============================================================

def build_prediction_html(
    predictions: dict,
) -> str:
    """
    4개 학대 유형의 확률과 신호 탐지 여부를 HTML로 변환한다.
    """

    result = """
    <div class="card">

        <h2>학대 관련 신호 분석</h2>
    """

    for label in LABEL_NAMES:

        item = predictions[
            label
        ]

        percentage = item[
            "percentage"
        ]

        threshold_percentage = (
            item["threshold"]
            * 100
        )

        if item["detected"]:

            status = (
                "관련 신호 있음"
            )

            status_class = (
                "detected"
            )

        else:

            status = (
                "관련 신호 없음"
            )

            status_class = (
                "not-detected"
            )

        result += f"""
        <div class="result-row">

            <div class="result-header">

                <span class="label-name">
                    {html.escape(label)}
                </span>

                <span class="percentage">
                    {percentage:.2f}%
                </span>

            </div>

            <div class="bar-background">

                <div
                    class="bar"
                    style="width: {percentage:.2f}%"
                ></div>

            </div>

            <div class="status {status_class}">

                {status}
                · 기준 {threshold_percentage:.0f}%

            </div>

        </div>
        """

    result += """
    </div>
    """

    return result


# ============================================================
# 6. 근거 표현 HTML 생성
# ============================================================

def build_evidence_html(
    predictions: dict,
    explanations: dict,
) -> str:
    """
    학대 관련 신호가 탐지된 유형뿐 아니라,
    일정 수준 이상 모델 반응이 존재하는 유형의 근거도 표시한다.

    50% 이상:
        관련 신호 있음

    20~50%:
        기준 미만이지만 모델이 반응한 표현을 참고용으로 표시
    """

    result = """
    <div class="card">

        <h2>모델 예측의 주요 근거 표현</h2>

        <div class="notice">
            아래 표현은 Phrase Occlusion 방식으로 분석한
            <strong>모델 예측 기여 표현</strong>입니다.
            실제 학대 여부를 확정하거나 인과관계를 의미하지 않습니다.
        </div>
    """

    displayed_count = 0

    for label in LABEL_NAMES:

        prediction = predictions[
            label
        ]

        probability = prediction[
            "probability"
        ]

        # ----------------------------------------------------
        # 확률이 너무 낮은 라벨은 근거 표시하지 않음
        # ----------------------------------------------------

        if (
            probability
            < EVIDENCE_DISPLAY_THRESHOLD
        ):
            continue

        evidence_items = explanations.get(
            label,
            [],
        )

        # XAI 근거 자체가 없으면 굳이 빈 라벨을 출력하지 않음
        if not evidence_items:
            continue

        displayed_count += 1

        # ----------------------------------------------------
        # 탐지 여부에 따른 설명
        # ----------------------------------------------------

        if prediction["detected"]:

            evidence_status = (
                "관련 신호 있음"
            )

        else:

            evidence_status = (
                "관련 신호 기준 미만 · 참고용 근거"
            )

        result += f"""
        <div class="evidence-section">

            <div class="evidence-label">
                {html.escape(label)}
                <span style="
                    font-size: 12px;
                    font-weight: normal;
                    color: #777;
                    margin-left: 8px;
                ">
                    {evidence_status}
                    ({prediction['percentage']:.2f}%)
                </span>
            </div>
        """

        for item in evidence_items:

            phrase = html.escape(
                item["phrase"]
            )

            result += f"""
            <span class="evidence-item">
                {phrase}
            </span>
            """

        result += """
        </div>
        """

    if displayed_count == 0:

        result += """
        <div class="evidence-section">

            <div class="empty">
                현재 모델이 유의하게 반응한 근거 표현이 없습니다.
            </div>

        </div>
        """

    result += """
    </div>
    """

    return result

# ============================================================
# 7. GET
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    """
    초기 테스트 화면을 반환한다.
    """

    return page()


# ============================================================
# 8. POST 분석
# ============================================================

@app.post(
    "/",
    response_class=HTMLResponse,
)
def analyze(
    text: str = Form(...),
):
    """
    상담 텍스트에 대해 모델 예측과 근거 표현을 함께 분석한다.
    """

    try:

        # ----------------------------------------------------
        # 4개 유형 예측
        # ----------------------------------------------------

        predictions = (
            predict_abuse(
                text
            )
        )

        # ----------------------------------------------------
        # Phrase Occlusion XAI
        # ----------------------------------------------------

        explanations = (
            explain_abuse(
                text
            )
        )

        # ----------------------------------------------------
        # HTML 결과 생성
        # ----------------------------------------------------

        prediction_html = (
            build_prediction_html(
                predictions
            )
        )

        evidence_html = (
            build_evidence_html(
                predictions,
                explanations,
            )
        )

        result = (
            prediction_html
            + evidence_html
        )

        return page(
            result=result,
            text=text,
        )

    except Exception as error:

        error_message = html.escape(
            str(error)
        )

        result = f"""
        <div class="card">

            <h2>분석 오류</h2>

            <div class="notice">
                {error_message}
            </div>

        </div>
        """

        return page(
            result=result,
            text=text,
        )


# ============================================================
# 9. 서버 실행
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
    )