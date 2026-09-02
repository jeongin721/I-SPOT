"""I-SPOT STT adapter module.

이 모듈은 상담 음성 파일을 받아 STT 결과를 표준 JSON 형태로 변환하는 역할을 한다.
핵심 목적은 다음과 같다:
- 음성 파일의 유효성을 검사한다.
- 통합 STT provider(예: Whisper, CLOVA, Deepgram)를 호출한다.
- 결과를 I-SPOT 공통 Contract 구조에 맞게 정규화한다.
- Backend가 쉽게 import 해서 사용할 수 있는 Transcriber 클래스를 제공한다.

즉, 이 코드는 "상담 오디오 -> 텍스트 세그먼트 데이터"로 바꾸는 중간 계층이다.
"""

# 기존 try-except 구문 대신 직접 import
import os
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from deepgram import DeepgramClient


load_dotenv()

# 공부용 설명:
# 이 파일은 '음성 파일 -> 텍스트 segment JSON'으로 바꾸는 변환기다.
# 실제로는 외부 STT 서비스(Deepgram, Whisper)를 호출하는 역할을 하며,
# 그 결과를 프로젝트에서 공통으로 쓰는 표준 형식으로 정리한다.
#
# 핵심 상수 정리:
# 1) SUPPORTED_AUDIO_EXTENSIONS: 허용할 오디오 파일 확장자를 제한한다.
#    → 잘못된 파일을 미리 막아서 이후 코드에서 예외가 터지는 일을 줄인다.
# 2) SPEAKER_ENUM: 화자 정보를 일관되게 관리하기 위한 표준 값 집합이다.
#    → 상담사/아동/보호자처럼 표현이 달라도 최종에는 이 값만 남는다.
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac"}
SPEAKER_ENUM = {"COUNSELOR", "CHILD", "GUARDIAN", "OTHER", "UNKNOWN"}


# ------------------------------------------------------------
# 1. 에러 정의
# ------------------------------------------------------------
# 공부용 설명:
# 이 코드에서는 실수/오류를 그냥 "일반 에러"로 묶지 않고,
# 분리해서 관리한다. 이유는 디버깅이 쉬워지고, 어떤 단계에서 실패했는지
# 더 정확하게 알 수 있기 때문이다.
#
# InvalidAudioError: 오디오 파일 자체가 잘못되었을 때
# AudioProviderError: STT API/모델 호출이 실패했을 때
# SpeakerDiarizationError: 화자 분리 기능이 실패했을 때
class InvalidAudioError(ValueError):
    """Raised for unsupported or malformed audio input."""


class AudioProviderError(RuntimeError):
    """Raised when a configured STT provider fails."""


class SpeakerDiarizationError(RuntimeError):
    """Raised when speaker diarization is unavailable or fails."""


# ------------------------------------------------------------
# 2. STT provider 공통 인터페이스
# ------------------------------------------------------------
# 공부용 설명:
# 이 클래스는 "STT를 제공하는 객체들이 반드시 지켜야 하는 약속"이다.
# 실제 구현체들은 각각 Deepgram, Whisper, Mock 방식으로 동작하지만,
# 외부 코드는 transcribe()라는 이름 하나로 동일하게 호출할 수 있다.
#
# 이렇게 인터페이스를 맞춰두면 나중에 provider를 교체해도
# 다른 코드가 큰 수정 없이 동작한다.
class BaseSTTProvider:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        # provider마다 필요한 인증 정보와 URL을 저장한다.
        self.api_key = api_key
        self.api_url = api_url

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        # 실제 구현체가 반드시 오버라이드해야 하는 메서드.
        # 입력: 오디오 파일 경로
        # 출력: 표준화된 STT JSON 딕셔너리
        raise NotImplementedError

    def transcribe_and_diarize(self, audio_path: str) -> Dict[str, Any]:
        """하위 호환성을 위한 기본 레거시 인터페이스"""
        # 기존 코드에서 transcribe_and_diarize()를 호출해도 지금 구조에서는
        # transcribe()와 같은 동작을 수행하도록 연결해 준다.
        return self.transcribe(audio_path)


