# 04_DEVELOPMENT.md — Development Guide

## 1. 개발 원칙

- 5명 팀, 4개월 프로젝트 수준의 단순한 구조를 우선한다.
- MVP End-to-End Flow를 먼저 완성한다.
- 과도한 추상화·인프라를 피한다.
- 공통 Contract를 코드보다 먼저 확인한다.
- 가능한 경우 실제 코드와 테스트를 함께 작성한다.

## 2. 역할

### Backend
- FastAPI
- PostgreSQL
- Case/Session
- Audio/STT/AI 연동
- Document/Review
- API Test

### Frontend
- Next.js/TypeScript
- 핵심 User Flow
- Recorder
- STT 검수
- AI/Document Review
- API 연동

### Data/AI
- STT/화자 구분
- 요약
- 위험 발화
- 학대유형 관련 신호
- Risk Factor
- 평가

### UI/UX
- User Flow
- Wireframe/Figma
- Component/State
- Microcopy
- 사용성 Test

### Deploy/Test
- Docker
- CI
- API/Integration/E2E
- Deploy
- Smoke Test

## 3. 권장 개발 순서

```text
1. 공통 Contract 확정
2. DB/Backend 기본 구조
3. Case/Session
4. Frontend Case/Session
5. Audio
6. STT
7. Transcript Review
8. AI Pipeline
9. AI Review/Document
10. Approve
11. Integration Test
12. Deploy
```

## 4. Git

기본:
```text
main
develop
feature/*
```

PR 최소 조건:
- Build 성공
- Lint 성공
- Test 성공
- Secret 없음
- Contract 변경 시 docs 수정
- 주요 Flow 확인

## 5. 테스트

### Backend
- CRUD
- Validation
- Permission
- STT/AI Mock
- Error response

### Frontend
- Loading/Empty/Error
- Microphone permission
- Processing
- 수정/승인

### AI
- 정상
- 위험신호 없음
- 여러 유형
- 잘못된 JSON
- Timeout/Error

### E2E
```text
Case
→ Session
→ Audio
→ STT
→ Transcript 수정/확정
→ AI
→ Document
→ 수정
→ 승인
```

## 6. 배포

우선:
- Local: Docker Compose
- CI: GitHub Actions
- Frontend: Vercel
- Backend: Render/AWS
- DB: PostgreSQL

Kubernetes, Kafka, MSA는 요구사항상 필요성이 확인되기 전까지 사용하지 않는다.

## 7. AI 작업 응답 규칙

AI는 먼저 아래만 짧게 말한다.

```text
목표:
참조 문서:
수정/생성 파일:
의존 Task:
```

그 뒤 실제 구현을 진행한다.

작업 완료 시:
```text
완료 파일:
구현 기능:
테스트:
Contract 변경:
다음 Task:
```
