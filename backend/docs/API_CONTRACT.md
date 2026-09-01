# I-SPOT Backend API Contract (Frontend 연동용)

`I-SPOT_DOCS/docs/02_ARCHITECTURE.md` 의 공통 Contract 를 구현한 실제 API 명세다.
공통 Contract(STT / AI Output / 상태 / Response 형식)는 이 문서에서 변경하지 않는다.

- Base URL: `http://localhost:8000`
- API Prefix: `/api/v1`
- OpenAPI: `http://localhost:8000/docs`

---

## 1. 공통 규칙

### 1.1 성공 응답

항상 `data` 로 감싼다.

```json
{ "data": { "...": "..." } }
```

목록은 `data.items` + `data.meta` 구조를 사용한다.

```json
{
  "data": {
    "items": [],
    "meta": { "total": 0, "page": 1, "page_size": 20, "total_pages": 0 }
  }
}
```

### 1.2 실패 응답

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "사용자에게 보여줄 수 있는 메시지",
    "details": { "fields": [{ "field": "title", "reason": "..." }] }
  }
}
```

- `details` 는 있을 때만 포함된다(주로 `VALIDATION_ERROR`).
- `message` 는 한국어이며 그대로 노출 가능하다.

### 1.3 인증

로그인 후 받은 token 을 모든 요청에 붙인다.

```http
Authorization: Bearer <access_token>
```

- 토큰 없음/만료/오류 → `401 UNAUTHORIZED`
- 권한 없음 → `403 FORBIDDEN` (담당이 아닌 Case 접근 포함)

### 1.4 장시간 작업은 Polling

STT/AI 요청은 `202 Accepted` 로 즉시 반환되고 실제 처리는 서버에서 이어진다.
Frontend 는 아래 중 하나를 주기적으로 조회한다(권장 2~3초).

- `GET /sessions/{session_id}` — 전체 진행 상태
- `GET /sessions/{session_id}/transcript` — STT 진행/결과
- `GET /sessions/{session_id}/analysis` — AI 진행/결과

결과가 아직 없어도 **404 가 아니라** `transcript: null` / `analysis: null` 을 반환한다.

---

## 2. Session 상태

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

실패 상태(재시도 가능):

```text
STT_FAILED    ← STT_PROCESSING 실패
AI_FAILED     ← AI_PROCESSING 실패
```

실패 시 `error` 필드가 함께 내려온다.

```json
{
  "data": {
    "session_status": "STT_FAILED",
    "transcript": null,
    "error": { "code": "STT_TIMEOUT", "message": "..." }
  }
}
```

재시도는 같은 요청을 다시 호출하면 된다(`POST .../transcript`, `POST .../analysis`).

### 화면 상태 매핑 (권장)

| session_status | 화면 |
|---|---|
| `CREATED` | 녹음 대기 |
| `AUDIO_UPLOADED` | STT 실행 가능 |
| `STT_PROCESSING` | Processing (Polling) |
| `STT_REVIEW_REQUIRED` | Transcript 검수 화면 |
| `STT_CONFIRMED` | AI 분석 실행 가능 |
| `AI_PROCESSING` | Processing (Polling) |
| `AI_REVIEW_REQUIRED` | AI Review / Summary Editor |
| `APPROVED` | 읽기 전용 (완료) |
| `STT_FAILED` / `AI_FAILED` | Error + 재시도 버튼 |

---

## 3. Auth

### POST /api/v1/auth/login

```json
{ "email": "counselor@example.com", "password": "..." }
```

```json
{
  "data": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_in": 43200,
    "user": {
      "id": "uuid",
      "email": "counselor@example.com",
      "name": "상담사",
      "role": "COUNSELOR",
      "is_active": true,
      "created_at": "2026-09-01T10:00:00Z"
    }
  }
}
```

오류: `401 INVALID_CREDENTIALS`, `403 INACTIVE_USER`

### GET /api/v1/auth/me

현재 로그인 사용자. 새로고침 후 세션 복원에 사용한다.

### POST /api/v1/auth/users (관리자 전용)

```json
{ "email": "new@example.com", "password": "8자 이상", "name": "이름", "role": "COUNSELOR" }
```

`role`: `COUNSELOR | ADMIN`
오류: `403 FORBIDDEN`, `409 DUPLICATE_RESOURCE`

> 자유 회원가입 endpoint 는 존재하지 않는다.

---

## 4. Cases

### GET /api/v1/cases

Query: `page`, `page_size`(≤100), `status`(`ACTIVE|CLOSED`), `search`

- 상담사: 담당 Case 만 반환
- 관리자: 전체 반환

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "case_number": "C-2026-0001",
        "title": "사례 제목",
        "child_alias": "아동_001",
        "child_birth_year": 2015,
        "child_gender": null,
        "status": "ACTIVE",
        "notes": null,
        "counselor_id": "uuid",
        "created_at": "...",
        "updated_at": "..."
      }
    ],
    "meta": { "total": 1, "page": 1, "page_size": 20, "total_pages": 1 }
  }
}
```

