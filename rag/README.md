# I-SPOT RAG V1

목표: 상담 분석 결과와 관련된 공식 근거자료를 검색하고, 상담 문장과 체크리스트를 비교하여 근거 문장·확인 항목·추가 질문을 구조화해서 반환한다.

## 1. 폴더 구조

로컬에서 아래 구조로 원문 PDF를 배치한다. 원문 파일은 GitHub에 커밋하지 않는다.

```text
rag_data/
├── guidelines/
├── manuals/
├── checklists/
├── precedents/
├── research/
└── forms/
```

1차 MVP에서는 `guidelines`, `manuals`, `checklists`부터 사용한다.

## 2. 설치

```bash
pip install -r requirements.txt
pip install -r requirements-rag.txt
```

`.env`에 다음 값을 설정한다.

```env
OPENAI_API_KEY=...
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_ANALYZER_MODEL=gpt-5.6-luna
RAG_COLLECTION_NAME=ispot_child_abuse
RAG_CHUNK_SIZE=900
RAG_CHUNK_OVERLAP=120
RAG_TOP_K=5
```

## 3. 인덱스 생성

```bash
python -m rag.indexer
```

처리 흐름:

```text
PDF
→ 페이지별 텍스트 추출
→ metadata 부여
→ chunk 분할
→ embedding
→ Chroma Vector DB 저장
```

## 4. 검색 테스트

```bash
python -m rag.query "보호자가 아동에게 욕설하고 집에서 나가라고 하는 경우 확인할 정서학대 징후"
```

예시 필터:

```bash
python -m rag.query "정서학대 폭언 위협" --source-type checklist --abuse-type emotional
```

## 5. 상담 근거 분석 Pipeline

`rag/pipeline.py`는 다음 순서로 동작한다.

```text
상담 문장
→ RAG 체크리스트 Top-K 검색
→ LLM이 상담 문장과 후보 항목 비교
→ matched / needs_confirmation / excluded 분류
→ 상담 원문 근거 문장 추출
→ 추가 확인 질문 생성
→ 구조화된 결과 반환
```

사람이 읽기 쉬운 형태로 테스트:

```bash
python -m rag.pipeline "엄마가 화가 날 때마다 아이에게 욕을 하고 쓸모없는 사람이라고 반복해서 말한다고 한다" --abuse-type emotional
```

백엔드 연동용 JSON 출력:

```bash
python -m rag.pipeline "엄마가 화가 날 때마다 아이에게 욕을 하고 쓸모없는 사람이라고 반복해서 말한다고 한다" --abuse-type emotional --json
```

제외된 검색 후보까지 확인:

```bash
python -m rag.pipeline "엄마가 화가 날 때마다 아이에게 욕을 한다" --abuse-type emotional --show-excluded
```

### 상태값

- `matched`: 상담 원문에 체크리스트 항목을 직접 뒷받침하는 근거가 있음
- `needs_confirmation`: 관련 가능성은 있으나 현재 상담만으로 확인 불가
- `excluded`: 검색은 되었지만 현재 상담과 직접 관련성이 낮음

`matched`의 근거 문장은 상담 원문에 실제 존재하는 문장만 허용한다. 원문에서 직접 확인할 수 없는 경우 자동으로 `needs_confirmation`으로 낮춘다.

## 6. Pipeline JSON 형태

```json
{
  "analysis_type": "emotional",
  "consultation_text": "...",
  "evidence_sentences": [
    {
      "text": "...",
      "reason": "..."
    }
  ],
  "checklist_results": [
    {
      "status": "matched",
      "item": "...",
      "evidence": "...",
      "reason": "...",
      "source": "...",
      "organization": "...",
      "page": 1,
      "chunk_id": "...",
      "source_type": "checklist",
      "abuse_type": "emotional",
      "category": "abuse_sign"
    }
  ],
  "additional_questions": [
    "..."
  ],
  "disclaimer": "..."
}
```

## 7. Metadata V1

각 chunk에는 아래 필드를 저장한다.

- `document_id`: 문서 식별자
- `source`: 원본 파일명
- `organization`: 발행기관
- `source_type`: guideline/manual/checklist/precedent/research/form
- `category`: definition/abuse_sign/investigation/counseling/response 등
- `abuse_type`: physical/emotional/sexual/neglect/multiple/none
- `section`, `subsection`: 원문 목차 구조
- `page`: PDF 페이지
- `chunk_id`: chunk 고유 식별자
- `year`: 발행연도
- `authority_level`: official/reference 등

## 8. 역할 연결

현재 RAG 담당 파트의 입력/출력은 다음 형태를 목표로 한다.

```text
입력
- 상담 텍스트
- 멀티라벨 모델이 판단한 abuse_type

출력
- 근거 문장
- 일치 체크리스트
- 추가 확인 필요 항목
- 추가 질문
- 문서/페이지 출처
```

이 결과를 팀원 D가 Backend / LangGraph Agent에 연결한다.

※ 본 분석은 상담사의 판단을 지원하기 위한 참고정보이며 학대 여부를 확정하거나 법적 판단을 대신하지 않는다.
