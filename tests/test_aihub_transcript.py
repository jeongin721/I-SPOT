# AI-HUB JSON이 I-SPOT Transcript 형식으로 정상 변환되는지 테스트한다.
# 시간 변환, Q/A 화자 매핑, segment_id 생성 등을 검증한다.

from ai.adapters.aihub_transcript import aihub_to_transcript, timestamp_to_ms


SAMPLE = {
    "version": 1,
    "info": {
        "ID": "0016",
        "성별": "남",
        "나이": 10,
        "학년": "고학년",
        "유형구분": "저소득",
        "가정환경": "일반(핵가족 이상)",
        "상담일자": "2023-08-14",
        "평가일시": "2023-08-14",
        "작성자(상담사)": "임상심리사 2급",
        "상호작용 특성(종합)": "협조적",
        "긴장 수준(종합)": "보통",
        "행동 특성(종합)": "||",
        "위기단계": "관찰필요",
        "합계점수": 13,
        "학대의심": "(해당 없음)",
        "행동특성 점수": 0,
        "임상가 종합소견": (
            "상담을 종합해 보면 통증 및 신체적 문제와는 관련이 없으며, "
            "긍정적인 정서와 건강한 관계를 형성하고 있는 것으로 보입니다."
        ),
    },
    "list": [
        {
            "문항": "신체적 불편감",
            "문항합계": 0,
            "위기단계": "정상군",
            "list": [
                {
                    "항목": "통증",
                    "임상가코멘트": {
                        "val": "① 통증에 관련된 특별한 문제가 없어보입니다. [0점]"
                    },
                    "점수": 0,
                    "문제요인": {
                        "val": "없음"
                    },
                    "audio": [
                        {
                            "type": "Q",
                            "text": "최근에 아픈 곳이 있었니?",
                            "wave": "all.wav",
                            "start": "00:00.000",
                            "end": "00:02.230",
                        },
                        {
                            "type": "A",
                            "text": "최근에 아픈 적은 없어요.",
                            "wave": "all.wav",
                            "start": "00:03.680",
                            "end": "00:05.780",
                        },
                    ],
                }
            ],
        }
    ],
}


def test_timestamp_to_ms():
    assert timestamp_to_ms("00:03.680") == 3680
    assert timestamp_to_ms("01:02.500") == 62500


def test_aihub_json_to_transcript():
    transcript = aihub_to_transcript(SAMPLE)

    assert transcript.schema_version == "1.0"
    assert len(transcript.segments) == 2

    counselor = transcript.segments[0]

    assert counselor.segment_id == "seg_001"
    assert counselor.speaker == "COUNSELOR"
    assert counselor.text == "최근에 아픈 곳이 있었니?"
    assert counselor.start_ms == 0
    assert counselor.end_ms == 2230

    child = transcript.segments[1]

    assert child.segment_id == "seg_002"
    assert child.speaker == "CHILD"
    assert child.text == "최근에 아픈 적은 없어요."
    assert child.start_ms == 3680
    assert child.end_ms == 5780