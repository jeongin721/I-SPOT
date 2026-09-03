from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

from ai.modeling.abuse.infer_abuse import predict_abuse, LABEL_NAMES

app = FastAPI()


def page(result="", text=""):
    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <title>I-SPOT Test</title>
    </head>

    <body>
        <h2>상담 텍스트 테스트</h2>

        <form method="post">
            <textarea
                name="text"
                rows="10"
                cols="80"
                placeholder="상담 텍스트 입력"
            >{text}</textarea>

            <br><br>

            <button type="submit">분석</button>
        </form>

        <br>

        {result}
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
def home():
    return page()


@app.post("/", response_class=HTMLResponse)
def analyze(text: str = Form(...)):

    predictions = predict_abuse(text)

    result = "<h3>분석 결과</h3>"

    for label in LABEL_NAMES:

        item = predictions[label]

        status = (
            "관련 신호 있음"
            if item["detected"]
            else "관련 신호 없음"
        )

        result += (
            f"<p>"
            f"{label}: "
            f"{item['percentage']:.2f}% "
            f"→ {status}"
            f"</p>"
        )

    return page(result, text)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
    )