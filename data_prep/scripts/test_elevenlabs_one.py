import json
import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs


PROJECT_ROOT = Path(__file__).resolve().parents[2]

ENV_PATH = PROJECT_ROOT / ".env"

TS_ZIP = Path(
    r"C:\Users\USER\Desktop\헬스케어 4조\024.아동·청소년_상담_데이터"
    r"\3.개방데이터\1.데이터\Training\01.원천데이터\TS_in.zip"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data_prep"
    / "evaluation"
    / "elevenlabs"
    / "outputs"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# 우선 Deepgram에서 문제가 있었던 샘플 하나로 테스트
SAMPLE_ID = "3140"


def find_mp3_in_zip(
    zf: zipfile.ZipFile,
    sample_id: str,
):
    candidates = []

    for name in zf.namelist():

        if not name.lower().endswith(".mp3"):
            continue

        stem = Path(name).stem

        if stem == sample_id:
            return name

        if sample_id in stem:
            candidates.append(name)

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) > 1:
        print(
            f"[경고] 후보 MP3가 여러 개입니다: "
            f"{candidates}"
        )

        return candidates[0]

    return None


def obj_to_dict(obj):

    if obj is None:
        return None

    if isinstance(
        obj,
        (str, int, float, bool)
    ):
        return obj

    if isinstance(
        obj,
        list
    ):
        return [
            obj_to_dict(x)
            for x in obj
        ]

    if isinstance(
        obj,
        dict
    ):
        return {
            k: obj_to_dict(v)
            for k, v in obj.items()
        }

    if hasattr(
        obj,
        "model_dump"
    ):
        return obj_to_dict(
            obj.model_dump()
        )

    if hasattr(
        obj,
        "dict"
    ):
        return obj_to_dict(
            obj.dict()
        )

    if hasattr(
        obj,
        "__dict__"
    ):
        return {
            k: obj_to_dict(v)
            for k, v
            in vars(obj).items()
            if not k.startswith("_")
        }

    return str(obj)


def main():

    load_dotenv(
        ENV_PATH
    )

    api_key = os.getenv(
        "ELEVENLABS_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY가 "
            ".env에 없습니다."
        )

    client = ElevenLabs(
        api_key=api_key
    )

    print("=" * 70)
    print(
        "I-SPOT ElevenLabs "
        "Scribe v2 단일 샘플 테스트"
    )
    print("=" * 70)

    print(
        f"샘플 ID: {SAMPLE_ID}"
    )

    with zipfile.ZipFile(
        TS_ZIP,
        "r"
    ) as zf:

        mp3_name = find_mp3_in_zip(
            zf,
            SAMPLE_ID
        )

        if mp3_name is None:
            raise FileNotFoundError(
                f"{SAMPLE_ID} MP3를 "
                f"ZIP에서 찾지 못했습니다."
            )

        print(
            f"MP3: {mp3_name}"
        )

        audio_bytes = zf.read(
            mp3_name
        )

    print(
        f"오디오 크기: "
        f"{len(audio_bytes) / 1024 / 1024:.2f} MB"
    )

    print()
    print(
        "ElevenLabs Scribe v2 호출 중..."
    )

    response = (
        client.speech_to_text.convert(
            file=audio_bytes,
            model_id="scribe_v2",
            language_code="kor",
            diarize=True,
            tag_audio_events=False,
        )
    )

    data = obj_to_dict(
        response
    )

    output_path = (
        OUTPUT_DIR
        / f"{SAMPLE_ID}_elevenlabs.json"
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            default=str
        )

    print()
    print(
        "API 호출 성공"
    )

    print(
        f"저장 위치: "
        f"{output_path}"
    )

    print()

    if isinstance(
        data,
        dict
    ):

        print(
            "[최상위 key]"
        )

        for key in data.keys():
            print(
                f"  - {key}"
            )

        print()

        text = data.get(
            "text"
        )

        if text:

            print(
                "[전체 transcript 앞 500자]"
            )

            print(
                str(text)[:500]
            )

            print()

        words = data.get(
            "words",
            []
        )

        print(
            f"[word 개수] "
            f"{len(words)}"
        )

        print()
        print(
            "[앞 30개 word]"
        )

        for word in words[:30]:

            if not isinstance(
                word,
                dict
            ):
                print(
                    word
                )
                continue

            print(
                f"type={word.get('type')} | "
                f"text={word.get('text')} | "
                f"speaker_id={word.get('speaker_id')} | "
                f"start={word.get('start')} | "
                f"end={word.get('end')}"
            )

        speaker_ids = []

        for word in words:

            if not isinstance(
                word,
                dict
            ):
                continue

            speaker_id = word.get(
                "speaker_id"
            )

            if (
                speaker_id is not None
                and speaker_id
                not in speaker_ids
            ):
                speaker_ids.append(
                    speaker_id
                )

        print()
        print(
            "[감지된 speaker_id]"
        )

        print(
            speaker_ids
        )

        print(
            f"speaker 수: "
            f"{len(speaker_ids)}"
        )

    print()
    print("=" * 70)
    print(
        "테스트 완료"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()