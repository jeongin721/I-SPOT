// CaseApp 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/CaseApp.jsx)이 이어받아 데이터만 바꾼다.
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
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '초기 방문 상담'], [30, '사례관리 계획서 제출']]; }
ntReadIds() { try { return JSON.parse(this.ntGet('ispot-noti-read') || '[]'); } catch (e) { return []; } }
ntGo0() { let g = null; try { g = JSON.parse(this.ntGet('ispot-sched-go') || 'null'); } catch (e) {} if (!g || !g.t || Date.now() - g.t > 15000) return null; this.ntSet('ispot-sched-go', ''); return g; }
ntVals() {
  const recs = this.ntRecs(); const read = this.ntReadIds(); const days = ['일', '월', '화', '수', '목', '금', '토'];
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const items = [];
  recs.forEach((r) => this.ntTasks().forEach(([n, task]) => { if ((r.done || {})[n]) return; const due = new Date(r.y, r.m, r.d + n); const diff = Math.round((due - t0) / 86400000); const id = r.id + '-' + n;
    items.push({ id, due, diff, unread: read.indexOf(id) < 0, title: (r.senior || r.name || r['c' + 'hild'] || '') + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (due.getMonth() + 1) + '/' + due.getDate() + '(' + days[due.getDay()] + ')까지', y: due.getFullYear(), m: due.getMonth(), d: due.getDate() }); }));
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/CaseApp'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { qok: {}, qe: {}, qEdit: null, dText: '', dOpts: '', ne: {}, nEdit: null, nText: '' }; }
renderValsBase() {
  const K = { name: '김순자', short: '김순자 님', ini: '김', age: '만 82세 · 여 · 독거', types: '상실·애도 · 정서·우울', id: 'C-2026-0351', reason: '어르신이 남긴 말씀', rCls: 'chip c-sky', last: '어제 22:10', count: '19 / 21일', next: '오늘 16:00 9회차', urgent: false,
    quote: '다음에 오시면 드릴 말씀이 있어요', quoteAt: '음성 답변 · 어제 22:10 · 어르신 안부 앱(큰 글씨 · 음성)',
    famConsent: '가족 공유 · 일부 동의', famCls: 'chip c-sand', famScope: '공유 범위: 상담 일정 안내 · 안부 응답 여부 (상담 내용은 비공유)',
    famNotes: [['아들 · 이정훈 (가족 연계)', '10/16 21:10', '통화할 때 목소리에 힘이 없으세요. 아버지 기일이 다가와서 그런 것 같아요.'], ['아들 · 이정훈 (가족 연계)', '10/9 20:40', '주말에 반찬을 보내 드렸는데 잘 안 드신다고 하세요. 밤에 잠을 못 주무신다고 하셨어요.']],
    answers: [['공통 1', '어젯밤 잠은 잘 주무셨어요?', '밤에 자꾸 깨요', false, ['자다 깼어요', '자다 깼어요', '밤에 자꾸 깨요']], ['공통 2', '식사는 잘 하셨어요?', '밥은 조금 먹었어요', false, ['조금 먹었어요', '조금 먹었어요', '밥은 조금 먹었어요']], ['공통 3', '오늘 기분은 어떠세요?', '조금 울적해요', true, ['그저 그래요', '그저 그래요', '조금 울적해요']],
      ['SQ-E-05', '요즘 혼자 계실 때 영감님 생각이 많이 나세요?', '매일 나요', true, ['가끔요', '가끔요', '가끔요']], ['SQ-H-01', '요즘 몸이 불편한 곳이 있으세요?', '괜찮아요', false, ['괜찮아요', '괜찮아요', '허리가 좀 아파요']], ['SQ-E-03', '집에 계실 때 마음은 어떠세요?', '집이 너무 조용해요', false, ['편해요', '그저 그래요', '그저 그래요']]],
    flags: [{ q: '요즘 혼자 계실 때 영감님 생각이 많이 나세요? (SQ-E-05)', flow: ['가끔요', '가끔요', '가끔요', '매일 나요'], src: '10/6 응답 · 8회차 01:08', stt: '01:08', qi: [0] },
            { q: '오늘 기분은 어떠세요? (공통 3)', flow: ['그저 그래요', '그저 그래요', '조금 울적해요', '조금 울적해요'], src: '공통 3 · 최근 2주 12회', stt: '01:36', qi: [1] }],
    notes: ['8회차 상담에서 나온 사별 이야기와 같은 내용이 안부 앱에서 처음 나왔어요. 기일이 다가온다는 가족 관찰 메모와도 이어져요. 애도 반응을 다음 상담에서 확인해 보세요. (확인 제안)', '2주째 "조금 울적해요"가 이어지고 있어요. 어르신이 남긴 말씀과 함께 다음 상담 시작에서 다뤄 보시고, 필요하면 S-03 우울 선별을 검토해 보세요. (확인 제안)'],
    qs: [{ id: 'SQ-E-06', text: '영감님 생각이 나실 때 마음이 어떠세요?', opts: ['그립고 슬퍼요', '괜찮아요', '잘 모르겠어요', '말하기 어려워요'], why: 'SQ-E-05 응답', stt: '01:08', sendNote: '오늘 저녁 안부에 추가' },
         { id: 'SQ-S-05', text: '마음이 힘드실 때 이야기 나눌 분이 계세요?', opts: ['상담 선생님', '가족', '이웃 · 친구', '없어요', '말하기 어려워요'], why: '공통 3 응답 흐름', stt: '02:40', sendNote: '오늘 저녁 안부에 추가' }] };
  const s = this.state;
  const setTok = (key, top, v) => { try { window.localStorage.setItem(key, v); } catch (e) {} try { window.sessionStorage.setItem(key, v); } catch (e) {} try { window.top[top] = v; } catch (e) {} window[top] = v; };
  const goStt = (t) => { if (t) setTok('ispot-stt', '__ispotStt', t + '|' + Date.now()); };
  const goAns = () => setTok('ispot-senior', '__ispotSenior', 'C-2026-0351|' + Date.now());
  const hasOptsAt = (i) => (K.qs.at(i).opts || []).length > 0;

  const mkQs = (list) => list.map((q0, i) => {
    const cur = s.qe[i] || {}; const text = cur.text || q0.text; const opts = cur.opts || q0.opts || [];
    const ok = !!s.qok[i], editing = s.qEdit === i;
    return { goSrc: () => goStt(q0.stt), id: q0.id, why: q0.why, text, opts, hasOpts: opts.length > 0, edited: !!cur.text || !!cur.opts,
      st: ok ? (q0.sendNote ? '승인됨 · ' + q0.sendNote : '승인됨') : 'AI 초안', stCls: ok ? 'chip c-sel' : 'chip c-ai', ring: editing ? 'inset 0 0 0 2px #1F3A56' : 'none',
      okCls: ok ? 'btn-p' : 'btn-s', okLabel: ok ? '승인됨 ✓' : '승인',
      isEdit: editing, notEdit: !editing, draftText: s.dText, draftOpts: s.dOpts,
      approve: () => this.setState({ qok: { ...s.qok, [i]: !ok } }),
      startEdit: () => this.setState({ qEdit: i, dText: text, dOpts: opts.join(', ') }),
      setText: (e) => this.setState({ dText: e.target.value }), setOpts: (e) => this.setState({ dOpts: e.target.value }),
      save: () => this.setState({ qEdit: null, qok: { ...s.qok, [i]: false }, qe: { ...s.qe, [i]: { text: s.dText, opts: hasOptsAt(i) ? s.dOpts.split(',').map((x) => x.trim()).filter(Boolean) : null } } }),
      cancel: () => this.setState({ qEdit: null }) };
  });
  const mkNotes = (list) => list.map((n0, i) => {
    const text = s.ne[i] || n0; const editing = s.nEdit === i;
    return { text, edited: s.ne[i] !== undefined, isEdit: editing, notEdit: !editing, draft: s.nText,
      startEdit: () => this.setState({ nEdit: i, nText: text }), setDraft: (e) => this.setState({ nText: e.target.value }),
      save: () => this.setState({ nEdit: null, ne: { ...s.ne, [i]: s.nText } }), cancel: () => this.setState({ nEdit: null }) };
  });

  const answers = K.answers.map((a) => { const prev = a[4] || []; const changed = prev.length > 0 && prev[prev.length - 1] !== a[2]; return { id: a[0], q: a[1], ans: a[2], prev, changed, fw: a[3] || changed ? 700 : 500, bg: a[3] ? '#F8FBFD' : 'transparent', flagText: a[3] ? '확인 필요' : '' }; });
  const notes = mkNotes(K.notes);
  const allQs = mkQs(K.qs);
  const flags = K.flags.map((f, i) => ({ goSrc: () => goStt(f.stt), q: f.q, src: f.src, n: notes.at(i), qs: (f.qi || []).map((j) => allQs.at(j)), flow: f.flow.map((t, j) => ({ t, cls: j === f.flow.length - 1 ? 'v now' : 'v' })) }));
  const famNotes = K.famNotes.map((m) => ({ who: m[0], at: m[1], text: m[2] }));
  return { k: { ...K, hasQuote: !!K.quote }, answers, flags, flagCount: flags.length, famNotes, goAns };
}
}
