import { CASES } from "./cases";

export interface Session {
  id: string;
  caseId: string;
  date: string;
  time: string;
  sessionNumber: number;
  counselor: string;
  duration: string;
  type: "초기면담" | "정기상담" | "전화상담" | "방문상담";
  location: string;
  sttStatus: "처리중" | "검수필요" | "검수완료" | "분석완료";
  aiStatus: "대기중" | "분석중" | "검토필요" | "검토완료" | "승인완료";
  recordStatus: "미작성" | "작성중" | "작성완료" | "승인완료";
}

export interface AIAnalysis {
  id: string;
  sessionId: string;
  caseId: string;
  date: string;
  sessionNumber: number;
  status: "분석중" | "검토필요" | "검토중" | "수정됨" | "승인완료";
  signals: number;
  reviewedBy?: string;
  reviewedAt?: string;
  riskIndicators: string[];
  evidenceSpeeches: { text: string; timestamp: string; speaker: string }[];
  summary: string;
}

export interface Notification {
  id: string;
  type: "검토필요" | "고위험" | "업무" | "분석완료";
  title: string;
  body: string;
  time: string;
  read: boolean;
  link: string;
  caseId?: string;
}

// Helper dates
const DATES = [
  "2026-08-19", "2026-08-18", "2026-08-15", "2026-08-14",
  "2026-08-12", "2026-08-10", "2026-08-07", "2026-08-05",
  "2026-08-03", "2026-07-31",
];
const TIMES = ["09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00"];
const TYPES: Session["type"][] = ["초기면담", "정기상담", "전화상담", "방문상담"];
const LOCATIONS = ["면담실 A", "면담실 B", "전화", "가정 방문"];
const DURATIONS = ["30분", "45분", "50분", "60분"];

function buildSessions(): Session[] {
  const sessions: Session[] = [];

  CASES.forEach((c, caseIdx) => {
    const total = c.sessionCount;
    for (let i = 1; i <= total; i++) {
      const dateIdx = total - i;
      const date = DATES[Math.min(dateIdx, DATES.length - 1)];
      const isLast = i === total;

      // Top 3 cases have most recent session with검수필요/검토필요
      const isTopCase = ["C-2026-0412", "C-2026-0389", "C-2026-0351"].includes(c.id);
      let sttStatus: Session["sttStatus"];
      let aiStatus: Session["aiStatus"];
      let recordStatus: Session["recordStatus"];

      if (isLast && isTopCase) {
        sttStatus = "검수필요";
        aiStatus = "검토필요";
        recordStatus = "미작성";
      } else if (isLast) {
        sttStatus = "검수완료";
        aiStatus = "검토완료";
        recordStatus = "작성완료";
      } else {
        sttStatus = "분석완료";
        aiStatus = "승인완료";
        recordStatus = "승인완료";
      }

      const sessionId = `S-${c.id.slice(2)}-${String(i).padStart(2, "0")}`;

      sessions.push({
        id: sessionId,
        caseId: c.id,
        date,
        time: TIMES[(caseIdx + i) % TIMES.length],
        sessionNumber: i,
        counselor: c.counselor,
        duration: DURATIONS[(i + caseIdx) % DURATIONS.length],
        type: TYPES[(i + caseIdx) % TYPES.length],
        location: LOCATIONS[(i + caseIdx) % LOCATIONS.length],
        sttStatus,
        aiStatus,
        recordStatus,
      });
    }
  });

  return sessions;
}

export const SESSIONS: Session[] = buildSessions();

function buildAnalyses(): AIAnalysis[] {
  const analyses: AIAnalysis[] = [];

  SESSIONS.forEach((s, idx) => {
    if (s.sttStatus !== "검수완료" && s.sttStatus !== "분석완료") return;

    const c = CASES.find(c => c.id === s.caseId)!;
    const analysisId = `AI-${s.caseId.slice(2)}-${String(s.sessionNumber).padStart(2, "0")}`;

    let status: AIAnalysis["status"];
    if (s.aiStatus === "승인완료") status = "승인완료";
    else if (s.aiStatus === "검토완료") status = "수정됨";
    else status = "검토필요";

    analyses.push({
      id: analysisId,
      sessionId: s.id,
      caseId: s.caseId,
      date: s.date,
      sessionNumber: s.sessionNumber,
      status,
      signals: Math.floor((c.riskScore / 10) + idx % 4),
      reviewedBy: status === "승인완료" ? c.counselor : undefined,
      reviewedAt: status === "승인완료" ? s.date : undefined,
      riskIndicators: c.keywords.slice(0, 3),
      evidenceSpeeches: [
        { text: "소리 지르고 많이 때렸어요", timestamp: "00:41", speaker: "아동" },
        { text: "등이랑 팔이요. 말하면 더 혼난다고 했어요", timestamp: "01:08", speaker: "아동" },
      ],
      summary: `${c.childName} ${s.sessionNumber}회차 상담 AI 분석 결과. 위험 지표 ${Math.floor(c.riskScore / 10)}건 감지됨.`,
    });
  });

  return analyses;
}

export const AI_ANALYSES: AIAnalysis[] = buildAnalyses();

export const NOTIFICATIONS: Notification[] = [
  {
    id: "N-001",
    type: "검토필요",
    title: "STT 검수 완료",
    body: "김○○ (C-2026-0412) 6회차 STT 검수가 완료되었습니다.",
    time: "14분 전",
    read: false,
    link: "/cases/C-2026-0412/sessions",
    caseId: "C-2026-0412",
  },
  {
    id: "N-002",
    type: "고위험",
    title: "고위험 사례 알림",
    body: "이○○ (C-2026-0351) 고위험 신호가 감지되었습니다. 즉시 검토가 필요합니다.",
    time: "32분 전",
    read: false,
    link: "/cases/C-2026-0351",
    caseId: "C-2026-0351",
  },
  {
    id: "N-003",
    type: "업무",
    title: "업무 배정",
    body: "박○○ (C-2026-0389) 상담 일정이 배정되었습니다.",
    time: "1시간 전",
    read: false,
    link: "/cases/C-2026-0389/sessions",
    caseId: "C-2026-0389",
  },
  {
    id: "N-004",
    type: "분석완료",
    title: "AI 분석 완료",
    body: "김○○ (C-2026-0412) AI 분석이 완료되었습니다. 검토 후 승인해주세요.",
    time: "2시간 전",
    read: true,
    link: "/cases/C-2026-0412/analyses",
    caseId: "C-2026-0412",
  },
  {
    id: "N-005",
    type: "검토필요",
    title: "사례 검토 요청",
    body: "강○○ (C-2026-0312) 사례 종결 검토가 필요합니다.",
    time: "3시간 전",
    read: true,
    link: "/cases/C-2026-0312",
    caseId: "C-2026-0312",
  },
];