> 개인정보 최소화 원칙에 따라 아동 실명 필드는 없다. `child_alias` 를 사용한다.

### POST /api/v1/cases → 201

```json
{
  "title": "사례 제목",
  "child_alias": "아동_001",
  "child_birth_year": 2015,
  "child_gender": null,
  "notes": null,
  "counselor_id": null,
  "case_number": null
}
```

- `title`, `child_alias` 필수
- `counselor_id` 미지정 → 요청자 본인. 타인 지정은 **관리자만** 가능(`403 FORBIDDEN`)
- `case_number` 미지정 → `C-YYYY-NNNN` 자동 생성

### GET /api/v1/cases/{case_id}

`CaseResponse` + `counselor`(사용자 객체) + `session_count`

오류: `404 CASE_NOT_FOUND`, `403 FORBIDDEN`

### PATCH /api/v1/cases/{case_id}

변경할 필드만 보낸다. `status` 로 사례를 종결(`CLOSED`)할 수 있다.

### DELETE /api/v1/cases/{case_id} → 204

관리자 전용. Session 이하 데이터가 함께 삭제된다.

---

## 5. Sessions

### GET /api/v1/cases/{case_id}/sessions

Query: `page`, `page_size`, `status`
최신 회기(`session_number` 내림차순)부터 반환한다.

### POST /api/v1/cases/{case_id}/sessions → 201

```json
{ "title": "1회기 상담", "consulted_at": null, "location": null, "memo": null }
```

`session_number` 는 Case 내에서 1부터 자동 증가한다.

### GET /api/v1/sessions/{session_id}

**새로고침 후 화면 복원용 핵심 endpoint.**

```json
{
  "data": {
    "id": "uuid",
    "case_id": "uuid",
    "session_number": 1,
    "title": "1회기 상담",
    "status": "AI_REVIEW_REQUIRED",
    "counselor_id": "uuid",
    "consulted_at": null,
    "location": null,
    "memo": null,
    "created_at": "...",
    "updated_at": "...",
    "stt_started_at": "...",
    "stt_completed_at": "...",
    "ai_started_at": "...",
    "ai_completed_at": "...",
    "approved_at": null,

    "has_audio": true,
    "has_transcript": true,
    "transcript_version": 2,
    "transcript_confirmed": true,
    "has_analysis": true,
    "has_summary": true,
    "summary_approved": false,
    "error": null
  }
}
```

### PATCH /api/v1/sessions/{session_id}

`APPROVED` 상태에서는 `409 ALREADY_APPROVED`.

### DELETE /api/v1/sessions/{session_id} → 204

음성 파일도 함께 삭제된다.

---

## 6. Audio

### POST /api/v1/sessions/{session_id}/audio → 201

`multipart/form-data`

| field | 필수 | 설명 |
|---|---|---|
| `file` | O | 녹음 파일 |
| `duration_ms` | X | 클라이언트 측정 길이(ms). WAV 는 서버가 계산 |

```json
{
  "data": {
    "audio": {
      "id": "uuid",
      "session_id": "uuid",
      "path": "{case_id}/{session_id}/ab12cd34_recording.webm",
      "original_filename": "recording.webm",
      "mime_type": "audio/webm",
      "size_bytes": 183245,
      "duration_ms": 45000,
      "checksum_sha256": "...",
      "created_at": "..."
    },
    "session_status": "AUDIO_UPLOADED"
  }
}
```

