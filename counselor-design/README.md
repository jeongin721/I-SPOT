# I-SPOT 상담사 웹 · 디자인 원본 (2026-10-21)

디자인 캔버스 **"I-SPOT 상담사 웹 화면 설계 · 각진 UI"** 의 최신 화면 원본입니다.
Backend 연결과 `counselor-web/`(React) 반영 작업의 기준으로 쓰기 위해 올렸습니다.

- 화면 45개 (웹 33 · 휴대폰 6 · 태블릿 6)
- 모든 값은 **예시(가상) 데이터** 입니다. 실제 아동 · 상담 정보가 아닙니다.
- `counselor-web/` 은 이 폴더 때문에 바뀌지 않았습니다. 이 원본은 그보다 나중 디자인입니다.

## 폴더 구성

```text
counselor-design/
├─ README.md        # 이 문서
├─ canvas.json      # 캔버스 배치 · 화면 제목 · 줄(①~⑧) 제목
└─ screens/         # 화면 원본 45개 (*.dc.html)
```

## 파일 형식 (`*.dc.html`)

한 파일이 한 화면입니다. 디자인 도구 전용 형식이라 브라우저에서 바로 열면 그대로 보이지 않습니다.

| 부분 | 내용 |
| --- | --- |
| `<x-dc>` … `</x-dc>` | 화면 마크업. `{{ 이름 }}` 은 값 자리, `<sc-for list as>` 는 반복, `<sc-if value>` 는 조건 |
| `<helmet><style>` | 화면 CSS. 순서대로 기본 → 화면별 → 부분 뉴모피즘 → 다크 모드 → 화면별 추가 → 반응형 → 모서리 정리(각진 UI) |
| `<script type="text/x-dc">` | `class Component extends DCLogic` — `state` 와 `renderValsBase()`(예시 데이터 · 버튼 동작). `renderVals()` 는 다크 모드 등 공통 값을 덧붙이는 감싸개 |

`counselor-web/src/dc.js` 의 `DCLogic` · `useDC` 가 같은 구조(state + renderVals)를 React 에서 쓰려고 만든 어댑터입니다. 화면을 옮길 때는 `renderValsBase()` 의 예시 데이터를 훅 결과로 바꾸면 됩니다.

## 화면 목록

### ① 하루 시작 · 아이 연계

| 파일 | 화면 |
| --- | --- |
| Login | 로그인 (상담사 / 관리자 선택, 회원가입 인증 팝업) |
| Main | 홈 (대시보드) |
| Schedule | 일정 · 월간 달력 + 일정 추가 |
| ChildLink | 아이 연계 · 긴급 알림 + 아이 목록 |
| ChildDetail | 아이 상세 (아이가 쓴 글 · 질문 및 답변 · 확인할 답변 · 추가 질문) |
| ChildAnswers | **새 화면** · 과거 답변 기록 (문항별 표 · 날짜별 보기, 최근 1/2/4주) |

### ② 사례 관리

| 파일 | 화면 |
| --- | --- |
| CaseList | 통합 사례 관리 (사례 ID · 이름 · 신고접수일 · 위험도, 정렬 · 실명 보기) |
| CaseRegister | 새 사례 등록 팝업 (서식 4 초기면접지, 필수값 확인, 연 → 월 → 일 날짜 선택, '기타' 직접 입력) |

### ③ 사례 상세 (탭 4개 + 서식)

| 파일 | 화면 |
| --- | --- |
| CaseDetail | 탭 1 · 내담자 정보 (아이 연계 바로가기, **녹음하기 팝업**, 기관 서식, 종결 검토 등록) |
| CaseHistory | 탭 2 · 상담 이력 (회차를 누르면 그 회차 상세로) |
| SessionDetail | 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기) |
| PreBriefing | 탭 3 · 상담 전 브리핑 (먼저 볼 것 · 확인할 사항 · 추가 질문) |
| CaseApp | 아이 연계 (사례 상세 안. 아이 상세와 같은 화면, 기본 정보의 '아이 연계 →' 로 들어감) |
| CaseDocs | 탭 · 문서함 (기관 서식 + 녹취 · 일지 · 외부 문서) |
| CaseForm | 기관 서식 작성 (사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도. 문서함에서 고른 서식이 열림) |

> 위쪽 탭 메뉴에서 '아이 연계' 는 뺐습니다(왼쪽 메뉴와 겹침). 지금 탭은 내담자 정보 · 상담 이력 · 상담 전 브리핑 · 문서함 4개입니다.

### ④ 회차 처리

| 파일 | 화면 |
| --- | --- |
| UploadModal | 녹취 · 자료 올리기 팝업 (사례 → 회차(새 회차 맨 위, 전체 회차) → 파일) |
| SttReview | 1 · STT 검수 + 위험 신호 (화자 선택 · 저신뢰 구간 · 목소리 신호 · 관련 조문) |
| SignalReview | 2 · 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단) |
| NoteWrite | 3 · 상담 요약 · 상담 일지 (기관 양식) |
| FollowupQ | 4 · 추가 확인 · 질문 (섹션별 수정 → 확인/취소, 직접 추가) |

### ⑤ 종결 검토 · 통계 · 설정 · 문서함

