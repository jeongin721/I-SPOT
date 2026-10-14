# I-SPOT 상담사 웹 (프론트엔드 프로토타입)

아동보호전문기관 상담원용 웹 화면입니다. 디자인 캔버스에서 함께 만든 26개 화면을 **React + Vite** 코드로 옮겼습니다.
모든 화면은 예시(가상) 데이터로 동작하며, 버튼 · 탭 · 체크 · 수정 등 화면 안의 동작은 실제로 눌러 볼 수 있습니다.
**로그인 · 통합 사례 관리 · 사례 상세(내담자 정보 · 상담 이력) · 회차 상세 · 녹취 올리기 화면은 Backend 와 연결돼 있습니다**(아래 "서버 연결"). 나머지 화면은 아직 예시 데이터입니다.

## 실행

```bash
npm install
npm run dev        # http://localhost:5173  → 첫 화면은 '화면 목록'
npm run build      # dist/ 에 배포용 파일 생성
```

- Node.js 18 이상
- 화면 주소: `http://localhost:5173/#/Main` 처럼 `#/파일이름`. 사례 · 회차를 다루는 화면은 `#/CaseDetail?case=<사례 ID>` 처럼 쿼리로 ID 를 넘깁니다(아래 "화면 주소")
- 위치: I-SPOT 저장소의 `counselor-web/` 폴더 (기존 `ispotvscode/` 와 별개)

## 서버 연결

- 개발 중에는 `npm run dev` 가 `/api/v1` 요청을 Backend(기본 `http://127.0.0.1:8000`)로 넘깁니다. 주소가 다르면 `VITE_BACKEND_URL=http://127.0.0.1:8013 npm run dev` 처럼 바꿉니다.
- 배포할 때는 `.env` 에 `VITE_API_BASE_URL`(Backend 주소)을 넣습니다.
- 서버 연결 부분은 화면과 나눠 두었습니다. 화면(`.jsx`)은 JavaScript, 연결 부분은 TypeScript 이고 Vite 가 함께 빌드합니다.
  - `src/api/` Backend 호출(토큰 · 401 · 오류 형식), 주소 함수, Backend 응답 타입. `ispotvscode/src/api` 에서 옮겨 왔습니다.
  - `src/data/` 응답을 화면에 쓰기 좋은 모양으로 바꾸는 함수와 훅. 화면 이동은 하지 않고 상태만 돌려주므로 어느 화면 코드에도 끼울 수 있습니다.
  - `src/data/screens/` 화면별 값 함수. 훅 결과를 받아 화면의 예시 데이터를 대신할 값(문자열 · 목록 · 링크 · 이벤트 함수)을 만듭니다. 아래 "화면 파일과 값 함수".
- 회차를 다루는 훅은 회차 ID 를, 사례 상세는 사례 ID 를 받습니다. 로그인 확인 전에 부르지 않도록 `{ enabled: signedIn(session) }` 을 함께 넘깁니다.

