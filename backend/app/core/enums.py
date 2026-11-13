# I-SPOT Backend 공통 Enum.
# docs/02_ARCHITECTURE.md 의 공통 상태 / STT Contract / AI Output Contract 를 그대로 따른다.

from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    """
    사용자 권한. 계정은 관리자가 만들거나, 회원가입 신청을 관리자가 승인할 때 생긴다(2026-11-02).

    신청하는 사람은 역할을 고르지 않는다. 승인하는 관리자가 정한다.
    """

    COUNSELOR = "COUNSELOR"
    ADMIN = "ADMIN"


class SignupRequestStatus(str, Enum):
    """
    회원가입 대기 신청 상태(2026-11-02, API_CONTRACT 3절 '회원가입').

    PENDING 동안은 계정(users 행)이 없어 로그인할 수 없다. 관리자가 승인할 때만 계정이 생긴다.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SubjectType(str, Enum):
    """사례 대상 종류(2026-11-13, 고령자 건강상담 확장). 이 칸이 생기기 전 사례는 모두 CHILD 다."""

    CHILD = "CHILD"
    SENIOR = "SENIOR"


class LivingArrangement(str, Enum):
    """고령자 거주 형태(담당자가 고른다)."""

    ALONE = "ALONE"  # 혼자 산다
    COUPLE = "COUPLE"  # 배우자와 둘이
    WITH_FAMILY = "WITH_FAMILY"  # 자녀 등 가족과
    FACILITY = "FACILITY"  # 시설 · 공동생활
    OTHER = "OTHER"


class LongTermCareGrade(str, Enum):
    """노인장기요양 등급(담당자가 고른다). 받지 않았으면 NONE, 모르면 UNKNOWN."""

    GRADE_1 = "GRADE_1"
    GRADE_2 = "GRADE_2"
    GRADE_3 = "GRADE_3"
    GRADE_4 = "GRADE_4"
    GRADE_5 = "GRADE_5"
    COGNITIVE_SUPPORT = "COGNITIVE_SUPPORT"  # 인지지원등급
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class GlucoseTiming(str, Enum):
    """혈당을 잰 때. 공복 · 식후 값은 서로 비교하지 않는다(추이도 따로 낸다)."""

    FASTING = "FASTING"
    POST_MEAL = "POST_MEAL"
    RANDOM = "RANDOM"


class CaseStatus(str, Enum):
    """사례 상태. 종결은 상담사/관리자의 명시적 행위로만 발생한다."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class GuardianType(str, Enum):
    """
    아동의 보호자 유형.

    나중에 보호자 유형별 통계를 낼 수 있도록 목록으로 관리한다.
    목록에 없는 관계는 OTHER 로 두고 guardian_note 에 적는다.
    """

    PARENTS = "PARENTS"            # 부모
    FATHER = "FATHER"              # 부
    MOTHER = "MOTHER"              # 모
    GRANDPARENTS = "GRANDPARENTS"  # 조부모
    RELATIVE = "RELATIVE"          # 친인척
    FOSTER = "FOSTER"              # 위탁
    FACILITY = "FACILITY"          # 시설
    OTHER = "OTHER"                # 기타(guardian_note 에 직접 입력)


class SessionSource(str, Enum):
    """회차 자료(2026-11-02). AUDIO: 녹음 → 원문 검수 → AI 분석(1~4단계). DOCUMENT: 상담사가 쓴 상담 기록 문서를 올려
    3(상담 요약 · 상담 일지) · 4(다음 상담 준비)단계만 쓴다 — 음성 · 전사본 · AI 분석이 없다(API_CONTRACT 21절)."""

    AUDIO = "AUDIO"
    DOCUMENT = "DOCUMENT"


class ChildActionResult(str, Enum):
    """
    조치결과 · 피해아동(서식 4 ①, 2026-11-05).

    상담원이 고르는 값이다. AI 가 미리 고르거나 채우지 않는다.
    """

    HOME = "HOME"                  # 원가정보호
    RELATIVE = "RELATIVE"          # 친인척보호
    ACQUAINTANCE = "ACQUAINTANCE"  # 연고자에 의한 보호
    FOSTER = "FOSTER"              # 가정위탁
    FACILITY = "FACILITY"          # 시설입소
    HOSPITAL = "HOSPITAL"          # 병원입원
    OTHER = "OTHER"                # 기타


