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
| BE-01 | Backend | 프로젝트/DB 기본 구조 | - | TODO | - |
| BE-02 | Backend | Case/Session API | - | TODO | BE-01 |
| FE-01 | Frontend | Case List/Detail | - | TODO | BE-02 |
| BE-03 | Backend | Audio 업로드 | - | TODO | BE-02 |
| FE-02 | Frontend | 상담 녹음 UI | - | TODO | FE-01 |
| AI-01 | AI | STT Adapter/Schema | - | TODO | BE-03 |
| FE-03 | Frontend | Transcript Review | - | TODO | AI-01 |
| AI-02 | AI | Summary/위험 발화 분석 | - | TODO | AI-01 |
| BE-04 | Backend | AI 결과 저장/조회 | - | TODO | AI-02 |
| FE-04 | Frontend | AI Review/Document Editor | - | TODO | BE-04 |
| BE-05 | Backend | Document 승인/Audit | - | TODO | FE-04 |
| QA-01 | QA | 핵심 E2E Test | - | TODO | BE-05 |
| DEV-01 | Deploy | Docker/CI | - | TODO | BE-01 |
| DEV-02 | Deploy | Demo 배포 | - | TODO | QA-01 |

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