| 화면 | 훅 · 변환 | 하는 일 |
| --- | --- | --- |
| 로그인 | `useAuthSession` · `useLogin` · `useLogoutNotice` | 로그인 상태(401 · 임시 비밀번호 · 다른 탭), 로그인, 로그아웃 이유 |
| 사례 목록 | `useCaseList` · `caseRows` | 사례 목록 · 검색 |
| 사례 상세 · 상담 이력 | `useCaseDetail` · `sessionRows` | 사례 정보와 회차 목록. 처리 중인 회차가 있으면 끝날 때까지 다시 조회 |
| 회차 상세 | `useSessionDetail` | 회차 진행 단계 · 실패 문구 · 음성 파일 정보, 지금 할 수 있는 요청 |
| 녹음 업로드 | `useAudioUpload` · `audioFile` | (새 회차) → 음성 올리기 → 원문 변환 요청 → 끝날 때까지 기다리기. 실패하면 그 단계부터 다시(새 회차를 또 만들지 않음) |
| 원문(STT) 검수 | `useTranscriptReview` · `transcriptRows` | 발화 줄 · 저신뢰 · 화자 미확인, 고친 칸만 저장, 확정, 다시 변환 |
| AI 분석 | `useSessionAnalysis` | 분석 요청 · 진행 · AI 원본 요약과 안내(위험 신호 배열은 팀 결정 전이라 내보내지 않음) |
| 요약 검수 · 승인 | `useSummaryReview` | 요약 고치기 · 근거 발화 · 승인(승인하면 회차가 '승인 완료' 가 되어 더 고칠 수 없음) |
| 상담일지 | `useSessionDocuments` | 문서 목록 · 만들기 · 고치기 · 승인(회차 상태와 따로 움직임) |
| 설정 | `useAuthSession` + `profile` · `usePasswordChange` | 내 정보 표시, 비밀번호 변경 |
| 관리자 대시보드 | `useAdminDashboard` · `adminRows` | 전체 사례 · 처리 대기 업무(지연 · 종류별) · 활성 상담사 · 최근 접속 5건. 미배정 · 문서 승인 · 보안 경고는 `—` |
| 관리자 · 업무 처리 현황 | `useAdminTasks` | 모든 상담사의 처리 대기 회차(종류 · 지연 · 상담사로 거르기). 재처리 요청은 넣지 않음(팀 결정) |
| 관리자 · 상담사 계정 관리 | `useAdminAccounts` · `initialPassword` | 계정 목록 · 담당 사례 수, 등록(임시 비밀번호 발급) · 이름 · 역할 · 활성/비활성, 비밀번호 초기화 · 잠금 해제 · 휴면 해제 · 강제 로그아웃. 자기 계정은 막음 |
| 관리자 · 접속 기록 | `useAuditLogs` | 로그인 기록(성공 · 실패 · 기간 · 쪽), `action` 을 바꾸면 계정 관리 기록. 보안 이벤트 심각도는 Backend 에 없음 |
| 관리자 · 전체 사례 현황 | `useCaseList` | 관리자는 전체 사례가 온다(Backend 가 거름) |

- 관리자 훅(`useAdmin*` · `useAuditLogs`)은 `{ enabled }` 대신 `useAuthSession()` 결과를 첫 인자로 받습니다(`useAdminDashboard(session)`). `session.isAdmin`(로그인됐고 서버가 준 역할이 관리자)이 아니면 서버를 부르지 않고, 로그아웃 · 다른 계정으로 바뀌면 불러온 값을 바로 비웁니다. 계정 관리 훅의 요청 뒤에는 같은 탭의 대시보드 · 접속 기록도 다시 조회합니다(`adminEvents`).
- 한 화면에서 위 훅을 여러 개 함께 써도 됩니다. 한 훅의 요청(업로드 · 확정 · 분석 요청 · 승인)으로 회차 상태가 바뀌면 같은 회차를 보는 다른 훅도 다시 조회합니다(`sessionEvents`).
- Backend 에 없는 값(실명 · 신고접수일 · 위험도 · 상담 유형 · 기관 이름 등)은 다른 값으로 채우지 않고 `—` 로 둡니다.
- 타입 검사: `npx tsc --noEmit` (CI 에서도 돕니다)

### 화면 주소

화면 경로는 파일 이름 그대로이고(`App.jsx`), 다루는 사례 · 회차는 쿼리로 넘깁니다. **새 화면도 이 규칙을 따릅니다.**

| 쿼리 | 값 | 쓰는 화면 |
| --- | --- | --- |
| `case` | 사례 ID(UUID, 목록의 `CaseRow.id`). 화면에 보이는 사례번호 `C-2026-0001` 이 아닙니다 | 사례 상세 탭들, 녹취 올리기(그 사례를 고른 채 시작) |
| `session` | 회차 ID(UUID) | 회차 상세, 회차 처리 화면, 녹취 올리기(그 회차를 고른 채 시작) |

