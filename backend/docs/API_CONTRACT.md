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
예외: 계정 목록(3절 `GET /auth/users`) · 문서 목록(10절)은 `data` 가 배열 그대로다(페이지 없음).

```json
{
  "data": {
    "items": [],
    "meta": { "total": 0, "page": 1, "page_size": 20, "total_pages": 0 }
  }
}
```

목록 Query 의 `page` 는 1 ~ 1,000,000, `page_size` 는 1 ~ 100 이다(사례 · 회기 · 업무 · 감사 로그 목록 공통).
범위를 벗어나면 `422 VALIDATION_ERROR`(`details.fields` 의 `field` 는 `query.page` · `query.page_size`)다.
범위 안이지만 마지막 page 를 넘으면 `items` 가 빈 배열인 200 이다.

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
- `message` 는 한국어이며 그대로 노출 가능하다. 라우터에 닿기 전에 서버 프레임워크가 막는 오류도 같다 —
  없는 경로 `404 NOT_FOUND`("요청한 경로를 찾을 수 없습니다."), 허용되지 않는 method `405 METHOD_NOT_ALLOWED`
  ("허용되지 않는 요청 방식입니다."), 해석할 수 없거나 프레임워크의 form 제한을 넘는 form 본문(예: multipart 의
  boundary 없음, multipart · urlencoded 의 파일이 아닌 칸 하나가 1MB 를 넘음)
  `400 VALIDATION_ERROR`(`details` 없음, "요청 형식이 올바르지 않습니다."). `INTERNAL_ERROR` 는 서버 오류(5xx)에만 쓴다.
- JSON 문법 오류는 400 이 아니라 **`422 VALIDATION_ERROR`** 이고 `details.fields` 로 온다
  ("요청 값이 올바르지 않습니다."). 이때 `field` 는 필드 이름이 아니라 깨진 글자 위치(예: `"30"`), `reason` 은
  `"JSON decode error"` 다. 본문 해석은 로그인 확인보다 먼저라, JSON 본문을 받는 창구는 token 이 없어도 `401` 이
  아니라 이 422 를 준다.
- `400 VALIDATION_ERROR`(`details` 없음)는 위 경우 말고도 세 가지가 더 있다. `message` 로 구분한다.
  - JSON 본문을 읽을 수 없음 — JSON 본문을 받는 창구에 `Content-Type` 이 JSON 인 본문을 보냈는데 UTF-8 로 읽을 수
    없는 바이트가 들어 있음(예: CP949 로 인코딩한 한글). 프레임워크는 JSON 문법 오류만 422 로 바꾸고 이런 해석 오류는
    400 으로 낸다. **로그인 확인보다 먼저** 거절한다("요청 형식이 올바르지 않습니다.").
  - 본문이 너무 큼 — 본문을 받는 창구(JSON · form)에서 본문이 `REQUEST_MAX_BODY_MB`(기본 2MB)를 넘으면
    **로그인 확인보다 먼저** 거절한다("요청 본문이 너무 큽니다(최대 2MB)."). 음성 업로드는 6절(token 의 서명 · 만료를
    먼저 보고, 맞으면 `AUDIO_TOO_LARGE`, 없거나 틀리면 `401`).
    음성 업로드 경로라도 `multipart/form-data` 가 아닌 본문에는 음성 한도를 주지 않는다.
    `application/x-www-form-urlencoded` 본문은 이 한도와 문구를 쓴다(Content-Length 가 없거나 한도 안일 때,
    받은 양이 한도에 닿기 전에 칸 하나가 1MB 를 넘으면 위의 form 제한 "요청 형식이 올바르지 않습니다." 다).
    그 밖의 형식(JSON · text · octet-stream · Content-Type 없음)은 이 창구가 본문을 읽지 않으므로 크기와 상관없이
    token 이 없거나 틀리면 `401`, 맞으면 `422 VALIDATION_ERROR`(`details.fields` 에 `file` — 녹음 파일 없음)다.
    본문을 읽지 않는 창구(GET, 본문 없는 POST)는 보낸 본문을 무시하고 평소처럼 답한다(`401` 이나 정상 응답).
  - 서비스가 내는 것 — 사례 담당자로 정지된 계정을 지정함(4절).

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

처리 중 상태가 제한 시간(`STT_TIMEOUT_SECONDS` / `AI_TIMEOUT_SECONDS`) + 60초가 지나도 끝나지 않으면
(서버 재시작 등으로 작업이 사라진 경우) 위 조회나 재요청 시점에 `STT_FAILED` / `AI_FAILED` 로 바뀌고
`error.code` 도 같은 값으로 내려온다. 회기 목록(`GET /cases/{case_id}/sessions`)과 처리 대기 업무(11절) 조회도
같은 판단으로 먼저 마감한 뒤 돌려준다. 재시도 버튼으로 다시 요청하면 된다.

### 1.5 시각

시각 칸(`created_at`, `consulted_at` 등)은 ISO 8601 문자열이고, 저장은 UTC 로 한다.

- 소수점 아래 마이크로초가 붙을 수 있다(예: `2026-09-30T00:49:54.529999`). 0 이면 소수부가 없다.
- 시간대 표시는 DB 와 그 DB 의 시간대 설정에 따라 다르다(값이 가리키는 순간은 같다).
  - SQLite(로컬 · 테스트): 대부분 표시 없이 온다(예: `2026-09-30T04:09:41.553068`). 이 값은 UTC 로 읽는다.
  - PostgreSQL: DB 연결 시간대의 오프셋이 붙는다. `docker-compose.yml` 의 db(`TZ: Asia/Seoul`)에서는
    `+09:00`(예: `2026-09-30T13:09:41.553068+09:00`), 연결 시간대가 UTC 이면 `Z` 다.
  - 11절 `waiting_since` 는 DB 와 관계없이 항상 UTC(`Z`)로 준다. 방금 계산한 값을 그대로 돌려주는 칸도 `Z` 로 올 수 있다.
- Frontend 는 표시가 없으면 UTC 로, 있으면 그 표시대로 읽는다. 표시가 있는 값에 `Z` 를 덧붙이지 않는다.
  같은 칸도 DB 에 따라 표시가 달라지니, 칸 이름으로 나누지 말고 값의 모양을 보고 읽는다.
  같은 순간도 칸마다 표시가 다를 수 있으니(`waiting_since` 는 `Z`, `consulted_at` 은 `+09:00`) 문자열로 비교 · 정렬하지 않는다.
