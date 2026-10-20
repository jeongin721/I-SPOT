"""
STT Contract v1.0 결과를 오늘 만든 신규 파이프라인(analyze_session 계열)으로
연결하는 진입점.

실제 음성 인식·화자분리 모델은 별도로 제공될 예정이며, 이 모듈은 그 결과가
Contract v1.0 형식(schema_version="1.0", segments[])만 지키면 그대로
연결되도록 만든 어댑터다. 구버전 세부유형 모델을 쓰는 infer_session.py는
그대로 두고 건드리지 않는다.

1차 RoBERTa는 512 토큰 제한이 있어 상담사/아동 대화를 일정 길이로 나눠
chunk 단위로 돌리고, 하나의 chunk에서라도 탐지되면 세션 전체에서
탐지된 것으로 통합한다. 2차 LLM/상담 요약·일지/체크리스트 초안은
토큰 제한이 훨씬 커서 세션 전체 transcript를 한 번에 사용한다.
"""

import threading
import time
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional, Tuple

from ai.adapters.stt_analysis_adapter import validate_stt_result

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    predict_major_types,
)
from ai.modeling.abuse.second_stage_llm import (
    analyze_subtypes,
)
from ai.modeling.abuse.audio_to_counseling_note import (
    DEFAULT_MODEL as DEFAULT_NOTE_MODEL,
    generate_counseling_records,
)
from ai.modeling.abuse.checklist_llm import (
    DEFAULT_MODEL as DEFAULT_CHECKLIST_MODEL,
    generate_checklist_draft,
)
from ai.modeling.abuse.record_draft_llm import (
    build_transcript_citation_text,
    generate_record_draft,
)
from ai.modeling.abuse.protective_factor_llm import (
    generate_protective_factors,
)
from ai.modeling.abuse.severity_llm import (
    build_evidence_block_text,
    rate_severity_from_text,
)
from ai.modeling.abuse.narrative_summary_llm import (
    format_points_for_masking,
    generate_narrative_summary_from_masked_text,
)
from ai.modeling.abuse.session_change import (
    build_session_change_notes,
)
from ai.modeling.abuse.legal_reference_adapter import (
    build_legal_references,
    build_precedent_references,
)
from ai.modeling.abuse.followup_check_llm import (
    format_inputs_for_masking as format_followup_inputs_for_masking,
    generate_followup_check_points_from_masked_text,
)
from ai.modeling.abuse.llm_backend import (
    build_openai_client_and_model,
)
from ai.modeling.abuse.pii_masking import (
    restore_pii,
)
from ai.modeling.abuse.privacy_gateway import (
    mask_for_outbound,
)
from ai.modeling.abuse import case_store


# ============================================================
# 1. 기본 설정
# ============================================================

ABUSE_LABELS = [
    "신체학대",
    "정서학대",
    "성학대",
    "방임",
]

# predict_major_types(input_mode="qa")의 화자 파싱 정규식과
# 맞추기 위해 STT speaker enum을 한국어 화자 표시로 매핑한다.
# GUARDIAN/OTHER/UNKNOWN은 1차/2차 모델이 학습된 형식에 없으므로 제외한다.
SPEAKER_LABEL_KO = {
    "COUNSELOR": "상담사",
    "CHILD": "아동",
}

# 1차 RoBERTa(512 토큰) chunk 분할 기준.
#
# 원래는 stt_analysis_adapter.DEFAULT_MAX_CHARS와 같은 1000자를 썼는데,
# 실제 음성(0280.mp3)으로 확인해 보니 한 청크에 여러 주제/유형이 섞이면
# 모델이 그중 가장 강한 신호 하나만 잡고 나머지를 놓치는 경우가 있었다
# (신체+성학대가 같은 청크에 있었는데 신체학대만 1.00으로 잡히고 성학대는
# 0.03으로 묻힘). 청크를 500자로 줄이면 같은 세션에서 4개 유형이 모두
# 잡히는 것을 확인했다(300자도 동일하게 잘 잡히지만, 청크 수가 늘어나는
# 만큼 1차 호출 수만 늘고 2차 LLM 호출 수는 그대로라 500자로 여유를 뒀다).
MAX_CHUNK_CHARS = 500


