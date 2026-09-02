import json
import os
from ispot_stt import DeepgramSTTProvider

if __name__ == "__main__":
    # 테스트에 사용할 음성 파일 경로 (.wav 또는 .mp3)
    # 실제 보유 중인 샘플 오디오 파일명으로 변경해 주세요.
    sample_audio_path = "test.mp3.m4a"

    if not os.path.exists(sample_audio_path):
        print(f"[!] '{sample_audio_path}' 파일이 존재하지 않습니다.")
        print("    프로젝트 폴더 안에 테스트용 .wav 또는 .mp3 파일을 넣고 파일명을 맞춰주세요.")
    else:
        try:
            print("Deepgram API 호출 및 STT / 화자 분리 처리 중...")
            provider = DeepgramSTTProvider()
            result = provider.transcribe_and_diarize(sample_audio_path)
            
            print("\n=== STT Contract Schema v1.0 변환 성공 ===")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"[X] 오류 발생: {e}")