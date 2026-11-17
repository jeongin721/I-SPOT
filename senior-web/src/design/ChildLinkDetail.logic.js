// ChildLinkDetail 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/ChildLinkDetail.jsx)이 이어받아 데이터만 바꾼다.
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/ChildLinkDetail'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { qok: {}, qe: {}, qEdit: null, dText: '', dOpts: '', ne: {}, nEdit: null, nText: '' }; }
renderValsBase() {
  const K = { ...{ name: '서복례', short: '서복례 님', ini: '서', age: '만 85세 · 여 · 독거', types: '고립·외로움 · 건강·인지', id: 'C-2026-0389', reason: '식사 거름 반복', rCls: 'chip c-check', last: '어제 21:05', count: '20 / 21일', next: '10/22 정기상담 5회차', urgent: false,
    app: '어르신 안부 앱 · 큰 글씨 · 음성 답변 사용', quote: '혼자 먹으니 밥맛이 없어요', quoteAt: '음성 답변 · 어제 21:06',
    famConsent: '가족 공유 · 일부 동의', famCls: 'chip c-sand', famScope: '공유 범위: 상담 일정 · 안부 응답 여부 (상담 내용은 비공유)',
    famNotes: [['딸 · 김미영 (가족 연계)', '10/17 19:30', '지난 주말에 가 보니 냉장고 반찬이 거의 그대로였어요. 전화로는 괜찮다고만 하세요.'], ['딸 · 김미영 (가족 연계)', '10/10 20:05', '요즘 같은 이야기를 여러 번 물어보세요. 약은 제가 요일별 약통에 넣어 드렸어요.']],
    answers: [['공통 1', '어젯밤 잠은 잘 주무셨어요?', '밤에 자꾸 깨요', false, ['잘 잤어요', '잘 잤어요', '밤에 자꾸 깨요']], ['공통 2', '식사는 잘 하셨어요?', '조금 먹었어요', false, ['잘 먹었어요', '조금 먹었어요', '조금 먹었어요']], ['공통 3', '오늘 기분은 어떠세요?', '울적해요', false, ['좋아요', '그저 그래요', '그저 그래요']],
      ['SQ-M-02', '이번 주에 식사를 거르신 날은 며칠이에요?', '5일 이상', true, ['0일', '1~2일', '1~2일']], ['SQ-S-03', '어제 누구와 이야기 나누셨어요?', '아무도 없었어요', true, ['복지관 선생님', '딸', '복지관 선생님']], ['SQ-L-01', '오늘 복지관(경로당)에 다녀오셨어요?', '다녀왔어요', false, ['다녀왔어요', '다녀왔어요', '다녀왔어요']], ['SQ-H-01', '요즘 몸이 불편한 곳이 있으세요?', '무릎이 좀 아파요', false, ['괜찮아요', '괜찮아요', '무릎이 좀 아파요']]],
    flags: [{ q: '이번 주에 식사를 거르신 날은 며칠이에요? (SQ-M-02)', flow: ['0일', '1~2일', '1~2일', '5일 이상'], src: '어제 21:05 응답 · 3회차 상담일지', stt: '02:15', qi: [1] },
            { q: '어제 누구와 이야기 나누셨어요? (SQ-S-03)', flow: ['복지관 선생님', '딸', '복지관 선생님', '아무도 없었어요'], src: '어제 21:05 응답 · 21:06 어르신이 남긴 말씀', stt: '03:05', qi: [0] }],
    notes: ['3주째 늘고 있고, 이번에 처음 "5일 이상"이 나왔어요. 3회차 상담 말씀, 가족 관찰 메모(반찬이 그대로)와 같은 방향이에요. 다음 상담에서 식사 준비 어려움과 도시락·반찬 지원 연계를 확인해 보세요. (확인 제안)', '하루 동안 아무와도 이야기하지 않으셨다는 답이 처음 나왔어요. 어르신이 남긴 말씀과 같은 내용이에요. 교류 빈도와 외로움 정도를 확인해 보세요. (확인 제안)'],
    qs: [{ id: 'SQ-S-05', text: '요즘 마음 편하게 이야기 나누실 분이 계세요?', opts: ['자주 있어요', '가끔 있어요', '거의 없어요', '말하기 어려워요'], why: 'SQ-S-03 응답 · 어르신이 남긴 말씀', stt: '03:05', sendNote: '오늘 저녁 안부에 추가' },
         { id: 'SQ-M-04', text: '요즘 끼니는 주로 어떻게 챙겨 드세요?', opts: ['직접 해 먹어요', '반찬을 받아요', '사 먹어요', '자주 걸러요'], why: 'SQ-M-02 응답', stt: '02:15', sendNote: '오늘 저녁 안부에 추가' }] }, short0: '서' };
  const s = this.state;
  this._goAns = () => { const v = 'C-2026-0389|' + Date.now(); try { window.localStorage.setItem('ispot-senior', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-senior', v); } catch (e) {} try { window.top.__ispotSenior = v; } catch (e) {} window.__ispotSenior = v; };
  const goStt = (t) => { if (!t) return; const v = t + '|' + Date.now(); try { window.localStorage.setItem('ispot-stt', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-stt', v); } catch (e) {} try { window.top.__ispotStt = v; } catch (e) {} window.__ispotStt = v; };
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

  const answers = K.answers.filter((a) => !/^공통/.test(a[0])).map((a) => { const prev = a[4] || []; const changed = prev.length > 0 && prev[prev.length - 1] !== a[2]; return { id: a[0], q: a[1], ans: a[2], prev, changed, fw: a[3] || changed ? 700 : 500, bg: a[3] ? '#F8FBFD' : 'transparent', flagText: a[3] ? '확인 필요' : '' }; });
  const notes = mkNotes(K.notes);
  const allQs = mkQs(K.qs);
  const flags = K.flags.map((f, i) => ({ goSrc: () => goStt(f.stt), q: f.q, src: f.src, n: notes.at(i), qs: (f.qi || []).map((j) => allQs.at(j)), flow: f.flow.map((t, j) => ({ t, cls: j === f.flow.length - 1 ? 'v now' : 'v' })) }));
  const famNotes = K.famNotes.map((m) => ({ who: m[0], at: m[1], text: m[2] }));
  return { k: { ...K, hasQuote: !!K.quote }, answers, flags, flagCount: flags.length, famNotes, goAns: this._goAns };
}
}
