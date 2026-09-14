I-SPOT 웹서비스의 기존 UI를 전면 재설계하지 말고,
현재 정보구조와 사용자 흐름을 유지하면서
전문 UX/UI 디자이너가 실제 기관용 업무 시스템으로 정제한 수준으로 리디자인한다.

첨부된 다음 자료를 반드시 기준으로 삼는다.

1. 04_FRONTEND_PROMPT.md
2. I-SPOT 요구사항 정의서
3. 기존 UI스크린샷 PDF

기존 화면의 기능, 메뉴 구조, 데이터 구조, 주요 사용자 흐름은 임의로 삭제하거나 변경하지 않는다.

이번 작업의 핵심 목표는
기능을 새롭게 추가하는 것이 아니라
현재 UI에서 느껴지는 AI-generated SaaS template 느낌을 제거하고,
실제 아동보호전문기관에서 상담사가 장시간 사용할 수 있는
신뢰성 높은 enterprise case-management system 수준으로 시각적 완성도를 높이는 것이다.


━━━━━━━━━━━━━━━━━━━━
1. 제품 정체성
━━━━━━━━━━━━━━━━━━━━

서비스명: I-SPOT

I-SPOT은
아동 상담 과정에서 생성되는 음성 및 텍스트 데이터를 활용하여
상담 기록 작성과 아동학대 관련 위험 신호 확인을 지원하는
전문 상담 업무 지원 시스템이다.

주요 사용자는:

- 상담사
- 관리자

이다.

본 시스템은 AI가 상담사의 판단을 대신하거나
학대 여부를 자동으로 확정하는 시스템이 아니다.

AI는 상담사에게 참고 가능한 정보,
관련 신호,
근거 발화,
추가 확인 필요 사항을 제공하며
모든 중요 결과는 상담사의 검토 및 최종 승인 단계를 거친다.

따라서 전체 UI는 다음 인상을 전달해야 한다.

- 전문성
- 신뢰성
- 안정성
- 보안성
- 정확성
- 절제된 현대성
- 높은 정보 가독성

일반 소비자 앱,
AI 스타트업 landing page,
Dribbble용 concept UI처럼 보이지 않게 한다.


━━━━━━━━━━━━━━━━━━━━
2. 이번 디자인의 절대 원칙
━━━━━━━━━━━━━━━━━━━━

현재 UI의 기능과 정보구조는 유지한다.

다만 다음과 같은
AI-generated UI 특유의 패턴은 제거하거나 크게 줄인다.

금지 또는 최소화:

- 모든 정보를 카드 안에 넣는 card-heavy UI
- 모든 카드에 동일한 radius 적용
- 지나치게 큰 border-radius
- nested card 구조
- 과도한 drop shadow
- glassmorphism
- glow
- blue/purple gradient
- decorative gradient
- neon accent
- 과도하게 큰 hero text
- 의미 없는 빈 공간
- pill button 남용
- pill badge 남용
- emoji 아이콘
- 불필요한 decorative icon
- 모든 요소를 중앙 정렬
- 모든 summary 정보를 동일한 KPI card로 표현
- 같은 디자인 패턴이 화면마다 반복되는 AI dashboard
- AI Powered SaaS landing page 같은 시각 언어

세련됨은 decoration이 아니라 다음 요소에서 만들어라.

- Grid
- Alignment
- Typography
- Spacing
- Information hierarchy
- Component consistency
- Data density
- Micro interaction


━━━━━━━━━━━━━━━━━━━━
3. 전체 Layout System
━━━━━━━━━━━━━━━━━━━━

현재 UI스크린샷에 사용된

Dark Navy Sidebar
+
Light Main Workspace

구조는 유지한다.

Desktop 기준:

Sidebar:
약 220~240px

Main Content:
나머지 영역 사용

Content max width는 화면 성격에 따라 유연하게 사용하며,
무조건 중앙에 좁은 container를 만들지 않는다.

업무 시스템이므로
가용 화면 폭을 효율적으로 활용한다.

특히 Table,
Transcript,
AI Review,
Case Detail
화면에서는 충분한 horizontal space를 사용한다.

전체 grid는 4px 또는 8px 기반 spacing system을 사용한다.


━━━━━━━━━━━━━━━━━━━━
4. Sidebar
━━━━━━━━━━━━━━━━━━━━

현재의 Navy Sidebar 구조는 유지한다.

하지만 현재보다 더 절제되고 정돈된 형태로 변경한다.

Sidebar 특징:

