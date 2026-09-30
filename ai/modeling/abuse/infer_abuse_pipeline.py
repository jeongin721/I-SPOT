"""
1차 RoBERTa 대분류 모델, 2차 LLM 세부유형 분석, 상담 요약·상담일지 생성,
서식 체크리스트 초안 생성까지 하나로 묶는 전체 세션 파이프라인.

입력 유형(input_mode)에 따라 1차 모델 경로만 다르게 타고,
2차 세부유형 분석/상담 요약·상담일지/체크리스트 초안은 입력 유형과
무관하게 원문 텍스트만으로 동일하게 동작한다.

note(상담일지/서술형 텍스트) 입력용 1차 모델은 아직 없으므로
input_mode="note"는 이번 범위에 포함하지 않는다.

체크리스트 초안(checklist_draft)의 모든 제안 항목은 원문 근거가 있을 때만
포함되며, 높음/보통/낮음 같은 등급·점수는 절대 AI가 확정하지 않는다.
모든 제안은 상담사가 확인·수정·승인해야 하는 "AI 제안" 상태다.
"""

import json

from openai import OpenAI

from ai.modeling.abuse.infer_abuse_v3_adapter import (
    predict_major_types,
)
from ai.modeling.abuse.second_stage_llm import (
    analyze_subtypes,
    SUBTYPE_DEFINITIONS,
    _call_llm_with_retry,
)
from ai.modeling.abuse.audio_to_counseling_note import (
    DEFAULT_MODEL as DEFAULT_NOTE_MODEL,
    generate_counseling_records,
)
from ai.modeling.abuse.checklist_llm import (
    DEFAULT_MODEL as DEFAULT_CHECKLIST_MODEL,
    generate_checklist_draft,
)
from ai.modeling.abuse.pii_masking import (
    mask_pii,
    restore_pii,
)
from ai.modeling.abuse.llm_backend import (
    build_llm_client_and_model,
)


# ============================================================
# 1. note 모드 1차 결과 LLM 보완 체크
# ============================================================
# note 전용 1차 모델(roberta_abuse_note_v1)의 학습 데이터는 사례마다
# 유형을 하나만 붙여놨고(복합유형 동시 라벨 0건), 그래서 실제로 두 유형
# 이상이 섞인 글에서는 가장 강한 유형 하나만 확신하고 나머지는 확률이
# 크게 낮게 나오는 경향이 있다(예: 성학대 98.8% vs 정서학대 8.3%).
#
# 재학습 전까지는 1차가 놓친 유형을 LLM이 한 번 더 훑어보게 해서
# 이 blind spot을 보완한다. qa/child_only는 1차 정확도가 이미 높아
# (Macro F1 0.94+) 이 보완 체크를 적용하지 않는다.

