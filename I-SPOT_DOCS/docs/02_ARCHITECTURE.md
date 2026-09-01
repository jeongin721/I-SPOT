# 02_ARCHITECTURE.md — Architecture & Contracts

## 1. 기술 기준

- Frontend: Next.js / React / TypeScript
- Styling: Tailwind CSS
- Backend: FastAPI / Python
- DB: PostgreSQL
- ORM: SQLAlchemy 2.x
- Validation: Pydantic
- STT: Whisper 계열 또는 CLOVA Speech
- LLM: OpenAI 계열 API
- RAG: pgvector + LangChain, 필요 시
- Container: Docker / Docker Compose
- CI: GitHub Actions
- Frontend Deploy: Vercel
- Backend Deploy: Render 또는 AWS
- Storage: MVP Local 가능, 배포 시 S3 고려

기술 변경은 `현재안 → 문제 → 대안 → 영향 → 비용 → 추천` 순으로 제안한다.

## 2. 시스템 Flow

```text
Frontend
  ↓
FastAPI
  ├─ PostgreSQL
  ├─ Audio Storage
  ├─ STT Provider
  └─ LLM/AI Pipeline
        ↓
Structured JSON
  ↓
상담사 검수
  ↓
DB 저장
```

## 3. 데이터 구조

```text
User
 └─ Case
     └─ Session
         ├─ Audio
         ├─ Transcript
         ├─ AIAnalysis
         ├─ Summary
         ├─ Document
         └─ AuditLog
```

### 핵심 규칙
- 모든 상담 데이터는 `case_id`, `session_id`로 추적 가능해야 한다.
- AIAnalysis는 사용한 Transcript version을 추적한다.
- AI 상세 결과는 MVP에서 JSONB 사용 가능하다.
- 개인정보 컬럼은 필요한 최소 수준만 저장한다.

## 4. 공통 상태

```text
CREATED
→ AUDIO_UPLOADED
→ STT_PROCESSING
→ STT_REVIEW_REQUIRED
→ STT_CONFIRMED
→ AI_PROCESSING
→ AI_REVIEW_REQUIRED
→ APPROVED
```

실패 시 재시도 가능한 상태/오류 정보를 유지한다.

## 5. API 기준

Base:
```text
/api/v1
```

핵심 Resource:
```text
/auth
/cases
/cases/{case_id}/sessions
/sessions/{session_id}/audio
/sessions/{session_id}/transcript
/sessions/{session_id}/analysis
/sessions/{session_id}/summary
/sessions/{session_id}/documents
```

성공:
```json
{"data": {}}
```

실패:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "message"
  }
}
```

장시간 STT/AI 작업은 MVP에서 Polling을 우선한다.

## 6. STT Contract

```json
{
  "schema_version": "1.0",
  "segments": [
    {
      "segment_id": "seg_001",
      "speaker": "CHILD",
      "start_ms": 1000,
      "end_ms": 4500,
      "text": "예시",
      "confidence": 0.91
    }
  ]
}
```

speaker:
```text
COUNSELOR | CHILD | GUARDIAN | OTHER | UNKNOWN
```

## 7. AI Output Contract

```json
{
  "schema_version": "1.0",
  "summary": {
    "overview": "",
    "key_points": []
  },
  "risk_utterances": [],
  "abuse_signals": [],
  "risk_factors": [],
  "warnings": []
}
```

학대유형:
```text
PHYSICAL | EMOTIONAL | SEXUAL | NEGLECT
```

근거가 있는 결과는 가능한 한 `segment_id`로 STT와 연결한다.

## 8. Contract 변경 규칙

DB/API/AI 출력 변경이 필요하면:

```text
변경 이유
→ 영향 Contract
→ Backend 영향
→ Frontend 영향
→ AI 영향
→ Test 영향
→ 변경안
```

한 파트가 공통 Contract를 단독 변경하지 않는다.