- flat design
- 거의 shadow 없음
- 메뉴 간 vertical spacing 일정
- icon size 통일
- icon style은 simple outline
- 메뉴 text hierarchy 명확화
- selected menu는 과도한 밝은 blue box 대신
  subtle background와 left indicator 또는 restrained highlight 사용

메뉴 selection에
강한 cyan/royal blue rounded rectangle을 반복적으로 사용하지 않는다.

예:

default:
transparent background

hover:
rgba white 4~6%

selected:
slightly lighter navy
+
2~3px primary indicator
+
white text

메뉴 group title은
작고 muted한 secondary text 사용.

알림 badge는 실제 주의가 필요한 메뉴에만 표시한다.


━━━━━━━━━━━━━━━━━━━━
5. Header
━━━━━━━━━━━━━━━━━━━━

기존 화면 상단의

검색
알림
사용자 정보

구조를 유지한다.

Header는
높이 약 56~64px의 compact enterprise toolbar 형태로 구성한다.

불필요한 decoration 금지.

Search bar는
화면 전체의 시각적 중심이 되지 않도록
약 280~360px 범위의 restrained input 형태로 사용한다.

사용자 프로필은
작은 avatar + 이름 정도로 단순화한다.


━━━━━━━━━━━━━━━━━━━━
6. Typography
━━━━━━━━━━━━━━━━━━━━

한국어 중심 UI이므로
Pretendard를 기본 폰트로 사용한다.

fallback:

Inter
system-ui
sans-serif

권장 hierarchy:

Page Title:
24~28px
600~700

Section Title:
17~20px
600

Card / Panel Title:
14~16px
600

Body:
14px

Secondary:
13px

Caption:
12px

지나치게 큰 Heading 사용 금지.

Typography 크기보다
weight,
color,
spacing으로 hierarchy를 만든다.

한글 line-height를 충분히 확보한다.


━━━━━━━━━━━━━━━━━━━━
7. Color System
━━━━━━━━━━━━━━━━━━━━

현재 I-SPOT의 Navy identity는 유지한다.

추천 palette:

Primary Navy:
#15314A

Deep Navy:
#0F263B

Primary Blue:
#2563EB

Main Background:
#F6F8FB

Surface:
#FFFFFF

Secondary Surface:
#F8FAFC

Border:
#E2E8F0

Primary Text:
#172033

Secondary Text:
#64748B

Muted:
#94A3B8

Success:
restrained green

Warning:
restrained amber

Danger:
restrained red

Status color는 의미 전달에만 사용한다.

학대 관련 위험 정보라고 해서
화면 전체를 red/orange 계열로 만들지 않는다.

색상만으로 상태를 전달하지 않는다.


━━━━━━━━━━━━━━━━━━━━
8. Border / Radius / Shadow
━━━━━━━━━━━━━━━━━━━━

Radius:

Input: 6px
Button: 6px
Panel: 8px
Card: 8px
Modal: 8~10px

16px 이상의 radius는 사용하지 않는다.

Shadow:

기본 content panel:
shadow 없음

floating dropdown / modal:
very subtle shadow

기본 section 구분은
shadow 대신

- spacing
- border
- background contrast

로 표현한다.


━━━━━━━━━━━━━━━━━━━━
9. Dashboard
━━━━━━━━━━━━━━━━━━━━

기존 상담사 Dashboard의 기능은 유지한다.

표시 요소:

- 전체 담당 사례
- 오늘 예정 상담
- 고위험 우선 검토 사례
- 미처리 Task
- 나의 업무 목록
- 고위험 사례

다만 현재처럼
모든 summary 값을
같은 크기의 rounded card 4개로 배열하는 방식은 완화한다.

Summary 영역은
compact stat strip 또는
2~4개의 restrained metric panel 형태로 구성한다.

카드마다 큰 icon을 배치하지 않는다.

metric 정보는:

label
number
secondary description

중심으로 구성한다.

"나의 업무 목록"은
card collection이 아니라
compact task list 형태가 적합하다.

"우선 검토 사례"는
Table 또는 compact list를 사용한다.

Dashboard는
예쁜 SaaS dashboard가 아니라
업무 우선순위를 빠르게 파악할 수 있는
operation overview 역할을 해야 한다.


━━━━━━━━━━━━━━━━━━━━
10. Case List
━━━━━━━━━━━━━━━━━━━━

사례 목록 화면은
본 서비스에서 가장 자주 사용하는 핵심 화면 중 하나이다.

검색 조건:

- 아동명
- 보호자명
- Case ID
- 학대유형
- Risk Factor / 상담 키워드
- 상태
- 위험도

를 지원한다.

상단 search/filter 영역을
하나의 정돈된 filter toolbar로 구성한다.

