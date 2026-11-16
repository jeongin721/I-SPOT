// CaseInfo 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/CaseInfo.jsx)이 이어받아 데이터만 바꾼다.
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
  try { if (String(window.location.hash || '') === '#brief') setTimeout(() => { try { const el = document.getElementById('brief'); if (el) el.scrollIntoView({ block: 'start' }); } catch (e) {} }, 120); } catch (e) {}
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._ntT); try { document.removeEventListener('mousedown', this._ntDoc); } catch (e) {}
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
ntGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
ntSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
ntRecs() { try { const a = JSON.parse(this.ntGet('ispot-intake') || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
ntSave(a) { this.ntSet('ispot-intake', JSON.stringify(a)); }
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '가족·생활지원사 면담'], [30, '상담 계획서 작성']]; }
ntReadIds() { try { return JSON.parse(this.ntGet('ispot-noti-read') || '[]'); } catch (e) { return []; } }
ntGo0() { let g = null; try { g = JSON.parse(this.ntGet('ispot-sched-go') || 'null'); } catch (e) {} if (!g || !g.t || Date.now() - g.t > 15000) return null; this.ntSet('ispot-sched-go', ''); return g; }
ntVals() {
  const recs = this.ntRecs(); const read = this.ntReadIds(); const days = ['일', '월', '화', '수', '목', '금', '토'];
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const items = [];
  recs.forEach((r) => this.ntTasks().forEach(([n, task]) => { if ((r.done || {})[n]) return; const due = new Date(r.y, r.m, r.d + n); const diff = Math.round((due - t0) / 86400000); const id = r.id + '-' + n;
    items.push({ id, due, diff, unread: read.indexOf(id) < 0, title: r.child + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (due.getMonth() + 1) + '/' + due.getDate() + '(' + days[due.getDay()] + ')까지', y: due.getFullYear(), m: due.getMonth(), d: due.getDate() }); }));
  items.sort((a, b) => a.due - b.due);
  const unread = items.filter((x) => x.unread).length; const open = !!(this.state && this.state.__ntOpen);
  const markRead = (ids) => { const cur = this.ntReadIds(); this.ntSet('ispot-noti-read', JSON.stringify([...cur, ...ids.filter((i) => cur.indexOf(i) < 0)])); };
  return {
    ntOpen: open, ntExp: open ? 'true' : 'false', ntHasBadge: unread > 0, ntBadge: unread > 9 ? '9+' : String(unread),
    ntLabel: unread > 0 ? '알림 ' + unread + '건 읽지 않음' : '알림',
    ntSub: items.length ? '처리 기한 ' + items.length + '건' : '', ntEmpty: items.length === 0,
    ntToggle: () => this.setState({ __ntOpen: !open }),
    ntReadAll: () => { markRead(items.map((x) => x.id)); this.setState({ __ntTick: Date.now() }); },
    ntItems: items.map((x) => ({ title: x.title, sub: x.sub, cls: x.unread ? 'unread' : 'read',
      dd: x.diff < 0 ? '기한 지남' : x.diff === 0 ? '오늘 마감' : 'D-' + x.diff, ddCls: x.diff <= 0 ? 'urgent' : x.diff <= 2 ? 'soon' : '',
      go: (e) => { markRead([x.id]); this.ntSet('ispot-sched-go', JSON.stringify({ y: x.y, m: x.m, d: x.d, t: Date.now() })); this.setState({ __ntOpen: false, __ntTick: Date.now() }); if (this.schedGo) { if (e && e.preventDefault) e.preventDefault(); this.ntSet('ispot-sched-go', ''); this.schedGo(x.y, x.m, x.d); } } }))
  };
}
nmMask(t) { let r = String(t || ''); const F = ['박영수', '김순자', '오금자', '서복례', '이정희', '최만석', '윤기철', '정말순', '강덕수', '한옥분']; F.forEach((n) => { r = r.split(n).join(n[0] + '○' + n.slice(2)); }); F.forEach((n) => { const g = n.slice(1); r = r.split(g).join(g[0] + '○'); }); return r; }
outPrint(mask) { const done = []; try { if (mask) { const root = document.body; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { const v = this.nmMask(n.nodeValue); if (v !== n.nodeValue) { done.push([n, 'nodeValue', n.nodeValue]); n.nodeValue = v; } } root.querySelectorAll('textarea, input').forEach((el) => { const v = this.nmMask(el.value); if (v !== el.value) { done.push([el, 'value', el.value]); el.value = v; } }); } } catch (e) {}
  try { document.body.classList.add('print-brief'); } catch (e) {} try { window.print(); } catch (e) {} try { document.body.classList.remove('print-brief'); } catch (e) {} done.forEach(([el, k, v]) => { try { el[k] = v; } catch (e) {} }); }
