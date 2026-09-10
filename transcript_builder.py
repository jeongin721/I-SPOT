from typing import Any, Dict, List


class TranscriptBuilder:
    """
    I-SPOT STT 결과와 Runtime Speaker Role Mapping을 이용하여
    팀 공용 Transcript Schema에 맞는 데이터를 생성한다.

    역할:
    - SPEAKER_0 / SPEAKER_1 등의 STT 화자 ID를
      COUNSELOR / CHILD / UNKNOWN 등의 역할로 변환한다.
    - STT 내부 분석용 필드(words, is_low_confidence 등)는
      팀 공용 Transcript에서는 제외한다.
    - 원본 STT 데이터는 수정하지 않는다.
    """

    ALLOWED_ROLES = {
        "COUNSELOR",
        "CHILD",
        "GUARDIAN",
        "OTHER",
        "UNKNOWN",
    }

    def build(
        self,
        stt_data: Dict[str, Any],
        role_mapping: Dict[str, Any],
    ) -> Dict[str, Any]:

        segments = stt_data.get("segments", [])

        transcript_segments: List[Dict[str, Any]] = []

        for segment in segments:

            original_speaker = str(
                segment.get("speaker", "UNKNOWN")
            )

            # RuntimeSpeakerRoleMapper 결과에서
            # 해당 SPEAKER_n의 역할을 가져온다.
            role_info = role_mapping.get(
                original_speaker,
                {},
            )

            role = role_info.get(
                "role",
                "UNKNOWN",
            )

            # 팀 공용 Schema에서 허용하지 않는 값이 들어오면
            # 안전하게 UNKNOWN 처리한다.
            if role not in self.ALLOWED_ROLES:
                role = "UNKNOWN"

            transcript_segment = {
                "segment_id": str(
                    segment.get(
                        "segment_id",
                        "",
                    )
                ),
                "speaker": role,
                "start_ms": int(
                    segment.get(
                        "start_ms",
                        0,
                    )
                ),
                "end_ms": int(
                    segment.get(
                        "end_ms",
                        0,
                    )
                ),
                "text": str(
                    segment.get(
                        "text",
                        "",
                    )
                ).strip(),
                "confidence": float(
                    segment.get(
                        "confidence",
                        0.0,
                    )
                ),
            }

            transcript_segments.append(
                transcript_segment
            )

        return {
            "schema_version": "1.0",
            "segments": transcript_segments,
        }