필터마다 card를 만들지 않는다.

Main table은
enterprise data table 스타일을 사용한다.

Table 특징:

- 충분한 row height
- 명확한 column alignment
- subtle row separator
- hover state
- sticky header 가능
- selected row state
- compact status label

아동 개인정보는 필요한 경우
마스킹되어 보이는 형태를 고려한다.

위험도는
색상만이 아니라
텍스트 label과 함께 제공한다.


━━━━━━━━━━━━━━━━━━━━
11. Case Detail
━━━━━━━━━━━━━━━━━━━━

Case Detail은
하나의 큰 dashboard처럼 만들지 않는다.

정보 hierarchy는 다음처럼 구성한다.

Case Header
↓
기본 정보 / 현재 상태
↓
상담 회차 Timeline
↓
회차별 STT / AI / 기록
↓
관련 위험 신호 변화

Case ID는 모든 관련 데이터가 연결되는
중요한 식별자로 일관되게 표시한다.

상담 회차는
timeline 또는 structured list로 표현한다.

카드 안에 카드가 반복되는 구조는 피한다.


━━━━━━━━━━━━━━━━━━━━
12. Recording
━━━━━━━━━━━━━━━━━━━━

Recording 화면은 매우 중요하다.

상담 중 아동과 상담사의 라포 형성을 방해하지 않도록
UI를 최소화한다.

반드시 포함:

- 녹음 시작
- 일시정지
- 재개
- 종료
- 경과시간
- 마이크 상태
- 오류
- 업로드 상태

이번 MVP Recording 화면에는
다음을 넣지 않는다.

- 실시간 학대 판정
- 실시간 위험도 그래프
- Risk Factor dashboard
- 복잡한 상담 기록
- 종결 추천

Recording 화면은
UI 요소가 가장 적은 화면이어야 한다.

큰 timer,
clear recording state,
primary recording action

을 중심으로 구성한다.

화려한 waveform은 필수 아님.

필요하면 minimal audio level 정도만 사용한다.


━━━━━━━━━━━━━━━━━━━━
13. STT Review
━━━━━━━━━━━━━━━━━━━━

STT 검수 화면은
문서 편집 도구에 가까운 UI로 구성한다.

각 segment에 표시:

- speaker
- timestamp
- segment text
- confidence
- low-confidence indication

지원 action:

- 수정
- 확정

저신뢰 구간은
화면 전체를 노란색으로 만들지 않는다.

해당 sentence 또는 segment만
subtle warning background를 적용한다.

화자 label은
일관된 작은 label로 표시한다.

상담사와 아동 발화를
명확히 구분하되
과도한 색상을 사용하지 않는다.


━━━━━━━━━━━━━━━━━━━━
14. AI Review / Summary Editor
━━━━━━━━━━━━━━━━━━━━

AI Review 화면은
2-pane 구조를 기본으로 한다.

LEFT:
STT 원문

RIGHT:
AI 상담 요약 및 참고정보

상담사는 AI 생성 내용을 직접 수정할 수 있어야 한다.

권장 표현:

- AI 분석 참고정보
- 관련 신호
- 추가 확인 필요
- 근거 발화
- 상담사 검토 필요

절대 사용하지 말아야 할 표현:

- 학대 확정
- 위험 확정
- AI 판정
- 자동 결정

AI 관련 결과에는
근거 발화를 쉽게 확인할 수 있어야 한다.

Evidence를 선택하면
관련 STT 발화 위치로 이동하거나
highlight될 수 있는 interaction을 고려한다.

AI 결과가
상담사의 판단보다 시각적으로 더 강하게 보이지 않게 한다.


━━━━━━━━━━━━━━━━━━━━
15. Human-in-the-loop 표현
━━━━━━━━━━━━━━━━━━━━

본 서비스의 핵심은
상담사가 최종 판단자라는 점이다.

따라서 AI 결과에는
상태를 명확하게 표현한다.

예:

AI 생성됨
검토 필요
수정됨
승인 대기
승인 완료

최종 승인 전에는
AI 결과가 확정된 정보처럼 보이지 않도록 한다.

Primary CTA는 상황에 따라

"검토 완료"
"승인"

등으로 사용한다.


━━━━━━━━━━━━━━━━━━━━
16. 상담 기록 자동작성
━━━━━━━━━━━━━━━━━━━━

상담 종료 후 제공되는

- 상담 요약
- 상담일지 초안
- 사정기록지 초안

은 editor 스타일로 표현한다.

STT와 AI 생성 문서를
동시에 비교할 수 있는 2-pane 구조를 고려한다.