recTick(on) { clearInterval(this._recT); if (on) this._recT = setInterval(() => this.setState({ rs: this.state.rs + 1 }), 1000); }
recStopMedia() { try { if (this._mr && this._mr.state !== 'inactive') this._mr.stop(); } catch (e) {} try { if (this._stream) this._stream.getTracks().forEach((t) => t.stop()); } catch (e) {} this._stream = null; }
recCleanup() { this.recTick(false); this._noUrl = true; this.recStopMedia(); this._mr = null; try { if (this.state.rUrl) URL.revokeObjectURL(this.state.rUrl); } catch (e) {} }
recVals() {
  const s = Object.assign({ rec: false, rp: 'idle', rs: 0, rSes: 'new', rKind: '방문상담', rCon: false, rErr: false, rUrl: '', rSim: false }, this.state || {});
  const mm = String(Math.floor(s.rs / 60)).padStart(2, '0') + ':' + String(s.rs % 60).padStart(2, '0');
  const begin = (sim) => { this._noUrl = false; this.recTick(true); this.setState({ rp: 'rec', rs: 0, rSim: sim, rErr: false }); };
  const start = () => {
    if (!this.state.rCon) { this.setState({ rErr: true }); return; }
    let md = null; try { md = navigator.mediaDevices; } catch (e) {}
    if (!md || !md.getUserMedia || typeof MediaRecorder === 'undefined') { begin(true); return; }
    md.getUserMedia({ audio: true }).then((stream) => {
      this._stream = stream; const chunks = []; const mr = new MediaRecorder(stream); this._mr = mr;
      mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      mr.onstop = () => { if (this._noUrl) return; try { const url = URL.createObjectURL(new Blob(chunks, { type: mr.mimeType || 'audio/webm' })); this.setState({ rUrl: url }); } catch (e) {} };
      mr.start(); begin(false);
    }).catch(() => begin(true));
  };
  const status = { idle: '녹음 대기', rec: '녹음 중', paused: '일시정지', done: '녹음 완료', saved: '저장 완료' }[s.rp];
  return {
    recShow: s.rec, recOpen: () => this.setState({ rec: true, rp: 'idle', rs: 0, rErr: false, rUrl: '', rSim: false, rCon: false }),
    recClose: () => { this.recCleanup(); this.setState({ rec: false, rp: 'idle', rs: 0, rUrl: '', rSim: false, rErr: false }); },
    recSes: s.rSes, recSesSet: (e) => this.setState({ rSes: e.target.value }), recKind: s.rKind, recKindSet: (e) => this.setState({ rKind: e.target.value }),
    recLock: s.rp !== 'idle', recConsent: s.rCon, recConsentSet: (e) => this.setState({ rCon: !!e.target.checked, rErr: false }), recErr: s.rErr,
    recTime: mm, recStatus: status, recDotCls: s.rp === 'rec' ? 'live' : (s.rp === 'idle' ? 'idle' : 'off'),
    recIdle: s.rp === 'idle', recRunning: s.rp === 'rec' || s.rp === 'paused', recDone: s.rp === 'done', recSaved: s.rp === 'saved', recSim: s.rSim && s.rp !== 'saved',
    recStart: start,
    recPauseLabel: s.rp === 'paused' ? '계속 녹음' : '일시정지',
    recPause: () => { if (this.state.rp === 'rec') { try { if (this._mr && this._mr.pause) this._mr.pause(); } catch (e) {} this.recTick(false); this.setState({ rp: 'paused' }); } else { try { if (this._mr && this._mr.resume) this._mr.resume(); } catch (e) {} this.recTick(true); this.setState({ rp: 'rec' }); } },
    recStop: () => { this.recTick(false); this.recStopMedia(); this.setState({ rp: 'done' }); },
    recReset: () => { try { if (this.state.rUrl) URL.revokeObjectURL(this.state.rUrl); } catch (e) {} this.setState({ rp: 'idle', rs: 0, rUrl: '' }); },
    recSave: () => { const st = this.state; this.jobWrite(JSON.stringify({ t: Date.now(), name: '김순자 ' + (st.rSes === 'new' ? '9' : st.rSes) + '회차 녹음' })); this.setState({ rp: 'saved' }); }, recHasUrl: !!s.rUrl, recUrl: s.rUrl,
    recSummary: '김순자 · ' + (s.rSes === 'new' ? '9회차 (새 회차)' : s.rSes + '회차') + ' · ' + s.rKind + ' · ' + mm };
}
renderVals() {
  const v = this.renderValsBase() || {};
  v.goChecks = () => { this.ntSet('ispot-fq-go', 'checks|' + Date.now()); };
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, (() => { const st = this.state || {}; const mk = st.__outMask !== false; return { outShow: !!st.__outOpen, outTitle: '인쇄 · PDF', outGo: '인쇄', outOpen: () => this.setState({ __outOpen: true }), outClose: () => this.setState({ __outOpen: false }), outOpts: [[false, '실명 그대로', '예) 김순자'], [true, '이름 가리기', '예) 김○자 · 순○']].map(([m, label, ex]) => ({ label, ex, on: mk === m ? 'true' : 'false', cls: mk === m ? 'on' : '', pick: () => this.setState({ __outMask: m }) })), outRun: () => { this.setState({ __outOpen: false }); setTimeout(() => this.outPrint(mk), 120); } }; })(), this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), goForm: () => { const v = 'B|' + Date.now(); try { window.localStorage.setItem('ispot-form', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-form', v); } catch (e) {} try { window.top.__ispotForm = v; } catch (e) {} window.__ispotForm = v; }, markBack: () => { const v = '#/CaseInfo'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { reg: false, rec: false, rp: 'idle', rs: 0, rSes: 'new', rKind: '방문상담', rCon: false, rErr: false, rUrl: '', rSim: false }; }
recTick(on) { clearInterval(this._recT); if (on) this._recT = setInterval(() => this.setState({ rs: this.state.rs + 1 }), 1000); }
recStopMedia() { try { if (this._mr && this._mr.state !== 'inactive') this._mr.stop(); } catch (e) {} try { if (this._stream) this._stream.getTracks().forEach((t) => t.stop()); } catch (e) {} this._stream = null; }
recCleanup() { this.recTick(false); this._noUrl = true; this.recStopMedia(); this._mr = null; try { if (this.state.rUrl) URL.revokeObjectURL(this.state.rUrl); } catch (e) {} }
componentWillUnmountBase() { this.recCleanup(); }
renderValsBase() {
  const s = this.state;
  const mm = String(Math.floor(s.rs / 60)).padStart(2, '0') + ':' + String(s.rs % 60).padStart(2, '0');
  const begin = (sim) => { this._noUrl = false; this.recTick(true); this.setState({ rp: 'rec', rs: 0, rSim: sim, rErr: false }); };
  const start = () => {
    if (!this.state.rCon) { this.setState({ rErr: true }); return; }
    let md = null; try { md = navigator.mediaDevices; } catch (e) {}
    if (!md || !md.getUserMedia || typeof MediaRecorder === 'undefined') { begin(true); return; }
    md.getUserMedia({ audio: true }).then((stream) => {
      this._stream = stream; const chunks = []; const mr = new MediaRecorder(stream); this._mr = mr;
      mr.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
      mr.onstop = () => { if (this._noUrl) return; try { const url = URL.createObjectURL(new Blob(chunks, { type: mr.mimeType || 'audio/webm' })); this.setState({ rUrl: url }); } catch (e) {} };
      mr.start(); begin(false);
    }).catch(() => begin(true));
  };
  const status = { idle: '녹음 대기', rec: '녹음 중', paused: '일시정지', done: '녹음 완료', saved: '저장 완료' }[s.rp];
  return { isReg: s.reg, notReg: !s.reg, reg: () => this.setState({ reg: true }), unreg: () => this.setState({ reg: false }),
    recShow: s.rec, recOpen: () => this.setState({ rec: true, rp: 'idle', rs: 0, rErr: false, rUrl: '', rSim: false, rCon: false }),
    recClose: () => { this.recCleanup(); this.setState({ rec: false, rp: 'idle', rs: 0, rUrl: '', rSim: false, rErr: false }); },
    recSes: s.rSes, recSesSet: (e) => this.setState({ rSes: e.target.value }), recKind: s.rKind, recKindSet: (e) => this.setState({ rKind: e.target.value }),
    recLock: s.rp !== 'idle', recConsent: s.rCon, recConsentSet: (e) => this.setState({ rCon: !!e.target.checked, rErr: false }), recErr: s.rErr,
    recTime: mm, recStatus: status, recDotCls: s.rp === 'rec' ? 'live' : (s.rp === 'idle' ? 'idle' : 'off'),
    recIdle: s.rp === 'idle', recRunning: s.rp === 'rec' || s.rp === 'paused', recDone: s.rp === 'done', recSaved: s.rp === 'saved', recSim: s.rSim && s.rp !== 'saved',
    recStart: start,
    recPauseLabel: s.rp === 'paused' ? '계속 녹음' : '일시정지',
    recPause: () => { if (this.state.rp === 'rec') { try { if (this._mr && this._mr.pause) this._mr.pause(); } catch (e) {} this.recTick(false); this.setState({ rp: 'paused' }); } else { try { if (this._mr && this._mr.resume) this._mr.resume(); } catch (e) {} this.recTick(true); this.setState({ rp: 'rec' }); } },
    recStop: () => { this.recTick(false); this.recStopMedia(); this.setState({ rp: 'done' }); },
    recReset: () => { try { if (this.state.rUrl) URL.revokeObjectURL(this.state.rUrl); } catch (e) {} this.setState({ rp: 'idle', rs: 0, rUrl: '' }); },
    recSave: () => { const st = this.state; this.jobWrite(JSON.stringify({ t: Date.now(), name: '김순자 ' + (st.rSes === 'new' ? '9' : st.rSes) + '회차 녹음' })); this.setState({ rp: 'saved' }); }, recHasUrl: !!s.rUrl, recUrl: s.rUrl,
    recSummary: '김순자 · ' + (s.rSes === 'new' ? '9회차 (새 회차)' : s.rSes + '회차') + ' · ' + s.rKind + ' · ' + mm };
}
}
