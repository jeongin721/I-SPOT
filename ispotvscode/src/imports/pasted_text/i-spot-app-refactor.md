현재 제작되어 있는 I-SPOT 웹 애플리케이션을 수정한다.

첨부된 모든 자료와 현재 프로젝트의 기존 코드를 반드시 먼저 분석한 후 작업한다.

참고 자료:
- FRONTEND_PROMPT
- I-SPOT 요구사항 정의서
- UI 스크린샷
- 기존 I-SPOT UI 리디자인 프롬프트
- 현재 Figma Make 프로젝트의 모든 React/TypeScript 소스코드

현재 프로젝트에 이미 존재하는 App.tsx, AdminApp.tsx,
CaseSelectorPanel.tsx, cases.ts 및 각 View 컴포넌트를 최대한 재사용한다.

특히 현재 존재하는 다음 View를 삭제하거나 새로 중복 생성하지 않는다.

- RecordingView
- TranscriptReviewView
- AIReviewView
- CasePlanView
- ClosureView
- ReportView

기존 디자인 시스템과 앞서 적용한 I-SPOT의 전문적인
enterprise case-management UI 스타일을 그대로 유지한다.

이번 수정의 핵심은 "새로운 디자인 생성"이 아니라

1. 모든 주요 버튼의 실제 동작 구현
2. 화면 간 navigation 구현
3. 사례/아동/상담회차 데이터 연결
4. 업무 Workflow 연결
5. 필요한 중간 목록 화면 및 상세 화면 추가
6. 실제 서비스 수준의 interaction 구현

이다.


━━━━━━━━━━━━━━━━━━━━
1. 전역 Navigation 원칙
━━━━━━━━━━━━━━━━━━━━

현재 화면에 존재하는 모든 버튼, 링크, 목록 행,
아동 이름, 사례 ID, 업무 항목 등 클릭 가능한 요소를 전수 조사한다.

사용자가 클릭할 것으로 예상되는 UI가
아무 반응도 하지 않는 상태를 허용하지 않는다.

각 요소에는 다음 중 하나의 명확한 동작을 연결한다.

- 페이지 이동
- 상세 화면 표시
- modal / popover 표시
- 상태 변경
- 작업 실행
- 다운로드
- 확인/취소
- 이전 화면 복귀

클릭 가능한 요소에는 hover / focus / active state를 제공한다.

단순히 alert()로 기능을 흉내 내지 않는다.

페이지 이동이 필요한 기능에는 실제 navigation을 구현한다.

기존 프로젝트 구조와 호환되는 방식으로
React Router 또는 현재 프로젝트의 routing/state navigation 구조를 사용한다.

브라우저 뒤로가기도 정상적으로 작동하도록 한다.


━━━━━━━━━━━━━━━━━━━━
2. 우측 상단 알림 버튼
━━━━━━━━━━━━━━━━━━━━

Header 우측의 Bell 아이콘을 실제로 작동하게 한다.

Bell 클릭 시 Header 아래에
Notification Popover를 표시한다.

Popover 제목:

최근 알림

최신순으로 약 5개의 알림을 표시한다.

예:

[검토 필요]
김민준 아동 STT 검수가 완료되었습니다.
3분 전

[고위험]
박서준 사례에서 우선 검토가 필요한 신호가 확인되었습니다.
18분 전

[업무]
이하은 아동 상담기록 검토가 배정되었습니다.
1시간 전

[분석 완료]
김민준 아동의 AI 분석 결과가 생성되었습니다.
2시간 전

각 알림에는:

- 유형
- 제목
- 관련 아동/사례
- 발생 시각
- 읽음/안읽음
- 관련 페이지 link

를 포함한다.

알림 클릭 시 해당 업무 화면으로 즉시 이동한다.

예:

STT 알림
→ 해당 아동의 해당 상담회차 STT Review

분석 완료
→ 해당 분석 결과

고위험 알림
→ 해당 Case Detail 또는 AI Review

업무 배정
→ 해당 업무 화면

읽지 않은 알림에는 subtle indicator를 표시한다.

Bell에는 unread count badge를 표시한다.