- 이 문서 예시의 `Z` 는 표기 예일 뿐이다(11절 `waiting_since` 는 항상 `Z` 다).
- 보낼 때(`consulted_at` 만들기 · 고치기, 감사 로그 조회의 `since` · `until`)는 UTC(`Z`)로 보낸다. 표시 없이 보내지 않는다.
  감사 로그의 `since` · `until` 은 서버가 UTC 로 바꿔 비교하므로 `+09:00` 도 같은 순간으로 읽고, 표시 없는 값은 UTC 로 읽는다.
  `consulted_at` 은 아래처럼 어긋나니 반드시 `Z` 로 보낸다.
  SQLite 는 오프셋을 버리고 저장해 `+09:00` 을 붙여 보내면 9시간 어긋나고, PostgreSQL 은 표시 없는 값을
  DB 시간대로 읽어 `Asia/Seoul` 설정에서는 9시간 어긋난다(PostgreSQL 은 `Z` 와 `+09:00` 을 같은 순간으로 저장한다).

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
      "created_at": "2026-09-01T10:00:00Z",
      "last_login_at": "2026-09-29T09:00:00Z",
      "must_change_password": false,
      "is_locked": false,
      "locked_until": null,
      "dormant_at": null
    }
  }
}
```

오류: `401 INVALID_CREDENTIALS`, `403 INACTIVE_USER`, `403 ACCOUNT_DORMANT`, `403 TEMP_PASSWORD_EXPIRED`

**계정 상태는 비밀번호가 맞은 뒤에만 알려준다.** 먼저 알려주면 비밀번호를 모르는 사람이
"이 이메일은 등록돼 있다" 를 알아내는 계정 열거가 된다. 틀린 비밀번호는 언제나 `INVALID_CREDENTIALS` 다.

**실패 잠금은 비밀번호가 맞아도 알려주지 않는다.** 잠긴 계정은 비밀번호를 확인하지 않고
틀린 비밀번호 · 없는 계정과 **같은 `401 INVALID_CREDENTIALS`(같은 문구)** 를 준다. 잠김을 따로 알려주면
잠긴 뒤에도 계속 맞혀 보다가 응답이 바뀌는 순간 정답을 알게 된다. 잠긴 사람도 안내받도록 문구에
"여러 번 틀려 잠겼다면 관리자에게 문의하세요" 를 늘 함께 싣는다. 관리자는 감사 로그의 `error_code`
(`ACCOUNT_LOCKED`)와 계정 응답의 `is_locked` 로 구분한다. 없는 계정 · 잠긴 계정도 비밀번호 비교(bcrypt)를
한 번 하고, DB 기록도 같은 순서(대조 전에 시도 기록을 한 번 커밋, 대조 뒤에는 잠글 때 말고는 쓰지 않음)로 해서
응답 시간 차이를 줄였다. 있는 계정은 실패 횟수를 세는 쓰기 하나가 더 있어 그만큼(로컬 SQLite 실측 약 1ms)의
차이는 남는다.

```json
{ "error": { "code": "INVALID_CREDENTIALS", "message": "이메일 또는 비밀번호가 올바르지 않습니다. 여러 번 틀려 잠겼다면 관리자에게 문의하세요." } }
```

| 상태 | 로그인 응답 | 푸는 방법 |
| --- | --- | --- |
| 관리자가 정지 | `403 INACTIVE_USER` | 관리자가 `PATCH /auth/users/{id}` 로 활성화 |
| 로그인 5회 실패 | `401 INVALID_CREDENTIALS` (감사 로그 `error_code` 는 `ACCOUNT_LOCKED`) | 관리자가 `POST /auth/users/{id}/unlock`. `LOGIN_LOCK_MINUTES` 가 0 보다 크면 그 시간이 지나도 풀린다 |
| 2개월 미접속 | `403 ACCOUNT_DORMANT` | 관리자가 `POST /auth/users/{id}/reactivate` |
| 임시 비밀번호 기간 경과(72시간) | `403 TEMP_PASSWORD_EXPIRED` | 관리자가 `POST /auth/users/{id}/password-reset` |

관리자가 모두 잠기거나 휴면이 되면 관리자 화면으로는 풀 수 없다. 그때는 서버에서
`python -m scripts.unlock_user --email <이메일>` 로 푼다(API 는 없다. `backend/README.md` 2.5절).

기준값은 설정으로 바꾼다 — `LOGIN_MAX_FAILURES`(5), `LOGIN_LOCK_MINUTES`(0 = 관리자만 해제),
`DORMANT_AFTER_DAYS`(60), `TEMP_PASSWORD_VALID_HOURS`(72).
시간 잠금(`LOGIN_LOCK_MINUTES` > 0)이 풀리면 실패 횟수도 0 으로 돌아가, 다시 5번 틀리면 다시 잠긴다.
잠긴 동안의 로그인 시도는 실패 횟수에 더하지 않는다.
**동시에 몰려 들어와도 비밀번호를 대조하는 것은 기준 횟수(5번)까지다.** 서버는 대조하기 전에 실패 횟수를 먼저 1 올려
두고(맞으면 되돌린다), 기준을 이미 채운 뒤 들어온 시도는 잠긴 계정과 같게 대조 없이 거절한다(감사 로그 `ACCOUNT_LOCKED`).
시간 잠금이 풀리는 순간 몰려 들어와도 같다. 잠금을 풀고 횟수를 비우는 것은 처음 읽은 잠금 시각이 그대로일 때 한 요청만
하므로, 다른 요청이 예약한 횟수나 다시 걸린 잠금을 지우지 않는다.

**임시 비밀번호 상태**(`must_change_password`)에서는 `GET /auth/me` 와 `POST /auth/me/password` 외의
모든 요청이 `403 PASSWORD_CHANGE_REQUIRED` 로 막힌다.

**Token 무효화** — 비밀번호를 바꾸거나 관리자가 강제 로그아웃 · 역할 변경 · 정지를 하면
그 계정에 발급된 Token 이 전부 무효가 된다(`401 UNAUTHORIZED`). 다시 로그인해야 한다.
정지된 계정은 다시 로그인할 때 `403 INACTIVE_USER` 로 이유를 알려준다. Token 버전을 올리지 않고 정지된 계정
(서버에서 DB 를 직접 고친 경우 등)은 기존 Token 요청도 `403 INACTIVE_USER` 다.
현재 비밀번호를 정해진 횟수만큼 틀려도 Token 이 끊긴다(아래 `POST /auth/me/password`).

### GET /api/v1/auth/me

현재 로그인 사용자. 새로고침 후 세션 복원에 사용한다.

### POST /api/v1/auth/me/password

본인 비밀번호 변경. 성공하면 `204` (본문 없음).

```json
{ "current_password": "...", "new_password": "..." }
```

현재 비밀번호를 함께 받는다. Token 만 훔친 사람이 비밀번호를 바꿔 계정을 가져가는 것을 막는다.
주소에 사용자 id 를 두지 않는다(`me`). 남의 비밀번호를 바꾸는 경로를 만들지 않기 위해서다.

오류: `401 UNAUTHORIZED`(로그인 안 됨, 또는 아래 반복 실패로 끊김), `400 INVALID_CURRENT_PASSWORD`(현재 비밀번호 불일치),
`422 WEAK_PASSWORD`, `422 SAME_PASSWORD`, `422 PASSWORD_REUSED`

현재 비밀번호가 틀린 것은 `401` 이 아니다. Frontend 는 `401` 을 로그인 만료로 보고 로그인 화면으로 보내므로,
입력만 틀렸는데 쫓겨나지 않도록 `400` 으로 구분한다.

**검사 순서** — `422 WEAK_PASSWORD`(새 비밀번호 규칙)와 `422 SAME_PASSWORD`(두 칸이 같음)는 현재 비밀번호를
확인하기 **전에** 나간다. 확인한 뒤에 하면 "현재 비밀번호가 맞으면 422, 틀리면 400" 이 되어, 비밀번호를 바꾸지
않고도 정답인지 알아내는 수단이 된다. `422 PASSWORD_REUSED` 는 이전 비밀번호를 알려 주는 셈이라 현재 비밀번호를
확인한 **뒤에만** 본다.

**반복 실패** — 현재 비밀번호가 틀린 요청은 감사 로그에 `PASSWORD_CHANGED` · `FAILURE`
(`error_code` `INVALID_CURRENT_PASSWORD`)로 남는다. 마지막 로그인(또는 비밀번호 변경) 뒤로 `LOGIN_MAX_FAILURES`(5)번
틀리면 그 계정의 Token 을 모두 끊고 `401 UNAUTHORIZED` 를 준다(감사 로그 `LOGOUT_ALL`,
`detail.reason` = `PASSWORD_CHANGE_FAILURES`). 계정은 잠그지 않는다 — 다시 로그인하면 되고 횟수도 처음부터 센다.
Token 만 가진 사람이 이 창구로 현재 비밀번호를 끝없이 맞혀 보지 못하게 하기 위해서다.

동시에 몰려 들어와도 현재 비밀번호를 대조하는 것은 기준 횟수까지다. 서버는 대조하기 **전에** 시도를 먼저 실패로 남겨
(맞으면 성공 기록으로 바꾸고, `PASSWORD_REUSED` 로 거절되면 지운다) 함께 들어온 요청도 바로 센다.

- 기준을 이미 채운 뒤 들어온 시도는 대조하지 않고 `401 UNAUTHORIZED`(위와 같은 문구)를 준다. 감사 로그 `error_code` 는 `UNAUTHORIZED`.
- 현재 비밀번호를 대조하는 사이 Token 이 끊겼으면(함께 보낸 다른 시도가 기준을 채움, 강제 로그아웃 등) 맞는 비밀번호여도
  바꾸지 않고 `401 UNAUTHORIZED` 를 준다. 감사 로그 `error_code` 는 `UNAUTHORIZED`.
- `LOGOUT_ALL` 은 한 번만 남는다.

### POST /api/v1/auth/users (관리자 전용)

```json
{ "email": "new@example.com", "password": "아래 비밀번호 규칙 참고", "name": "이름", "role": "COUNSELOR" }
```

`role`: `COUNSELOR | ADMIN`
오류: `403 FORBIDDEN`, `409 DUPLICATE_RESOURCE`, `422 WEAK_PASSWORD`

만든 관리자와 함께 감사 로그 `USER_CREATED` 로 남는다(아래 감사 로그 절).

> 자유 회원가입 endpoint 는 존재하지 않는다.

### 계정 관리 (관리자 전용)

| 창구 | 하는 일 | 응답 |
| --- | --- | --- |
| `GET /api/v1/auth/users` | 계정 목록(페이지 없음, `created_at` 오래된 순) | `200` 계정 배열 |
| `PATCH /api/v1/auth/users/{id}` | 활성화 · 비활성화(`is_active`), 역할(`role`), 이름(`name`) | `200` 계정 |
| `POST /api/v1/auth/users/{id}/password-reset` | 임시 비밀번호 재발급 | `200` 임시 비밀번호 |
| `POST /api/v1/auth/users/{id}/unlock` | 실패 잠금 해제 | `204` |
| `POST /api/v1/auth/users/{id}/reactivate` | 휴면 해제 + 임시 비밀번호 재발급 | `200` 임시 비밀번호 |
| `POST /api/v1/auth/users/{id}/logout-all` | 발급된 Token 전부 무효 | `204` |

```json
{ "data": { "temporary_password": "...", "expires_at": "...", "must_change_password": true } }
```

계정 목록은 `data` 가 계정 배열 그대로다(`items` · `meta` 없음 — 1.1 의 예외). 계정 하나의 모양은 로그인 응답의 `user` 와 같다.

**임시 비밀번호는 이 응답에서 한 번만 나간다.** 다시 조회할 수 없고 DB 에는 해시만 남는다.

**마지막 활성 관리자는 비활성화 · 역할 변경을 할 수 없다**(`409 VALIDATION_ERROR`). 아무도 풀 수 없게 되기 때문이다.
여기서 활성 관리자는 "지금 로그인할 수 있는 관리자" 다 — 정지 · 휴면 · **실패 잠금**된 관리자는 세지 않는다.
그래서 다른 관리자가 잠겨 있으면 남은 한 명은 끌 수 없고, 잠긴 관리자를 끄는 것은 막지 않는다.
마지막 관리자는 휴면으로도 바뀌지 않는다(같은 기준).
자기 계정에 `logout-all` 도 할 수 없다(`409 VALIDATION_ERROR`).

계정 응답에는 상태를 구분할 수 있게 `last_login_at` · `must_change_password` ·
`is_locked` · `locked_until` · `dormant_at` 이 함께 온다.

- **잠김 여부는 `is_locked` 로 본다.** 기본 설정(`LOGIN_LOCK_MINUTES`=0)에서는 시간이 지나도 풀리지 않아
  `locked_until` 이 비어 있다. `locked_until` 은 시간 잠금일 때 풀리는 시각이고, 그 시각이 지나면 `is_locked` 는 `false` 다.
- 로그인은 잠김을 알려주지 않으므로(위 로그인 절) 관리자 화면이 잠긴 계정을 알 수 있는 곳은 이 값과 감사 로그뿐이다.

### GET /api/v1/auth/audit-logs (관리자 전용)

Query: `page`(≤1,000,000), `page_size`(≤100), `action`, `status`(`SUCCESS|FAILURE`), `actor_id`, `since`, `until`

- `since` · `until` 은 ISO 8601 이고 경계를 포함한다(`since` ≤ `created_at` ≤ `until`). UTC(`Z`)로 보낸다(1.5).
  서버가 UTC 로 바꿔 비교하므로 `+09:00` 을 붙여도 같은 순간으로 읽고, 표시가 없으면 UTC 로 읽는다.
  UTC 로 바꾸면 날짜 범위를 벗어나는 값(예: `0001-01-01T00:00:00+09:00`, `9999-12-31T23:59:59-01:00`)은 가장 이른 ·
  가장 늦은 시각으로 보고 평소처럼 `200` 으로 답한다.
  화면의 날짜 입력값(`datetime-local`, 표시 없는 지역 시각)을 그대로 보내면 9시간 어긋나니 `Date.toISOString()` 으로 바꿔 보낸다.

```json
{
  "data": {
    "items": [{
      "id": "uuid", "action": "LOGIN", "status": "FAILURE",
      "error_code": "INVALID_CREDENTIALS", "actor_id": null, "actor_name": null,
      "entity_type": "User", "entity_id": null,
      "ip_address": "127.0.0.1", "user_agent": "...",
      "detail": null, "created_at": "..."
    }],
    "meta": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
  }
}
```

**행동은 `action`, 결과는 `status` 로 나눈다.** 실패를 별도 action 으로 만들지 않는다.
로그인 실패에 이메일은 저장하지 않으므로, 없는 계정의 실패는 `actor_id` 가 비어 있다.
`actor_name` 은 행동한 사람의 이름이다. `actor_id` 가 비어 있으면 함께 비어 있다.

로그인 실패의 `error_code` 는 응답과 다를 수 있다. 잠긴 계정의 시도는 응답이 `INVALID_CREDENTIALS` 라도
여기에는 `ACCOUNT_LOCKED` 로 남는다.

계정 생성은 `USER_CREATED` 로 남는다(`detail` 에 역할만, 이메일 · 이름은 담지 않는다). 관리자 API 로 만들면
`actor_id` 가 그 관리자, 서버에서 script 로 만들거나 고친 것은 `actor_id` 가 비어 있고 `detail.via` 에 script 이름이 있다.
**변경 전후 값은 담지 않는다** — 상담 원문이 감사 로그에 복제되면 개인정보 파기가 불가능해진다.

### 비밀번호 규칙

**새로 정하는 비밀번호에만 적용한다.** 로그인 요청은 검사하지 않는다 —
검사하면 규칙 이전에 만든 계정이 전부 잠긴다.

기본값은 **팀 회의 결정(2026-09-18)** 인 "8자 이상, 영문 · 숫자 · 특수문자 포함" 이다.

| 항목 | 기본값 | 설정 이름 |
| --- | --- | --- |
| 최소 길이 | 8자 | `PASSWORD_MIN_LENGTH` |
| 문자 종류 | 글자 · 숫자 · 특수문자 **3종 모두**. 대문자와 소문자를 나누지 않는다 | `PASSWORD_MIN_CLASSES` |
| 종류 면제 | **없음** (`0`). `12`~`72` 로 설정하면 그 길이 이상은 종류를 보지 않는다 | `PASSWORD_PASSPHRASE_LENGTH` |
| 공백 | 공백도 특수문자로 센다(앞뒤 공백은 거부) | 고정 |
| 최대 | 72바이트 (한글 24자) | 고정 — bcrypt 가 그 뒤를 잘라낸다 |

한글도 글자로 센다. 한글 + 숫자 + 특수문자면 통과한다.

같이 막는 것: 이메일 아이디 · 이름(한글 이름 포함), 서비스 이름(`ispot`), 흔한 비밀번호(`password` 등),
같은 문자 4회 반복, 연속 문자(`1234` · `qwer` · `asdf`), 숫자 · 영문 교차 배열(`1q2w` · `q1w2`),
한글 자판 상태로 친 키보드 줄(`ㅂㅈㄷㄱ` · `ㅁㄴㅇㄹ` · `ㅋㅌㅊㅍ`), 앞뒤 공백.
금지 단어는 흔한 기호 치환(`@`·`4`→a, `0`→o, `1`→i, `3`→e, `5`·`$`→s, `7`→t)을 되돌려서도 찾는다.
`P@ssw0rd` 는 `password` 로 본다.

한글은 표기 방식이 두 가지(NFC · NFD)라 Backend 가 저장 · 검증 모두 NFC 로 맞춘다. 기기가 달라도 같은 비밀번호로 로그인된다.

**이전 비밀번호는 다시 쓸 수 없다**(`422 PASSWORD_REUSED`). 최근 `PASSWORD_HISTORY_COUNT`(3)개를 본다.
관리자 재발급(`password-reset`) · 휴면 해제(`reactivate`) 전 비밀번호도 이력에 들어간다.
임시 비밀번호는 이력에 넣지 않는다 — 사람이 정한 비밀번호가 아니고, 넣으면 재발급 몇 번으로 진짜 이전 비밀번호가 밀려난다.

위반하면 `422 WEAK_PASSWORD` 이고 사유가 `details.reasons` 에 문장 배열로 담긴다.
아래는 `abc` 를 보냈을 때다.

```json
{
  "error": {
    "code": "WEAK_PASSWORD",
    "message": "비밀번호가 규칙에 맞지 않습니다.",
    "details": {
      "reasons": [
        "8자 이상이어야 합니다.",
        "영문(한글도 됩니다) · 숫자 · 특수문자 중 3종류 이상을 섞어야 합니다."
      ]
    }
  }
}
```

**비밀번호 원문은 응답 · 오류 · 로그 어디에도 담기지 않는다.**
8자 미만도 `WEAK_PASSWORD` 로 나간다. `422 VALIDATION_ERROR` 는 빈 값과 128자 초과뿐이다(요청 형식 검사).

---

## 4. Cases

### GET /api/v1/cases

Query: `page`(≤1,000,000), `page_size`(≤100), `status`(`ACTIVE|CLOSED`), `search`

- `search` 는 제목 · 사례 번호 · 아동 별칭에서 찾는다. `%`, `_` 도 글자 그대로 찾는다
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
        "guardian_type": "PARENTS",
        "guardian_note": null,
        "status": "ACTIVE",
        "notes": null,
        "counselor_id": "uuid",
        "counselor_name": "이서연",
        "created_at": "...",
        "updated_at": "...",
        "last_session_at": "2026-09-01T14:30:00Z"
      }
    ],
    "meta": { "total": 1, "page": 1, "page_size": 20, "total_pages": 1 }
  }
}
```

