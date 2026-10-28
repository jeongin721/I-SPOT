# I-SPOT 상담사 웹 (프론트엔드 프로토타입)

아동보호전문기관 상담원용 웹 화면입니다. 디자인 캔버스에서 함께 만든 26개 화면을 **React + Vite** 코드로 옮겼습니다.
모든 화면은 예시(가상) 데이터로 동작하며, 버튼 · 탭 · 체크 · 수정 등 화면 안의 동작은 실제로 눌러 볼 수 있습니다.
**로그인 · 홈 · 통합 사례 관리 · 새 사례 등록 · 사례 상세(내담자 정보 · 상담 이력 · 상담 전 브리핑 · 문서함) · 회차 상세 · 녹취 올리기 · STT 검수 · 유형별 위험도 · 요약 · 일지 작성 · 추가 확인 · 질문(AI 확인 메모) · 일정 · 종결 검토 목록 · 통계 · 설정 · 관리자 화면은 Backend 와 연결돼 있습니다**(아래 "서버 연결"). 나머지 화면은 아직 예시 데이터입니다.

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
| 홈 | `useHomeDashboard` | 진행 중 사례 수, 미처리 업무(종류별 수 · 지연 · 오래 기다린 3건). 관리자는 전체 사례 · 모든 상담사의 업무 |
| 사례 목록 | `useCaseList` · `caseRows` | 사례 목록 · 검색 |
| 새 사례 등록 | `useCaseRegister` | 서버가 받는 칸만 등록(`toCaseCreateRequest` 로 확인 · 변환). 관리자면 담당 상담사로 고를 활성 계정 목록도 부름. 한 번 만들면 다시 보내지 않음 |
| 사례 상세 위험도 · 확인 메모 | `useCaseSignals` | 분석이 끝난 가장 최근 회차(결과 검수 중 · 승인 완료) 하나의 상담원 판단(risk-assessments) · AI 관련 신호 · 확인 메모. 내담자 정보의 주요 위험 요인 · 사례 머리 위험도 · 상담 전 브리핑 확인할 사항이 쓴다(새 API 없음) |
| 사례 상세 · 상담 이력 | `useCaseDetail` · `sessionRows` | 사례 정보와 회차 목록. 처리 중인 회차가 있으면 끝날 때까지 다시 조회. 초기면접 아동 특성 · 가정상황 고치기(`saveIntake`, PATCH `/cases/{id}` 로 두 목록을 통째로) |
| 일정 · 종결 검토 목록 · 통계 | `useCaseOverview` | 볼 수 있는 사례를 모두(100건씩 쪽마다) 모으고, 사례마다 회차 목록(`"sessions"`) 또는 회차 수만(`"counts"`) 부름(한 번에 4사례씩, 사례 2,000건 · 사례당 회차 1,000개까지). 집계 API 는 없음 |
| 사례 문서함 | `useCaseDocuments` | 사례의 회차마다 회차 상세(녹음 · 원문 상태) + 문서 목록을 모음(한 번에 4회차씩). 사례 단위 문서 API 는 없음 |
| 회차 상세 | `useSessionDetail` | 회차 진행 단계 · 실패 문구 · 음성 파일 정보, 지금 할 수 있는 요청 |
| 녹음 업로드 | `useAudioUpload` · `audioFile` | (새 회차) → 음성 올리기 → 원문 변환 요청 → 끝날 때까지 기다리기. 실패하면 그 단계부터 다시(새 회차를 또 만들지 않음). 변환을 요청하면 그 회차를 `transcriptionJobs` 에 맡긴다 |
| 원문 변환 알림 | `transcriptionJobs` | 업로드 창 · 녹음하기 창을 닫거나 다른 화면으로 가도 원문 변환이 끝날 때까지 `GET /sessions/{id}/transcript` 를 되풀이 조회하는 공용 저장소(화면 상태). 맡길 때의 로그인 토큰과 지금 토큰이 다르면 버린다. 화면 위쪽 알림 `components/JobToast.jsx` 가 읽는다 |
| 사례 수정 | `useCaseDetail` 의 `saveCase` · `useCaseIntake` | 초기면접지 화면에서 고친 칸만 `PATCH /cases/{id}` 로 보낸다(늦은 응답 방어는 `saveIntake` 와 같음) |
| 마이크 녹음 | `useAudioRecorder` | 사례 상세 '녹음하기' 창. 브라우저 MediaRecorder 로 녹음해 파일을 만들고, 저장하면 `useAudioUpload` 로 올린다. 마이크는 HTTPS · localhost 에서만 열리고, 못 열면 이유를 알린다(녹음하는 척하지 않음) |
| 원문(STT) 검수 | `useTranscriptReview` · `transcriptRows` | 발화 줄 · 저신뢰 · 화자 미확인, 고친 칸만 저장, 확정, 다시 변환 |
| 녹음 다시 듣기 | `useSessionAudio` · `useAudioPlayer` | 음성 파일(`GET /sessions/{id}/audio/file`)을 Authorization 헤더로 받아 Blob URL 로 재생. STT 검수의 시간 단추(그 발화부터)와 하단 재생 바(재생 · 정지 · 5초 이동 · 위치 이동). 원문이 보이면 파일을 미리 받아 둔다(브라우저가 사용자 조작 직후에만 재생을 허용해서). 회차를 바꾸면 URL 을 거둔다 |
| 음성 참고 표시 | `useVoiceMarks` · `voiceMarkRows` | 정담원 님 `stt/voice_marks` 결과(`GET /sessions/{id}/voice-marks`, API_CONTRACT 16절)를 아동 발화 줄 아래 칩으로(떨림 · 웅얼거림 · 작게 말함, flag 가 켜진 것만. 기준값은 응답의 thresholds). '분석 전'(결과 없음, 잠시 되풀이 조회) · '분석 불가(이유)' · '탐지 없음' 을 구분하고, 결과의 원문 판이 지금 판과 다르면 알린다. 다시 들어 볼 구간을 알려 주는 참고 표시이며 판정이 아니다 |
| AI 분석 | `useSessionAnalysis` | 분석 요청 · 진행 · AI 원본 요약과 안내 · 위험 관련 발화(`riskUtterances`) · 유형별 신호(`abuseSignals`) · 심각도 · 보호 요인 · 다음 상담 확인 메모(`followupCheckPoints`)(Contract 그대로, 10/23 · 10/26) |
| 위험 신호 카드 | `useRiskSignals` · `riskRows.ts` | 위험 관련 발화를 카드(유형 · 세부 유형 · 근거 직접성 · 이유 · 원문 대조)로, 유형별 신호를 네 줄로. 근거 위치(몇 분 · 누구)는 원문(`GET …/transcript`)에서 찾는다. 읽기 전용 |
| 요약 검수 · 승인 | `useSummaryReview` | 요약 고치기 · 근거 발화 · 승인(승인하면 회차가 '승인 완료' 가 되어 더 고칠 수 없음) |
| 상담일지 | `useSessionDocuments` | 문서 목록 · 만들기 · 고치기 · 승인(회차 상태와 따로 움직임) |
| 유형별 위험도(상담원 판단) | `useRiskAssessments` | 네 유형(신체 · 정서 · 성 · 방임)의 상담원 판단(상 · 중 · 하) · 이유 · 판단 당시 AI 제안(1~5) 조회와 저장. 원문 확정 뒤에만 저장, 회차 상태는 바뀌지 않음. AI 단계 ↔ 상 · 중 · 하 대응과 사례 단위 위험도는 팀 결정 전이라 계산하지 않음. 유형별 위험도(`SignalReview`) 화면의 유형 줄마다 단추로 저장 |
| 설정 | `useAuthSession` + `profile` · `usePasswordChange` | 내 정보 표시, 비밀번호 변경 |
| 관리자 대시보드 | `useAdminDashboard` · `adminRows` | 전체 사례 · 처리 대기 업무(지연 · 종류별) · 활성 상담사 · 최근 접속 5건. 미배정 · 문서 승인 · 보안 경고는 `—` |
| 관리자 · 업무 처리 현황 | `useAdminTasks` | 모든 상담사의 처리 대기 회차(종류 · 지연 · 상담사로 거르기). 재처리 요청은 넣지 않음(팀 결정) |
| 관리자 · 상담사 계정 관리 | `useAdminAccounts` · `initialPassword` | 계정 목록 · 담당 사례 수, 등록(임시 비밀번호 발급) · 이름 · 역할 · 활성/비활성, 비밀번호 초기화 · 잠금 해제 · 휴면 해제 · 강제 로그아웃. 자기 계정은 막음 |
| 관리자 · 접속 기록 | `useAuditLogs` | 로그인 기록(성공 · 실패 · 기간 · 쪽), `action` 을 바꾸면 계정 관리 기록. 보안 이벤트 심각도는 Backend 에 없음 |
| 관리자 · 전체 사례 현황 | `useCaseList` | 관리자는 전체 사례가 온다(Backend 가 거름) |

