# TASKS.md — Project Progress

이 문서는 현재 개발 상태만 관리한다.
기획이나 Contract를 중복 작성하지 않는다.

## 상태

```text
TODO
IN_PROGRESS
BLOCKED
REVIEW
DONE
```

## 현재 MVP

| ID | 영역 | Task | 담당 | 상태 | 의존 |
|---|---|---|---|---|---|
| BE-01 | Backend | 프로젝트/DB 기본 구조 | C | REVIEW | - |
| BE-02 | Backend | Case/Session API | C | REVIEW | BE-01 |
| FE-01 | Frontend | Case List/Detail | - | TODO | BE-02 |
| BE-03 | Backend | Audio 업로드 | C | REVIEW | BE-02 |
| FE-02 | Frontend | 상담 녹음 UI | - | TODO | FE-01 |
| AI-01 | AI | STT Adapter/Schema | - | TODO | BE-03 |
| FE-03 | Frontend | Transcript Review | - | TODO | AI-01 |
| AI-02 | AI | Summary/위험 발화 분석 | - | TODO | AI-01 |
| BE-04 | Backend | AI 결과 저장/조회 | C | REVIEW | AI-02 |
| FE-04 | Frontend | AI Review/Document Editor | - | TODO | BE-04 |
| BE-05 | Backend | Document 승인/Audit | C | REVIEW | FE-04 |
| BE-06 | Backend | 인증/권한 + Audit Log | C | REVIEW | BE-01 |
| BE-07 | Backend | STT/AI 연동 Adapter + Mock Provider | C | REVIEW | BE-03 |
| QA-01 | QA | 핵심 E2E Test | - | TODO | BE-05 |
| DEV-01 | Deploy | Docker/CI | C | REVIEW | BE-01 |
| DEV-02 | Deploy | Demo 배포 | - | TODO | QA-01 |

### Backend 진행 메모 (2026-09-01)

- BE-01~BE-07 은 구현 + `pytest` 통과 상태이며 팀 검토를 기다린다.
- STT/AI 는 `STT_PROVIDER` / `AI_PROVIDER` 환경변수로 `mock` ↔ 실제 Provider 를 전환한다.
  팀 A(AI-01) / 팀 B(AI-02) 산출물이 붙기 전에도 Frontend 통합이 가능하다.
- BE-04 는 팀 B 의 `run_analysis_pipeline` 호출 경로까지 구현했고,
  `AI_PROVIDER=pipeline` 으로 전환하면 실제 결과가 저장된다.
- Frontend 연동 규격은 `backend/docs/API_CONTRACT.md` 를 참조한다.
- DEV-01 은 `docker-compose.yml`(PostgreSQL + Backend)까지만 포함한다. CI 는 미포함.

## 작업 기록 규칙

Task 시작:
```text
TODO → IN_PROGRESS
```

다른 작업 때문에 진행 불가:
```text
IN_PROGRESS → BLOCKED
```

구현 완료 후 검토 필요:
```text
IN_PROGRESS → REVIEW
```

테스트/검토 완료:
```text
REVIEW → DONE
```

## 새 Task 추가 규칙

새 Task는 아래 정보만 기록한다.

```text
ID
영역
Task
담당
상태
의존 Task
```

세부 요구사항은 `docs/` 문서에 둔다.
