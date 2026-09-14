import { useState, useMemo } from "react";
import { CASES, type RiskLevel, type AbuseType } from "../data/cases";

// ── Types ──────────────────────────────────────────────────────────────────
type AdminView =
  | "overview"
  | "cases"
  | "workqueue"
  | "approvals"
  | "accounts"
  | "access-log"
  | "security"
  | "notices"
  | "assignments";

// ── Mock data ──────────────────────────────────────────────────────────────
const COUNSELORS = [
  { id: "C001", name: "이서연", role: "상담사", status: "active",  lastLogin: "2026-08-21 09:14", caseCount: 6,  ip: "192.168.1.12" },
  { id: "C002", name: "박지훈", role: "상담사", status: "active",  lastLogin: "2026-08-21 08:52", caseCount: 4,  ip: "192.168.1.19" },
  { id: "C003", name: "최수민", role: "상담사", status: "inactive", lastLogin: "2026-08-14 14:30", caseCount: 0,  ip: "192.168.1.34" },
  { id: "C004", name: "정다은", role: "선임상담사", status: "active", lastLogin: "2026-08-21 09:01", caseCount: 7, ip: "192.168.1.8"  },
  { id: "C005", name: "한승호", role: "상담사", status: "active",  lastLogin: "2026-08-20 17:45", caseCount: 3,  ip: "192.168.1.22" },
];

const ACCESS_LOG = [
  { time: "2026-08-21 09:14", user: "이서연", role: "상담사",   ip: "192.168.1.12", result: "성공", ua: "Chrome 126" },
  { time: "2026-08-21 09:01", user: "정다은", role: "선임상담사", ip: "192.168.1.8",  result: "성공", ua: "Chrome 126" },
  { time: "2026-08-21 08:52", user: "박지훈", role: "상담사",   ip: "192.168.1.19", result: "성공", ua: "Firefox 128" },
  { time: "2026-08-21 08:47", user: "unknown", role: "-",       ip: "203.0.113.44", result: "실패", ua: "Python-requests/2.31" },
  { time: "2026-08-21 08:46", user: "unknown", role: "-",       ip: "203.0.113.44", result: "실패", ua: "Python-requests/2.31" },
  { time: "2026-08-21 08:45", user: "unknown", role: "-",       ip: "203.0.113.44", result: "실패", ua: "Python-requests/2.31" },
  { time: "2026-08-20 17:45", user: "한승호", role: "상담사",   ip: "192.168.1.22", result: "성공", ua: "Safari 17" },
  { time: "2026-08-20 16:02", user: "이서연", role: "상담사",   ip: "192.168.1.12", result: "성공", ua: "Chrome 126" },
  { time: "2026-08-20 14:30", user: "최수민", role: "상담사",   ip: "10.0.0.55",    result: "성공", ua: "Chrome 126" },
  { time: "2026-08-20 09:00", user: "김민준", role: "관리자",   ip: "192.168.1.2",  result: "성공", ua: "Chrome 126" },
];

const SECURITY_EVENTS = [
  { time: "2026-08-21 08:45~08:47", level: "high",  event: "연속 로그인 실패 3회", detail: "외부 IP(203.0.113.44)에서 반복 접속 시도 — 자동 차단 적용됨", action: "차단 완료" },
  { time: "2026-08-19 23:12",       level: "mid",   event: "비정상 접속 시간",    detail: "이서연 계정이 야간(23:00 이후)에 접속 시도", action: "알림 발송" },
  { time: "2026-08-18 14:05",       level: "low",   event: "비밀번호 변경",       detail: "박지훈 상담사가 비밀번호를 변경함", action: "기록 완료" },
  { time: "2026-08-15 09:30",       level: "low",   event: "신규 계정 생성",      detail: "한승호 (C005) 계정이 관리자에 의해 생성됨", action: "기록 완료" },
];