- 관리자 훅(`useAdmin*` · `useAuditLogs`)은 `{ enabled }` 대신 `useAuthSession()` 결과를 첫 인자로 받습니다(`useAdminDashboard(session)`). `session.isAdmin`(로그인됐고 서버가 준 역할이 관리자)이 아니면 서버를 부르지 않고, 로그아웃 · 다른 계정으로 바뀌면 불러온 값을 바로 비웁니다. 계정 관리 훅의 요청 뒤에는 같은 탭의 대시보드 · 접속 기록도 다시 조회합니다(`adminEvents`).
- 한 화면에서 위 훅을 여러 개 함께 써도 됩니다. 한 훅의 요청(업로드 · 확정 · 분석 요청 · 승인)으로 회차 상태가 바뀌면 같은 회차를 보는 다른 훅도 다시 조회합니다(`sessionEvents`).
- 회차 훅의 쓰기 요청(저장 · 확정 · 분석 요청 · 승인 · 승인 풀기 · 판단 저장)은 보낼 때 `useRemote` 의 표(`capture()` — key · 대상 세대 · 로그인 토큰)를 잡아 두고, 응답이 오면 그 표가 아직 지금 대상일 때만 반영합니다(`setData(표, …)` · `isCurrent(표)`). 그사이 다른 회차로 옮겼거나, 갔다 돌아왔거나(A → B → A), 다른 탭에서 다시 로그인했거나, 화면을 떠났으면 결과 · 오류를 버리고 '반영 못 함'(`null` · `false`)을 돌려줍니다. 버린 응답이 성공이고 화면이 아직 같은 회차를 보고 있으면(갔다 돌아옴 · 다시 로그인) 조용히 다시 조회합니다(돌아와서 받은 값이 쓰기 전 값일 수 있어서. 조회는 지금 로그인 토큰으로). 저장 → 승인 같은 화면 연쇄와 응답 뒤 이동(`useScreenGo`)도 다음 요청 · 이동 전에 같은 표로 확인합니다. 일지 화면의 고친 일지도 그때의 표와 함께 두어, 대상이 바뀌면(다른 회차 · 갔다 돌아옴 · 다시 로그인) 버립니다. 상담일지 만들기는 그 문서가 목록에 들어올 때까지 같은 회차에서 저장 · 승인을 막습니다(세대가 바뀌어도 같은 회차에 두 번 만들지 않게). 세대는 key 가 바뀔 때만 오르므로(다시 조회 · 되풀이 조회에는 그대로) 처리 중 조회 사이의 저장은 반영됩니다. 녹음 업로드는 시작할 때의 로그인 토큰이 바뀌면 다음 단계를 보내지 않고 멈추고, 실패로 멈춘 뒤 로그인이 바뀌었으면 다시 시도를 막고 앞 로그인이 만든 회차를 다시 쓰지 않습니다.
- Backend 에 없는 값(실명 · 신고접수일 · 위험도 · 상담 유형 · 기관 이름 등)은 다른 값으로 채우지 않고 `—` 로 둡니다.
- 타입 검사: `npx tsc --noEmit` (CI 에서도 돕니다)

### 화면 주소

화면 경로는 파일 이름 그대로이고(`App.jsx`), 다루는 사례 · 회차는 쿼리로 넘깁니다. **새 화면도 이 규칙을 따릅니다.**

| 쿼리 | 값 | 쓰는 화면 |
| --- | --- | --- |
| `case` | 사례 ID(UUID, 목록의 `CaseRow.id`). 화면에 보이는 사례번호 `C-2026-0001` 이 아닙니다 | 사례 상세 탭들, 녹취 올리기(그 사례를 고른 채 시작) |
| `session` | 회차 ID(UUID) | 회차 상세, 회차 처리 화면, 녹취 올리기(그 회차를 고른 채 시작) |
| `back` | 팝업을 연 화면 주소(`/CaseDetail?case=…` 꼴, 앱에 있는 화면만 — App.jsx 가 `registerScreens` 로 화면 목록을 넘김) | 녹취 올리기 · 새 사례 등록(닫기 · 취소 · 나중에가 그 화면으로). `components/A.jsx` 가 팝업으로 가는 링크에 자동으로 붙입니다(`withBack` · `readBackHref`) |
| `seg` | 발화 ID(`segment_id`, 회차 안에서만 뜻이 있어 `session` 과 함께) | STT 검수(그 줄을 금색 테두리로 표시하고 한 번 스크롤, '확인할 곳' 보기에서도 숨기지 않음). 재생 바의 확인할 곳 표시를 눌러도 같은 방식으로 그 줄로 간다. `readFocusSegment`(`sttReview.ts`) · `useSttFocus` |
| `user` | 계정 ID | 관리자 · 상담사 상세(`#/AdminStaffDetail?user=…`). `staffDetailHref` · `USER_PARAM`(`src/data/screens/admin.ts`) |
| `overdue` | `1` | 관리자 · 업무 처리 현황에서 지연된 업무만(`#/AdminTasks?overdue=1`) |
| `view` | `tasks` · `accounts` · `audit`(없으면 홈) | 옛 주소 `#/Admin?view=…` 를 새 관리자 화면(AdminTasks · AdminAccounts · AdminSecurity · AdminHome)으로 넘길 때만 읽습니다(`readAdminView` · `adminHref`) |

