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
      "matched_keywords": ["정서적 학대행위"],
      "portal_url": "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=290207&joNo=0017&joBrNo=00"
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
  "precedents": []
}
```

화면 섹션별 사용 필드:

| 화면 섹션 | 필드 | 내용 |
|---|---|---|
| 매뉴얼과 서식 | `manual_references` | `manual` / `guideline` / `form` 원문에서 유형별 상위 2개 (최대 6개) |
| 매뉴얼과 서식 | `checklist_results` | 공식 체크리스트·서식 항목과 상담 일치 여부 |
| 법령과 판례 | `related_laws` | 국가법령정보센터 현행 조문 |
| 법령과 판례 | `precedents` | `rag_data/precedents/` 원문 상위 3개. 원문이 없으면 빈 배열 |

`reference_materials`는 위 자료 중 핵심 2~3개만 섞어서 고른 요약용 필드다.

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
- 최상위 `main.py`의 `/api/v1/analyze`는 아동 발화가 있으면 RAG 분석과 동시에 이 함수를 돌려 `manual_screen_references`로 응답에 담는다. `backend/`에 저장하는 방법은 `I-SPOT_DOCS/docs/PROPOSAL_manual_references.md`(제안, 합의 전)를 본다.
- 아동 발화로는 추가 확인 · 질문만 결과가 나온다. 상담 전 브리핑 · 종결 검토는 지난 회차 요약 · 사례 요약처럼 다른 문장을 넣어야 한다(제안서 §1-3).
- 매뉴얼은 색인 전에 원문을 정리한다(`splitter.clean_manual_text`: 쪽 머리말 · 표 머리글 · 벌어진 글자 · 서식 빈칸 제거). 화면용 구간 조각은 앞에 구간 이름을 붙여 색인하고, 화면에 보일 때는 뗀다.
- 색인할 때 이번에 만들지 않은 예전 조각은 지운다.
- 서식 8 · 9는 색인할 때 번호 항목 하나가 한 조각이 되도록 나눈다(`splitter._split_numbered_items`). 한 쪽 전체를 한 조각으로 두면 항목 8~10개가 섞여 검색 점수가 흐려진다.
- 요약에서 인쇄본 쪽 머리말은 뺀다. 화면에는 쪽 번호를 보여주지 않는다.
- 구간표를 바꾸거나 새 판 매뉴얼을 넣으면 `python -m rag.indexer`로 다시 색인한다.

### 유사도 점수

`search_evidence()` 결과의 `similarity`는 질문과 조각의 **코사인 유사도**다. 1에 가까울수록 뜻이 비슷하고, 0 근처면 관련이 거의 없다. Chroma 기본 거리(제곱 유클리드 거리 d²)를 `1 − d² / 2`로 바꾼 값이다(OpenAI 임베딩은 길이가 1이라 성립). `min_similarity`를 주면 그보다 낮은 결과를 뺀다.

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

law/portal.py
- 법령 API의 법령일련번호(MST)와 조문번호로 국가법령정보센터 법령 본문 화면 주소(portal_url, `lsInfoP.do?lsiSeq=..&joNo=..`) 생성
- 화면의 '원문보기' 버튼이 이 주소를 연다. 포털 본문 화면(목차·연혁·3단비교 메뉴 포함)이 열리고 해당 조문 위치로 이동한다. API의 법령상세링크는 OC 인증값이 들어 있어 쓰지 않는다.
- 포털은 가지번호(joBrNo)를 무시하므로 '제10조의2' 같은 가지조문은 본조 위치에서 열린다.
- 일련번호를 쓰므로 화면에 보여준 조문과 같은 시행 버전이 열린다. 법령 캐시가 오래되면 옛 버전이 열리므로 캐시는 24시간마다 갱신한다.

rag/evidence_analyzer.py
- 상담 문장과 체크리스트 비교

rag/checklist_builder.py
- 체크리스트 + 법령을 바탕으로 다음 상담 질문 3~5개 구성

rag/resource_ranker.py
- 상담사에게 보여줄 공식 참고자료 2~3개 선택
- 매뉴얼·판례 검색 결과를 화면 표시용 형식으로 변환

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
