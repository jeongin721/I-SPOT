"""I-SPOT Downstream Analysis Module.

후처리 완료된 STT JSON 데이터를 전달받아 OpenAI LLM 기반 상황 분석 및 위험도를 평가한다.
"""

import json
import os
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI

# 공부용 설명:
# 이 파일은 STT로 뽑아낸 상담 대화 내용을 받아서,
# 실제로 위험 상황을 판단하는 최종 분석기다.
#
# 핵심 역할:
# - 대화를 사람이 이해하기 쉬운 문자열 형태로 만든다.
# - LLM에게 상황을 설명하는 프롬프트를 생성한다.
# - OpenAI API를 호출해 위험도 평가를 받는다.
# - 마지막으로 결과를 프로젝트 표준 JSON으로 정리해 반환한다.
#
# 즉, 이 파일은 "STT 결과를 분석해서 위험 여부와 조치사항까지 뽑는 단계"다.
load_dotenv()


class RiskAnalyzer:
    def __init__(self, model_name: str = "openai/gpt-oss-120b"):
        self.model_name = model_name
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            raise ValueError("[X] GROQ_API_KEY가 .env 파일에 설정되어 있지 않습니다.")
        
        # Groq의 OpenAI 호환 Base URL 설정
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key
        )

    def _build_prompt(self, stt_data: Dict[str, Any]) -> str:
        segments = stt_data.get("segments", [])
        dialogue_text = "".join([f"[{seg['speaker']}] {seg['text']}\n" for seg in segments])

        return f"""
당신은 아동학대 및 위험 상황 감지 전문 분석가입니다. 대화를 분석하여 JSON으로 응답하세요.

[대화 내역]
{dialogue_text}

[출력 요구사항 - 반드시 아래 JSON 형식만 반환]
{{
    "risk_level": "LOW | MEDIUM | HIGH",
    "risk_score": 0,
    "summary": "상황 핵심 요약 2~3문장",
    "detected_risks": ["감지된 위험 요소"],
    "recommended_action": "권장 조치 사항"
}}
"""

    def analyze(self, stt_data: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self._build_prompt(stt_data)
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a professional risk analysis assistant. Respond ONLY with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            return {
                "schema_version": "1.0",
                "analysis_result": json.loads(response.choices[0].message.content)
            }
        except Exception as exc:
            raise RuntimeError(f"Groq LLM 분석 처리 중 오류 발생: {exc}") from exc