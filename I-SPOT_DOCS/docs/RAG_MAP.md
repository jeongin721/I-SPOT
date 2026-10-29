# 상담사 웹 화면별 RAG 적용 지점 · 필요 자료

> 기준: `frontend-design-web` 브랜치의 상담사 웹 화면 25개(`7d14585`) + `feature/rag` 브랜치의 `rag/` · `law/` 패키지
> 작성일: 2026-10-12

## 0. 한눈에 보기

이 화면 구성에서 "근거"는 두 종류입니다. RAG도 두 갈래로 나눠야 합니다.

| 구분 | 무엇을 검색하나 | 예 (화면 문구) | 저장 위치 |
| --- | --- | --- | --- |
| **A. 지식 RAG** (공통) | 매뉴얼 · 서식 작성지침 · 척도 문항 · 체크리스트 · 법령 · 질문 은행 | "매뉴얼 5장", "참고자료 3 · 43문항", "QB-N-12", "「아동복지법」상 아동연령" | 기관 공통 Vector DB (`rag_data/` → Chroma) |
| **B. 사례 RAG** (사례별) | 이 사례의 검수본 · 확정 일지 · 아이 앱 응답 · 아이가 쓴 글 · 서비스 기록 | "근거 · 8회차 01:08", "10/7 아이 메시지", "가정방문 6/19" | 사례 단위로 분리된 색인 (권한 = 사례 접근 권한) |

`feature/rag` 는 A의 일부(체크리스트 · 매뉴얼 · 법령)만 다룹니다. 화면 대부분의 "근거 · N회차 mm:ss" 는 **B 사례 RAG** 가 있어야 채워집니다.

## 1. 화면별 RAG 필요 여부

### 1-1. RAG 필요 — 핵심

| 화면 | 위치 (AI 표시) | RAG 종류 | 검색 대상 → 출력 | 필요 자료 |
| --- | --- | --- | --- | --- |
| **SignalReview** 위험 신호 검토 | 세부 신호 카드 "근거" · `AI 분석 · 판정 아님` | A + B | 아동 발화 ↔ 학대 유형 · 세부 신호 정의/징후 → 신호명 · 근거 발화 · 기준 문서 출처 | ①매뉴얼 학대 유형 정의 · 징후, ②징후 체크리스트, ③경찰 현장조사 체크리스트, ④CAF 판단 척도, ⑪세부 신호 사전(15종) |
| **FollowupQ** 추가 확인 · 질문 | "다음 상담 전 확인할 사항" · 추가 질문 `AI 초안` | A(질문 은행) + B | 확인할 사항(근거 회차) → 질문 은행에서 문항 검색 → `QB-xx` 문항 제안 | ⑩질문 은행, ⑨아동 면담 가이드 |
| **PreBriefing** 상담 전 브리핑 | 확인할 사항 · 추가 질문 `AI 초안` · **신변안전 확인 (매뉴얼 5장)** | A + B | 지난 회차 · 아이 앱 변화 → 확인할 사항 / 위험 상황(대상자 귀가 · 음주) → 매뉴얼 안전 수칙 | ①매뉴얼(상담원 신변안전 장), ⑩질문 은행 |
| **NoteWrite** 상담 요약 · 상담 일지 | 사정기록지 안전영역 4칸 · 아동/보호자 특성 체크 `AI 제안` | A(서식 지침) + B | 이번 회차 + 이전 회차 → 칸별 초안 + 근거 시각 | ⑤서식 6 사정기록지 작성 지침, ⑥상담일지 기관 양식 |
| **CaseForm** 기관 서식 작성 | 서식 6 안전영역 9문항, 서식 27 점검표, 위험수준 척도(43문항), 가족관계 척도(15문항) `AI 제안` | A + B | 문항 원문 · 채점 기준 ↔ 사례 기록 전체 → 문항별 응답 제안 + 근거 | ⑤서식 6·27, ⑦위험수준별 개입 사정 척도(참고자료 3), ⑧가족관계 척도(참고자료 1) |
| **ClosureReview** 전체 상담 내역 검토 | 영역별 핵심 요약 + 근거 `AI 초안` | B | 1~N회차 검수본 · 일지 · 아이 연계 · 서비스 기록 → 영역별 요약 | (사례 데이터만) |
| **ClosureDetail** 종결보고서 (서식 29) | 종결 사유 · 개입목표 달성 · 안전영역 `AI 초안/제안` | A + B + 법령 | 종결 기준 조항 ↔ 사례 기록 → 해당 사유 체크 제안 + 근거 | ①매뉴얼 종결 장, ⑤서식 29, ⑫아동복지법(아동 연령 등) |

