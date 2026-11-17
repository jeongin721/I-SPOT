// 관리자 화면(AdminHome · AdminHomeTablet · AdminCases · AdminCounselor · AdminAccounts)이 같이 쓰는 계산.
// .js 라서 라우트로 잡히지 않는다(App.jsx 는 pages/*.jsx 만 등록).
//  - 관리자 전용 API(GET /auth/users · /auth/audit-logs)는 상담사로 열면 403 — 그때는 안내 문구만 보이고 값은 비운다.
//  - 고령자 현황 = GET /senior-overview(27절, 관리자는 모든 고령자 사례). 사례 번호 · 나이 · 접수일은 cases.list(subject_type SENIOR).
//  - 아동 전용 숫자(학대 위기도 · 아이 앱)는 쓰지 않는다. 안부 연계 앱 긴급 알림 · 기관 내부망 구분은 서버에 없어 '—' · 준비 중.
import { auth, cases, schedule, tasks } from '@cw/api/endpoints';
import { parseBackendTime, pad2, toDateOnly, toDateTime } from '@cw/data/time';
import { senior } from '../api/senior';
import { DASH } from '../data/format';

export const ROLE = { ADMIN: '관리자', COUNSELOR: '상담사' };
export const DENIED = '관리자 화면은 관리자 계정으로만 볼 수 있어요. 담당 대상자는 후속관리 화면에서 확인해 주세요.';
/** 사이드바 숫자 배지(안부 연계 앱 · 보안 이벤트)는 공통 값이 없어 비운다. */
export const SIDE = { cntApp: '', cntSec: '' };

export function errMsg(error, fallback) {
  if (!error) return '';
  if (error.status === 403) return DENIED;
  return error.message || fallback;
}

/** 상담사 상세 주소. 디자인은 브라우저 저장소로 넘기지만 여기서는 ?user= 로 넘긴다. */
export function staffHref(userId) {
  return userId ? `#/AdminCounselor?user=${encodeURIComponent(userId)}` : '#/AdminAccounts';
}

/** 'lee.seoyeon' 처럼 이메일 앞부분(디자인의 기관 ID 자리). */
export function loginId(email) {
  return email ? String(email).split('@')[0] : DASH;
}

/** 계정 상태 칩. 비활성(관리자 정지) · 잠김(로그인 실패) · 휴면 · 활성. */
export function userState(u) {
  if (!u.is_active) return { st: '비활성', stCls: 'chip c-check', op: 0.6, on: false };
  if (u.is_locked) return { st: '잠김', stCls: 'chip c-urgent', op: 1, on: true };
  if (u.dormant_at) return { st: '휴면', stCls: 'chip c-check', op: 1, on: true };
  return { st: '활성', stCls: 'chip c-ok', op: 1, on: true };
}

/** '11/17 09:14'(사용자 시간대). */
export function mdhm(iso) {
  const d = iso ? parseBackendTime(iso) : null;
  return d ? `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}` : DASH;
}
export { toDateOnly, toDateTime };

export function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** 이번 주 월~일(YYYY-MM-DD). */
export function weekRange() {
  const d = new Date();
  const mon = new Date(d.getFullYear(), d.getMonth(), d.getDate() - ((d.getDay() + 6) % 7));
  const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
  const iso = (x) => `${x.getFullYear()}-${pad2(x.getMonth() + 1)}-${pad2(x.getDate())}`;
  return [iso(mon), iso(sun)];
}

/** 고령자 사례 전체(쪽을 모두 받음). 대상자가 적어 한 번에 받는다. */
export async function loadSeniorCases() {
  const all = [];
  for (let page = 1; page <= 50; page += 1) {
    const res = await cases.list({ subject_type: 'SENIOR', page, page_size: 100 });
    all.push(...res.items);
    if (page >= res.meta.total_pages || res.items.length === 0) break;
  }
  return all;
}

/** 처리 대기 업무 전체(관리자는 모든 사례 — 아동 사례도 섞여 오므로 부르는 쪽이 고령자 사례만 고른다). */
async function loadTasks() {
  const all = [];
  for (let page = 1; page <= 10; page += 1) {
    const res = await tasks.list({ page, page_size: 100 });
    all.push(...res.items);
    if (page >= res.meta.total_pages || res.items.length === 0) break;
  }
  return all;
}

/** 최근 로그인 성공 기록에서 계정마다 가장 최근 접속 IP(최근 100건 안에서). */
export async function loadLoginIps() {
  const page = await auth.auditLogs({ action: 'LOGIN', status: 'SUCCESS', page_size: 100 });
  const ips = new Map();
  page.items.forEach((log) => {
    if (log.actor_id && log.ip_address && !ips.has(log.actor_id)) ips.set(log.actor_id, log.ip_address);
  });
  return ips;
}

/** 진행 중(종결 안 됨) 고령자 사례. */
export const isOpenCase = (r) => r.case_status !== 'CLOSED' && r.care_status !== 'SERVICE_ENDED';