AI 생성 문서는
읽기 전용 card가 아니라
상담사가 수정 가능한 문서 editor 형태로 디자인한다.

변경 내용과 승인 상태를
명확하게 표시한다.


━━━━━━━━━━━━━━━━━━━━
17. Risk Signal / Risk Factor
━━━━━━━━━━━━━━━━━━━━

위험 정보는 민감한 정보이므로
화려한 visualization보다
정확한 정보전달을 우선한다.

사용 가능한 표현:

관련 신호
Risk Factor
근거 발화
회차별 변화
과거 중대사건 패턴 비교

위험도를
큰 gauge,
radial chart,
red gradient
등으로 과도하게 표현하지 않는다.

필요한 경우:

- compact trend chart
- structured comparison
- simple status indicator

를 사용한다.


━━━━━━━━━━━━━━━━━━━━
18. Status System
━━━━━━━━━━━━━━━━━━━━

전체 서비스에서 다음 상태를
공통 컴포넌트로 설계한다.

Loading
Empty
Processing
Review Required
Success
Error
Permission Denied

각 상태마다
거대한 illustration이나 emoji를 사용하지 않는다.

Loading:
skeleton / small spinner

Empty:
simple icon + short guidance

Processing:
progress indicator + 상태 설명

Error:
명확한 오류 설명 + retry

Permission Denied:
권한 설명 + back action

형태로 구현한다.


━━━━━━━━━━━━━━━━━━━━
19. Security / Privacy
━━━━━━━━━━━━━━━━━━━━

아동 및 상담 관련 민감정보를 다루는 시스템이므로
보안 UI를 실제 업무 시스템 수준으로 설계한다.

로그인 화면에는:

- 기관 ID
- 비밀번호
- 상담사 / 관리자 권한
- 필요 시 OTP
- 최근 로그인 정보
- 보안 안내

를 표시한다.

사례 목록에서는
필요한 개인정보를 마스킹한다.

관리자와 상담사의 접근 가능한 메뉴 및 데이터 범위가
시각적으로 일관되게 구분되어야 한다.


━━━━━━━━━━━━━━━━━━━━
20. Login
━━━━━━━━━━━━━━━━━━━━

현재 로그인 화면의
2-column 구조는 유지한다.

LEFT:
I-SPOT branding / product explanation

RIGHT:
institution login

왼쪽에 현재 표시된

"말과 그림 속 작은
위험 신호를 찾아,
상담사의 판단을 돕는"

문구와

"AI 아동상담 지원 서비스"

정체성을 유지한다.

emoji 스타일 기능 icon은
simple outline icon으로 교체한다.

로그인 Card는
큰 floating SaaS card처럼 보이지 않게 한다.

Login container:
radius 8~10px
shadow 최소화
neutral border 중심

상담사 / 관리자 선택은
segmented control 형태로 구성한다.

최근 로그인 정보는
secondary security information으로 표현한다.


━━━━━━━━━━━━━━━━━━━━
21. Administrator UI
━━━━━━━━━━━━━━━━━━━━

기존 관리자 화면의 구조:

- 관리자 Dashboard
- 전체 사례 현황
- 업무 처리 현황
- 상담사 계정 관리
- 접속 기록
- 보안 이벤트
- 공지사항 관리
- 업무 배정

은 참고한다.

다만 현재 개발 우선순위는
상담사 핵심 Workflow이다.

따라서 관리자 Dashboard를
지나치게 복잡하게 확장하지 않는다.

관리자 UI도 상담사 UI와
동일한 Design System을 사용한다.

관리자라고 해서
purple theme 등 별도의 디자인 언어를 만들지 않는다.

역할 구분은
작은 role indicator 정도로 표현한다.


━━━━━━━━━━━━━━━━━━━━
22. Report
━━━━━━━━━━━━━━━━━━━━

보고서 화면은
문서 생성 workflow처럼 디자인한다.

LEFT:
report type / include section

RIGHT:
document preview

지원 보고서:

- 내부 사례회의
- 외부기관 전달
- 종결 검토 등

출력:

PDF
HWP

preview 영역을
빈 card처럼 크게 방치하지 말고
실제 document canvas처럼 표현한다.


━━━━━━━━━━━━━━━━━━━━
23. Responsive
━━━━━━━━━━━━━━━━━━━━

Desktop First.

본 시스템은 업무용이므로
1440px / 1280px Desktop 환경을 우선한다.

Tablet에서도 기능이 동작하도록 한다.

Mobile에서는
전체 desktop UI를 그대로 축소하지 않는다.

필요하면 Sidebar를 drawer 형태로 전환한다.