### 1-2. RAG 필요 — 보조

| 화면 | 위치 | RAG 종류 | 비고 |
| --- | --- | --- | --- |
| **ChildDetail / CaseApp** 아이 연계 | "확인할 답변" 해석 · 추가 질문 `AI 초안` | A(질문 은행) + B | 앱 응답 변화를 상담 진술과 연결("3회차 상담 진술과 같은 방향"). 문항 ID(`QB-N-12`, `N-5`)는 질문 은행 메타데이터 |
| **CaseHistory / SessionDetail** 상담 이력 | "지금까지 상담" 누적 요약, 회차 AI 요약 | B | 회차 요약 집계. 회차 1개 요약은 RAG 없이 Transcript 직접 입력으로 충분 |
| **CaseDocs** 문서함 | 서식별 `AI 초안/제안` 배지 | — | CaseForm · ClosureDetail 결과를 보여 주기만 함 |

### 1-3. RAG 불필요

Login · Main · Schedule · ChildLink(목록) · CaseList · CaseRegister · UploadModal · SttReview · Stats · Settings · Admin
(검색 · 통계 · 입력 화면입니다. SttReview 는 STT 결과 검수라 근거 검색이 없습니다.)

## 2. 수집할 자료

`feature/rag` 의 폴더 규칙(`rag_data/guidelines · manuals · checklists · precedents · research · forms`)에 맞춰 두었습니다. 목록은 `I-SPOT_DOCS/rag_sources.csv` 에도 있습니다.

### 2-1. 공식 자료 (내려받기)