/** 담당 상담사가 비활성(또는 없음)인 진행 중 사례 = 재배정 필요. */
export function needsReassign(row, users) {
  if (!isOpenCase(row)) return false;
  const u = users.find((x) => x.id === row.counselor_id);
  return !u || !u.is_active;
}

// ---------------------------------------------------------------- 관리자 홈(웹 · 태블릿)

export async function loadAdminHome() {
  const users = await auth.listUsers(); // 관리자가 아니면 403 — 여기서 멈춘다
  const [wk0, wk1] = weekRange();
  const [ov, logs, events, taskItems] = await Promise.all([
    senior.overview(),
    auth.auditLogs({ action: 'LOGIN', page_size: 8 }).then((p) => p.items).catch(() => null),
    schedule.list({ from: wk0, to: wk1 }).then((r) => r.items || []).catch(() => null),
    loadTasks().catch(() => null),
  ]);
  return { users, ov, logs, events, taskItems };
}

const REVIEW = new Set(['REVIEW_TRANSCRIPT', 'REVIEW_ANALYSIS']);

/** 디자인 로직 결과(base) 위에 서버 값을 덮는다. */
export function adminHomeVals(base, shell, data) {
  const goUrgent = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const el = document.getElementById('urgent');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  const uFilters = (base.uFilters || []).map((f, i) => ({ ...f, label: i === 0 ? `전체 ${DASH}` : `확인 전 ${DASH}` }));
  const urgent = [{
    t: DASH, elder: DASH, cid: '', msg: '안부 연계 앱 긴급 알림은 준비 중이에요.', who: DASH,
    st: DASH, stCls: 'note', pending: false, btnLabel: '', btnCls: '', nudge: undefined,
  }];
  const empty = {
    ...base, ...shell, ...SIDE, goUrgent, uFilters, urgent,
    activeCases: DASH, activeNote: '', pendingCnt: DASH, urgentNote: '안부 연계 앱 준비 중',
    counselorOn: DASH, counselorTotal: '', counselorNote: '', access: [], load: [], msg: '',
  };
  if (data.error) return { ...empty, urgent: [], msg: errMsg(data.error, '기관 현황을 불러오지 못했어요.') };
  const d = data.data;
  if (!d) return empty;

  const { users, ov, logs, events, taskItems } = d;
  const rows = ov.rows;
  const open = rows.filter(isOpenCase);
  const counselors = users.filter((u) => u.role === 'COUNSELOR');
  const on = counselors.filter((u) => u.is_active).length;
  const reassign = rows.filter((r) => needsReassign(r, users)).length;

  const byId = new Map(users.map((u) => [u.id, u]));
  const access = (logs || []).map((log) => {
    const ok = log.status === 'SUCCESS';
    const u = log.actor_id ? byId.get(log.actor_id) : null;
    return {
      t: mdhm(log.created_at), name: log.actor_name || '알 수 없음', uid: u ? loginId(u.email) : DASH,
      ev: ok ? '로그인 성공' : '로그인 실패', evCls: ok ? 'chip c-ok' : 'chip c-urgent',
      ip: log.ip_address || DASH, net: DASH, netCls: 'note',
    };
  });

  const [wk0, wk1] = weekRange();
  const caseIds = new Set(rows.map((r) => r.case_id));
  const week = (events || []).filter((e) => e.kind === 'CONSULT' && e.case_id && caseIds.has(e.case_id) && e.date >= wk0 && e.date <= wk1);
  const review = (taskItems || []).filter((t) => caseIds.has(t.case_id) && REVIEW.has(t.task_type));
  const staff = users.filter((u) => u.role === 'COUNSELOR' || rows.some((r) => r.counselor_id === u.id));
  const counts = staff.map((u) => open.filter((r) => r.counselor_id === u.id).length);
  const max = Math.max(1, ...counts);
  const load = staff.map((u, i) => {
    const mine = new Set(rows.filter((r) => r.counselor_id === u.id).map((r) => r.case_id));
    const role = ROLE[u.role] || '상담사';
    return {
      name: u.name, ini: (u.name || '?').slice(0, 1), rank: u.is_active ? role : `${role} · 비활성`,
      cases: counts[i], w: `${Math.round((counts[i] / max) * 100)}%`, hi: DASH,
      week: events ? week.filter((e) => mine.has(e.case_id)).length : DASH,
      stt: taskItems ? review.filter((t) => mine.has(t.case_id)).length : DASH,
      note: DASH,
    };
  });

  const miss = [logs ? '' : '최근 접속 기록', events ? '' : '이번 주 일정', taskItems ? '' : '기록 확인 대기'].filter(Boolean);
  return {
    ...empty,
    activeCases: String(open.length),
    activeNote: `상담사 ${new Set(open.map((r) => r.counselor_id).filter(Boolean)).size}명 담당`,
    counselorOn: String(on), counselorTotal: ` / ${counselors.length}`,
    counselorNote: `비활성 ${counselors.length - on}명 · 재배정 필요 ${reassign}건`,
    access, load,
    msg: miss.length ? `${miss.join(' · ')}을(를) 불러오지 못했어요. 새로 고침해 주세요.` : '',
  };
}