Transcript,
AI Review,
data table은
mobile에서 vertical layout으로 변경할 수 있다.


━━━━━━━━━━━━━━━━━━━━
24. Interaction
━━━━━━━━━━━━━━━━━━━━

모든 주요 component에 다음 상태를 설계한다.

default
hover
focus
active
selected
disabled
loading
error

Transition:
150~200ms

불필요한 animation은 사용하지 않는다.

업무 처리 완료에
confetti,
bounce,
large motion
등은 사용하지 않는다.


━━━━━━━━━━━━━━━━━━━━
25. Accessibility
━━━━━━━━━━━━━━━━━━━━

WCAG를 고려한다.

- 충분한 contrast
- keyboard navigation
- visible focus
- input label 연결
- status를 색상에만 의존하지 않음
- 최소 click target 확보
- 표의 header hierarchy 유지

상담사가 장시간 사용하는 시스템이므로
시각적 피로를 최소화한다.


━━━━━━━━━━━━━━━━━━━━
26. 구현 우선순위
━━━━━━━━━━━━━━━━━━━━

현재 핵심 구현 화면은 다음 순서이다.

S01 Login
S02 Case List
S03 Case Detail
S04 Recording
S05 Transcript Review
S06 AI Review / Summary Editor

이 6개 화면의 디자인 완성도를 우선한다.

이 화면들이 완성되기 전에는
복잡한 관리자 통계,
추가 Dashboard,
장식성 analytics 화면을 확장하지 않는다.


━━━━━━━━━━━━━━━━━━━━
27. 화면 간 일관성
━━━━━━━━━━━━━━━━━━━━

Login 화면에서 정립한 Design Language를
Master Design Reference로 사용한다.

모든 화면에서 다음을 통일한다.

- typography
- colors
- icon style
- spacing
- radius
- border
- input
- button
- status
- table
- panel
- navigation

페이지마다 새로운 디자인 스타일을 생성하지 않는다.


━━━━━━━━━━━━━━━━━━━━
28. Figma Component System
━━━━━━━━━━━━━━━━━━━━

재사용 가능한 Component / Variant를 만든다.

예:

Button
- Primary
- Secondary
- Danger
- Ghost
- Disabled
- Loading

Input
- Default
- Focus
- Error
- Disabled

Status
- Processing
- Review Required
- Approved
- Error

Badge
- Risk
- Role
- Task

Table Row
- Default
- Hover
- Selected

Navigation Item
- Default
- Hover
- Active
- Notification

Transcript Segment
- Default
- Low Confidence
- Selected
- Editing

AI Review Block
- Generated
- Needs Review
- Modified
- Approved

모든 화면에서 동일 component를 재사용한다.


━━━━━━━━━━━━━━━━━━━━
29. 최종 QA
━━━━━━━━━━━━━━━━━━━━

완성 후 모든 화면을 다시 검토한다.

다음 질문에 하나라도 YES라면 다시 수정한다.

"이 화면이 AI가 10초 만에 생성한 SaaS template처럼 보이는가?"

"모든 정보가 rounded card 안에 들어가 있는가?"

"불필요하게 색상이 많은가?"

"blue accent가 너무 많이 사용되었는가?"

"큰 icon과 badge가 지나치게 많은가?"

"spacing이 너무 넓어 실제 업무 시스템치고 정보 밀도가 낮은가?"

"같은 card pattern이 반복되는가?"

"AI 결과가 상담사의 판단보다 더 강하게 표현되는가?"

"Recording 화면이 너무 복잡한가?"

"Table 대신 card list를 불필요하게 사용하고 있는가?"

YES인 항목이 있으면 수정한다.


━━━━━━━━━━━━━━━━━━━━
30. 최종 목표
━━━━━━━━━━━━━━━━━━━━

최종 결과물은

"AI가 만든 상담 서비스 컨셉 UI"

가 아니라

"전문 UX/UI 디자이너가 설계하여
실제 아동보호전문기관에 납품할 수 있는
production-ready enterprise case management software"

처럼 보여야 한다.

현재 UI의 장점인

- Navy 기반 신뢰감
- 명확한 Sidebar navigation
- 상담 중심 workflow
- Case 중심 정보 구조

는 유지한다.

하지만

- card-heavy
- excessive rounded UI
- badge-heavy
- SaaS-template 느낌
- 과도한 whitespace
- 화면마다 반복되는 AI-generated layout

은 제거한다.

기존 기능을 삭제하지 말고,
정보 탐색 속도와 상담 업무 효율을 가장 중요한 디자인 기준으로 사용하여
전체 I-SPOT UI를 정제한다.