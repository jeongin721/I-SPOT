"""
상담사가 작성한 자유형식 상담 기록을 입력해 4개 학대 관련 신호를 테스트하는 FastAPI 웹 페이지.
현재 최고 기록형 RoBERTa Multi-label 체크포인트를 로드하여 각 유형의 sigmoid 확률을 출력한다.
"""

from pathlib import Path

import torch
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import uvicorn


# ============================================================
# 기본 설정
# ============================================================

MODEL_ID = "klue/roberta-base"

LABEL_NAMES = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

NUM_LABELS = len(LABEL_NAMES)

MAX_LEN = 512

# 우선 기본 threshold 0.5 사용
# 추후 Validation 기준으로 라벨별 threshold 튜닝 예정
THRESHOLDS = {
    "신체학대": 0.5,
    "정서학대": 0.5,
    "성학대": 0.5,
    "방임": 0.5,
}


# ============================================================
# 모델 경로
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODEL_PATH = (
    PROJECT_ROOT
    / "ai"
    / "modeling"
    / "abuse"
    / "weight"
    / "roberta_multilabel_record_macro09398_2026-09-03.pth"
)


# ============================================================
# Device 설정
# ============================================================

DEVICE = torch.device(
    "cuda"
    if torch.cuda.is_available()
    else "cpu"
)

print(f"Device: {DEVICE}")

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
# Model 생성
# ============================================================

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_ID,
    num_labels=NUM_LABELS,
    problem_type="multi_label_classification",
)

state_dict = torch.load(
    MODEL_PATH,
    map_location=DEVICE,
    weights_only=True,
)

model.load_state_dict(
    state_dict
)

model.to(
    DEVICE
)

model.eval()

print(
    f"Loaded model: {MODEL_PATH}"
)


# ============================================================
# 예측 함수
# ============================================================

def predict(
    text: str,
) -> list:
    """
    상담 기록 텍스트를 입력받아
    각 학대 관련 신호의 sigmoid 확률을 계산한다.
    """

    encoded = tokenizer(
        text,
        max_length=MAX_LEN,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    input_ids = encoded[
        "input_ids"
    ].to(DEVICE)

    attention_mask = encoded[
        "attention_mask"
    ].to(DEVICE)

    with torch.no_grad():

        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        probabilities = torch.sigmoid(
            outputs.logits
        )[0]

    probabilities = (
        probabilities
        .cpu()
        .numpy()
    )

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
                "percent": probability * 100,
                "detected": probability >= threshold,
            }
        )

    return results


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="I-SPOT Record Model Test"
)


# ============================================================
# HTML 생성
# ============================================================

def render_page(
    text: str = "",
    results: list = None,
) -> str:
    """테스트용 웹 페이지 HTML을 생성한다."""

    results = results or []

    result_html = ""

    if results:

        cards = []

        for result in results:

            status = (
                "관련 신호 감지"
                if result["detected"]
                else "기준 미만"
            )

            cards.append(
                f"""
                <div class="result-card">
                    <div class="result-header">
                        <strong>{result["label"]}</strong>
                        <span>{result["percent"]:.2f}%</span>
                    </div>

                    <div class="bar">
                        <div
                            class="bar-value"
                            style="width: {result["percent"]:.2f}%;">
                        </div>
                    </div>

                    <div class="status">
                        {status}
                    </div>
                </div>
                """
            )

        result_html = f"""
        <div class="results">
            <h2>분석 결과</h2>
            {''.join(cards)}
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="ko">

    <head>

        <meta charset="UTF-8">

        <title>
            I-SPOT 상담 기록 테스트
        </title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                background: #f5f6f8;
                margin: 0;
                padding: 40px;
            }}

            .container {{
                max-width: 850px;
                margin: auto;
                background: white;
                padding: 35px;
                border-radius: 14px;
                box-shadow: 0 4px 18px rgba(0,0,0,0.08);
            }}

            h1 {{
                margin-top: 0;
            }}

            .description {{
                color: #666;
                line-height: 1.6;
                margin-bottom: 25px;
            }}

            textarea {{
                width: 100%;
                height: 230px;
                box-sizing: border-box;
                padding: 16px;
                font-size: 16px;
                line-height: 1.6;
                border: 1px solid #ccc;
                border-radius: 8px;
                resize: vertical;
            }}

            button {{
                margin-top: 15px;
                width: 100%;
                padding: 14px;
                border: 0;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
            }}

            .results {{
                margin-top: 35px;
            }}

            .result-card {{
                padding: 18px;
                margin-top: 12px;
                background: #f7f7f7;
                border-radius: 8px;
            }}

            .result-header {{
                display: flex;
                justify-content: space-between;
                font-size: 17px;
            }}

            .bar {{
                height: 10px;
                margin-top: 12px;
                background: #ddd;
                border-radius: 5px;
                overflow: hidden;
            }}

            .bar-value {{
                height: 100%;
                background: #555;
            }}

            .status {{
                margin-top: 8px;
                color: #666;
                font-size: 14px;
            }}

            .warning {{
                margin-top: 30px;
                padding: 14px;
                background: #f5f5f5;
                border-radius: 8px;
                color: #666;
                font-size: 13px;
                line-height: 1.5;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <h1>
                I-SPOT 상담 기록 테스트
            </h1>

            <div class="description">
                상담사가 작성한 상담 기록을 그대로 입력하세요.<br>
                모델이 신체학대·정서학대·성학대·방임 관련 신호를
                독립적으로 분석합니다.
            </div>

            <form method="post">

                <textarea
                    name="text"
                    placeholder="예) 아동은 아버지가 화가 나면 자신과 동생을 때린다고 말함. 최근에는 일주일에 두세 번 정도 발생했으며 팔에 멍이 든 적이 있다고 함."
                    required>{text}</textarea>

                <button type="submit">
                    분석하기
                </button>

            </form>

            {result_html}

            <div class="warning">
                ※ 본 결과는 학대 여부에 대한 최종 판단이 아니라
                상담 기록에서 관련 신호를 탐지하여 상담사의 검토를
                보조하기 위한 모델 테스트 결과입니다.
            </div>

        </div>

    </body>

    </html>
    """


# ============================================================
# GET
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse,
)
def home():
    """초기 테스트 페이지를 표시한다."""

    return render_page()


# ============================================================
# POST
# ============================================================

@app.post(
    "/",
    response_class=HTMLResponse,
)
def analyze(
    text: str = Form(...),
):
    """입력된 상담 기록을 모델로 분석한다."""

    text = text.strip()

    results = predict(
        text
    )

    return render_page(
        text=text,
        results=results,
    )


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
    )