import json
import os
from dotenv import load_dotenv

from ispot_stt import DeepgramSTTProvider
from ispot_postprocess import STTPostProcessor

load_dotenv()

# 공부용 설명:
# 이 파일은 Deepgram 단일 provider를 직접 테스트하는 스크립트다.
#
# 핵심 흐름:
# 1) 오디오 파일을 읽는다.
# 2) DeepgramSTTProvider.transcribe()를 호출해 STT 결과를 받는다.
# 3) STTPostProcessor를 통해 동일 화자 발화를 병합한다.
# 4) 최종 결과를 JSON으로 출력한다.
#
# 즉, 'STT 자체의 정상 동작'을 확인하는 데 집중하는 테스트 파일이다.
# 전체 파이프라인 검증 파일이 아니라, Deepgram 입출력과 후처리 전반을 확인하는 용도다.

def run_pipeline(audio_path: str):
    print("1. Deepgram STT 및 화자 분리 진행 중...")
    provider = DeepgramSTTProvider()
    raw_stt_result = provider.transcribe(audio_path)

    print("2. STT 결과 후처리 및 동일 화자 발화 병합 중...")
    post_processor = STTPostProcessor(low_confidence_threshold=0.70)
    final_result = post_processor.process(raw_stt_result)

    print("\n=== 최종 정규화 파이프라인 결과 ===")
    print(json.dumps(final_result, indent=2, ensure_ascii=False))
    return final_result

if __name__ == "__main__":
    # 프로젝트 폴더 내 테스트용 오디오 파일 경로
    AUDIO_FILE = "test.mp3.m4a"
    
    if os.path.exists(AUDIO_FILE):
        run_pipeline(AUDIO_FILE)
    else:
        print(f"[X] 테스트 오디오 파일을 찾을 수 없습니다: {AUDIO_FILE}")