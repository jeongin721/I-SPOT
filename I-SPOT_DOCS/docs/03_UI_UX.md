# 03_UI_UX.md — UI/UX & User Flow

## 1. UX 목표

- 상담 중 조작 최소화
- 상담 종료 후 검수 효율화
- AI 근거 확인 용이
- 수정·승인 흐름 명확화
- 개인정보 노출 최소화
- AI가 최종 판정처럼 보이지 않게 설계

## 2. 핵심 User Flow

```text
로그인
→ 사례 목록
→ 사례 상세
→ 새 상담
→ 녹음/업로드
→ STT 처리
→ STT 검수
→ AI 분석
→ 상담 요약/문서
→ 수정
→ 승인
```

## 3. MVP 화면

### S01 Login
- 인증
- 권한 확인

### S02 Case List
- 담당 사례
- 사례 코드
- 최근 상담일
- 상태
- 검색
- 새 사례

### S03 Case Detail
- Case 기본정보
- Session Timeline
- Session 상태
- 새 상담 시작

### S04 Recording
- 녹음 시작
- 일시정지
- 종료
- 경과시간
- 마이크 오류
- 업로드 상태

상담 중 복잡한 AI 결과를 노출하지 않는다.

### S05 Transcript Review
- speaker
- timestamp
- segment text
- confidence
- 저신뢰 구간
- 수정
- 확정

### S06 AI Review / Document Editor
권장 구조:

```text
좌측
STT 원문 + 근거 Highlight

우측
AI 참고정보
상담 요약
문서 초안
수정/승인
```

## 4. 공통 UI 상태

```text
Loading
Empty
Processing
Review Required
Success
Error
Permission Denied
```

STT/AI 처리 화면은 새로고침 또는 재진입 후에도 현재 상태를 복구할 수 있어야 한다.

## 5. AI 표현 규칙

금지:
- 학대 확정
- 위험 확정
- AI 판정
- 자동 결정

권장:
- 관련 신호
- 추가 확인 필요
- AI 분석 참고정보
- 근거 발화
- 상담사 검토 필요

색상만으로 위험 상태를 표현하지 않는다.

## 6. Frontend 전달 규칙

화면 명세는 아래까지만 작성한다.

```text
화면 목적
→ 핵심 행동
→ 표시 데이터
→ Component
→ State
→ Event
→ Error
→ 완료 조건
```

새 데이터가 필요하면 임의로 화면용 필드를 만들지 않는다.
`02_ARCHITECTURE.md`의 API Contract 변경 필요 여부를 먼저 확인한다.
