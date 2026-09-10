# I-SPOT RAG V1

목표: 상담 분석 결과와 관련된 공식 근거자료를 검색하고, 문서명·페이지 등 출처와 함께 반환한다.

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
python -m rag.query "정서학대 폭언 위협" --source-type checklist
```

## 5. Metadata V1

각 chunk에는 아래 필드를 저장한다.

- `document_id`: 문서 식별자
- `source`: 원본 파일명
- `organization`: 발행기관
- `source_type`: guideline/manual/checklist/precedent/research/form
- `category`: definition/abuse_sign/risk_factor/counseling/response 등 (현재 자동값은 unknown, 다음 단계에서 문서별 규칙 추가)
- `abuse_type`: physical/emotional/sexual/neglect/multiple/none (현재 자동값은 none, 다음 단계에서 문서별 규칙 추가)
- `section`, `subsection`: 원문 목차 구조 (다음 단계에서 추출 규칙 추가)
- `page`: PDF 페이지
- `chunk_id`: chunk 고유 식별자
- `year`: 발행연도
- `authority_level`: official/reference 등

## 6. 다음 단계

V1 코드는 기본 파이프라인이 동작하도록 만든 상태다. 다음 작업은 실제 수집 문서별 규칙을 추가하여 `category`, `abuse_type`, `section`, `subsection`, `year`, `organization` metadata 정확도를 높이는 것이다.

그 후 검색 품질을 평가하고 판례 DB를 별도로 추가한다.