알림을 클릭하면 읽음 상태로 변경한다.

"모두 읽음 처리" 기능도 제공한다.

Popover 바깥을 클릭하거나 ESC를 누르면 닫힌다.


━━━━━━━━━━━━━━━━━━━━
3. Dashboard - 나의 업무 목록
━━━━━━━━━━━━━━━━━━━━

Dashboard의 "나의 업무 목록"을 실제 업무 queue처럼 동작하게 한다.

각 업무 항목에는 업무 종류에 따라:

- 처리
- 검수
- 확인
- 작성
- 승인

등의 Action Button이 존재한다.

Action Button을 클릭하면
해당 업무를 처리할 수 있는 정확한 화면으로 이동한다.

예:

STT 검수
→ Transcript Review

분석 결과 검토
→ AI Review

상담기록 검토
→ Summary Editor

사례관리계획 작성
→ Case Plan

종결 검토
→ Closure Review

버튼을 클릭했는데 관련 페이지가 존재하지 않는다면
현재 Design System에 맞는 페이지를 새로 생성한다.

이동 시 반드시 해당 업무와 연결된

caseId
childId
sessionId
taskId

등 필요한 context를 전달한다.


━━━━━━━━━━━━━━━━━━━━
4. Dashboard - 고위험 우선 검토
━━━━━━━━━━━━━━━━━━━━

"고위험 우선 검토" 목록에서
아동 이름을 클릭 가능하게 변경한다.

아동 이름은 단순 텍스트가 아니라
accessible text link 형태로 표현한다.

클릭:

아동 이름
→ 해당 아동의 Case Detail

Case Detail에는 최소한:

- Case ID
- 아동 기본정보
- 보호자 정보
- 사례 상태
- 현재 위험 수준
- 최근 상담
- 상담 회차
- 최근 STT
- 최근 AI 분석
- 상담기록
- 사례관리계획

을 확인할 수 있도록 한다.


━━━━━━━━━━━━━━━━━━━━
5. 통합 사례 목록
━━━━━━━━━━━━━━━━━━━━

통합 사례 목록에서 사례를 클릭하면
현재 존재하는 간략 정보 화면을 유지한다.

간략 화면에는 최소:

- 기본 사례 정보
- 최근 상담
- 위험 수준
- 담당 상담사
- 상태

를 표시한다.

그리고 다음 두 개의 명확한 Action을 제공한다.

[상세 정보]
[새 상담 시작]


━━━━━━━━━━━━━━━━━━━━
6. 상세 정보 버튼
━━━━━━━━━━━━━━━━━━━━

통합 사례 목록 → 사례 선택 → 간략 정보 →

"상세 정보"

클릭 시 별도의 Case Detail Page로 이동한다.

Modal을 크게 확장하는 방식이 아니라
독립적인 페이지로 만든다.

Case Detail Page에는:

Header
- 아동 이름
- Case ID
- 상태
- 담당 상담사
- 위험 수준

Overview
- 아동 기본정보
- 보호자
- 접수 정보
- 주요 위험요인

Counseling Timeline
- 상담일
- 상담 회차
- 상담사
- STT 상태
- AI 분석 상태
- 기록 상태

Risk / Evidence
- 관련 신호
- 최근 분석
- 근거 발화

Documents
- 상담일지
- 사정기록지
- 사례관리계획
- 보고서

를 구성한다.

각 상담 회차도 클릭 가능하게 한다.


━━━━━━━━━━━━━━━━━━━━
7. 새 상담 시작
━━━━━━━━━━━━━━━━━━━━

통합 사례 목록 → 사례 선택 →

"새 상담 시작"

클릭 시 별도의 상담 시작 화면으로 이동한다.

바로 녹음을 시작하지 않는다.

먼저 Pre-session 화면을 제공한다.

표시 정보:

상담 대상 아동
Case ID
현재 날짜
상담사
예정 상담 회차

입력:

상담 유형
상담 방식
상담 장소
간단한 상담 목적/메모

Action:

[취소]
[상담 시작]

"상담 시작" 클릭:

→ RecordingView

RecordingView에는 선택된 caseId와 child 정보가 전달되어야 한다.


