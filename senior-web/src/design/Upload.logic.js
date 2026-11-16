// Upload 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Upload.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {
backRead() {
  let v = null;
  try { v = window.localStorage.getItem('ispot-back'); } catch (e) {}
  if (!v) { try { v = window.sessionStorage.getItem('ispot-back'); } catch (e) {} }
  if (!v) { try { v = window.top.__ispotBack; } catch (e) {} }
  if (!v) v = window.__ispotBack;
  return v || '#/Home';
}
backShow() { this._backShown = this.backRead(); return this._backShown; }
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
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown || this.backRead() !== this._backShown) this.setState({ __thmTick: Date.now() }); }, 200);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), backHref: this.backShow(), syncBack: (e) => { try { const h = this.backRead(); if (e && e.currentTarget) e.currentTarget.setAttribute('href', h); } catch (err) {} this.resetFlow(); }, resetFlow: () => this.resetFlow(), themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

resetFlow() { setTimeout(() => this.setState({ step: 1, c: 0, x: null, confirm: false, file: null }), 0); }
constructor(props) { super(props); this.state = { step: 1, c: 0, x: null, confirm: false, file: null }; }
renderValsBase() {
  const s = this.state;
  const labels = ['사례 선택', '상담 회차', '파일 선택'];
  const steps = labels.map((label, i) => { const n = i + 1, done = n < s.step, cur = n === s.step;
    return { label, mark: done ? '✓' : String(n), bg: cur ? '#E8F4FC' : 'transparent', fg: cur ? '#1F3A56' : (done ? '#1F3A56' : '#66788A'), fw: cur ? 700 : 400,
      dotBg: cur ? '#1F3A56' : (done ? '#ECF5FA' : '#DDE6EC'), dotFg: cur ? '#D6ECFA' : (done ? '#55687A' : '#66788A') }; });
  const CS = [['김순자', 'C-2026-0351', 8, null], ['오금자', 'C-2026-0412', 6, null], ['서복례', 'C-2026-0389', 3, null], ['박영수', 'C-2026-0277', 10, [10, 8]], ['이정희', 'C-2026-0338', 5, [10, 5]], ['최만석', 'C-2026-0374', 2, [10, 9]],
    ['윤기철', 'C-2026-0298', 9, [10, 1]], ['정말순', 'C-2026-0229', 11, [9, 29]], ['강덕수', 'C-2026-0312', 12, [10, 7]], ['한옥분', 'C-2026-0251', 10, [10, 6]]];
  const cs = CS.map((c) => [c[0], c[1] + ' · ' + c[2] + '회차까지 진행']);
  const radio = (on) => ({ bd: on ? '#1F3A56' : '#D9E3EA', bg: on ? '#E8F4FC' : '#FFFFFF', dot: on ? '#1F3A56' : '#C5D4DE', fill: on ? '#1F3A56' : 'transparent' });
  const cases = cs.map((c, i) => ({ name: c[0], meta: c[1], ...radio(i === s.c), pick: () => this.setState({ c: i, x: null }) }));
  const last = CS[s.c][2];
  const DATES = { 0: ['10/2 방문상담', '9/18 정기상담', '9/4 정기상담', '8/21 정기상담', '8/7 정기상담', '7/24 정기상담', '7/10 정기상담', '6/26 초기상담'], 1: ['10/6 정기상담', '9/22 정기상담', '9/8 방문상담', '8/25 정기상담', '8/11 정기상담', '7/28 초기상담'], 2: ['9/30 정기상담', '9/16 정기상담', '9/2 초기상담'] }[s.c] || (() => { const [mo, da] = CS[s.c][3]; const out = []; for (let n = last; n >= 1; n--) { const d = new Date(2026, mo - 1, da - (last - n) * 14); out.push((d.getMonth() + 1) + '/' + d.getDate() + (n === 1 ? ' 초기상담' : ' 정기상담')); } return out; })();
  const xs = [['새 회차 · ' + (last + 1) + '회차', '새로 등록']];
  for (let n = last; n >= 1; n--) xs.push([n + '회차 · ' + DATES[last - n], (s.c === 0 && n === last) ? '녹취 아직 없음' : '녹취 있음 · 추가 자료']);
  const xSel = s.x == null ? 1 : s.x;
  const sessions = xs.map((x, i) => ({ label: x[0], meta: x[1], ...radio(i === xSel), pick: () => this.setState({ x: i }) }));
  const fl = s.file;
  return { steps, cases, sessions, caseName: cs[s.c][0] + ' · ' + cs[s.c][1].split(' · ')[0], sesLabel: xSel === 0 ? xs[0][0].split(' · ')[1] + ' (새 회차)' : xs[xSel][0].split(' · ')[0],
    hasFile: !!fl, fileName: fl ? fl.name : '', fileSize: fl ? fl.size : '', fileKind: fl ? fl.kind : '',
    pickFile: (e) => { const t = e && e.target && e.target.files && e.target.files[0]; if (!t) return; const mb = t.size / 1048576; this.setState({ file: { name: t.name, size: mb >= 1 ? mb.toFixed(1) + 'MB' : Math.max(1, Math.round(t.size / 1024)) + 'KB', kind: /\.(mp3|m4a|wav|aac|ogg)$/i.test(t.name) || /^audio\//.test(t.type || '') ? '음성' : '문서' } }); },
    clearFile: () => this.setState({ file: null }),
    confirmFile: fl ? ' · ' + fl.name : '',
    s1: s.step === 1, s2: s.step === 2, s3: s.step === 3, notFirst: s.step > 1, notLast: s.step < 3, confirm: s.confirm,
    next: () => this.setState({ step: Math.min(3, s.step + 1) }), prev: () => this.setState({ step: Math.max(1, s.step - 1) }),
    upload: () => { this.jobWrite(JSON.stringify({ t: Date.now(), name: fl ? fl.name : '' })); this.setState({ confirm: true }); } };
}
}