허용 확장자: `.wav .mp3 .m4a .mp4 .ogg .flac .webm`
기본 최대 크기: 200MB (`AUDIO_MAX_SIZE_MB`)

브라우저 `MediaRecorder` 의 `audio/webm` 을 그대로 업로드할 수 있다.
재업로드도 허용되며 최신 파일이 STT 대상이 된다.

오류 코드

| code | status | 상황 |
|---|---|---|
| `AUDIO_EMPTY_FILE` | 400 | 빈 파일 |
| `AUDIO_TOO_LARGE` | 400 | 크기 초과 |
| `AUDIO_UNSUPPORTED_TYPE` | 400 | 확장자/MIME 불허, 확장자와 실제 형식 불일치 |
| `AUDIO_CORRUPTED` | 400 | 음성 형식 판별 불가 |
| `AUDIO_INVALID_FILENAME` | 400 | 파일명 없음/확장자 없음 |
| `INVALID_SESSION_STATE` | 409 | 업로드 불가 상태 |

### GET /api/v1/sessions/{session_id}/audio

최신 음성 metadata. 없으면 `404 AUDIO_NOT_FOUND`.

---

## 7. Transcript (STT)

### POST /api/v1/sessions/{session_id}/transcript → 202

STT 실행 요청. Body 없음.

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "STT_PROCESSING",
    "message": "STT 처리를 시작했습니다. 상태를 Polling 해 주세요."
  }
}
```

오류: `404 AUDIO_NOT_FOUND`(음성 미업로드), `409 INVALID_SESSION_STATE`

### GET /api/v1/sessions/{session_id}/transcript

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "STT_REVIEW_REQUIRED",
    "transcript": {
      "id": "uuid",
      "session_id": "uuid",
      "version": 1,
      "schema_version": "1.0",
      "source": "STT",
      "is_confirmed": false,
      "confirmed_at": null,
      "stt_provider": "mock",
      "stt_model": "mock-stt-1.0",
      "created_at": "...",
      "segments": [
        {
          "segment_id": "seg_001",
          "speaker": "CHILD",
          "start_ms": 1000,
          "end_ms": 4500,
          "text": "발화 내용",
          "confidence": 0.91
        }
      ],
      "edited_segment_ids": []
    },
    "error": null
  }
}
```

**`segments` 는 STT Contract 와 완전히 동일하다.** segment 안에 필드를 추가하지 않는다.
상담사 수정 여부는 transcript level 의 `edited_segment_ids` 로 판단한다.

`speaker`: `COUNSELOR | CHILD | GUARDIAN | OTHER | UNKNOWN`
`source`: `STT | COUNSELOR_EDIT`

저신뢰 구간 표시는 `confidence` 로 판단하되(예: `< 0.7`),
`edited_segment_ids` 에 포함된 segment 는 상담사가 확인했으므로 경고를 해제해도 된다.

### PATCH /api/v1/sessions/{session_id}/transcript

수정은 **새 version 을 생성**하고 이전 version 은 이력으로 보존한다.

```json
{
  "segments": [
    { "segment_id": "seg_001", "text": "수정된 문장", "speaker": "CHILD", "start_ms": 1000, "end_ms": 4200 }
  ],
  "removed_segment_ids": ["seg_008"]
}
```

- `segments[]` 는 `segment_id` 필수 + 나머지 중 최소 1개
- 수정/삭제 중 최소 1개는 있어야 한다(`422 VALIDATION_ERROR`)
- 모든 segment 삭제는 불가
- `confidence` 는 STT 값이므로 수정 대상이 아니다

응답은 새 `TranscriptResponse`. 확정 이후 수정하면 상태가 `STT_REVIEW_REQUIRED` 로 되돌아간다.

오류: `404 TRANSCRIPT_NOT_FOUND`(없는 segment_id 포함), `409 INVALID_SESSION_STATE`

### POST /api/v1/sessions/{session_id}/transcript/confirm

Transcript 확정 → `STT_CONFIRMED`. AI 분석의 전제 조건이다.

오류: `404 TRANSCRIPT_NOT_FOUND`, `409 TRANSCRIPT_ALREADY_CONFIRMED`

---

## 8. Analysis (AI)

