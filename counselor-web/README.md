# I-SPOT 상담사 웹 (프론트엔드 프로토타입)

아동보호전문기관 상담원용 웹 화면입니다. 디자인 캔버스에서 함께 만든 26개 화면을 **React + Vite** 코드로 옮겼습니다.
모든 화면은 예시(가상) 데이터로 동작하며, 버튼 · 탭 · 체크 · 수정 등 화면 안의 동작은 실제로 눌러 볼 수 있습니다.
**로그인 · 홈 · 통합 사례 관리 · 새 사례 등록 · 사례 상세(내담자 정보 · 상담 이력 · 문서함) · 회차 상세 · 녹취 올리기 · STT 검수 · 위험 신호 검토 · 요약 · 일지 작성 · 일정 · 종결 검토 목록 · 통계 · 설정 · 관리자 화면은 Backend 와 연결돼 있습니다**(아래 "서버 연결"). 나머지 화면은 아직 예시 데이터입니다.

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
| 사례 상세 · 상담 이력 | `useCaseDetail` · `sessionRows` | 사례 정보와 회차 목록. 처리 중인 회차가 있으면 끝날 때까지 다시 조회 |
| 일정 · 종결 검토 목록 · 통계 | `useCaseOverview` | 볼 수 있는 사례를 모두(100건씩 쪽마다) 모으고, 사례마다 회차 목록(`"sessions"`) 또는 회차 수만(`"counts"`) 부름(한 번에 4사례씩, 사례 2,000건 · 사례당 회차 1,000개까지). 집계 API 는 없음 |
| 사례 문서함 | `useCaseDocuments` | 사례의 회차마다 회차 상세(녹음 · 원문 상태) + 문서 목록을 모음(한 번에 4회차씩). 사례 단위 문서 API 는 없음 |
| 회차 상세 | `useSessionDetail` | 회차 진행 단계 · 실패 문구 · 음성 파일 정보, 지금 할 수 있는 요청 |
| 녹음 업로드 | `useAudioUpload` · `audioFile` | (새 회차) → 음성 올리기 → 원문 변환 요청 → 끝날 때까지 기다리기. 실패하면 그 단계부터 다시(새 회차를 또 만들지 않음) |
| 원문(STT) 검수 | `useTranscriptReview` · `transcriptRows` | 발화 줄 · 저신뢰 · 화자 미확인, 고친 칸만 저장, 확정, 다시 변환 |
| AI 분석 | `useSessionAnalysis` | 분석 요청 · 진행 · AI 원본 요약과 안내(위험 신호 배열은 팀 결정 전이라 내보내지 않음) |
| 요약 검수 · 승인 | `useSummaryReview` | 요약 고치기 · 근거 발화 · 승인(승인하면 회차가 '승인 완료' 가 되어 더 고칠 수 없음) |
| 상담일지 | `useSessionDocuments` | 문서 목록 · 만들기 · 고치기 · 승인(회차 상태와 따로 움직임) |
| 유형별 위험도(상담원 판단) | `useRiskAssessments` | 네 유형(신체 · 정서 · 성 · 방임)의 상담원 판단(상 · 중 · 하) · 이유 · 판단 당시 AI 제안(1~5) 조회와 저장. 원문 확정 뒤에만 저장, 회차 상태는 바뀌지 않음. AI 단계 ↔ 상 · 중 · 하 대응과 사례 단위 위험도는 팀 결정 전이라 계산하지 않음. `RiskProfile` 화면에는 아직 연결하지 않음 |
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
| `view` | `tasks` · `accounts` · `audit`(없으면 대시보드) | 관리자 화면의 보기(업무 처리 현황 · 상담사 계정 관리 · 접속 기록). `readAdminView` · `adminHref`(`src/data/screens/admin.ts`) |

