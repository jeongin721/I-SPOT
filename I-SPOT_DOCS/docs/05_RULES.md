# 05_RULES.md — AI & Project Rules

이 문서는 모든 역할에 공통 적용된다.

## 1. 절대 금지

- AI가 학대 여부를 최종 확정
- 자동 사례 종결 결정
- 자동 가정복귀 결정
- `abuse_confirmed = true` 같은 확정 필드
- 실제 아동 개인정보를 개발/테스트 데이터로 사용
- API Key/Secret 하드코딩
- 상담 원문 전체를 일반 로그에 출력
- 근거 없는 위험 신호 생성
- 공통 DB/API/AI Contract 단독 변경
- MVP 필요성이 없는 MSA/Kafka/Kubernetes 도입

## 2. Human-in-the-loop

모든 AI 결과는:
```text
AI 생성
→ 상담사 확인
→ 수정/제외 가능
→ 승인
→ 저장
```

형태를 유지한다.

## 3. AI 결과 규칙

- JSON Schema validation 가능
- 근거가 있으면 `segment_id` 연결
- 근거 부족 시 빈 결과 허용
- 결과를 억지로 생성하지 않음
- 내부 chain-of-thought를 결과 데이터로 저장하지 않음
- Provider/Model 변경 시 기존 Contract 유지

## 4. 데이터 규칙

- Case/Session 중심
- 개인정보 최소 저장
- 합성/가상 데이터는 기능 테스트에 사용 가능
- 합성 데이터 성능을 실제 현장 성능처럼 표현하지 않음
- 승인/수정 이력 추적

## 5. 변경 규칙

공통 구조 변경 필요 시 즉시 코드 수정 금지.

먼저:
```text
변경 이유
영향 문서
Backend 영향
Frontend 영향
AI 영향
Test 영향
권장 변경안
```

을 제시한다.

## 6. AI의 자율 결정 범위

AI가 직접 결정 가능:
- 함수명
- 내부 파일 분리
- 컴포넌트 세부 구조
- 테스트 구현 방식
- 비즈니스 규칙을 바꾸지 않는 리팩터링

AI가 임의 결정하면 안 됨:
- MVP 범위 변경
- 핵심 사용자 Flow 변경
- API Contract 변경
- DB 핵심 Entity 의미 변경
- AI 출력 Enum/필드 변경
- 최종 판단 주체 변경

## 7. 불확실한 경우

작업을 막지 않는 세부사항:
`ASSUMPTION`으로 명시하고 MVP에 가장 단순한 기본값을 사용한다.

작업을 막는 핵심사항:
질문은 한 번에 필요한 것만 최소한으로 한다.