━━━━━━━━━━━━━━━━━━━━
8. STT 검수 메뉴 구조 변경
━━━━━━━━━━━━━━━━━━━━

현재 STT 검수 메뉴를 클릭했을 때
곧바로 특정 STT 상세 편집 화면으로 이동하지 않는다.

3단계 구조로 변경한다.

STEP 1
사례 선택

STEP 2
해당 사례/아동의 녹음 목록

STEP 3
STT 상세 검수


━━━━━━━━━━━━━━━━━━━━
9. STT - 사례 선택
━━━━━━━━━━━━━━━━━━━━

STT 검수 메뉴 클릭:

→ Case Selector

사례 목록에서 다음 정보를 제공한다.

- 아동명
- Case ID
- 최근 상담일
- STT 검수 대기 건수
- 상태

검색 가능:

- 아동명
- Case ID

사례를 선택하면:

→ 해당 아동의 Recording / Session List


━━━━━━━━━━━━━━━━━━━━
10. STT - 녹음 목록
━━━━━━━━━━━━━━━━━━━━

선택한 아동의 상담 녹음 목록을 표시한다.

정렬:

최신 상담이 가장 위에 오도록 descending order.

각 row:

- 상담 날짜
- 상담 시간
- 회차
- 상담사
- 녹음 길이
- STT 처리 상태
- STT 검수 상태
- AI 분석 상태

상태 예:

처리 중
검수 필요
검수 완료
분석 완료

목록 중 하나를 클릭:

→ 해당 session의 TranscriptReviewView


━━━━━━━━━━━━━━━━━━━━
11. STT 상세 검수
━━━━━━━━━━━━━━━━━━━━

TranscriptReviewView에서는 기존 요구사항을 유지한다.

표시:

speaker
timestamp
text
confidence
low-confidence indication

상담사는 문장을 수정할 수 있다.

Action:

[임시 저장]
[검수 완료]

검수 완료 클릭 시 confirmation을 제공한다.

예:

"STT 검수를 완료하시겠습니까?
완료 후 AI 분석 결과 검토 단계로 이동합니다."

[취소]
[검수 완료]


━━━━━━━━━━━━━━━━━━━━
12. STT 완료 → AI 분석 연결
━━━━━━━━━━━━━━━━━━━━

STT 검수 완료 이후
사용자가 다음 업무를 찾기 위해 메뉴를 다시 이동하게 하지 않는다.

완료 성공 상태를 짧게 표시한 뒤:

"STT 검수가 완료되었습니다."

Primary CTA:

[분석 결과 검토하기]

를 제공한다.

AI 분석이 이미 완료되었다면:

→ 해당 session의 AI Review Detail

분석 중이라면:

→ Processing 화면

Processing 화면:

AI 분석을 진행하고 있습니다.
STT 검수는 완료되었습니다.

진행 상태를 표시한다.

분석 완료 시 자동으로 결과 검토 가능 상태로 변경한다.


━━━━━━━━━━━━━━━━━━━━
13. 분석 결과 검토 메뉴 구조 변경
━━━━━━━━━━━━━━━━━━━━

현재 분석 결과 검토 메뉴를 클릭했을 때
특정 분석 상세 화면을 바로 표시하지 않는다.

다음 구조로 변경한다.

STEP 1
사례/아동 선택

STEP 2
해당 아동의 분석 결과 목록

STEP 3
분석 결과 상세 검토


━━━━━━━━━━━━━━━━━━━━
14. 분석 결과 목록
━━━━━━━━━━━━━━━━━━━━

아동을 선택하면
해당 아동의 AI 분석 결과 목록을 최신순으로 표시한다.

각 row:

- 분석 날짜
- 상담 회차
- 상담일
- 분석 상태
- 관련 신호 수
- 검토 상태
- 검토자
- 최종 수정일

최신 결과를 가장 위에 표시한다.

상태:

분석 중
검토 필요
검토 중
수정됨
승인 완료

목록 클릭:

→ AIReviewView Detail


━━━━━━━━━━━━━━━━━━━━
15. 분석 결과 상세 검토
━━━━━━━━━━━━━━━━━━━━

