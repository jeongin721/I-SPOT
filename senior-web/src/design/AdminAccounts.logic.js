// AdminAccounts 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminAccounts.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { f: 'all', show: false, name: '', uid: '', err: false, msg: '', extra: [], act: {} }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const BASE = [
    ['이서연', 'lee.seoyeon', '', '10', '2026-10-15 09:14', '192.168.1.12', true], ['정다은', 'jung.daeun', '', '9', '2026-10-15 09:01', '192.168.1.8', true],
    ['한승호', 'han.seungho', '', '11', '2026-10-15 08:52', '192.168.1.21', true], ['박지훈', 'park.jihoon', '', '8', '2026-10-14 22:03', '211.36.142.9', true],
    ['오유진', 'oh.yujin', '', '4 · 재배정 필요', '2026-09-12 17:30', '192.168.1.30', false], ['김민준', 'kim.minjun', '', '—', '2026-10-15 08:40', '192.168.1.2', true]
  ];
  const all = BASE.concat(s.extra).map((a) => { const on = s.act[a[1]] === undefined ? a[6] : s.act[a[1]]; return { a, on }; });
  const remember = (o) => { const v = JSON.stringify(o); try { window.localStorage.setItem('ispot-staff', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-staff', v); } catch (e) {} try { window.top.__ispotStaff = v; } catch (e) {} window.__ispotStaff = v; };
  const rows = all.filter((x) => s.f === 'all' || (s.f === 'on' ? x.on : !x.on)).map(({ a, on }) => ({
    name: a[0], ini: a[0].slice(0, 1), uid: a[1], cases: a[3], last: a[4], ip: a[5], ext: a[5] !== '—' && !a[5].startsWith('192.168.'),
    st: on ? '활성' : '비활성', stCls: on ? 'chip c-ok' : 'chip c-check', op: on ? 1 : 0.6,
    pick: () => remember({ name: a[0], uid: a[1], cases: a[3], last: a[4], ip: a[5], on }) }));
  const onCnt = all.filter((x) => x.on).length;
  const create = () => { const n = s.name.trim(); const u = s.uid.trim();
    if (!n || !u) { this.setState({ err: true }); return; }
    this.setState({ extra: [...s.extra, [n, u, '', '0', '접속 기록 없음', '—', true]], show: false, name: '', uid: '', err: false, msg: `${n} (${u}) 계정을 만들었어요 · 임시 비밀번호 발급됨` }); };
  return { rows, showForm: s.show, formErr: s.err, fName: s.name, fId: s.uid, created: !!s.msg, createdMsg: s.msg,
    setName: (e) => this.setState({ name: e.target.value }), setId: (e) => this.setState({ uid: e.target.value }),
    toggleForm: () => this.setState({ show: !s.show, err: false }), create, formBtnLabel: s.show ? '닫기' : '+ 계정 생성', formBtnCls: s.show ? 'btn-s' : 'btn-p',
    filters: segOf('f', s.f, [['all', `전체 ${all.length}`], ['on', `활성 ${onCnt}`], ['off', `비활성 ${all.length - onCnt}`]]) };
}
}