const WORK_QUEUE = {
  stt: [
    { caseId: "C-2026-0412", child: "김○○", counselor: "이서연", submitted: "2026-08-21 13:50", status: "처리중" },
    { caseId: "C-2026-0389", child: "최○○", counselor: "박지훈", submitted: "2026-08-21 11:20", status: "대기" },
    { caseId: "C-2026-0451", child: "황○○", counselor: "한승호", submitted: "2026-08-20 16:44", status: "오류" },
  ],
  aiReview: [
    { caseId: "C-2026-0351", child: "박○○", counselor: "정다은", submitted: "2026-08-21 10:05", status: "검토 대기" },
    { caseId: "C-2026-0277", child: "오○○", counselor: "이서연", submitted: "2026-08-20 14:30", status: "검토 대기" },
  ],
  approval: [
    { caseId: "C-2026-0312", child: "이○○", counselor: "정다은", docType: "상담일지",  submitted: "2026-08-21 09:40", status: "승인 대기" },
    { caseId: "C-2026-0389", child: "최○○", counselor: "박지훈", docType: "사정기록지", submitted: "2026-08-20 17:10", status: "승인 대기" },
    { caseId: "C-2026-0234", child: "정○○", counselor: "한승호", docType: "상담일지",  submitted: "2026-08-19 15:55", status: "반려됨" },
  ],
};

const NOTICES = [
  { id: 1, title: "2026년 9월 상담사 역량 강화 교육 안내",        author: "김민준",  date: "2026-08-20", active: true,  pinned: true },
  { id: 2, title: "아동학대 신고의무자 교육 이수 기한 안내 (9/30)", author: "김민준",  date: "2026-08-15", active: true,  pinned: true },
  { id: 3, title: "개인정보처리방침 개정 안내 (v2.4)",             author: "김민준",  date: "2026-08-10", active: true,  pinned: false },
  { id: 4, title: "시스템 점검 완료 안내 (8/7 03:00~05:00)",       author: "시스템",  date: "2026-08-07", active: false, pinned: false },
];

const UNASSIGNED_CASES = [
  { id: "C-2026-0501", child: "강○○", age: 9,  types: ["신체"] as AbuseType[],     risk: "high" as RiskLevel, received: "2026-08-21" },
  { id: "C-2026-0498", child: "임○○", age: 7,  types: ["방임"] as AbuseType[],     risk: "mid"  as RiskLevel, received: "2026-08-20" },
  { id: "C-2026-0495", child: "나○○", age: 12, types: ["정서", "방임"] as AbuseType[], risk: "mid" as RiskLevel, received: "2026-08-19" },
];

// ── Mini helpers ───────────────────────────────────────────────────────────
function RiskBadge({ level }: { level: RiskLevel }) {
  const cfg = {
    high: "bg-red-50 text-red-700 border-red-200",
    mid:  "bg-amber-50 text-amber-700 border-amber-200",
    low:  "bg-green-50 text-green-700 border-green-200",
  }[level];
  const label = { high: "고위험", mid: "중위험", low: "저위험" }[level];
  return <span className={`px-2 py-0.5 rounded text-xs font-medium border ${cfg}`}>{label}</span>;
}

function AbuseBadge({ type }: { type: AbuseType }) {
  const cls: Record<AbuseType, string> = {
    "신체": "bg-red-100 text-red-800",
    "정서": "bg-purple-100 text-purple-800",
    "성": "bg-orange-100 text-orange-800",
    "방임": "bg-slate-100 text-slate-700",
  };
  return <span className={`px-1.5 py-0.5 rounded text-[11px] font-medium ${cls[type]}`}>{type}</span>;
}