def _screen_missed_major_types(
    text: str,
    client: OpenAI,
    model: str,
    already_detected: list,
) -> list:
    candidates = [
        label
        for label in SUBTYPE_DEFINITIONS.keys()
        if label not in already_detected
    ]

    if not candidates:
        return []

    # 대분류명만 답하라고 강하게 못박으면 모델이 오히려 과도하게
    # 보수적으로 변해서(제약이 많아질수록 "애매하다"며 회피) 놓치는
    # 사례가 늘었다. 반대로 세부유형까지 자유롭게 답하게 하면 정확도가
    # 높아지므로, 여기서는 세부유형 단위로 자유롭게 답하게 하고
    # subtype_to_major 매핑으로 대분류로 환산한다.
    definitions_text = "\n\n".join(
        label
        + ": "
        + " / ".join(
            f"{subtype}({description})"
            for subtype, description in SUBTYPE_DEFINITIONS[label].items()
        )
        for label in candidates
    )

    # 보완 체크가 신체학대를 과하게 추가하는 문제(로컬 qwen3:14b로 판례집 85건에서
    # 신체학대 오탐 5건 -> 21건)를 줄이기 위한 규칙. 오탐 16건 중 13건은 아동의 몸에
    # 가해진 행위가 없는데 신체학대로 잡힌 경우였다(부모 간 폭행을 본 것, 문자·말로만 한
    # 위협, 방치, 욕설). 다른 유형에는 제약을 더하지 않는다(제약이 많으면 놓치는 사례가
    # 늘어난 전례가 위에 있다).
    #
    # "위험한 물질을 먹임" 예시는 뺐다 — "강제로 술을 마시게 함"을 여기 걸리게
    # 해서, 우리 분류상 정서학대(통제·강요)인 사례를 신체학대로 잘못 추가하는
    # 원인이었다(테스트 30건 중 1건, P013).
    #
    # "부모 등 다른 사람이 맞는 것을 본 경우"는 이미 있었는데도 로컬 모델이
    # 안 지킨 사례가 추가로 확인됐다(P012: 아빠가 엄마를 때리는 걸 본 아동에게
    # 신체학대를 잘못 추가, P102: 다른 아이들이 피해아동을 때린 것을 시설장의
    # 신체학대로 잘못 추가). 추상적인 규칙만으로는 부족해서, 구체적인 예시를
    # 붙이고 "누구의 몸이냐"를 직접 되묻는 문장으로 강화했다.
    extra_rules = ""
    if "신체학대" in candidates:
        # 조건 2를 "지금 판단 대상인 어른 본인인가"로 좁게 쓰면 P040처럼
        # 실제로 아동을 때린 사람(친부)과 이 판결에서 유죄로 다투는 사람
        # (방임 혐의의 친모)이 다른 경우를 놓친다. 우리가 필요한 건 "이
        # 재판에서 누가 기소됐는가"가 아니라 "때린 사람이 보호자/교사 등
        # 책임 있는 어른인가, 또래 아동인가"이므로 그 기준으로 고쳤다.
        extra_rules = """
신체학대는 보호자·교사·시설장 등 아동에 대해 책임 있는 어른이 아동 본인의
몸에 직접 가한 행위(때림, 밀침, 붙잡아 끎, 도구 사용 등)가 원문에 있을 때만
해당한다. 원문에 폭행 장면이 나와도 아래 두 조건 중 하나라도 아니면 신체학대가
아니다:
1) 맞은 사람이 아동 본인인가? — 예: 아빠가 엄마를 때리는 것을 아동이 지켜본
   경우는 맞은 사람이 아동이 아니므로 신체학대가 아니다(정서학대의 폭력상황
   노출에 해당한다).
2) 때린 사람이 보호자·교사·시설장 등 아동에 대해 책임 있는 어른인가, 아니면
   또래 아동(다른 아이)인가? — 예: 다른 아이들이 아동을 때렸고 시설장·교사
   등 어른은 그걸 막지 않고 방치만 한 경우, 때린 사람이 또래 아동이므로 그
   어른에게는 신체학대가 아니라 방임(보호 의무를 다하지 않음)을 적용한다.
   반대로 부모·교사·시설장 등 책임 있는 어른 본인이 직접 때렸다면, 이 사건의
   유죄 판단이 다른 사람(예: 방임 혐의를 받은 다른 보호자)을 향해 있어도
   신체학대에 해당한다.
그 외에 신체학대가 아닌 경우:
- 말이나 문자로만 한 협박·위협·욕설, 집 밖으로 내보냄, 방치, 유기
- 붙잡거나 억지로 벌리는 등 몸에 손을 대지 않고, 말로만 술이나 음식을
  마시게/먹게 시킨 경우 (몸을 붙잡고 억지로 먹인 경우는 신체학대에 해당한다)
신체학대로 판단하기 전에 "누가 때렸고, 누가 맞았는가? 둘 다 맞는 사람들인가?"를
먼저 확인해라.
"""

    system_prompt = f"""다음 학대유형 정의를 참고해서, 상담일지 원문에 각 유형에 해당하는
내용이 있는지 판단해줘.

{definitions_text}
{extra_rules}
원문을 읽고, 위 유형 중 원문 표현으로 명확히 뒷받침되는 유형이 있으면
그 유형명을 배열에 넣어서 JSON으로만 답해:
{{"types": []}}
"""

    user_prompt = text

    try:
        parsed = _call_llm_with_retry(
            client=client,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_retries=2,
            timeout_seconds=180.0,
        )
    except Exception:
        # 보완 체크 실패는 1차 결과를 그대로 살리고 무시한다.
        return []

    additional = parsed.get(
        "types",
        [],
    )

    # 대분류명 자체가 올 수도 있고(모델이 그렇게 답한 경우),
    # 세부유형명이 올 수도 있어서(의도한 정상 경로) 세부유형 ->
    # 대분류로 매핑해 최종 대분류 목록으로 환산한다.
    subtype_to_major = {
        subtype: label
        for label in candidates
        for subtype in SUBTYPE_DEFINITIONS[label].keys()
    }

    resolved = set()

    for name in additional:
        if name in candidates:
            resolved.add(name)
        elif name in subtype_to_major:
            resolved.add(subtype_to_major[name])

    return list(resolved)


# ============================================================
# 2. 통합 함수
# ============================================================

