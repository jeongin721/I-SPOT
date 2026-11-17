// AdminHome 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminHome.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { uf: 'all', nudged: {} }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const now = new Date(); const W = ['일', '월', '화', '수', '목', '금', '토'];
  const dateLabel = `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${W[now.getDay()]}요일`;
  const U = [
    { id: 'u1', t: '오늘 08:12', elder: '박영수', cid: 'C-2026-0277', msg: '위기 신호 · “요즘은 그냥 다 그만두고 싶어요”', who: '이서연', ok: false, wait: '1시간 50분 경과' },
    { id: 'u2', t: '어제 21:40', elder: '한동길', cid: 'C-2026-0418', msg: '안부 무응답 · 48시간째 응답 없음', who: '정다은', ok: true, at: '어제 21:58 확인' },
    { id: 'u3', t: '어제 17:05', elder: '임춘자', cid: 'C-2026-0366', msg: '연락 요청 버튼 3회 연속 · “상담사님 목소리 좀 듣고 싶어요”', who: '박지훈', ok: true, at: '어제 17:20 확인' },
    { id: 'u4', t: '10/13 22:31', elder: '오정숙', cid: 'C-2026-0402', msg: '위기 신호 · “밥을 이틀째 못 먹었어요”', who: '한승호', ok: false, wait: '1일 11시간 경과' }
  ];
  const pend = U.filter((u) => !u.ok);
  const urgent = (s.uf === 'pending' ? pend : U).map((u) => { const n = !!s.nudged[u.id];
    return { ...u, pending: !u.ok, st: u.ok ? u.at : `확인 전 · ${u.wait}`, stCls: u.ok ? 'chip c-ok' : 'chip c-urgent',
      btnLabel: n ? '다시 알림 보냄 ✓' : '담당자에게 다시 알림', btnCls: n ? 'btn-s' : 'btn-p', nudge: () => this.setState({ nudged: { ...s.nudged, [u.id]: !n } }) }; });
  const A = [
    ['10/15 09:14', '이서연', 'lee.seoyeon', 'ok', '192.168.1.12', 'in'], ['10/15 09:01', '정다은', 'jung.daeun', 'ok', '192.168.1.8', 'in'],
    ['10/15 08:52', '한승호', 'han.seungho', 'ok', '192.168.1.21', 'in'], ['10/15 08:47', '알 수 없음', 'admin', 'fail', '203.0.113.44', 'out'],
    ['10/15 08:46', '알 수 없음', 'lee.seoyeon', 'fail', '203.0.113.44', 'out'], ['10/15 08:45', '한승호', 'han.seungho', 'otp', '192.168.1.21', 'in'],
    ['10/15 08:40', '김민준', 'kim.minjun', 'ok', '192.168.1.2', 'in'], ['10/14 22:03', '박지훈', 'park.jihoon', 'ok', '211.36.142.9', 'out']
  ];
  const EV = { ok: ['로그인 성공', 'chip c-ok'], fail: ['로그인 실패', 'chip c-urgent'], otp: ['OTP 실패', 'chip c-check'] };
  const access = A.map((r) => ({ t: r[0], name: r[1], uid: r[2], ev: EV[r[3]][0], evCls: EV[r[3]][1], ip: r[4], net: r[5] === 'in' ? '기관 내부망' : '외부', netCls: r[5] === 'in' ? 'note' : 'chip c-check' }));
  const L = [['이서연', '선임 상담사', 10, 3, 4, 2, 2, 3], ['정다은', '상담사', 9, 2, 5, 0, 1, 1], ['한승호', '상담사', 11, 3, 3, 1, 2, 1], ['박지훈', '상담사', 8, 1, 4, 1, 0, 1], ['오유진', '상담사 · 비활성', 4, 2, 0, 0, 0, 0]];
  const load = L.map((r) => ({ name: r[0], ini: r[0].slice(0, 1), rank: r[1], cases: r[2], w: `${Math.round(r[2] / 12 * 100)}%`, hi: r[3], week: r[4], stt: r[5], note: r[6] }));
  return { dateLabel, urgent, access, load, pendingCnt: pend.length, urgentCnt: U.length,
    uFilters: segOf('uf', s.uf, [['all', `전체 ${U.length}`], ['pending', `확인 전 ${pend.length}`]]) };
}
}
