import { useState, useMemo, useEffect, useCallback } from "react";
import { Navigate, useNavigate, useParams } from "react-router";
import { CASES, type RiskLevel, type AbuseType } from "../data/cases";
import { ApiError } from "../api/client";
import { auth as authApi, cases as casesApi } from "../api/endpoints";
import { useAdminSession } from "../api/useAdminSession";
import {
  ROLE_LABELS,
  accountStateTags,
  countCasesByCounselor,
  toAuditRange,
  toBrowserLabel,
  toLocalDateTime,
  toLoginFailureReason,
} from "../api/adminAdapters";
import type { AuditLog, Case, Paged, TemporaryPassword, User } from "../api/types";
import { useToast } from "../components/ui/Toast";
import { ConfirmDialog, CreateAccountDialog, TemporaryPasswordDialog } from "./AccountDialogs";

// ── Types ──────────────────────────────────────────────────────────────────
type AdminView =
  | "overview"
  | "cases"
  | "workqueue"
  | "approvals"
  | "accounts"
  | "access-log"
  | "security"
  | "stats";

// ── Mock data ──────────────────────────────────────────────────────────────
const COUNSELORS = [
  { id: "C001", name: "이서연", role: "상담사",    status: "active",   lastLogin: "2026-08-21 09:14", caseCount: 6, ip: "192.168.1.12", locked: false },
  { id: "C002", name: "박지훈", role: "상담사",    status: "active",   lastLogin: "2026-08-21 08:52", caseCount: 4, ip: "192.168.1.19", locked: false },
  { id: "C003", name: "최수민", role: "상담사",    status: "inactive", lastLogin: "2026-08-14 14:30", caseCount: 0, ip: "192.168.1.34", locked: false },
  { id: "C004", name: "정다은", role: "선임상담사", status: "active",   lastLogin: "2026-08-21 09:01", caseCount: 7, ip: "192.168.1.8",  locked: true  },
  { id: "C005", name: "한승호", role: "상담사",    status: "active",   lastLogin: "2026-08-20 17:45", caseCount: 3, ip: "192.168.1.22", locked: false },
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
    { caseId: "C-2026-0451", child: "황○○", counselor: "한승호", submitted: "2026-08-20 16:44", status: "오류",    waitTime: "17시간 52분", stage: "오류",    reason: "STT 변환 처리", handler: "시스템" },
    { caseId: "C-2026-0389", child: "최○○", counselor: "박지훈", submitted: "2026-08-21 11:20", status: "대기",    waitTime: "4시간 30분",  stage: "처리 대기", reason: "STT 변환 처리", handler: "시스템" },
    { caseId: "C-2026-0412", child: "김○○", counselor: "이서연", submitted: "2026-08-21 13:50", status: "처리중",  waitTime: "2시간 15분",  stage: "처리중",   reason: "STT 변환 처리", handler: "시스템" },
  ],
  aiReview: [
    { caseId: "C-2026-0277", child: "오○○", counselor: "이서연", submitted: "2026-08-20 14:30", status: "검토 대기", waitTime: "22시간 17분", stage: "검토 대기", reason: "AI 분석 완료 검토 요청", handler: "이서연" },
    { caseId: "C-2026-0351", child: "박○○", counselor: "정다은", submitted: "2026-08-21 10:05", status: "검토 대기", waitTime: "5시간 42분",  stage: "검토 대기", reason: "AI 분석 완료 검토 요청", handler: "정다은" },
  ],
  approval: [
    { caseId: "C-2026-0234", child: "정○○", counselor: "한승호", docType: "상담일지",  submitted: "2026-08-19 15:55", status: "반려됨",   waitTime: "51시간 52분", stage: "반려됨",  reason: "상담일지 제출",  handler: "한승호" },
    { caseId: "C-2026-0389", child: "최○○", counselor: "박지훈", docType: "사정기록지", submitted: "2026-08-20 17:10", status: "승인 대기", waitTime: "26시간 37분", stage: "승인 대기", reason: "사정기록지 제출", handler: "박지훈" },
    { caseId: "C-2026-0312", child: "이○○", counselor: "정다은", docType: "상담일지",  submitted: "2026-08-21 09:40", status: "승인 대기", waitTime: "6시간 7분",   stage: "승인 대기", reason: "상담일지 제출",  handler: "정다은" },
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
  const label = { high: "확인 필요", mid: "확인 중", low: "확인 완료" }[level];
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
    { label: `확인 필요 사례 ${highRisk}건 집중 모니터링 필요`, tag: "사례", color: "text-amber-700 bg-amber-50 border-amber-200", view: "cases" as AdminView },
    { label: `문서 승인 대기 ${WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length}건`,             tag: "승인", color: "text-blue-700 bg-blue-50 border-blue-200",  view: "approvals" as AdminView },
    { label: `미배정 신규 사례 ${UNASSIGNED_CASES.length}건`,                                                   tag: "배정", color: "text-purple-700 bg-purple-50 border-purple-200", view: "cases" as AdminView },
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
          { label: "전체 관리 사례", value: String(CASES.length),          sub: `확인 필요 ${highRisk}건 포함`,   color: "text-slate-900",  icon: "📁" },
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
  const [showUnassigned, setShowUnassigned] = useState(false);
  const [assignedMap, setAssignedMap] = useState<Record<string, string>>({});

  const counselorNames = ["전체", ...Array.from(new Set(CASES.map(c => c.counselor)))];
  const activeCounselors = COUNSELORS.filter(c => c.status === "active");

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
            const labels = { "전체": "전체", high: "확인 필요", mid: "확인 중", low: "확인 완료" };
            return (
              <button key={r} onClick={() => setRiskFilter(r)}
                className={`px-3 py-1.5 rounded text-xs font-medium border transition-all ${riskFilter === r ? "bg-[#172033] text-white border-[#172033]" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
              >
                {labels[r]}
              </button>
            );
          })}
        </div>
        <button
          onClick={() => setShowUnassigned(v => !v)}
          className={`px-3 py-1.5 rounded text-xs font-medium border transition-all ${showUnassigned ? "bg-purple-700 text-white border-purple-700" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
        >
          미배정 ({UNASSIGNED_CASES.length})
        </button>
        <span className="ml-auto text-xs text-slate-400 font-medium">{showUnassigned ? UNASSIGNED_CASES.length : filtered.length}건</span>
      </div>

      {showUnassigned ? (
        <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                {["사례 ID", "아동명", "연령", "학대유형", "위험도", "접수일", "담당자 배정"].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {UNASSIGNED_CASES.map(uc => (
                <tr key={uc.id} className="hover:bg-slate-50 transition-colors border-l-2 border-l-purple-300">
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{uc.id}</td>
                  <td className="px-4 py-3 font-semibold text-slate-900 text-sm">{uc.child}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{uc.age}세</td>
                  <td className="px-4 py-3"><div className="flex gap-1">{uc.types.map(t => <AbuseBadge key={t} type={t} />)}</div></td>
                  <td className="px-4 py-3"><RiskBadge level={uc.risk} /></td>
                  <td className="px-4 py-3 text-xs text-slate-500 font-mono">{uc.received}</td>
                  <td className="px-4 py-3">
                    {assignedMap[uc.id] ? (
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-1 rounded">✓ {assignedMap[uc.id]}</span>
                        <button onClick={() => setAssignedMap(p => { const n = { ...p }; delete n[uc.id]; return n; })} className="text-xs text-slate-400 hover:text-slate-600">취소</button>
                      </div>
                    ) : (
                      <select onChange={e => e.target.value && setAssignedMap(p => ({ ...p, [uc.id]: e.target.value }))} defaultValue=""
                        className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                      >
                        <option value="">담당자 선택</option>
                        {activeCounselors.map(c => <option key={c.id} value={c.name}>{c.name} ({c.caseCount}건)</option>)}
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
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
      )}
    </div>
  );
}

// ── Section: 업무 처리 현황 ────────────────────────────────────────────────
function waitTimeColor(wt: string): string {
  const h = parseInt(wt);
  if (h >= 24) return "text-red-600 font-semibold";
  if (h >= 12) return "text-amber-600";
  return "text-slate-500";
}

function StageBadge({ stage }: { stage: string }) {
  const cfg: Record<string, string> = {
    "처리중":  "bg-blue-50 text-blue-700",
    "처리 대기": "bg-slate-100 text-slate-600",
    "오류":    "bg-red-50 text-red-700",
    "검토 대기": "bg-amber-50 text-amber-700",
    "승인 대기": "bg-amber-50 text-amber-700",
    "반려됨":  "bg-red-50 text-red-700",
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${cfg[stage] ?? "bg-slate-100 text-slate-600"}`}>{stage}</span>;
}

function WorkQueueView() {
  const [tab, setTab] = useState<"stt" | "aiReview" | "approval">("stt");

  const tabCfg = [
    { id: "stt" as const,      label: "STT 처리 대기",   count: WORK_QUEUE.stt.length },
    { id: "aiReview" as const, label: "상담사 검토 대기",    count: WORK_QUEUE.aiReview.length },
    { id: "approval" as const, label: "문서 승인 대기",  count: WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length },
  ];

  return (
    <div className="p-7 space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">업무 처리 현황</h1>
        <p className="text-slate-500 text-sm mt-0.5">STT 변환 · AI 검토 · 문서 승인 처리 대기 현황 (대기시간 기준 내림차순)</p>
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
              {["사례 ID", "아동명", "담당 상담사", "제출 시각", "대기시간", "처리단계", "사유", "담당 처리자", "작업"].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.stt.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-4 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-700">{row.counselor}</td>
                  <td className="px-4 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className={`px-4 py-3.5 text-xs font-mono ${waitTimeColor(row.waitTime)}`}>{row.waitTime}</td>
                  <td className="px-4 py-3.5"><StageBadge stage={row.stage} /></td>
                  <td className="px-4 py-3.5 text-xs text-slate-500">{row.reason}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-700">{row.handler}</td>
                  <td className="px-4 py-3.5">
                    {row.stage === "오류" && <button className="text-xs text-red-600 hover:text-red-800 font-medium">재처리 요청</button>}
                    {row.stage !== "오류" && <button className="text-xs text-slate-400 font-medium">상세보기</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "aiReview" && (
          <table className="w-full">
            <thead><tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "담당 상담사", "제출 시각", "대기시간", "처리단계", "담당 처리자", "작업"].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.aiReview.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-4 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-700">{row.counselor}</td>
                  <td className="px-4 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className={`px-4 py-3.5 text-xs font-mono ${waitTimeColor(row.waitTime)}`}>{row.waitTime}</td>
                  <td className="px-4 py-3.5"><StageBadge stage={row.stage} /></td>
                  <td className="px-4 py-3.5 text-sm text-slate-700">{row.handler}</td>
                  <td className="px-4 py-3.5"><button className="text-xs text-[#2563EB] hover:text-[#1d4ed8] font-medium">검토 독려</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "approval" && (
          <table className="w-full">
            <thead><tr className="border-b border-slate-100 bg-slate-50">
              {["사례 ID", "아동명", "문서 유형", "제출 시각", "대기시간", "상태", "사유", "담당 처리자", "작업"].map(h => (
                <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {WORK_QUEUE.approval.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3.5 font-mono text-xs text-slate-500">{row.caseId}</td>
                  <td className="px-4 py-3.5 font-semibold text-slate-900 text-sm">{row.child}</td>
                  <td className="px-4 py-3.5"><span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-xs font-medium">{row.docType}</span></td>
                  <td className="px-4 py-3.5 text-xs text-slate-500 font-mono">{row.submitted}</td>
                  <td className={`px-4 py-3.5 text-xs font-mono ${waitTimeColor(row.waitTime)}`}>{row.waitTime}</td>
                  <td className="px-4 py-3.5"><StageBadge stage={row.stage} /></td>
                  <td className="px-4 py-3.5 text-xs text-slate-500">{row.reason}</td>
                  <td className="px-4 py-3.5 text-sm text-slate-700">{row.handler}</td>
                  <td className="px-4 py-3.5">
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
// GET /auth/users(관리자 포함 전체) + 담당 사례 수(GET /cases 전체 페이지를 받아 셈).
// 자기 계정에는 비활성화 · 강제 로그아웃 · 비밀번호 초기화 · 휴면 해제 단추를 두지 않는다(바로 자기 로그인이 끊긴다).
const CASE_PAGE_SIZE = 100;

async function loadAllCases(): Promise<Case[]> {
  const all: Case[] = [];

  for (let page = 1; ; page += 1) {
    const result = await casesApi.list({ page, page_size: CASE_PAGE_SIZE });

    all.push(...result.items);

    if (page >= result.meta.total_pages || result.items.length === 0) return all;
  }
}

type AccountAction = "deactivate" | "logoutAll" | "resetPassword" | "reactivate";

const ACCOUNT_ACTION_TEXT: Record<AccountAction, { title: string; confirm: string; danger: boolean; message: (u: User) => string }> = {
  deactivate: {
    title: "계정 비활성화",
    confirm: "비활성화",
    danger: true,
    message: u => `${u.name}(${u.email}) 계정을 비활성화합니다. 지금 로그인돼 있으면 바로 끊기고, 다시 활성화할 때까지 로그인할 수 없습니다.`,
  },
  logoutAll: {
    title: "강제 로그아웃",
    confirm: "강제 로그아웃",
    danger: true,
    message: u => `${u.name}(${u.email}) 계정의 모든 기기 로그인을 끊습니다. 비밀번호는 그대로이며 다시 로그인할 수 있습니다.`,
  },
  resetPassword: {
    title: "비밀번호 초기화",
    confirm: "초기화",
    danger: true,
    message: u => `${u.name}(${u.email}) 계정의 비밀번호를 임시 비밀번호로 바꿉니다. 지금 로그인돼 있으면 끊기고, 다음 로그인 때 새 비밀번호로 바꿔야 합니다.`,
  },
  reactivate: {
    title: "휴면 해제",
    confirm: "휴면 해제",
    danger: false,
    message: u => `${u.name}(${u.email}) 계정의 휴면을 풀고 임시 비밀번호를 새로 발급합니다.`,
  },
};

const TAG_TONE: Record<"red" | "amber" | "slate", string> = {
  red: "bg-red-50 text-red-600 border-red-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  slate: "bg-slate-100 text-slate-600 border-slate-200",
};

function AccountsView({ me }: { me: User }) {
  const { showToast } = useToast();
  const [accounts, setAccounts] = useState<User[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [caseCounts, setCaseCounts] = useState<Map<string, number> | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pending, setPending] = useState<{ action: AccountAction; user: User } | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  // 임시 비밀번호는 이 창에서 한 번만 보여 주고 닫으면 버린다.
  const [issued, setIssued] = useState<{ title: string; user: User; temporary: TemporaryPassword } | null>(null);

  const reload = useCallback(() => setReloadKey(k => k + 1), []);

  useEffect(() => {
    let cancelled = false;

    authApi.listUsers()
      .then(list => { if (!cancelled) { setAccounts(list); setLoadError(null); } })
      .catch(caught => { if (!cancelled) setLoadError(caught instanceof ApiError ? caught.message : "계정 목록을 불러오지 못했습니다."); });

    // 담당 사례 수는 실패해도 목록은 보여 준다(칸에 "—").
    loadAllCases()
      .then(list => { if (!cancelled) setCaseCounts(countCasesByCounselor(list)); })
      .catch(() => { if (!cancelled) setCaseCounts(null); });

    return () => { cancelled = true; };
  }, [reloadKey]);

  async function toggleStatus(a: User) {
    if (a.is_active) {
      setPendingError(null);
      setPending({ action: "deactivate", user: a });
      return;
    }

    setBusyId(a.id);
    try {
      await authApi.updateUser(a.id, { is_active: true });
      showToast(`${a.name} 계정을 활성화했습니다.`, "success");
      reload();
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "활성화하지 못했습니다.", "error");
    } finally {
      setBusyId(null);
    }
  }

  async function unlock(a: User) {
    setBusyId(a.id);
    try {
      await authApi.unlockUser(a.id);
      showToast(`${a.name} 계정의 잠금을 해제했습니다.`, "success");
      reload();
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "잠금을 해제하지 못했습니다.", "error");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmPending() {
    if (!pending) return;

    const { action, user } = pending;

    setBusyId(user.id);
    setPendingError(null);
    try {
      if (action === "deactivate") {
        await authApi.updateUser(user.id, { is_active: false });
        showToast(`${user.name} 계정을 비활성화했습니다.`, "success");
      } else if (action === "logoutAll") {
        await authApi.logoutAll(user.id);
        showToast(`${user.name} 계정의 로그인을 모두 끊었습니다.`, "success");
      } else {
        const temporary = action === "resetPassword" ? await authApi.resetPassword(user.id) : await authApi.reactivateUser(user.id);
        setIssued({ title: action === "resetPassword" ? "비밀번호 초기화 완료" : "휴면 해제 완료", user, temporary });
      }
      setPending(null);
      reload();
    } catch (caught) {
      setPendingError(caught instanceof ApiError ? caught.message : "처리하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusyId(null);
    }
  }

  function handleCreated(user: User, temporary: TemporaryPassword | null) {
    setCreating(false);
    reload();

    if (temporary) {
      setIssued({ title: "신규 계정 생성 완료", user, temporary });
    } else {
      showToast(`${user.name} 계정은 만들었지만 임시 비밀번호를 발급하지 못했습니다. 목록에서 '비밀번호 초기화'를 눌러 주세요.`, "error");
    }
  }

  const pendingText = pending ? ACCOUNT_ACTION_TEXT[pending.action] : null;

  return (
    <div className="p-7 space-y-5 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">상담사 계정 관리</h1>
          <p className="text-slate-500 text-sm mt-0.5">계정 활성화·비활성화 · 비밀번호 초기화 · 신규 계정 생성</p>
        </div>
        <button onClick={() => setCreating(true)} className="flex items-center gap-2 px-4 py-2 bg-[#15314A] text-white text-sm font-semibold rounded-lg hover:bg-[#0F263B] transition-colors">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          신규 계정 생성
        </button>
      </div>

      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["계정 ID", "이름", "직급", "담당 사례", "최근 접속", "상태", ""].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {!accounts && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-sm text-slate-400">{loadError ?? "불러오는 중..."}</td></tr>
            )}
            {accounts?.map(a => {
              const isSelf = a.id === me.id;
              const busy = busyId === a.id;
              return (
                <tr key={a.id} className={`transition-colors ${!a.is_active ? "bg-slate-50/60 opacity-70" : "hover:bg-slate-50"}`}>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500">{a.email}</td>
                  <td className="px-5 py-3.5 font-semibold text-slate-900 whitespace-nowrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      {a.name}
                      {isSelf && <span className="px-1.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded text-[10px] font-semibold">본인</span>}
                      {accountStateTags(a).map(t => (
                        <span key={t.label} className={`px-1.5 py-0.5 border rounded text-[10px] font-semibold ${TAG_TONE[t.tone]}`}>{t.label}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-sm text-slate-600">{ROLE_LABELS[a.role] ?? a.role}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-sm text-slate-700">{caseCounts ? `${caseCounts.get(a.id) ?? 0}건` : "—"}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap text-xs text-slate-500 font-mono">{toLocalDateTime(a.last_login_at)}</td>
                  <td className="px-5 py-3.5 whitespace-nowrap"><StatusDot active={a.is_active} /></td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3 whitespace-nowrap">
                      {!isSelf && (
                        <button disabled={busy} onClick={() => toggleStatus(a)} className={`text-xs font-medium transition-colors disabled:opacity-50 ${a.is_active ? "text-amber-600 hover:text-amber-800" : "text-green-600 hover:text-green-800"}`}>
                          {a.is_active ? "비활성화" : "활성화"}
                        </button>
                      )}
                      {a.is_locked && (
                        <button disabled={busy} onClick={() => unlock(a)} className="text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors disabled:opacity-50">잠금 해제</button>
                      )}
                      {!isSelf && a.dormant_at && (
                        <button disabled={busy} onClick={() => { setPendingError(null); setPending({ action: "reactivate", user: a }); }} className="text-xs text-blue-600 hover:text-blue-800 font-medium transition-colors disabled:opacity-50">휴면 해제</button>
                      )}
                      {!isSelf && (
                        <button disabled={busy} onClick={() => { setPendingError(null); setPending({ action: "logoutAll", user: a }); }} className="text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors disabled:opacity-50">강제 로그아웃</button>
                      )}
                      {!isSelf && (
                        <button disabled={busy} onClick={() => { setPendingError(null); setPending({ action: "resetPassword", user: a }); }} className="text-xs text-slate-400 hover:text-slate-600 font-medium transition-colors disabled:opacity-50">비밀번호 초기화</button>
                      )}
                      {isSelf && <span className="text-xs text-slate-400">본인 계정</span>}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {pending && pendingText && (
        <ConfirmDialog
          title={pendingText.title}
          message={pendingText.message(pending.user)}
          confirmLabel={pendingText.confirm}
          danger={pendingText.danger}
          busy={busyId === pending.user.id}
          error={pendingError}
          onConfirm={confirmPending}
          onCancel={() => setPending(null)}
        />
      )}
      {creating && <CreateAccountDialog onCreated={handleCreated} onCancel={() => setCreating(false)} />}
      {issued && <TemporaryPasswordDialog title={issued.title} user={issued.user} temporary={issued.temporary} onClose={() => setIssued(null)} />}
    </div>
  );
}

// ── Section: 접속 기록 ────────────────────────────────────────────────────
// GET /auth/audit-logs?action=LOGIN. 성공/실패 · 기간은 서버에서 거르고 20건씩 넘긴다.
// 로그인 당시 역할은 기록에 없어 '현재 역할'(계정 목록)을 보여 준다.
const ACCESS_LOG_PAGE_SIZE = 20;

function AccessLogView() {
  const [filter, setFilter] = useState<"전체" | "성공" | "실패">("전체");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Paged<AuditLog> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roles, setRoles] = useState<Map<string, User["role"]>>(new Map());

  const rangeInvalid = Boolean(startDate && endDate && startDate > endDate);

  useEffect(() => {
    let cancelled = false;

    authApi.listUsers()
      .then(list => { if (!cancelled) setRoles(new Map(list.map(u => [u.id, u.role]))); })
      .catch(() => { /* 역할 칸만 "—" 로 둔다 */ });

    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (rangeInvalid) return;

    let cancelled = false;

    setLoading(true);
    setError(null);

    authApi.auditLogs({
      action: "LOGIN",
      status: filter === "성공" ? "SUCCESS" : filter === "실패" ? "FAILURE" : undefined,
      ...toAuditRange(startDate, endDate),
      page,
      page_size: ACCESS_LOG_PAGE_SIZE,
    })
      .then(data => { if (!cancelled) setResult(data); })
      .catch(caught => { if (!cancelled) setError(caught instanceof ApiError ? caught.message : "접속 기록을 불러오지 못했습니다."); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [filter, startDate, endDate, page, rangeInvalid]);

  const rows = result?.items ?? [];
  const totalPages = Math.max(1, result?.meta.total_pages ?? 1);
  const dateInput = "px-2 py-1.5 rounded border border-slate-200 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#2563EB]";

  return (
    <div className="p-7 space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">접속 기록</h1>
        <p className="text-slate-500 text-sm mt-0.5">최근 시스템 접속 이력 · 이상 접속 감지</p>
      </div>
      <div className="flex gap-2 flex-wrap items-center">
        {(["전체", "성공", "실패"] as const).map(f => (
          <button key={f} onClick={() => { setFilter(f); setPage(1); }}
            className={`px-4 py-1.5 rounded text-xs font-medium border transition-all ${filter === f ? "bg-[#172033] text-white border-[#172033]" : "border-slate-200 text-slate-600 hover:border-slate-400"}`}
          >
            {f}
          </button>
        ))}
        <div className="flex items-center gap-1.5 ml-3">
          <label htmlFor="log-start" className="text-xs font-semibold text-slate-500">기간</label>
          <input id="log-start" type="date" value={startDate} max={endDate || undefined} onChange={e => { setStartDate(e.target.value); setPage(1); }} className={dateInput} aria-label="시작일" />
          <span className="text-xs text-slate-400">~</span>
          <input id="log-end" type="date" value={endDate} min={startDate || undefined} onChange={e => { setEndDate(e.target.value); setPage(1); }} className={dateInput} aria-label="종료일" />
          {(startDate || endDate) && (
            <button onClick={() => { setStartDate(""); setEndDate(""); setPage(1); }} className="text-xs text-slate-400 hover:text-slate-600 ml-1">기간 지우기</button>
          )}
        </div>
        <span className="ml-auto text-xs text-slate-400 self-center">{result ? `${result.meta.total}건` : ""}</span>
      </div>
      {rangeInvalid && <p className="text-xs text-red-600">시작일이 종료일보다 늦습니다.</p>}
      <div className="bg-white rounded-[8px] border border-[#E2E8F0] overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50">
              {["접속 시각", "사용자", "현재 역할", "IP 주소", "브라우저", "결과"].map(h => (
                <th key={h} className="px-5 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(error || (loading && rows.length === 0) || (!loading && rows.length === 0)) && (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-sm text-slate-400">
                {error ?? (loading ? "불러오는 중..." : "조건에 맞는 접속 기록이 없습니다.")}
              </td></tr>
            )}
            {!error && rows.map(log => {
              const failed = log.status === "FAILURE";
              const role = log.actor_id ? roles.get(log.actor_id) : undefined;
              return (
                <tr key={log.id} className={`transition-colors ${failed ? "bg-red-50/40 hover:bg-red-50" : "hover:bg-slate-50"}`}>
                  <td className="px-5 py-3 whitespace-nowrap text-xs text-slate-500 font-mono">{toLocalDateTime(log.created_at)}</td>
                  <td className="px-5 py-3 whitespace-nowrap font-semibold text-sm text-slate-900" title={log.actor_name ? undefined : "등록되지 않은 이메일로 시도"}>{log.actor_name ?? "알 수 없음"}</td>
                  <td className="px-5 py-3 whitespace-nowrap text-sm text-slate-600">{role ? ROLE_LABELS[role] : "—"}</td>
                  <td className="px-5 py-3 whitespace-nowrap text-xs text-slate-500 font-mono">{log.ip_address ?? "—"}</td>
                  <td className="px-5 py-3 whitespace-nowrap text-xs text-slate-400" title={log.user_agent ?? undefined}>{toBrowserLabel(log.user_agent)}</td>
                  <td className="px-5 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${failed ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>{failed ? "실패" : "성공"}</span>
                    {failed && log.error_code && <span className="block mt-1 text-[11px] text-slate-500">{toLoginFailureReason(log.error_code)}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-center gap-3">
        <button disabled={page <= 1 || loading} onClick={() => setPage(p => Math.max(1, p - 1))}
          className="px-3 py-1.5 rounded border border-slate-200 text-xs font-medium text-slate-600 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed">이전</button>
        <span className="text-xs text-slate-500">{page} / {totalPages}</span>
        <button disabled={page >= totalPages || loading} onClick={() => setPage(p => p + 1)}
          className="px-3 py-1.5 rounded border border-slate-200 text-xs font-medium text-slate-600 hover:border-slate-400 disabled:opacity-40 disabled:cursor-not-allowed">다음</button>
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

// ── Section: 통계 리포트 ──────────────────────────────────────────────────
function StatsView() {
  const monthlyData = [
    { month: "3월", count: 28 },
    { month: "4월", count: 35 },
    { month: "5월", count: 31 },
    { month: "6월", count: 42 },
    { month: "7월", count: 38 },
    { month: "8월", count: 45 },
  ];
  const abuseTypes = [
    { label: "신체", count: 38, color: "#EF4444" },
    { label: "정서", count: 27, color: "#A855F7" },
    { label: "방임", count: 22, color: "#64748B" },
    { label: "성",   count: 13, color: "#F97316" },
  ];
  const ageGroups = [
    { label: "0~6세", count: 18 },
    { label: "7~12세", count: 32 },
    { label: "13~18세", count: 15 },
  ];

  const maxMonthly = Math.max(...monthlyData.map(d => d.count));
  const total = abuseTypes.reduce((s, t) => s + t.count, 0);
  const maxAge = Math.max(...ageGroups.map(g => g.count));

  // Pie chart slices
  let cumAngle = -Math.PI / 2;
  const slices = abuseTypes.map(t => {
    const angle = (t.count / total) * 2 * Math.PI;
    const start = cumAngle;
    cumAngle += angle;
    const end = cumAngle;
    const r = 70;
    const cx = 90; const cy = 90;
    const x1 = cx + r * Math.cos(start); const y1 = cy + r * Math.sin(start);
    const x2 = cx + r * Math.cos(end);   const y2 = cy + r * Math.sin(end);
    const large = angle > Math.PI ? 1 : 0;
    return { ...t, d: `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} Z` };
  });

  // Line chart points
  const svgW = 480; const svgH = 140; const padL = 30; const padR = 10; const padT = 10; const padB = 30;
  const pts = monthlyData.map((d, i) => {
    const x = padL + (i / (monthlyData.length - 1)) * (svgW - padL - padR);
    const y = padT + (1 - d.count / maxMonthly) * (svgH - padT - padB);
    return { x, y, ...d };
  });
  const polyline = pts.map(p => `${p.x},${p.y}`).join(" ");

  return (
    <div className="p-7 space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">통계 리포트</h1>
        <p className="text-slate-500 text-sm mt-0.5">2026년 8월 기준 · 기관 업무 통계 요약</p>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "이번 달 상담 건수", value: "45건", sub: "전월(38건) 대비", change: "+18.4%", up: true },
          { label: "이번 달 처리 건수", value: "39건", sub: "처리율 86.7%", change: "+12.0%", up: true },
          { label: "평균 대기 시간",    value: "14.2시간", sub: "전월(11.8시간) 대비", change: "+20.3%", up: false },
        ].map(s => (
          <div key={s.label} className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
            <p className="text-xs font-medium text-slate-500 mb-2">{s.label}</p>
            <p className="text-2xl font-bold text-slate-900">{s.value}</p>
            <p className="text-xs text-slate-400 mt-1">{s.sub} <span className={`font-semibold ${s.up ? "text-green-600" : "text-red-500"}`}>{s.change}</span></p>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-5">
        {/* Line chart */}
        <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
          <p className="text-sm font-semibold text-slate-800 mb-4">월별 상담 건수 (최근 6개월)</p>
          <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full">
            {/* Grid lines */}
            {[0, 0.5, 1].map(f => {
              const y = padT + f * (svgH - padT - padB);
              return <line key={f} x1={padL} y1={y} x2={svgW - padR} y2={y} stroke="#E2E8F0" strokeWidth="1" />;
            })}
            <polyline points={polyline} fill="none" stroke="#2563EB" strokeWidth="2" strokeLinejoin="round" />
            {pts.map((p, i) => (
              <g key={i}>
                <circle cx={p.x} cy={p.y} r="4" fill="#2563EB" />
                <text x={p.x} y={svgH - 8} textAnchor="middle" fontSize="10" fill="#94A3B8">{p.month}</text>
                <text x={p.x} y={p.y - 8} textAnchor="middle" fontSize="10" fill="#475569" fontWeight="600">{p.count}</text>
              </g>
            ))}
          </svg>
        </div>

        {/* Pie chart */}
        <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
          <p className="text-sm font-semibold text-slate-800 mb-4">학대유형별 비율</p>
          <div className="flex items-center gap-6">
            <svg viewBox="0 0 180 180" className="w-36 h-36 shrink-0">
              {slices.map((s, i) => <path key={i} d={s.d} fill={s.color} />)}
            </svg>
            <div className="space-y-2">
              {abuseTypes.map(t => (
                <div key={t.label} className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: t.color }} />
                  <span className="text-sm text-slate-700">{t.label}</span>
                  <span className="text-xs text-slate-400 ml-auto">{Math.round(t.count / total * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Age bar chart + work status table */}
      <div className="grid grid-cols-2 gap-5">
        <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
          <p className="text-sm font-semibold text-slate-800 mb-4">연령별 사례 분포</p>
          <div className="space-y-4">
            {ageGroups.map(g => (
              <div key={g.label}>
                <div className="flex justify-between text-xs text-slate-600 mb-1.5">
                  <span>{g.label}</span>
                  <span className="font-semibold">{g.count}건</span>
                </div>
                <div className="h-5 bg-slate-100 rounded overflow-hidden">
                  <div className="h-full bg-[#2563EB] rounded transition-all" style={{ width: `${(g.count / maxAge) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-[8px] border border-[#E2E8F0] p-5">
          <p className="text-sm font-semibold text-slate-800 mb-4">전체 업무 현황</p>
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-100">
                {["구분", "대기 건수"].map(h => (
                  <th key={h} className="pb-2 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {[
                { label: "STT 처리 대기",  count: WORK_QUEUE.stt.length },
                { label: "상담사 검토 대기",   count: WORK_QUEUE.aiReview.length },
                { label: "문서 승인 대기", count: WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length },
              ].map(r => (
                <tr key={r.label}>
                  <td className="py-2.5 text-sm text-slate-700">{r.label}</td>
                  <td className="py-2.5 text-sm font-bold text-slate-900">{r.count}건</td>
                </tr>
              ))}
            </tbody>
          </table>
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
      { id: "stats",      label: "통계 리포트",      icon: "chart" },
    ],
  },
];

const BADGE_MAP: Partial<Record<AdminView, number>> = {
  "security":  1,
  "workqueue": WORK_QUEUE.approval.filter(a => a.status === "승인 대기").length + WORK_QUEUE.stt.filter(s => s.status === "오류").length,
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
    chart:  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/></svg>,
  };
  return <>{icons[id] ?? null}</>;
}

function AdminSidebar({ me, current, onChange, onLogout }: { me: User; current: AdminView; onChange: (v: AdminView) => void; onLogout: () => void }) {
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
          <div className="w-8 h-8 rounded-full bg-[#15314A] flex items-center justify-center text-xs font-bold text-white">{me.name.charAt(0) || "?"}</div>
          <div>
            <div className="text-sm font-medium text-white">{me.name}</div>
            {/* 역할 3종(시스템 관리자 등)은 아직 Backend 에 없어 '관리자'로 둔다. */}
            <div className="text-[11px]" style={{ color: "rgba(255,255,255,0.45)" }}>{ROLE_LABELS[me.role]}</div>
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
// 메뉴는 주소(/admin, /admin/accounts …)로 나눈다. 새로고침해도 보던 메뉴가 유지된다.
const ADMIN_VIEWS: AdminView[] = ["overview", "cases", "workqueue", "approvals", "accounts", "access-log", "security", "stats"];

export default function AdminApp() {
  const navigate = useNavigate();
  const { view: viewParam } = useParams();
  const { me, error, retry, logout } = useAdminSession();

  const setView = useCallback((v: AdminView) => {
    navigate(v === "overview" ? "/admin" : `/admin/${v}`);
  }, [navigate]);

  // 모르는 메뉴 주소는 대시보드로. overview 는 /admin 이 대표 주소다.
  if (viewParam !== undefined && (viewParam === "overview" || !ADMIN_VIEWS.includes(viewParam as AdminView))) {
    return <Navigate to="/admin" replace />;
  }

  const view: AdminView = (viewParam as AdminView | undefined) ?? "overview";

  // 관리자인지 서버에서 확인하기 전에는 아무 화면도 그리지 않는다(관리자가 아니면 useAdminSession 이 다른 곳으로 보낸다).
  if (!me) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#F6F8FB]">
        {error ? (
          <div className="bg-white border border-[#E2E8F0] rounded-[8px] px-6 py-5 text-center space-y-3 max-w-sm">
            <p className="text-sm text-slate-700">{error}</p>
            <div className="flex gap-2 justify-center">
              <button onClick={retry} className="px-4 py-2 bg-[#15314A] text-white text-sm font-semibold rounded-lg hover:bg-[#0F263B]">다시 시도</button>
              <button onClick={logout} className="px-4 py-2 border border-slate-200 text-slate-600 text-sm font-medium rounded-lg hover:bg-slate-50">로그인 화면으로</button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-400">관리자 정보를 확인하는 중...</p>
        )}
      </div>
    );
  }

  const renderView = () => {
    switch (view) {
      case "overview":   return <AdminOverview onNavigate={setView} />;
      case "cases":      return <AllCasesView />;
      case "workqueue":  return <WorkQueueView />;
      case "approvals":  return <WorkQueueView />;
      case "accounts":   return <AccountsView me={me} />;
      case "access-log": return <AccessLogView />;
      case "security":   return <SecurityView />;
      case "stats":      return <StatsView />;
      default:           return <AdminOverview onNavigate={setView} />;
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <AdminSidebar me={me} current={view} onChange={setView} onLogout={logout} />

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
            <div className="w-7 h-7 rounded-full bg-[#15314A] flex items-center justify-center text-white text-xs font-bold">{me.name.charAt(0) || "?"}</div>
            <span className="text-sm font-medium text-slate-700">{me.name}</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[#F6F8FB]">
          {renderView()}
        </main>
      </div>
    </div>
  );
}