- 예: `#/CaseDetail?case=…`, `#/SessionDetail?case=…&session=…`
- 읽기는 `readScreenIds(useSearchParams()[0])`, 만들기는 `screenHref('/SessionDetail', { caseId, sessionId })`(`src/data/screens/links.ts`). 주소 문자열을 직접 이어 붙이지 않습니다.
- 회차 화면은 `session` 만 있어도 됩니다. 사례는 회차 정보에서 찾고, 주소의 `case` 와 다르면 회차 쪽을 씁니다. 링크를 만들 때는 아는 ID 를 모두 넣습니다.
- 필요한 ID 가 없거나 없는 사례 · 회차면 화면 위에 안내와 돌아갈 링크를 보입니다(`screenNotice` → `components/Notice.jsx`).
- 아직 예시 데이터인 화면(아이 연계, 서식)도 들어올 때 받은 ID 를 다음 화면 링크에 넘깁니다:
  `const carry = useCarryHref();` → `<A to={carry('/NoteWrite')}>`(`src/data/useCarryHref.ts`). 회차 ID 는 회차 화면으로 갈 때만 넘깁니다
  (녹취 올리기에 회차 ID 가 붙으면 '그 회차에 이어 올리기'가 됩니다). 예시 화면을 연결된 화면 사이에 새로 둘 때도 이렇게 합니다.

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

- 디자인이 바뀌면 위 훅 몇 줄과 `renderVals()` 를 그대로 두고 JSX 만 바꿉니다. 새 배치에 필요한 값이 없으면 값 함수에 더합니다(화면 파일에서 계산하지 않습니다).
- 화면만의 상태(단계 · 고른 항목 · 펼침 등)는 `Logic.state` 에 두고, 처음 값 · 바꾸는 함수는 값 함수가 줍니다(`uploadModal.ts` 의 `initialUploadState` · `setState`). 훅에 넘겨야 하는 상태(검색어 · 고른 사례)는 화면 함수의 `useState` 로 듭니다.
- 공용: 사이드바 내 이름 · 로그아웃 `sidebarValues`, 로그인 화면으로 보낼지 `needsLogin`, 화면 위 안내 `screenNotice`, 회차 상태 칩 `TONE_CHIP`(`common.ts`), 회차 단계 → 다음 화면 `continueLink` · 회차 처리 단계 표시 `processNav`(`flow.ts`; 끝난 단계 ✓ 와 지금 할 단계만 누를 수 있고 그 뒤 단계는 잠김 — 다음 단계로는 화면 아래 단추로만 간다. 그리는 것은 `components/StepNav.jsx`, 회차 상세의 단계 카드도 같은 규칙), 회차 처리 화면 머리 `processHeaderValues`(`process.ts`). 요청 응답 뒤 이동 `useScreenGo`(요청할 때 잡은 표가 지금 대상이 아니면 옮기지 않음), 저장하지 않은 수정이 있을 때 떠나기 전 확인 `useLeaveGuard`(값 함수의 `unsaved` 를 넘김, 뒤로 가기는 못 막음).
- `Login.jsx` 는 아직 값 계산이 화면 파일 안에 있습니다(이 규칙 전에 연결).

| 화면 | 화면 파일 | 주소 | 훅 | 값 함수(`src/data/screens/`) |
| --- | --- | --- | --- | --- |
| 홈 | `Main.jsx` | — | `useAuthSession` · `useHomeDashboard` | `main.ts` `mainValues` |
| 통합 사례 관리 | `CaseList.jsx` | — | `useAuthSession` · `useCaseList` | `caseList.ts` `caseListValues` |
| 새 사례 등록 | `CaseRegister.jsx` | — | `useAuthSession` · `useCaseRegister` | `caseRegister.ts` `caseRegisterValues` |
| 사례 상세 · 내담자 정보 | `CaseDetail.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseDetailValues` |
| 사례 상세 · 상담 이력 | `CaseHistory.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseHistoryValues` |
| 사례 상세 · 상담 전 브리핑 | `PreBriefing.jsx` | `case` | `useCaseDetail` · `useCaseSignals` | `preBriefing.ts` `preBriefingValues` |
| 사례 상세 · 문서함 | `CaseDocs.jsx` | `case` | `useCaseDetail` · `useCaseDocuments` | `caseDocs.ts` `caseDocsValues` |
| 사례 상세 · 초기면접지 | `CaseIntake.jsx` | `case` | `useCaseDetail`(`saveCase`) · `useIntakeCounselors` | `caseIntake.ts` `caseIntakeValues` |
| 회차 상세 | `SessionDetail.jsx` | `case` · `session` | `useSessionDetail` · `useCaseDetail`(회차의 사례) | `sessionDetail.ts` `sessionDetailValues` |
| 녹취 · 자료 올리기 | `UploadModal.jsx` | (`case` · `session`) | `useCaseList` · `useCaseDetail`(고른 사례) · `useAudioUpload` | `uploadModal.ts` `uploadModalValues` |
| 1 · STT 검수 | `SttReview.jsx` | `case` · `session` | `useTranscriptReview` + 머리 `useSessionDetail` · `useCaseDetail` | `sttReview.ts` `sttReviewValues` |
| 2 · 유형별 위험도 | `SignalReview.jsx`(옛 `RiskProfile` 주소는 여기로 넘김) | `case` · `session` | `useSessionAnalysis` · `useRiskSignals` · `useRiskAssessments` + 머리 | `signalReview.ts` `signalReviewValues` |
| 3 · 요약 · 일지 작성 | `NoteWrite.jsx` | `case` · `session` | `useSummaryReview` · `useSessionDocuments` + 머리 | `noteWrite.ts` `noteWriteValues` |
| 4 · 추가 확인 · 질문 | `FollowupQ.jsx` | `case` · `session` | `useSessionAnalysis` · `useRiskSignals`(근거 위치) + 머리 | `followupQ.ts` `followupQValues` |
| 일정 | `Schedule.jsx` | — | `useAuthSession` · `useCaseOverview`(`sessions`) | `schedule.ts` `scheduleValues` |
| 종결 검토 목록 | `Closure.jsx` | — | `useAuthSession` · `useCaseOverview`(`counts`) | `closure.ts` `closureValues` |
| 통계 | `Stats.jsx` | — | `useAuthSession` · `useCaseOverview`(`sessions`) | `stats.ts` `statsValues` |
| 설정 | `Settings.jsx` | — | `useAuthSession` · `usePasswordChange` | `settings.ts` `settingsValues` |
| 법령 · 매뉴얼 | `LawGuide.jsx` | — | `useAuthSession` | `lawGuide.ts` `lawGuideValues` · 목록 `lawGuideRefs.ts` |
| 관리자 · 홈 | `AdminHome.jsx` | — | `useAdminDashboard` · `useAdminTasks`(업무 구역) · `useAdminAccounts`(활성 상담사 · 업무량) · `useCaseList`(진행 중 사례) | `adminHome.ts` |
| 관리자 · 상담사 계정 관리 | `AdminAccounts.jsx` | — | `useAdminAccounts` | `adminAccounts.ts` |
| 관리자 · 상담사 상세 | `AdminStaffDetail.jsx` | `user` | `useAdminAccounts` | `adminStaffDetail.ts` |
| 관리자 · 접속 기록 · 보안 이벤트 | `AdminSecurity.jsx` | — | `useAuditLogs` · `useAdminAccounts`(잠긴 계정) | `adminSecurity.ts` |
| 관리자 · 통계 · 보고 | `AdminStats.jsx` | — | `useAdminAccounts` · `useCaseOverview` | `adminStats.ts` |
| 관리자 · 업무 처리 현황 | `AdminTasks.jsx` | (`overdue`) | `useAdminTasks` | `admin.ts` |
| (옛 주소) | `Admin.jsx` | (`view`) | — | 새 관리자 화면으로 넘겨 주기만 함 |

