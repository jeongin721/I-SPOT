# 법령·매뉴얼 AI 질의

> 작성: 이경진 · 2026-10-26
> 브랜치: `feat/law-qa` (main 기준)

현직자 인터뷰(2026-10-24, "I-SPOT 현직자 인터뷰 정리.pdf" §6-2
"법령·매뉴얼 AI 질의")가 요청한 기능. 상담사가 자연어로 법령·매뉴얼을
물어보면 AI가 근거(조문·서식)를 달아 답한다.

```
§6-2 원문: "확인해야 하는 법령이 있고 매년 개정되어 헷갈릴 때가
많습니다. 주로 보는 법은 아동복지법과 아동학대범죄의 처벌 등에 관한
특례법(아동학대처벌법) 두 가지입니다 ... 기관에서 쓰는 법령과 매뉴얼을
웹에 학습시켜, AI에게 물어보면 바로 확인할 수 있기를 원했습니다."
```

## 구조

- `law/` — 국가법령정보센터 Open API 연동(`client.py`), 조문 파싱
  (`parser.py`), 학대유형별 자동 인용 랭킹(`mapper.py`, 기존
  `legal_reference_adapter.py`가 씀 — 이 기능과는 별개 용도).
  `ai-modeling` 브랜치에 있던 같은 이름의 패키지를 main 기준으로
  포팅했다. `mapper.py`/`parser.py`는 동일하고, `client.py`/`portal.py`는
  `from rag.config import ...` → `from .config import ...` 한 줄만
  다르다. **`ai-modeling`에는 이 브랜치에 없는 `query.py`가 있고, 이
  브랜치에는 `ai-modeling`에 없는 `config.py`가 있다 — 나중에
  `ai-modeling`을 main에 합칠 때 `law/`에서 충돌이 난다. 그때는 이
  브랜치(`law-qa`) 쪽 `law/`를 기준으로 풀면 된다(2026-10-26, 민규
  리뷰).**
- `manual/` — "2026년 아동학대 대응 업무 매뉴얼" 6장(서식·참고자료)
  이미지 10장의 키워드·페이지 매니페스트(`manifest.py`).
- `ai/modeling/abuse/law_qa_llm.py` — 법령 전용 질의
  (`answer_law_question`). 아동복지법 + 아동학대처벌법 전체 조문
  텍스트(합쳐서 약 9.8만 자, 실측)를 LLM 컨텍스트에 그대로 넣는다 —
  벡터 검색(RAG) 불필요.
- `ai/modeling/abuse/legal_manual_qa_llm.py` — 법령 + 매뉴얼 결합 질의
  (`answer_legal_manual_question`, 실제 엔드포인트가 부를 함수). 질문
  키워드로 관련 매뉴얼 페이지를 최대 3장 골라, 법령 전문 텍스트와 함께
  멀티모달 LLM 호출에 첨부한다.

## 왜 매뉴얼은 텍스트가 아니라 이미지인가

매뉴얼 원본은 PDF가 아니라 실물 책자를 촬영한 사진(`사례관리_업무/`,
카카오톡 전송본)이라 텍스트 레이어가 없다. OCR·수동 전사 대신 이미지를
그대로 멀티모달 LLM에 보여주는 방식을 택했다 — 위험사정 척도 같은
숫자·문항을 손으로 옮기다 하나라도 틀리면 상담 판단에 영향을 줄 수
있어서다.

**이미지 폴더(`사례관리_업무/`)는 저작권 있는 정부 발간물 원본이라 git에
커밋하지 않는다**(`.gitignore`). 로컬에서 매뉴얼 질의까지 테스트하려면
이 폴더를 따로 받아 `MANUAL_IMAGE_DIR` 환경변수(또는 기본 경로
`<repo>/사례관리_업무`)에 둬야 한다. 법령만 묻는 질문은 이미지 없이도
동작한다.

## 인용 신뢰도 차이

- **법령 인용**(`cited_articles`)은 `law_qa_llm._verify_cited_articles`가
  실제 조문 목록과 `(법령명, 조문번호)`로 대조 검증한다.
- **매뉴얼 인용**(`manual_references`)은 원본이 이미지라 문장 단위 사실
  검증이 불가능하다. `legal_manual_qa_llm._verify_manual_references`는
  "이번 호출에 실제로 첨부한 페이지를 가리켰는지"까지만 보장한다 — 그
  페이지에 실제로 그 내용이 있다는 보장은 아니다. 이 한계를 답변
  자체에도 명시하게 시스템 프롬프트를 짰다("확신이 서지 않는 부분은
  원본을 직접 확인하라고 안내").

## 1차 범위: 6장(서식·참고자료)만

실물 책자 19장(2026-10-26, 경진 촬영) 중 6장 10장만 다룬다. 5장
(신변안전매뉴얼, 상담원 본인 안전)은 "헷갈려서 바로 찾아보고 싶은 것"
이라는 인터뷰 취지와 결이 달라 1차 범위에서 뺐다. 필요해지면
`manual/manifest.py`에 `ManualPage`를 추가하는 식으로 확장한다.

## 발견한 버그 (회귀 테스트로 고정)

두 법령 모두 같은 번호 조문이 있어서(둘 다 제10조·제63조 존재, 완전히
다른 내용), 조문 번호만으로 인용 매칭하면 엉뚱한 법령 조문이 붙었다 —
`(법령명, 조문번호)` 쌍으로 검증하도록 고침(`tests/test_law_qa_llm.py`).

매뉴얼 쪽은 프롬프트가 "제목 (p.350)" 형식으로 자료 목록을 보여주면,
LLM이 페이지 표시까지 그대로 베껴 반환해서 제목 완전일치 검증에서
걸러지는 버그가 있었다 — `startswith` 매칭으로 고침
(`tests/test_legal_manual_qa_llm.py`).

둘 다 실제 LLM 호출 테스트 중에 발견했다 — 코드만 읽어서는 안 보이는
종류의 버그였다.

## 테스트

루트 `tests/`는 CI(backend-ci)가 돌리지 않는다(`backend/tests/`만
돈다). 수동 실행:

```bash
python3 -m pytest tests/test_law_qa_llm.py tests/test_legal_manual_qa_llm.py -q
# 11 passed
```

## 아직 안 된 것 / 정해야 할 것 (Backend, 민규)

- counselor-web 질의 화면, Backend 엔드포인트 — Contract 변경 제안서
  (7단계)로 별도 정리 예정. 입력 `question`(+선택 `law_names`), 출력은
  `{answer, law_names, cited_articles, manual_references}` 그대로
  (`manual_references` 는 `{id, title, page}` 목록, 실패는 예외 —
  2026-10-27, PROPOSAL_law_guide_api.md §6-1 · §6-2).
- 질문·답변을 서버에 저장할지(개인정보 범위) — 팀 결정 필요.
- 매뉴얼 촬영본을 서버에 둘 수 있는지(저작권 있는 발간물) — 팀장님 확인
  필요.
- 응답 시간 제한·비용(`deadline`을 Backend가 넘기는 구조) — Backend
  쪽에서 결정.
- `backend/Dockerfile`은 `ai/`·`agent/`·`stt/`만 복사하고 루트
  `law/`·`manual/`은 안 들어간다 — Backend에서 이 함수를 부르게 될 때
  COPY 추가 필요(민규).
