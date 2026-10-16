export type RiskLevel = "high" | "mid" | "low";
export type AbuseType = "신체" | "정서" | "성" | "방임";

export interface CaseRecord {
  id: string;
  childName: string;
  age: number;
  guardian: string;
  abuseTypes: AbuseType[];
  /** Backend 에는 사례 위험도가 아직 없다. Backend 에서 온 사례는 비어 있고(adapters.toUiCase) 화면은 "—" 로 그린다. */
  riskLevel?: RiskLevel;
  /** 위험도가 없으면 0. */
  riskScore: number;
  lastSession: string;
  sessionCount: number;
  counselor: string;
  status: "active" | "pending" | "review";
  keywords: string[];
}

/** 가짜 데이터(아직 Backend 에 연결되지 않은 화면용)는 위험도가 늘 있다. */
export type MockCaseRecord = CaseRecord & { riskLevel: RiskLevel };

export const CASES: MockCaseRecord[] = [
  { id: "C-2026-0412", childName: "김○○", age: 8,  guardian: "부모",   abuseTypes: ["신체", "정서"], riskLevel: "high", riskScore: 87, lastSession: "2026-08-19", sessionCount: 6, counselor: "이서연", status: "active",  keywords: ["멍", "두려움", "회피", "수면장애"] },
  { id: "C-2026-0389", childName: "박○○", age: 11, guardian: "모",     abuseTypes: ["방임", "정서"], riskLevel: "high", riskScore: 82, lastSession: "2026-08-20", sessionCount: 4, counselor: "이서연", status: "review",  keywords: ["결석", "영양실조", "위축"] },
  { id: "C-2026-0374", childName: "최○○", age: 6,  guardian: "부모",   abuseTypes: ["신체"],          riskLevel: "mid",  riskScore: 61, lastSession: "2026-08-18", sessionCount: 3, counselor: "김민준", status: "active",  keywords: ["타박상", "설명불일치"] },
  { id: "C-2026-0351", childName: "이○○", age: 13, guardian: "부",     abuseTypes: ["성", "정서"],   riskLevel: "high", riskScore: 91, lastSession: "2026-08-15", sessionCount: 8, counselor: "이서연", status: "review",  keywords: ["외상후증상", "수치심", "자해시도"] },
  { id: "C-2026-0338", childName: "정○○", age: 9,  guardian: "조부모", abuseTypes: ["방임"],          riskLevel: "mid",  riskScore: 54, lastSession: "2026-08-17", sessionCount: 5, counselor: "박지수", status: "active",  keywords: ["위생불량", "배고픔", "무단결석"] },
  { id: "C-2026-0312", childName: "강○○", age: 7,  guardian: "부모",   abuseTypes: ["정서"],          riskLevel: "low",  riskScore: 31, lastSession: "2026-08-14", sessionCount: 7, counselor: "이서연", status: "active",  keywords: ["불안", "과잉경계"] },
  { id: "C-2026-0298", childName: "윤○○", age: 10, guardian: "모",     abuseTypes: ["신체", "방임"], riskLevel: "mid",  riskScore: 67, lastSession: "2026-08-13", sessionCount: 2, counselor: "김민준", status: "pending", keywords: ["멍", "혼자등교", "늦귀가"] },
  { id: "C-2026-0277", childName: "장○○", age: 5,  guardian: "부",     abuseTypes: ["신체"],          riskLevel: "high", riskScore: 78, lastSession: "2026-08-12", sessionCount: 3, counselor: "박지수", status: "review",  keywords: ["골절", "병원회피", "공격성"] },
  { id: "C-2026-0251", childName: "조○○", age: 14, guardian: "부모",   abuseTypes: ["정서"],          riskLevel: "low",  riskScore: 28, lastSession: "2026-08-10", sessionCount: 9, counselor: "이서연", status: "active",  keywords: ["자존감저하", "또래갈등"] },
  { id: "C-2026-0229", childName: "신○○", age: 8,  guardian: "모",     abuseTypes: ["방임", "신체"], riskLevel: "mid",  riskScore: 59, lastSession: "2026-08-08", sessionCount: 4, counselor: "김민준", status: "active",  keywords: ["지저분한외모", "멍", "우울"] },
];
