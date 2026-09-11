import json

from ai.adapters.aihub_transcript import aihub_to_transcript
from ai.services.summary_service import summarize_consultation


SAMPLE = {
    "version": 1,
    "info": {
        "ID": "SYNTHETIC_001"
    },
    "list": [
        {
            "문항": "가정생활",
            "문항합계": 0,
            "위기단계": "정상군",
            "list": [
                {
                    "항목": "가족관계",
                    "점수": 0,
                    "audio": [
                        {
                            "type": "Q",
                            "text": "집에서는 요즘 어떻게 지내?",
                            "wave": "all.wav",
                            "start": "00:00.000",
                            "end": "00:02.000",
                        },
                        {
                            "type": "A",
                            "text": "동생이랑 자주 싸우기는 하는데 엄마랑은 이야기를 많이 해요.",
                            "wave": "all.wav",
                            "start": "00:03.000",
                            "end": "00:07.000",
                        },
                        {
                            "type": "Q",
                            "text": "요즘 힘들거나 걱정되는 건 있어?",
                            "wave": "all.wav",
                            "start": "00:08.000",
                            "end": "00:10.000",
                        },
                        {
                            "type": "A",
                            "text": "학교 숙제가 많아서 조금 스트레스 받아요.",
                            "wave": "all.wav",
                            "start": "00:11.000",
                            "end": "00:14.000",
                        },
                    ],
                }
            ],
        }
    ],
}


transcript = aihub_to_transcript(SAMPLE)

result = summarize_consultation(transcript)

print(
    json.dumps(
        result.model_dump(),
        ensure_ascii=False,
        indent=2,
    )
)