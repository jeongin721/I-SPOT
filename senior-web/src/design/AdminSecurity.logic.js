// AdminSecurity 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminSecurity.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { f: 'all', done: {} }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const E = [
    ['e1', '10/15 09:14', '이서연', 'lee.seoyeon', 'ok', '192.168.1.12', 'in', '허용', ''],
    ['e2', '10/15 09:01', '정다은', 'jung.daeun', 'ok', '192.168.1.8', 'in', '허용', ''],
    ['e3', '10/15 08:47', '알 수 없음', 'admin', 'fail', '203.0.113.44', 'out', '차단 · 없는 계정', 'ip'],
    ['e4', '10/15 08:46', '알 수 없음', 'lee.seoyeon', 'fail', '203.0.113.44', 'out', '차단 · 비밀번호 틀림', 'ip2'],
    ['e5', '10/15 08:45', '한승호', 'han.seungho', 'otp', '192.168.1.21', 'in', '재시도 후 로그인', ''],
    ['e6', '10/14 22:03', '박지훈', 'park.jihoon', 'ok', '211.36.142.9', 'out', '허용 · OTP 확인', ''],
    ['e7', '10/14 21:58', '박지훈', 'park.jihoon', 'otp', '211.36.142.9', 'out', '재시도 허용', ''],
    ['e8', '10/14 07:12', '오유진', 'oh.yujin', 'fail', '175.223.10.4', 'out', '차단 · 비활성 계정', ''],
    ['e9', '10/13 23:41', '정다은', 'jung.daeun', 'lock', '175.223.18.77', 'out', '계정 잠금 · 5회 실패', 'unlock'],
    ['e10', '10/13 18:40', '박지훈', 'park.jihoon', 'ok', '192.168.1.15', 'in', '허용', '']
  ];
  const EV = { ok: ['로그인 성공', 'chip c-ok'], fail: ['로그인 실패', 'chip c-urgent'], otp: ['OTP 실패', 'chip c-check'], lock: ['로그인 실패 5회', 'chip c-urgent'] };
  const pass = (e) => s.f === 'all' || (s.f === 'lock' && e[4] === 'lock') || (s.f === 'fail' && (e[4] === 'fail' || e[4] === 'lock')) || (s.f === 'out' && e[6] === 'out') || (s.f === 'otp' && e[4] === 'otp');
  const rows = E.filter(pass).map((e) => { const d = !!s.done[e[0]];
    const lbl = e[8] === 'unlock' ? (d ? '잠금 해제됨 ✓' : '잠금 해제') : (d ? 'IP 차단됨 ✓' : 'IP 차단 목록에 추가');
    return { t: e[1], name: e[2], uid: e[3], ev: EV[e[4]][0], evCls: EV[e[4]][1], ip: e[5], net: e[6] === 'in' ? '기관 내부망' : '외부', netCls: e[6] === 'in' ? 'note' : 'chip c-check',
      res: e[8] === 'unlock' && d ? '잠금 해제 · 관리자' : e[7], hasAct: !!e[8], actLabel: lbl, act: () => this.setState({ done: { ...s.done, [e[0]]: !d } }) }; });
  const lockCnt = E.filter((e) => e[4] === 'lock' && !s.done[e[0]]).length;
  const kb = (v) => ({ cls: s.f === v ? 'on' : '', pressed: s.f === v ? 'true' : 'false', pick: () => this.setState({ f: s.f === v ? 'all' : v }) });
  return { rows, failCnt: E.filter((e) => e[4] === 'fail' && e[1].startsWith('10/15')).length, extCnt: E.filter((e) => e[6] === 'out' && (e[1].startsWith('10/15') || e[1].startsWith('10/14 2'))).length,
    otpCnt: E.filter((e) => e[4] === 'otp').length, lockCnt, kfail: kb('fail'), kout: kb('out'), kotp: kb('otp'), klock: kb('lock'),
    filters: segOf('f', s.f, [['all', '전체 접속 기록'], ['fail', '로그인 실패'], ['out', '외부 IP 접속'], ['otp', 'OTP 실패']]) };
}
}