기존 AIReviewView의 2-pane 구조를 유지한다.

LEFT:
STT 원문

RIGHT:
AI 분석 결과

AI 결과에는:

- 관련 신호
- 위험요인
- 추가 확인 필요사항
- 근거 발화
- 상담 요약

등을 제공한다.

AI가 판단을 확정하는 표현은 사용하지 않는다.

모든 분석 결과에는 Evidence Source를 연결한다.

근거 출처 클릭:

→ 해당 STT session
→ 해당 timestamp
→ 해당 발화

로 바로 이동할 수 있도록 한다.


━━━━━━━━━━━━━━━━━━━━
16. 사례관리계획 - 판단 근거 연결
━━━━━━━━━━━━━━━━━━━━

CasePlanView에서
계획 수립의 근거가 된 AI 분석 정보를 확인할 수 있도록 한다.

"판단 근거" 또는 "관련 분석 근거" section을 추가한다.

각 근거:

- 관련 분석 결과
- 분석 날짜
- 상담 회차
- 관련 신호
- 근거 발화 일부
- 출처

를 표시한다.

[근거 출처 보기]

클릭 시:

→ 해당 AI Review Detail
→ 해당 Evidence

로 즉시 이동한다.

필요하면 해당 evidence를 highlight한다.

Case Plan에서 AI 결과가
최종 판단처럼 보이지 않게 한다.

"상담사 판단을 위한 참고 근거"로 표현한다.


━━━━━━━━━━━━━━━━━━━━
17. 보고서 생성 Workflow
━━━━━━━━━━━━━━━━━━━━

ReportView를 실제 보고서 생성 Workflow로 수정한다.

보고서 종류 선택에 따라
내용과 section 구성이 달라져야 한다.

예:

A. 내부 사례회의 보고서

포함:
- 사례 개요
- 상담 경과
- 주요 위험 신호
- 상담사 판단
- 최근 변화
- 논의 필요사항


B. 외부기관 전달 보고서

포함:
- 기본 사례 정보
- 전달 목적
- 상담 경과 요약
- 확인된 사실
- 보호조치 현황
- 협조 요청사항

민감한 내부 AI score 등은
외부 전달용 보고서에서 자동 제외하거나 최소화한다.


C. 종결 검토 보고서

포함:
- 사례 개요
- 개입 경과
- 상담 회차
- 위험요인 변화
- 보호요인
- 종결 검토 근거
- 사후관리 계획


D. 가정복귀 검토 보고서

포함:
- 사례 경과
- 아동 상태
- 보호자 변화
- 위험요인
- 보호요인
- 가정환경
- 상담사 의견
- 추가 확인사항


보고서 종류를 변경하면
오른쪽 Preview가 실제로 변경되어야 한다.

단순히 제목만 변경하지 않는다.

각 보고서에 적합한 section과 내용이 달라져야 한다.


━━━━━━━━━━━━━━━━━━━━
18. 보고서 편집
━━━━━━━━━━━━━━━━━━━━

보고서 생성 결과는
읽기 전용 이미지가 아니라 editable document 형태로 제공한다.

상담사가 생성된 문구를 수정할 수 있도록 한다.

Action:

[임시 저장]
[PDF 다운로드]
[HWP 다운로드]


━━━━━━━━━━━━━━━━━━━━
19. PDF 다운로드
━━━━━━━━━━━━━━━━━━━━

PDF 다운로드 버튼을 실제 작동하게 한다.

버튼 클릭 시
현재 선택된 보고서 내용으로 PDF 파일을 생성하여 다운로드한다.

파일명 예:

I-SPOT_내부사례회의_김민준_2026-09-03.pdf

다운로드 상태:

생성 중
→ 다운로드 완료

오류 시:

PDF 생성에 실패했습니다.
[다시 시도]

단순 alert() 사용 금지.


━━━━━━━━━━━━━━━━━━━━
20. HWP 다운로드
━━━━━━━━━━━━━━━━━━━━

HWP 다운로드 버튼도 실제 download action을 구현한다.

