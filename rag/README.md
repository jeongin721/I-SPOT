# I-SPOT RAG V2

목표: 상담 분석 결과와 관련된 공식 근거자료를 검색하고, 상담 문장·공식 체크리스트·현행 법령을 함께 비교하여 근거 문장, 확인 항목, 다음 상담용 동적 체크리스트, 참고자료 2~3개를 구조화해서 반환한다.

## 1. 전체 흐름

```text
상담 문장
→ 멀티라벨 모델 abuse_type
→ RAG 체크리스트 검색
→ 상담 문장과 체크리스트 비교
→ 국가법령정보센터 API에서 현행 법령 조회
→ 관련 조문 랭킹
→ 다음 상담용 확인 질문 3~5개 생성
→ 체크리스트 / 법령 / 매뉴얼·가이드 중 참고자료 2~3개 선택
→ JSON 반환
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
      "matched_keywords": ["정서적 학대행위"]
    }
  ],
  "next_session_checklist": {
    "items": [
      {
        "question": "이러한 말을 얼마나 자주 듣나요?",
        "priority": "high",
        "rationale": "현재 상담에서 반복성 확인이 필요함",
        "basis_refs": ["checklist:1", "law:1"]
      }
    ]
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
  ]
}
```

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

law/parser.py
- 법령 JSON을 조문 단위로 변환

law/mapper.py
- physical/emotional/sexual/neglect에 맞춰 관련 조문 랭킹

rag/evidence_analyzer.py
- 상담 문장과 체크리스트 비교

rag/checklist_builder.py
- 체크리스트 + 법령을 바탕으로 다음 상담 질문 3~5개 구성

rag/resource_ranker.py
- 상담사에게 보여줄 공식 참고자료 2~3개 선택

rag/pipeline.py
- 전체 기능 통합
```

## 11. 팀 연동

```text
입력
- STT 상담 텍스트
- 멀티라벨 모델의 abuse_type

출력
- 상담 근거 문장
- 확인된 체크리스트 항목
- 추가 확인 필요 항목
- 관련 현행 법령
- 다음 상담용 확인 체크리스트
- 참고자료 2~3개
```

이 JSON을 팀원 D가 Backend / LangGraph Agent에 연결하고, 팀원 E가 Frontend에서 상담사가 확인할 수 있도록 표시한다.

※ 본 기능은 상담사의 의사결정을 지원하기 위한 참고정보이며 학대 여부 또는 법적 판단을 자동 확정하지 않는다.
