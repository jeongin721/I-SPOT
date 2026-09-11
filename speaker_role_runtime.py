from typing import Any, Dict, List


class RuntimeSpeakerRoleMapper:
    """
    실제 서비스용 speaker role 추정기.

    GT(Q/A) 없이 STT 결과만 보고
    COUNSELOR / CHILD 역할을 추정한다.

    v1 기준:
    - 질문 비율이 더 높은 speaker → COUNSELOR
    - 다른 speaker → CHILD
    - 두 speaker의 질문 비율 차이가 너무 작으면 UNKNOWN
    """

    MIN_QUESTION_RATIO_GAP = 0.20

    @staticmethod
    def _is_question(text: str) -> bool:
        text = (text or "").strip()

        if not text:
            return False

        question_patterns = (
            "?",
            "까",
            "니",
            "어?",
            "야?",
            "있어?",
            "했어?",
            "했니?",
            "인가?",
        )

        return any(
            text.endswith(pattern)
            for pattern in question_patterns
        )

    def _extract_features(
        self,
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:

        speaker_stats = {}

        for segment in segments:
            speaker = segment.get("speaker")
            text = (segment.get("text") or "").strip()

            if (
                not speaker
                or speaker == "UNKNOWN"
                or not text
            ):
                continue

            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    "utterance_count": 0,
                    "question_count": 0,
                    "short_answer_count": 0,
                    "total_chars": 0,
                }

            stats = speaker_stats[speaker]

            stats["utterance_count"] += 1
            stats["total_chars"] += len(text)

            if self._is_question(text):
                stats["question_count"] += 1

            if len(text) <= 10:
                stats["short_answer_count"] += 1

        features = {}

        for speaker, stats in speaker_stats.items():
            count = stats["utterance_count"]

            if count == 0:
                continue

            features[speaker] = {
                "utterance_count": count,
                "question_ratio":
                    stats["question_count"] / count,
                "short_answer_ratio":
                    stats["short_answer_count"] / count,
                "avg_chars":
                    stats["total_chars"] / count,
            }

        return features

    def map_roles(
        self,
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:

        features = self._extract_features(segments)

        speakers = list(features.keys())

        if len(speakers) < 2:
            return {
                speaker: {
                    "role": "UNKNOWN",
                    "confidence": 0.0,
                    **features[speaker],
                }
                for speaker in speakers
            }


        # ---------------------------------------------------------
        # Deepgram이 한 실제 화자를 SPEAKER_2 등으로
        # 잘못 분리하는 경우를 대비한다.
        #
        # 우선 발화 수가 가장 많은 두 speaker를
        # 주요 화자로 선택한다.
        # ---------------------------------------------------------

        main_speakers = sorted(
            speakers,
            key=lambda speaker: features[speaker]["utterance_count"],
            reverse=True,
        )[:2]

        speaker_a = main_speakers[0]
        speaker_b = main_speakers[1]

        ratio_a = features[speaker_a]["question_ratio"]
        ratio_b = features[speaker_b]["question_ratio"]

        question_gap = abs(
            ratio_a - ratio_b
        )

        # 질문 비율 차이가 너무 작으면
        # 강제로 상담자/아동을 결정하지 않음
        if question_gap < self.MIN_QUESTION_RATIO_GAP:
            return {
                speaker_a: {
                    "role": "UNKNOWN",
                    "confidence": round(
                        question_gap,
                        4,
                    ),
                    **features[speaker_a],
                },
                speaker_b: {
                    "role": "UNKNOWN",
                    "confidence": round(
                        question_gap,
                        4,
                    ),
                    **features[speaker_b],
                },
            }

        # 질문 비율이 높은 쪽을 상담자로 추정
        if ratio_a > ratio_b:
            counselor = speaker_a
            child = speaker_b
        else:
            counselor = speaker_b
            child = speaker_a

        result = {}

        for speaker in speakers:

            if speaker == counselor:
                role = "COUNSELOR"
                confidence = question_gap

            elif speaker == child:
                role = "CHILD"
                confidence = question_gap

            else:
                # 주요 두 화자 외의 speaker는
                # diarization 분할 또는 제3 화자 가능성이 있으므로
                # 함부로 CHILD로 합치지 않는다.
                role = "UNKNOWN"
                confidence = 0.0

            result[speaker] = {
                "role": role,
                "confidence": round(
                    confidence,
                    4,
                ),
                **features[speaker],
            }

        return result