- 예: `#/CaseDetail?case=…`, `#/SessionDetail?case=…&session=…`
- 읽기는 `readScreenIds(useSearchParams()[0])`, 만들기는 `screenHref('/SessionDetail', { caseId, sessionId })`(`src/data/screens/links.ts`). 주소 문자열을 직접 이어 붙이지 않습니다.
- 회차 화면은 `session` 만 있어도 됩니다. 사례는 회차 정보에서 찾고, 주소의 `case` 와 다르면 회차 쪽을 씁니다. 링크를 만들 때는 아는 ID 를 모두 넣습니다.
- 필요한 ID 가 없거나 없는 사례 · 회차면 화면 위에 안내와 돌아갈 링크를 보입니다(`screenNotice` → `components/Notice.jsx`).
- 아직 예시 데이터인 화면(추가 확인 · 질문, 유형별 위험도, 상담 전 브리핑, 아이 연계, 서식)도 들어올 때 받은 ID 를 다음 화면 링크에 넘깁니다:
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
- 공용: 사이드바 내 이름 · 로그아웃 `sidebarValues`, 로그인 화면으로 보낼지 `needsLogin`, 화면 위 안내 `screenNotice`, 회차 상태 칩 `TONE_CHIP`(`common.ts`), 회차 단계 → 다음 화면 `continueLink` · 회차 처리 단계 표시 `processNav`(`flow.ts`), 회차 처리 화면 머리 `processHeaderValues`(`process.ts`). 요청 응답 뒤 이동 `useScreenGo`(그사이 다른 회차 · 화면으로 옮겼으면 옮기지 않음), 저장하지 않은 수정이 있을 때 떠나기 전 확인 `useLeaveGuard`(값 함수의 `unsaved` 를 넘김, 뒤로 가기는 못 막음).
- `Login.jsx` 는 아직 값 계산이 화면 파일 안에 있습니다(이 규칙 전에 연결).

| 화면 | 화면 파일 | 주소 | 훅 | 값 함수(`src/data/screens/`) |
| --- | --- | --- | --- | --- |
| 홈 | `Main.jsx` | — | `useAuthSession` · `useHomeDashboard` | `main.ts` `mainValues` |
| 통합 사례 관리 | `CaseList.jsx` | — | `useAuthSession` · `useCaseList` | `caseList.ts` `caseListValues` |
| 새 사례 등록 | `CaseRegister.jsx` | — | `useAuthSession` · `useCaseRegister` | `caseRegister.ts` `caseRegisterValues` |
| 사례 상세 · 내담자 정보 | `CaseDetail.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseDetailValues` |
| 사례 상세 · 상담 이력 | `CaseHistory.jsx` | `case` | `useCaseDetail` | `caseDetail.ts` `caseHistoryValues` |
| 사례 상세 · 문서함 | `CaseDocs.jsx` | `case` | `useCaseDetail` · `useCaseDocuments` | `caseDocs.ts` `caseDocsValues` |
| 회차 상세 | `SessionDetail.jsx` | `case` · `session` | `useSessionDetail` · `useCaseDetail`(회차의 사례) | `sessionDetail.ts` `sessionDetailValues` |
| 녹취 · 자료 올리기 | `UploadModal.jsx` | (`case` · `session`) | `useCaseList` · `useCaseDetail`(고른 사례) · `useAudioUpload` | `uploadModal.ts` `uploadModalValues` |
| 1 · STT 검수 | `SttReview.jsx` | `case` · `session` | `useTranscriptReview` + 머리 `useSessionDetail` · `useCaseDetail` | `sttReview.ts` `sttReviewValues` |
| 2 · 위험 신호 검토 | `SignalReview.jsx` | `case` · `session` | `useSessionAnalysis` + 머리 | `signalReview.ts` `signalReviewValues` |
| 3 · 요약 · 일지 작성 | `NoteWrite.jsx` | `case` · `session` | `useSummaryReview` · `useSessionDocuments` + 머리 | `noteWrite.ts` `noteWriteValues` |
| 일정 | `Schedule.jsx` | — | `useAuthSession` · `useCaseOverview`(`sessions`) | `schedule.ts` `scheduleValues` |
| 종결 검토 목록 | `Closure.jsx` | — | `useAuthSession` · `useCaseOverview`(`counts`) | `closure.ts` `closureValues` |
| 통계 | `Stats.jsx` | — | `useAuthSession` · `useCaseOverview`(`sessions`) | `stats.ts` `statsValues` |
| 설정 | `Settings.jsx` | — | `useAuthSession` · `usePasswordChange` | `settings.ts` `settingsValues` |
| 관리자 | `Admin.jsx` | (`view`) | `useAdminDashboard` · `useAdminTasks`(대시보드 탭 2종 · 업무 보기) · `useAdminAccounts` · `useAuditLogs` | `admin.ts` `adminValues` |

