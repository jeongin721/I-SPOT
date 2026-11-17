// AdminCounselor 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminCounselor.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { act: null, pw: false, msg: '' }; }
renderValsBase() {
  const s = this.state;
  let pick = null; const rd = (v) => { try { return v ? JSON.parse(v) : null; } catch (e) { return null; } };
  try { pick = rd(window.localStorage.getItem('ispot-staff')); } catch (e) {}
  if (!pick) { try { pick = rd(window.sessionStorage.getItem('ispot-staff')); } catch (e) {} }
  if (!pick) { try { pick = rd(window.top.__ispotStaff); } catch (e) {} }
  if (!pick) pick = rd(window.__ispotStaff);
  if (!pick) pick = { name: '이서연', uid: 'lee.seoyeon', cases: '10', last: '2026-10-15 09:14', ip: '192.168.1.12', on: true };
  const INFO = {
    'lee.seoyeon': ['2025-03-02', '2026-08-12', true, [true, true, false], '09:00'], 'jung.daeun': ['2025-07-14', '2026-09-01', true, [true, true, true], '08:30'],
    'han.seungho': ['2024-11-04', '2026-06-20', true, [true, false, true], '09:00'], 'park.jihoon': ['2025-09-22', '2026-10-01', true, [true, true, false], '13:00'],
    'oh.yujin': ['2024-05-13', '2026-04-03', true, [true, true, false], '09:00'], 'kim.minjun': ['2023-02-01', '2026-09-15', true, [true, false, false], '08:30']
  };
  const inf = INFO[pick.uid] || [new Date().toISOString().slice(0, 10), '임시 비밀번호 사용 중', false, [true, true, false], '09:00'];
  const on = s.act === null ? pick.on !== false : s.act;
  const defs = ['긴급 알림(위기 신호·안부 무응답) 즉시 알림', '상담 30분 전 브리핑 알림', 'STT 분석 완료 알림'];
  const notify = defs.map((l, i) => ({ label: l, st: inf[3][i] ? '켜짐' : '꺼짐', cls: inf[3][i] ? 'chip c-ok' : 'chip c-normal' }));
  const self = pick.uid === 'kim.minjun';
  return { name: pick.name, ini: (pick.name || '?').slice(0, 1), uid: pick.uid, cases: pick.cases, mail: `${pick.uid}@ondam-center.kr`,
    created: inf[0], last: pick.last, ip: pick.ip, ext: !!pick.ip && pick.ip !== '—' && !String(pick.ip).startsWith('192.168.'),
    otp: inf[2] ? '등록됨' : '첫 로그인 때 등록 예정', otpCls: inf[2] ? 'chip c-ok' : 'chip c-check',
    pwText: s.pw ? '재설정 링크 발송됨 · 30분 유효' : (inf[2] ? `마지막 변경 ${inf[1]}` : inf[1]), pwLabel: s.pw ? '다시 보내기' : '비밀번호 재설정 링크 보내기', pwCls: 'btn-s',
    resetPw: () => this.setState({ pw: true }), notify, batch: inf[4],
    st: on ? '활성' : '비활성', stCls: on ? 'chip c-ok' : 'chip c-check',
    actLabel: self ? '본인 계정' : (on ? '계정 비활성화' : '계정 다시 활성화'), actCls: 'btn-s',
    toggleAct: () => { if (self) return; this.setState({ act: !on, msg: on ? `${pick.name} 계정을 비활성화했어요 · 로그인할 수 없어요` : `${pick.name} 계정을 다시 활성화했어요` }); },
    hasMsg: !!s.msg, msg: s.msg };
}
}
