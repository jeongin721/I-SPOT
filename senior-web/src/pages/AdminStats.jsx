// 관리자 · 통계 · 보고 — 디자인 AdminStats.dc.html(v2). 관리자 전용 화면.
// 디자인의 예시 숫자 대신 서버의 고령자 대상자로 셀 수 있는 것만 센다(cases.list SENIOR · senior.overview · 계정 목록).
//  - 기간: 이번 달 · 이번 분기 · 올해 누적(오늘까지). 접수일 = 상담 접수일(report_date), 없으면 등록일.
//  - 신규 접수: 기간 안에 접수된 대상자 수. 사례관리 개시: 그중 상담 회차가 하나라도 있는 대상자(last_session_at).
//  - 종결: 돌봄 상태가 '서비스 종료'(senior-overview care_status SERVICE_ENDED)로 바뀐 때가 기간 안인 대상자.
//  - 추이: 올해 · 분기는 월별, 이번 달은 주별(1~7일 …) — 신규 접수 · 종결.
//  - 연령대: 기간 안 접수 대상자의 출생연도(접수 해 기준). 65세 미만 · 출생연도 없는 대상자는 뺀다.
//  - 의뢰 경로: 등록 때 적은 '의뢰 경로: …' 줄(linked_background)을 디자인 항목에 맞춘다. 맞는 항목이 없으면 기타.
//  - 상담사별: 현재 담당(진행 중) 대상자 수 · 기간 안 종결 수. 상담 회차 · 일지 작성률은 '—'.
//  - 서버에 셀 원천이 없는 것은 '—' · 준비 중: 위기 재발률 · 평균 사례관리 기간 · 72시간 내 초기상담 · 안부 앱 응답률,
//    주호소 유형(유형 분류 없음) · 위기도(고령자에는 위기도 판정이 없다) · 가구형태 · 연계 기관 · 서비스 제공 · 종결 사유.
//  - 엑셀 · PDF 내려받기는 준비 중 안내만. 관리자가 아니면 서버를 부르지 않고 안내만 보인다.
import { useDC } from '../dc';
import DesignLogic from '../design/AdminStats.logic';
import { auth, cases } from '@cw/api/endpoints';
import { senior } from '../api/senior';
import { useAsync } from '../data/useAsync';
import { useShell } from '../data/useShell';
import { DASH } from '../data/format';
import { errText } from './Step3Summary.basis';
import { utc, isAdmin, DENIED, ROLE, sideVals } from './AdminSecurity';
import View from './AdminStats.view';

const p2 = (x) => String(x).padStart(2, '0');
const isoOf = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
const caseDay = (c) => c.report_date || isoOf(utc(c.created_at));
const referral = (c) => {
  const m = /의뢰 경로:\s*([^·\n]+)/.exec(c.linked_background || '');
  return m ? m[1].trim() : null;
};

const TYPES = ['정서 · 우울', '상실 · 애도', '고립 · 외로움', '건강 · 인지', '가족관계', '경제 · 주거', '생활 적응 · 여가', '삶의 정리'];
const AGES = [['65~69세', 65, 69], ['70~74세', 70, 74], ['75~79세', 75, 79], ['80~84세', 80, 84], ['85세 이상', 85, 200]];
const ACTORS = ['독거', '부부', '자녀 동거', '조손', '기타 친족 동거', '기타'];
const REPORTERS = ['본인', '가족', '행정복지센터', '맞춤돌봄 수행기관', '의료기관', '치매안심센터', '노인복지관 · 경로당', '기타'];
const AGENCY = new Set(['행정복지센터', '맞춤돌봄 수행기관', '의료기관', '치매안심센터', '노인복지관 · 경로당']);
// 등록 화면(CaseRegister · CaseIntake)의 의뢰 경로 고르기 → 디자인 항목.
const REF_MAP = {
  본인: '본인', 가족: '가족', '행정복지센터(읍·면·동)': '행정복지센터', '노인맞춤돌봄 수행기관(생활지원사)': '맞춤돌봄 수행기관',
  의료기관: '의료기관', 치매안심센터: '치매안심센터', '노인복지관 · 경로당': '노인복지관 · 경로당',
};
const MEASURES = ['노인맞춤돌봄', '정신건강복지센터', '치매안심센터', '장기요양 · 통합돌봄 창구', '노인복지관 프로그램', '노인보호전문기관'];
const SERVICES = ['개별 상담(내방)', '방문 상담', '전화 안부 · 상담', '가족 상담 · 돌봄자 교육', '집단 프로그램'];
const CLOSURES = ['목표 달성', '타 기관 연계', '장기요양 전환', '시설 입소', '이사', '본인 중단 요청', '사망'];