- 회차 처리 흐름: 녹취 올리기 → STT 검수(고친 발화 저장 · 원문 확정) → 위험 신호 검토(AI 분석 요청 · 진행 · 실패 뒤 다시 분석) → 요약 · 일지 작성(요약 고치기 · 저장 · **요약 승인 = 회차 '승인 완료'**, 상담일지 저장 · 승인).
- 위험 신호 카드 · 채택/보류/제외는 서버(AI)가 아직 신호를 주지 않아 준비 중입니다. 위험 신호 검토 화면은 AI 분석 상태와 AI 안내만 보입니다.
- '요약 승인' · '일지 승인' 은 누르면 (고친 칸을 저장하고) 바로 승인합니다. 요약 승인은 회차를 '승인 완료' 로 바꿉니다. 승인한 칸에는 '요약 수정' · '일지 수정' 단추만 보이고, 누르면 쓴 내용 그대로 승인이 풀려 고친 뒤 다시 승인합니다(요약을 풀면 회차는 'AI 결과 검수 필요' 로 돌아갑니다). '저장 · 추가 확인 · 질문 →' 은 저장만 합니다.
- 관리자 화면: 디자인은 대시보드 한 장이라 왼쪽 메뉴의 업무 처리 현황 · 상담사 계정 관리 · 접속 기록은 같은 화면의 다른 보기(`?view=`)로 두고 디자인의 카드 · 표 · 칩을 그대로 씁니다. 상담원 계정이면 훅이 서버를 부르지 않고 안내만 보입니다. 대시보드 업무 탭은 Backend 가 종류를 하나만 거를 수 있어 두 종류씩 불러 오래 기다린 순서로 합칩니다(원문 변환 · 상담사 검토 · AI 분석). 계정 만들기 · 비밀번호 초기화 · 휴면 해제의 임시 비밀번호는 화면 상태에만 한 번 두고 '닫기' 로 버립니다(다른 관리자로 바뀌면 보이지 않음). 비밀번호 초기화 · 휴면 해제 · 비활성화 · 강제 로그아웃은 한 번 더 묻습니다. 미배정 사례 · 문서 승인 · 보안 경고 · 재처리 요청은 서버에 없어 `—` · 준비 중입니다.
- 새 사례 등록: 서버에 저장하는 칸은 사례 제목 · 아동 별칭(필수), 개별사건번호(비우면 Backend 가 `C-YYYY-NNNN` 으로 만듦, 겹치면 거절 문구) · 성별 · 출생연도 · 보호자 유형(기타면 관계 메모) · 사례 메모, 담당 상담원(관리자만 고름, 상담원은 본인)입니다. 등록되면 새 사례 상세(`?case=새 ID`)로 갑니다. 서식 4 의 나머지 칸(실명 · 생년월일 · 사례관리대상자 · 신고 · 연계 · 면접일 · 학대유형 · 조치결과 · 위험도 · 사례연계 경위, ② 초기면접 내용 탭 전체)은 개인정보 저장 범위가 팀 결정 전이라 입력을 막고 '준비 중' 으로 둡니다. 그 내용을 사례 메모 등 다른 칸에 옮겨 담지 않습니다. 화면 칸 '대상아동 이름' · '생년월일' · '관계' 는 '아동 별칭' · '출생연도' · '보호자 유형' 으로 바꿨습니다(사례관리대상자는 보호자와 같은 뜻이 아니어서 따로 준비 중).
- 홈: 미처리 업무는 회차 처리 대기(`/tasks` 7종)만 셉니다. 줄을 누르면 그 회차에서 이어서 할 화면(녹취 올리기 · STT 검수 · 위험 신호 검토 · 요약 · 일지 작성)으로 갑니다. 오래 기다린 업무는 '지연'(위험 신호가 아니라 '긴급' 이라고 쓰지 않음)입니다. 관리자는 사례 목록을 담당자로 거를 수 없어 두 숫자 모두 전체(라벨에 '전체')로 둡니다. 오늘 일정 · 다음 상담까지 남은 시간 · 아이 앱 긴급 응답은 서버에 없어 `—` · 준비 중이고, 시계 · 빠른 실행(편집은 저장하지 않음)은 화면 상태입니다.
- 문서함: 회차마다 녹음(파일 이름 · 올린 날) · STT 원문(변환 상태 · 검수 필요/완료 · 버전) · 문서(상담일지 작성 중/승인)를 한 줄씩 보입니다. 녹음은 회차 상세, 원문은 STT 검수, 상담일지는 요약 · 일지 작성 화면으로 갑니다. 기관 서식 6종의 작성 기록 · 상담 전 브리핑 · 외부 문서(PDF · HWPX) 올리기는 서버에 없어 준비 중입니다('자료 올리기' 는 녹음 올리기 창).
- 일정: 회차의 상담 일시 · 장소만 달력에 '상담 회차' 로 놓습니다(관리자는 담당 상담사도 붙임). 고른 날의 회차를 누르면 회차 상세로 갑니다. 상담 일시를 넣지 않은 회차는 등록일로 대신하지 않고 빼고 몇 건인지 알립니다. 개인 · 기관 일정, 일정 추가 · 중요 표시 · 팀 공유는 일정과 회차의 관계가 팀 결정 전이라 준비 중입니다.
- 종결 검토 목록: 사례 기본정보(별칭 · 출생연도 · 사례 ID · 사례 상태) · 회차 수 · 사례 등록일만 보이고, 누르면 사례 상세로 갑니다. 종결 검토 등록 · 진행 단계 · 내역 검토 진행률은 서버에 없어 준비 중이고, **이 목록은 종결 검토 대상 목록이 아닙니다**(종결(CLOSED) 사례를 '검토 대기' 로 쓰지 않음). 별칭 · 사례 ID 검색은 불러온 목록 안에서 하고, 검색어는 입력한 계정에 묶여 다른 계정으로 바뀌면 비웁니다(`useAccountSearch`).
- 통계: 사례 수 · 지금 진행/종결 수, 기간 안에 등록한 사례 수 · 등록 추이(사례 등록일 기준 — **신고접수일이 아님**), 기간 안의 상담 회차 수 · 추이(상담 일시 기준, 일시 없는 회차는 뺌)만 셉니다. 기간 프리셋 · 직접 선택 · 달력은 화면 상태입니다. 불러오기 전 · 불러오지 못했을 때 추이는 0 이 아니라 `—` 와 안내로 둡니다. 신고 접수 · 학대 판단 · 재신고 · 서비스 지표, 유형 · 연령 · 행위자 · 서비스 분포, AI 요약은 원천 데이터 · 지표 정의가 팀 결정 전이라 `—` · 준비 중입니다. 상담원은 담당 사례, 관리자는 전체 사례 기준입니다.
- 설정 화면: 이름 · 이메일 · 역할 · 계정 만든 날은 내 정보에서, 비밀번호는 현재 비밀번호를 넣고 바꿉니다(바꾸면 로그아웃 → 로그인 화면). 이름 · 이메일 바꾸기, 소속 기관, 마지막 비밀번호 변경일, 알림 설정은 서버에 없어 `—` · 준비 중입니다.
- 상담일지는 Backend 에서 제목 · 본문 텍스트 하나입니다. 화면의 칸(아동 진술 · 대상자 태도 · 물리적 환경 · 아동 특성 · 가정상황 · 위험 신호 검토 결과 · 상담원 소견)은 `[칸 이름]` 머리줄로 나눠 본문에 담습니다(`noteWrite.ts` 의 `formatNote` · `parseNote`). 기관 양식 구조가 정해지기 전의 임시 형식입니다.

