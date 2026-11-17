// AdminStats 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminStats.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {
themeRead() {
  const K = 'ispot-theme'; let v = null;
  try { v = window.localStorage.getItem(K); } catch (e) {}
  if (!v) { try { v = window.sessionStorage.getItem(K); } catch (e) {} }
  if (!v) { try { v = window.top.__ispotTheme; } catch (e) {} }
  if (!v) { v = window.__ispotTheme; }
  return v === 'dark';
}
themeWrite(dark) {
  const K = 'ispot-theme'; const v = dark ? 'dark' : 'light';
  try { window.localStorage.setItem(K, v); } catch (e) {}
  try { window.sessionStorage.setItem(K, v); } catch (e) {}
  try { window.top.__ispotTheme = v; } catch (e) {}
  window.__ispotTheme = v;
}
jobRead() { let v = null; try { v = window.localStorage.getItem('ispot-job'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-job'); } catch (e) {} } if (!v) { try { v = window.top.__ispotJob; } catch (e) {} } if (!v) v = window.__ispotJob; try { return v ? JSON.parse(v) : null; } catch (e) { return null; } }
jobPhase() { const j = this.jobRead(); if (!j || !j.t) return ''; const el = Date.now() - j.t; return el < 8000 ? 'run' : el < 11000 ? 'done' : el < 11500 ? 'out' : ''; }
jobWrite(v) { try { window.localStorage.setItem('ispot-job', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-job', v); } catch (e) {} try { window.top.__ispotJob = v; } catch (e) {} window.__ispotJob = v; }
componentDidMount() {
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { p: 'year', msg: '' }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const P = {
    year: { label: '올해 누적', range: '2026-01-01 ~ 2026-10-15', f: 1, k: [412, 286, 241, '9.8%', 164, '93%', '78%'],
      trend: [['1월', 38, 20], ['2월', 35, 22], ['3월', 44, 25], ['4월', 41, 24], ['5월', 47, 28], ['6월', 43, 26], ['7월', 46, 27], ['8월', 44, 24], ['9월', 41, 23], ['10월', 33, 22]],
      types: [74, 38, 52, 31, 46, 19, 17, 9], risk: [21, 47, 132, 86], ages: [38, 61, 72, 69, 46], actors: [112, 96, 21, 14, 18, 25] },
    q3: { label: '3분기', range: '2026-07-01 ~ 2026-09-30', f: 0.318, k: [131, 92, 74, '10.4%', 158, '94%', '80%'],
      trend: [['7월', 46, 27], ['8월', 44, 24], ['9월', 41, 23]], types: [24, 12, 17, 10, 15, 6, 5, 3], risk: [7, 15, 43, 27], ages: [12, 20, 23, 22, 15], actors: [36, 31, 7, 4, 6, 8] },
    month: { label: '이번 달', range: '2026-10-01 ~ 2026-10-15', f: 0.053, k: [22, 15, 11, '8.1%', 171, '95%', '77%'],
      trend: [['10/1~7', 10, 5], ['10/8~14', 10, 5], ['10/15', 2, 1]], types: [4, 2, 3, 1, 2, 1, 1, 1], risk: [1, 3, 7, 4], ages: [2, 3, 4, 4, 2], actors: [6, 5, 1, 1, 1, 1] }
  };
  const d = P[s.p]; const f = d.f;
  const bars = (names, vals, unit) => { const tot = vals.reduce((a, b) => a + b, 0) || 1; const mx = Math.max(...vals) || 1;
    return names.map((n, i) => ({ name: n, v: `${vals[i].toLocaleString()}${unit}`, p: `${Math.round(vals[i] / tot * 1000) / 10}%`, w: `${Math.round(vals[i] / mx * 100)}%`, tip: `${n} ${vals[i]}${unit}` })); };
  const sc = (arr) => arr.map((v) => Math.max(0, Math.round(v * f)));
  const kpis = [
    { label: '신규 접수', v: `${d.k[0]}건`, sub: d.label }, { label: '사례관리 개시', v: `${d.k[1]}건`, sub: `접수 중 ${Math.round(d.k[1] / d.k[0] * 100)}%` },
    { label: '종결', v: `${d.k[2]}건`, sub: '종결보고서 승인 기준' }, { label: '위기 재발률', v: d.k[3], sub: '종결 후 1년 내' },
    { label: '평균 사례관리 기간', v: `${d.k[4]}일`, sub: '접수부터 종결까지' }, { label: '72시간 내 초기상담', v: d.k[5], sub: '첫 상담(내방·방문·전화) 기준' },
    { label: '안부 앱 응답률', v: d.k[6], sub: '연결 어르신 안부 응답 기준' }
  ];
  const mx = Math.max(...d.trend.map((t) => Math.max(t[1], t[2])));
  const trend = d.trend.map((t) => ({ label: t[0], a: t[1], b: t[2], ha: `${Math.round(t[1] / mx * 160)}px`, hb: `${Math.round(t[2] / mx * 160)}px`, tip: `${t[0]} 신규 ${t[1]}건 · 종결 ${t[2]}건` }));
  const rTot = d.risk.reduce((a, b) => a + b, 0);
  const risk = [['위기', '#A33B2E'], ['집중', '#1F3A56'], ['관심', '#5FA4D6'], ['일반', '#A0B0BB']].map(([n, c], i) => ({ name: n, c, v: d.risk[i], p: `${Math.round(d.risk[i] / rTot * 100)}%`, w: `${d.risk[i] / rTot * 100}%`, tip: `위기도 ${n} ${d.risk[i]}건` }));
  const rep = sc([47, 63, 118, 61, 22, 18, 54, 29]); const repTot = rep.reduce((a, b) => a + b, 0);
  const S = [['이서연', '선임 상담사', 10, 96, 91, 14], ['정다은', '상담사', 9, 88, 96, 12], ['한승호', '상담사', 11, 102, 84, 16], ['박지훈', '상담사', 8, 79, 93, 11], ['오유진', '상담사 · 비활성', 4, 41, 88, 6]];
  const sesMx = Math.max(...S.map((r) => Math.round(r[3] * f)));
  const staff = S.map((r) => { const ses = Math.round(r[3] * f); return { name: r[0], rank: r[1], cases: r[2], ses: `${ses}회`, w: `${Math.round(ses / (sesMx || 1) * 100)}%`, rate: `${r[4]}%`, rCls: r[4] < 90 ? 'warn' : '', closed: Math.round(r[5] * f) }; });
  const say = (m) => () => this.setState({ msg: m });
  return { periodLabel: d.label, rangeLabel: d.range, kpis, trend, risk,
    trendAria: d.trend.map((t) => `${t[0]} 신규 ${t[1]} 종결 ${t[2]}`).join(', '), riskAria: risk.map((r) => `위기도 ${r.name} ${r.v}건`).join(', '),
    types: bars(['정서 · 우울', '상실 · 애도', '고립 · 외로움', '건강 · 인지', '가족관계', '경제 · 주거', '생활 적응 · 여가', '삶의 정리'], d.types, '건'), ages: bars(['65~69세', '70~74세', '75~79세', '80~84세', '85세 이상'], d.ages, '명'),
    actors: bars(['독거', '부부', '자녀 동거', '조손', '기타 친족 동거', '기타'], d.actors, '명'),
    reporters: bars(['본인', '가족', '행정복지센터', '맞춤돌봄 수행기관', '의료기관', '치매안심센터', '노인복지관 · 경로당', '기타'], rep, '건'),
    mandatoryNote: `기관 의뢰 비율 ${Math.round((rep[2] + rep[3] + rep[4] + rep[5] + rep[6]) / (repTot || 1) * 100)}%`,
    measures: bars(['노인맞춤돌봄', '정신건강복지센터', '치매안심센터', '장기요양 · 통합돌봄 창구', '노인복지관 프로그램', '노인보호전문기관'], sc([98, 46, 31, 42, 69, 7]), '건'),
    services: bars(['개별 상담(내방)', '방문 상담', '전화 안부 · 상담', '가족 상담 · 돌봄자 교육', '집단 프로그램'], sc([1820, 412, 236, 154, 88]), '회'),
    closures: bars(['목표 달성', '타 기관 연계', '장기요양 전환', '시설 입소', '이사', '본인 중단 요청', '사망'], sc([138, 31, 24, 12, 10, 15, 11]), '건'),
    staff, hasMsg: !!s.msg, msg: s.msg,
    exportXls: say(`${d.label} 통계를 엑셀 파일로 내려받을 준비가 됐어요 (${d.range})`), exportPdf: say(`${d.label} 상급 기관 보고서 PDF를 만들었어요 (${d.range})`),
    periods: segOf('p', s.p, [['month', '이번 달'], ['q3', '3분기'], ['year', '올해 누적']]) };
}
}