현재 프론트엔드 환경에서
진짜 HWP binary 생성 라이브러리 또는 backend API가 연결되어 있다면
해당 방식으로 구현한다.

현재 환경에서 실제 HWP 생성이 기술적으로 불가능하다면
가짜 .hwp 파일을 만들지 않는다.

대신 download service abstraction을 구현하고
Mock 단계에서는 명확하게:

"HWP 파일 생성 API 연결 필요"

상태를 개발 구조에 남긴다.

실서비스 API 연결 시
동일 버튼에서 HWP가 다운로드되도록 설계한다.

사용자 UI에서는 disabled/loading/error 상태를 적절하게 제공한다.


━━━━━━━━━━━━━━━━━━━━
21. 상담사 계정
━━━━━━━━━━━━━━━━━━━━

Header 우측의 상담사 이름을 클릭 가능하게 한다.

클릭:

→ Account / Profile Page

새로운 Account Page를 만든다.

표시:

- 상담사 이름
- 소속 기관
- 역할
- 기관 ID
- 이메일
- 연락처
- 계정 상태
- 마지막 로그인
- 최근 접속 위치
- 비밀번호 변경
- 보안 설정

Action:

[계정 정보 수정]
[비밀번호 변경]
[로그아웃]

관리자라면 Role을 "관리자"로 표시한다.


━━━━━━━━━━━━━━━━━━━━
22. Sidebar Navigation
━━━━━━━━━━━━━━━━━━━━

Sidebar의 모든 메뉴를 실제 페이지와 연결한다.

예:

대시보드
→ Dashboard

통합 사례
→ Case List

상담/녹음
→ Case Select 또는 Recording workflow

STT 검수
→ STT Case Selector

분석 결과 검토
→ AI Analysis Case Selector

사례관리계획
→ Case Plan Selector

종결·가정복귀 검토
→ Closure Selector

보고서
→ Report Workflow

현재 페이지는 active state로 표시한다.


━━━━━━━━━━━━━━━━━━━━
23. Breadcrumb
━━━━━━━━━━━━━━━━━━━━

깊이가 2단계 이상인 화면에는 Breadcrumb를 추가한다.

예:

통합 사례
> 김민준
> 상세 정보

STT 검수
> 김민준
> 2026-09-03 상담
> 검수

분석 결과 검토
> 김민준
> 2026-09-03 분석 결과

사례관리계획
> 김민준
> 계획 작성

Breadcrumb 클릭 시 이전 단계로 이동한다.


━━━━━━━━━━━━━━━━━━━━
24. 데이터 관계
━━━━━━━━━━━━━━━━━━━━

현재 cases.ts 및 기존 mock data를 활용한다.

모든 데이터를 독립적인 dummy object로 만들지 말고
관계를 유지한다.

권장 관계:

Case
 ├─ Child
 ├─ Counselor
 ├─ Sessions[]
 │    ├─ Recording
 │    ├─ Transcript
 │    ├─ AIAnalysis
 │    └─ CounselingRecord
 ├─ CasePlan
 ├─ ClosureReview
 └─ Reports[]

동일한 아동을 선택했는데
페이지마다 다른 Case ID나 상담 기록이 나오는 일이 없도록 한다.

하나의 mock data source를 공유한다.


━━━━━━━━━━━━━━━━━━━━
25. 페이지 간 Context 유지
━━━━━━━━━━━━━━━━━━━━

예:

김민준 선택
→ STT 목록
→ 3회차 선택
→ STT 검수
→ AI 분석 검토
→ Evidence 확인
→ 사례관리계획

으로 이동하는 동안

childId
caseId
sessionId

context를 유지한다.

사용자가 이전 페이지로 돌아와도
가능한 경우 기존 선택 상태를 유지한다.


━━━━━━━━━━━━━━━━━━━━
26. 모든 목록 공통 Interaction
━━━━━━━━━━━━━━━━━━━━

목록 화면에는 필요에 따라 다음을 구현한다.

- 검색
- 필터
- 정렬
- pagination 또는 적절한 list handling
- empty state
- loading
- error
- selected state

검색 결과가 없으면:

"검색 조건에 맞는 사례가 없습니다."