def analyze_abuse(
    text: str,
    input_mode: str = "qa",
    client: OpenAI = None,
    model: str = "gpt-5.6-luna",
) -> dict:
    """
    1차 대분류 판정 → 2차 세부유형 분석까지 이어서 수행한다.

    input_mode: "qa" | "child_only" | "note"
    note 모드는 1차 결과에 LLM 보완 체크를 한 번 더 거친다
    (_screen_missed_major_types 참고).

    client/model을 지정하지 않으면 llm_backend.build_llm_client_and_model이
    LLM_BACKEND 환경변수(openai/ollama)에 따라 알아서 만든다.
    """

    # 1차 판정은 로컬 모델이라 개인정보 유출 위험이 없으므로 원문을 그대로 쓴다.
    major_result = predict_major_types(
        text=text,
        input_mode=input_mode,
    )

    detected_major_types = [
        label
        for label, prediction in major_result.items()
        if prediction.get(
            "detected",
            False,
        )
    ]

    if input_mode == "note":
        if client is None:
            client, model = build_llm_client_and_model(
                default_openai_model=model,
            )

        additional_types = _screen_missed_major_types(
            text=text,
            client=client,
            model=model,
            already_detected=detected_major_types,
        )

        for label in additional_types:
            detected_major_types.append(label)
            major_result[label]["detected"] = True
            major_result[label]["llm_supplementary"] = True

    if not detected_major_types:
        subtype_result = {
            "results": [],
            "note": "탐지된 대분류 없음",
        }
    else:
        if client is None:
            client, model = build_llm_client_and_model(
                default_openai_model=model,
            )

        # 2차부터는 외부(또는 로컬 Ollama) LLM을 호출하므로 비식별화한
        # 텍스트만 전달하고, 응답에 남은 토큰은 상담사 화면에 보이기 전에
        # 원문으로 되돌린다.
        masked_text, entity_map = mask_pii(text)

        subtype_result = analyze_subtypes(
            text=masked_text,
            major_types=detected_major_types,
            client=client,
            model=model,
        )

        subtype_result = restore_pii(
            subtype_result,
            entity_map,
        )

    return {
        "input_mode": input_mode,
        "major_types": major_result,
        "detected_major_types": detected_major_types,
        "subtype_analysis": subtype_result,
    }


# ============================================================
# 2. 전체 세션 파이프라인 (1차 + 2차 + 상담 요약/상담일지)
# ============================================================

def analyze_session(
    text: str,
    input_mode: str = "qa",
    client: OpenAI = None,
    note_model: str = DEFAULT_NOTE_MODEL,
    checklist_model: str = DEFAULT_CHECKLIST_MODEL,
) -> dict:
    """
    한 세션 텍스트에 대해
    1차 대분류 판정 → 2차 세부유형 분석 → 상담 요약·상담일지 생성 →
    서식 체크리스트 초안 생성까지 한 번에 수행한다.

    상담 요약/상담일지/체크리스트 초안은 학대 탐지 여부와 무관하게 항상 생성한다.

    input_mode="child_only"인 경우 generate_counseling_records와
    generate_checklist_draft도 아동 발화만 보고 작성하게 된다.
    상담사 질문이 빠져 있으므로 "상담 일지"보다는
    "아동 진술 기반 기록"에 가까운 결과가 나온다는 점에 유의한다.

    checklist_draft의 모든 제안 항목은 원문 근거가 있을 때만 포함되며,
    안전영역 항목에는 높음/보통/낮음 등급을 절대 매기지 않는다.
    상담사가 확인하기 전까지는 "AI 제안" 상태로만 취급한다.
    """

    # LLM_BACKEND=ollama면 세션 전체(2차/요약/체크리스트)가 같은 로컬
    # 모델 하나를 쓰도록 여기서 한 번만 client를 정하고 아래로 전달한다.
    # openai 백엔드에서는 기존과 동일하게 각자 자기 기본 모델을 쓴다.
    subtype_model = "gpt-5.6-luna"

    if client is None:
        client, resolved_model = build_llm_client_and_model(
            default_openai_model=note_model,
        )

        if resolved_model != note_model:
            # ollama 백엔드 -> note/checklist/subtype 모두 같은 로컬 모델로 통일
            note_model = resolved_model
            checklist_model = resolved_model
            subtype_model = resolved_model

    # analyze_abuse(1차+2차 판정), generate_counseling_records(요약/일지),
    # generate_checklist_draft(체크리스트 초안)는 서로 결과를 참조하지 않는
    # 독립 호출이라 순차 실행해도 결과는 같다.
    # FastAPI로 옮길 때는 asyncio.gather 등으로 병렬화할 수 있다.
    abuse_result = analyze_abuse(
        text=text,
        input_mode=input_mode,
        client=client,
        model=subtype_model,
    )

    # 상담 요약/일지, 체크리스트 초안도 외부 LLM 호출이므로
    # 비식별화한 텍스트로 생성하고, 결과는 원문으로 복원해 돌려준다.
    masked_text, entity_map = mask_pii(text)

    counseling_records = generate_counseling_records(
        client=client,
        transcript=masked_text,
        model=note_model,
    )

    counseling_records = restore_pii(
        counseling_records,
        entity_map,
    )

    checklist_draft = generate_checklist_draft(
        text=masked_text,
        client=client,
        model=checklist_model,
    )

    checklist_draft = restore_pii(
        checklist_draft,
        entity_map,
    )

    return {
        **abuse_result,
        "counseling_summary": counseling_records[
            "counseling_summary"
        ],
        "counseling_note": counseling_records[
            "counseling_note"
        ],
        "counseling_record_model": note_model,
        "checklist_draft": checklist_draft,
    }


# ============================================================
# 3. 데모
# ============================================================

if __name__ == "__main__":

    text = """
상담사: 아빠가 어떻게 했어?
아동: 아빠가 막대기로 제 팔을 여러 번 때렸어요.
상담사: 또 다른 일도 있었어?
아동: 저번에는 벨트로 허벅지를 때렸어요.
"""

    input_mode = "qa"

    result = analyze_session(
        text=text,
        input_mode=input_mode,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )
