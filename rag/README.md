# I-SPOT RAG V2

목표: 상담 분석 결과와 관련된 공식 근거자료를 검색하고, 상담 문장·공식 체크리스트·현행 법령을 함께 비교하여 근거 문장, 확인 항목, 다음 상담용 동적 체크리스트, 참고자료 2~3개를 구조화해서 반환한다.

## 1. 전체 흐름

```text
STT 검수 후 Transcript → CHILD 발화만 추림
→ (선택) 이전 회차 기록 · 아이 앱 응답을 사례 기록으로 모음 (8-3)
→ 멀티라벨 모델 abuse_type
→ 비식별 (외부 전송 전, 상담 문장 · 사례 기록을 한 번에, 8-0)
→ RAG 체크리스트 검색
→ 상담 문장과 체크리스트 비교
→ 국가법령정보센터 API에서 현행 법령 조회
→ 관련 조문 랭킹 · 유사 판례 검색 (8-2)
→ 다음 상담 전 확인할 사항 추출 → 추가 질문 생성 → 규칙 · LLM 검증 (8-3)
→ 체크리스트 / 법령 / 매뉴얼·가이드 중 참고자료 2~3개 선택
→ 비식별 토큰 복원 → JSON 반환
```

AI는 학대 여부나 법 위반 여부를 확정하지 않는다. 공식 자료를 근거로 상담사가 다음 상담에서 확인할 항목을 정리하는 보조 역할만 수행한다.

## 2. RAG 원문 폴더

```text
rag_data/
├── guidelines/
├── manuals/
├── checklists/
├── precedents/
├── research/
└── forms/
```

원문 PDF와 생성된 Vector DB, 법령 API 캐시는 GitHub에 커밋하지 않는다.

## 3. 설치

```bash
pip install -r requirements.txt
pip install -r requirements-rag.txt
```

## 4. .env 설정

```env
OPENAI_API_KEY=...

RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_ANALYZER_MODEL=gpt-5.6-luna
RAG_COLLECTION_NAME=ispot_child_abuse
RAG_TOP_K=5

LAW_API_OC=국가법령정보센터에서_승인받은_OC
LAW_CACHE_DIR=law_cache
LAW_CACHE_MAX_AGE_HOURS=24
LAW_TARGET_LAWS=아동복지법,아동학대범죄의 처벌 등에 관한 특례법
```

실제 API Key와 OC 인증값은 `.env`에만 작성하고 GitHub에는 올리지 않는다.

## 5. RAG 인덱스 생성

```bash
python -m rag.indexer
```

```text
PDF
→ 페이지별 텍스트 추출
→ metadata
→ chunk 분할
→ embedding
→ Chroma Vector DB
```

## 6. 국가법령정보센터 API 단독 테스트

아동복지법을 조회하고 정서학대 관련 조문을 확인한다.

```bash
python -m law.query "아동복지법" --abuse-type emotional --text "엄마가 화가 나면 욕을 하고 쓸모없는 사람이라고 말한다" --refresh
```

첫 호출은 국가법령정보센터에서 목록/본문을 가져와 `law_cache/`에 저장한다. 이후에는 기본적으로 24시간 동안 캐시를 재사용한다.

## 7. 상담 분석 Pipeline

```bash
python -m rag.pipeline "엄마가 화가 날 때마다 아이에게 욕을 하고 쓸모없는 사람이라고 반복해서 말한다고 한다" --abuse-type emotional
```

처리 순서:

```text
1. checklist RAG Top-K 검색
2. matched / needs_confirmation / excluded 분류
3. 상담 원문의 근거 문장 추출
4. 국가법령정보센터 API에서 관련 현행 조문 조회
5. 다음 상담용 확인 질문 3~5개 구성
6. 상담사 참고자료 2~3개 선택
```

법령 캐시를 강제로 새로 받으려면:

```bash
python -m rag.pipeline "상담 문장" --abuse-type emotional --refresh-law
```

법령 API 없이 RAG 부분만 테스트하려면:

```bash
python -m rag.pipeline "상담 문장" --abuse-type emotional --skip-law
```

백엔드 연동용 JSON:

```bash
python -m rag.pipeline "상담 문장" --abuse-type emotional --json
```

## 8. 주요 JSON 출력

```json
{
  "analysis_type": "emotional",
  "evidence_sentences": [],
  "checklist_results": [],
  "related_laws": [
    {
      "law_name": "아동복지법",
      "article": "제17조",
      "title": "금지행위",
      "content": "...",
      "matched_keywords": ["정서적 학대행위"],
      "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=290207&joNo=0017&joBrNo=00"
    }
  ],
  "next_session_checklist": {
    "check_items": [
      {
        "id": "check:1",
        "item": "등 · 팔 통증 이후 치료를 받았는지",
        "kind": "info_gap",
        "priority": "high",
        "reason": "통증을 말했지만 치료 여부가 확인되지 않음",
        "case_refs": ["case:2"],
        "knowledge_refs": ["checklist:1"],
        "basis": [
          {"ref": "case:2", "type": "case", "source": "transcript", "label": "8회차 01:08", "session_no": 8, "segment_id": "seg_014", "start_ms": 68000},
          {"ref": "checklist:1", "type": "checklist", "label": "아동학대 의심 체크리스트.pdf p.3"}
        ]
      }
    ],
    "items": [
      {
        "question": "등이랑 팔이 아팠던 건 지금은 어때? 누가 봐 준 적 있어?",
        "audience": "counselor",
        "question_type": "open",
        "priority": "high",
        "rationale": "치료 여부와 현재 상태를 확인",
        "check_item_id": "check:1",
        "case_refs": ["case:2"],
        "knowledge_refs": ["manual:1", "checklist:1"],
        "basis_refs": ["case:2", "manual:1", "checklist:1"],
        "basis": [{"ref": "case:2", "type": "case", "label": "8회차 01:08"}, {"ref": "manual:1", "type": "manual", "label": "업무 매뉴얼 · 상담·조사·사정 p.125"}],
        "review_status": "passed"
      }
    ],
    "validation": {"generated": 7, "rule_rejected": 2, "review_rejected": 1, "rounds": 2, "reviewed": true}
  },
  "reference_materials": [
    {
      "type": "checklist",
      "title": "아동학대 의심 체크리스트.pdf"
    },
    {
      "type": "law",
      "title": "아동복지법",
      "article": "제17조"
    },
    {
      "type": "manual",
      "title": "아동보호서비스 업무 매뉴얼"
    }
  ],
  "manual_references": [
    {
      "type": "manual",
      "title": "[붙임1] 2026년 아동보호서비스 업무 매뉴얼.pdf",
      "summary": "...",
      "source": "[붙임1] 2026년 아동보호서비스 업무 매뉴얼.pdf",
      "organization": "보건복지부·아동권리보장원",
      "page": 123,
      "chunk_id": "..."
    }
  ],
  "precedents": [
    {
      "type": "precedent",
      "origin": "guidebook",
      "title": "친부가 욕설을 하는 자녀를 때림",
      "summary": "피고인은 피해아동(13세)의 친부이다. ...",
      "court": "인천지방법원",
      "case_number": "2022고정1131",
      "citation": "인천지방법원 2022고정1131",
      "abuse_type": "physical",
      "perpetrator": "부모 등",
      "source": "(교육부) 아동학대 예방 및 대처요령 교육부문 가이드북_제4판.pdf",
      "page": 21,
      "url": "",
      "similarity": 0.30
    },
    {
      "type": "precedent",
      "origin": "law_api",
      "title": "어린이집 교사인 피고인 甲이 아동인 피해자들의 입을 주먹으로 때리거나 …",
      "case_name": "아동학대범죄의처벌등에관한특례법위반(아동복지시설종사자등의아동학대가중처벌)",
      "summary": "공소사실의 요지 ...",
      "citation": "○○지방법원 2020. 1. 1. 2019고단0000",
      "url": "https://www.law.go.kr/LSW/precInfoP.do?precSeq=...",
      "similarity": 0.43
    }
  ]
}
```

화면 섹션별 사용 필드:

| 화면 섹션 | 필드 | 내용 |
|---|---|---|
| 매뉴얼과 서식 | `manual_references` | `manual` / `guideline` / `form` 원문에서 유형별 상위 2개 (최대 6개) |
| 매뉴얼과 서식 | `checklist_results` | 공식 체크리스트·서식 항목과 상담 일치 여부 |
| 법령과 판례 | `related_laws` | 국가법령정보센터 현행 조문 |
| 법령과 판례 | `precedents` | 유사 판례. 색인된 가이드북 · 판례 API 판례 중 유사도순 최대 3건. 8-2 참고 |

`reference_materials`는 위 자료 중 핵심 2~3개만 섞어서 고른 요약용 필드다.

## 8-0. 입력 · 비식별 원칙

- **STT 검수 후 Transcript만 쓴다.** `rag.session.analyze_reviewed_transcript(transcript, abuse_type)`가 진입점이고, 최상위 `main.py`의 `POST /api/v1/rag/analyze`가 이것을 부른다. 업로드 직후 `/api/v1/analyze`는 RAG를 돌리지 않는다.
- **아동(`CHILD`) 발화만 넣는다**(`RAG_INPUT_SPEAKERS`). 보호자 진술은 아이에게 할 질문의 근거로 쓰지 않는다(화면 원칙 6). 상담원 · 기타 · 미확정 화자도 뺀다. 뺀 수는 `excluded_speakers`로 돌려준다.
- **외부로 보내기 전에 비식별한다**(9/18 회의 결정). `analyze_consultation_evidence` · `build_screen_references` · `search_screen_manual`은 상담 문장을 `ai.modeling.abuse.privacy_gateway.mask_for_outbound`로 가린 뒤 임베딩 · LLM에 보내고, 결과의 토큰(`[PERSON_01]` 등)을 원문으로 되돌린다(`rag/privacy.py`). 가린 뒤 재검사에서 식별 정보가 남으면 아무것도 보내지 않고 `RagPrivacyBlocked`를 던진다.
- `known_identifiers`(사례에 등록된 아동 · 보호자 실명)를 넘기면 NER이 놓친 이름도 정확 매칭으로 가린다. NER의 사람 이름 미탐률이 36.8%라(`privacy_gateway.py` 머리말) 실제 서비스에서는 넘기는 것이 좋다.
- 비식별 모듈은 처음 부를 때 NER 모델(`Leo97/KoELECTRA-small-v3-modu-ner`)을 내려받아 올린다(약 15초, 이후 한 문장 0.1초 이내).

## 8-1. 화면별 업무 매뉴얼 검색

`2026년 아동보호서비스 업무 매뉴얼`은 상담사 화면 세 곳에 필요한 구간만 검색한다. 구간은 `rag/metadata.py`의 `MANUAL_SCREEN_SECTIONS`(PDF 쪽 범위)로 정하고, 색인할 때 조각마다 `screen` · `screen_section`을 붙인다.

| screen | 화면 | 매뉴얼 구간 |
|---|---|---|
| `followup` | 추가 확인 · 질문 | 상담·조사·사정, [서식 8] 친부모 상황 점검표, [서식 9] 아동 상황 점검표 |
| `prebriefing` | 상담 전 브리핑 | [서식 15] 양육상황 점검표 |
| `closure` | 종결 검토 | 종결, 사후관리, [서식 20] 종결심사서, [서식 28] 사후관리 점검표 |

```bash
python -m rag.screen_manual "상담 문장" --screen followup --json
```

```python
from rag.screen_manual import search_screen_manual

references = search_screen_manual("상담 문장", "closure", top_k=3)
# [{"type": "manual", "title": ..., "section": "종결", "summary": ..., "organization": ..., "chunk_id": ...}]
```

- 구간 밖 내용(전달체계, 입양, 실종아동 등)은 검색되지 않는다.
- **맞는 내용이 없으면 빈 목록을 돌려준다.** 화면에는 근거를 표시하지 않는다.
  - `followup`: 서식 8 · 9의 번호 항목 42개 전체를 LLM(`RAG_ANALYZER_MODEL`)에 보여 주고, 상담 내용에 실제로 나온 상황을 점검하는 항목만 고르게 한다. 결과에 `item_no`(항목 번호), `reason`(고른 이유), `detail`(작성방법 설명)이 붙는다. 아동 상황 점검표(서식 9) 항목을 먼저 둔다.
  - `prebriefing` · `closure`: 벡터 검색 후보(최대 9개) 중 코사인 유사도가 기준점(브리핑 0.32, 종결 0.35) 미만인 것은 먼저 버리고(`SCREEN_MIN_SIMILARITY`), 남은 후보를 LLM이 화면 목적(`SCREEN_PURPOSES`)에 맞는지 확인해 맞는 것만 남긴다. 서식 작성 절차(작성자 · 시기 · 송부처)만 있는 후보는 뺀다. 결과에 `similarity`, `reason`이 붙는다. 기준점을 넘는 후보가 없으면 LLM을 부르지 않는다.
- 화면 검색 한 번에 LLM 호출이 한 번 들어간다(`RAG_ANALYZER_MODEL`).
- LLM 확인 때문에 화면 하나에 3~5초가 걸린다. **화면을 열 때 검색하지 말고 분석할 때 미리 만들어 저장한다.** `build_screen_references(text)`는 세 화면을 동시에 만들고(하나씩 10.4초 → 동시에 6.1초), 한 화면이 실패해도 나머지 결과를 돌려준다(`{"references": {...}, "errors": {...}}`). CLI: `--screen all`.
- 최상위 `main.py`의 `/api/v1/rag/analyze`(STT 검수 후)는 아동 발화가 있으면 RAG 분석과 동시에 이 함수를 돌려 `manual_screen_references`로 응답에 담는다. `backend/`에 저장하는 방법은 `I-SPOT_DOCS/docs/PROPOSAL_manual_references.md`(제안, 합의 전)를 본다.
- 아동 발화로는 추가 확인 · 질문만 결과가 나온다. 상담 전 브리핑 · 종결 검토는 지난 회차 요약 · 사례 요약처럼 다른 문장을 넣어야 한다(제안서 §1-3).
- 매뉴얼은 색인 전에 원문을 정리한다(`splitter.clean_manual_text`: 쪽 머리말 · 표 머리글 · 벌어진 글자 · 서식 빈칸 제거). 화면용 구간 조각은 앞에 구간 이름을 붙여 색인하고, 화면에 보일 때는 뗀다.
- 색인할 때 이번에 만들지 않은 예전 조각은 지운다.
- 서식 8 · 9는 색인할 때 번호 항목 하나가 한 조각이 되도록 나눈다(`splitter._split_numbered_items`). 한 쪽 전체를 한 조각으로 두면 항목 8~10개가 섞여 검색 점수가 흐려진다.
- 요약에서 인쇄본 쪽 머리말은 뺀다. 화면에는 쪽 번호를 보여주지 않는다.
- 구간표를 바꾸거나 새 판 매뉴얼을 넣으면 `python -m rag.indexer`로 다시 색인한다.

## 8-2. 유사 판례

`precedents.find_similar_precedents(text, abuse_type)`는 **미리 색인해 둔 판례**에서 상담 내용과 비슷한 사건을 찾는다(코사인 유사도 0.25 이상, 학대 유형 안에서 최대 3건). 분석할 때 국가법령정보센터를 부르지 않는다. API 검색은 최근 선고 순이라 비슷한 사건을 고를 수 없기 때문이다. 실패하면 빈 목록과 `precedent_warning`을 돌려준다.

| origin | 출처 | 색인 방법 |
|---|---|---|
| `guidebook` | 교육부 가이드북 4판 '판례로 보는 ○○ 사례' 23건(신체 7 · 정서 7 · 성 3 · 방임 6) | 색인할 때 PDF에서 사건 단위로 뽑는다(`precedents.build_precedent_documents`). 출처는 `source` · `page` |
| `law_api` | 국가법령정보센터 판례 API에서 모은 아동학대 판례(2026-10 기준 98건) | `python -m rag.precedent_harvest`로 모아 `law_cache/precedent_index.json`에 저장하고, 인덱서가 읽는다. `url`은 포털 판례 화면(`precInfoP.do?precSeq=`) |

판례 모으기(`rag/precedent_harvest.py`):

```bash
python -m rag.precedent_harvest   # 판례 API → law_cache/precedent_index.json
python -m rag.indexer             # 가이드북 판례와 함께 색인
```

- 검색어 7개(사건명: 아동학대 · 아동복지법위반 · 아동학대처벌법위반 / 본문: 신체적 · 정서적 · 성적 학대행위 · 방임행위)의 모든 쪽을 받는다. **상담 문장은 보내지 않는다.**
- 학대 유형은 사건명 · 판시사항 · 판결요지 · 사실관계 앞 3000자에 나온 표현(`TYPE_TERMS`)으로 정한다. 판결 뒤쪽은 제17조 각 호를 통째로 인용해 모든 유형이 걸리므로 앞부분만 본다. 아동 학대 문맥(`CHILD_CONTEXT`)이 없으면 뺀다(노인 방임 · 직무유기 등). 여러 유형이면 유형마다 조각을 하나씩 둔다.
- 색인 내용은 '제목 + 사실관계(공소사실의 요지 · 【범죄사실】 · 【이유】 순으로 찾은 곳부터 1200자)'. 법리 문장(판결요지)보다 사실관계가 아동 발화와 더 비슷하다.
- 제목은 판시사항 첫 항목. 판시사항이 없는 하급심은 사실관계 첫 문장('피고인은 …'), 그것도 아니면 사건명.
- 판례 본문은 `law_cache/precedents/`에 기한 없이 캐시한다. 목록에는 있지만 본문 API가 "일치하는 판례가 없습니다"를 돌려주는 판례(3건)는 건너뛴다.
- 판례 API 사용 신청(open.law.go.kr → OPEN API 신청 → 판례)이 필요하다. 새 판례를 반영하려면 두 명령을 다시 돌린다.
- 기준점 0.25는 2026-10 측정값이다(맞는 문장 9개 1위 0.26~0.53 / 무관한 문장 5개 0.13~0.32, 무관한 5개 중 2개는 통과). 실제 상담 문장이 쌓이면 다시 맞춘다.

## 8-3. 다음 상담 체크리스트 (추가 확인 · 질문 화면)

`rag/checklist_builder.build_next_session_checklist`가 화면의 **다음 상담 전 확인할 사항**(`check_items`)과 **추가 질문**(`items`)을 만든다. 질문은 질문 은행에서 고르지 않고 LLM이 직접 쓴다. 대신 근거 ID와 검증을 강제한다.

### 입력 — 사례 기록 (`rag/case_context.build_case_records`)

`POST /api/v1/rag/analyze`에 아래 필드를 함께 보내면 질문 근거로 쓴다. 없으면 이번 회차 아동 발화만 쓴다.

```json
{
  "transcript": {"segments": [...]},
  "session_no": 8,
  "previous_sessions": [
    {
      "session_no": 7,
      "summary": "상담사가 확정한 회차 요약",
      "safety_plan": "위험할 때 조모에게 연락하기로 함",
      "check_items": [{"item": "조모 연락처를 아는지", "status": "open", "note": ""}],
      "transcript": {"segments": [...]}
    }
  ],
  "child_app_responses": [
    {"response_id": "r1", "question": "요즘 기분은 어때?", "answer": "조금 무서워요", "answered_at": "2026-10-07"}
  ]
}
```

| 사례 기록 | 쓰는 것 | 화면 근거 표기(`basis[].label`) |
|---|---|---|
| 이번 회차 | 검수된 Transcript의 `CHILD` 발화만. 발화마다 `segment_id` · `start_ms` | `8회차 01:08` |
| 이전 회차 | 최근 3개 회차의 확정 요약 · 안전 계획 · 확인 사항(`status`) · `CHILD` 발화(회차당 최근 40개) | `7회차 안전 계획`, `7회차 확인 사항`, `7회차 00:10` |
| 아이 앱 응답 | 답이 있는 최근 10개 | `10/7 아이 앱 응답` |

- 기록마다 `case:N` 번호를 붙여 LLM에 보낸다. 기록 하나는 600자에서 자른다.
- 보호자 · 상담원 · 미확정 화자 발화는 이전 회차 검수본에서도 뺀다. 요약 · 안전 계획은 상담사가 확정한 문장을 넣는다.
- 화자 미확정(`UNKNOWN`) 발화는 질문 근거로 쓰지 않고, 응답 최상위 `speaker_check_items`("02:15 발화의 화자", 근거 `8회차 02:15 · 화자 불확실")로 따로 돌려준다. 발화 내용은 외부로 보내지 않는다.

### 비식별

- 상담 문장과 사례 기록 전체를 `rag/privacy.mask_payload`(`privacy_gateway.review`)로 **한 번에** 가린다. 따로 가리면 다른 사람이 같은 토큰(`[PERSON_01]`)을 받아 복원이 꼬인다.
- 이전 회차 · 아이 앱 기록 때문에 비식별 검증에 막히면 이번 회차 기록만으로 다시 하고 `case_context_warning`을 붙인다. 이번 회차 발화가 막히면 지금처럼 `RagPrivacyBlocked`.

### 생성 단계

```text
1) 확인할 사항 추출 (LLM 1회)
   사례 기록 + 체크리스트 needs_confirmation
   → info_gap(시기 · 빈도 · 치료 여부 미확인) / plan_followup(이전 계획 · status=open 확인 사항)
     / change(이전 회차 · 앱과 달라진 점) / inconsistency(기록끼리 안 맞음) / checklist_gap
   → 사례 근거(case:N)가 없는 항목은 버린다. 최대 6개.
2) 질문 생성 (LLM 1회)
   확인할 사항 + 사례 기록 + 공식 근거
   공식 근거: manual:N(업무 매뉴얼 '상담·조사·사정' 구간의 면담 원칙 + 매뉴얼·가이드·서식 검색 결과)
             checklist:N / law:N / precedent:N
   → audience: counselor(다음 상담에서 직접, 3~5개) / child_app(아이 앱으로 먼저, 0~3개)
3) 검증
   규칙: 사례 근거 + 공식 근거 ID 각 1개 이상, 길이(상담 120자 · 앱 50자), 판단 · 법률 용어(학대 · 처벌 · 신고 …),
        꼬리 · 부정형 질문("~했지?", "~맞지?", "~하지 않았어?"),
        아동이 말하지 않은 행위자 + 행위 조합(아동 표현을 되묻는 것은 허용, 활용형 차이는 같은 행위로 봄),
        아이 앱 질문의 특정 행위(때림 · 만짐 · 욕 …)
   LLM 검토(1회): leading / presupposes / age_inappropriate / judgmental — 하나라도 걸리거나 판정이 빠지면 탈락
   → 상담사용 질문이 3개 미만이면 탈락 질문 · 사유를 알려 주고 한 번 더 만든다(최대 2회)
```

- LLM 호출은 3~5회(`RAG_ANALYZER_MODEL`). 회차 분석이 끝날 때 만들어 저장해 두고 화면에서 읽는다.
- `review_status`: `passed`(검토 통과) / `not_reviewed`(검토 호출 실패, 규칙만 통과) / `fallback`(질문 생성 실패 시 체크리스트 판정 단계의 추가 질문을 규칙 검증만 거쳐 씀).
- 법령은 배경 근거로만, 판례는 어떤 사실(반복성 · 상처 정도 · 시기)이 중요한지 참고로만 쓰게 프롬프트로 막는다. 판례 속 사건 내용이 질문에 들어가지 않게 한다.
- 모든 질문은 상담사가 승인해야 쓰인다. 승인 · 수정한 질문과 체크한 확인 사항은 다음 회차 `previous_sessions[].check_items`로 다시 넣는다.
- `validation`에는 생성 · 탈락 수만 담는다(질문 문장은 싣지 않는다).

## 9. 상태값

- `matched`: 상담 원문에서 체크리스트 항목을 직접 뒷받침하는 근거가 확인됨
- `needs_confirmation`: 관련 가능성은 있으나 현재 상담만으로 확인 불가
- `excluded`: 검색되었지만 현재 상담과 직접 관련성이 낮음

검색되었다는 이유만으로 해당 항목을 `matched` 처리하지 않는다.

## 10. 새 파일 역할

```text
law/client.py
- 법령 목록 조회
- 본문 조회
- 24시간 캐시
- 판례 검색 · 본문 조회(판례 API 사용 신청 필요)

law/parser.py
- 법령 JSON을 조문 단위로 변환

law/mapper.py
- physical/emotional/sexual/neglect에 맞춰 관련 조문 랭킹

law/portal.py
- 법령 API의 법령일련번호(MST)와 조문번호로 국가법령정보센터 법령 본문 화면 주소(portal_url, `lsInfoP.do?lsiSeq=..&joNo=..`) 생성
- 화면의 '원문보기' 버튼이 이 주소를 연다. 포털 본문 화면(목차·연혁·3단비교 메뉴 포함)이 열리고 해당 조문 위치로 이동한다. API의 법령상세링크는 OC 인증값이 들어 있어 쓰지 않는다.
- 포털은 가지번호(joBrNo)를 무시하므로 '제10조의2' 같은 가지조문은 본조 위치에서 열린다.
- 일련번호를 쓰므로 화면에 보여준 조문과 같은 시행 버전이 열린다. 법령 캐시가 오래되면 옛 버전이 열리므로 캐시는 24시간마다 갱신한다.

rag/evidence_analyzer.py
- 상담 문장과 체크리스트 비교

rag/checklist_builder.py
- 다음 상담 전 확인할 사항 추출 → 추가 질문 생성(상담 · 아이 앱) → 규칙 · LLM 검증 (8-3)

rag/case_context.py
- 이번 회차 CHILD 발화 · 이전 회차 기록 · 아이 앱 응답을 case:N 사례 기록으로 모으고 화면 근거 표기를 만든다
- 화자 미확정 발화를 '확인할 사항'으로 만든다(외부 전송 없음)

rag/resource_ranker.py
- 상담사에게 보여줄 공식 참고자료 2~3개 선택
- 매뉴얼·판례 검색 결과를 화면 표시용 형식으로 변환

rag/pipeline.py
- 전체 기능 통합 (상담 문장을 비식별한 뒤 분석하고 결과를 복원)

rag/session.py
- STT 검수 후 Transcript에서 CHILD 발화만 추려 근거자료 분석과 화면별 매뉴얼 근거를 동시에 만든다

rag/privacy.py
- 외부 전송 전 비식별(privacy_gateway.mask_for_outbound · 여러 문장은 mask_payload)과 결과 복원

rag/precedents.py
- 가이드북 '판례로 보는 사례'를 사건 단위 조각으로 만들고, 색인된 판례에서 유사 판례를 찾는다

rag/precedent_harvest.py
- 판례 API에서 아동학대 판례를 모아 사실관계 · 학대 유형을 뽑고 색인용 파일로 저장한다
```

## 11. 팀 연동

```text
입력
- STT 검수 후 Transcript (CHILD 발화만 사용)
- 멀티라벨 모델의 abuse_type
- (선택) 사례에 등록된 실명 known_identifiers
- (선택) session_no · previous_sessions · child_app_responses (다음 상담 질문 근거, 8-3)

출력
- 상담 근거 문장
- 확인된 체크리스트 항목
- 추가 확인 필요 항목
- 관련 현행 법령
- 유사 판례
- 다음 상담 전 확인할 사항 · 추가 질문(상담 / 아이 앱, 근거 시각 포함)
- 참고자료 2~3개
```

이 JSON을 팀원 D가 Backend / LangGraph Agent에 연결하고, 팀원 E가 Frontend에서 상담사가 확인할 수 있도록 표시한다.

※ 본 기능은 상담사의 의사결정을 지원하기 위한 참고정보이며 학대 여부 또는 법적 판단을 자동 확정하지 않는다.