class TargetActionResult(str, Enum):
    """
    조치결과 · 사례관리대상자(서식 4 ①, 2026-11-05).

    상담원이 고르는 값이다. AI 가 미리 고르거나 채우지 않는다.
    """

    OBSERVATION = "OBSERVATION"  # 지속관찰
    SEPARATION = "SEPARATION"    # 아동과의 분리
    COMPLAINT = "COMPLAINT"      # 고소 · 고발
    OTHER = "OTHER"              # 기타


class FamilyType(str, Enum):
    """
    가족유형(서식 4 ② 초기면접 내용, 2026-11-05). 하나만 고른다. 11/03 디자인의 서식 항목 21개.

    상담원이 고르는 값이다. AI 가 미리 고르거나 채우지 않는다.
    """

    GENERAL = "GENERAL"                      # 일반가정
    FATHER_BEREAVED = "FATHER_BEREAVED"      # 부자가정(사별)
    FATHER_DIVORCED = "FATHER_DIVORCED"      # 부자가정(이혼)
    FATHER_LEFT = "FATHER_LEFT"              # 부자가정(가출)
    FATHER_SEPARATED = "FATHER_SEPARATED"    # 부자가정(별거)
    MOTHER_BEREAVED = "MOTHER_BEREAVED"      # 모자가정(사별)
    MOTHER_DIVORCED = "MOTHER_DIVORCED"      # 모자가정(이혼)
    MOTHER_LEFT = "MOTHER_LEFT"              # 모자가정(가출)
    MOTHER_SEPARATED = "MOTHER_SEPARATED"    # 모자가정(별거)
    UNMARRIED_FATHER = "UNMARRIED_FATHER"    # 미혼부가정
    UNMARRIED_MOTHER = "UNMARRIED_MOTHER"    # 미혼모가정
    UNMARRIED_PARENTS = "UNMARRIED_PARENTS"  # 미혼부모가정
    FATHER_STEPMOTHER = "FATHER_STEPMOTHER"  # 친부+계모
    MOTHER_STEPFATHER = "MOTHER_STEPFATHER"  # 친모+계부
    RELATIVE_CARE = "RELATIVE_CARE"          # 친인척보호
    FATHER_PARTNER = "FATHER_PARTNER"        # 친부+동거녀
    MOTHER_PARTNER = "MOTHER_PARTNER"        # 친모+동거남
    FOSTER = "FOSTER"                        # 가정위탁
    ADOPTIVE = "ADOPTIVE"                    # 입양가정
    FACILITY = "FACILITY"                    # 시설보호
    OTHER = "OTHER"                          # 기타


class SessionStatus(str, Enum):
    """
    상담 Session 상태.

    docs/02_ARCHITECTURE.md 공통 상태:
        CREATED
        → AUDIO_UPLOADED
        → STT_PROCESSING
        → STT_REVIEW_REQUIRED
        → STT_CONFIRMED
        → AI_PROCESSING
        → AI_REVIEW_REQUIRED
        → APPROVED

    ASSUMPTION:
    공통 문서는 "실패 시 재시도 가능한 상태/오류 정보를 유지한다"만 규정하고
    실패 상태 이름을 정의하지 않았다. MVP에서는 가장 단순하게
    STT_FAILED / AI_FAILED 두 상태를 추가하고, 재시도 시 각각
    AUDIO_UPLOADED / STT_CONFIRMED 로 되돌린다.
    """

    CREATED = "CREATED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    STT_PROCESSING = "STT_PROCESSING"
    STT_REVIEW_REQUIRED = "STT_REVIEW_REQUIRED"
    STT_CONFIRMED = "STT_CONFIRMED"
    AI_PROCESSING = "AI_PROCESSING"
    AI_REVIEW_REQUIRED = "AI_REVIEW_REQUIRED"
    APPROVED = "APPROVED"

    STT_FAILED = "STT_FAILED"
    AI_FAILED = "AI_FAILED"


