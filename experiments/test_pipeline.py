import json
import os
from ispot_stt import DeepgramSTTProvider
from ispot_postprocess import STTPostProcessor
from ispot_analyzer import RiskAnalyzer

# 공부용 설명:
# 이 파일은 전체 I-SPOT 분석 파이프라인을 한 번에 테스트하는 스크립트다.
#
# 흐름은 다음과 같다:
# 1) Deepgram으로 원본 STT 결과를 생성한다.
# 2) STTPostProcessor로 발화 병합/정리 작업을 수행한다.
# 3) RiskAnalyzer로 위험도 분석을 실행한다.
# 4) 최종적으로 stt_data와 analysis를 함께 묶어 출력한다.
#
# 즉, 이 파일은 '엔드투엔드(E2E) 동작 확인'을 위한 통합 테스트용 코드다.
# 각 단위 기능만 보는 것이 아니라 전체 흐름이 제대로 이어지는지를 확인한다.

def run_full_pipeline(audio_path: str):
    print("[Step 1] Deepgram STT & 화자 분리 실행 중...")
    provider = DeepgramSTTProvider()
    raw_stt = provider.transcribe(audio_path)

    print("[Step 2] STT 결과 후처리 및 발화 병합 중...")
    post_processor = STTPostProcessor()
    processed_stt = post_processor.process(raw_stt)

    print("[Step 3] Downstream AI 위험도 분석 실행 중...")
    analyzer = RiskAnalyzer()
    final_analysis = analyzer.analyze(processed_stt)

    # 최종 병합 출력
    pipeline_output = {
        "stt_data": processed_stt,
        "analysis": final_analysis["analysis_result"]
    }

    print("\n=== [I-SPOT End-to-End 파이프라인 최종 출력] ===")
    print(json.dumps(pipeline_output, indent=2, ensure_ascii=False))
    return pipeline_output

if __name__ == "__main__":
    AUDIO_FILE = "test.mp3.m4a"
    if os.path.exists(AUDIO_FILE):
        run_full_pipeline(AUDIO_FILE)
    else:
        print(f"[X] 테스트 파일 없음: {AUDIO_FILE}")