> 개인정보 최소화 원칙에 따라 아동 실명 필드는 없다. `child_alias` 를 사용한다.
> 같은 이유로 **보호자 실명도 저장하지 않는다.** 관계 유형만 기록한다.

`last_session_at` 은 Case List 화면(`03_UI_UX.md` S02)의 **최근 상담일**이다.
목록 조회에서 함께 계산되므로 Case 별로 Session 을 다시 호출할 필요가 없다.
Session 이 없으면 `null`, `consulted_at` 이 기록되지 않은 Session 은 생성 시각으로 대체된다.

`counselor_name` 은 담당 상담사 이름이다. 화면이 담당자를 이름으로 표시하므로
목록에서 함께 내려준다. 상담사 계정이 삭제되었으면 `null`.

#### 보호자 (`guardian_type` / `guardian_note`)

```text
PARENTS | FATHER | MOTHER | GRANDPARENTS | RELATIVE | FOSTER | FACILITY | OTHER
  부모     부       모       조부모         친인척     위탁     시설      기타
```

- 선택 항목이다. 지정하지 않으면 `null`
- 목록에 없는 관계는 `guardian_type: "OTHER"` + `guardian_note` 에 직접 입력
- **`guardian_note` 는 `OTHER` 일 때만 사용한다.** 다른 유형과 함께 보내면 `422`
  (유형을 골라놓고 자유 입력까지 하면 통계 기준이 갈라진다)
