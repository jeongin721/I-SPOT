// AppSchedule 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AppSchedule.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {

stGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
stSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
themeRead() { let v = null; try { v = window.localStorage.getItem('ispot-theme'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-theme'); } catch (e) {} } if (!v) { try { v = window.top.__ispotTheme; } catch (e) {} } if (!v) v = window.__ispotTheme; return v === 'dark'; }
qRead() { let a = null; try { a = JSON.parse(this.stGet('ispot-app-q') || 'null'); } catch (e) {} if (!Array.isArray(a)) { a = [
  { id: 'q1', name: '김순자_8회차_방문상담.m4a', kind: '녹음', who: '김순자 · 8회차', size: '23.4MB', status: 'fail', err: '네트워크 연결이 끊겨 올리지 못했어요', t: '오늘 15:42' },
  { id: 'q2', name: '상담동의서_사진_01.jpg', kind: '사진', who: '오금자', size: '2.1MB', status: 'done', t: '오늘 11:05' },
  { id: 'q3', name: '복지관_이용확인서.pdf', kind: '문서', who: '서복례', size: '480KB', status: 'done', t: '어제 17:20' }]; this.stSet('ispot-app-q', JSON.stringify(a)); } return a; }
qWrite(a) { this.stSet('ispot-app-q', JSON.stringify(a)); this.setState({ __q: Date.now() }); }
qSet(id, patch) { this.qWrite(this.qRead().map((x) => (x.id === id ? { ...x, ...patch } : x))); }
qRetry(id) { this.qSet(id, { status: 'run', err: '' }); setTimeout(() => { try { this.qSet(id, { status: 'done', t: '방금' }); } catch (e) {} }, 1800); }
qAdd(item) { const id = 'q' + Date.now().toString(36); this.qWrite([{ id, status: 'run', t: '방금', ...item }, ...this.qRead()]); setTimeout(() => { try { this.qSet(id, { status: 'done' }); } catch (e) {} }, 2000); return id; }
elders() { return ['김순자', '서복례', '오금자', '이정희', '윤기철', '최만석', '강덕수', '한옥분', '정말순', '박영수']; }
componentDidMount() {
  this._raw = this.stGet('ispot-app-q') + '|' + this.themeRead();
  this._t = setInterval(() => { const r = this.stGet('ispot-app-q') + '|' + this.themeRead(); if (r !== this._raw) { this._raw = r; this.setState({ __t: Date.now() }); } }, 600);
  if (this.mountExtra) this.mountExtra();
}
componentWillUnmount() { clearInterval(this._t); clearInterval(this._recT); }
commonVals(cur) {
  const q = this.qRead(); const fails = q.filter((x) => x.status === 'fail'); const st = this.state || {};
  const notes = fails.map((x) => ({ red: 'red', title: '업로드 실패 · ' + x.kind, sub: x.name + ' · ' + x.t, desc: x.err || '', hasAct: true, act: '다시 올리기', go: () => this.qRetry(x.id), hasLink: false, href: '', linkLabel: '', nav: () => {} }))
    .concat([{ red: '', title: '다음 상담 준비가 됐어요', sub: '오늘 16:00 · 김순자 · 9회차 정기상담', desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: '#/AppNext', linkLabel: '다음 상담 준비 보기', nav: () => { const f = this._self || ({ home: '#/AppHome', cases: '#/AppCases', cal: '#/AppSchedule', memo: '#/AppMemo', up: '#/AppUpload', rec: '#/AppRecord', set: '#/AppSettings' })[cur]; if (f && f !== '#/AppNext') this.stSet('ispot-app-from', f); } },
      { red: '', title: '오늘 남은 상담 2건', sub: '14:00 서복례 · 16:00 김순자', desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: '#/AppSchedule', linkLabel: '일정 보기', nav: () => {} }]);
  return {
    rootCls: this.themeRead() ? 'app dark' : 'app',
    tabs: [['home', '홈', '#/AppHome'], ['up', '업로드', '#/AppUpload'], ['rec', '', '#/AppRecord'], ['cal', '일정', '#/AppSchedule'], ['memo', '메모', '#/AppMemo']].map(([k, label, href]) => ({ label, href, aria: k === 'rec' ? '녹음' : label, cls: 'tab' + (k === 'rec' ? ' tab-rec' : '') + (k === cur ? ' on' : ''), cur: k === cur ? 'page' : 'false', isHome: k === 'home', isRec: k === 'rec', isUp: k === 'up', isCal: k === 'cal', isMemo: k === 'memo', hasLabel: !!label })),
    homeCls: cur === 'home' ? 'ibtn on' : 'ibtn', setCls: cur === 'set' ? 'ibtn on' : 'ibtn', homeCur: cur === 'home' ? 'page' : 'false', setCur: cur === 'set' ? 'page' : 'false',
    ntCount: String(notes.length), ntHas: notes.length > 0, ntOpen: !!st.__nt, ntToggle: () => this.setState({ __nt: !st.__nt }), ntClose: () => this.setState({ __nt: false }), notes,
    failN: fails.length, hasFail: fails.length > 0, failText: '업로드 실패 ' + fails.length + '건 · 다시 올려 주세요'
  };
}


constructor(props) { super(props); const now = new Date(); const td = now.getFullYear() === 2026 && now.getMonth() === 9 && now.getDate() >= 26 ? now.getDate() - 26 : (now.getFullYear() === 2026 && now.getMonth() === 10 && now.getDate() === 1 ? 6 : 3);
  this.state = { day: td, today: td, sheet: null, ask: false, f: {}, events: [
    { id: 1, day: 0, time: '10:00', t: 'p', title: '시니어 사례회의', place: '3층 회의실' },
    { id: 2, day: 1, time: '16:00', t: 'c', elder: '오금자', ctype: '정기상담 8회차', place: '상담실 A (내방)' },
    { id: 3, day: 2, time: '13:00', t: 'c', elder: '이정희', ctype: '방문상담', place: '어르신 자택 방문' },
    { id: 4, day: 3, time: '10:00', t: 'p', title: '슈퍼비전', place: '팀장실' },
    { id: 5, day: 3, time: '14:00', t: 'c', elder: '서복례', ctype: '정기상담 6회차', place: '상담실 A (내방)' },
    { id: 6, day: 3, time: '16:00', t: 'c', elder: '김순자', ctype: '정기상담 9회차', place: '어르신 자택 방문', brief: true },
    { id: 7, day: 4, time: '15:00', t: 'c', elder: '윤기철', ctype: '전화상담', place: '전화 (천천히 · 크게)' }] }; }
renderVals() {
  const s = this.state; const DOW = ['월', '화', '수', '목', '금', '토', '일'];
  const dateOf = (i) => { const d = new Date(2026, 9, 26 + i); return { m: d.getMonth() + 1, n: d.getDate() }; };
  const dw = (i) => ((i % 7) + 7) % 7; const ws = s.day - dw(s.day);
  const lab = (i) => { const d = dateOf(i); return d.m + '월 ' + d.n + '일 ' + DOW[dw(i)] + '요일'; };
  const titleOf = (e) => (e.t === 'c' ? e.elder + ' · ' + e.ctype : e.title);
  const stop = (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); };
  const days = DOW.map((dow, k) => { const i = ws + k; return { dow, n: String(dateOf(i).n), sel: i === s.day ? 'true' : 'false', cls: 'day' + (i === s.day ? ' on' : '') + (i === s.today ? ' today' : ''), dot: s.events.some((e) => e.day === i) ? 'dot' : 'dot no', pick: () => this.setState({ day: i }) }; });
  const cells = []; for (let i = -28; i <= 6; i++) { const d = dateOf(i); const has = s.events.some((e) => e.day === i);
    cells.push({ n: String(d.n), sel: i === s.day ? 'true' : 'false', aria: d.m + '월 ' + d.n + '일' + (has ? ' · 일정 있음' : ''), cls: 'mc' + (d.m !== 10 ? ' out' : '') + (i === s.day ? ' on' : '') + (i === s.today ? ' today' : ''), dot: has ? 'dot' : 'dot no', pick: () => this.setState({ day: i, exp: false }) }); }
  const evs = s.events.filter((e) => e.day === s.day).sort((a, b) => a.time.localeCompare(b.time)).map((e) => ({ time: e.time, title: titleOf(e), sub: e.place || '장소 미정', tag: e.t === 'c' ? '상담' : '개인 · 기관', chipCls: e.t === 'c' ? 'chip gold' : 'chip', isC: e.t === 'c', brief: !!e.brief, noBrief: !e.brief, aria: titleOf(e) + ' 자세히 보기',
    open: () => this.setState({ sheet: { mode: 'view', id: e.id }, ask: false }), stop, toBrief: (ev) => { stop(ev); this.stSet('ispot-app-from', '#/AppSchedule'); }, rec: (ev) => { stop(ev); this.stSet('ispot-app-rec', JSON.stringify({ elder: e.elder, t: Date.now() })); } }));
  const cur = s.sheet && s.sheet.id ? s.events.find((e) => e.id === s.sheet.id) : null;
  const v = cur ? { title: titleOf(cur), tag: cur.t === 'c' ? '상담' : '개인 · 기관', chipCls: cur.t === 'c' ? 'chip gold' : 'chip',
    rows: [['날짜', lab(cur.day)], ['시간', cur.time], ['장소', cur.place || '—']].concat(cur.t === 'c' ? [['다음 상담 준비', cur.brief ? '준비됨' : '준비 중']] : []).map(([k, val]) => ({ k, v: val })),
    edit: () => this.setState({ sheet: { mode: 'form', id: cur.id }, f: { t: cur.t, elder: cur.elder || '김순자', ctype: cur.t === 'c' ? cur.ctype.split(' ')[0] : '정기상담', suffix: cur.t === 'c' ? cur.ctype.split(' ').slice(1).join(' ') : '', title: cur.title || '', day: String(cur.day), time: cur.time, place: cur.place || '' } }),
    askDel: () => this.setState({ ask: true }), cancelDel: () => this.setState({ ask: false }), del: () => this.setState({ events: s.events.filter((e) => e.id !== cur.id), sheet: null, ask: false }) } : {};
  const f = s.f || {}; const isC = (f.t || 'c') === 'c'; const setF = (k) => (ev) => this.setState({ f: { ...this.state.f, [k]: ev.target.value } });
  return Object.assign(this.commonVals('cal'), { stop, monthLabel: ws === s.today - dw(s.today) ? '2026년 10월 · 이번 주' : dateOf(ws).m + '/' + dateOf(ws).n + ' 주', days, cells, dows: DOW, calMonth: '2026년 10월',
    exp: !!s.exp, notExp: !s.exp, expA: s.exp ? 'true' : 'false', expLabel: s.exp ? '접기 ▴' : '펼치기 ▾', toggleExp: () => this.setState({ exp: !this.state.exp }), goToday: () => this.setState({ day: this.state.today }), dayLabel: lab(s.day), evs, noEv: evs.length === 0,
    shView: !!(s.sheet && s.sheet.mode === 'view' && cur), shForm: !!(s.sheet && s.sheet.mode === 'form'), shClose: () => this.setState({ sheet: null, ask: false }), v, ask: !!s.ask, noAsk: !s.ask,
    openAdd: () => this.setState({ sheet: { mode: 'form', id: null }, f: { t: 'c', elder: '김순자', ctype: '정기상담', suffix: '', title: '', day: String(s.day), time: '10:00', place: '' } }),
    formTitle: s.sheet && s.sheet.id ? '일정 수정' : '일정 추가', isC, isP: !isC, kC: isC ? 'true' : 'false', kP: isC ? 'false' : 'true', kCcls: isC ? 'on' : '', kPcls: isC ? '' : 'on',
    kindC: () => this.setState({ f: { ...f, t: 'c' } }), kindP: () => this.setState({ f: { ...f, t: 'p' } }), f, elderOpts: this.elders(),
    dayOpts: DOW.map((d, k) => { const fd = parseInt(f.day, 10); const w0 = (isNaN(fd) ? s.day : fd) - dw(isNaN(fd) ? s.day : fd); const i = w0 + k; return { v: String(i), label: dateOf(i).m + '/' + dateOf(i).n + ' (' + d + ')' }; }),
    setChild: setF('elder'), setCtype: setF('ctype'), setTitle: setF('title'), setDay: setF('day'), setTime: setF('time'), setPlace: setF('place'),
    save: () => { const ff = this.state.f; const day = isNaN(parseInt(ff.day, 10)) ? s.day : parseInt(ff.day, 10); const base = ff.t === 'c' ? { t: 'c', elder: ff.elder, ctype: ff.ctype + (ff.suffix ? ' ' + ff.suffix : ''), title: '' } : { t: 'p', title: (ff.title || '').trim() || '개인 일정' };
      const id = s.sheet && s.sheet.id; const old = id ? s.events.find((e) => e.id === id) : null; const ev = { ...(old || {}), ...base, id: id || Date.now(), day, time: ff.time || '10:00', place: ff.place || '' };
      this.setState({ events: id ? s.events.map((e) => (e.id === id ? ev : e)) : [...s.events, ev], sheet: null, day }); } });
}

}
