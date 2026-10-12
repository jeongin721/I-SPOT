# I-SPOT 상담사 웹 (프론트엔드 프로토타입)

아동보호전문기관 상담원용 웹 화면입니다. 디자인 캔버스에서 함께 만든 25개 화면을 **React + Vite** 코드로 옮겼습니다.
모든 화면은 예시(가상) 데이터로 동작하며, 버튼 · 탭 · 체크 · 수정 등 화면 안의 동작은 실제로 눌러 볼 수 있습니다.

## 실행

```bash
npm install
npm run dev        # http://localhost:5173  → 첫 화면은 '화면 목록'
npm run build      # dist/ 에 배포용 파일 생성
```

- Node.js 18 이상
- 화면 주소: `http://localhost:5173/#/Main`, `#/CaseDetail` 처럼 `#/파일이름`
- 위치: I-SPOT 저장소의 `counselor-web/` 폴더 (기존 `ispotvscode/` 와 별개)

## 폴더 구조

```
src/
  main.jsx            진입점 (공통 CSS 로드)
  App.jsx             라우터 — src/pages/*.jsx 를 '/파일이름' 경로로 자동 등록 (HashRouter)
  Overview.jsx        첫 화면: 흐름별 화면 목록
  dc.js               화면 로직 어댑터 (DCLogic · useDC)
  components/A.jsx    화면 간 이동 링크 (내부 경로는 react-router Link)
  styles/common.css   공통 스타일 (사이드바 · 카드 · 칩 · 버튼 · 탭 · 단계 표시 등)
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

- 예시 데이터는 각 화면 `renderVals()` 안에 있습니다. API 연결 시 이 부분을 fetch 결과로 바꾸면 됩니다.
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

**④ 회차 처리 · 녹취 올리기 → STT 검수 → 위험 신호 검토 → 요약 · 일지 작성 → 추가 확인 · 질문**

| 경로 | 파일 | 화면 |
|---|---|---|
| `/#/UploadModal` | `src/pages/UploadModal.jsx` | 녹취 · 자료 올리기 (팝업 3단계 + 확인창) |
| `/#/SttReview` | `src/pages/SttReview.jsx` | 1 · STT 검수 (화자: 피해아동 · 사례관리대상자 · 상담원) |
| `/#/SignalReview` | `src/pages/SignalReview.jsx` | 2 · 위험 신호 검토 |
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