- 회차 처리 흐름(10/27 디자인): 녹취 올리기 → STT 검수(고친 발화 저장 · '원문 확정 · 유형별 위험도 →' 가 원문 확정 + AI 분석 요청 + 이동) → 유형별 위험도(AI 분석 진행 · 실패 뒤 다시 분석, 심각도 · 근거 발화 · 상담원 판단) → 요약 · 일지 작성(요약 고치기 · 저장 · **요약 승인 = 회차 '승인 완료'**, 상담일지 저장 · 승인).
- STT 검수(10/21 · 10/22 디자인): 화자는 목록에서 고르고(Esc 로 닫힘), 줄마다 시간 단추(다시 듣기 — 서버에 녹음 재생이 없어 꺼 둠)가 있습니다. 전체 보기는 정해진 높이 안에서 스크롤하고, 아래에 재생 바(`components/SttPlayer.jsx`)가 붙습니다. 재생 · 정지 · 5초 앞뒤 · 재생 위치는 서버에 음성 파일 API 가 없어 꺼 두고(준비 중), 확인하지 않은 저신뢰 · 화자 미확인 줄을 '시작 시각 ÷ 음성 길이' 자리에 표시해 누르면 '확인할 곳' 보기로 바뀌고 그 줄로 갑니다. 10/22 디자인대로 '위험 신호' 구역은 뺐습니다(범례에 목소리 신호 · 관련 조문 준비 중만). 저장 · '원문 확정 · 유형별 위험도 →' 단추는 범례 아래에 있고, 누르면 원문 확정 + AI 분석 요청 + 이동을 한 번에 합니다(10/27 디자인 — 분석 요청 단계가 따로 없음. 이미 확정했고 분석 전이면 요청하고, 분석 중 · 끝남 · 실패면 그냥 갑니다). 현재 단계 강조(먹색 칸 + '현재 단계')는 `common.css` 의 공통 규칙입니다.
- 유형별 위험도(10/27 디자인, `SignalReview`): 10/23 의 '위험 신호 검토' 와 '유형별 위험도' 두 화면을 디자인대로 한 화면으로 합쳤습니다. 위쪽 'AI 초안' 자리는 AI 분석 상태(분석 중 · 실패 · 대기, 실패 · 대기면 다시 요청 단추)이고 회차 전체 AI 위험도 · 안전 플래그 수 · 지난 회차 비교는 서버에 없어 준비 중입니다. 상담원 판단(상 · 중 · 하)은 디자인의 회차 전체 하나 대신 서버(`…/risk-assessments`)대로 유형 줄마다 저장합니다(원문 확정 뒤에만, 저장 뒤 '그때 AI 제안 n/5', 기존 판단 이유는 그대로 보냄). 유형 줄: 관련 신호 칩('관련 신호' / '관련 신호 없음' / '부정 응답으로 뺌' / '검출 여부 미확인' / '근거 없어 제외' — 없음으로 단정하지 않음) · AI 심각도 1~5(`severity_ratings`, 읽기 전용 — 디자인의 '눌러서 상담사 수정' 은 저장할 API 가 없어 하지 않음, `null` 은 '정보 부족') · 해당 기준(단계 설명, 디자인 초안 문구이며 팀이 확정한 기준이 아님) · AI 이유 · 근거 발화(`risk_utterances`, 원문 위치 '몇 분 · 누구', 누르면 STT 검수의 그 발화로 `?seg=`) · 기준 보기(단계 설명 전체 + 근거 발화 전체와 세부 유형 · 근거 직접성 · 원문 대조 · 이유). 근거 발화가 없는 유형은 '언급 없음 ≠ 학대 없음' 을 적습니다. 보호요인(`protective_factors`)은 읽기 전용으로 보이고, 회차별 추이 · 안전 플래그 · 재학대 요인 · 위험요인은 준비 중입니다. 디자인 아래 단추의 '확정' 은 서버에 위험 신호 확정 기록이 없어 빼고 '요약 · 일지 작성 →' 으로만 갑니다. 채택/보류/제외 기록도 서버에 없습니다(팀 결정 전). 모두 AI 제안이고 판정이 아닙니다. 지금은 `AI_PROVIDER=modeling` 만 값을 채우고 mock · pipeline · langgraph 는 빈 배열입니다.
- 추가 확인 · 질문(10/27 디자인, `FollowupQ`): '다음 상담 전 확인할 사항' 에 분석 결과의 `followup_check_points`(AI 가 남긴 확인 메모)를 읽기 전용으로 보입니다(10/26 까지는 유형별 위험도 화면의 카드). 'AI 확인 메모 · 질문 아님' 칩을 붙이고 아이에게 할 질문으로 보이거나 질문 은행과 잇지 않습니다(메모로만 보이면 원칙 7 과 어긋나지 않는다는 10/26 결정). 근거는 `segment_ids` 를 원문에서 찾아 '몇 분 · 누구' 로 보이고 누르면 STT 검수의 그 발화로 갑니다(비어 있으면 '근거 위치 없음'). 브리핑에 넣기 · 수정 · 직접 추가와 추가 질문(다음 상담에서 직접 · 아이 앱으로 먼저)은 서버에 없어 준비 중이고 예시 질문은 보이지 않습니다. 아래 단추는 회차 상세로 갑니다(회차 상태에 '질문 처리 완료' 가 없고 상담 전 브리핑은 아직 예시 화면).
- '요약 승인' · '일지 승인' 은 누르면 (고친 칸을 저장하고) 바로 승인합니다. 요약 승인은 회차를 '승인 완료' 로 바꿉니다. 승인한 칸에는 '요약 수정' · '일지 수정' 단추만 보이고, 누르면 쓴 내용 그대로 승인이 풀려 고친 뒤 다시 승인합니다(요약을 풀면 회차는 'AI 결과 검수 필요' 로 돌아갑니다). '저장 · 추가 확인 · 질문 →' 은 저장만 합니다. → 추가 확인 · 질문(AI 확인 메모 보기).
- 관리자 화면(10/21 디자인): 화면을 나눠 홈(`AdminHome`) · 상담사 계정 관리 · 상담사 상세 · 접속 기록 · 보안 이벤트 · 통계 · 보고를 두고, 왼쪽 메뉴는 공용 `components/AdminSidebar.jsx` 입니다. 디자인 메뉴의 아이 연계 앱 관리 · 열람 기록은 서버가 없어(팀 결정 전) 링크 없는 '준비 중' 이고, 디자인에 없는 기존 기능(업무 처리 현황 `AdminTasks` · 전체 사례 현황 · 상담원 화면으로)은 아래 묶음으로 남겼습니다. 계정 요청(비활성화 · 다시 활성화 · 비밀번호 초기화 · 잠금 해제 · 휴면 해제 · 강제 로그아웃)은 상담사 상세 화면에 있습니다. 옛 주소 `#/Admin`(`?view=`)은 새 화면으로 넘겨 줍니다. 긴급 알림 · OTP · 접속 위치 · IP 차단 · 심각도 · 기관 지표는 서버에 없어 `—` · 준비 중입니다. 모든 관리자 화면은 상담원 계정이면 서버를 부르지 않고 안내만 보입니다. 대시보드 업무 탭은 Backend 가 종류를 하나만 거를 수 있어 두 종류씩 불러 오래 기다린 순서로 합칩니다(원문 변환 · 상담사 검토 · AI 분석). 계정 만들기 · 비밀번호 초기화 · 휴면 해제의 임시 비밀번호는 화면 상태에만 한 번 두고 '닫기' 로 버립니다(다른 관리자로 바뀌면 보이지 않음). 비밀번호 초기화 · 휴면 해제 · 비활성화 · 강제 로그아웃은 한 번 더 묻습니다. 미배정 사례 · 문서 승인 · 보안 경고 · 재처리 요청은 서버에 없어 `—` · 준비 중입니다.
- 새 사례 등록: 서버에 저장하는 칸은 사례 제목 · 아동 별칭(필수), 개별사건번호(비우면 Backend 가 `C-YYYY-NNNN` 으로 만듦, 겹치면 거절 문구) · 성별 · 출생연도 · 보호자 유형(기타면 관계 메모) · 사례 메모, ② 초기면접 내용의 가정상황 · 아동 특성(서식 4 항목 고르기), 담당 상담원(관리자만 고름, 상담원은 본인)입니다. 등록되면 새 사례 상세(`?case=새 ID`)로 갑니다(가정상황 · 아동 특성은 등록 뒤 사례 상세에서 고칩니다). 서식 4 의 나머지 칸(실명 · 생년월일 · 사례관리대상자 · 신고 · 연계 · 면접일 · 학대유형 · 조치결과 · 위험도 · 사례연계 경위, ② 탭의 관계 · 가족 · 문제력 · 태도 · 소견)은 개인정보 저장 범위가 팀 결정 전이라 입력을 막고 '준비 중' 으로 둡니다. 그 내용을 사례 메모 등 다른 칸에 옮겨 담지 않습니다. 화면 칸 '대상아동 이름' · '생년월일' · '관계' 는 '아동 별칭' · '출생연도' · '보호자 유형' 으로 바꿨습니다(사례관리대상자는 보호자와 같은 뜻이 아니어서 따로 준비 중). 10/21 디자인대로 학대유형 칸은 뺐고, 필수 칸(사례 제목 · 아동 별칭)을 채워야 ② 탭으로 넘어갑니다(빈 칸 표시 · 남은 항목 안내). 날짜 달력 · '기타' 직접 입력은 그 칸이 준비 중이라 옮기지 않았습니다.
- 로그인: 10/21 디자인대로 '기관 이메일' · 로그인 유형(상담사 · 관리자) · 회원가입 단추를 두고 OTP 칸은 뺐습니다. 관리자 유형은 서버 역할이 관리자일 때만 관리자 화면으로 가고 아니면 홈으로 갑니다. 회원가입(인증번호 메일)은 Backend 에 없어 준비 중입니다. 10/27 디자인의 3단계 회원가입 팝업(본인 인증 → 계정 정보 → 완료, 이메일 인증번호 5분)도 같은 이유로 옮기지 않았습니다(가입 방식 · 메일 발송은 팀 결정).
- 법령 · 매뉴얼(10/27 디자인, `LawGuide.jsx`): 왼쪽 메뉴 '법령 · 매뉴얼'. 위쪽 'AI에게 묻기' 는 서버에 법령 · 매뉴얼 질의 API 가 아직 없어 준비 중입니다(안내 말풍선 · 예시 질문 · 입력칸은 디자인대로 보이되 꺼 둠, 디자인의 키워드 답변은 옮기지 않음 — 이경진 님 제안서 `I-SPOT_DOCS/docs/PROPOSAL_law_guide_api.md`, AI 모듈 PR #83). 아래 '업무 단계별 참고사항 · 주요 조문' 은 디자인의 정리 문구(`lawGuideRefs.ts`, 매뉴얼 쪽수 · 조문 요약 18개)를 그대로 보이고, 분류(전체 · 업무 단계 · 아동복지법 · 아동학대처벌법) · 펼침은 화면 상태입니다. 서버 값이 아니고 팀이 확정한 기준도 아니라 화면 아래에 원문 확인 안내를 둡니다. '원문보기' · 원문 자료는 국가법령정보센터로 갑니다.
- 녹취 올리기 · 새 사례 등록 팝업: 이 팝업으로 가는 링크(`components/A.jsx`)는 지금 화면 주소를 `?back=` 으로 넘기고, 닫기 · 취소 · 나중에는 그 화면으로 돌아갑니다(10/21 디자인의 `markBack`. 디자인은 브라우저 저장소를 쓰지만 앱은 주소 쿼리 — `links.ts` 의 `withBack` · `readBackHref`). 녹취 올리기의 사례 · 회차 목록은 정해진 높이 안에서 스크롤하고(새 회차가 맨 위), 고른 파일은 '빼기' 로 뺄 수 있습니다.
- 원문 변환 알림(10/22 디자인): 녹취 올리기 · 녹음하기에서 원문 변환을 요청하면 화면 위쪽에 '분석 중입니다... (파일 이름)' 이 뜨고, 창을 닫거나 다른 화면으로 가도 남습니다. 변환이 끝나면 '분석 완료 [검수]'(그 회차의 STT 검수로)가 3초 보이고 사라지며, 실패하면 '원문 변환에 실패했어요 [다시 변환]' 이 6초 보입니다. 디자인의 '분석' 은 원문 변환(STT)이고, AI 분석은 STT 검수 · 원문 확정 뒤에 따로 요청합니다. 로그인 화면 · 시작 화면에서는 보이지 않고, 다른 계정으로 바뀌면 버립니다. 새로고침하면 사라집니다(화면 상태).
- 사례 상세 '녹음하기': 회차(녹취 올리기와 같은 목록)를 고르고 녹음 동의를 확인한 뒤 녹음 · 일시정지 · 정지 · 들어 보기 · 다시 녹음, '저장' 하면 녹취 올리기와 같은 흐름으로 올리고 원문 변환까지 기다립니다. 상담 유형 · 녹음 동의는 Backend 에 칸이 없어 저장하지 않습니다(상담 유형은 준비 중). 녹음 중이거나 올리지 않은 녹음이 있으면 화면을 떠날 때 묻습니다. '현재 진행 상황' 칸은 가장 최근 회차의 그 단계 화면 링크이고, 사례 상단 탭에서 빠진 아이 연계는 '기본 정보' 옆 '아이 연계 →' 로 들어갑니다.
- 홈: 미처리 업무는 회차 처리 대기(`/tasks` 7종)만 셉니다. 줄을 누르면 그 회차에서 이어서 할 화면(녹취 올리기 · STT 검수 · 유형별 위험도 · 요약 · 일지 작성)으로 갑니다. 오래 기다린 업무는 '지연'(위험 신호가 아니라 '긴급' 이라고 쓰지 않음)입니다. 관리자는 사례 목록을 담당자로 거를 수 없어 두 숫자 모두 전체(라벨에 '전체')로 둡니다. 오늘 일정 · 다음 상담까지 남은 시간 · 아이 앱 긴급 응답은 서버에 없어 `—` · 준비 중이고, 시계 · 빠른 실행(편집은 저장하지 않음)은 화면 상태입니다.
- 문서함: 회차마다 녹음(파일 이름 · 올린 날) · STT 원문(변환 상태 · 검수 필요/완료 · 버전) · 문서(상담일지 작성 중/승인)를 한 줄씩 보입니다. 녹음은 회차 상세, 원문은 STT 검수, 상담일지는 요약 · 일지 작성 화면으로 갑니다. 기관 서식 6종의 작성 기록 · 상담 전 브리핑 · 외부 문서(PDF · HWPX) 올리기는 서버에 없어 준비 중입니다('자료 올리기' 는 녹음 올리기 창). '초기면접지 (아동용)' 줄의 '열기' 는 초기면접지 화면으로 갑니다.
- 초기면접지(10/22 디자인, `CaseIntake.jsx`): 새 사례 등록과 같은 서식에 사례 값을 채워 사례 상세 안에서 엽니다. 사례 제목 · 아동 별칭 · 성별 · 출생연도 · 보호자 유형(기타면 관계 메모) · 사례 메모 · 가정상황 · 아동 특성(담당 상담원은 관리자만)을 고쳐 '저장' 하면 고친 칸만 보냅니다. 개별사건번호는 서버가 바꾸지 않아 읽기만 하고, 나머지 칸은 사례 등록처럼 준비 중입니다(개인정보 저장 범위 팀 결정 전). 디자인의 '임시 저장' · '확정' 은 서버에 확정 상태가 없어 '저장' 하나입니다.
- 시작 화면(10/22 디자인, `Landing.jsx`): 소개와 '로그인' 단추. 위쪽 메뉴 · 아래 링크는 연결할 화면이 없어 글자만이고, '서비스 둘러보기' 는 화면 목록(`/`)으로 갑니다. 기능 카드 오른쪽 위 장식 도형은 10/27 디자인대로 뺐습니다.
- 종결 검토 내역 확인(예시 화면): 10/22 디자인대로 모두 확인하지 않아도 '종결보고서 작성' 으로 갈 수 있습니다.
- 일정: 회차의 상담 일시 · 장소만 달력에 '상담 회차' 로 놓습니다(관리자는 담당 상담사도 붙임). 고른 날의 회차를 누르면 회차 상세로 갑니다. 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 빼고 몇 건인지 알립니다. 개인 · 기관 일정, 일정 추가 · 중요 표시 · 팀 공유는 일정과 회차의 관계가 팀 결정 전이라 준비 중입니다.
- 종결 검토 목록: 사례 기본정보(별칭 · 출생연도 · 사례 ID · 사례 상태) · 회차 수 · 사례 등록일만 보이고, 누르면 사례 상세로 갑니다. 종결 검토 등록 · 진행 단계 · 내역 검토 진행률은 서버에 없어 준비 중이고, **이 목록은 종결 검토 대상 목록이 아닙니다**(종결(CLOSED) 사례를 '검토 대기' 로 쓰지 않음). 별칭 · 사례 ID 검색은 불러온 목록 안에서 하고, 검색어는 입력한 계정에 묶여 다른 계정으로 바뀌면 비웁니다(`useAccountSearch`).
- 통계: 사례 수 · 지금 진행/종결 수, 기간 안에 등록한 사례 수 · 등록 추이(사례 등록일 기준 — **신고접수일이 아님**), 기간 안의 상담 회차 수 · 추이(상담 일시 기준, 일시 없는 회차는 뺌)만 셉니다. 기간 프리셋 · 직접 선택 · 달력은 화면 상태입니다. 불러오기 전 · 불러오지 못했을 때 추이는 0 이 아니라 `—` 와 안내로 둡니다. 신고 접수 · 학대 판단 · 재신고 · 서비스 지표, 유형 · 연령 · 행위자 · 서비스 분포, AI 요약은 원천 데이터 · 지표 정의가 팀 결정 전이라 `—` · 준비 중입니다. 상담원은 담당 사례, 관리자는 전체 사례 기준입니다. 10/21 디자인대로 프리셋은 전체 · 이번 달 · 최근 3개월 · 직접 선택 순서이고, 직접 선택은 글자 입력 + 연 → 월 → 일 팝업(`components/StatsDateField.jsx`)입니다. 치는 중인 글자는 있는 날짜이면서 '모은 자료의 가장 이른 날 ~ 오늘' 안일 때만 기간에 넣고(칸을 나가면 원래 날짜로), 숫자 8자리도 받습니다.
- 설정 화면: 이름 · 이메일 · 역할 · 계정 만든 날은 내 정보에서, 비밀번호는 현재 비밀번호를 넣고 바꿉니다(바꾸면 로그아웃 → 로그인 화면). 이름 · 이메일 바꾸기, 소속 기관, 마지막 비밀번호 변경일, 알림 설정은 서버에 없어 `—` · 준비 중입니다. 왼쪽 메뉴의 '설정' 을 다시 누르거나 다른 화면에 다녀오면 첫 화면으로 돌아가고 비밀번호 칸을 비웁니다(10/21 디자인). 디자인의 '계정' 진입 전 비밀번호 확인 창은 서버에 비밀번호만 확인하는 API 가 없어 만들지 않았습니다(재인증은 팀 결정).
- 상담일지는 Backend 에서 제목 · 본문 텍스트 하나입니다. 화면의 칸(아동 진술 · 대상자 태도 · 물리적 환경 · 아동 특성 · 가정상황 · 위험 신호 검토 결과 · 상담원 소견)은 `[칸 이름]` 머리줄로 나눠 본문에 담습니다(`noteWrite.ts` 의 `formatNote` · `parseNote`). 기관 양식 구조가 정해지기 전의 임시 형식입니다.
- 사례 상세 · 초기면접 내용: 내담자 정보 탭의 '초기면접 내용' 카드(디자인에 없어 더한 칸)에 사례 등록 ② 탭에서 고른 가정상황 · 아동 특성을 단어로 보입니다. '수정' 을 누르면 사례 등록과 같은 고르기 단추(서식 4 항목, `intakePick.ts`)로 고치고 '저장' 하면 두 목록을 통째로 바꿉니다(모두 빼면 빈 목록). 바꾼 것이 없으면 보내지 않고 닫고, 저장하지 않고 다른 화면으로 가려 하면 한 번 묻습니다. 저장 응답이 오기 전에 다른 사례에 갔다 돌아왔거나 다시 로그인했으면 응답을 화면에 합치지 않고, 화면이 같은 사례를 보고 있으면 지금 로그인으로 다시 조회해 저장된 값을 보입니다(`useRemote` 의 `resync`). ② 탭의 나머지 칸은 여전히 준비 중이라 이 카드에도 없습니다.
- 일지의 아동 특성 · 가정상황: 사례 등록 때 초기면접(서식 4 ②)에서 고른 항목(Backend `intake_child_traits` · `intake_family_situations`)은 단어로만 보이고, 나머지 서식 4 항목(`intakeItems.ts`, 사례 등록 · Backend 와 같은 목록)은 칸마다 '수정' 으로 고르기 단추를 펼쳐 추가로 고르고 '확인' 으로 접습니다(10/21 디자인. 펼침은 화면 상태이고, 고른 것은 바로 일지 초안에 들어가 저장 · 승인은 '일지 저장' · '일지 승인' 이 합니다. 접으면 이 일지에서 고른 항목만 보입니다). 본문에는 일지에서 추가로 고른 항목만 담습니다. 사례 정보를 받기 전 · 승인된 일지에서는 펼칠 수 없습니다. 일지를 쓴 뒤 사례 상세에서 초기면접을 고쳐 일지 항목과 겹치면, 그 항목은 '초기면접에도 있음' 을 붙여 체크한 채 남깁니다. 이미 저장된 일지에 담긴 항목이면 체크를 풀어도 일지를 저장할 때까지 목록에 남아 다시 고를 수 있고, 저장하면 본문과 목록에서 빠집니다(저장하지 않은 초안에만 있던 항목은 체크를 풀면 바로 목록에서 빠집니다). 저절로 지우지는 않습니다.

## 폴더 구조

```
src/
  main.jsx            진입점 (공통 CSS 로드)
  App.jsx             라우터 — src/pages/*.jsx 를 '/파일이름' 경로로 자동 등록 (HashRouter)
  Overview.jsx        첫 화면: 흐름별 화면 목록
  dc.js               화면 로직 어댑터 (DCLogic · useDC)
  components/A.jsx    화면 간 이동 링크 (내부 경로는 react-router Link)
  components/Notice.jsx 화면 위 한 줄 안내 (불러오는 중 · 오류 · 대상 없음)
  components/Sidebar.jsx 상담원 화면 왼쪽 메뉴 (문서함 '준비 중' · 900px 이하 메뉴 토글 · 내 정보 · 로그아웃 · 관리자 메뉴)
  components/JobToast.jsx 화면 위쪽 원문 변환 알림 (App.jsx 가 모든 화면 위에 한 번)
  components/SttPlayer.jsx STT 검수 아래 재생 바 (재생은 준비 중 · 확인할 곳 표시)
  components/AdminSidebar.jsx 관리자 화면 왼쪽 메뉴 (아이 연계 앱 · 열람 기록 '준비 중' · 업무 처리 현황 등 기존 기능 · 권한 없음 안내)
  components/ThemeToggle.jsx 밝은 · 어두운 화면 스위치
  theme.js            다크 모드 상태 (브라우저에만 기억)
  styles/common.css   공통 스타일 (사이드바 · 카드 · 칩 · 버튼 · 탭 · 단계 표시 · 다크 모드 · 반응형 · 각진 모서리 등)
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
- 사이드바 · 사례 상세 탭은 지금 각 화면에 복사돼 있습니다. 첫 리팩터링으로 `components/` 로 빼는 걸 추천합니다. 회차 처리 4단계 표시는 `components/StepNav.jsx` 로 뺐습니다(10/27).

## 디자인 기준

원본은 다솔 님 디자인 `counselor-web-design/*.dc.html`(Claude Design 캔버스, `front_new` 브랜치)입니다. 화면 JSX 는 그 마크업을, `src/styles/common.css` 는 20개 이상 화면이 똑같이 쓰는 규칙을, `src/pages/<화면>.css` 는 그 화면에만 있는 규칙을 옮긴 것입니다. 10/21 새 디자인(`origin/frontend261021` 의 `counselor-design/`)의 공통 틀(왼쪽 메뉴 · 반응형 · 모서리)은 `Sidebar.jsx` 와 `common.css` 끝 블록으로 옮겼습니다. 10/27 판(같은 브랜치 `c766848`)에서 더해진 법령 · 매뉴얼 화면 · 메뉴와 시작 화면 장식 제거도 옮겼습니다.

| 용도 | 색 |
|---|---|
| 본문 바탕 / 왼쪽 레일 | `#F2F2F0` / `#E9E7E1` (본문이 레일에 이어진 모양, 현재 메뉴는 금색 점) |
| 먹색 (주요 버튼 · 글자) | `#2B2A26`, 버튼 글자 `#EADBB5` |
| 금색 포인트 (선택 테두리 · 초점 · 현재 탭) | `#C2A36B` · 링크 `#8C7340` |
| 긴급 · 위험도 '상' | `#A33B2E` / 배경 `#F7E4DF` |
| 위험도 '중' | 글자 `#7A5F28` / 배경 `#F3EAD3` |
| 그 밖 | 무채색 (보조 `#6E6A62` · `#7A776F`, 테두리 `#E2DED3` · `#DAD5C9`) |

- 글꼴: 본문 IBM Plex Sans KR, 제목(h1 · 로고) Noto Serif KR (Google Fonts, `index.html`)
- 카드 · 단추 · 입력칸은 부분 뉴모피즘 그림자(`--sd` · `--sl`)를 씁니다. 모서리 크기는 아래 '모서리(각진 UI)' 줄을 따릅니다.
- 다크 모드: 화면 오른쪽 위 스위치(`components/ThemeToggle.jsx`). 이 브라우저에만 기억하고(localStorage `ispot-theme`) 서버에는 저장하지 않습니다(`src/theme.js`). 화면 맨 바깥 div 에 `useTheme().cls` 를 붙이면 `common.css` 의 다크 모드 규칙이 걸립니다. 이 규칙은 인라인 style 의 색을 찾아 바꾸므로 **화면 JSX 와 값 함수의 색은 위 색표(디자인 값)만 씁니다.**
- 왼쪽 메뉴는 `components/Sidebar.jsx` 하나를 모든 상담원 화면이 씁니다. 메뉴 옆 숫자(디자인의 예시 값)는 넣지 않았고, 관리자 계정이면 '관리자 메뉴' 링크(`#/AdminHome`)가 더 보입니다. 관리자 화면(`Admin*.jsx`)은 관리자 계정만 보이고 왼쪽 메뉴는 `components/AdminSidebar.jsx` 입니다.
- 900px 이하에서는 메뉴가 위쪽 띠로 바뀌고 '메뉴' 단추(`#mnav` 체크박스 + 라벨)로 펼칩니다. JS 상태가 없어서 화면을 옮기면 저절로 닫힙니다. '문서함' 은 화면(DocBox)이 생길 때까지 링크 없이 '준비 중' 입니다. 문서함과 통계 사이의 '법령 · 매뉴얼'(`LawGuide`)은 10/27 디자인에서 더해진 메뉴입니다.
- 반응형은 `common.css` 끝 블록입니다(1100 · 900 · 600px). 1100px 이하는 메뉴 폭 220px · 본문 여백 24px, 900px 이하는 메뉴 띠 · 본문 전체 폭, 600px 이하는 격자 1열 · 단계 2×2. 휴대폰 · 태블릿 화면 12개는 웹 6화면의 복사본이라 따로 만들지 않고 이 규칙으로 봅니다.
- 모서리(각진 UI): 버튼 · 입력 10px, 칩 6px, 카드 14px, 묶음 버튼(`.seg` · `.tabs`) 12px / 8px. 실명 보기 단추(`.tg`)는 12px. 아바타(`.av`) · 단계 번호(`.sn`) · 다크 스위치(`.thm-tg`)는 원형을 유지합니다.
- 위험도는 상 / 중 / 하로만 표시 (점수 · % 없음)
- 색은 중요한 곳에만. 보충 설명 문구는 최소로.

## 지켜야 할 원칙 (AI 기능)

1. AI는 제안만 합니다. 신고 · 판정 · 종결 결정은 상담원이 합니다.
2. AI가 만든 내용은 항상 `AI 초안` / `AI 제안` 으로 표시합니다.
3. 모든 제안에는 근거 위치(몇 회차 몇 분, 아이 연계 몇 월 며칠)를 함께 보여 줍니다.
4. 서로 다른 진술은 합치지 않고 그대로 나란히 둡니다.
5. 아이의 무응답은 위험 신호가 아닙니다.
6. 보호자 진술은 아이에게 할 질문의 근거로 쓰지 않습니다.
7. 추가 질문은 질문 은행에서만 제안하고, 상담원이 고친 질문은 `상담사 수정` 으로 표시합니다. AI 확인 메모(`followup_check_points`)는 질문이 아니라 '메모' 로만 보입니다(10/26).
8. 화면의 모든 내용은 상담원이 고칠 수 있어야 합니다.

## 화면 목록

**① 하루 시작 · 로그인 → 홈 → 일정 → 아이 연계 → 아이 상세**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/Landing` | `src/pages/Landing.jsx` | 시작 화면(소개 · 로그인) |
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

**③ 사례 상세 · 탭 4개 (내담자 정보 · 상담 이력 · 상담 전 브리핑 · 문서함) + 아이 연계(기본 정보 옆 단추) + 기관 서식 작성**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/CaseDetail` | `src/pages/CaseDetail.jsx` | 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록 |
| `/#/CaseHistory` | `src/pages/CaseHistory.jsx` | 탭 2 · 상담 이력 (① 지금까지 상담 → ② 상담 회차 → ③ 회차별 세부 신호) |
| `/#/SessionDetail` | `src/pages/SessionDetail.jsx` | 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기) |
| `/#/PreBriefing` | `src/pages/PreBriefing.jsx` | 탭 3 · 상담 전 브리핑 |
| `/#/CaseApp` | `src/pages/CaseApp.jsx` | 내담자 정보 › 아이 연계 (아이 상세와 같은 화면, 탭 없음) |
| `/#/CaseDocs` | `src/pages/CaseDocs.jsx` | 탭 4 · 문서함 (기관 서식 6종 + 파일) |
| `/#/CaseIntake` | `src/pages/CaseIntake.jsx` | 탭 4 › 초기면접지 (서식 4, 사례 값 채움 · 서버가 받는 칸 저장) |
| `/#/CaseForm` | `src/pages/CaseForm.jsx` | 탭 4 › 기관 서식 작성 (사정기록지 안전영역 · 사례관리 점검표 · 위험수준 척도 · 가족관계 척도) |

**④ 회차 처리 · 녹취 올리기 → STT 검수 → 유형별 위험도 → 요약 · 일지 작성 → 추가 확인 · 질문**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/UploadModal` | `src/pages/UploadModal.jsx` | 녹취 · 자료 올리기 (팝업 3단계 + 확인창) |
| `/#/SttReview` | `src/pages/SttReview.jsx` | 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원) |
| `/#/SignalReview` | `src/pages/SignalReview.jsx` | 2 · 유형별 위험도 (AI 제안 · 심각도 1~5 · 상담원 판단) |
| `/#/RiskProfile` | `src/pages/RiskProfile.jsx` | 옛 주소 — 유형별 위험도(`SignalReview`)로 넘김 |
| `/#/NoteWrite` | `src/pages/NoteWrite.jsx` | 3 · 상담 요약 (사정 관점) · 상담 일지 (기관 양식) |
| `/#/FollowupQ` | `src/pages/FollowupQ.jsx` | 4 · 추가 확인 · 질문 (AI 확인 메모 · 수정 · 추가 질문은 준비 중) |

**⑤ 종결 검토 (목록 → 전체 내역 검토 → 종결보고서) · 통계 · 설정 · 법령 · 매뉴얼 · 관리자**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/Closure` | `src/pages/Closure.jsx` | 종결 검토 · 대상 아동 목록 |
| `/#/ClosureReview` | `src/pages/ClosureReview.jsx` | 종결 검토 › ① 전체 상담 내역 검토 (핵심 요약 + 근거 · 확인 후 보고서로) |
| `/#/ClosureDetail` | `src/pages/ClosureDetail.jsx` | 종결 검토 › ② 사례관리 종결보고서 (서식 29 · AI 초안) |
| `/#/Stats` | `src/pages/Stats.jsx` | 통계 (기간 직접 선택 · 원형 · 가로/세로 막대 · 표) |
| `/#/Settings` | `src/pages/Settings.jsx` | 설정 · 계정 / 알림 설정 |
| `/#/LawGuide` | `src/pages/LawGuide.jsx` | 법령 · 매뉴얼 (AI 질문은 준비 중 · 업무 단계별 참고사항 · 주요 조문 · 원문 링크) |
| `/#/AdminHome` | `src/pages/AdminHome.jsx` | 관리자 · 홈(기관 현황 · 처리 대기 업무 · 최근 접속 · 상담원별 업무량) |
| `/#/AdminAccounts` | `src/pages/AdminAccounts.jsx` | 관리자 · 상담사 계정 관리 |
| `/#/AdminStaffDetail` | `src/pages/AdminStaffDetail.jsx` | 관리자 · 상담사 상세(계정 요청) |
| `/#/AdminSecurity` | `src/pages/AdminSecurity.jsx` | 관리자 · 접속 기록 · 보안 이벤트 |
| `/#/AdminStats` | `src/pages/AdminStats.jsx` | 관리자 · 통계 · 보고 |
| `/#/AdminTasks` | `src/pages/AdminTasks.jsx` | 관리자 · 업무 처리 현황(디자인에 없는 기존 기능) |
| `/#/Admin` | `src/pages/Admin.jsx` | 옛 주소 → 위 화면으로 넘김 |

## 참고

- 기관 서식은 「2026년 아동학대 대응 업무 매뉴얼」 양식(서식 4 초기면접지, 서식 6 사정기록지, 서식 27 사례관리 점검표, 서식 29 사례관리 종결보고서, 참고자료 1 · 3 척도)을 따랐습니다.
- 모든 이름 · 사례 · 수치는 가상 데이터입니다.
