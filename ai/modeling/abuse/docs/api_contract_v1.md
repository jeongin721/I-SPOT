# I-SPOT AI 분석 — 백엔드 연동 계약서 v1

백엔드가 호출할 파이썬 함수들의 입력/출력/에러를 정리한다. **이 AI 쪽은
HTTP API 서버가 아니다** — 백엔드가 이 함수들을 감싸서(직접 import하든,
별도 프로세스로 띄워서 내부망으로 부르든) 자기들의 API로 외부에 노출하는
구조를 가정한다.

관련 있는 다른 문서: `subtype_rubric_v1.md`(세부유형 판정 기준).

---

## 0. 호출 순서 요약

```
1. (최초 1회) case_store.set_known_identifiers(case_id, [아동/보호자 실명...])
2. 상담 분석
   - 텍스트/PDF: infer_abuse_pipeline.analyze_session(text, input_mode, case_id)
   - 음성:      infer_audio_session.analyze_audio_session(stt_result, case_id)
   (음성은 분석 전에 infer_audio_session.quick_risk_scan(stt_result)로
    검수 화면에 위험 신호 미리 띄울 수 있음 — 선택)
3. case_store.save_draft_session(...)으로 결과 저장 (AI 초안 상태)
4. 상담사가 확인/수정 후 case_store.approve_session(...)으로 확정
5. (필요시) case_comparison.summarize_case_trend(case_id)로 종결 검토 참고자료
```

세션 저장/승인(3~5번)은 지금 로컬 SQLite(`case_store.db`)로 구현돼 있다.
백엔드가 자체 DB로 세션/사례를 관리할 계획이면 이 부분은 그대로 가져다
써도 되고, 자체 구현으로 대체해도 된다 — AI 분석 자체(1~2번)와는 독립적이다.

---

## 1. 상담 분석

### 1.1 텍스트/PDF 상담 — `infer_abuse_pipeline.analyze_session`

```python
analyze_session(
    text: str,
    input_mode: str = "qa",      # "qa" | "child_only" | "note"
    case_id: str = None,
) -> dict
```

| 파라미터 | 설명 |
|---|---|
| `text` | 상담 원문. `input_mode="qa"`면 `"상담사: ...\n아동: ..."` 형식(화자 표시 필수, 순서 보존). `input_mode="note"`면 3인칭 서술형 상담일지 텍스트. |
| `input_mode` | `"qa"`: 상담사+아동 대화. `"child_only"`: 아동 발화만(상담사 질문 없음). `"note"`: PDF 등에서 추출한 상담일지 서술문. |
| `case_id` | 사례 ID. 주면 Privacy Gateway Tier 2(아래 3절)가 적용됨. 없으면 NER/정규식 탐지만 적용(정확도 낮아짐, 1.3절 참고). |

**반환값(dict):**

```jsonc
{
  "input_mode": "qa",
  "major_types": {
    "신체학대": {"detected": true},
    "정서학대": {"detected": false},
    "성학대": {"detected": false},
    "방임": {"detected": false, "llm_supplementary": true}   // note 모드에서 LLM이 추가한 경우만 존재
  },
  "detected_major_types": ["신체학대"],
  "subtype_analysis": {
    "results": [
      {
        "major_type": "신체학대",
        "subtypes": [
          {
            "type": "직접 신체 가해",
            "evidences": [
              {
                "evidence": "막대기로 제 팔을 여러 번 때렸어요",
                "evidence_verified": true,
                "evidence_strength": "높음",
                "strength_reason": "...",   // 있을 수도 없을 수도 있음(버전에 따라 다름)
                "action": "때리다",
                "instrument": "막대기",
                "target_body_part": "팔",
                "needs_review": false
              }
            ],
            "needs_review": false,
            "borderline": false
          }
        ]
      }
    ],
    "model": "gpt-5.6-luna"
  },
  "counseling_summary": "아동은 ...",
  "counseling_note": "상담사가 ... 질문하자, 아동은 ... 답함.",
  "counseling_record_model": "qwen3:14b",
  "checklist_draft": {
    "problem_history_draft": "...",
    "counselor_opinion_draft": "...",
    "checklist": [
      {"category": "가정상황", "item": "부적절한양육태도", "suggested": true, "evidence": [...]},
      {"category": "아동 특성", "item": "불안", "suggested": false, "evidence": []}
    ],
    "safety_assessment_evidence": [
      {"category": "가족구성원", "item": "가정 내 가정폭력 문제", "evidence": [...]}
    ],
    "environment_key_person": {"status": "있음", "evidence": [...]},
    "model": "qwen3:14b"
  }
}
```

`major_types`/`subtype_analysis`/`checklist_draft` 전부 **"AI 제안" 상태다.**
안전영역(`safety_assessment_evidence`)에는 높음/보통/낮음 등급이 AI가 절대
매기지 않는다 — 상담사가 확인·수정·승인해야 하는 초안으로 그대로 보여줘야
한다.

### 1.2 음성 상담 — `infer_audio_session.analyze_audio_session`