| # | 자료 | 넣을 폴더 | 쓰는 화면 | 상태 · 받는 곳 |
| --- | --- | --- | --- | --- |
| ① | **아동보호서비스 업무 매뉴얼** (보건복지부 · 아동권리보장원) — 2026년판 우선, 없으면 2025년판 | `manuals/` | 전체 (정의 · 징후 · 신변안전 · 종결) | 2025년판: [보건복지부 게시글](https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=1485922&tag=&nPage=1) (PDF + 서식 hwpx). 2026년판: [서울시아동보호전문기관 자료실](https://seoulcenter.org/pages/page_32.php?sn=3058)에 게시 확인, **복지부 원문 게시 확인 필요** |
| ① | 같은 매뉴얼의 **서식 파일(hwpx)** — 서식 4 · 6 · 27 · 29, 참고자료 1 · 3 | `forms/` | CaseRegister · NoteWrite · CaseForm · ClosureDetail | 위 게시글 첨부. hwpx 는 `PyPDFLoader` 로 못 읽으므로 PDF 로 변환하거나 로더 추가 필요 |
| ② | **아동학대 예방 및 대처요령 교육부문 가이드북 4판** (징후 체크리스트 · 유형별 징후 예시 · 판례) | `checklists/` · `precedents/` | SignalReview | [PDF 직접 링크 (충북교육청 게시)](https://www.cbe.go.kr/upload/dept-21/na/bbs_1661/2026/03/AC1D0C24-4393-F719-8DFF-64E35865C917.pdf) |
| ③ | **범죄수사규칙 별지 제130호 아동학대 현장조사 체크리스트** | `checklists/` | SignalReview | [국가법령정보센터 서식 다운로드](https://www.law.go.kr/LSW//flDownload.do?flSeq=134431977&flNm=%5B%EC%84%9C%EC%8B%9D+130%5D+%EC%95%84%EB%8F%99%ED%95%99%EB%8C%80+%ED%98%84%EC%9E%A5%EC%A1%B0%EC%82%AC+%EC%B2%B4%ED%81%AC%EB%A6%AC%EC%8A%A4%ED%8A%B8%28%EC%A0%9C197%EC%A1%B0+%EC%A0%9C3%ED%95%AD+%EA%B4%80%EB%A0%A8%29&bylClsCd=200202) |
| ④ | **아동학대 판단 척도(CAF)** — 행위 위험성 · 결과 위험성 · 피해자 · 행위자 · 참작사유 | `guidelines/` | SignalReview (참고만, 판정 금지) | 업무 매뉴얼 안에 수록. ①에서 해당 장 확인 |
| ⑤ | 서식 6 사정기록지 · 서식 27 점검표 · 서식 29 종결보고서 **작성 요령** | `forms/` | NoteWrite · CaseForm · ClosureDetail | ① 매뉴얼 본문의 서식 설명 부분 |
| ⑦ | **위험수준별 개입 사정 척도** (참고자료 3 · 43문항 · 0~) | `forms/` | CaseForm · ClosureDetail | ① 매뉴얼 참고자료. 문항 · 점수 기준을 **구조화 데이터(JSON)로도** 따로 만들어야 문항별 제안이 가능 |
| ⑧ | **가족관계 척도** (참고자료 1 · 15문항, 화면 표기 "척도집(2017)") | `forms/` | CaseForm · ClosureReview | ① 매뉴얼 참고자료. 2017 척도집 원본은 웹에서 못 찾음 → 아동권리보장원 문의 |
| ⑨ | **아동 면담 가이드** (개방형 질문 · 비유도 원칙) | `guidelines/` | FollowupQ · PreBriefing | 공식 한국어 PDF 웹에서 못 찾음. 매뉴얼의 조사 · 면담 장을 우선 사용, 아동권리보장원 교육자료 확인 필요 |
| ⑫ | **아동복지법 · 아동학대범죄의 처벌 등에 관한 특례법** | (API) | ClosureDetail · SignalReview | `law/` 패키지가 국가법령정보센터 Open API 로 조회. `LAW_API_OC` 신청 + **호출 서버 IP 등록** 필요 |
| (참고) | 원가정 관계개선과 복귀를 위한 사례관리 실천 가이드북 (아동보호전문기관용) | `guidelines/` | ClosureReview · ClosureDetail | [PDF](https://www.chorogusan.or.kr/STH2/upload/file/contentsTheSis/2024/5/17/EAAUAAQIMM_20240517095117.pdf) |
| (Later) | 아동학대 사망 · 중대사건 분석 자료 | `research/` | PRD §7 "과거 중대사건 RAG" | 이번 범위 아님 |

### 2-2. 팀이 직접 만들어야 하는 자료 (웹에 없음)

| # | 자료 | 왜 필요한가 | 형식 제안 |
| --- | --- | --- | --- |
| ⑩ | **질문 은행** (`QB-E-05`, `QB-N-12`, `QB-S-01`, `N-5` …) | README 원칙 7: "추가 질문은 질문 은행에서만 제안". 지금 저장소 어디에도 없음 | `rag_data/question_bank.jsonl` — `id`, `domain`(E 정서 · N 방임 · S 안전 · P 신체 …), `audience`(상담 · 아이 앱), `question`, `options`, `age_range`, `basis`(매뉴얼 쪽수) |
| ⑪ | **세부 신호 사전** (화면의 "세부 신호 3 · 4 · 9 · 12") | SignalReview 카드 번호와 세부유형 모델 15종(`physical_direct` … `neglect_medical`)을 잇는 정의표 | `rag_data/signal_dictionary.json` — `no`, `subtype`, `name`, `definition`, `examples`, `manual_ref` |
| ⑥ | **상담일지 · 서비스제공 일지 기관 양식** | NoteWrite "AI 초안 · 기관 양식" | 기관 실제 양식 확인 후 칸 정의 JSON |

### 2-3. 사례 RAG(B) 에 넣을 데이터

이미 Backend 에 있거나 생길 데이터입니다. 별도 수집은 없고 **색인 대상과 메타데이터만** 정하면 됩니다.

| 데이터 | 메타데이터 (화면 "근거" 표기에 필요) |
| --- | --- |
| STT 검수본 (확정 Transcript) | `case_id`, `session_no`, `segment_id`, `start_ms`, `speaker`(피해아동 · 사례관리대상자 · 상담원) |
| 확정 상담 요약 · 일지 | `case_id`, `session_no`, `confirmed_at` |
| 아이 앱 체크인 응답 · 아이가 쓴 글 | `case_id`, `question_id`(QB-xx), `answered_at` |
| 서비스 기록 (부모교육 출석 · 가정방문 · 심리치료) | `case_id`, `service_type`, `date` |
| 기관 서식 확정본 (서식 6 · 27 · 척도 점수) | `case_id`, `form_no`, `date` |

## 3. 지금 코드와 어긋나는 점

1. ~~**질문 생성 방식**~~ → 10/28 방향 변경. 질문 은행 없이 **LLM 이 직접 질문을 쓰는 방식**으로 갑니다(화면 원칙 7 수정 필요). 대신 근거와 검증을 강제합니다: 이번 회차 아동 발화 · 이전 회차 기록 · 아이 앱 응답(사례 근거 `case:N`)과 매뉴얼 면담 지침 · 체크리스트 · 법령 · 판례(공식 근거)를 각각 하나 이상 달아야 하고, 규칙(유도 · 판단 용어 · 아동이 말하지 않은 행위자/행위) + LLM 검토를 통과해야 화면에 올라갑니다. 자세한 내용은 `rag/README.md` 8-3. 질문 은행 ⑩ 이 생기면 예시 문항으로 프롬프트에 함께 넣어 표현을 맞출 수 있습니다.
2. ~~**검수 전 텍스트 사용**~~ → 10/20 반영. RAG 는 `/api/v1/analyze`(검수 전)에서 빠지고, 검수된 Transcript 를 받는 `POST /api/v1/rag/analyze`(`rag/session.py`)로 옮겼습니다.
3. ~~**비식별**~~ → 10/20 반영. 임베딩 · 판정 LLM · 질문 생성 · 화면별 매뉴얼 검색 모두 `privacy_gateway.mask_for_outbound` 로 가린 문장만 보내고 결과를 복원합니다(`rag/privacy.py`). 검증에 막히면 보내지 않습니다. 사례 RAG(B)를 만들 때도 같은 관문을 거쳐야 합니다.
4. ~~**보호자 진술**~~ → 10/20 반영. RAG 입력은 `CHILD` 발화만 씁니다(`rag/session.RAG_INPUT_SPEAKERS`). 사례 RAG(B)를 만들 때도 같은 규칙으로 `GUARDIAN` 발화를 질문 생성 입력에서 뺍니다.
5. **hwpx 서식** — 서식 원본이 hwpx 라 현재 `rag/loader.py`(PDF 전용)로는 색인되지 않습니다.
6. **`.gitignore`** — 이 브랜치 `.gitignore` 에는 `rag_data/` · `rag_storage/` · `law_cache/` 가 없습니다. 자료를 받기 전에 추가해야 원문 PDF 가 커밋되지 않습니다.

## 4. 우선순위 제안

1. ① 업무 매뉴얼(2026) + 서식 파일 확보 → 대부분 화면의 A 근거가 여기서 나옴
2. ⑩ 질문 은행 · ⑪ 세부 신호 사전 작성 (팀 작업, 매뉴얼 기반)
3. 사례 RAG(B) 색인 설계 — ClosureReview · CaseForm · PreBriefing 이 여기에 달려 있음
4. ② ③ 체크리스트, ⑦ ⑧ 척도 구조화
5. ⑫ 법령 API OC · IP 등록