- 예: `#/CaseDetail?case=…`, `#/SessionDetail?case=…&session=…`
- 읽기는 `readScreenIds(useSearchParams()[0])`, 만들기는 `screenHref('/SessionDetail', { caseId, sessionId })`(`src/data/screens/links.ts`). 주소 문자열을 직접 이어 붙이지 않습니다.
- 회차 화면은 `session` 만 있어도 됩니다. 사례는 회차 정보에서 찾고, 주소의 `case` 와 다르면 회차 쪽을 씁니다. 링크를 만들 때는 아는 ID 를 모두 넣습니다.
- 필요한 ID 가 없거나 없는 사례 · 회차면 화면 위에 안내와 돌아갈 링크를 보입니다(`screenNotice` → `components/Notice.jsx`).

### 화면 파일과 값 함수

화면 파일(`.jsx`)에는 훅을 부르고 넘기는 몇 줄과 배치(JSX)만 둡니다. 값 계산은 `src/data/screens/` 에 둡니다.

```jsx
class Logic extends DCLogic {
  renderVals() {
    return caseDetailValues(this.props);           // 값 계산은 src/data/screens/caseDetail.ts
  }
}
export default function CaseDetail(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const v = useDC(Logic, { ...props, session, detail, caseId });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return ( /* JSX: v.title, v.basics … */ );
}
```

- 피그마 화면이 오면 위 훅 몇 줄과 `renderVals()` 를 그대로 옮기고 JSX 만 바꿉니다. 새 배치에 필요한 값이 없으면 값 함수에 더합니다(화면 파일에서 계산하지 않습니다).
- 화면만의 상태(단계 · 고른 항목 · 펼침 등)는 `Logic.state` 에 두고, 처음 값 · 바꾸는 함수는 값 함수가 줍니다(`uploadModal.ts` 의 `initialUploadState` · `setState`). 훅에 넘겨야 하는 상태(검색어 · 고른 사례)는 화면 함수의 `useState` 로 듭니다.
- 공용: 사이드바 내 이름 · 로그아웃 `sidebarValues`, 로그인 화면으로 보낼지 `needsLogin`, 화면 위 안내 `screenNotice`, 회차 상태 칩 `TONE_CHIP`(`common.ts`), 회차 단계 → 다음 화면 `continueLink`(`flow.ts`).
- `Login.jsx` 는 아직 값 계산이 화면 파일 안에 있습니다(이 규칙 전에 연결).

| 화면 | 화면 파일 | 주소 | 훅 | 값 함수(`src/data/screens/`) |
| --- | --- | --- | --- | --- |
| 통합 사례 관리 | `CaseList.jsx` | — | `useAuthSession` · `useCaseList` | `caseList.ts` `caseListValues` |
| 사례 상세 · 내담자 정보 | `CaseDetail.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseDetailValues` |
| 사례 상세 · 상담 이력 | `CaseHistory.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseHistoryValues` |
| 회차 상세 | `SessionDetail.jsx` | `case` · `session` | `useSessionDetail` · `useCaseDetail`(회차의 사례) | `sessionDetail.ts` `sessionDetailValues` |
| 녹취 · 자료 올리기 | `UploadModal.jsx` | (`case` · `session`) | `useCaseList` · `useCaseDetail`(고른 사례) · `useAudioUpload` | `uploadModal.ts` `uploadModalValues` |

## 폴더 구조

```
src/
  main.jsx            진입점 (공통 CSS 로드)
  App.jsx             라우터 — src/pages/*.jsx 를 '/파일이름' 경로로 자동 등록 (HashRouter)
  Overview.jsx        첫 화면: 흐름별 화면 목록
  dc.js               화면 로직 어댑터 (DCLogic · useDC)
  components/A.jsx    화면 간 이동 링크 (내부 경로는 react-router Link)
  components/Notice.jsx 화면 위 한 줄 안내 (불러오는 중 · 오류 · 대상 없음)
  styles/common.css   공통 스타일 (사이드바 · 카드 · 칩 · 버튼 · 탭 · 단계 표시 등)
  api/                Backend 호출 (TypeScript) — client · endpoints · types
  data/               응답 변환 함수 · 데이터 훅 (TypeScript)
    screens/          화면별 값 함수 · 화면 주소(links.ts)
  pages/
    Xxx.jsx           화면 1개 = 파일 1개 (로직 class + JSX)
    Xxx.css           그 화면 전용 스타일 (.pg-Xxx 로 범위 제한)
    manifest.json     화면 목록 · 제목 · 흐름(행) 정보
```