```python
analyze_audio_session(
    stt_result: Dict[str, Any],   # STT Contract v1.0
    case_id: str = None,
) -> dict
```

`stt_result` 형식(STT Contract v1.0):

```jsonc
{
  "schema_version": "1.0",
  "segments": [
    {
      "segment_id": "seg_001",
      "speaker": "COUNSELOR",   // COUNSELOR | CHILD | GUARDIAN | OTHER | UNKNOWN
      "text": "아빠가 어떻게 했어?",
      "start_ms": 0,
      "end_ms": 2000,
      "confidence": 0.95
    }
  ]
}
```

**반환값**: 1.1절 구조에 아래 필드가 추가됨.

| 필드 | 설명 |
|---|---|
| `full_text` | 세션 전체를 하나의 텍스트로 합친 것(`"화자: 발화"` 줄바꿈 연결) |
| `chunk_results` | 1차 판정에 쓴 chunk별 상세(`chunk_index`, `segment_ids`, `has_low_confidence`, `major_types`) — 디버깅/검수용, 최종 판정은 `major_types`/`detected_major_types`를 봐야 함 |
| `subtype_analysis.results[].subtypes[].evidences[]` | `timestamps: {start_ms, end_ms, segment_ids}` 포함 — 근거 발화를 원본 음성 재생 위치와 연결 가능 |

### 1.3 STT 검수 전 빠른 위험신호 스캔 — `infer_audio_session.quick_risk_scan` (선택)

```python
quick_risk_scan(stt_result: Dict[str, Any]) -> Dict[str, List[str]]
# 반환: {segment_id: ["신체학대", ...]}
```

STT 직후, 상담사가 "분석하기"를 누르기 전부터 화면에서 위험 구간을 바로
보여주고 싶을 때 쓴다. **1차 분류기만 돌아서 빠르다(초 단위)** — LLM 호출
없음. 최종 판정이 아니라 미리보기이므로, 이 결과와 `analyze_audio_session`의
최종 결과가 다를 수 있다(특히 note 모드 LLM 보완 추가분은 여기 안 잡힘).

### 1.4 발생 가능한 예외

| 예외 | 발생 상황 | 처리 |
|---|---|---|
| `privacy_gateway.PrivacyGatewayBlocked` | 2차 분석 결과를 OpenAI로 보내기 전 Privacy Gateway가 개인정보 잔존을 발견 | `.reasons`(List[str])에 막힌 필드 경로+사유만 담김(실제 내용 없음). 전체 요청을 실패 처리해야 함 — 일부만 통과시키지 않는 all-or-nothing 설계. |
| `RuntimeError` | `OPENAI_API_KEY` 미설정, 또는 LLM 호출이 타임아웃/실패로 재시도까지 소진 | 메시지에 원인 포함. 상담사에게 "분석 실패, 다시 시도" 안내 |
| `ValueError` | 빈 텍스트, STT 결과에 분석 가능한 발화 없음, `stt_result` 형식 오류 | 입력 검증 실패로 처리 |

### 1.5 처리 시간/비용 참고

- 1차(분류기)만: 수 초 이내
- 2차(세부유형, OpenAI) 포함: 수십 초~1~2분, **학대유형이 하나라도 탐지된
  세션마다 실제 OpenAI API 비용 발생**
- 상담요약/체크리스트(로컬 Ollama): 탐지 여부와 무관하게 매번 생성, 로컬이라
  비용 없음, 수십 초~드물게 3분 이상(긴 체크리스트 스키마 때문에 지연 변동 큼)
- 학대유형 미탐지 세션은 2차를 안 타므로 더 빠름(요약/체크리스트만 생성)

---

## 2. 사례/회기 저장 — `case_store`

로컬 SQLite 구현. 함수 시그니처만 보고 백엔드 자체 DB로 대체해도 무방.

| 함수 | 설명 |
|---|---|
| `create_case_if_missing(case_id, known_identifiers=None)` | 사례 생성(이미 있으면 무시). `known_identifiers` 같이 주면 등록까지 됨 |
| `save_draft_session(case_id, input_mode, source_type, raw_text, analysis) -> session_id` | 1절 분석 결과를 "초안" 상태로 저장. `source_type`: `"text"` \| `"audio"` \| `"pdf"` |
| `approve_session(session_id, final_counseling_summary, final_counseling_note, final_checklist) -> edit_log` | 상담사가 확정한 최종본 저장. AI 초안과 다른 점을 `edit_log`에 자동 기록 |
| `get_session(session_id) -> dict \| None` | 회기 1건 조회 |
| `list_cases() -> List[dict]` | 사례 목록(`case_id`, `session_count`, `last_session_at`) |
| `list_sessions_for_case(case_id) -> List[dict]` | 한 사례의 회기 전체(시간순) |

`list_sessions_for_case`/`get_session`이 반환하는 dict의 `major_types`,
`subtype_analysis`, `final_checklist` 등은 **DB에 JSON 문자열로 저장돼
있어서 그대로 반환된다** — 백엔드에서 `json.loads()`로 한 번 더 파싱해야 함.