- 목록에 없는 값을 보내면 `422`

### POST /api/v1/cases → 201

```json
{
  "title": "사례 제목",
  "child_alias": "아동_001",
  "child_birth_year": 2015,
  "child_gender": null,
  "guardian_type": "PARENTS",
  "guardian_note": null,
  "notes": null,
  "counselor_id": null,
  "case_number": null
}
```

- `title`, `child_alias` 필수
- `guardian_type` 선택. 값 목록과 `guardian_note` 규칙은 위 참조
- `counselor_id` 미지정 → 요청자 본인. 타인 지정은 **관리자만** 가능(`403 FORBIDDEN`)
  - 없는 계정 → `404 USER_NOT_FOUND`, 정지된 계정(`is_active=false`) → `400 VALIDATION_ERROR`(`details` 없이 `message` 만 온다.
    "비활성화된 사용자를 담당 상담사로 지정할 수 없습니다.")
- `case_number` 미지정 → `C-YYYY-NNNN` 자동 생성

### GET /api/v1/cases/{case_id}

`CaseResponse` + `counselor`(사용자 객체) + `session_count` + `last_session_at`

오류: `404 CASE_NOT_FOUND`, `403 FORBIDDEN`

### PATCH /api/v1/cases/{case_id}

변경할 필드만 보낸다. `status` 로 사례를 종결(`CLOSED`)할 수 있다.

- `title`, `child_alias`, `status` 는 `null` 로 보낼 수 없다(`422 VALIDATION_ERROR`). 바꾸지 않을 필드는 빼고 보낸다
- `counselor_id` 변경은 **관리자만** 가능(`403 FORBIDDEN`). 없는 계정 · 정지된 계정은 위 `POST` 와 같다
  (`404 USER_NOT_FOUND`, `400 VALIDATION_ERROR`). 거절되면 담당자는 바뀌지 않는다