### POST /api/v1/sessions/{session_id}/analysis → 202

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "AI_PROCESSING",
    "analysis_id": "uuid",
    "message": "AI 분석을 시작했습니다. 상태를 Polling 해 주세요."
  }
}
```

오류
- `404 TRANSCRIPT_NOT_FOUND` — Transcript 없음
- `409 TRANSCRIPT_NOT_CONFIRMED` — 확정 전
- `409 INVALID_SESSION_STATE`

### GET /api/v1/sessions/{session_id}/analysis

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "AI_REVIEW_REQUIRED",
    "analysis": {
      "id": "uuid",
      "session_id": "uuid",
      "transcript_id": "uuid",
      "transcript_version": 2,
      "status": "COMPLETED",
      "schema_version": "1.0",
      "provider": "mock",
      "model": "mock-ai-1.0",
      "created_at": "...",
      "completed_at": "...",
      "result": {
        "schema_version": "1.0",
        "summary": { "overview": "...", "key_points": ["...", "..."] },
        "risk_utterances": [],
        "abuse_signals": [],
        "risk_factors": [],
        "warnings": ["추가 확인이 필요한 항목이 있습니다."]
      },
      "summary_evidence": [
        { "key_point": "...", "segment_ids": ["seg_004"], "score": 0.75 }
      ],
      "error": null
    },
    "error": null
  }
}
```

- `result` 는 **AI 담당의 Structured JSON Contract 원본**이다. Backend 가 변형하지 않는다.
- 9월 범위에서 `risk_utterances` / `abuse_signals` / `risk_factors` 는 빈 배열일 수 있다.
- `summary_evidence` 는 요약 문장 ↔ 근거 발화(`segment_id`) 연결 정보다. 근거 발화 하이라이트에 사용한다.
- `analysis.status`: `PROCESSING | COMPLETED | FAILED`

AI 오류 코드: `AI_FAILED`, `AI_TIMEOUT`, `AI_INVALID_OUTPUT`, `AI_AUTH_ERROR`, `AI_QUOTA_ERROR`

> **표현 주의**: AI 결과는 판정이 아니다. "AI 분석 참고정보", "관련 신호",
> "추가 확인 필요", "근거 발화", "상담사 검토 필요" 로 표기하고
> "학대 확정", "위험 확정", "AI 판정", "자동 결정" 표현은 사용하지 않는다.

---

## 9. Summary (상담사 검수 / 승인)

AI 원본(`analysis.result`)은 보존되고, 상담사가 수정하는 사본이 Summary 다.

### GET /api/v1/sessions/{session_id}/summary

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "AI_REVIEW_REQUIRED",
    "summary": {
      "id": "uuid",
      "session_id": "uuid",
      "analysis_id": "uuid",
      "overview": "요약 본문",
      "key_points": ["항목 1", "항목 2"],
      "counselor_note": null,
      "status": "DRAFT",
      "is_edited": false,
      "approved_at": null,
      "approved_by_id": null,
      "created_at": "...",
      "updated_at": "..."
    },
    "summary_evidence": [
      { "key_point": "항목 1", "segment_ids": ["seg_004"], "score": 0.75 }
    ],
    "error": null
  }
}
```

`status`: `DRAFT | APPROVED` — AI 결과는 항상 `DRAFT` 로 시작하며 자동 승인되지 않는다.

### PATCH /api/v1/sessions/{session_id}/summary

```json
{
  "overview": "상담사가 검토한 요약",
  "key_points": ["확인된 내용", "추가 확인 필요"],
  "counselor_note": "다음 회기 확인 예정"
}
```

- 최소 1개 필드 필요(`422 VALIDATION_ERROR`)
- 수정하면 `is_edited: true`
- 상태는 `AI_REVIEW_REQUIRED` 에서만 수정 가능
- 승인 후 수정 시 `409 ALREADY_APPROVED`

> 수정한 Summary 는 AI 재분석으로 덮어써지지 않는다.
> 새 AI 결과는 `GET .../analysis` 로 확인한다.

### POST /api/v1/sessions/{session_id}/summary/approve

승인 → Summary `APPROVED`, Session `APPROVED`.

오류: `404 SUMMARY_NOT_FOUND`, `409 ALREADY_APPROVED`, `409 INVALID_SESSION_STATE`

---

## 10. Documents

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/sessions/{session_id}/documents` | 목록 |
| POST | `/api/v1/sessions/{session_id}/documents` | 생성 (201) |
| PATCH | `/api/v1/sessions/{session_id}/documents/{document_id}` | 수정 |
| POST | `/api/v1/sessions/{session_id}/documents/{document_id}/approve` | 승인 |