---

## 3. Privacy Gateway Tier 2 — 등록된 실명 (중요, 꼭 연결 필요)

```python
case_store.set_known_identifiers(case_id: str, known_identifiers: List[str]) -> None
case_store.get_known_identifiers(case_id: str) -> List[str]
```

**왜 필요한가**: 2차 분석(및 OpenAI로 나가는 모든 호출)은 보내기 전에
사람 이름을 자동 탐지(NER)해서 가리는데, KLUE-NER 5,000문장 기준 실측
결과 **사람이름 미탐률이 36.8%**였다(2026-10-01 측정) — AI 혼자서는
이름 3개 중 1개를 못 가린다는 뜻이다. 아동/보호자 실명을 미리 등록해두면
"이 글자가 보이면 무조건 지운다"는 정확매칭으로 보강돼서, NER이 놓쳐도
반드시 가려진다.

**연결 방법**: 사례 등록/수정 화면에서 아동명·보호자명을 입력받는 UI가
있다면, 그 값을 `set_known_identifiers(case_id, [아동명, 보호자명, ...])`로
저장하면 된다. **analyze_session/analyze_audio_session 호출 시 case_id만
넘기면 내부에서 자동으로 조회해서 쓴다** — 매번 따로 넘길 필요 없음.

등록 안 해도 analyze_session 자체는 정상 동작한다(NER/정규식만 적용) —
다만 그만큼 실명이 가려지지 않고 외부로 나갈 위험이 올라간다.

---

## 4. 사례 비교/종결 검토 — `case_comparison`

```python
compare_case_sessions(case_id: str) -> List[dict]
summarize_case_trend(case_id: str) -> dict | None
```

승인된(`approve_session`을 거친) 회기들의 체크리스트만 비교하는 **순수
데이터 로직 — AI/LLM 호출 전혀 없음.** 백엔드가 체크리스트 JSON을 갖고
있다면 직접 구현해도 되는 수준의 로직이다(새로 나타난/반복되는/사라진
항목을 집합 연산으로 계산).

`summarize_case_trend` 반환값:

```jsonc
{
  "case_id": "...",
  "total_sessions": 4,
  "latest_session_id": 12,
  "consecutive_clean_sessions": 2,
  "active_items": [["가정상황", "부적절한양육태도"]],
  "summary_text": "총 4회기 중 가장 최근 회기(#12) 기준으로 아직 활성 상태인 항목이 있습니다: ...",
  "disclaimer": "이 요약은 종결 검토를 위한 참고 자료일 뿐이며, 종결 여부는 상담사와 사례회의가 공식 절차에 따라 판단해야 합니다."
}
```

**중요**: 이 함수는 "종결해도 된다"를 판단하지 않는다. 참고 자료만
제공한다 — `disclaimer` 필드를 UI에서 빼지 말고 그대로 노출해야 한다.
승인된 회기가 없으면 `None`을 반환한다.

---

## 5. 실행 환경 (환경변수)

| 변수 | 용도 | 없으면? |
|---|---|---|
| `OPENAI_API_KEY` | 2차 세부유형 분석(OpenAI, 항상 외부 호출) | 학대유형이 하나라도 탐지되는 즉시 `RuntimeError` — 서비스 필수 |
| `OLLAMA_BASE_URL` | 로컬 LLM(요약/체크리스트/note 보완체크), 기본 `http://localhost:11434/v1` | 기본값 사용 |
| `OLLAMA_MODEL` | 로컬 LLM 모델 태그, 기본 `qwen3:14b` | 기본값 사용 |
| `ELEVENLABS_API_KEY` | 음성 STT(ElevenLabs Scribe v2) | 음성 분석 전 단계(STT)에서 실패 — `analyze_audio_session` 자체는 영향 없음(STT 끝난 결과를 입력받음) |

`.env` 파일(프로젝트 루트)에서 자동 로드된다(`python-dotenv`) — 셸
환경변수가 이미 있으면 그게 우선한다.

---

## 6. 알아 두면 좋은 설계 특성

- **2차(세부유형)는 항상 OpenAI, 요약/체크리스트는 항상 로컬 Ollama로
  고정돼 있다.** 환경변수로 전체를 토글하는 방식이 아니다 — 호출 종류별로
  백엔드가 다르다.
- **Privacy Gateway는 차단형이다.** 개인정보가 의심되면 마스킹해서
  보내는 게 아니라 아예 전송을 막고 예외를 던진다(1.4절). "일부만
  마스킹해서 통과"는 없다.
- **1차 모델(RoBERTa)은 로컬 추론이라 원문을 그대로 쓴다** — 네트워크로
  나가지 않으므로 마스킹이 필요 없다. 2차부터(OpenAI/로컬 LLM 모두)
  마스킹이 적용된다.
- 체크리스트/상담요약/상담일지는 **학대 탐지 여부와 무관하게 항상
  생성된다** — "아무것도 탐지 안 됨"인 세션도 요약은 나온다.
