"""
Q+A 문맥 기반 멀티라벨 학대 신호 모델을 브라우저에서 간단히 테스트하는 FastAPI 웹 페이지.
상담 텍스트를 입력하면 신체·정서·성·방임 관련 신호 확률을 백분율로 출력한다.
"""

from pathlib import Path

import torch
import uvicorn

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


# ============================================================
# 기본 모델 설정
# ============================================================

MODEL_ID = "klue/roberta-base"

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

MAX_LEN = 512

# 아직 QA 모델 전용 threshold tuning 전이므로
# 우선 학습 평가와 동일하게 모든 유형에 0.5를 사용한다.
THRESHOLDS = {
    "신체학대": 0.5,
    "정서학대": 0.5,
    "성학대": 0.5,
    "방임": 0.5,
}


# ============================================================
# 최고 성능 QA 모델 경로
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = (
    BASE_DIR
    / "weight"
    / "roberta_multilabel_qa_macro09098_2026-09-03.pth"
)


# ============================================================
# GPU 설정
# ============================================================

device = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print(
    "Device:",
    device,
)

if torch.cuda.is_available():
    print(
        "GPU:",
        torch.cuda.get_device_name(0),
    )


# ============================================================
# Tokenizer 로드
# ============================================================

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_ID
)


# ============================================================
# QA Multi-label 모델 생성
# ============================================================

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID,
    num_labels=len(LABEL_NAMES),
    problem_type="multi_label_classification",
)


# ============================================================
# 저장된 최고 성능 Weight 로드
# ============================================================

state_dict = torch.load(
    MODEL_PATH,
    map_location=device,
)

model.load_state_dict(
    state_dict
)

model.to(device)
model.eval()

print(
    "Loaded model:",
    MODEL_PATH,
)


# ============================================================
# 학대 관련 신호 예측 함수
# ============================================================

def predict_abuse(text: str):
    """
    입력 상담 텍스트를 QA 모델에 전달하고
    유형별 관련 신호 확률을 반환한다.
    """

    inputs = tokenizer(
        text,
        add_special_tokens=True,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_attention_mask=True,
        return_tensors="pt",
    )

    input_ids = inputs[
        "input_ids"
    ].to(device)

    attention_mask = inputs[
        "attention_mask"
    ].to(device)

    token_type_ids = inputs.get(
        "token_type_ids"
    )

    if token_type_ids is not None:
        token_type_ids = token_type_ids.to(
            device
        )

    # --------------------------------------------------------
    # Gradient 계산 없이 추론만 수행
    # --------------------------------------------------------

    with torch.no_grad():

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )[0]

    probabilities = (
        probabilities
        .detach()
        .cpu()
        .numpy()
    )

    # --------------------------------------------------------
    # 유형별 확률 및 관련 신호 탐지 여부 정리
    # --------------------------------------------------------

    results = []

    for label, probability in zip(
        LABEL_NAMES,
        probabilities,
    ):

        probability = float(
            probability
        )

        threshold = THRESHOLDS[
            label
        ]

        results.append(
            {
                "label": label,
                "probability": probability,
                "percentage": probability * 100,
                "threshold": threshold,
                "detected": probability >= threshold,
            }
        )

    return results


# ============================================================
# FastAPI 앱 생성
# ============================================================

app = FastAPI(
    title="I-SPOT QA Abuse Signal Test"
)


# ============================================================
# HTML 페이지 생성
# ============================================================

def render_page(
    text: str = "",
    results=None,
):

    result_html = ""

    # --------------------------------------------------------
    # 모델 분석 결과가 있는 경우 결과 카드 생성
    # --------------------------------------------------------

    if results:

        for result in results:

            detected_text = (
                "관련 신호 감지"
                if result["detected"]
                else "관련 신호 낮음"
            )

            result_html += f"""
            <div class="result-card">
                <div class="result-header">
                    <strong>{result["label"]}</strong>
                    <span>{result["percentage"]:.2f}%</span>
                </div>

                <div class="progress">
                    <div
                        class="progress-value"
                        style="width:{result["percentage"]:.2f}%">
                    </div>
                </div>

                <div class="status">
                    {detected_text}
                </div>
            </div>
            """

    else:

        result_html = """
        <div class="empty">
            상담 텍스트를 입력하면 분석 결과가 표시됩니다.
        </div>
        """

    # --------------------------------------------------------
    # 전체 웹 페이지
    # --------------------------------------------------------

    return f"""
    <!DOCTYPE html>

    <html lang="ko">

    <head>

        <meta charset="UTF-8">

        <title>
            I-SPOT QA Model Test
        </title>

        <style>

            body {{
                font-family:
                    Arial,
                    sans-serif;

                background:
                    #f5f6f8;

                margin: 0;
                padding: 40px;
            }}

            .container {{
                max-width: 850px;
                margin: auto;
                background: white;
                padding: 32px;
                border-radius: 14px;
                box-shadow:
                    0 4px 18px
                    rgba(0, 0, 0, 0.08);
            }}

            h1 {{
                margin-top: 0;
            }}

            .description {{
                color: #666;
                margin-bottom: 24px;
            }}

            textarea {{
                width: 100%;
                height: 180px;
                box-sizing: border-box;
                padding: 15px;
                font-size: 16px;
                border: 1px solid #ccc;
                border-radius: 8px;
                resize: vertical;
            }}

            button {{
                width: 100%;
                margin-top: 12px;
                padding: 14px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                background: #222;
                color: white;
            }}

            .results {{
                margin-top: 30px;
            }}

            .result-card {{
                padding: 16px;
                margin-bottom: 12px;
                border: 1px solid #ddd;
                border-radius: 10px;
            }}

            .result-header {{
                display: flex;
                justify-content: space-between;
                font-size: 18px;
                margin-bottom: 10px;
            }}

            .progress {{
                height: 10px;
                background: #eee;
                border-radius: 10px;
                overflow: hidden;
            }}

            .progress-value {{
                height: 100%;
                background: #333;
            }}

            .status {{
                margin-top: 8px;
                font-size: 13px;
                color: #666;
            }}

            .empty {{
                color: #888;
                padding: 20px 0;
            }}

            .notice {{
                margin-top: 25px;
                padding: 14px;
                background: #f5f5f5;
                border-radius: 8px;
                color: #666;
                font-size: 13px;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <h1>
                I-SPOT QA 학대 관련 신호 테스트
            </h1>

            <div class="description">
                Q+A 문맥 기반 RoBERTa Multi-label 모델
            </div>

            <form
                method="post"
                action="/predict">

                <textarea
                    name="text"
                    placeholder="[상담사] ... [아동] ..."
                    required>{text}</textarea>

                <button type="submit">
                    분석하기
                </button>

            </form>

            <div class="results">

                {result_html}

            </div>

            <div class="notice">
                본 결과는 학대 여부에 대한 최종 판단이 아니라
                상담 내용에서 관련 신호를 탐지하기 위한 AI 보조 결과입니다.
            </div>

        </div>

    </body>

    </html>
    """


# ============================================================
# 메인 페이지
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)

def home():

    return render_page()


# ============================================================
# 분석 요청
# ============================================================

@app.post(
    "/predict",
    response_class=HTMLResponse,
)

def predict(
    text: str = Form(...),
):

    results = predict_abuse(
        text
    )

    return render_page(
        text=text,
        results=results,
    )


# ============================================================
# 서버 실행
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
    )