### 화면 파일 읽는 법

```jsx
class Logic extends DCLogic {
  constructor(props) { super(props); this.state = { tab: 'A' }; }   // 화면 상태
  renderVals() {                                                     // 화면에 쓸 값 + 이벤트 함수
    return { isA: this.state.tab === 'A', goB: () => this.setState({ tab: 'B' }) };
  }
}
export default function Page(props) {
  const v = useDC(Logic, props);     // v.isA, v.goB ...
  return <button onClick={v.goB}>…</button>;
}
```

- 아직 연결하지 않은 화면은 예시 데이터가 `renderVals()` 안에 있습니다. 연결할 때는 위 "화면 파일과 값 함수" 대로 값 함수로 바꿉니다.
- 원하면 화면별로 `useState` / 커스텀 훅 / 컴포넌트로 자유롭게 리팩터링해도 됩니다. (자동 변환이라 인라인 style 이 많습니다 — 공통 컴포넌트로 묶어 가며 정리 추천)
- 사이드바 · 사례 상세 탭 · 회차 처리 4단계 표시는 지금 각 화면에 복사돼 있습니다. 첫 리팩터링으로 `components/` 로 빼는 걸 추천합니다.

## 디자인 기준

| 용도 | 색 |
|---|---|
| 페이지 배경 / 사이드바 | `#FFFEFA` / `#FFFCF5` |
| 메인 (주요 버튼 · 현재 메뉴 · 선택 상태) | 하늘색 `#A8C6E7` · `#7FA8D6` · 선택 배경 `#E2ECF8` |
| 긴급 · 위험도 '상' · 중요 일정 | 적갈색 `#93452E` / 배경 `#FBE4DC` |
| 위험도 '중' · '아이가 쓴 글' 강조 | 머스타드 `#FCEFB4` / 글자 `#7B4A26` |
| 그 밖 | 무채색 (글자 `#2F3A44`, 보조 `#6F7880`, 테두리 `#E7E0CE`) |

- 글꼴: Noto Sans KR
- 위험도는 상 / 중 / 하로만 표시 (점수 · % 없음)
- 색은 중요한 곳에만. 보충 설명 문구는 최소로.

## 지켜야 할 원칙 (AI 기능)

1. AI는 제안만 합니다. 신고 · 판정 · 종결 결정은 상담원이 합니다.
2. AI가 만든 내용은 항상 `AI 초안` / `AI 제안` 으로 표시합니다.
3. 모든 제안에는 근거 위치(몇 회차 몇 분, 아이 연계 몇 월 며칠)를 함께 보여 줍니다.
4. 서로 다른 진술은 합치지 않고 그대로 나란히 둡니다.
5. 아이의 무응답은 위험 신호가 아닙니다.
6. 보호자 진술은 아이에게 할 질문의 근거로 쓰지 않습니다.
7. 추가 질문은 질문 은행에서만 제안하고, 상담원이 고친 질문은 `상담사 수정` 으로 표시합니다.
8. 화면의 모든 내용은 상담원이 고칠 수 있어야 합니다.

## 화면 목록

**① 하루 시작 · 로그인 → 홈 → 일정 → 아이 연계 → 아이 상세**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/Login` | `src/pages/Login.jsx` | 로그인 |
| `/#/Main` | `src/pages/Main.jsx` | 홈 (대시보드) |
| `/#/Schedule` | `src/pages/Schedule.jsx` | 일정 · 월간 달력 + 일정 추가 |
| `/#/ChildLink` | `src/pages/ChildLink.jsx` | 아이 연계 · 긴급 알림 + 아이 목록 (응답 · 상태) |
| `/#/ChildDetail` | `src/pages/ChildDetail.jsx` | 아이 연계 › 아이 상세 (아이가 쓴 글 · 질문과 답 · 확인할 답변 · 추가 질문) |