와 같이 명확한 Empty State를 제공한다.


━━━━━━━━━━━━━━━━━━━━
27. Confirmation
━━━━━━━━━━━━━━━━━━━━

중요 상태 변경에는 Confirmation을 제공한다.

예:

STT 검수 완료
AI 결과 승인
사례관리계획 승인
종결 검토 승인

단순 browser confirm() 대신
현재 Design System의 Confirmation Modal을 사용한다.


━━━━━━━━━━━━━━━━━━━━
28. Toast Feedback
━━━━━━━━━━━━━━━━━━━━

작업 완료 시
작은 Toast notification을 사용한다.

예:

STT 검수가 저장되었습니다.

분석 결과 검토가 완료되었습니다.

사례관리계획이 저장되었습니다.

보고서가 생성되었습니다.

Toast는 화면을 방해하지 않고
3~5초 후 자동으로 사라지도록 한다.


━━━━━━━━━━━━━━━━━━━━
29. Loading / Processing
━━━━━━━━━━━━━━━━━━━━

실제 비동기 처리가 예상되는 기능에는
Loading state를 반드시 제공한다.

예:

STT 생성
AI 분석
보고서 생성
PDF 생성
데이터 로딩

버튼 클릭 후 아무 반응 없는 상태를 만들지 않는다.

Button 자체에도 loading state를 제공한다.


━━━━━━━━━━━━━━━━━━━━
30. Error Handling
━━━━━━━━━━━━━━━━━━━━

모든 주요 기능에 오류 상태를 구현한다.

예:

데이터 조회 실패
녹음 업로드 실패
STT 생성 실패
AI 분석 실패
보고서 생성 실패
다운로드 실패

오류 메시지에는
가능한 경우 recovery action을 제공한다.

[다시 시도]

등.


━━━━━━━━━━━━━━━━━━━━
31. 권한
━━━━━━━━━━━━━━━━━━━━

상담사와 관리자 Role에 따라
사용 가능한 기능을 구분한다.

상담사가 접근할 수 없는 관리자 기능은
단순히 깨진 페이지로 이동하지 않는다.

Permission Denied 또는
메뉴 비노출 정책을 일관되게 사용한다.


━━━━━━━━━━━━━━━━━━━━
32. 새로 필요한 페이지
━━━━━━━━━━━━━━━━━━━━

현재 프로젝트에 없는 경우
다음 화면을 새로 만든다.

- Case Detail Page
- Pre-session / New Counseling Page
- STT Session List
- AI Analysis Result List
- Account / Profile Page
- Notification Popover
- 필요한 Selector Page
- Download / Processing states
- Permission Denied
- Not Found

새 화면도 반드시 기존 I-SPOT Design System을 사용한다.

새로운 디자인 언어를 만들지 않는다.


━━━━━━━━━━━━━━━━━━━━
33. URL / Route 구조
━━━━━━━━━━━━━━━━━━━━

가능하면 실제 서비스에 가까운 route 구조를 사용한다.

예:

/dashboard

/cases
/cases/:caseId

/cases/:caseId/counseling/new

/cases/:caseId/sessions

/cases/:caseId/sessions/:sessionId/recording

/cases/:caseId/sessions/:sessionId/transcript

/cases/:caseId/analyses

/cases/:caseId/analyses/:analysisId

/cases/:caseId/plan

/cases/:caseId/closure

/cases/:caseId/reports

/profile

route naming은 현재 프로젝트 구조에 맞게 조정 가능하다.


━━━━━━━━━━━━━━━━━━━━
34. 버튼 전수 검사
━━━━━━━━━━━━━━━━━━━━

작업 마지막 단계에서
전체 애플리케이션의 모든 버튼을 검사한다.

다음 상태를 허용하지 않는다.

- 클릭해도 아무 반응 없음
- 링크인데 cursor가 일반 pointer가 아님
- 존재하지 않는 페이지로 이동
- 동일 버튼이 화면마다 다른 동작
- 저장 버튼인데 데이터 상태가 변경되지 않음
- 다운로드 버튼인데 다운로드가 발생하지 않음
- 뒤로가기 불가능
- Modal을 열었는데 닫을 수 없음

