from pathlib import Path
import subprocess
import whisper

AUDIO_PATH = Path("test_sample/1354.mp3")
CLIP_PATH = Path("test_sample/1354_critical_clip.mp3")

# GT 핵심 A 구간:
# 04:35.543 ~ 04:44.025
START = "00:04:35.543"
DURATION = "8.482"

# 1) ffmpeg로 문제 구간 자르기
subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-ss", START,
        "-i", str(AUDIO_PATH),
        "-t", DURATION,
        "-acodec", "libmp3lame",
        str(CLIP_PATH),
    ],
    check=True,
)

print("클립 생성 완료:", CLIP_PATH)

# 2) Whisper 로드
print("Whisper base 모델 로딩 중...")
model = whisper.load_model("large-v3")

# 3) 한국어로 전사
print("Whisper 전사 중...")
result = model.transcribe(
    str(CLIP_PATH),
    language="ko",
    fp16=False,
)

print("\n" + "=" * 70)
print("Whisper 결과")
print("=" * 70)
print(result["text"].strip())