| 파일 | 화면 |
| --- | --- |
| Closure | 종결 검토 · 대상 아동 목록 |
| ClosureReview | ① 전체 상담 내역 검토 |
| ClosureDetail | ② 사례관리 종결보고서 (서식 29) |
| Stats | 통계 (기간: 전체 · 이번 달 · 최근 3개월 · 직접 선택) |
| Settings | 설정 · 계정 / 알림 |
| DocBox | 문서함 (폴더 · 올리기 · 내려받기 · 정렬 날짜↑↓ / 이름↑↓ · 미리보기) |

### ⑥ 관리자

| 파일 | 화면 |
| --- | --- |
| AdminHome | 관리자 홈 |
| AdminApp | 아이 연계 앱 관리 |
| AdminAccounts | 상담사 계정 관리 |
| AdminViewLog | 열람 기록 (실명 보기 · 녹취) |
| AdminSecurity | 접속 기록 · 보안 이벤트 |
| AdminStats | 통계 · 보고 (기관 단위) |
| AdminStaffDetail | 상담사 상세 |

### ⑦ 휴대폰 (390px) · ⑧ 태블릿 (820px)

`Phone*` · `Tablet*` 는 같은 이름의 웹 화면을 좁은 폭에서 본 대표 화면입니다(Login · Main · CaseList · CaseDetail · SttReview · AdminHome). 화면 내용은 웹과 같고, 900px 이하에서는 왼쪽 메뉴가 위쪽 '메뉴' 버튼으로 바뀝니다.

## 화면 사이에 넘기는 값

디자인에서는 화면끼리 값을 넘기려고 브라우저 저장소(localStorage · sessionStorage)를 썼습니다. 실제 구현에서는 `counselor-web` 의 규칙대로 **주소 쿼리(`case` · `session`)나 상태 관리로 바꿔야 합니다.**

| 키 | 넣는 곳 → 읽는 곳 | 뜻 |
| --- | --- | --- |
| `ispot-theme` | 모든 화면 | 다크 모드 (`dark` / `light`) |
| `ispot-back` | 각 화면 → UploadModal · CaseRegister | 팝업을 닫으면 돌아갈 화면 |
| `ispot-ses` | CaseHistory → SessionDetail | 고른 회차 번호 |
| `ispot-form` | CaseDocs · CaseDetail → CaseForm | 열 서식 (A 사정기록지 · B 점검표 · C 위험수준 척도 · D 가족관계 척도) |
| `ispot-stt` | ChildDetail · CaseApp → SttReview | 근거 원문 위치(시간). STT 화면에서 그 발화로 스크롤 · 강조 |
| `ispot-child` | ChildDetail · CaseApp → ChildAnswers | 과거 답변 기록을 볼 아이(사례 ID) |

## Backend 가 필요한 부분 (이번 디자인에서 새로 생기거나 바뀐 것)

| 화면 · 기능 | 필요한 값 · 동작 |
| --- | --- |
| CaseDetail · 녹음하기 팝업 | 지금 사례가 고정된 채 회차(새 회차 / 기존 회차 전체) · 상담 유형 선택 → 브라우저 녹음(MediaRecorder) → 저장 시 음성 업로드 → STT 검수로 이동. 녹음 동의 확인 체크 필요 |
| UploadModal | 사례의 **모든 회차** 목록(새 회차 맨 위), 실제로 고른 파일만 표시 |
| ChildDetail · CaseApp | 문항별 지난 답변 3회(3주 전 → 지난주)와 이번 답변, 바뀐 답 표시 |
| ChildAnswers | 아이별 날짜 × 문항 답변 기록(최근 4주), 무응답 날, 아이가 쓴 글 |
| ChildDetail · CaseApp 근거 | 근거 → 원문(STT) 위치 연결: 회차 + 발화 시간(또는 발화 ID) |
| CaseHistory → SessionDetail | 고른 회차의 상세를 열어야 함(지금은 회차 번호로 예시) |
| CaseForm | 서식별 저장 · 확정. 위험수준 척도 43문항(0~3점, 화면 문구는 매우 아니다 · 아니다 · 그렇다 · 매우 그렇다), 위험요인 · 보호요인 합계 |
| FollowupQ | 확인 사항 · 추가 질문의 수정과 상담사 직접 추가(확인을 눌렀을 때만 저장) |
| DocBox | 정렬(날짜 · 이름, 오름 / 내림) |
| Stats | 기간 범위 조회(시작일 ~ 종료일) |

## 디자인 기준

- 색: 기본 `#F2F2F0` · 메뉴 `#E9E7E1` · 글자 `#2B2A26` · 강조 `#C2A36B` / `#EADBB5` · 위험 `#A33B2E`
- 모서리(각진 UI): 버튼 · 입력 10px, 칩 6px, 카드 14px, 묶음 버튼 12px / 8px. 토글 · 아바타 · 단계 번호는 원형 유지
- 다크 모드: 오른쪽 위 스위치. 모든 화면에서 같은 값 유지
- 왼쪽 메뉴는 스크롤해도 고정(900px 초과), 메뉴 사이 옅은 구분선
- 반응형: 1100px · 900px · 600px 기준