class TaskType(str, Enum):
    """
    처리 대기 업무 종류. 사람이 처리할 차례인 Session 상태 하나에 하나씩 대응한다.

    업무는 따로 저장하지 않고 Session 상태에서 계산한다(task_service).
    """

    UPLOAD_AUDIO = "UPLOAD_AUDIO"            # CREATED — 녹음 업로드
    REQUEST_STT = "REQUEST_STT"              # AUDIO_UPLOADED — 원문 변환 요청
    REVIEW_TRANSCRIPT = "REVIEW_TRANSCRIPT"  # STT_REVIEW_REQUIRED — 원문 검수
    REQUEST_ANALYSIS = "REQUEST_ANALYSIS"    # STT_CONFIRMED — AI 분석 요청
    REVIEW_ANALYSIS = "REVIEW_ANALYSIS"      # AI_REVIEW_REQUIRED — 분석 결과 검토·승인
    RETRY_STT = "RETRY_STT"                  # STT_FAILED — 원문 변환 재시도
    RETRY_ANALYSIS = "RETRY_ANALYSIS"        # AI_FAILED — AI 분석 재시도


class Speaker(str, Enum):
    """STT Contract speaker Enum. 확실하지 않으면 UNKNOWN 을 사용한다."""

    COUNSELOR = "COUNSELOR"
    CHILD = "CHILD"
    GUARDIAN = "GUARDIAN"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TranscriptSource(str, Enum):
    """Transcript version 이 생성된 경로."""

    STT = "STT"
    COUNSELOR_EDIT = "COUNSELOR_EDIT"


