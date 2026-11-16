// Step4Next 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Step4Next.jsx)이 이어받아 데이터만 바꾼다.
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
fqGo() { const v = this.ntGet('ispot-fq-go'); if (!v || v === this._fqTok) return; this._fqTok = v; const ts = parseInt(String(v).split('|')[1] || '0', 10); if (Date.now() - ts > 15000) return; this.ntSet('ispot-fq-go', ''); setTimeout(() => { try { const el = document.getElementById('next-checks'); if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); el.classList.add('fq-flash'); setTimeout(() => el.classList.remove('fq-flash'), 1600); } } catch (e) {} }, 80); }
componentDidMount() {
  this.fqGo(); this._fqT = setInterval(() => this.fqGo(), 400);
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._fqT);
  clearInterval(this._ntT); try { document.removeEventListener('mousedown', this._ntDoc); } catch (e) {}
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
ntGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
ntSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
ntRecs() { try { const a = JSON.parse(this.ntGet('ispot-intake') || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
ntSave(a) { this.ntSet('ispot-intake', JSON.stringify(a)); }
ntTasks() { return [[3, '어르신 안부 전화 확인'], [7, '가족(주 돌봄자) 상담'], [30, '서비스 계획 수립']]; }
ntReadIds() { try { return JSON.parse(this.ntGet('ispot-noti-read') || '[]'); } catch (e) { return []; } }
ntGo0() { let g = null; try { g = JSON.parse(this.ntGet('ispot-sched-go') || 'null'); } catch (e) {} if (!g || !g.t || Date.now() - g.t > 15000) return null; this.ntSet('ispot-sched-go', ''); return g; }
ntVals() {
  const recs = this.ntRecs(); const read = this.ntReadIds(); const days = ['일', '월', '화', '수', '목', '금', '토'];
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const items = [];
  recs.forEach((r) => this.ntTasks().forEach(([n, task]) => { if ((r.done || {})[n]) return; const due = new Date(r.y, r.m, r.d + n); const diff = Math.round((due - t0) / 86400000); const id = r.id + '-' + n;
    items.push({ id, due, diff, unread: read.indexOf(id) < 0, title: r['c' + 'hild'] + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (due.getMonth() + 1) + '/' + due.getDate() + '(' + days[due.getDay()] + ')까지', y: due.getFullYear(), m: due.getMonth(), d: due.getDate() }); }));
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
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Step4Next'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { tab: 'meet', on: { 0: true, 1: true, 2: false }, qok: {}, qe: {}, extraQs: [], qEditing: false, qDraft: {}, qNew: [], ne: {}, extraNotes: [], nEditing: false, nDraft: {}, nNew: [] }; }
renderValsBase() {
  const s = this.state;
  const ALL = [
    { g: 'meet', id: '열린 질문', text: '요즘 밤에 깨시면 주로 어떤 생각이 드세요?', opts: [], why: '8회차 01:08' },
    { g: 'meet', id: '열린 질문', text: '아드님께 요즘 지내시는 이야기를 하신다면, 어디까지 말씀하고 싶으세요?', opts: [], why: '8회차 01:36' },
    { g: 'meet', id: 'QB-L-01', text: '복지관 노래교실에 다시 나가 보시면 어떠실 것 같으세요?', opts: [], why: '8회차 02:40' },
    { g: 'app', id: 'QB-M-01', text: '어제 식사는 몇 번 하셨어요?', opts: ['못 먹었어요', '한 번', '두 번', '세 번', '말하기 어려워요'], why: '8회차 00:41', sendNote: '오늘 저녁 발송' },
    { g: 'app', id: 'QB-S-02', text: '어젯밤 잠은 잘 주무셨어요?', opts: ['잘 잤어요', '자다가 자주 깼어요', '거의 못 잤어요', '말하기 어려워요'], why: '8회차 01:08', sendNote: '오늘 저녁 발송' }
  ].concat(s.extraQs.map((q) => ({ g: q.g, id: '직접 작성', text: q.text, opts: q.opts, why: '상담사 직접 추가', sendNote: q.g === 'app' ? '오늘 저녁 발송' : '' })));
  const splitOpts = (v) => String(v || '').split(',').map((x) => x.trim()).filter(Boolean);

  /* 추가 질문 */
  const qCur = (i) => { const q0 = ALL[i]; const cur = s.qe[i] || {}; return { text: cur.text || q0.text, opts: cur.opts || q0.opts || [] }; };
  const qDraftAll = () => { const d = {}; ALL.forEach((q0, i) => { const c = qCur(i); d[i] = { text: c.text, opts: c.opts.join(', ') }; }); return d; };
  const allQs = ALL.map((q0, i) => {
    const c = qCur(i); const cur = s.qe[i] || {}; const ok = !!s.qok[i]; const d = s.qDraft[i] || {};
    return { g: q0.g, id: q0.id, why: q0.why, text: c.text, opts: c.opts, hasOpts: c.opts.length > 0, edited: !!cur.text || !!cur.opts,
      ok, st: q0.sendNote ? '발송 예약 · ' + q0.sendNote : '발송 예약', okCls: ok ? 'btn-p' : 'btn-s', okLabel: ok ? '발송 예약 ✓' : '발송 예약',
      isEdit: s.qEditing, notEdit: !s.qEditing, draftText: d.text || '', draftOpts: d.opts || '',
      approve: () => this.setState({ qok: { ...this.state.qok, [i]: !this.state.qok[i] } }),
      setText: (e) => { const v = e.target.value; this.setState({ qDraft: { ...this.state.qDraft, [i]: { ...(this.state.qDraft[i] || {}), text: v } } }); },
      setOpts: (e) => { const v = e.target.value; this.setState({ qDraft: { ...this.state.qDraft, [i]: { ...(this.state.qDraft[i] || {}), opts: v } } }); } };
  });
  const qs = allQs.filter((q) => q.g === s.tab);
  const qNewRows = s.qNew.map((r, j) => ({ ...r, j, withOpts: r.g === 'app',
    setText: (e) => { const v = e.target.value; const n = this.state.qNew.slice(); n[j] = { ...n[j], text: v }; this.setState({ qNew: n }); },
    setOpts: (e) => { const v = e.target.value; const n = this.state.qNew.slice(); n[j] = { ...n[j], opts: v }; this.setState({ qNew: n }); } })).filter((r) => r.g === s.tab);
  const startQ = () => this.setState({ qEditing: true, qDraft: qDraftAll(), qNew: [] });
  const addQ = () => { const st = this.state; this.setState({ qEditing: true, qDraft: st.qEditing ? st.qDraft : qDraftAll(), qNew: (st.qEditing ? st.qNew : []).concat([{ g: st.tab, text: '', opts: '' }]) }); };
  const qOk = () => {
    const st = this.state; const qe = { ...st.qe }; const qok = { ...st.qok };
    ALL.forEach((q0, i) => { const c = qCur(i); const d = st.qDraft[i]; if (!d) return;
      const t = String(d.text || '').trim() || c.text; const o = c.opts.length ? splitOpts(d.opts) : [];
      if (t !== c.text || (c.opts.length && o.join('|') !== c.opts.join('|'))) { qe[i] = { text: t, opts: c.opts.length ? (o.length ? o : c.opts) : null }; qok[i] = false; } });
    const added = st.qNew.filter((r) => String(r.text || '').trim()).map((r) => ({ g: r.g, text: r.text.trim(), opts: r.g === 'app' ? splitOpts(r.opts) : [] }));
    this.setState({ qe, qok, extraQs: st.extraQs.concat(added), qEditing: false, qDraft: {}, qNew: [] });
  };
  const qCancel = () => this.setState({ qEditing: false, qDraft: {}, qNew: [] });

  /* 다음 상담 전 확인할 사항 */
  const base = [
    { t: '식사 · 수면 · 기분이 지난 상담 이후 어떻게 달라졌는지', why: '8회차 00:41 · 01:08' },
    { t: '02:15 죽음 관련 말씀의 의미 · S-04 자살위험 선별 필요 여부', why: '8회차 02:15 · 의미 확인 필요' },
    { t: '아들 이정훈 님과의 연락 빈도 · 가족 공유 동의 범위', why: '8회차 01:36 · 주 1회 통화' },
    { t: '복지관 노래교실 등 프로그램 재참여 의사', why: '8회차 02:40' },
    { t: '안부 앱 식사 · 수면 답변 확인 (이번 주)', why: '안부 앱 · 음성 답변 2건' },
    { t: 'SGDS-K 재측정 시점 (직전 측정 5회차)', why: 'S-03 · 5회차 측정 후 3회 경과' }
  ].concat(s.extraNotes.map((t) => ({ t, why: '상담사 직접 추가' })));
  const nText = (i) => (s.ne[i] !== undefined ? s.ne[i] : base[i].t);
  const nDraftAll = () => { const d = {}; base.forEach((b, i) => { d[i] = nText(i); }); return d; };
  const nDel = s.nDel || {};
  const checks = base.map((b, i) => ({ i, b })).filter((x) => !nDel[x.i]).map(({ b, i }) => ({ why: b.why, text: nText(i), edited: s.ne[i] !== undefined, on: !!s.on[i],
    isEdit: s.nEditing, notEdit: !s.nEditing, draft: s.nDraft[i] !== undefined ? s.nDraft[i] : '',
    setDraft: (e) => { const v = e.target.value; this.setState({ nDraft: { ...this.state.nDraft, [i]: v } }); },
    toggle: () => this.setState({ on: { ...this.state.on, [i]: !this.state.on[i] } }),
    del: () => this.setState({ nDel: { ...(this.state.nDel || {}), [i]: true } }) }));
  const nNewRows = s.nNew.map((t, j) => ({ draft: t, setDraft: (e) => { const v = e.target.value; const n = this.state.nNew.slice(); n[j] = v; this.setState({ nNew: n }); } }));
  const startN = () => this.setState({ nEditing: true, nDraft: nDraftAll(), nNew: [] });
  const addN = () => { const st = this.state; this.setState({ nEditing: true, nDraft: st.nEditing ? st.nDraft : nDraftAll(), nNew: (st.nEditing ? st.nNew : []).concat(['']) }); };
  const nOk = () => {
    const st = this.state; const ne = { ...st.ne }; const on = { ...st.on };
    base.forEach((b, i) => { const d = st.nDraft[i]; if (d === undefined) return; const t = String(d).trim(); if (t && t !== nText(i)) ne[i] = t; });
    const added = st.nNew.map((t) => String(t || '').trim()).filter(Boolean);
    added.forEach((t, k) => { on[base.length + k] = true; });
    this.setState({ ne, on, extraNotes: st.extraNotes.concat(added), nEditing: false, nDraft: {}, nNew: [] });
  };
  const nCancel = () => this.setState({ nEditing: false, nDraft: {}, nNew: [] });

  return { checks, nNewRows, addN, startN, nOk, nCancel, nIsEdit: s.nEditing, nNotEdit: !s.nEditing,
    qs, qNewRows, addQ, startQ, qOk, qCancel, qIsEdit: s.qEditing, qNotEdit: !s.qEditing,
    meetCls: s.tab === 'meet' ? 'on' : '', appCls: s.tab === 'app' ? 'on' : '',
    showMeet: () => this.setState({ tab: 'meet' }), showApp: () => this.setState({ tab: 'app' }) };
}
}