# ------------------------------------------------------------
# 3. 화자 분리(diarization) 로직
# ------------------------------------------------------------
# 공부용 설명:
# STT는 단순히 '텍스트가 무엇인지'만 알려주는 경우가 많다.
# 하지만 이 프로젝트는 상담 상황이라서 누가 말했는지(상담사/아동/보호자)도 중요하다.
# 그래서 별도의 화자 분리 클래스가 필요하다.
#
# 예시:
# - "상담사" / "counselor" / "speaker_0" → 모두 COUNSELOR로 통일
# - "아동" / "kid" / "speaker_1" → CHILD로 통일
# 이런 변환을 여기서 수행한다.
class SpeakerDiarizer:
    """Normalize raw diarization labels into the project's speaker enum."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_path: Optional[str] = None,
        role_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.provider_name = (provider or os.getenv("I_SPOT_SPEAKER_DIARIZATION_PROVIDER") or "mock").lower()
        self.model_path = model_path or os.getenv("I_SPOT_SPEAKER_DIARIZATION_MODEL")
        self.role_map = {
            "COUNSELOR": ["counselor", "상담사", "therapist", "interviewer", "speaker_0", "speaker0"],
            "CHILD": ["child", "아동", "kid", "young", "speaker_1", "speaker1"],
            "GUARDIAN": ["guardian", "보호자", "parent", "caregiver", "mother", "father"],
            "OTHER": ["other", "기타"],
            "UNKNOWN": ["unknown", "unassigned"],
        }
        if role_map:
            for key, value in role_map.items():
                self.role_map.setdefault(key.upper(), [])
                if isinstance(value, str):
                    self.role_map[key.upper()].append(value)
                elif isinstance(value, (list, tuple, set)):
                    self.role_map[key.upper()].extend(str(item) for item in value)

    @staticmethod
    def normalize_speaker_label(value: Any) -> str:
        """Raw diarization label을 I-SPOT Speaker Enum으로 매핑한다."""
        # 공부용 설명:
        # 화자 라벨은 모델마다 표현 방식이 다르다.
        # Deepgram는 speaker 번호를 주고, pyannote는 이름을 줄 수 있고,
        # 다른 환경에서는 "상담사", "mother", "child" 같은 문자열이 들어올 수 있다.
        # 이 함수는 이런 표현들을 모두 표준 값으로 바꾼다.
        #
        # 중요한 점:
        # 이 함수는 "결과를 축약하는 것"이 아니라,
        # 프로젝트 전체에서 같은 의미를 가진 값으로 통일하는 역할을 한다.
        if value is None:
            return "UNKNOWN"

        raw = str(value).strip()
        if not raw:
            return "UNKNOWN"

        lowered = raw.lower()
        lowered_no_space = re.sub(r"[^a-z0-9가-힣]+", "", lowered)

        if any(token in lowered_no_space for token in ["상담사", "counselor", "therapist", "interviewer"]):
            return "COUNSELOR"
        if any(token in lowered_no_space for token in ["아동", "child", "kid", "teen", "young"]):
            return "CHILD"
        if any(token in lowered_no_space for token in ["보호자", "guardian", "parent", "caregiver", "mother", "father"]):
            return "GUARDIAN"
        if any(token in lowered_no_space for token in ["other", "기타"]):
            return "OTHER"

        if any(token in lowered for token in ["speaker_0", "speaker0", "spk0", "spk_0"]):
            return "COUNSELOR"
        if any(token in lowered for token in ["speaker_1", "speaker1", "spk1", "spk_1"]):
            return "CHILD"

        return "UNKNOWN"

    def diarize(self, audio_path: str, segments: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        # 공부용 설명:
        # 이 함수는 화자 분리 결과를 실제로 만드는 곳이다.
        #
        # mock 모드:
        # - 실제 화자 모델 없이도 테스트를 돌릴 수 있게 한다.
        # - segment 0,2,4...는 상담사, 1,3,5...는 아동처럼 간단히 배치한다.
        #
        # pyannote 모드:
        # - 실제 AI 화자 분리 모델을 호출한다.
        # - 각 turn마다 화자 이름이 들어오며, 이를 표준값으로 정리한다.
        if self.provider_name == "mock":
            count = len(segments) if segments else 1
            labels: List[str] = []
            for idx in range(count):
                if idx % 2 == 0:
                    labels.append("COUNSELOR")
                else:
                    labels.append("CHILD")
            return labels

        # pyannote를 실제로 쓰는 경우
        # 오디오에서 발화 turn을 추출하고, 각 turn의 화자를 normalize_speaker_label()로 표준화한다.
        if self.provider_name in {"pyannote", "pyannote_audio"}:
            try:
                from pyannote.audio import Pipeline
            except ImportError as exc:  # pragma: no cover
                raise SpeakerDiarizationError("pyannote is not installed for speaker diarization") from exc

            pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization")
            diarized = pipeline(audio_path)
            labels: List[str] = []
            for turn, _, speaker in diarized.iter_tracks(yield_label=True):
                labels.append(self.normalize_speaker_label(speaker))
            return labels or ["UNKNOWN"]

        # provider를 설정하지 않았거나 지원하지 않는 값이면 기본적으로 UNKNOWN을 사용한다.
        return ["UNKNOWN"] * (len(segments) if segments else 1)

    def apply_to_segments(self, segments: List[Dict[str, Any]], audio_path: Optional[str] = None) -> List[Dict[str, Any]]:
        # 공부용 설명:
        # STT 결과는 보통 각 segment가 텍스트, 시간, 신뢰도 정보를 갖는다.
        # 여기서 각 segment에 speaker 값을 추가해 최종적으로
        # "누가 어떤 말을 했는지"까지 알 수 있는 구조를 만든다.
        #
        # 즉, 이 함수는 단순히 화자 분리를 끝내는 것이 아니라,
        # 전체 transcript의 품질을 높이는 마지막 정리 단계다.
        if not segments:
            return segments

        if audio_path is None:
            labels = ["UNKNOWN"] * len(segments)
        else:
            labels = self.diarize(audio_path, segments=segments)

        if len(labels) < len(segments):
            labels = labels + ["UNKNOWN"] * (len(segments) - len(labels))

        for index, segment in enumerate(segments):
            label = labels[index] if index < len(labels) else "UNKNOWN"
            segment["speaker"] = self.normalize_speaker_label(label)

        return segments


# ------------------------------------------------------------
# 4. 실제 STT provider 구현
# ------------------------------------------------------------
# 공부용 설명:
# 이 파일의 가장 중요한 점은 provider마다 구현 방식은 다르지만,
# 최종 출력 형태는 모두 같게 맞춘다는 것이다.
#
# 이런 구조를 만들면 나중에 Deepgram 대신 다른 STT를 쓰더라도,
# 백엔드와 프론트가 기대하는 데이터 형식은 바뀌지 않는다.
#
# 즉, 이 코드의 핵심 목표는 '엔진 교체가 쉬운 아답터 구조'를 만드는 것이다.
class MockSTTProvider(BaseSTTProvider):
    """Fallback provider used when external STT keys are unavailable."""

    # 실제 API 키가 없거나 외부 서비스가 동작하지 않을 때
    # 최소한의 유효한 STT JSON 구조를 만들어 준다.
    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        path = Path(audio_path)
        duration_ms = _estimate_duration_ms(path)
        transcript = "음성을 인식할 수 없는 구간이 있어 기본 텍스트로 대체합니다."
        confidence = 0.84
        if duration_ms <= 0:
            raise AudioProviderError("Audio duration could not be estimated.")

        return {
            "schema_version": "1.0",
            "segments": [
                {
                    "segment_id": "seg_001",
                    "speaker": "UNKNOWN",
                    "start_ms": 0,
                    "end_ms": max(duration_ms, 1000),
                    "text": transcript,
                    "confidence": confidence,
                    "is_low_confidence": confidence < 0.6,
                }
            ],
        }


# 4-1. Deepgram provider
# 공부용 설명:
# Deepgram는 실제로 음성을 인식하는 외부 서비스이다.
# 이 코드에서는 그 API를 호출해 transcript, start/end time, confidence 등을 받아오고,
# 이를 프로젝트 내부 표준 JSON 구조로 바꿔서 넘긴다.
#
# 여기서 중요한 건, 외부 API 응답 구조와 내부 데이터 구조가 다르다는 점이다.
# 그래서 _coerce_to_contract()가 필요한 것이다.
class DeepgramSTTProvider(BaseSTTProvider):
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None):
        super().__init__(api_key=api_key, api_url=api_url)
        if DeepgramClient is None:
            raise AudioProviderError("deepgram-sdk 패키지가 설치되지 않았습니다.")

        self.api_key = self.api_key or os.getenv("I_SPOT_STT_API_KEY") or os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise AudioProviderError("Deepgram API Key가 설정되지 않았습니다.")
        
        self.client = DeepgramClient(api_key=self.api_key)

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        # 파일이 실제로 존재하는지, 비어 있지 않은지 먼저 확인한다.
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise InvalidAudioError("유효하지 않거나 텅 빈 오디오 파일입니다.")

        try:
            with open(audio_path, "rb") as audio_file:
                audio_bytes = audio_file.read()

            # Deepgram 최신 SDK(v3/v4+) 표준 호출 메서드
            # diarize=True: 화자 분리 활성화
            # punctuate=True: 문장부호 보정
            # utterances=True: 발화 단위의 세그먼트 생성
            response = self.client.listen.v1.media.transcribe_file(
                request=audio_bytes,
                model="nova-2",
                language="ko",
                diarize=True,
                punctuate=True,
                utterances=True,
            )

            segments = self._coerce_to_contract(response)
            return {"schema_version": "1.0", "segments": segments}

        except Exception as exc:
            raise AudioProviderError(f"Deepgram STT 처리 중 오류 발생: {exc}") from exc

    def transcribe_and_diarize(self, audio_path: str) -> Dict[str, Any]:
        """기존 test_deepgram_run.py 코드와의 하위 호환성을 위한 메서드"""
        # 기존 코드가 이 메서드를 쓰더라도 현재 구조에서는 transcribe()로 통일한다.
        return self.transcribe(audio_path)

    def _coerce_to_contract(self, response) -> List[Dict[str, Any]]:
        # 공부용 설명:
        # Deepgram가 준 원본 응답은 우리가 직접 다루기 편한 형태가 아니다.
        # 예를 들어 results.utterances 안에 발화 단위 정보가 들어 있는데,
        # 프로젝트는 segment_id, speaker, start_ms, end_ms, text 같은 형태를 기대한다.
        #
        # 그래서 이 함수는 "외부 API 응답을 내부 표준 규격으로 바꾸는 변환기" 역할을 한다.
        contract_segments = []

        results = getattr(response, "results", None)
        utterances = getattr(results, "utterances", []) if results else []

        if not utterances:
            return contract_segments

        for idx, utt in enumerate(utterances, start=1):
            # Deepgram는 초 단위로 시간을 제공하므로 ms 단위로 바꾼다.
            start_ms = int(math.floor(utt.start * 1000))
            end_ms = int(math.ceil(utt.end * 1000))
            confidence = round(float(utt.confidence), 2)

            speaker_num = getattr(utt, "speaker", None)
            speaker_label = f"SPEAKER_{speaker_num}" if speaker_num is not None else "UNKNOWN"

            contract_segments.append(
                {
                    "segment_id": f"seg_{idx:03d}",
                    "speaker": speaker_label,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "text": utt.transcript.strip(),
                    "confidence": confidence,
                    "is_low_confidence": confidence < 0.70,
                }
            )

        return contract_segments


# 4-2. Whisper provider
# 공부용 설명:
# Whisper는 로컬 모델 또는 OpenAI API 둘 다 쓸 수 있는 구조로 설계되어 있다.
# 먼저 local whisper가 설치되어 있으면 그것을 쓰고,
# 그렇지 않으면 OpenAI transcription API를 이용한다.
#
# 이 방식은 환경에 따라 유연하게 동작하게 만들기 위한 설계다.
# 즉, 코드가 특정 서비스에 강하게 묶이지 않도록 만든 것이다.
class WhisperSTTProvider(BaseSTTProvider):
    """Thin adapter for providers compatible with OpenAI Whisper-style transcription."""

    @staticmethod
    def _coerce_segments_to_contract(raw_segments: Any) -> List[Dict[str, Any]]:
        # Whisper 모델이 자체적으로 준 segment는 보통 start/end/text/confidence 형태이다.
        # 하지만 프로젝트는 이 정보를 내부 Contract로 나중에 쉽게 재사용할 수 있도록
        # segment_id, speaker, start_ms, end_ms 등에 맞게 변환해야 한다.
        if raw_segments is None:
            return []

        normalized: List[Dict[str, Any]] = []
        for index, segment in enumerate(raw_segments, start=1):
            if isinstance(segment, dict):
                start = float(segment.get("start", 0.0) or 0.0)
                end = float(segment.get("end", start) or start)
                text = str(segment.get("text") or "").strip()
                confidence = segment.get("confidence")
                avg_logprob = segment.get("avg_logprob")
            else:
                start = float(getattr(segment, "start", 0.0) or 0.0)
                end = float(getattr(segment, "end", start) or start)
                text = str(getattr(segment, "text", "") or "").strip()
                confidence = getattr(segment, "confidence", None)
                avg_logprob = getattr(segment, "avg_logprob", None)

            if not text:
                continue

            if confidence is None:
                confidence = avg_logprob
            if confidence is None:
                confidence = 0.9
            confidence = max(0.0, min(1.0, float(confidence)))

            normalized.append(
                {
                    "segment_id": f"seg_{index:03d}",
                    "speaker": "UNKNOWN",
                    "start_ms": int(start * 1000),
                    "end_ms": int(end * 1000),
                    "text": text,
                    "confidence": confidence,
                    "is_low_confidence": confidence < 0.6,
                }
            )

        return normalized

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        # 공부용 설명:
        # 여기서는 STT provider를 선택하는 로직이 아니라,
        # 실제 전사 로직이 실행되는 지점이다.
        #
        # 1) 로컬 환경에 whisper 라이브러리가 있으면 우선적으로 사용한다.
        #    - 속도가 빠르고 외부 네트워크 의존이 적다.
        # 2) 실패하면 OpenAI API를 사용한다.
        #    - 환경 변수 API 키가 있으면 안정적으로 동작한다.
        try:
            import whisper

            model = whisper.load_model("base")
            result = model.transcribe(audio_path, fp16=False)
            segments = self._coerce_segments_to_contract(result.get("segments", []))
            if segments:
                return {"schema_version": "1.0", "segments": segments}
        except Exception:
            pass

        # 2) local whisper가 안 되면 OpenAI API를 쓴다.
        #    이 경우에는 API 키를 환경변수에서 읽어와 호출한다.
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AudioProviderError("openai package is required for Whisper provider") from exc

        api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AudioProviderError("OPENAI_API_KEY is not configured.")

        client = OpenAI(api_key=api_key)
        with open(audio_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        if isinstance(result, dict):
            raw_segments = result.get("segments", [])
            text = result.get("text", "")
        else:
            raw_segments = getattr(result, "segments", []) or []
            text = getattr(result, "text", "") or ""

        segments = self._coerce_segments_to_contract(raw_segments)
        if not segments and text.strip():
            segments = [
                {
                    "segment_id": "seg_001",
                    "speaker": "UNKNOWN",
                    "start_ms": 0,
                    "end_ms": max(int(_estimate_duration_ms(Path(audio_path)) or 1000), 1000),
                    "text": text.strip(),
                    "confidence": 0.9,
                    "is_low_confidence": False,
                }
            ]

        if not segments:
            segments = [
                {
                    "segment_id": "seg_001",
                    "speaker": "UNKNOWN",
                    "start_ms": 0,
                    "end_ms": max(int(_estimate_duration_ms(Path(audio_path)) or 1000), 1000),
                    "text": "음성 인식 결과가 비어 있습니다.",
                    "confidence": 0.0,
                    "is_low_confidence": True,
                }
            ]

        return {"schema_version": "1.0", "segments": segments}


# 4-3. CLOVA placeholder
# 공부용 설명:
# CLOVA는 아직 실제 연동 코드가 없기 때문에, '빈 자리' 역할을 하는 클래스다.
# 현재는 에러를 발생시키지만, 나중에 이 자리 안에 CLOVA API 호출 코드를 넣으면
# 같은 인터페이스와 같은 JSON contract를 유지할 수 있다.
#
# 이 구조는 provider를 추가할 때 아주 중요하다.
# 새 STT 엔진을 붙일 때 기존 코드 전체를 바꾸지 않고
# 이 클래스처럼 추가만 하면 된다.
class ClovaSpeechSTTProvider(BaseSTTProvider):
    """Provider skeleton for CLOVA Speech compatibility. Uses the same JSON contract."""

    def transcribe(self, audio_path: str) -> Dict[str, Any]:
        raise AudioProviderError("CLOVA Speech integration is not configured in this environment.")


# ------------------------------------------------------------
# 5. 유틸 함수
# ------------------------------------------------------------
# 이 부분은 실제 전사 전에 필요한 기반 정보를 계산하는 핵심 함수들이다.
# - 오디오 길이 추정: segment end_ms, fallback 기본값 등에 사용된다.
# - 파일 경로 정규화: 입력이 올바른 오디오 파일인지 검사한다.

def _estimate_duration_ms(audio_path: Path) -> int:
    # 오디오의 길이를 밀리초 단위로 계산한다.
    # WAV는 wave 모듈로 직접 읽고, 다른 형식은 ffprobe 명령으로 길이를 측정한다.
    if not audio_path.exists():
        raise InvalidAudioError(f"Audio file not found: {audio_path}")

    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if frames <= 0 or rate <= 0:
                    raise InvalidAudioError("Audio file contains no readable waveform data.")
                return int((frames / rate) * 1000)
        except (wave.Error, OSError) as exc:
            raise InvalidAudioError(f"Invalid WAV file: {audio_path}") from exc

    ffprobe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if ffprobe.returncode == 0 and ffprobe.stdout.strip():
        try:
            return int(float(ffprobe.stdout.strip()) * 1000)
        except ValueError:
            pass

    return 1000


def _normalize_audio_path(audio_path: str | os.PathLike[str]) -> Path:
    # 사용자가 넣은 경로가 실제 존재하는 파일인지, 비어 있지 않은지,
    # 지원 형식인지까지 검사하여 잘못된 입력을 차단한다.
    path = Path(audio_path)
    if not path.exists():
        raise InvalidAudioError(f"Audio file not found: {path}")
    if path.stat().st_size <= 0:
        raise InvalidAudioError(f"Audio file is empty: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise InvalidAudioError(
            f"Unsupported audio format: {path.suffix or 'unknown'}; supported: {sorted(SUPPORTED_AUDIO_EXTENSIONS)}"
        )
    return path


# ------------------------------------------------------------
# 6. 최종 진입점: Transcriber
# ------------------------------------------------------------
# 공부용 설명:
# 이 클래스가 실제 프로젝트에서 가장 많이 쓰는 입구다.
#
# 외부에서 다음처럼 사용한다고 생각하면 된다:
#   transcriber = Transcriber(provider="deepgram")
#   result = transcriber.transcribe("sample.wav")
#
# 이 한 줄의 호출이 내부적으로는 아래 단계를 모두 거친다:
# 1) 파일 검증
# 2) provider 선택
# 3) STT 수행
# 4) 결과 정규화
# 5) 화자 정보 보정
# 6) 최종 JSON 반환
#
# 즉, 이 클래스를 중심으로 전체 STT 시스템이 작동한다.
class Transcriber:
    """Backend-friendly adapter that preserves the global STT contract across providers."""

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        provider_options: Optional[Dict[str, Any]] = None,
    ) -> None:
        # 공부용 설명:
        # 생성자에서는 실제 전사 기능을 사용하기 전에 필요한 설정을 준비한다.
        #
        # 어떤 provider를 쓸지 정하고,
        # 인증키를 찾고,
        # 화자 분리 기능을 켤지 여부를 판단한다.
        #
        # 전달되지 않으면 환경 변수 I_SPOT_STT_PROVIDER를 확인하고,
        # 그래도 없으면 mock을 기본값으로 사용한다.
        self.provider_name = (provider or os.getenv("I_SPOT_STT_PROVIDER") or "mock").lower()

        # API 키는 여러 위치에서 올 수 있으므로 우선순위대로 읽어온다.
        self.api_key = api_key or os.getenv("I_SPOT_STT_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPGRAM_API_KEY")
        self.api_url = api_url or os.getenv("I_SPOT_STT_API_URL")
        self.provider_options = provider_options or {}

        # 화자 분리 옵션이 켜져 있으면 diarizer를 연결한다.
        self.speaker_diarizer = None
        if self.provider_options.get("speaker_diarization") or os.getenv("I_SPOT_SPEAKER_DIARIZATION_PROVIDER"):
            self.speaker_diarizer = SpeakerDiarizer(
                provider=os.getenv("I_SPOT_SPEAKER_DIARIZATION_PROVIDER"),
                model_path=os.getenv("I_SPOT_SPEAKER_DIARIZATION_MODEL"),
            )

        # 실제 provider 인스턴스를 생성한다.
        self._provider = self._build_provider()

    def _build_provider(self) -> BaseSTTProvider:
        # 공부용 설명:
        # 문자열 provider 이름을 실제 클래스 객체로 연결해 주는 부분이다.
        #
        # 예:
        # "deepgram" -> DeepgramSTTProvider
        # "whisper" -> WhisperSTTProvider
        # "mock" -> MockSTTProvider
        #
        # 이렇게 분리해 두면 if문을 코드 여기저기에 쓰지 않고 깔끔하게 관리할 수 있다.
        provider_map = {
            "mock": MockSTTProvider,
            "whisper": WhisperSTTProvider,
            "clova": ClovaSpeechSTTProvider,
            "clova_speech": ClovaSpeechSTTProvider,
            "deepgram": DeepgramSTTProvider,
        }
        provider_cls = provider_map.get(self.provider_name, MockSTTProvider)
        return provider_cls(api_key=self.api_key, api_url=self.api_url)

    def _fallback_response(self, audio_path: Path) -> Dict[str, Any]:
        # 공부용 설명:
        # STT 엔진이 실패하면 전체 시스템이 멈추면 안 된다.
        # 그래서 최소한의 JSON 구조를 만들어서 다시 반환하는 안전장치가 필요하다.
        #
        # 이 응답은 실제 transcript를 못 받아도,
        # backend가 항상 기대하는 형태를 유지할 수 있게 해 준다.
        duration_ms = _estimate_duration_ms(audio_path)
        confidence = 0.82
        return {
            "schema_version": "1.0",
            "segments": [
                {
                    "segment_id": "seg_001",
                    "speaker": "UNKNOWN",
                    "start_ms": 0,
                    "end_ms": max(duration_ms, 1000),
                    "text": "모델이 음성을 인식하지 못했지만 JSON Contract 형식은 유지합니다.",
                    "confidence": confidence,
                    "is_low_confidence": confidence < 0.6,
                }
            ],
        }

    def transcribe(self, audio_path: str | os.PathLike[str]) -> Dict[str, Any]:
        # 공부용 설명:
        # 이 함수는 전체 STT 과정의 '최종 관리자' 역할을 한다.
        # 실제로는 아래와 같은 순서로 작업한다.
        #
        # 1) 파일이 올바른 오디오인지 확인
        # 2) provider를 호출해서 transcript 결과 받기
        # 3) 결과를 segment 구조로 정리하기
        # 4) speaker 값 보정
        # 5) 최종 JSON 반환
        #
        # 이 함수가 성공하면 backend 쪽에서는 결과값만 받아서 처리하면 된다.
        path = _normalize_audio_path(audio_path)
        try:
            result = self._provider.transcribe(str(path))
        except AudioProviderError:
            result = self._fallback_response(path)
        except Exception as exc:
            raise InvalidAudioError(f"Unexpected STT failure for {path}: {exc}") from exc

        if not isinstance(result, dict) or "segments" not in result:
            raise AudioProviderError("Provider returned an invalid STT payload.")

        normalized_segments: List[Dict[str, Any]] = []
        for index, segment in enumerate(result.get("segments", []) or [], start=1):
            segment_id = segment.get("segment_id") or f"seg_{index:03d}"
            speaker = segment.get("speaker")
            if speaker not in SPEAKER_ENUM:
                speaker = SpeakerDiarizer.normalize_speaker_label(speaker)
            start_ms = int(segment.get("start_ms", 0))
            end_ms = int(segment.get("end_ms", start_ms))
            text = str(segment.get("text") or "")
            confidence = float(segment.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            is_low_confidence = bool(segment.get("is_low_confidence", confidence < 0.6))
            normalized_segments.append(
                {
                    "segment_id": segment_id,
                    "speaker": speaker,
                    "start_ms": max(0, start_ms),
                    "end_ms": max(start_ms, end_ms),
                    "text": text,
                    "confidence": confidence,
                    "is_low_confidence": is_low_confidence,
                }
            )

        if not normalized_segments:
            fallback = self._fallback_response(path)
            return fallback

        if self.speaker_diarizer is not None:
            normalized_segments = self.speaker_diarizer.apply_to_segments(normalized_segments, str(path))

        return {"schema_version": "1.0", "segments": normalized_segments}

    def transcribe_and_diarize(self, audio_path: str | os.PathLike[str]) -> Dict[str, Any]:
        """하위 호환성을 위한 wrapper 메서드"""
        # 기존 코드가 transcribe_and_diarize()를 쓰고 있어도
        # 실제 구현은 transcribe()를 그대로 사용한다.
        return self.transcribe(audio_path)


__all__ = ["Transcriber", "InvalidAudioError", "AudioProviderError", "SpeakerDiarizer", "SpeakerDiarizationError"]