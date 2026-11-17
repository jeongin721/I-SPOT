// ChildLinkHistory 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/ChildLinkHistory.jsx)이 이어받아 데이터만 바꾼다.
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

seniorRead() { let v = null; try { v = window.localStorage.getItem('ispot-senior'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-senior'); } catch (e) {} } if (!v) { try { v = window.top.__ispotSenior; } catch (e) {} } if (!v) v = window.__ispotSenior; return String(v || 'C-2026-0389').split('|')[0]; }
seniorSync() { const id = this.seniorRead(); if (id !== this.state.cid) this.setState({ cid: id, day: '2026-10-19' }); }
componentDidMountBase() { this.seniorSync(); this._chT = setInterval(() => this.seniorSync(), 300); }
componentWillUnmountBase() { clearInterval(this._chT); }
constructor(props) { super(props); this.state = { per: 14, view: 'q', day: '2026-10-19', cid: 'C-2026-0389' }; }
renderValsBase() {
  const s = this.state;
  const SETS = {
    'C-2026-0389': { k: { name: '서복례', short: '서복례 님', short0: '서', age: '만 85세 · 여 · 독거', id: 'C-2026-0389', home: '#/ChildLink', homeLabel: '안부 연계', back: '#/ChildLinkDetail' }, time: '21:05',
      miss: { '2026-10-03': true }, quotes: { '2026-10-19': ['혼자 먹으니 밥맛이 없어요', '음성 · 21:06'], '2026-10-14': ['오늘 복지관에서 노래 교실 했어요. 오랜만에 웃었어요', '음성 · 20:41'] },
      bad: { '5일 이상': 1, '아무도 없었어요': 1, '울적해요': 1, '밤에 자꾸 깨요': 1 },
      q: [
        { id: '공통 1', q: '어젯밤 잠은 잘 주무셨어요?', w: ['잘 잤어요', '잘 잤어요', '자다 깼어요', '밤에 자꾸 깨요'] },
        { id: '공통 2', q: '식사는 잘 하셨어요?', w: ['잘 먹었어요', '잘 먹었어요', '밥은 조금 먹었어요', '밥은 조금 먹었어요'] },
        { id: '공통 3', q: '오늘 기분은 어떠세요?', w: ['좋아요', '그저 그래요', '그저 그래요', '울적해요'], alt: { 2: ['그저 그래요', '좀 쓸쓸해요'] } },
        { id: 'SQ-M-02', q: '이번 주에 식사를 거르신 날은 며칠이에요?', w: ['0일', '1~2일', '1~2일', '5일 이상'], weekly: true },
        { id: 'SQ-S-03', q: '어제 누구와 이야기 나누셨어요?', w: ['복지관 선생님', '딸이랑 통화했어요', '복지관 선생님', '아무도 없었어요'], alt: { 2: ['딸이랑 통화했어요', '복지관 선생님'] } },
        { id: 'SQ-L-01', q: '오늘 복지관(경로당)에 다녀오셨어요?', w: ['다녀왔어요', '다녀왔어요', '다녀왔어요', '다녀왔어요'], school: true },
        { id: 'SQ-H-01', q: '요즘 몸이 불편한 곳이 있으세요?', w: ['괜찮아요', '괜찮아요', '무릎이 좀 아파요', '무릎이 좀 아파요'], alt: { 2: ['괜찮아요', '무릎이 좀 아파요'] } }] },
    'C-2026-0351': { k: { name: '김순자', short: '김순자 님', short0: '김', age: '만 82세 · 여 · 독거', id: 'C-2026-0351', home: '#/CaseList', homeLabel: '대상자 관리', back: '#/CaseApp' }, time: '22:10',
      miss: { '2026-10-03': true, '2026-10-11': true }, quotes: { '2026-10-19': ['다음에 오시면 드릴 말씀이 있어요', '음성 · 22:10'] },
      bad: { '매일 나요': 1, '조금 울적해요': 1, '밤에 자꾸 깨요': 1, '집이 너무 조용해요': 1 },
      q: [
        { id: '공통 1', q: '어젯밤 잠은 잘 주무셨어요?', w: ['자다 깼어요', '자다 깼어요', '밤에 자꾸 깨요', '밤에 자꾸 깨요'] },
        { id: '공통 2', q: '식사는 잘 하셨어요?', w: ['조금 먹었어요', '조금 먹었어요', '밥은 조금 먹었어요', '밥은 조금 먹었어요'] },
        { id: '공통 3', q: '오늘 기분은 어떠세요?', w: ['그저 그래요', '그저 그래요', '조금 울적해요', '조금 울적해요'], alt: { 1: ['그저 그래요', '조금 울적해요'] } },
        { id: 'SQ-E-05', q: '요즘 혼자 계실 때 영감님 생각이 많이 나세요?', w: ['가끔요', '가끔요', '가끔요', '매일 나요'], weekly: true },
        { id: 'SQ-H-01', q: '요즘 몸이 불편한 곳이 있으세요?', w: ['괜찮아요', '괜찮아요', '허리가 좀 아파요', '괜찮아요'] },
        { id: 'SQ-E-03', q: '집에 계실 때 마음은 어떠세요?', w: ['편해요', '그저 그래요', '그저 그래요', '집이 너무 조용해요'], alt: { 2: ['그저 그래요', '집이 너무 조용해요'] } }] }
  };
  const SET = SETS[s.cid] || SETS['C-2026-0389'];
  const K = SET.k;
  const END = new Date(2026, 9, 19); const ALLD = 28;
  const DOW = ['일', '월', '화', '수', '목', '금', '토'];
  const iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const dates = []; for (let i = 0; i < ALLD; i++) { const d = new Date(END); d.setDate(END.getDate() - i); dates.push(d); }
  const week = (d) => { const diff = Math.round((END - d) / 86400000); return diff === 0 ? 3 : diff <= 6 ? 2 : diff <= 13 ? 1 : 0; };
  const MISS = SET.miss;
  const Q = SET.q;
  const BAD = SET.bad;
  const ansOf = (q, d) => { const k = iso(d); if (MISS[k]) return null; if (q.weekly && d.getDay() !== 1) return ''; if (q.school && (d.getDay() === 0 || d.getDay() === 6)) return '쉬는 날';
    const wk = week(d); if (q.alt && q.alt[wk]) { const a = q.alt[wk]; const diff = Math.round((END - d) / 86400000); return diff >= (wk === 2 ? 4 : wk === 1 ? 10 : 17) ? a[0] : a[1]; } return q.w[wk]; };
  const QUOTES = SET.quotes;
  /* 이전 답(바로 앞에 응답한 날 기준) */
  const prevOf = (q, idx) => { for (let j = idx + 1; j < ALLD; j++) { const v = ansOf(q, dates[j]); if (v && v !== '쉬는 날') return v; } return ''; };
  const shown = dates.slice(0, s.per);
  const cols = shown.map((d) => ({ md: (d.getMonth() + 1) + '/' + d.getDate(), dow: DOW[d.getDay()] + (MISS[iso(d)] ? ' · 무응답' : '') }));
  const rows = Q.map((q) => ({ id: q.id, q: q.q, cells: shown.map((d, i) => { const v = ansOf(q, d); if (v === null) return { v: '—', cls: 'miss' }; if (v === '') return { v: '', cls: 'blank' };
    const p = prevOf(q, i); const ch = v !== '쉬는 날' && p && p !== v; return { v, cls: [BAD[v] ? 'bad' : '', ch ? 'chg2' : ''].join(' ').trim() }; }) }));
  const answered = dates.filter((d) => !MISS[iso(d)]).length;
  const dayIdx = Math.max(0, dates.findIndex((d) => iso(d) === s.day)); const dd = dates[dayIdx];
  const items = Q.map((q) => { const v = ansOf(q, dd); if (!v) return null; const p = prevOf(q, dayIdx); const ch = v !== '쉬는 날' && p && p !== v;
    return { id: q.id, q: q.q, v, prev: p || '—', changed: !!ch, fw: BAD[v] || ch ? 700 : 500, bg: BAD[v] ? '#F8FBFD' : 'transparent' }; }).filter(Boolean);
  const qd = QUOTES[s.day];
  const day = { label: (dd.getMonth() + 1) + '월 ' + dd.getDate() + '일 (' + DOW[dd.getDay()] + ')', time: MISS[s.day] ? '' : SET.time + ' 응답', items, has: items.length > 0, none: !!MISS[s.day], hasQuote: !!qd, quote: qd ? qd[0] : '', quoteAt: qd ? qd[1] : '' };
  const dateList = shown.map((d) => { const k = iso(d); const bad = Q.some((q) => BAD[ansOf(q, d)]); const on = k === s.day;
    return { label: (d.getMonth() + 1) + '/' + d.getDate() + ' (' + DOW[d.getDay()] + ')', meta: MISS[k] ? '무응답' : (QUOTES[k] ? '남기신 말씀 있음' : (bad ? '확인 필요한 답 있음' : '응답함')), cls: on ? 'on' : '', on: on ? 'true' : 'false', pick: () => this.setState({ day: k }) }; });
  const periods = [[7, '최근 1주'], [14, '최근 2주'], [28, '최근 4주']].map(([n, label]) => ({ label, cls: s.per === n ? 'on' : '', on: s.per === n ? 'true' : 'false', pick: () => this.setState({ per: n }) }));
  const views = [['q', '문항별'], ['d', '날짜별']].map(([k, label]) => ({ label, cls: s.view === k ? 'on' : '', on: s.view === k ? 'true' : 'false', pick: () => this.setState({ view: k }) }));
  return { k: K, cols, rows, periods, views, byQ: s.view === 'q', byD: s.view === 'd', dates: dateList, day, answered, days: ALLD };
}
}