class AnalysisStatus(str, Enum):
    """AI 분석 실행 상태."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DraftsStatus(str, Enum):
    """3 · 4단계 AI 초안(상담 요약 · 확인 메모 · 추가 질문 등) 상태(2026-11-04, PROPOSAL_analysis_signals_first.md).

    학대 신호 확인(2단계) 값을 먼저 저장하면(analysis COMPLETED) PENDING 이 되고, 나머지를 채우면 DONE,
    못 채우면 FAILED 다. 한 번에 저장한 분석(콜백 없음 · 이 칸이 생기기 전 분석)과 처리 중 · 실패한 분석은 DONE 이다.
    """

    PENDING = "PENDING"
    DONE = "DONE"
    FAILED = "FAILED"


class ReviewStatus(str, Enum):
    """
    상담사 검수 대상(Summary/Document) 상태.

    Human-in-the-loop 원칙(docs/05_RULES.md)에 따라
    AI 생성 결과는 항상 DRAFT 로 시작한다.
    """

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class AbuseType(str, Enum):
    """
    학대 유형 대분류. AI Output Contract 와 같은 영문 대문자 값이다(02_ARCHITECTURE.md).

    한글 이름은 화면과 AI 결과(severity_ratings[].major_type)에서만 쓴다.
    서로 바꿀 때는 abuse_type_label · abuse_type_from_label 을 쓴다.
    """

    PHYSICAL = "PHYSICAL"    # 신체학대
    EMOTIONAL = "EMOTIONAL"  # 정서학대
    SEXUAL = "SEXUAL"        # 성학대
    NEGLECT = "NEGLECT"      # 방임


_ABUSE_TYPE_LABELS = {
    AbuseType.PHYSICAL: "신체학대",
    AbuseType.EMOTIONAL: "정서학대",
    AbuseType.SEXUAL: "성학대",
    AbuseType.NEGLECT: "방임",
}


def abuse_type_label(abuse_type: AbuseType) -> str:
    """학대 유형의 한글 이름."""

    return _ABUSE_TYPE_LABELS[abuse_type]


def abuse_type_from_label(label: object) -> Optional[AbuseType]:
    """
    한글 이름(예: "신체학대") 이나 영문 값(예: "PHYSICAL")을 학대 유형으로 바꾼다.

    AI 결과는 지금 한글 이름으로 온다. 띄어쓰기("신체 학대")와 영문 대소문자는 가리지 않는다.
    모르는 값이나 문자열이 아닌 값은 None 이다.
    """

    if not isinstance(label, str):
        return None

    key = "".join(label.split())

    for abuse_type, name in _ABUSE_TYPE_LABELS.items():
        if key == name or key.upper() == abuse_type.value:
            return abuse_type

    return None


class RiskLevel(str, Enum):
    """
    상담원이 회차 전체 또는 학대 유형마다 내리는 위험도 판단(상 · 중 · 하).

    AI 가 제안하는 심각도(1~5)와 척도가 다르다. 둘을 대응시키는 규칙은 팀 결정 전이라
    따로 저장만 하고 서로 바꾸지 않는다.
    """

    HIGH = "HIGH"      # 상
    MEDIUM = "MEDIUM"  # 중
    LOW = "LOW"        # 하


class FollowupQuestionKind(str, Enum):
    """
    추가 질문 종류(2026-10-28, PROPOSAL_ai_suggestions_case_context.md §4 · §7 답 4 · 5).

    OPEN 은 아동이 한 말을 이어받는 열린 질문이다. BANK 는 검증된 질문 은행의 질문 자리로,
    은행이 생길 때까지 AI 가 내지 않는다(bank_code 와 함께 예약만 해 둔다).
    """

    OPEN = "OPEN"
    BANK = "BANK"


class ConsultationType(str, Enum):
    """상담 유형(2026-10-30, 10/29 디자인 녹음하기 창 · 상담 이력). 회차마다 하나, 비울 수 있다."""

    INITIAL = "INITIAL"  # 초기면담
    REGULAR = "REGULAR"  # 정기상담
    VISIT = "VISIT"  # 방문상담
    OFFICE = "OFFICE"  # 기관 면담
    PHONE = "PHONE"  # 전화상담


class FollowupQuestionSource(str, Enum):
    """승인한 추가 질문이 어디서 왔는가. AI 초안을 고쳐 승인해도 AI 다."""

    AI = "AI"
    COUNSELOR = "COUNSELOR"


class CaseFormType(str, Enum):
    """기관 서식 종류(2026-11-02, 탭 5 › 기관 서식 작성 디자인). 사례 단위로 차수마다 한 행을 쓴다."""

    # 사정기록지 안전영역(서식 6)
    SAFETY_ASSESSMENT = "SAFETY_ASSESSMENT"
    # 사례관리 점검표(서식 27)
    MANAGEMENT_CHECKLIST = "MANAGEMENT_CHECKLIST"
    # 아동학대 위험수준별 개입 사정 척도(참고자료 3 · 43문항)
    RISK_SCALE = "RISK_SCALE"
    # 축약형 가족관계 척도(참고자료 1 · 15문항)
    FAMILY_SCALE = "FAMILY_SCALE"


class ScheduleKind(str, Enum):
    """일정 종류(2026-11-02, 일정 디자인). 상담 일정(● 둥근 표시) · 개인 · 기관 일정(■ 네모 표시)."""

    CONSULT = "CONSULT"
    OTHER = "OTHER"


class ScheduleConsultType(str, Enum):
    """상담 일정의 상담 유형(디자인 일정 추가 창 그대로). 회차의 ConsultationType 과 따로 둔다('종결 상담' 이 있어서)."""

    REGULAR = "REGULAR"  # 정기상담
    INITIAL = "INITIAL"  # 초기면담
    VISIT = "VISIT"  # 방문상담
    PHONE = "PHONE"  # 전화상담
    CLOSING = "CLOSING"  # 종결 상담


class ScheduleCategory(str, Enum):
    """개인 · 기관 일정의 분류(디자인 그대로). INTAKE(최초접수)는 사례가 필수이고 처리 기한(3 · 7 · 30일)이 따라붙는다."""

    AGENCY_MEETING = "AGENCY_MEETING"  # 기관 회의
    CASE_MEETING = "CASE_MEETING"  # 사례회의(종결평가 회의 포함)
    INTAKE = "INTAKE"  # 최초접수
    SUPERVISION = "SUPERVISION"  # 슈퍼비전
    TRAINING = "TRAINING"  # 교육
    FIELD_WORK = "FIELD_WORK"  # 외근
    LEAVE = "LEAVE"  # 휴가
    ETC = "ETC"  # 기타


class AuditAction(str, Enum):
    """수정/승인 이력 추적용 Audit action."""

    CASE_CREATED = "CASE_CREATED"
    CHILD_APP_INVITED = "CHILD_APP_INVITED"
    CHILD_APP_ALERT_ACKED = "CHILD_APP_ALERT_ACKED"
    CHILD_APP_QUESTIONS_SENT = "CHILD_APP_QUESTIONS_SENT"
    CHILD_APP_AI_DRAFT_CREATED = "CHILD_APP_AI_DRAFT_CREATED"
    CHILD_APP_AI_DRAFT_EDITED = "CHILD_APP_AI_DRAFT_EDITED"
    CHILD_APP_QUESTION_WITHDRAWN = "CHILD_APP_QUESTION_WITHDRAWN"
    CHILD_APP_UNLINKED = "CHILD_APP_UNLINKED"
    CASE_UPDATED = "CASE_UPDATED"
    CLOSURE_REVIEW_REGISTERED = "CLOSURE_REVIEW_REGISTERED"
    CLOSURE_REVIEW_CANCELED = "CLOSURE_REVIEW_CANCELED"
    CLOSURE_SUMMARY_GENERATED = "CLOSURE_SUMMARY_GENERATED"
    CLOSURE_SUMMARY_UPDATED = "CLOSURE_SUMMARY_UPDATED"
    CASE_DELETED = "CASE_DELETED"
    # 개인 식별 정보(암호화한 실명 등, API_CONTRACT 4절 '개인 식별 정보'). 복호화해서 내준 열람도 남긴다.
    # detail 에는 칸 이름 · 사례 ID 만 넣고 값은 넣지 않는다. 목록은 조회 1번에 1줄(case_ids · count).
    CASE_PERSONAL_INFO_VIEWED = "CASE_PERSONAL_INFO_VIEWED"
    CASE_PERSONAL_INFO_UPDATED = "CASE_PERSONAL_INFO_UPDATED"
    CASE_LIST_PERSONAL_INFO_VIEWED = "CASE_LIST_PERSONAL_INFO_VIEWED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_UPDATED = "SESSION_UPDATED"
    SESSION_DELETED = "SESSION_DELETED"
    AUDIO_UPLOADED = "AUDIO_UPLOADED"
    STT_REQUESTED = "STT_REQUESTED"
    STT_COMPLETED = "STT_COMPLETED"
    STT_FAILED = "STT_FAILED"
    TRANSCRIPT_UPDATED = "TRANSCRIPT_UPDATED"
    TRANSCRIPT_CONFIRMED = "TRANSCRIPT_CONFIRMED"
    ANALYSIS_REQUESTED = "ANALYSIS_REQUESTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    # 3 · 4단계 AI 초안을 채움 · 못 채움(2026-11-04, 2단계를 먼저 저장한 분석만). detail 에는 수 · 오류 코드만 남긴다.
    ANALYSIS_DRAFTS_COMPLETED = "ANALYSIS_DRAFTS_COMPLETED"
    ANALYSIS_DRAFTS_FAILED = "ANALYSIS_DRAFTS_FAILED"
    SUMMARY_UPDATED = "SUMMARY_UPDATED"
    SUMMARY_APPROVED = "SUMMARY_APPROVED"
    DOCUMENT_CREATED = "DOCUMENT_CREATED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    DOCUMENT_APPROVED = "DOCUMENT_APPROVED"
    # 상담원 위험도 판단(유형별). detail 에는 유형과 단계 값만 남긴다(판단 이유 원문은 넣지 않는다).
    RISK_ASSESSMENT_CREATED = "RISK_ASSESSMENT_CREATED"
    RISK_ASSESSMENT_UPDATED = "RISK_ASSESSMENT_UPDATED"
    # 상담원 위험도 판단(회차 전체, 2026-10-29). detail 에는 단계 값과 ai_level 만 남긴다(판단 이유 원문은 넣지 않는다).
    OVERALL_RISK_ASSESSMENT_CREATED = "OVERALL_RISK_ASSESSMENT_CREATED"
    OVERALL_RISK_ASSESSMENT_UPDATED = "OVERALL_RISK_ASSESSMENT_UPDATED"
    # 법령 · 매뉴얼 AI 질문(17절, 2026-10-28). detail 에는 걸린 시간 · provider · 모델 · 근거 수만 남긴다(질문 원문은 넣지 않는다).
    # 실패는 status=FAILED + error_code 다.
    LAW_QA_ASKED = "LAW_QA_ASKED"
    # 승인한 추가 질문 목록 저장(18절, 2026-10-28). detail 에는 질문 수 · 출처별 수만 남긴다(질문 원문은 넣지 않는다).
    FOLLOWUP_QUESTIONS_UPDATED = "FOLLOWUP_QUESTIONS_UPDATED"
    FOLLOWUP_CHECKS_UPDATED = "FOLLOWUP_CHECKS_UPDATED"
    # 다음 상담 체크리스트 만들기 · 다시 만들기 요청(19절, 2026-10-30). detail 에는 provider · 시도 번호만 남긴다(문장은 넣지 않는다).
    FOLLOWUP_CHECKLIST_REQUESTED = "FOLLOWUP_CHECKLIST_REQUESTED"
    # 상담 기록 문서(2026-11-02). detail 에는 형식 · 글자 수 · 채운 칸 이름만 남긴다(문서 글은 넣지 않는다).
    SOURCE_DOCUMENT_UPLOADED = "SOURCE_DOCUMENT_UPLOADED"
    DOCUMENT_FOLLOWUPS_DRAFTED = "DOCUMENT_FOLLOWUPS_DRAFTED"
    # 일정(2026-11-02). detail 에는 종류 · 분류 · 바뀐 칸 이름만 남긴다(제목 · 장소 글은 넣지 않는다).
    SCHEDULE_CREATED = "SCHEDULE_CREATED"
    SCHEDULE_UPDATED = "SCHEDULE_UPDATED"
    SCHEDULE_DELETED = "SCHEDULE_DELETED"
    # 문서함(2026-11-05). detail 에는 파일 수 · 형식 · 크기 · 폴더 id 만(파일 이름 · 내용은 넣지 않는다).
    DOCBOX_FOLDER_CREATED = "DOCBOX_FOLDER_CREATED"
    DOCBOX_FILE_UPLOADED = "DOCBOX_FILE_UPLOADED"
    DOCBOX_FILE_MOVED = "DOCBOX_FILE_MOVED"
    DOCBOX_FILE_DOWNLOADED = "DOCBOX_FILE_DOWNLOADED"
    DOCBOX_FILE_DELETED = "DOCBOX_FILE_DELETED"
    # 기관 서식(2026-11-02). detail 에는 서식 종류 · 차수만 남긴다(칸 값 · 소견 글은 넣지 않는다).
    CASE_FORM_CREATED = "CASE_FORM_CREATED"
    CASE_FORM_UPDATED = "CASE_FORM_UPDATED"
    CASE_FORM_CONFIRMED = "CASE_FORM_CONFIRMED"
    # 고령자 건강상담(2026-11-13, API_CONTRACT 27절). detail 에는 칸 이름 · 측정 항목 이름만(값 · 메모 글은 넣지 않는다).
    SENIOR_PROFILE_UPDATED = "SENIOR_PROFILE_UPDATED"
    HEALTH_MEASUREMENT_CREATED = "HEALTH_MEASUREMENT_CREATED"
    HEALTH_MEASUREMENT_UPDATED = "HEALTH_MEASUREMENT_UPDATED"
    HEALTH_MEASUREMENT_DELETED = "HEALTH_MEASUREMENT_DELETED"
    SENIOR_BRIEF_GENERATED = "SENIOR_BRIEF_GENERATED"

    # 계정
    # 실패는 별도 action 이 아니라 status 칸으로 표현한다.
    LOGIN = "LOGIN"
    LOGOUT_ALL = "LOGOUT_ALL"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    PASSWORD_RESET = "PASSWORD_RESET"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_UNLOCKED = "ACCOUNT_UNLOCKED"
    ACCOUNT_DORMANT = "ACCOUNT_DORMANT"
    ACCOUNT_REACTIVATED = "ACCOUNT_REACTIVATED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    # 회원가입(2026-11-02, API_CONTRACT 3절 '회원가입'). detail 에 이메일 · 이름 · 인증번호 · 토큰은 넣지 않는다.
    # 인증번호를 만듦(메일 실패는 status=FAILURE · MAIL_SEND_FAILED) · 맞힘(살아 있는 번호를 틀리면 FAILURE).
    SIGNUP_CODE_SENT = "SIGNUP_CODE_SENT"
    SIGNUP_CODE_VERIFIED = "SIGNUP_CODE_VERIFIED"
    SIGNUP_REQUESTED = "SIGNUP_REQUESTED"
    SIGNUP_APPROVED = "SIGNUP_APPROVED"
    SIGNUP_REJECTED = "SIGNUP_REJECTED"


class ChildAppLinkStatus(str, Enum):
    """아이 앱 연결 상태. 행이 없으면 미연결이다."""

    INVITED = "INVITED"
    LINKED = "LINKED"


class ChildQuestionSetStatus(str, Enum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    REPLACED = "REPLACED"


class ChildAppEventKind(str, Enum):
    LINKED = "LINKED"
    UNLINKED = "UNLINKED"
    QUESTIONS_SENT = "QUESTIONS_SENT"
    ANSWERS = "ANSWERS"
    ALERT = "ALERT"


class ChildAnswerLevel(str, Enum):
    NONE = "NONE"
    SKIP = "SKIP"
    AMBER = "AMBER"
    RED = "RED"
