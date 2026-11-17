// AdminAccess 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminAccess.jsx)이 이어받아 데이터만 바꾼다.
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

constructor(props) { super(props); this.state = { k: 'all', other: false }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const L = [
    ['10/15 09:18', '이서연', '선임 상담사', '김순자', 'C-2026-0351', 'play', '기록 확인', '192.168.1.12', 'own'],
    ['10/14 17:42', '정다은', '상담사', '한동길', 'C-2026-0418', 'dl', '문서함', '192.168.1.8', 'own'],
    ['10/13 20:15', '박지훈', '상담사', '김순자', 'C-2026-0351', 'play', '상담 이력', '211.36.142.9', 'other'],
    ['10/13 15:30', '이서연', '선임 상담사', '오금자', 'C-2026-0412', 'play', '기록 확인', '192.168.1.12', 'own']
  ];
  const KN = { play: ['녹취 재생', 'chip c-normal'], dl: ['녹취 내려받기', 'chip c-check'] };
  const OWN = { own: ['담당', 'chip c-ok'], other: ['담당 외', 'chip c-urgent'], admin: ['관리 권한', 'chip c-normal'] };
  const rows = L.filter((r) => (s.k === 'all' || r[5] === s.k) && (!s.other || r[8] === 'other')).map((r) => ({
    t: r[0], who: r[1], rank: r[2], elder: r[3], cid: r[4], kind: KN[r[5]][0], kCls: KN[r[5]][1], screen: r[6], ip: r[7], ext: !r[7].startsWith('192.168.'), own: OWN[r[8]][0], oCls: OWN[r[8]][1] }));
    return { rows, total: L.length, recCnt: L.length, dlCnt: L.filter((r) => r[5] === 'dl').length, otherCnt: L.filter((r) => r[8] === 'other').length,
    onlyOther: s.other, tgBg: s.other ? '#1F3A56' : '#C5D4DE', tgX: s.other ? '16px' : '2px', toggleOther: () => this.setState({ other: !s.other }),
    kFilters: segOf('k', s.k, [['all', '전체'], ['play', '녹취 재생'], ['dl', '녹취 내려받기']]) };
}
}