- 보호자 규칙은 저장된 값과 합쳐서 판단한다
  - 이미 `OTHER` 인 사례는 `guardian_note` 만 보내도 된다
  - `OTHER` 가 아닌 사례에 `guardian_note` 만 보내면 `422`
  - `guardian_type` 을 `OTHER` 가 아닌 값(또는 `null`)으로 바꾸면 기존 `guardian_note` 는 지워진다

### DELETE /api/v1/cases/{case_id} → 204

관리자 전용. Session 이하 데이터가 함께 삭제되고, 저장소의 음성 파일도 함께 삭제된다.

---

## 5. Sessions

### GET /api/v1/cases/{case_id}/sessions

Query: `page`(≤1,000,000), `page_size`(≤100), `status`
최신 회기(`session_number` 내림차순)부터 반환한다.
멈춘 처리 중 회기는 먼저 실패로 마감한 뒤 세고 거른다(1.4). 그래서 `status` 필터와 `meta.total` 도 마감 뒤 상태 기준이다.

### POST /api/v1/cases/{case_id}/sessions → 201

```json
{ "title": "1회기 상담", "consulted_at": null, "location": null, "memo": null }
```

`session_number` 는 Case 내에서 1부터 자동 증가한다. 요청 본문으로 지정할 수 없다.
같은 Case 에 회기를 동시에 만들어도 번호가 겹치지 않는다(겹치면 서버가 다시 계산한다).

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

- 큰 본문(`AUDIO_MAX_SIZE_MB` + 1MB 까지)은 서명 · 만료가 맞는 token 을 붙인 `multipart/form-data` 요청만 받는다.
  token 이 없거나 틀리거나 만료됐으면 본문을 해석하기 전에 `401 UNAUTHORIZED` 로 답한다. 문구는 다른 창구와 같고
  ("Authorization 헤더가 없습니다." · "유효하지 않은 토큰입니다." · "토큰이 만료되었습니다. 다시 로그인해 주세요."),
  본문 크기와 상관없다. 이때도 남은 본문은 버리며 읽은 뒤 답한다(최대 30초).
- 여기서는 token 의 서명 · 만료만 본다. 정지 · 강제 로그아웃 · 임시 비밀번호 상태는 본문을 받은 뒤 평소처럼 확인한다(3절).
- `multipart/form-data` 가 아닌 본문에는 음성 한도를 주지 않는다. urlencoded 본문은 일반 본문 한도
  (`REQUEST_MAX_BODY_MB`)를 쓰고, 그 밖의 형식(JSON · text 등)은 본문을 읽지 않고 크기와 상관없이 `401`(token 없음 ·
  틀림) 또는 `422`(`file` 없음)로 답한다(1.2).
- token 이 맞는 multipart 라도 파일이 아닌 칸 하나가 1MB 를 넘으면 `400 VALIDATION_ERROR`
  ("요청 형식이 올바르지 않습니다.", 1.2)다. 파일 칸에는 이 제한이 없다.

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
| `AUDIO_TOO_LARGE` | 400 | 크기 초과. token 이 맞는 요청의 본문 전체가 `AUDIO_MAX_SIZE_MB` + 1MB 를 넘으면 계정 상태 · 회기 확인보다 먼저 거절한다(token 이 없거나 틀리면 크기와 상관없이 `401`). 거절 전에 남은 본문을 읽어 버리므로(최대 30초) 개발 프록시(vite)를 거쳐도 이 응답이 온다 |
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
처음 변환(`AUDIO_UPLOADED`), 실패 뒤 재시도(`STT_FAILED`), 검수 중 다시 변환(`STT_REVIEW_REQUIRED`) 모두 받는다.

STT 가 발화를 하나도 찾지 못하면(무음 · 잡음만 있는 음성) 실패로 마감한다 — `STT_FAILED`, `error.code` `STT_FAILED`,
`error.message` "음성에서 발화를 찾지 못했습니다. …". 빈 전사본(version)은 만들지 않는다. 검수할 발화가 없는
`STT_REVIEW_REQUIRED` 로 두면 확정할 것도 없는 막다른 상태가 되기 때문이다. 다시 요청하거나 음성을 다시 올리면 된다.

```json
{
  "data": {
    "session_id": "uuid",
    "session_status": "STT_PROCESSING",
    "message": "STT 처리를 시작했습니다. 상태를 Polling 해 주세요."
  }
}
```