**② 사례 관리 · 통합 목록 → 새 사례 등록**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/CaseList` | `src/pages/CaseList.jsx` | 통합 사례 관리 (사례 ID · 이름 · 신고접수일 · 위험도) |
| `/#/CaseRegister` | `src/pages/CaseRegister.jsx` | 새 사례 등록 (팝업 · 서식 4 초기면접지) |

**③ 사례 상세 · 탭 5개 (내담자 정보 · 상담 이력 · 상담 전 브리핑 · 아이 연계 · 문서함) + 기관 서식 작성**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/CaseDetail` | `src/pages/CaseDetail.jsx` | 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록 |
| `/#/CaseHistory` | `src/pages/CaseHistory.jsx` | 탭 2 · 상담 이력 (① 지금까지 상담 → ② 상담 회차 → ③ 회차별 세부 신호) |
| `/#/SessionDetail` | `src/pages/SessionDetail.jsx` | 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기) |
| `/#/PreBriefing` | `src/pages/PreBriefing.jsx` | 탭 3 · 상담 전 브리핑 (+ 신변안전 확인) |
| `/#/CaseApp` | `src/pages/CaseApp.jsx` | 탭 4 · 아이 연계 (아이 상세와 같은 화면) |
| `/#/CaseDocs` | `src/pages/CaseDocs.jsx` | 탭 5 · 문서함 (기관 서식 6종 + 파일) |
| `/#/CaseForm` | `src/pages/CaseForm.jsx` | 탭 5 › 기관 서식 작성 (사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도) |

**④ 회차 처리 · 녹취 올리기 → STT 검수 → 위험 신호 검토 → 유형별 위험도 → 요약 · 일지 작성 → 추가 확인 · 질문**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/UploadModal` | `src/pages/UploadModal.jsx` | 녹취 · 자료 올리기 (팝업 3단계 + 확인창) |
| `/#/SttReview` | `src/pages/SttReview.jsx` | 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원) |
| `/#/SignalReview` | `src/pages/SignalReview.jsx` | 2 · 위험 신호 검토 (→ 유형별 위험도) |
| `/#/RiskProfile` | `src/pages/RiskProfile.jsx` | 2 › 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단) |
| `/#/NoteWrite` | `src/pages/NoteWrite.jsx` | 3 · 상담 요약 (사정 관점) · 상담 일지 (기관 양식) |
| `/#/FollowupQ` | `src/pages/FollowupQ.jsx` | 4 · 추가 확인 · 질문 (모두 승인 / 수정 가능) |

**⑤ 종결 검토 (목록 → 전체 내역 검토 → 종결보고서) · 통계 · 설정 · 관리자**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/Closure` | `src/pages/Closure.jsx` | 종결 검토 · 대상 아동 목록 |
| `/#/ClosureReview` | `src/pages/ClosureReview.jsx` | 종결 검토 › ① 전체 상담 내역 검토 (핵심 요약 + 근거 · 확인 후 보고서로) |
| `/#/ClosureDetail` | `src/pages/ClosureDetail.jsx` | 종결 검토 › ② 사례관리 종결보고서 (서식 29 · AI 초안) |
| `/#/Stats` | `src/pages/Stats.jsx` | 통계 (기간 직접 선택 · 원형 · 가로/세로 막대 · 표) |
| `/#/Settings` | `src/pages/Settings.jsx` | 설정 · 계정 / 알림 설정 |
| `/#/Admin` | `src/pages/Admin.jsx` | 관리자 대시보드 |

## 참고

- 기관 서식은 「2026년 아동학대 대응 업무 매뉴얼」 양식(서식 4 초기면접지, 서식 6 사정기록지, 서식 27 사례관리 점검표, 서식 29 사례관리 종결보고서, 참고자료 1 · 3 척도)을 따랐습니다.
- 모든 이름 · 사례 · 수치는 가상 데이터입니다.