각 버튼에 실제 목적과 동작이 존재해야 한다.


━━━━━━━━━━━━━━━━━━━━
35. End-to-End Workflow QA
━━━━━━━━━━━━━━━━━━━━

다음 시나리오가 처음부터 끝까지 실제로 동작하는지 확인한다.

FLOW A

로그인
→ Dashboard
→ 고위험 우선 검토
→ 아동 이름 클릭
→ Case Detail


FLOW B

Dashboard
→ 나의 업무
→ STT 검수 처리
→ 해당 아동 STT 목록
→ 최신 상담 선택
→ STT 검수
→ 검수 완료
→ AI 분석 결과 검토
→ 승인


FLOW C

통합 사례
→ 사례 선택
→ 간략 정보
→ 상세 정보
→ Case Detail


FLOW D

통합 사례
→ 사례 선택
→ 새 상담 시작
→ Pre-session
→ 상담 시작
→ Recording


FLOW E

분석 결과 검토
→ 아동 선택
→ 분석 결과 목록
→ 분석 결과 상세
→ 근거 발화 클릭
→ STT 원문 해당 위치


FLOW F

사례관리계획
→ 아동 선택
→ 판단 근거 확인
→ 근거 출처 클릭
→ 해당 AI 분석 / STT evidence


FLOW G

보고서
→ 사례 선택
→ 보고서 종류 선택
→ 보고서 생성
→ 내용 확인/수정
→ PDF 다운로드


FLOW H

Header
→ Bell 클릭
→ 최근 알림
→ 알림 클릭
→ 관련 업무


FLOW I

Header
→ 상담사 이름 클릭
→ Account Page
→ 계정 정보 확인


모든 Flow가 끊김 없이 동작해야 한다.


━━━━━━━━━━━━━━━━━━━━
36. UI 디자인 유지 원칙
━━━━━━━━━━━━━━━━━━━━

기능을 추가한다는 이유로
기존에 정립한 UI 디자인 방향을 훼손하지 않는다.

계속 유지:

- Navy 기반 I-SPOT identity
- restrained enterprise UI
- 작은 radius
- subtle border
- minimal shadow
- Pretendard typography
- information-dense layout
- professional case-management interface

추가 기능에도:

glassmorphism
neon
gradient
large rounded card
emoji
oversized icon
decorative animation

등을 사용하지 않는다.


━━━━━━━━━━━━━━━━━━━━
37. 구현 품질
━━━━━━━━━━━━━━━━━━━━

프로토타입처럼 보이지만 실제로는 작동하지 않는 화면을 만들지 않는다.

React/TypeScript 코드 기준으로
실제 실행 가능한 interaction을 구현한다.

중복 코드를 최소화한다.

공통 컴포넌트화:

Button
Modal
Toast
Popover
Breadcrumb
StatusBadge
CaseSelector
SessionList
LoadingState
EmptyState
ErrorState

등을 고려한다.

TypeScript type을 명확하게 정의한다.

Mock Data 단계에서도
나중에 실제 API로 교체할 수 있도록
UI와 data access를 가능한 한 분리한다.


━━━━━━━━━━━━━━━━━━━━
38. 최종 목표
━━━━━━━━━━━━━━━━━━━━

최종 결과는
"클릭 가능한 것처럼 보이는 Figma 시안"이 아니라

실제로 사용자가:

로그인하고
→ 업무를 확인하고
→ 사례를 선택하고
→ 상담하고
→ STT를 검수하고
→ AI 결과와 근거를 검토하고
→ 사례관리계획을 작성하고
→ 보고서를 생성하고
→ PDF를 다운로드할 수 있는

end-to-end I-SPOT 웹 애플리케이션이어야 한다.

기존 화면이 있으면 수정하고 재사용한다.
기존 화면이 없으면 동일 Design System으로 새로 제작한다.

모든 주요 CTA와 Navigation은 실제로 작동해야 한다.

작업 완료 후 전체 버튼과 사용자 Workflow를 다시 점검하여
dead button, dead link, dead-end page가 하나도 남지 않도록 수정한다.