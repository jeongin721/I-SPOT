// CaseHistory 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/CaseHistory.jsx)이 이어받아 데이터만 바꾼다.
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
  if (this.state && this.state.open) this.setState({ open: false });
  this._histNav = (e) => { const t = e.target && e.target.closest ? e.target.closest('a[href]') : null; if (t && this.state && this.state.open) this.setState({ open: false }); }; try { document.addEventListener('click', this._histNav, true); } catch (e) {}
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  try { document.removeEventListener('click', this._histNav, true); } catch (e) {} if (this.state && this.state.open) this.setState({ open: false });
  this.recCleanup();
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
nsVals() {
  const s = this.state || {}; const step = s.nsStep || 1; const ses = s.nsSes || 'new';
  const LIST = [['new', '새 회차 · 9회차', '오늘 10/27 · 새 회차 만들기'], ['8', '8회차', '10/2 방문상담'], ['7', '7회차', '9/18 내방상담'], ['6', '6회차', '9/4 방문상담'], ['5', '5회차', '8/28 내방상담'], ['4', '4회차', '8/21 방문상담'], ['3', '3회차', '8/14 전화상담'], ['2', '2회차', '8/7 방문상담'], ['1', '1회차', '7/31 초기상담(방문)']];
  const cur = LIST.find((x) => x[0] === ses) || LIST[0];
  const reset = { nsShow: false, nsStep: 1, nsSes: 'new', nsBody: '', nsNote: '', nsErr: false, nsDone: false };
  return {
    nsShow: !!s.nsShow, nsS1: step === 1, nsS2: step === 2, nsDone: !!s.nsDone,
    nsOpen: () => this.setState({ ...reset, nsShow: true }), nsClose: () => this.setState(reset),
    nsSteps: [['상담 회차', 1], ['상담 내용 · 소견', 2]].map(([label, n]) => ({ label, mark: step > n ? '✓' : String(n), cls: step === n ? 'on' : step > n ? 'done' : '' })),
    nsSessions: LIST.map(([v, label, meta]) => ({ label, meta, on: ses === v ? 'true' : 'false', cls: ses === v ? 'on' : '', pick: () => this.setState({ nsSes: v }) })),
    nsSesLabel: ses === 'new' ? '9회차 (새 회차)' : cur[1] + ' · ' + cur[2],
    nsNext: () => this.setState({ nsStep: 2 }), nsPrev: () => this.setState({ nsStep: 1, nsErr: false }),
    nsBody: s.nsBody || '', nsBodySet: (e) => this.setState({ nsBody: e.target.value, nsErr: false }), nsNote: s.nsNote || '', nsNoteSet: (e) => this.setState({ nsNote: e.target.value }),
    nsErr: !!s.nsErr, nsBodyBd: s.nsErr ? '#A33B2E' : '#C5D4DE',
    nsSave: () => { if (!(this.state.nsBody || '').trim()) { this.setState({ nsErr: true }); return; } this.setState({ nsDone: true }); },
    nsBodyLen: (s.nsBody || '').trim().length, nsNoteLen: (s.nsNote || '').trim().length
  };
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.recVals(), this.nsVals(), this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/CaseHistory'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { open: false, sigOnly: false }; }
renderValsBase() {
  const RAW = {
    8: { date: '2026-10-02', kind: '방문상담 · 24분', status: '처리 중', st: 'chip c-check', sig: '채택 3 · 보류 1', proc: true,
      sttState: '검수 중 · 저신뢰 3곳', sttCls: 'chip c-check',
      lines: [{ t: '00:41', sp: '어르신', s: '그 양반 가고 나서는 집이 너무 조용해요. 하루 종일 말 한마디 안 할 때도 있어요.', c: '62%' }, { t: '01:08', sp: '어르신', s: '아들한테는 말 안 해요. 바쁜 애한테 짐 되기 싫어서요.', c: '58%' }, { t: '01:36', sp: '어르신', s: '그냥 적적해요.', c: '91%' }, { t: '02:15', sp: '화자?', s: '끼니를 그냥 넘길 때가 많아요.', c: '70%' }],
      diaryState: '작성 전', diaryCls: 'chip c-check', diary: '아직 작성하지 않았어요. 회차 처리 3단계에서 AI 초안을 받아 작성해요.', diaryBtn: '상담일지 작성하러 가기',
      sumState: '작성 전', sumCls: 'chip c-check', summary: '요약은 회차 처리 3단계에서 확정돼요.',
      ai: '어르신이 배우자 사별 후 집이 조용해 외로움을 크게 느낀다고 말씀하심. 아들에게 "짐이 될까 봐" 어려움을 알리지 않는다고 하심. 식사 관련 발화는 화자 확인 필요.',
      sigs: [['정서', '우울감 · 기분 저하 · 00:41'], ['정서', '상실 · 애도 반응 · 00:41'], ['고립', '외로움 · 고립감 · 01:08, 01:36'], ['생활', '식사 · 수면 변화 (보류) · 02:15']] },
    7: { date: '2026-09-18', kind: '내방상담 · 50분', status: '확정', st: 'chip c-ok', sig: '채택 2', proc: false, sttState: '검수 완료', sttCls: 'chip c-ok',
      lines: [{ t: '02:40', sp: '어르신', s: '마음이 답답하면 생활지원사 선생님한테 전화해 볼게요.', c: '93%' }, { t: '05:10', sp: '어르신', s: '가끔은 이렇게 살아서 뭐 하나 싶어요.', c: '88%' }],
      diaryState: '확정', diaryCls: 'chip c-ok', diary: '위기 시 연락 계획을 어르신과 함께 정리함. 마음이 힘들 때 생활지원사 · 상담사에게 연락하기로 함. "이렇게 살아서 뭐 하나" 말씀이 있어 S-04 자살위험 선별을 실시함(현재 계획 · 수단 없음, 보호요인: 아들 · 경로당 지인). 109 안내함. 다음 회차에도 계속 확인하기로 함.', diaryBtn: '일지 수정',
      sumState: '확정', sumCls: 'chip c-ok', summary: '위기 시 연락 계획 수립 · 죽음 관련 언급 1건 · S-04 선별(계획 없음) · 109 안내.',
      ai: '어르신과 위기 시 연락 계획을 세움. 삶의 의미 저하와 관련된 말씀이 있어 자살위험 선별 확인이 필요함.', sigs: [['고립', '외로움 · 고립감 · 02:40'], ['위기', '죽음 관련 언급 · 05:10']] },
    6: { date: '2026-09-04', kind: '방문상담 · 45분', status: '확정', st: 'chip c-ok', sig: '채택 2', proc: false, sttState: '검수 완료', sttCls: 'chip c-ok',
      lines: [{ t: '03:20', sp: '어르신', s: '밤에 누우면 그 양반 생각이 나서 잠이 안 와요.', c: '95%' }, { t: '05:02', sp: '어르신', s: '밥은… 그냥 대충 먹어요.', c: '90%' }],
      diaryState: '확정', diaryCls: 'chip c-ok', diary: '배우자 생각에 잠들기 어렵다고 말씀하심. 식사 질문에는 "대충 먹는다"고 답하심. 식사 · 수면 변화를 기록해 둠.', diaryBtn: '일지 수정',
      sumState: '확정', sumCls: 'chip c-ok', summary: '사별 후 불면 · 식사 질문에 모호한 답.', ai: '어르신이 배우자 사별 후 불면과 그리움을 표현하심.',
      sigs: [['정서', '우울감 · 기분 저하 · 05:02'], ['고립', '외로움 · 고립감 · 03:20']] }
  };
  const DATES = ['', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-21', '2026-08-28'];
  const getS = (n) => RAW[n] || { date: DATES[n], kind: n === 1 ? '초기상담(방문) · 40분' : n === 3 ? '전화상담 · 25분' : n === 5 ? '내방상담 · 45분' : '방문상담 · 45분', status: '확정', st: 'chip c-ok', proc: false,
    sig: n <= 3 ? '신호 없음' : '채택 ' + (n === 5 ? 3 : 1), sttState: '검수 완료', sttCls: 'chip c-ok',
    lines: [{ t: '01:00', sp: '어르신', s: n <= 3 ? '복지관 점심은 가끔 먹으러 가요.' : '영감 가고 나서는 입맛이 통 없어요.', c: '94%' }],
    diaryState: '확정', diaryCls: 'chip c-ok', diary: n <= 3 ? '관계 형성 단계. 하루 일과와 이용 중인 서비스를 중심으로 대화함.' : '배우자 사별 후 입맛 저하를 처음 말씀하심. 말씀 내용을 그대로 기록함.', diaryBtn: '일지 수정',
    sumState: '확정', sumCls: 'chip c-ok', summary: n <= 3 ? '관계 형성 · 일상 파악 중심.' : '사별 후 입맛 저하 언급 · 원문 기록.',
    ai: n <= 3 ? '어르신과 라포 형성 중. 특이 사항 없음.' : '어르신이 사별 후 입맛 저하를 말씀하심.',
    sigs: n <= 3 ? [] : [['정서', '우울감 · 기분 저하 · 01:00']] };

  const sigs = [
    { type: '정서', name: '우울감 · 기분 저하', v: [0, 0, 0, 1, 2, 1, 0, 1] },
    { type: '정서', name: '상실 · 애도 반응', v: [0, 0, 0, 0, 1, 0, 0, 1] },
    { type: '고립', name: '외로움 · 고립감', v: [0, 0, 0, 0, 0, 1, 1, 2] },
    { type: '위기', name: '죽음 관련 언급', v: [0, 0, 0, 0, 0, 0, 1, 0] },
    { type: '생활', name: '식사 · 수면 변화', v: [0, 0, 0, 0, 0, 0, 0, -1], at: { 8: '02:15' } }
  ];
  const goPend = (n, t) => () => { const now = Date.now(); const sv = n + '|' + now; const tv = t + '|' + now + '|q'; try { window.localStorage.setItem('ispot-ses', sv); window.localStorage.setItem('ispot-stt', tv); } catch (e) {} try { window.sessionStorage.setItem('ispot-ses', sv); window.sessionStorage.setItem('ispot-stt', tv); } catch (e) {} try { window.top.__ispotSes = sv; window.top.__ispotStt = tv; } catch (e) {} window.__ispotSes = sv; window.__ispotStt = tv; };
  const mrows = sigs.map((g) => ({ type: g.type, name: g.name, 
    cells: g.v.map((n, i) => ({ pend: n < 0, notPend: !(n < 0), go: goPend(i + 1, (g.at || {})[i + 1] || ''), v: n > 0 ? String(n) : (n < 0 ? '?' : ''), tip: `${i + 1}회차 · ${g.name} · ${n > 0 ? n + '번' : n < 0 ? '보류' : '없음'}`,
      bg: n >= 2 ? '#66788A' : n === 1 ? '#DDE6EC' : 'transparent', fg: n >= 2 ? '#FFFFFF' : n < 0 ? '#66788A' : '#1F3A56', ring: n < 0 ? 'inset 0 0 0 1.5px #66788A' : 'none' })) }));
  const st = this.state;
  const sessions = [8, 7, 6, 5, 4, 3, 2, 1].map((n) => { const r = getS(n); return { go: () => { const v = n + '|' + Date.now(); try { window.localStorage.setItem('ispot-ses', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-ses', v); } catch (e) {} try { window.top.__ispotSes = v; } catch (e) {} window.__ispotSes = v; }, no: n + '회차', date: r.date, kind: r.kind, kindShort: r.kind.split(' · ')[0], status: r.status, st: r.st, sig: r.sig, hasSig: r.sig !== '신호 없음', proc: r.proc }; });
  const ordered = sessions.filter((x) => x.proc).concat(sessions.filter((x) => !x.proc));
  const all = st.sigOnly ? ordered.filter((x) => x.hasSig) : ordered;
  return { mrows, recent: ordered.slice(0, 3), all, total: sessions.length, shownCount: all.length + '개', open: st.open, openAttr: st.open ? 'true' : 'false', sigOnly: st.sigOnly,
    toggleOpen: () => this.setState({ open: !st.open }), toggleSig: () => this.setState({ sigOnly: !st.sigOnly }),
    cols: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => ({ label: n + '회', go: () => { const v = n + '|' + Date.now(); try { window.localStorage.setItem('ispot-ses', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-ses', v); } catch (e) {} try { window.top.__ispotSes = v; } catch (e) {} window.__ispotSes = v; } })) };
}
}