오류: `404 AUDIO_NOT_FOUND`(음성 미업로드), `409 INVALID_SESSION_STATE`(변환 중(`STT_PROCESSING`), 원문 확정 뒤(`STT_CONFIRMED` · `AI_PROCESSING` · `AI_REVIEW_REQUIRED` · `AI_FAILED` · `APPROVED`), 또는 동시에 들어온 같은 요청이 먼저 처리됨)

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
      "edited_segment_ids": [],
      "child_handoff": { "...": "아래 child_handoff 참고" }
    },
    "error": null
  }
}
```

**`segments` 는 STT Contract 와 완전히 동일하다.** segment 안에 필드를 추가하지 않는다.
상담사 수정 여부는 transcript level 의 `edited_segment_ids` 로 판단한다.

`speaker`: `COUNSELOR | CHILD | GUARDIAN | OTHER | UNKNOWN`
`source`: `STT | COUNSELOR_EDIT`

`confidence` 가 `0.0` 이면 **STT 공급자가 신뢰도를 주지 않았다는 뜻**이다(0% 가 아니다).
`STT_PROVIDER=module` 일 때 STT 모듈(`stt/`)의 기본 공급자인 ElevenLabs 결과는 모든 발화가 `0.0` 이며,
이 값은 저신뢰로 표시하지 않는다.
저신뢰 구간은 `0 < confidence < 0.7` 로 판단한다(Mock AI 의 저신뢰 경고와 같은 기준).
`edited_segment_ids` 에 포함된 segment 는 상담사가 확인했으므로 경고를 해제해도 된다.

#### child_handoff (아동 발화 인계 보기)

transcript level 칸이다. `segments` Contract 는 바뀌지 않는다.
저장하지 않고 응답할 때마다 그 version 의 `speaker` 로 다시 만들므로, 상담사가 화자를 고치면 다음 응답에 바로 반영된다.
GET 뿐 아니라 PATCH · confirm 응답(같은 Transcript 모양)에도 들어간다.

```json
{
  "child_handoff": {
    "child_analysis_text": "네, 안녕하세요. 요즘은 괜찮아요.",
    "confirmed_child_segments": [
      { "segment_id": "seg_002", "text": "네, 안녕하세요.", "start_ms": 2800, "end_ms": 5800 },
      { "segment_id": "seg_004", "text": "요즘은 괜찮아요.", "start_ms": 8400, "end_ms": 10900 }
    ],
    "review_needed_segments": [
      {
        "segment_id": "seg_008", "text": "화자 확인이 필요한 발화", "start_ms": 19600, "end_ms": 22600,
        "reason": "UNRESOLVED_SPEAKER"
      }
    ]
  }
}
```

- `confirmed_child_segments`: `speaker` 가 `CHILD` 인 발화. 시작 시각 순이다.
  문장이 있는 `CHILD` 발화가 하나도 없으면 빈 배열이다.
- `review_needed_segments`: `speaker` 가 `UNKNOWN` 이라 사람이 화자를 확인해야 하는 발화. 시작 시각 순이다.
  `reason` 은 지금 `UNRESOLVED_SPEAKER` 하나뿐이다. 모르는 값이 오면 그대로 보여 준다.
- `COUNSELOR` · `GUARDIAN` · `OTHER` 발화는 어느 쪽에도 들어가지 않는다.
- `child_analysis_text`: 문장이 있는 `CHILD` 발화를 시간 순으로 공백 하나로 이은 문장. 없으면 `""`.
- `child_handoff` 는 `null` 일 수 있다. Backend 가 STT 모듈(`stt/`)을 불러오지 못하는 배포(예: backend 폴더만 담은 이미지)에서는 비워서 준다.
- 분류 모델의 판단이 아니라 `speaker` 값을 옮겨 담은 참고용 보기다. 화자 확인은 상담사가 한다.

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
- 모든 segment 삭제는 불가(`409 VALIDATION_ERROR`)
- 시각이 거꾸로(`end_ms < start_ms`)이면 불가. 어디서 걸리느냐에 따라 응답이 다르다
  - 한 발화에 `start_ms` · `end_ms` 를 **둘 다** 보내 거꾸로면 요청 형식 오류 `422 VALIDATION_ERROR`(`details.fields`, `field` = `segments.N`)
  - **한쪽만** 보내 원래 값과 합친 결과가 거꾸로면 `409 VALIDATION_ERROR`(`details` 없이 `message` 만 온다)
- `confidence` 는 STT 값이므로 수정 대상이 아니다

응답은 새 `TranscriptResponse`. 확정 이후 수정하면 상태가 `STT_REVIEW_REQUIRED` 로 되돌아간다.

오류: `404 TRANSCRIPT_NOT_FOUND`(없는 segment_id 포함), `409 INVALID_SESSION_STATE`, `409 DUPLICATE_RESOURCE`(다른 요청이 같은 version 을 먼저 수정함 — 새로고침 후 다시 수정),
`409 VALIDATION_ERROR`(모든 segment 삭제, 한쪽만 보내 합친 뒤 시각 역전 — `details` 없이 `message` 만 온다), `422 VALIDATION_ERROR`(요청 형식 — 한 발화에 두 시각을 모두 보내 거꾸로인 경우 포함)

### POST /api/v1/sessions/{session_id}/transcript/confirm

Transcript 확정 → `STT_CONFIRMED`. AI 분석의 전제 조건이다.

오류: `404 TRANSCRIPT_NOT_FOUND`, `409 TRANSCRIPT_ALREADY_CONFIRMED`(이미 확정됨. 확정 검사는 상태 검사보다 먼저 한다), `409 INVALID_SESSION_STATE`(원문 검수 필요(`STT_REVIEW_REQUIRED`)가 아닌 상태 — 예: 재업로드 · 재변환 뒤 이전 전사본이 남은 채 `AUDIO_UPLOADED` · `STT_PROCESSING` · `STT_FAILED` 인 경우)

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

요청할 수 있는 상태(모두 `202`)
- `STT_CONFIRMED` — 첫 분석
- `AI_FAILED` — 재시도
- `AI_REVIEW_REQUIRED` — 재분석(아래 "재분석" 참고)

오류
- `404 TRANSCRIPT_NOT_FOUND` — Transcript 없음
- `409 TRANSCRIPT_NOT_CONFIRMED` — 확정 전. Transcript 검사는 상태 검사보다 먼저 한다
- `409 INVALID_SESSION_STATE` — 처리 중(`AI_PROCESSING`), 승인된 회기(`APPROVED`), 또는 동시에 들어온 같은 요청이 먼저 처리됨

#### 재분석 (`AI_REVIEW_REQUIRED` 에서 다시 요청)

- 새 분석을 만든다. `GET …/analysis` 는 가장 최근 분석을 주므로, 요청한 뒤로는 이전 결과를 API 로 다시 볼 수 없다
  (도는 동안에는 `status: "PROCESSING"` · `result: null`, 실패하면 `status: "FAILED"` 가 온다).
- 성공하면 `summary.analysis_id` 가 새 분석으로 바뀐다. 상담사가 고치지 않은 요약(`is_edited: false`)은
  새 결과로 바뀐다(`DRAFT`). 상담사가 고친 요약(`is_edited: true`)은 내용을 그대로 둔다(9절).
- 실패하면 Session 이 `AI_FAILED` 가 된다. 이때(재분석이 도는 동안도 같다)는 요약 수정 · 승인이
  `409 INVALID_SESSION_STATE` 로 막히고, 다시 요청(재시도)해 성공해야 풀린다.

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
  - 예외: `AI_PROVIDER=langgraph` 결과는 저장 전에 **근거 발화가 없는 위험 항목을 뺀다**
    (`05_RULES.md` §1 "근거(`segment_id`) 없는 위험 신호 생성" 금지).
    `risk_utterances` / `abuse_signals` / `risk_factors` 의 각 항목 중 `segment_id` · `segment_ids` 가
    비었거나 Transcript 에 없는 번호를 하나라도 가리키면 제외하고,
    `warnings` 에 `"segment 근거가 없는 신호 N건을 제외했습니다."` 를 덧붙인다. 필드 모양은 바뀌지 않는다.
    `abuse_signals` 중 `detected` 가 명시적으로 `false` 인 항목은 위험 신호가 아니므로 근거가 없어도 남긴다.
- `result.schema_version` 은 AI Output Contract 버전이다(지금 `"1.0"`). 성공한 분석의 `analysis.schema_version` 과 같다.
- `risk_utterances` / `abuse_signals` / `risk_factors` 는 **객체 배열**이다. 항목 구조는
  `I-SPOT_DOCS/docs/PROPOSAL_risk_fields.md` §7 의 합의를 기다리고 있어 Backend 는 항목 구조(키 목록)를 검증하지 않는다.
  다만 `langgraph` 결과는 위 근거 확인을 위해 `segment_id` · `segment_ids` · `detected` 를 본다.
  Frontend 는 키가 없을 수 있다고 보고 하나씩 확인하며 읽는다. 지금은 `mock` · `pipeline` · `langgraph` 모두 빈 배열을 준다.
- `summary_evidence` 는 요약 문장 ↔ 근거 발화(`segment_id`) 연결 정보다. 근거 발화 하이라이트에 사용한다.
- `analysis.status`: `PROCESSING | COMPLETED | FAILED`

AI 오류 코드: `AI_FAILED`, `AI_TIMEOUT`, `AI_INVALID_OUTPUT`, `AI_AUTH_ERROR`, `AI_QUOTA_ERROR`

AI 쪽에서 알 수 없는 예외가 나면 `error.message` 에는 고정 문구와 예외 종류 이름만 담는다
(예: `"AI 분석에 실패했습니다: RuntimeError"`). 예외 문구에 상담 발화가 섞일 수 있어서다.
자세한 내용은 서버 로그에 `session_id` 와 함께 남는다. `pipeline` · `langgraph` 모두 같다.

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

`summary_evidence` 는 `summary.analysis_id` 가 가리키는 분석(마지막으로 성공한 분석)의 근거 정보를 그대로 준다.
재분석이 도는 중이거나 실패해도 이전 근거는 사라지지 않는다.

- `key_point` 는 **AI 원본 요약 문장**이다. 상담사가 `key_points` 를 고쳐도 바뀌지 않으므로,
  요약 문장과 문자열 일치로 연결하지 않는다. 근거 발화 표시는 `segment_ids` 로 한다.
- 수정한 요약에서 재분석이 성공하면 요약 문장은 상담사 것 그대로, `summary_evidence` 는 새 분석 것이 된다.

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

> 수정한 Summary 는 AI 재분석으로 덮어써지지 않는다. 다만 `analysis_id` 와 `summary_evidence` 는
> 새 분석 것으로 바뀐다. 새 AI 결과는 `GET .../analysis` 로 확인한다(8절 "재분석").

### POST /api/v1/sessions/{session_id}/summary/approve

승인 → Summary `APPROVED`, Session `APPROVED`.

오류: `404 SUMMARY_NOT_FOUND`, `409 ALREADY_APPROVED`, `409 INVALID_SESSION_STATE`

---

## 10. Documents

상담사가 작성하는 상담 기록(상담일지 등) 문서다. 파일이 아니라 제목 · 본문 텍스트다.

| Method | Path | 설명 |
|---|---|---|
| GET | `/api/v1/sessions/{session_id}/documents` | 목록 |
| POST | `/api/v1/sessions/{session_id}/documents` | 생성 (201) |
| PATCH | `/api/v1/sessions/{session_id}/documents/{document_id}` | 수정 |
| POST | `/api/v1/sessions/{session_id}/documents/{document_id}/approve` | 승인 |

문서 하나를 조회하거나 삭제하는 API 는 없다(`405 METHOD_NOT_ALLOWED`). 하나를 볼 때도 목록에서 찾는다.

### 응답

생성 · 수정 · 승인은 문서 하나를 준다.

```json
{
  "data": {
    "id": "uuid",
    "session_id": "uuid",
    "doc_type": "CONSULTATION_RECORD",
    "title": "상담 기록",
    "content": "본문",
    "status": "DRAFT",
    "created_by_id": "uuid",
    "approved_by_id": null,
    "approved_at": null,
    "created_at": "...",
    "updated_at": "..."
  }
}
```

- 목록은 `data` 가 **문서 배열 그대로**다(`items` · `meta` 가 없다 — 1.1 의 예외). 페이지를 나누지 않고 `created_at` 오래된 순이다.
- `created_by_id` · `approved_by_id` 는 그 계정이 DB 에서 지워지면 `null` 로 비워진다(계정을 지우는 API 는 지금 없다). `approved_by_id` 는 승인 전에도 `null` 이다.

### 요청 규칙

```json
{ "title": "상담 기록", "content": "본문", "doc_type": "CONSULTATION_RECORD" }
```

| 칸 | 생성(POST) | 수정(PATCH) |
|---|---|---|
| `title` | 필수, 1~200자 | 선택, 1~200자 |
| `content` | 선택, 50000자 이하, 빼면 `""` | 선택, 50000자 이하 |
| `doc_type` | 선택, 50자 이하, 빼면 `CONSULTATION_RECORD` | 바꿀 수 없다(보내도 무시) |

- `doc_type` 은 정해진 값 목록이 아니라 자유 문자열이라 Backend 가 검사하지 않는다(빈 문자열도 받는다).
  지금 정해진 값은 `CONSULTATION_RECORD`(상담일지) 하나다.
- PATCH 는 `title` · `content` 중 최소 1개가 있어야 한다. 둘 다 없으면(예: `doc_type` 만 보냄) `422 VALIDATION_ERROR`.

### 상태 규칙

- 항상 `DRAFT` 로 만들어진다. 승인하면 `APPROVED` 가 되고 `approved_at` · `approved_by_id` 가 채워진다.
- 승인된 문서는 수정하거나 다시 승인할 수 없다(`409 ALREADY_APPROVED`).
- 회기 상태를 검사하지 않는다. 어느 상태(`CREATED` 포함)에서도 만들고 고치고 승인할 수 있다.
- 요약 승인(9절)과 따로 동작한다. 문서를 승인해도 회기 상태는 바뀌지 않고, 회기가 `APPROVED` 여도 문서는 만들고 고칠 수 있다.

오류: `403 FORBIDDEN`(담당이 아닌 사례), `404 SESSION_NOT_FOUND`, `404 DOCUMENT_NOT_FOUND`(없는 문서, 다른 회기의 문서),
`409 ALREADY_APPROVED`, `422 VALIDATION_ERROR`

---

## 11. Tasks (처리 대기 업무)

대시보드의 "나의 업무 목록"용. **사람이 처리할 차례인 Session** 을 오래 기다린 순서로 준다.
업무는 따로 저장하지 않고 Session 상태에서 계산한다.

| Session 상태 | `task_type` | 화면 이름 | 기다리기 시작한 시각 |
|---|---|---|---|
| `CREATED` | `UPLOAD_AUDIO` | 녹음 업로드 | 상담일(`consulted_at`), 없으면 생성 시각 |
| `AUDIO_UPLOADED` | `REQUEST_STT` | 원문 변환 요청 | 가장 최근 음성 업로드 시각 |
| `STT_REVIEW_REQUIRED` | `REVIEW_TRANSCRIPT` | 원문 검수 | STT 완료 시각 (확정한 원문을 다시 고친 경우 되돌린 시각) |
| `STT_CONFIRMED` | `REQUEST_ANALYSIS` | AI 분석 요청 | 원문 확정 시각 |
| `AI_REVIEW_REQUIRED` | `REVIEW_ANALYSIS` | 분석 결과 검토 | AI 완료 시각 |
| `STT_FAILED` | `RETRY_STT` | 원문 변환 재시도 | 실패 시각 |
| `AI_FAILED` | `RETRY_ANALYSIS` | AI 분석 재시도 | 실패 시각 |

- `REVIEW_TRANSCRIPT` 는 STT 완료 · 최근 확정 · 되돌린 시각 중 가장 늦은 값이다. 되돌린 시각은 확정 뒤
  처음 고친(`PATCH …/transcript`) 시각이다. 오래전에 확정한 원문을 오늘 다시 고치면 오늘부터 세고,
  되돌린 뒤 더 고쳐도 다시 세지 않는다.
- `REQUEST_ANALYSIS` 는 AI 실패 뒤 이 상태로 되돌아오면 실패 시각이 더 늦을 때 그것을 쓴다.
  상태 전이 규칙에만 있는 대비용이고, 지금은 이 경로로 가는 API 가 없다.
- 처리 중(`STT_PROCESSING`, `AI_PROCESSING`)과 `APPROVED` 는 업무가 아니다.
  처리 중에 멈춘 Session 은 조회할 때 실패로 마감되어 재시도 업무로 나온다(1.4 참고).
- **종결(`CLOSED`) 사례의 Session 과, 상담일이 아직 오지 않은 `CREATED` Session 은 뺀다.**
- 상담사는 담당 사례의 Session 만, 관리자는 전체를 본다.

### GET /api/v1/tasks

Query: `page`(≤1,000,000), `page_size`(≤100), `task_type`, `overdue_only`(`true`/`false`), `counselor_id`

- `counselor_id` 는 **관리자만** 쓸 수 있다. 상담사가 본인이 아닌 id 를 보내면 `403 FORBIDDEN`
- 모르는 `task_type` 이면 `422 VALIDATION_ERROR`
- 정렬: `waiting_since` 오래된 순, 같으면 `case_number` · `session_number` 순

```json
{
  "data": {
    "items": [
      {
        "session_id": "uuid",
        "case_id": "uuid",
        "case_number": "C-2026-0001",
        "child_alias": "아동_001",
        "session_number": 2,
        "session_title": "2회기 상담",
        "session_status": "STT_REVIEW_REQUIRED",
        "task_type": "REVIEW_TRANSCRIPT",
        "waiting_since": "2026-09-15T02:10:00Z",
        "is_overdue": true,
        "counselor_id": "uuid",
        "counselor_name": "이서연",
        "last_error_code": null
      }
    ],
    "meta": { "total": 1, "page": 1, "page_size": 20, "total_pages": 1 }
  }
}
```

- `waiting_since` 는 항상 UTC(`Z`)로 준다.
- `is_overdue` 는 `waiting_since` 로부터 `TASK_OVERDUE_HOURS`(기본 48시간)가 지났는지다.
  화면에는 **"지연"** 으로 표시한다. 위험 신호와 헷갈리지 않게 "긴급"이라고 쓰지 않고, 색만으로 구분하지 않는다.
- 아동은 `child_alias` 만 준다. 상담 원문은 주지 않는다.
- `last_error_code` 는 재시도 업무에만 값이 있다. 메시지는 `GET /api/v1/sessions/{session_id}` 의 `error` 에서 본다.

### GET /api/v1/tasks/summary

Query: `counselor_id` (목록과 같은 규칙)

```json
{
  "data": {
    "total": 5,
    "overdue": 3,
    "by_type": {
      "UPLOAD_AUDIO": 1, "REQUEST_STT": 0, "REVIEW_TRANSCRIPT": 1, "REQUEST_ANALYSIS": 0,
      "REVIEW_ANALYSIS": 2, "RETRY_STT": 1, "RETRY_ANALYSIS": 0
    }
  }
}
```

`by_type` 에는 업무 종류 7개가 **항상 모두** 들어 있다. 없는 종류는 `0` 이다.

---

## 12. Error Code 목록

| code | status | 설명 |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | 로그인 실패 (틀린 비밀번호 · 없는 계정 · 실패 잠금 모두 같다) |
| `INVALID_CURRENT_PASSWORD` | 400 | 비밀번호 변경 때 현재 비밀번호 불일치 (로그인 만료가 아니다. 반복되면 Token 이 끊겨 401 — 3절) |
| `UNAUTHORIZED` | 401 | 토큰 없음/만료/오류, 무효화된 토큰(비밀번호 변경 · 강제 로그아웃 · 역할 변경 · 정지 · 현재 비밀번호 반복 실패 — 대조하는 사이 끊긴 경우 포함) |
| `INACTIVE_USER` | 403 | 비활성 계정 — 정지된 계정의 로그인(비밀번호가 맞았을 때만), Token 버전을 올리지 않고 정지된 계정의 요청 |
| `ACCOUNT_LOCKED` | — | **감사 로그 전용.** 잠긴 계정의 로그인 시도가 LOGIN 실패의 `error_code` 로 남는다. 응답에는 쓰지 않는다 |
| `ACCOUNT_DORMANT` | 403 | 휴면 계정 (비밀번호가 맞았을 때만) |
| `TEMP_PASSWORD_EXPIRED` | 403 | 임시 비밀번호 사용 기간 경과 (비밀번호가 맞았을 때만) |
| `PASSWORD_CHANGE_REQUIRED` | 403 | 임시 비밀번호 상태에서 비밀번호 변경 외의 요청 |
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
| `VALIDATION_ERROR` | 422 | 입력값 오류 (`details.fields`). JSON 문법 오류도 여기다(로그인 확인 전, `field` 는 글자 위치, `reason` 은 "JSON decode error" — 1.2). 목록의 `page` · `page_size` 범위 밖(1.1) |
| `VALIDATION_ERROR` | 400 | `details` 없음 — form 본문을 해석할 수 없거나 form 제한을 넘음(예: multipart 의 boundary 없음, 파일이 아닌 칸 하나가 1MB 초과), JSON 본문에 UTF-8 로 읽을 수 없는 바이트가 있음(로그인 확인 전, 문법 오류는 422 — 1.2), 본문을 받는 창구에서 본문이 `REQUEST_MAX_BODY_MB` 를 넘음(로그인 확인 전, 음성 경로의 urlencoded 본문 포함, 1.2), 사례 담당자로 정지된 계정을 지정함(4절) |
| `VALIDATION_ERROR` | 409 | 지금 데이터 상태로는 할 수 없는 요청. `details` 없음 — 마지막 활성 관리자 비활성화 · 역할 변경, 자기 계정 `logout-all`, 전사본 PATCH 의 모든 segment 삭제 · 한쪽 시각만 보내 합친 뒤 시각 역전 |
| `WEAK_PASSWORD` | 422 | 비밀번호 규칙 위반 (`details.reasons`) |
| `SAME_PASSWORD` | 422 | 새 비밀번호가 현재 비밀번호와 같음 |
| `PASSWORD_REUSED` | 422 | 최근에 쓰던 비밀번호 (`PASSWORD_HISTORY_COUNT` 개) |
| `DUPLICATE_RESOURCE` | 409 | 중복 (이메일 / 사례번호 / 동시에 수정된 Transcript version) |
| `INVALID_SESSION_STATE` | 409 | 지금 회기 상태에서 할 수 없는 요청 (`details.current_status`, `details.expected_status` — 표 아래 참고) |
| `TRANSCRIPT_NOT_CONFIRMED` | 409 | 확정 전 AI 분석 요청 |
| `TRANSCRIPT_ALREADY_CONFIRMED` | 409 | 이미 확정됨 |
| `ALREADY_APPROVED` | 409 | 이미 승인됨 |
| `AUDIO_EMPTY_FILE` / `AUDIO_TOO_LARGE` / `AUDIO_UNSUPPORTED_TYPE` / `AUDIO_CORRUPTED` / `AUDIO_INVALID_FILENAME` / `AUDIO_STORAGE_ERROR` | 400 | 음성 검증 실패 (`AUDIO_TOO_LARGE` 는 token 이 맞는 요청이면 계정 상태 · 회기 확인보다 먼저 온다. token 이 없거나 틀리거나 만료됐으면 크기와 상관없이 `401` — 6절) |
| `STT_FAILED` / `STT_TIMEOUT` / `STT_INVALID_OUTPUT` | — | Session `error` 필드로 전달 |
| `AI_FAILED` / `AI_TIMEOUT` / `AI_INVALID_OUTPUT` / `AI_AUTH_ERROR` / `AI_QUOTA_ERROR` | — | Session `error` 필드로 전달 |
| `METHOD_NOT_ALLOWED` | 405 | 잘못된 method (`message` 는 "허용되지 않는 요청 방식입니다.") |
| `INTERNAL_ERROR` | 500 | 서버 오류 (5xx 에만 쓴다) |

`INVALID_SESSION_STATE` 의 `message` 는 한국어 상태 이름으로 쓰고 상태 코드를 넣지 않는다. 화면에는 그대로 보여 주면 된다.
예: `"지금 회기 상태(음성 업로드 대기)에서는 할 수 없는 요청입니다. 원문 검수 필요 · AI 분석 대기 상태에서만 할 수 있습니다."`
승인된 회기에서는 `"승인이 끝난 회기는 바꿀 수 없습니다."` 로 온다.

- `details.current_status` 는 지금 상태 코드다.
- `details.expected_status` 는 참고용 상태 코드 목록(`, ` 로 이음)이다. 요청에 따라 "이 요청을 할 수 있는 상태"이기도 하고
  "지금 상태에서 넘어갈 수 있는 상태"이기도 해서, "필요한 상태"로 읽지 않는다. 뒤쪽 뜻인데 넘어갈 수 있는 상태가 없으면(`APPROVED`) `없음` 이다.
- 동시에 들어온 요청과 겹친 경우 일부는 `details` 없이 `message` 만 온다.

---

## 13. 전체 Flow 예시

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

## 14. Contract 변경 요청

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