```json
{ "title": "상담 기록", "content": "본문", "doc_type": "CONSULTATION_RECORD" }
```

승인된 문서는 수정할 수 없다(`409 ALREADY_APPROVED`).

---

## 11. Error Code 목록

| code | status | 설명 |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | 로그인 실패 |
| `UNAUTHORIZED` | 401 | 토큰 없음/만료/오류 |
| `INACTIVE_USER` | 403 | 비활성 계정 |
| `FORBIDDEN` | 403 | 권한 없음 (담당 아닌 Case 포함) |
| `NOT_FOUND` | 404 | 존재하지 않는 경로 |
| `CASE_NOT_FOUND` | 404 | 사례 없음 |
| `SESSION_NOT_FOUND` | 404 | Session 없음 |
| `AUDIO_NOT_FOUND` | 404 | 음성 없음 |
| `TRANSCRIPT_NOT_FOUND` | 404 | Transcript / segment_id 없음 |
| `ANALYSIS_NOT_FOUND` | 404 | AI 결과 없음 |
| `SUMMARY_NOT_FOUND` | 404 | 요약 없음 |
| `DOCUMENT_NOT_FOUND` | 404 | 문서 없음 |
| `USER_NOT_FOUND` | 404 | 사용자 없음 |
| `VALIDATION_ERROR` | 422 | 입력값 오류 (`details.fields`) |
| `DUPLICATE_RESOURCE` | 409 | 중복 (이메일 / 사례번호) |
| `INVALID_SESSION_STATE` | 409 | 상태 전이 불가 (`details.current_status`, `details.expected_status`) |
| `TRANSCRIPT_NOT_CONFIRMED` | 409 | 확정 전 AI 분석 요청 |
| `TRANSCRIPT_ALREADY_CONFIRMED` | 409 | 이미 확정됨 |
| `ALREADY_APPROVED` | 409 | 이미 승인됨 |
| `AUDIO_EMPTY_FILE` / `AUDIO_TOO_LARGE` / `AUDIO_UNSUPPORTED_TYPE` / `AUDIO_CORRUPTED` / `AUDIO_INVALID_FILENAME` / `AUDIO_STORAGE_ERROR` | 400 | 음성 검증 실패 |
| `STT_FAILED` / `STT_TIMEOUT` / `STT_INVALID_OUTPUT` | — | Session `error` 필드로 전달 |
| `AI_FAILED` / `AI_TIMEOUT` / `AI_INVALID_OUTPUT` / `AI_AUTH_ERROR` / `AI_QUOTA_ERROR` | — | Session `error` 필드로 전달 |
| `METHOD_NOT_ALLOWED` | 405 | 잘못된 method |
| `INTERNAL_ERROR` | 500 | 서버 오류 |

---

## 12. 전체 Flow 예시

```text
POST /auth/login
GET  /cases
POST /cases                                   (필요 시)
POST /cases/{case_id}/sessions                → CREATED
POST /sessions/{id}/audio                     → AUDIO_UPLOADED
POST /sessions/{id}/transcript                → 202 / STT_PROCESSING
GET  /sessions/{id}/transcript   (polling)    → STT_REVIEW_REQUIRED
PATCH /sessions/{id}/transcript               → version 2
POST /sessions/{id}/transcript/confirm        → STT_CONFIRMED
POST /sessions/{id}/analysis                  → 202 / AI_PROCESSING
GET  /sessions/{id}/analysis     (polling)    → AI_REVIEW_REQUIRED
PATCH /sessions/{id}/summary                  → is_edited: true
POST /sessions/{id}/summary/approve           → APPROVED
GET  /sessions/{id}                           → 상태/데이터 유지 확인
```

---

## 13. Contract 변경 요청

이 문서의 구조를 바꿔야 하면 코드 수정 전에 아래 형식으로 제안한다.

```text
변경 이유
영향 Contract
Backend 영향
Frontend 영향
AI 영향
Test 영향
권장 변경안
```
