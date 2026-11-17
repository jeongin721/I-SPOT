// AdminCases 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminCases.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { who: 'all', risk: 'all', sort: 'date', q: '' }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const TODAY = Date.parse('2026-10-15');
  const STAFF = [['이서연', 'lee.seoyeon', '2026-10-15 09:14', '192.168.1.12', true], ['정다은', 'jung.daeun', '2026-10-15 09:01', '192.168.1.8', true], ['한승호', 'han.seungho', '2026-10-15 08:52', '192.168.1.21', true], ['박지훈', 'park.jihoon', '2026-10-14 22:03', '211.36.142.9', true], ['오유진', 'oh.yujin', '2026-09-12 17:30', '192.168.1.30', false]];
  // [사례 ID, 성함, 연령(만), 담당, 위기도, 접수일, 최근 상담, 진행 단계]
  const C = [
    ['C-2026-0277', '박영수', 76, '이서연', '위기', '2026-06-02', '10/13', 'ing'], ['C-2026-0351', '김순자', 82, '이서연', '집중', '2026-07-28', '10/08', 'ing'],
    ['C-2026-0412', '오금자', 77, '이서연', '집중', '2026-08-19', '10/06', 'ing'], ['C-2026-0389', '서복례', 85, '이서연', '관심', '2026-09-03', '10/08', 'ing'],
    ['C-2026-0338', '이정희', 69, '이서연', '관심', '2026-08-05', '10/07', 'ing'], ['C-2026-0374', '최만석', 88, '이서연', '집중', '2026-09-25', '10/08', 'ing'],
    ['C-2026-0298', '윤기철', 73, '이서연', '관심', '2026-06-20', '10/13', 'ing'], ['C-2026-0229', '정말순', 91, '이서연', '일반', '2026-05-14', '10/02', 'ing'],
    ['C-2026-0312', '강덕수', 80, '이서연', '관심', '2026-04-08', '10/14', 'close'], ['C-2026-0251', '한옥분', 79, '이서연', '일반', '2026-05-30', '10/15', 'close'],
    ['C-2026-0418', '한동길', 78, '정다은', '위기', '2026-09-22', '10/14', 'ing'], ['C-2026-0425', '홍성택', 83, '정다은', '관심', '2026-10-06', '10/10', 'new'],
    ['C-2026-0347', '송미자', 70, '정다은', '관심', '2026-07-21', '10/07', 'ing'], ['C-2026-0361', '김화자', 83, '정다은', '관심', '2026-08-11', '10/09', 'ing'],
    ['C-2026-0302', '이분례', 90, '정다은', '일반', '2026-06-24', '10/01', 'ing'], ['C-2026-0244', '박말자', 89, '정다은', '일반', '2026-05-22', '10/12', 'close'],
    ['C-2026-0395', '최봉순', 88, '정다은', '집중', '2026-09-08', '10/13', 'ing'], ['C-2026-0326', '정기용', 68, '정다은', '관심', '2026-07-30', '10/02', 'ing'],
    ['C-2026-0218', '강필순', 80, '정다은', '일반', '2026-05-06', '09/29', 'ing'],
    ['C-2026-0402', '오정숙', 72, '한승호', '위기', '2026-09-30', '10/13', 'ing'], ['C-2026-0359', '문병철', 86, '한승호', '관심', '2026-08-20', '10/06', 'ing'],
    ['C-2026-0431', '노재만', 79, '한승호', '관심', '2026-10-09', '10/11', 'new'], ['C-2026-0285', '윤정임', 76, '한승호', '일반', '2026-06-12', '10/05', 'ing'],
    ['C-2026-0408', '장경희', 72, '한승호', '집중', '2026-09-26', '10/14', 'ing'], ['C-2026-0333', '임태식', 81, '한승호', '관심', '2026-08-02', '10/08', 'ing'],
    ['C-2026-0267', '한복희', 78, '한승호', '일반', '2026-06-05', '10/10', 'ing'], ['C-2026-0236', '오갑식', 75, '한승호', '일반', '2026-05-19', '10/13', 'close'],
    ['C-2026-0381', '신용철', 70, '한승호', '관심', '2026-08-28', '10/09', 'ing'], ['C-2026-0414', '권영숙', 80, '한승호', '관심', '2026-09-24', '10/12', 'ing'],
    ['C-2026-0273', '황인호', 82, '한승호', '일반', '2026-06-09', '10/01', 'ing'],
    ['C-2026-0366', '임춘자', 84, '박지훈', '집중', '2026-08-26', '10/14', 'ing'], ['C-2026-0384', '배종호', 74, '박지훈', '관심', '2026-08-30', '10/04', 'ing'],
    ['C-2026-0428', '남순이', 87, '박지훈', '관심', '2026-10-08', '10/13', 'new'], ['C-2026-0309', '안광수', 73, '박지훈', '일반', '2026-07-03', '10/07', 'ing'],
    ['C-2026-0354', '송재덕', 79, '박지훈', '관심', '2026-08-13', '10/10', 'ing'], ['C-2026-0291', '류상근', 84, '박지훈', '일반', '2026-06-17', '10/08', 'ing'],
    ['C-2026-0399', '전만수', 85, '박지훈', '집중', '2026-09-15', '10/14', 'ing'], ['C-2026-0257', '고영배', 71, '박지훈', '일반', '2026-06-01', '10/02', 'close'],
    ['C-2026-0377', '서영자', 81, '오유진', '관심', '2026-08-18', '09/11', 'move'], ['C-2026-0342', '문옥자', 77, '오유진', '관심', '2026-07-24', '09/09', 'move'],
    ['C-2026-0318', '양순덕', 86, '오유진', '일반', '2026-07-08', '09/04', 'move'], ['C-2026-0393', '손정란', 74, '오유진', '위기', '2026-09-05', '09/10', 'move']
  ];
  const ST = { ing: ['사례관리 진행', 'chip c-normal'], new: ['초기 상담', 'chip c-mid'], close: ['후속관리', 'chip c-check'], move: ['재배정 필요', 'chip c-urgent'] };
  const RC = { '위기': 'chip c-hi', '집중': 'chip c-hi', '관심': 'chip c-mid', '일반': 'chip c-lo' }; const RK = { '위기': 0, '집중': 1, '관심': 2, '일반': 3 };
  const period = (d) => { const days = Math.round((TODAY - Date.parse(d)) / 864e5); if (days < 30) return days + '일'; const m = Math.max(1, Math.floor(days / 30.44)); return m >= 12 ? '1년 ' + (m - 12) + '개월' : m + '개월'; };
  const q = (s.q || '').trim();
  let list = C.filter((c) => (s.who === 'all' || c[3] === s.who) && (s.risk === 'all' || c[4] === s.risk) && (!q || c[1].indexOf(q) >= 0 || c[0].indexOf(q) >= 0));
  list = list.slice().sort((a, b) => s.sort === 'risk' ? (RK[a[4]] - RK[b[4]] || b[5].localeCompare(a[5])) : s.sort === 'long' ? a[5].localeCompare(b[5]) : b[5].localeCompare(a[5]));
  const remember = (st) => { const o = { name: st[0], uid: st[1], cases: String(C.filter((c) => c[3] === st[0]).length) + (st[4] ? '' : ' · 재배정 필요'), last: st[2], ip: st[3], on: st[4] }; const v = JSON.stringify(o); try { window.localStorage.setItem('ispot-staff', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-staff', v); } catch (e) {} try { window.top.__ispotStaff = v; } catch (e) {} window.__ispotStaff = v; };
  const rows = list.map((c) => { const st = STAFF.find((x) => x[0] === c[3]);
    return { id: c[0], name: c[1], ini: c[1].slice(0, 1), age: '만 ' + c[2] + '세', who: c[3], risk: c[4], rCls: RC[c[4]], date: c[5], period: period(c[5]), last: c[6], stage: ST[c[7]][0], stCls: ST[c[7]][1], pick: () => remember(st) }; });
  const hi = C.filter((c) => c[4] === '위기' || c[4] === '집중').length, cl = C.filter((c) => c[7] === 'close').length, mv = C.filter((c) => c[7] === 'move').length;
  return { rows, empty: rows.length === 0, q: s.q, setQ: (e) => this.setState({ q: e.target.value }),
    kpis: [
      { label: '전체 사례', v: C.length + '건', note: '상담사 ' + STAFF.length + '명 담당', fg: 'inherit', bar: '' },
      { label: '위기도 위기·집중', v: hi + '건', note: '전체의 ' + Math.round(hi / C.length * 100) + '%', fg: '#A33B2E', bar: 'inset 0 4px 0 #A33B2E' },
      { label: '후속관리', v: cl + '건', note: '종결 평가 대상', fg: 'inherit', bar: '' },
      { label: '재배정 필요', v: mv + '건', note: '담당 상담사 비활성', fg: 'inherit', bar: '' }
    ],
    staffF: segOf('who', s.who, [['all', '전체 ' + C.length]].concat(STAFF.map((x) => [x[0], x[0] + ' ' + C.filter((c) => c[3] === x[0]).length]))),
    riskF: segOf('risk', s.risk, [['all', '전체'], ['위기', '위기'], ['집중', '집중'], ['관심', '관심'], ['일반', '일반']]),
    sortF: segOf('sort', s.sort, [['date', '최근 접수'], ['risk', '위기도'], ['long', '관리 기간']]),
    countLabel: '사례 ' + rows.length + '건 표시 · 2026-10-15 기준' };
}
}