# ============================================================
# 2. STT segment → transcript 변환
# ============================================================

def build_qa_transcript_lines(
    segments: List[Dict[str, Any]],
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """
    검증된 STT segment를 (화자표시, 텍스트, 원본segment) 튜플 목록으로 만든다.
    """

    lines = []

    for segment in segments:

        speaker_ko = SPEAKER_LABEL_KO.get(
            segment["speaker"]
        )

        if not speaker_ko:
            continue

        text = segment["text"].strip()

        if not text:
            continue

        lines.append(
            (
                speaker_ko,
                text,
                segment,
            )
        )

    return lines


def build_full_transcript_text(
    lines: List[Tuple[str, str, Dict[str, Any]]],
) -> str:
    """
    세션 전체 transcript 텍스트를 만든다.
    2차 LLM/상담 요약·일지/체크리스트는 이 전체 텍스트를 그대로 쓴다.
    """

    return "\n".join(
        f"{speaker}: {text}"
        for speaker, text, _ in lines
    )


def build_qa_chunks(
    lines: List[Tuple[str, str, Dict[str, Any]]],
    max_chars: int = MAX_CHUNK_CHARS,
) -> List[List[Tuple[str, str, Dict[str, Any]]]]:
    """
    1차 RoBERTa 입력용으로 상담사/아동 줄을 max_chars 단위로 묶는다.
    """

    chunks: List[List[Tuple[str, str, Dict[str, Any]]]] = []

    current: List[Tuple[str, str, Dict[str, Any]]] = []
    current_length = 0

    for speaker, text, segment in lines:

        line = f"{speaker}: {text}"

        additional_length = len(line)

        if current:
            additional_length += 1

        if (
            current
            and current_length + additional_length > max_chars
        ):
            chunks.append(current)

            current = []
            current_length = 0

        current.append(
            (speaker, text, segment)
        )

        current_length += additional_length

    if current:
        chunks.append(current)

    return chunks


def _chunk_to_text(
    chunk: List[Tuple[str, str, Dict[str, Any]]],
) -> str:
    return "\n".join(
        f"{speaker}: {text}"
        for speaker, text, _ in chunk
    )


# ============================================================
# 2.4 "분석하기" 전 빠른 1차 스캔(검수 화면용)
# ============================================================
# 상담사가 "검수 완료 — 분석하기"를 누르기 전, STT 직후 화면에서부터
# 위험 신호가 있는 구간을 바로 보고 재생할 수 있게 한다(2026-10-01
# 추가). LLM 보완체크(_verify_major_types_qa)는 건당 수십 초가 걸려서
# 이 빠른 미리보기 단계에는 쓰지 않는다 — 순수 1차 분류기만 돌린다
# (어차피 "분석하기"를 누르면 LLM 보완체크까지 포함한 정식 분석이 한
# 번 더 돈다 — 이건 그 전 단계의 미리보기일 뿐이다).

def quick_risk_scan(
    stt_result: Dict[str, Any],
) -> Dict[str, List[str]]:
    """
    STT 결과에 1차 분류기만 빠르게 돌려서, segment_id별로 탐지된
    학대유형 목록을 반환한다. 실제 "분석하기"가 쓰는 것과 동일한
    chunk 분할(build_qa_chunks)을 재사용해 일관성을 유지한다.
    """

    try:
        segments = validate_stt_result(stt_result)
    except Exception:
        return {}

    lines = build_qa_transcript_lines(segments)

    if not lines:
        return {}

    chunks = build_qa_chunks(lines)

    risk_by_segment: Dict[str, List[str]] = {}

    for chunk in chunks:
        chunk_prediction = predict_major_types(
            text=_chunk_to_text(chunk),
            input_mode="qa",
        )

        detected_labels = [
            label
            for label in ABUSE_LABELS
            if chunk_prediction.get(label, {}).get("detected", False)
        ]

        if not detected_labels:
            continue

        for _, _, segment in chunk:
            segment_id = str(segment.get("segment_id", ""))
            risk_by_segment.setdefault(segment_id, [])
            for label in detected_labels:
                if label not in risk_by_segment[segment_id]:
                    risk_by_segment[segment_id].append(label)

    return risk_by_segment


# ============================================================
# 2.5 근거(evidence) → 원본 음성 타임스탬프 역매핑
# ============================================================
# 2차 LLM의 evidence_start/evidence_end는 build_full_transcript_text가
# 만든 전체 텍스트 안에서의 문자 위치다. 그 문자 위치가 어떤 STT
# segment(들)에서 나왔는지 되짚어서 start_ms/end_ms를 붙여주면
# 근거 발화를 원본 음성 재생 위치와 연결할 수 있다.

def build_line_char_spans(
    lines: List[Tuple[str, str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    build_full_transcript_text와 완전히 동일한 조립 규칙
    ("화자: 텍스트"를 "\\n"으로 join)으로 각 줄의 문자 구간을 계산한다.
    """

    spans: List[Dict[str, Any]] = []

    cursor = 0

    for speaker, text, segment in lines:
        line_text = f"{speaker}: {text}"

        start_char = cursor
        end_char = cursor + len(line_text)

        spans.append(
            {
                "start_char": start_char,
                "end_char": end_char,
                "segment_id": segment["segment_id"],
                "start_ms": segment["start_ms"],
                "end_ms": segment["end_ms"],
            }
        )

        # build_full_transcript_text가 줄 사이에 "\n" 하나를 넣으므로
        # 다음 줄은 그만큼 뒤에서 시작한다.
        cursor = end_char + 1

    return spans


def _find_spans_for_char_range(
    start_char: int,
    end_char: int,
    line_spans: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        span
        for span in line_spans
        if span["start_char"] < end_char
        and span["end_char"] > start_char
    ]


def link_evidence_timestamps(
    subtype_analysis: Dict[str, Any],
    line_spans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    subtype_analysis 안의 evidence마다 원본 음성 타임스탬프
    (start_ms/end_ms/segment_ids)를 timestamps 필드로 붙인다.

    evidence_verified가 False이거나 문자 위치가 없으면
    timestamps는 None으로 둔다 (근거 자체가 불확실한 상태에서
    잘못된 시간 구간을 링크하지 않기 위함).
    """

    for major_result in subtype_analysis.get(
        "results",
        [],
    ):
        for subtype in major_result.get(
            "subtypes",
            [],
        ):
            for evidence in subtype.get(
                "evidences",
                [],
            ):
                start_char = evidence.get(
                    "evidence_start"
                )

                end_char = evidence.get(
                    "evidence_end"
                )

                if (
                    not evidence.get(
                        "evidence_verified"
                    )
                    or start_char is None
                    or end_char is None
                ):
                    evidence["timestamps"] = None
                    continue

                matches = _find_spans_for_char_range(
                    start_char,
                    end_char,
                    line_spans,
                )

                if not matches:
                    evidence["timestamps"] = None
                    continue

                evidence["timestamps"] = {
                    "start_ms": min(
                        span["start_ms"]
                        for span in matches
                    ),
                    "end_ms": max(
                        span["end_ms"]
                        for span in matches
                    ),
                    "segment_ids": [
                        span["segment_id"]
                        for span in matches
                    ],
                }

    return subtype_analysis


# ============================================================
# 3. 세션 전체 분석
# ============================================================

def _check_deadline(
    deadline: Optional[float],
    stage_name: str,
) -> None:
    """
    deadline(time.monotonic() 기준 마감 시각)이 이미 지났으면 다음 단계를
    시작하지 않고 바로 TimeoutError를 낸다(2026-10-16, backend 요청 —
    AI_TIMEOUT_SECONDS를 넘긴 뒤에도 뒤에서 OpenAI 호출이 계속되던 문제를
    막기 위함). deadline이 None이면 기존과 동일하게 아무 일도 안 한다.
    """

    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError(
            f"{stage_name} 전에 시간 초과"
        )


def analyze_audio_session(
    stt_result: Dict[str, Any],
    client: Any = None,
    note_model: str = DEFAULT_NOTE_MODEL,
    checklist_model: str = DEFAULT_CHECKLIST_MODEL,
    case_id: str = None,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """
    STT Contract v1.0 결과(한 세션)를 1차 → 2차 → 상담 요약·일지 →
    체크리스트 초안까지 오늘 만든 파이프라인으로 분석한다.

    2026-10-02부터 요약/체크리스트도 2차 세부유형 분석과 마찬가지로 항상
    외부 OpenAI로 나간다(MVP 아키텍처가 "GPT+Cloud, 비식별 최소정보만
    외부 전송"으로 통일되면서 로컬 Ollama 서빙을 뺐다). 세션 전체
    (요약/체크리스트)가 같은 OpenAI client 하나를 쓰도록 여기서 한 번만
    만들어 아래로 전달한다. 2차 세부유형 분석은 이 client와 무관하게
    항상 별도의 OpenAI client를 쓴다(infer_abuse_pipeline.analyze_abuse
    참고).

    case_id를 주면 Privacy Gateway Tier 2(등록된 실명 정확매칭)가 2차
    세부유형 분석과 요약/체크리스트 생성 둘 다에 적용된다.

    deadline: time.monotonic() 기준 마감 시각(2026-10-16, backend 요청).
    None이면 기존과 동일하게 동작한다. 넘기면 각 단계를 시작하기 전에
    마감이 지났는지 확인해 TimeoutError를 내고(_check_deadline), 각
    OpenAI 호출에는 남은 시간을 실제 timeout으로 넘긴다
    (_call_llm_with_retry 참고) — 마감을 넘긴 뒤에도 호출이 뒤에서
    계속되는 걸 막는다.
    """

    subtype_model = "gpt-5.6-luna"

    if client is None:
        client, _ = build_openai_client_and_model(
            default_openai_model=note_model,
        )

    segments = validate_stt_result(
        stt_result
    )

    lines = build_qa_transcript_lines(
        segments
    )

    if not lines:
        raise ValueError(
            "분석 가능한 상담사/아동 발화가 없습니다."
        )

    full_text = build_full_transcript_text(
        lines
    )

    # --------------------------------------------------------
    # 1차: chunk 단위로 돌리고, 하나라도 탐지되면
    # 세션 전체에서 탐지된 것으로 통합한다.
    # --------------------------------------------------------

    chunks = build_qa_chunks(
        lines
    )

    session_detected = {
        label: False
        for label in ABUSE_LABELS
    }

    chunk_results = []

    _check_deadline(deadline, "1차 분석")

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        chunk_prediction = predict_major_types(
            text=_chunk_to_text(chunk),
            input_mode="qa",
        )

        for label in ABUSE_LABELS:
            if chunk_prediction.get(
                label,
                {},
            ).get(
                "detected",
                False,
            ):
                session_detected[label] = True

        chunk_results.append(
            {
                "chunk_index": index,
                "segment_ids": [
                    segment["segment_id"]
                    for _, _, segment in chunk
                ],
                "has_low_confidence": any(
                    segment["is_low_confidence"]
                    for _, _, segment in chunk
                ),
                "major_types": chunk_prediction,
            }
        )

    major_types = {
        label: {"detected": session_detected[label]}
        for label in ABUSE_LABELS
    }

    detected_major_types = [
        label
        for label in ABUSE_LABELS
        if session_detected[label]
    ]

    # --------------------------------------------------------
    # 2차: 세션 전체 transcript로 한 번에 (LLM은 512 토큰 제한 없음)
    # --------------------------------------------------------

    known_identifiers = (
        case_store.get_known_identifiers(case_id) if case_id else []
    )

    if detected_major_types:
        # 2차는 항상 외부 OpenAI로 나가므로(infer_abuse_pipeline.analyze_abuse와
        # 동일 — 이 파일은 예전에 이 단계가 빠져 있어서 원문이 그대로
        # 나가고 있었다, 2026-09-30 발견 후 추가) 별도의 OpenAI client를
        # 쓰고 Privacy Gateway(차단형 검증)를 거친다.
        subtype_client, subtype_model = build_openai_client_and_model(
            default_openai_model=subtype_model,
        )

        masked_full_text, entity_map = mask_for_outbound(
            full_text, known_identifiers=known_identifiers
        )

        _check_deadline(deadline, "2차 세부유형 분석")

        subtype_result = analyze_subtypes(
            text=masked_full_text,
            major_types=detected_major_types,
            client=subtype_client,
            model=subtype_model,
            deadline=deadline,
        )

        # link_evidence_timestamps는 원문 line_spans와 인용문을 대조해
        # 타임스탬프를 붙이므로, 마스킹 토큰이 남아 있으면 대조에
        # 실패한다 — 대조 전에 원문으로 복원한다.
        subtype_result = restore_pii(
            subtype_result,
            entity_map,
        )

        line_spans = build_line_char_spans(
            lines
        )

        subtype_result = link_evidence_timestamps(
            subtype_result,
            line_spans,
        )
    else:
        subtype_result = {
            "results": [],
            "note": "탐지된 대분류 없음",
        }

    # --------------------------------------------------------
    # 상담 요약/일지 + 체크리스트 초안 + 기록 초안 + 보호 요인
    # --------------------------------------------------------
    # 2026-10-16(Mingyu 제안, 처리시간 측정 뒤): 이 네 호출은 서로의
    # 결과를 쓰지 않는다(infer_audio_session.py 원래 556~645행대
    # 참고) — 순서대로 돌리면 ~45초가 걸리던 걸 동시에 돌려 가장 느린
    # 호출(보호요인, ~18초) 수준으로 줄인다. "향후 계획"은 기록 초안에서
    # 뺐다 — 질문 추천은 자유생성보다 검증된 질문 은행에서 RAG로 찾는
    # 게 안전한데 지금 그 은행이 없다(record_draft_llm 모듈 docstring
    # 참고). 은행이 생기면 그때 추가한다. 보호요인은 위험신호 분석
    # (subtype_result)과 완전히 분리된 호출이라 여기 실패해도 위험신호/
    # 기록초안 결과에는 영향이 없다(protective_factor_llm.py 모듈
    # docstring 참고).

    # 요약/체크리스트도 이제 2차처럼 외부로 나가므로 mask_pii()의 최선형
    # 마스킹이 아니라 Privacy Gateway의 차단형 검증(mask_for_outbound)을
    # 거친다.
    masked_full_text, entity_map = mask_for_outbound(
        full_text, known_identifiers=known_identifiers
    )

    citation_text = build_transcript_citation_text(segments)

    masked_citation_text, citation_entity_map = mask_for_outbound(
        citation_text, known_identifiers=known_identifiers
    )

    total_ms = max(
        (segment.get("end_ms", 0) for segment in segments),
        default=0,
    )
    duration_label = (
        f"녹취 {total_ms // 60000}분" if total_ms else ""
    )
    session_overview = " · ".join(
        part
        for part in [duration_label, f"발화 {len(segments)}건"]
        if part
    )

    _check_deadline(
        deadline,
        "상담 요약·일지/체크리스트/기록초안/보호요인 생성",
    )

    # use_correction_hint=False: build_correction_hint_text()가 과거 회차
    # 원문 인용을 mask_for_outbound 없이 시스템 프롬프트에 붙이므로, 외부
    # LLM으로 나가는 이 경로에서는 끈다(2026-10-16 Mingyu 리뷰, 높음 4번).
    executor = ThreadPoolExecutor(max_workers=4)
    # 넷 중 하나가 fail-fast로 먼저 실패해도, 아직 돌던 호출이 재시도를
    # 계속 보내던 문제(2026-10-20 Mingyu 리뷰) — 실패가 확정되면 이
    # 신호를 켜서, 아직 재시도 전인 호출들이 다음 시도를 시작하기 전에
    # 바로 포기하게 한다(second_stage_llm._call_llm_with_retry 참고).
    stop_event = threading.Event()

    try:
        counseling_future = executor.submit(
            generate_counseling_records,
            client=client,
            transcript=masked_full_text,
            model=note_model,
            deadline=deadline,
            stop_event=stop_event,
        )
        checklist_future = executor.submit(
            generate_checklist_draft,
            text=masked_full_text,
            client=client,
            model=checklist_model,
            use_correction_hint=False,
            deadline=deadline,
            stop_event=stop_event,
        )
        record_draft_future = executor.submit(
            generate_record_draft,
            client=client,
            model=note_model,
            masked_transcript_text=masked_citation_text,
            segments=segments,
            subtype_analysis=subtype_result,
            session_overview=session_overview,
            deadline=deadline,
            stop_event=stop_event,
        )
        protective_factors_future = executor.submit(
            generate_protective_factors,
            client=client,
            model=note_model,
            masked_transcript_text=masked_citation_text,
            segments=segments,
            deadline=deadline,
            stop_event=stop_event,
        )

        all_futures = [
            counseling_future,
            checklist_future,
            record_draft_future,
            protective_factors_future,
        ]

        # 넷 중 하나라도 실패하면(record_draft/protective_factors는 내부에서
        # 이미 실패를 삼키므로 사실상 counseling_records/checklist_draft만
        # 해당) 나머지가 아직 안 끝났어도 기다리지 않고 바로 실패 처리한다
        # (2026-10-19 Mingyu 리뷰) — wait(..)가 반환하자마자 shutdown을
        # wait=False로 불러 이미 끝난 것 말고는 안 기다린다. 이미 시작된
        # 스레드 자체를 강제로 멈추지는 못하지만(파이썬 한계), 이 함수는
        # 더 기다리지 않고 바로 돌아간다 — 그 스레드들도 각자 deadline으로
        # 묶여 있어 결국 끝난다.
        done, _not_done = wait(all_futures, return_when=FIRST_EXCEPTION)

        # wait()가 돌아온 시점(전부 끝났거나 하나가 실패했거나)에 바로
        # 켠다 — 전부 성공했으면 아무도 이 신호를 다시 보지 않으니
        # 무해하고, 하나가 실패했으면 아직 재시도 전인 나머지가 바로
        # 포기하게 된다.
        stop_event.set()

        for future in done:
            future.result()

        counseling_records = counseling_future.result()
        checklist_draft = checklist_future.result()
        record_draft = record_draft_future.result()
        protective_factors = protective_factors_future.result()
    finally:
        # cancel_futures는 Python 3.9+에서만 있다(이 저장소는 환경마다
        # 3.8/3.9/3.12가 섞여 있다) — 없으면 그냥 wait=False만 쓴다.
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            executor.shutdown(wait=False)

    counseling_records = restore_pii(
        counseling_records,
        entity_map,
    )
    checklist_draft = restore_pii(
        checklist_draft,
        entity_map,
    )
    record_draft = restore_pii(
        record_draft,
        citation_entity_map,
    )
    protective_factors = restore_pii(
        protective_factors,
        citation_entity_map,
    )

    # --------------------------------------------------------
    # 관련 법령(law/ 포팅, 2026-10-19 추가 · 2026-10-20 law/만 직접 호출로 변경)
    # --------------------------------------------------------
    # 탐지된 학대유형마다 그 유형의 위험 신호 근거 발화를 모아 랭킹한다
    # (세그먼트마다 부르지 않는 이유는 legal_reference_adapter.py 모듈
    # docstring 참고). LAW_API_OC가 없거나 law.go.kr 조회가 실패하면
    # 해당 부분만 빈 값으로 돌아온다 — 실패해도 세션 분석 전체를 막지
    # 않는다.

    _check_deadline(deadline, "관련 법령 조회")

    try:
        legal_references, legal_reference_warnings = build_legal_references(
            detected_major_types=detected_major_types,
            risk_signal_points=record_draft.get("risk_signal_points", []),
            deadline=deadline,
        )
    except Exception:
        # 예외 문구에 law.go.kr 요청 주소(OC 인증값 포함)가 섞여 있을
        # 수 있어 그대로 노출하지 않는다(2026-10-20 Mingyu 지적).
        legal_references = []
        legal_reference_warnings = ["관련 법령을 불러오지 못했습니다."]

    # --------------------------------------------------------
    # 유사 판례(jeongin님의 feature/rag 판례 색인 포팅, 2026-10-20 추가)
    # --------------------------------------------------------
    # 판례 색인(rag_storage/chroma, law_cache/precedent_index.json)이 이
    # 환경에 없거나 판례 API 사용 신청 전이면 빈 값 + 경고로 돌아온다 —
    # 실패해도 세션 분석 전체를 막지 않는다(legal_reference_adapter.py
    # 모듈 docstring "유사 판례" 절 참고).

    _check_deadline(deadline, "유사 판례 조회")

    try:
        precedent_references, precedent_reference_warnings = (
            build_precedent_references(
                detected_major_types=detected_major_types,
                risk_signal_points=record_draft.get("risk_signal_points", []),
                known_identifiers=known_identifiers,
                deadline=deadline,
            )
        )
    except Exception:
        precedent_references = []
        precedent_reference_warnings = ["유사 판례를 불러오지 못했습니다."]

    # --------------------------------------------------------
    # 상담 요약 문단 종합(2026-10-13 추가)
    # --------------------------------------------------------
    # 이미 만든 보호요인/위험신호를 자연스러운 문단으로 "다시 쓰기"만
    # 한다 — 새 사실을 추가하지 않는다. narrative_summary_llm.py
    # 모듈 docstring 참고(지금은 이번 세션 1개 분량만, 여러 회차를
    # 가로지르는 종합은 case_store 쪽 작업이 더 필요해 범위 밖).
    #
    # protective_factors/risk_signal_points는 이 시점에 이미
    # restore_pii로 실명이 복원된 상태라, 외부 LLM에 보내기 전에
    # 여기서 다시 마스킹한다(narrative_summary_llm.py의 PII 마스킹
    # 설계 결정 참고).

    narrative_combined = format_points_for_masking(
        protective_factors,
        record_draft.get("risk_signal_points", []),
    )

    masked_narrative_combined, narrative_entity_map = mask_for_outbound(
        narrative_combined, known_identifiers=known_identifiers
    )

    _check_deadline(deadline, "강점·위험 서사 요약 생성")

    narrative_summary = generate_narrative_summary_from_masked_text(
        client=client,
        model=note_model,
        masked_combined_text=masked_narrative_combined,
        deadline=deadline,
    )

    narrative_summary = restore_pii(
        narrative_summary, narrative_entity_map
    )

    narrative_summary["strengths_citations"] = sorted(
        {
            str(sid)
            for p in protective_factors
            for sid in (p.get("segment_ids") or [])
        }
    )
    narrative_summary["risks_citations"] = sorted(
        {
            str(sid)
            for p in record_draft.get("risk_signal_points", [])
            for sid in (p.get("segment_ids") or [])
        }
    )

    record_draft["narrative_summary"] = narrative_summary

    # --------------------------------------------------------
    # 유형별 심각도("유형별 위험도" 화면, 2026-10-13 추가, 검수 전 초안)
    # --------------------------------------------------------
    # severity_llm.py 모듈 docstring 참고 — subtype_result는 이 시점에
    # 이미 restore_pii로 실명이 복원된 상태라(515행 근처 link_evidence_
    # timestamps 때문에 복원이 먼저 필요했음), 외부 LLM에 보내기 전에
    # 여기서 다시 마스킹한다.

    severity_evidence_blocks = build_evidence_block_text(
        subtype_result
    )

    severity_ratings = []

    if severity_evidence_blocks:
        severity_major_types = list(severity_evidence_blocks.keys())

        severity_text = "\n\n".join(
            f"[{major_type}]\n{block}"
            for major_type, block in severity_evidence_blocks.items()
        )

        masked_severity_text, severity_entity_map = mask_for_outbound(
            severity_text, known_identifiers=known_identifiers
        )

        _check_deadline(deadline, "심각도 평가")

        severity_ratings = rate_severity_from_text(
            client=client,
            model=note_model,
            major_types=severity_major_types,
            masked_evidence_text=masked_severity_text,
            deadline=deadline,
        )

        severity_ratings = restore_pii(
            severity_ratings, severity_entity_map
        )

    # --------------------------------------------------------
    # 회차 간 진술 변화("상담 요약" 화면의 "(안전관련) 조사 후 변화된
    # 사항", 2026-10-14 추가) — session_change.py 모듈 docstring 참고,
    # LLM을 쓰지 않는 순수 텍스트 비교다. 이 세션이 case_store에 아직
    # 저장되기 전이라(저장은 이 함수가 끝난 뒤 호출부에서 한다),
    # list_sessions_for_case가 돌려주는 건 전부 "이전" 회차뿐이다.
    session_change_notes: List[str] = []
    current_round_label = ""

    if case_id:
        approved_sessions = [
            session
            for session in case_store.list_sessions_for_case(
                case_id
            )
            if session.get("status") == "approved"
        ]

        current_round_label = f"{len(approved_sessions) + 1}회차"

        if approved_sessions:
            previous_session = approved_sessions[-1]

            session_change_notes = build_session_change_notes(
                current_subtype_analysis=subtype_result,
                previous_session_row=previous_session,
                previous_round_label=f"{len(approved_sessions)}회차",
                current_round_label=current_round_label,
            )

    # --------------------------------------------------------
    # 다음 상담에서 확인할 것("유형별 위험도" 화면, 2026-10-14 추가,
    # 같은 날 재설계 — followup_check_llm.py 모듈 docstring 참고)
    # --------------------------------------------------------
    # 질문 문구를 만들지 않고 "무엇이 불확실하거나 확인이 안 됐는지"만
    # 서술하게 범위를 제한했다. 회차 간 진술 변화는 "상담 요약"
    # 화면에 이미 따로 나오므로(조사 후 변화된 사항) 여기 다시 섞지
    # 않는다 — 중복이라 치웠다. segments/record_draft는 이 시점에
    # 이미 restore_pii로 실명이 복원된 상태라 외부로 보내기 전에
    # 여기서 다시 마스킹한다.

    followup_masked_text, followup_entity_map = mask_for_outbound(
        format_followup_inputs_for_masking(
            segments,
            record_draft.get("child_statement_points", []),
            record_draft.get("risk_signal_points", []),
        ),
        known_identifiers=known_identifiers,
    )

    _check_deadline(deadline, "다음 상담 확인사항 생성")

    followup_check_points = generate_followup_check_points_from_masked_text(
        client=client,
        model=note_model,
        masked_combined_text=followup_masked_text,
        deadline=deadline,
    )

    followup_check_points = restore_pii(
        followup_check_points, followup_entity_map
    )

    _check_deadline(deadline, "결과 조립")

    return {
        "full_text": full_text,
        "segments": segments,
        "major_types": major_types,
        "detected_major_types": detected_major_types,
        "subtype_analysis": subtype_result,
        "counseling_summary": counseling_records[
            "counseling_summary"
        ],
        "counseling_note": counseling_records[
            "counseling_note"
        ],
        "counseling_record_model": note_model,
        "checklist_draft": checklist_draft,
        "record_draft": record_draft,
        "protective_factors": protective_factors,
        "legal_references": legal_references,
        "legal_reference_warnings": legal_reference_warnings,
        "precedent_references": precedent_references,
        "precedent_reference_warnings": precedent_reference_warnings,
        "severity_ratings": severity_ratings,
        "session_change_notes": session_change_notes,
        "current_round_label": current_round_label,
        "followup_check_points": followup_check_points,
        "chunk_results": chunk_results,
    }


# ============================================================
# 4. 데모
# ============================================================

if __name__ == "__main__":
    import json

    sample_stt_result = {
        "schema_version": "1.0",
        "segments": [
            {
                "segment_id": "seg_001",
                "speaker": "COUNSELOR",
                "text": "아빠가 어떻게 했어?",
                "start_ms": 0,
                "end_ms": 2000,
                "confidence": 0.95,
            },
            {
                "segment_id": "seg_002",
                "speaker": "CHILD",
                "text": "아빠가 막대기로 제 팔을 여러 번 때렸어요.",
                "start_ms": 2200,
                "end_ms": 5000,
                "confidence": 0.92,
            },
            {
                "segment_id": "seg_003",
                "speaker": "COUNSELOR",
                "text": "또 다른 일도 있었어?",
                "start_ms": 5200,
                "end_ms": 6500,
                "confidence": 0.96,
            },
            {
                "segment_id": "seg_004",
                "speaker": "CHILD",
                "text": "저번에는 벨트로 허벅지를 때렸어요.",
                "start_ms": 6700,
                "end_ms": 9000,
                "confidence": 0.60,
                "is_low_confidence": True,
            },
        ],
    }

    result = analyze_audio_session(
        stt_result=sample_stt_result
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