function period(p, now) {
  const y = now.getFullYear();
  const m = now.getMonth();
  const today = isoOf(now);
  if (p === 'month') return { label: '이번 달', from: `${y}-${p2(m + 1)}-01`, to: today };
  if (p === 'q') {
    const q = Math.floor(m / 3);
    return { label: `${q + 1}분기`, from: `${y}-${p2(q * 3 + 1)}-01`, to: today };
  }
  return { label: '올해 누적', from: `${y}-01-01`, to: today };
}

function binsOf(p, from, to) {
  const out = [];
  const [y, m0] = from.split('-').map(Number);
  if (p === 'month') {
    const last = Number(to.slice(8, 10));
    for (let d = 1; d <= last; d += 7) {
      const e = Math.min(last, d + 6);
      out.push({ label: d === e ? `${m0}/${d}` : `${m0}/${d}~${e}`, from: `${y}-${p2(m0)}-${p2(d)}`, to: `${y}-${p2(m0)}-${p2(e)}` });
    }
    return out;
  }
  const mEnd = Number(to.slice(5, 7));
  for (let m = m0; m <= mEnd; m++) out.push({ label: `${m}월`, from: `${y}-${p2(m)}-01`, to: `${y}-${p2(m)}-31` });
  return out;
}

const dashBars = (names) => names.map((n) => ({ name: n, v: DASH, p: '', w: '0%', tip: `${n} ${DASH}` }));
const bars = (names, vals, unit) => {
  const tot = vals.reduce((a, b) => a + b, 0);
  const mx = Math.max(...vals) || 1;
  return names.map((n, i) => ({
    name: n, v: `${vals[i].toLocaleString()}${unit}`, p: tot ? `${Math.round((vals[i] / tot) * 1000) / 10}%` : '0%',
    w: `${Math.round((vals[i] / mx) * 100)}%`, tip: `${n} ${vals[i]}${unit}`,
  }));
};