## 폴더 구조

```
src/
  main.jsx            진입점 (공통 CSS 로드)
  App.jsx             라우터 — src/pages/*.jsx 를 '/파일이름' 경로로 자동 등록 (HashRouter)
  Overview.jsx        첫 화면: 흐름별 화면 목록
  dc.js               화면 로직 어댑터 (DCLogic · useDC)
  components/A.jsx    화면 간 이동 링크 (내부 경로는 react-router Link)
  components/Notice.jsx 화면 위 한 줄 안내 (불러오는 중 · 오류 · 대상 없음)
  components/Sidebar.jsx 상담원 화면 왼쪽 메뉴 (내 정보 · 로그아웃 · 관리자 메뉴)
  components/ThemeToggle.jsx 밝은 · 어두운 화면 스위치
  theme.js            다크 모드 상태 (브라우저에만 기억)
  styles/common.css   공통 스타일 (사이드바 · 카드 · 칩 · 버튼 · 탭 · 단계 표시 · 다크 모드 등)
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

원본은 다솔 님 디자인 `counselor-web-design/*.dc.html`(Claude Design 캔버스, `front_new` 브랜치)입니다. 화면 JSX 는 그 마크업을, `src/styles/common.css` 는 20개 이상 화면이 똑같이 쓰는 규칙을, `src/pages/<화면>.css` 는 그 화면에만 있는 규칙을 옮긴 것입니다.

| 용도 | 색 |
|---|---|
| 본문 바탕 / 왼쪽 레일 | `#F2F2F0` / `#E9E7E1` (본문이 레일에 이어진 모양, 현재 메뉴는 금색 점) |
| 먹색 (주요 버튼 · 글자) | `#2B2A26`, 버튼 글자 `#EADBB5` |
| 금색 포인트 (선택 테두리 · 초점 · 현재 탭) | `#C2A36B` · 링크 `#8C7340` |
| 긴급 · 위험도 '상' | `#A33B2E` / 배경 `#F7E4DF` |
| 위험도 '중' | 글자 `#7A5F28` / 배경 `#F3EAD3` |
| 그 밖 | 무채색 (보조 `#6E6A62` · `#7A776F`, 테두리 `#E2DED3` · `#DAD5C9`) |

- 글꼴: 본문 IBM Plex Sans KR, 제목(h1 · 로고) Noto Serif KR (Google Fonts, `index.html`)
- 카드 · 단추 · 입력칸은 부분 뉴모피즘 그림자(`--sd` · `--sl`)와 알약 모양 단추
- 다크 모드: 화면 오른쪽 위 스위치(`components/ThemeToggle.jsx`). 이 브라우저에만 기억하고(localStorage `ispot-theme`) 서버에는 저장하지 않습니다(`src/theme.js`). 화면 맨 바깥 div 에 `useTheme().cls` 를 붙이면 `common.css` 의 다크 모드 규칙이 걸립니다. 이 규칙은 인라인 style 의 색을 찾아 바꾸므로 **화면 JSX 와 값 함수의 색은 위 색표(디자인 값)만 씁니다.**
- 왼쪽 메뉴는 `components/Sidebar.jsx` 하나를 모든 상담원 화면이 씁니다. 메뉴 옆 숫자(디자인의 예시 값)는 넣지 않았고, 관리자 계정이면 '관리자 메뉴' 링크가 더 보입니다. 관리자 화면(`Admin.jsx`)은 관리자 계정만 보입니다.
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