function StatusDot({ active }: { active: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${active ? "text-green-700" : "text-slate-400"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-green-500" : "bg-slate-300"}`} />
      {active ? "활성" : "비활성"}
    </span>
  );
}

// ── Section: 관리자 대시보드 ────────────────────────────────────────────────
function AdminOverview({ onNavigate }: { onNavigate: (v: AdminView) => void }) {
  const highRisk   = CASES.filter(c => c.riskLevel === "high").length;
  const pendingAll = WORK_QUEUE.stt.length + WORK_QUEUE.aiReview.length + WORK_QUEUE.approval.length;

  const urgent = [
    { label: "외부 IP 반복 로그인 실패 감지", tag: "보안", color: "text-red-700 bg-red-50 border-red-200",    view: "security" as AdminView },
    { label: `고위험 사례 ${highRisk}건 집중 모니터링 필요`, tag: "사례", color: "text-amber-700 bg-amber-50 border-amber-200", view: "cases" as AdminView },
    { label: `문서 승인 대기 ${WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length}건`,             tag: "승인", color: "text-blue-700 bg-blue-50 border-blue-200",  view: "approvals" as AdminView },
    { label: `미배정 신규 사례 ${UNASSIGNED_CASES.length}건`,                                                   tag: "배정", color: "text-purple-700 bg-purple-50 border-purple-200", view: "assignments" as AdminView },
  ];

  return (
    <div className="p-7 space-y-6 max-w-6xl">
      <div>
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-2xl font-bold text-slate-900">관리자 대시보드</h1>
          <span className="px-2 py-0.5 bg-[#E8EFF6] text-[#15314A] text-xs font-semibold rounded border border-[#D1DCE8]">관리자</span>
        </div>
        <p className="text-slate-500 text-sm">2026년 8월 21일 목요일 · 김민준 관리자 · 전체 현황 요약</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "전체 관리 사례", value: String(CASES.length),          sub: `고위험 ${highRisk}건 포함`,   color: "text-slate-900",  icon: "📁" },
          { label: "처리 대기 업무", value: String(pendingAll),             sub: "STT·AI검토·승인 합산",       color: "text-amber-700",  icon: "⏳" },
          { label: "활성 상담사",    value: String(COUNSELORS.filter(c => c.status === "active").length), sub: `전체 ${COUNSELORS.length}명 중`, color: "text-green-700",  icon: "👤" },
          { label: "미배정 사례",    value: String(UNASSIGNED_CASES.length), sub: "즉시 배정 필요",            color: "text-[#2563EB]", icon: "📋" },
        ].map(c => (
          <div key={c.label} className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 mb-2">{c.label}</p>
                <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
                <p className="text-xs text-slate-400 mt-1">{c.sub}</p>
              </div>
              <span className="text-2xl">{c.icon}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 bg-white rounded-[8px] border border-[#E2E8F0]">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">즉시 확인 필요</h2>
          </div>
          <div className="divide-y divide-slate-50">
            {urgent.map((u, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3.5 hover:bg-slate-50 transition-colors">
                <span className={`shrink-0 px-2 py-0.5 rounded text-[11px] font-semibold border ${u.color}`}>{u.tag}</span>
                <span className="text-sm text-slate-800 flex-1">{u.label}</span>
                <button onClick={() => onNavigate(u.view)} className="shrink-0 text-xs text-blue-600 font-medium hover:text-blue-800 transition-colors">바로가기</button>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-[8px] border border-[#E2E8F0]">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="font-semibold text-slate-900">최근 접속 활동</h2>
          </div>
          <div className="divide-y divide-slate-50">
            {ACCESS_LOG.slice(0, 5).map((log, i) => (
              <div key={i} className="px-5 py-2.5">
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-medium ${log.result === "실패" ? "text-red-700" : "text-slate-800"}`}>{log.user}</span>
                  <span className={`text-[11px] font-semibold px-1.5 py-0.5 rounded ${log.result === "성공" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{log.result}</span>
                </div>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5">{log.time} · {log.ip}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Section: 전체 사례 현황 ────────────────────────────────────────────────
function AllCasesView() {
  const [counselorFilter, setCounselorFilter] = useState("전체");
  const [riskFilter, setRiskFilter] = useState<RiskLevel | "전체">("전체");
  const [query, setQuery] = useState("");

  const counselorNames = ["전체", ...Array.from(new Set(CASES.map(c => c.counselor)))];

  const filtered = useMemo(() => CASES.filter(c => {
    if (counselorFilter !== "전체" && c.counselor !== counselorFilter) return false;
    if (riskFilter !== "전체" && c.riskLevel !== riskFilter) return false;
    if (query && !c.childName.includes(query) && !c.id.includes(query)) return false;
    return true;
  }).sort((a, b) => b.riskScore - a.riskScore), [counselorFilter, riskFilter, query]);

  return (
    <div className="p-7 space-y-5 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">전체 사례 현황</h1>
        <p className="text-slate-500 text-sm mt-0.5">기관 전체 사례 조회 · 담당자 변경 및 현황 확인</p>
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5 flex items-center gap-4 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="아동명·사례ID 검색" className="w-full pl-8 pr-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]" />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-500">담당자</span>
          <select value={counselorFilter} onChange={e => setCounselorFilter(e.target.value)} className="px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]">
            {counselorNames.map(n => <option key={n}>{n}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          {(["전체", "high", "mid", "low"] as const).map(r => {
            const labels = { "전체": "전체", high: "고위험", mid: "중위험", low: "저위험" };
            return (
              <button key={r} onClick={() => setRiskFilter(r)}
                className={`px-3 py-1.5 rounded text-xs font-medium border transition-all ${riskFilter === r ? "bg-[#172033] text-white border-[#172033]" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
              >
                {labels[r]}
              </button>
            );
          })}
        </div>
        <span className="ml-auto text-xs text-slate-400 font-medium">{filtered.length}건</span>
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "연령", "학대유형", "위험도", "담당 상담사", "최근 상담", "상태", ""].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {filtered.map(c => (
              <tr key={c.id} className={`hover:bg-slate-50 transition-colors ${c.riskLevel === "high" ? "border-l-2 border-l-red-400" : ""}`}>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{c.id}</td>
                <td className="px-4 py-3 font-semibold text-slate-900 text-sm">{c.childName}</td>
                <td className="px-4 py-3 text-sm text-slate-600">{c.age}세</td>
                <td className="px-4 py-3"><div className="flex gap-1">{c.abuseTypes.map(t => <AbuseBadge key={t} type={t} />)}</div></td>
                <td className="px-4 py-3"><RiskBadge level={c.riskLevel} /></td>
                <td className="px-4 py-3 text-sm text-slate-700 font-medium">{c.counselor}</td>
                <td className="px-4 py-3 text-xs text-slate-500 font-mono">{c.lastSession}</td>
                <td className="px-4 py-3">
                  <span className={{active:"bg-blue-50 text-blue-700", pending:"bg-slate-100 text-slate-600", review:"bg-amber-50 text-amber-700"}[c.status] + " px-2 py-0.5 rounded text-xs font-medium"}>
                    {{active:"진행중", pending:"대기중", review:"검토필요"}[c.status]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button className="text-xs text-[#2563EB] hover:text-[#1d4ed8] font-medium transition-colors">담당자 변경</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Section: 업무 처리 현황 ────────────────────────────────────────────────
function WorkQueueView() {
  const [tab, setTab] = useState<"stt" | "aiReview" | "approval">("stt");

  const tabCfg = [
    { id: "stt" as const,      label: "STT 처리 대기",   count: WORK_QUEUE.stt.length },
    { id: "aiReview" as const, label: "AI 검토 대기",    count: WORK_QUEUE.aiReview.length },
    { id: "approval" as const, label: "문서 승인 대기",  count: WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length },
  ];

  const sttStatusCfg: Record<string, string> = {
    "처리중": "bg-blue-50 text-blue-700",
    "대기":   "bg-slate-100 text-slate-600",
    "오류":   "bg-red-50 text-red-700",
  };

  return (
    <div className="p-7 space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">업무 처리 현황</h1>
        <p className="text-slate-500 text-sm mt-0.5">STT 변환 · AI 검토 · 문서 승인 처리 대기 현황</p>
      </div>

      <div className="flex gap-2">
        {tabCfg.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-[8px] text-sm font-medium border transition-all ${tab === t.id ? "bg-[#15314A] text-white border-[#15314A]" : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
          >
            {t.label}
            <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-full ${tab === t.id ? "bg-white/20 text-white" : "bg-slate-100 text-slate-600"}`}>{t.count}</span>
          </button>
        ))}
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        {tab === "stt" && (
          <table className="w-full">
            <thead><tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "담당 상담사", "제출 시각", "상태", ""].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.stt.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-5 py-3.5 text-sm text-slate-700">{row.counselor}</td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className="px-5 py-3.5"><span className={`px-2 py-0.5 rounded text-xs font-medium ${sttStatusCfg[row.status]}`}>{row.status}</span></td>
                  <td className="px-5 py-3.5">
                    {row.status === "오류" && <button className="text-xs text-red-600 hover:text-red-800 font-medium">재처리 요청</button>}
                    {row.status !== "오류" && <button className="text-xs text-slate-400 font-medium">상세보기</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "aiReview" && (
          <table className="w-full">
            <thead><tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "담당 상담사", "검토 요청 시각", ""].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.aiReview.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-5 py-3.5 text-sm text-slate-700">{row.counselor}</td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className="px-5 py-3.5"><button className="text-xs text-[#2563EB] hover:text-[#1d4ed8] font-medium">검토 독려</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "approval" && (
          <table className="w-full">
            <thead><tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "문서 유형", "담당 상담사", "제출 시각", "상태", ""].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.approval.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-5 py-3.5"><span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-xs font-medium">{row.docType}</span></td>
                  <td className="px-5 py-3.5 text-sm text-slate-700">{row.counselor}</td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className="px-5 py-3.5">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${row.status === "승인 대기" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-red-700"}`}>{row.status}</span>
                  </td>
                  <td className="px-5 py-3.5">
                    {row.status === "승인 대기" && (
                      <div className="flex gap-2">
                        <button className="text-xs text-green-700 hover:text-green-900 font-medium">승인</button>
                        <button className="text-xs text-red-600 hover:text-red-800 font-medium">반려</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Section: 상담사 계정 관리 ───────────────────────────────────────────────
function AccountsView() {
  const [accounts, setAccounts] = useState(COUNSELORS);

  function toggleStatus(id: string) {
    setAccounts(prev => prev.map(a => a.id === id ? { ...a, status: a.status === "active" ? "inactive" : "active" } : a));
  }

  return (
    <div className="p-7 space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">상담사 계정 관리</h1>
          <p className="text-slate-500 text-sm mt-0.5">계정 활성화·비활성화 · 비밀번호 초기화 · 신규 계정 생성</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-[#15314A] text-white text-sm font-semibold rounded-lg hover:bg-[#0F263B] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          신규 계정 생성
        </button>
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["계정 ID", "이름", "직급", "담당 사례", "최근 접속", "접속 IP", "상태", ""].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {accounts.map(a => (
              <tr key={a.id} className={`transition-colors ${a.status === "inactive" ? "bg-slate-50/60 opacity-70" : "hover:bg-slate-50"}`}>
                <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{a.id}</td>
                <td className="px-5 py-3.5 font-semibold text-slate-900">{a.name}</td>
                <td className="px-5 py-3.5 text-sm text-slate-600">{a.role}</td>
                <td className="px-5 py-3.5 text-sm text-slate-700">{a.caseCount}건</td>
                <td className="px-5 py-3.5 text-xs text-slate-500 font-mono">{a.lastLogin}</td>
                <td className="px-5 py-3.5 text-xs text-slate-400 font-mono">{a.ip}</td>
                <td className="px-5 py-3.5"><StatusDot active={a.status === "active"} /></td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <button onClick={() => toggleStatus(a.id)} className={`text-xs font-medium transition-colors ${a.status === "active" ? "text-amber-600 hover:text-amber-800" : "text-green-600 hover:text-green-800"}`}>
                      {a.status === "active" ? "비활성화" : "활성화"}
                    </button>
                    <button className="text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors">비밀번호 초기화</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Section: 접속 기록 ────────────────────────────────────────────────────
function AccessLogView() {
  const [filter, setFilter] = useState<"전체" | "성공" | "실패">("전체");
  const rows = filter === "전체" ? ACCESS_LOG : ACCESS_LOG.filter(r => r.result === filter);

  return (
    <div className="p-7 space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">접속 기록</h1>
        <p className="text-slate-500 text-sm mt-0.5">최근 시스템 접속 이력 · 이상 접속 감지</p>
      </div>
      <div className="flex gap-2">
        {(["전체", "성공", "실패"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-4 py-1.5 rounded text-xs font-medium border transition-all ${filter === f ? "bg-[#172033] text-white border-[#172033]" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
          >
            {f}
          </button>
        ))}
        <span className="ml-auto text-xs text-slate-400 self-center">{rows.length}건</span>
      </div>
      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["접속 시각", "사용자", "직급", "IP 주소", "브라우저", "결과"].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((log, i) => (
              <tr key={i} className={`transition-colors ${log.result === "실패" ? "bg-red-50/40 hover:bg-red-50" : "hover:bg-slate-50"}`}>
                <td className="px-5 py-3 text-xs text-slate-500 font-mono">{log.time}</td>
                <td className="px-5 py-3 font-semibold text-sm text-slate-900">{log.user}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{log.role}</td>
                <td className="px-5 py-3 text-xs text-slate-500 font-mono">{log.ip}</td>
                <td className="px-5 py-3 text-xs text-slate-400">{log.ua}</td>
                <td className="px-5 py-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold ${log.result === "성공" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>{log.result}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Section: 보안 이벤트 ──────────────────────────────────────────────────
function SecurityView() {
  const levelCfg: Record<string, { bg: string; badge: string; label: string }> = {
    high: { bg: "border-l-red-500 bg-red-50/30",     badge: "bg-red-100 text-red-700",    label: "높음" },
    mid:  { bg: "border-l-amber-500 bg-amber-50/30", badge: "bg-amber-100 text-amber-700", label: "중간" },
    low:  { bg: "border-l-slate-300 bg-white",       badge: "bg-slate-100 text-slate-600", label: "낮음" },
  };

  return (
    <div className="p-7 space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">보안 이벤트</h1>
        <p className="text-slate-500 text-sm mt-0.5">비정상 접속·보안 위협 감지 기록</p>
      </div>
      <div className="space-y-3">
        {SECURITY_EVENTS.map((ev, i) => {
          const cfg = levelCfg[ev.level];
          return (
            <div key={i} className={`bg-white rounded-[8px] border-[#E2E8F0] border border-l-4 ${cfg.bg} p-5`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${cfg.badge}`}>심각도 {cfg.label}</span>
                    <span className="font-semibold text-slate-900 text-sm">{ev.event}</span>
                  </div>
                  <p className="text-sm text-slate-600 leading-relaxed">{ev.detail}</p>
                  <p className="text-[11px] text-slate-400 font-mono mt-2">{ev.time}</p>
                </div>
                <div className="shrink-0 text-right">
                  <span className="text-xs font-medium text-slate-500 bg-slate-100 px-3 py-1 rounded">{ev.action}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="bg-slate-50 border border-[#E2E8F0] rounded-[8px] p-5">
        <p className="text-sm font-semibold text-slate-700 mb-1">IP 차단 관리</p>
        <div className="flex items-center gap-3 mt-2">
          <span className="px-3 py-1.5 bg-red-50 border border-red-200 rounded text-xs font-mono text-red-700">203.0.113.44 — 차단됨</span>
          <button className="text-xs text-red-600 hover:text-red-800 font-medium transition-colors">차단 해제</button>
          <span className="text-xs text-slate-400">자동 차단 후 24시간 유지</span>
        </div>
      </div>
    </div>
  );
}

// ── Section: 공지사항 관리 ────────────────────────────────────────────────
function NoticesView() {
  const [notices, setNotices] = useState(NOTICES);
  const [composing, setComposing] = useState(false);
  const [draft, setDraft] = useState("");

  function toggleActive(id: number) {
    setNotices(prev => prev.map(n => n.id === id ? { ...n, active: !n.active } : n));
  }

  function publish() {
    if (!draft.trim()) return;
    setNotices(prev => [{ id: Date.now(), title: draft, author: "김민준", date: "2026-08-21", active: true, pinned: false }, ...prev]);
    setDraft("");
    setComposing(false);
  }

  return (
    <div className="p-7 space-y-5 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">공지사항 관리</h1>
          <p className="text-slate-500 text-sm mt-0.5">상담사 공지 작성·게시·관리</p>
        </div>
        <button onClick={() => setComposing(v => !v)} className="flex items-center gap-2 px-4 py-2 bg-[#15314A] text-white text-sm font-semibold rounded-lg hover:bg-[#0F263B] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          새 공지 작성
        </button>
      </div>

      {composing && (
        <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5 space-y-3">
          <p className="text-sm font-semibold text-slate-700">새 공지 작성</p>
          <input value={draft} onChange={e => setDraft(e.target.value)} placeholder="공지 제목을 입력하세요..." className="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]" />
          <div className="flex gap-2">
            <button onClick={publish} className="px-4 py-2 bg-[#15314A] text-white text-sm font-semibold rounded-lg hover:bg-[#0F263B] transition-colors">게시</button>
            <button onClick={() => { setComposing(false); setDraft(""); }} className="px-4 py-2 border border-slate-200 text-slate-600 text-sm rounded-lg hover:bg-slate-50 transition-colors">취소</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        <div className="px-5 py-3 bg-slate-50 border-b border-slate-100">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">전체 {notices.length}건</span>
        </div>
        <div className="divide-y divide-slate-100">
          {notices.map(n => (
            <div key={n.id} className={`flex items-center gap-4 px-5 py-3.5 ${!n.active ? "opacity-50" : "hover:bg-slate-50"} transition-colors`}>
              {n.pinned && <span className="text-amber-500 shrink-0" title="고정">📌</span>}
              {!n.pinned && <span className="w-4 shrink-0" />}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{n.title}</p>
                <p className="text-[11px] text-slate-400 mt-0.5">{n.author} · {n.date}</p>
              </div>
              <span className={`shrink-0 text-xs px-2 py-0.5 rounded font-medium ${n.active ? "bg-green-50 text-green-700" : "bg-slate-100 text-slate-500"}`}>{n.active ? "게시중" : "숨김"}</span>
              <div className="flex gap-2 shrink-0">
                <button onClick={() => toggleActive(n.id)} className="text-xs text-slate-500 hover:text-slate-700 font-medium transition-colors">{n.active ? "숨기기" : "게시"}</button>
                <button className="text-xs text-red-400 hover:text-red-600 font-medium transition-colors">삭제</button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Section: 업무 배정 ────────────────────────────────────────────────────
function AssignmentsView() {
  const [assigned, setAssigned] = useState<Record<string, string>>({});

  const activeCounselors = COUNSELORS.filter(c => c.status === "active");

  function assign(caseId: string, counselorName: string) {
    setAssigned(prev => ({ ...prev, [caseId]: counselorName }));
  }

  return (
    <div className="p-7 space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">업무 배정</h1>
        <p className="text-slate-500 text-sm mt-0.5">미배정 신규 사례에 담당 상담사를 배정합니다</p>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-2">
        {activeCounselors.map(c => (
          <div key={c.id} className="bg-white rounded-[8px] border border-[#E2E8F0] p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full bg-[#E8EFF6] flex items-center justify-center text-[#15314A] text-sm font-bold shrink-0">{c.name[0]}</div>
              <div>
                <p className="text-sm font-semibold text-slate-900">{c.name}</p>
                <p className="text-[11px] text-slate-500">{c.role}</p>
              </div>
            </div>
            <div className="text-[11px] text-slate-500">현재 담당: <span className="font-semibold text-slate-700">{c.caseCount}건</span></div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900 text-sm">미배정 사례 ({UNASSIGNED_CASES.length}건)</h2>
        </div>
        <div className="divide-y divide-slate-100">
          {UNASSIGNED_CASES.map(uc => (
            <div key={uc.id} className="flex items-center gap-5 px-5 py-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-slate-900">{uc.child}</span>
                  <span className="text-slate-400 text-xs">({uc.age}세)</span>
                  <RiskBadge level={uc.risk} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">{uc.id}</span>
                  <span className="text-slate-300">·</span>
                  <div className="flex gap-1">{uc.types.map(t => <AbuseBadge key={t} type={t} />)}</div>
                  <span className="text-slate-300">·</span>
                  <span className="text-xs text-slate-400">접수일 {uc.received}</span>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {assigned[uc.id] ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-lg">✓ {assigned[uc.id]} 배정 완료</span>
                    <button onClick={() => setAssigned(p => { const n = { ...p }; delete n[uc.id]; return n; })} className="text-xs text-slate-400 hover:text-slate-600 transition-colors">취소</button>
                  </div>
                ) : (
                  <select onChange={e => e.target.value && assign(uc.id, e.target.value)} defaultValue=""
                    className="px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  >
                    <option value="">담당자 선택</option>
                    {activeCounselors.map(c => <option key={c.id} value={c.name}>{c.name} ({c.caseCount}건)</option>)}
                  </select>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────
const NAV_SECTIONS = [
  { label: null, items: [{ id: "overview", label: "관리자 대시보드", icon: "grid" }] },
  {
    label: "데이터·업무 관리",
    items: [
      { id: "cases",     label: "전체 사례 현황",  icon: "folder" },
      { id: "workqueue", label: "업무 처리 현황",  icon: "queue" },
      { id: "approvals", label: "문서 승인 관리",  icon: "check" },
    ],
  },
  {
    label: "권한·보안",
    items: [
      { id: "accounts",   label: "상담사 계정 관리", icon: "user" },
      { id: "access-log", label: "접속 기록",        icon: "log" },
      { id: "security",   label: "보안 이벤트",      icon: "shield" },
    ],
  },
  {
    label: "운영 편의",
    items: [
      { id: "notices",     label: "공지사항 관리", icon: "bell" },
      { id: "assignments", label: "업무 배정",     icon: "assign" },
    ],
  },
];

const BADGE_MAP: Partial<Record<AdminView, number>> = {
  "security":    1,
  "workqueue":   WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length + WORK_QUEUE.stt.filter(s => s.status === "오류").length,
  "assignments": UNASSIGNED_CASES.length,
};

function AdminIcon({ id }: { id: string }) {
  const icons: Record<string, React.ReactNode> = {
    grid:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>,
    folder: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>,
    queue:  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
    check:  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>,
    user:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
    log:    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="12" y2="17"/></svg>,
    shield: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    bell:   <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>,
    assign: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>,
  };
  return <>{icons[id] ?? null}</>;
}

function AdminSidebar({ current, onChange, onLogout }: { current: AdminView; onChange: (v: AdminView) => void; onLogout: () => void }) {
  return (
    <aside className="flex flex-col w-60 min-h-screen shrink-0" style={{ background: "#0F263B", borderRight: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="px-5 py-5" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: "rgba(255,255,255,0.1)" }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <div>
            <div className="text-base font-bold tracking-wide text-white">i-SPOT</div>
            <div className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.45)" }}>관리자</div>
          </div>
        </div>
      </div>

      <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#15314A] flex items-center justify-center text-xs font-bold text-white">김</div>
          <div>
            <div className="text-sm font-medium text-white">김민준</div>
            <div className="text-[11px]" style={{ color: "rgba(255,255,255,0.45)" }}>시스템 관리자</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_SECTIONS.map((section, si) => (
          <div key={si} className="px-3 mb-2">
            {section.label && (
              <p className="text-[10px] font-semibold uppercase tracking-widest px-2 pt-3 pb-1.5" style={{ color: "rgba(255,255,255,0.25)" }}>{section.label}</p>
            )}
            {section.items.map(item => {
              const active = current === item.id;
              const badge = BADGE_MAP[item.id as AdminView];
              return (
                <button
                  key={item.id}
                  onClick={() => onChange(item.id as AdminView)}
                  style={active
                    ? { borderLeft: "2px solid #2563EB", background: "rgba(255,255,255,0.07)", color: "white" }
                    : { color: "rgba(255,255,255,0.55)" }
                  }
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm mb-0.5 transition-all text-left font-medium ${
                    active ? "pl-[10px]" : "rounded-lg hover:text-white"
                  }`}
                  onMouseEnter={active ? undefined : (e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)"; }}
                  onMouseLeave={active ? undefined : (e) => { (e.currentTarget as HTMLElement).style.background = ""; }}
                >
                  <span className="shrink-0 opacity-80"><AdminIcon id={item.icon} /></span>
                  <span className="leading-tight flex-1">{item.label}</span>
                  {badge !== undefined && badge > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">{badge}</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="p-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <button onClick={onLogout} className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm transition-all" style={{ color: "rgba(255,255,255,0.55)" }}
          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)"; (e.currentTarget as HTMLElement).style.color = "white"; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = ""; (e.currentTarget as HTMLElement).style.color = "rgba(255,255,255,0.55)"; }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          로그아웃
        </button>
      </div>
    </aside>
  );
}

// ── Root ───────────────────────────────────────────────────────────────────
export default function AdminApp({ onLogout }: { onLogout: () => void }) {
  const [view, setView] = useState<AdminView>("overview");

  const renderView = () => {
    switch (view) {
      case "overview":    return <AdminOverview onNavigate={setView} />;
      case "cases":       return <AllCasesView />;
      case "workqueue":   return <WorkQueueView />;
      case "approvals":   return <WorkQueueView />;
      case "accounts":    return <AccountsView />;
      case "access-log":  return <AccessLogView />;
      case "security":    return <SecurityView />;
      case "notices":     return <NoticesView />;
      case "assignments": return <AssignmentsView />;
      default:            return <AdminOverview onNavigate={setView} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <AdminSidebar current={view} onChange={setView} onLogout={onLogout} />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-[#E2E8F0] px-7 py-3.5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="px-2 py-0.5 bg-[#E8EFF6] text-[#15314A] text-xs font-semibold rounded border border-[#D1DCE8]">관리자</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 text-slate-500 hover:text-slate-700 transition-colors">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
            </button>
            <div className="h-6 w-px bg-slate-200" />
            <div className="w-7 h-7 rounded-full bg-[#15314A] flex items-center justify-center text-white text-xs font-bold">김</div>
            <span className="text-sm font-medium text-slate-700">김민준</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[#F6F8FB]">
          {renderView()}
        </main>
      </div>
    </div>
  );
}