class Logic extends DesignLogic {
  renderValsBase() {
    const s = this.state;
    const { shell, data } = this.props;
    const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v, msg: '' }) }));
    const now = new Date();
    const pd = period(s.p, now);
    const say = (m) => () => this.setState({ msg: m });
    const KPI = [['신규 접수', pd.label], ['사례관리 개시', DASH], ['종결', '서비스 종료 기준'], ['위기 재발률', '준비 중'], ['평균 사례관리 기간', '준비 중'], ['72시간 내 초기상담', '준비 중'], ['안부 앱 응답률', '준비 중']];
    const base = {
      ...sideVals(shell),
      periodLabel: pd.label, rangeLabel: `${pd.from} ~ ${pd.to}`,
      kpis: KPI.map(([label, sub]) => ({ label, v: DASH, sub })),
      trend: [], trendAria: '', risk: [['위기', '#A33B2E'], ['집중', '#1F3A56'], ['관심', '#5FA4D6'], ['일반', '#A0B0BB']].map(([name, c]) => ({ name, c, v: DASH, p: '', w: '0%', tip: `위기도 ${name} ${DASH}` })),
      riskAria: '위기도 준비 중',
      types: dashBars(TYPES), ages: dashBars(AGES.map((a) => a[0])), actors: dashBars(ACTORS), reporters: dashBars(REPORTERS),
      mandatoryNote: `기관 의뢰 비율 ${DASH}`,
      measures: dashBars(MEASURES), services: dashBars(SERVICES), closures: dashBars(CLOSURES),
      staff: [], hasMsg: !!s.msg, msg: s.msg,
      exportXls: say('엑셀로 내려받기는 준비 중이에요.'), exportPdf: say('보고서 PDF 만들기는 준비 중이에요.'),
      periods: segOf('p', s.p, [['month', '이번 달'], ['q', period('q', now).label], ['year', '올해 누적']]),
    };
    const withMsg = (m) => ({ ...base, hasMsg: true, msg: m });
    if (shell.ready && !isAdmin(shell)) return withMsg(DENIED);
    if (data.error) return withMsg(errText(data.error, '통계를 불러오지 못했어요.'));
    const d = data.data;
    if (!d) return data.loading ? withMsg('불러오는 중…') : base;

    const inR = (day, a = pd.from, b = pd.to) => day && day >= a && day <= b;
    const all = d.cases;
    const R = all.filter((c) => inR(caseDay(c)));
    const started = R.filter((c) => c.last_session_at).length;
    const endDay = (r) => (r.care_status === 'SERVICE_ENDED' && r.care_status_changed_at ? isoOf(utc(r.care_status_changed_at)) : null);
    const ended = d.ov.rows.filter((r) => inR(endDay(r)));

    const kpis = base.kpis.slice();
    kpis[0] = { ...kpis[0], v: `${R.length}건` };
    kpis[1] = { ...kpis[1], v: `${started}건`, sub: R.length ? `접수 중 ${Math.round((started / R.length) * 100)}%` : '접수 없음' };
    kpis[2] = { ...kpis[2], v: `${ended.length}건` };

    const bins = binsOf(s.p, pd.from, pd.to);
    const tv = bins.map((b) => [R.filter((c) => inR(caseDay(c), b.from, b.to)).length, ended.filter((r) => inR(endDay(r), b.from, b.to)).length]);
    const mx = Math.max(1, ...tv.flat());
    const trend = bins.map((b, i) => ({
      label: b.label, a: tv[i][0], b: tv[i][1], ha: `${Math.round((tv[i][0] / mx) * 160)}px`, hb: `${Math.round((tv[i][1] / mx) * 160)}px`,
      tip: `${b.label} 신규 ${tv[i][0]}건 · 종결 ${tv[i][1]}건`,
    }));

    const ageOf = (c) => (c.child_birth_year ? Number(caseDay(c).slice(0, 4)) - Number(c.child_birth_year) : null);
    const ages = bars(AGES.map((a) => a[0]), AGES.map(([, lo, hi]) => R.filter((c) => ageOf(c) !== null && ageOf(c) >= lo && ageOf(c) <= hi).length), '명');

    const refs = R.map(referral).filter(Boolean).map((x) => REF_MAP[x] || '기타');
    const reporters = refs.length ? bars(REPORTERS, REPORTERS.map((n) => refs.filter((x) => x === n).length), '건') : base.reporters;
    const mandatoryNote = refs.length ? `기관 의뢰 비율 ${Math.round((refs.filter((x) => AGENCY.has(x)).length / refs.length) * 100)}%` : base.mandatoryNote;

    const users = new Map(d.users.map((u) => [u.id, u]));
    const ids = new Set(d.users.filter((u) => u.is_active && u.role === 'COUNSELOR').map((u) => u.id));
    all.forEach((c) => c.counselor_id && ids.add(c.counselor_id));
    const staff = [...ids].map((id) => {
      const u = users.get(id);
      const mine = all.filter((c) => c.counselor_id === id);
      const name = u ? u.name : (mine[0] && mine[0].counselor_name) || DASH;
      const rank = (u ? ROLE[u.role] || '상담사' : '상담사') + (u && !u.is_active ? ' · 비활성' : '');
      return {
        name, rank, cases: mine.filter((c) => c.status === 'ACTIVE').length, ses: DASH, w: '0%', rate: DASH, rCls: '',
        closed: ended.filter((r) => r.counselor_id === id).length,
      };
    }).sort((a, b) => b.cases - a.cases);

    return {
      ...base, kpis, trend, trendAria: trend.map((t) => `${t.label} 신규 ${t.a} 종결 ${t.b}`).join(', '),
      ages, reporters, mandatoryNote, staff,
    };
  }
}

export default function AdminStats(props) {
  const shell = useShell();
  const admin = isAdmin(shell);
  const data = useAsync(async () => {
    if (!shell.ready || !admin) return null;
    const list = [];
    for (let page = 1; page <= 50; page++) {
      const res = await cases.list({ subject_type: 'SENIOR', page, page_size: 100 });
      list.push(...res.items);
      if (page >= (res.meta.total_pages || 1)) break;
    }
    const [ov, users] = await Promise.all([senior.overview(), auth.listUsers()]);
    return { cases: list, ov, users };
  }, [shell.ready, admin]);
  const v = useDC(Logic, { ...props, shell, data });
  return <View v={v} />;
}
