// Schedule 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Schedule.jsx)이 이어받아 데이터만 바꾼다.
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
ntTasks() { return [[3, '어르신 전화 안부 상담'], [7, '가족(보호자) 상담'], [30, '상담 계획서 작성']]; }
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
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Schedule'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

  constructor(props) {
    super(props);
    const now = new Date();
    const inOct = now.getFullYear() === 2026 && now.getMonth() === 9;
    const C = (d, time, title, sub) => ({ y: 2026, m: 9, d, time, t: 'c', title, sub, tag: '상담' });
    const P = (d, time, title, sub) => ({ y: 2026, m: 9, d, time, t: 'p', title, sub, tag: sub });
    this.state = {
      y: 2026, m: 9, sel: inOct ? now.getDate() : 8, filter: 'all', adding: false, kind: 'c',
      form: { child: '김순자 님', ctype: '방문상담', pcat: '기관 회의', title: '', time: '10:00', place: '', imp: false },
      events: [
        C(2, '15:00', '김순자 님 · 정기상담 8회차', '어르신 댁 방문'),
        P(5, '10:00', '기관 사례회의', '기관 회의'),
        C(6, '11:00', '오금자 님 · 내방상담 6회차', '상담실 A'),
        C(7, '14:00', '이정희 님 · 가족 상담 2회차', '상담실 B'),
        P(8, '10:00', '기관 사례회의', '기관 회의'),
        C(8, '13:00', '서복례 님 · 정기상담 4회차', '상담실 A'),
        C(8, '14:30', '최만석 님 · 초기상담', '어르신 댁 방문'),
        C(8, '16:00', '김순자 님 · 정기상담 9회차', '상담실 B'),
        P(8, '17:30', '슈퍼비전', '슈퍼비전'),
        P(12, '09:30', '자살예방 게이트키퍼 교육', '교육'),
        C(12, '11:00', '오금자 님 · 내방상담 7회차', '상담실 A'),
        C(13, '16:00', '윤기철 님 · 전화상담', '전화'),
        { ...C(14, '15:00', '강덕수 님 · 종결 상담', '상담실 A'), imp: true },
        C(15, '15:00', '한옥분 님 · 정기상담', '상담실 B'),
        C(16, '14:00', '김순자 님 · 정기상담 10회차', '상담실 B'),
        P(19, '종일', '연가', '휴가'),
        C(20, '10:00', '정말순 님 · 방문상담', '어르신 댁 방문'),
        { ...P(21, '14:00', '통합돌봄 지역 사례회의 (행정복지센터)', '기관 회의'), imp: true },
        C(22, '13:00', '서복례 님 · 정기상담 5회차', '상담실 A'),
        P(23, '15:00', '팀 회의', '기관 회의'),
        P(26, '10:00', '기관 사례회의', '기관 회의'),
        P(27, '10:00', '노인복지관 여가 프로그램 연계 동행', '복지관 프로그램 연계'),
        C(27, '16:00', '오금자 님 · 내방상담 8회차', '상담실 A'),
        P(29, '10:00', '슈퍼비전', '슈퍼비전'),
        C(29, '14:00', '박영수 님 · 가족 상담', '상담실 B')
      ]
    };
    try { const g = this.ntGo0(); if (g) { this.state.y = g.y; this.state.m = g.m; this.state.sel = g.d; } } catch (e) {}
  }
  schedGo(y, m, d) { this.setState({ y, m, sel: d, adding: false }); }
  schedExtra() { try { const a = JSON.parse(this.ntGet('ispot-sched-extra') || '[]'); return Array.isArray(a) ? a.filter((e) => e && typeof e.y === 'number' && typeof e.m === 'number' && typeof e.d === 'number') : []; } catch (e) { return []; } }
  renderValsBase() {
    const s = this.state;
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    const holidays = { '2026-9-3': '개천절', '2026-9-9': '한글날' };
    const now = new Date();
    const first = new Date(s.y, s.m, 1).getDay();
    const dim = new Date(s.y, s.m + 1, 0).getDate();
    const total = Math.ceil((first + dim) / 7) * 7;
    const recs = this.ntRecs();
    const updRec = (id, fn) => { this.ntSave(this.ntRecs().map((r) => (r.id === id ? fn(r) : r))); this.setState({ __ntTick: Date.now() }); };
    const derived = [];
    recs.forEach((r) => {
      derived.push({ y: r.y, m: r.m, d: r.d, time: r.time || '10:00', t: 'p', title: r.child + ' · 최초접수', sub: r.place ? '최초접수 · ' + r.place : '최초접수 · 의뢰 접수 후 배정', tag: '최초접수', imp: !!r.imp, rid: r.id });
      this.ntTasks().forEach(([n, task]) => { const dd = new Date(r.y, r.m, r.d + n); const done = !!(r.done || {})[n];
        derived.push({ y: dd.getFullYear(), m: dd.getMonth(), d: dd.getDate(), time: '기한', t: 'p', title: (done ? '✓ ' : '') + r.child + ' · ' + task, sub: '접수 후 ' + n + '일 이내 · ' + (r.m + 1) + '/' + r.d + ' 접수', tag: '처리 기한', imp: !done, rid: r.id, dl: n, done }); });
    });
    const extra = this.schedExtra(); const saveExtra = (a) => { this.ntSet('ispot-sched-extra', JSON.stringify(a)); };
    const allEv = [...s.events.map((e, i) => ({ ...e, i })), ...extra.map((e, k) => ({ ...e, xi: k })), ...derived];
    const keyOf = (e) => (e.dl ? { src: 'dl', id: e.rid, n: e.dl } : e.rid ? { src: 'rec', id: e.rid } : e.xi != null ? { src: 'ex', k: e.xi } : { src: 'ev', i: e.i });
    const findKey = (k) => (!k ? null : allEv.find((e) => (k.src === 'ex' ? e.xi === k.k : k.src === 'ev' ? e.i === k.i && !e.rid && e.xi == null : k.src === 'rec' ? e.rid === k.id && !e.dl : e.rid === k.id && e.dl === k.n)) || null);
    const show = (e) => s.filter === 'all' || (s.filter === 'i' ? !!e.imp : e.t === s.filter);
    const rk = (t) => (t === '종일' ? 0 : t === '기한' ? 1 : 2); const sortT = (a, b) => (rk(a.time) - rk(b.time) || a.time.localeCompare(b.time));
    const style = (e) => e.imp
      ? { bg: '#F7E4DF', fg: '#A33B2E', dot: '#A33B2E', radius: e.t === 'c' ? '50%' : '2px', tagBg: '#F7E4DF', tagFg: '#A33B2E', fw: 700 }
      : e.t === 'c'
      ? { bg: '#ECF5FA', fg: '#1F3A56', dot: '#66788A', radius: '50%', tagBg: '#ECF5FA', tagFg: '#55687A', fw: 400 }
      : { bg: '#F8FBFD', fg: '#55687A', dot: '#A0B0BB', radius: '2px', tagBg: '#F8FBFD', tagFg: '#55687A', fw: 400 };
    const cells = [];
    for (let i = 0; i < total; i++) {
      const d = i - first + 1;
      const valid = d >= 1 && d <= dim;
      const dow = i % 7;
      const evs = valid ? allEv.filter((e) => e.y === s.y && e.m === s.m && e.d === d && show(e)).sort(sortT) : [];
      const isToday = valid && now.getFullYear() === s.y && now.getMonth() === s.m && now.getDate() === d;
      const isSel = valid && d === s.sel;
      const hol = valid ? (holidays[`${s.y}-${s.m}-${d}`] || '') : '';
      cells.push({
        num: valid ? String(d) : '',
        holiday: hol,
        aria: valid ? `${s.m + 1}월 ${d}일 일정 ${evs.length}건` : '빈 칸',
        bg: valid ? (isSel ? '#E8F4FC' : '#FFFFFF') : '#F8FBFD',
        ring: isSel ? 'inset 0 0 0 2px #1F3A56' : 'none',
        numBg: isToday ? '#1F3A56' : 'transparent',
        numFg: isToday ? '#FFFFFF' : (hol || dow === 0 ? '#66788A' : '#1F3A56'),
        fw: isToday || isSel ? 700 : 400,
        pills: evs.slice(0, 3).map((e) => { const st = style(e); return { label: `${e.time === '종일' ? '' : e.time + ' '}${e.title}`, time: e.time === '종일' ? '' : e.time, who: (e.title.split(' · ').length > 1 ? e.title.split(' · ')[0] : ''), hasHead: e.time !== '종일' || e.title.split(' · ').length > 1, body: (e.title.split(' · ').length > 1 ? e.title.split(' · ').slice(1).join(' · ') : e.title), title: e.title, bg: st.bg, fg: st.fg, fw: st.fw, dot: st.dot, radius: st.radius, tip: e.title + ' · 자세히 보기', open: (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); this.setState({ sel: d, view: keyOf(e), adding: false, edit: null, delAsk: false }); } }; }),
        more: evs.length > 3 ? `+${evs.length - 3}건 더` : '',
        pick: () => { if (valid) this.setState({ sel: d, view: null, delAsk: false }); }
      });
    }
    const selDate = new Date(s.y, s.m, s.sel);
    const wrapRow = (e, out) => { const stop = (fn) => (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); fn(ev); }; const go = () => this.setState({ view: keyOf(e), adding: false, edit: null, delAsk: false });
      return { ...out, toggleImp: stop(out.toggleImp), open: go, key: (ev) => { if (ev && (ev.key === 'Enter' || ev.key === ' ')) { if (ev.preventDefault) ev.preventDefault(); go(); } }, aria: e.title + ' 자세히 보기' }; };
    const dayEvents = allEv.filter((e) => e.y === s.y && e.m === s.m && e.d === s.sel && show(e)).sort(sortT).map((e) => wrapRow(e, ((e) => { const st = style(e); const on = !!e.imp;
      const row = { time: e.time, title: e.title, sub: e.sub, tag: e.tag, dot: st.dot, radius: st.radius, tagBg: st.tagBg, tagFg: st.tagFg, fw: on ? 700 : 500, titleFg: on ? '#A33B2E' : '#1F3A56',
        impOn: on ? 'true' : 'false', impLabel: on ? '! 중요' : '중요 표시', impBg: on ? '#A33B2E' : '#FFFFFF', impFg: on ? '#FFFFFF' : '#66788A', impBd: on ? '#A33B2E' : '#C5D4DE',
        toggleImp: () => this.setState({ events: s.events.map((x, j) => (j === e.i ? { ...x, imp: !x.imp } : x)) }) };
      if (e.xi != null) return { ...row, toggleImp: () => { saveExtra(this.schedExtra().map((x, j) => (j === e.xi ? { ...x, imp: !x.imp } : x))); this.setState({ __ntTick: Date.now() }); } };
      if (e.rid && !e.dl) return { ...row, toggleImp: () => updRec(e.rid, (r) => ({ ...r, imp: !r.imp })) };
      if (e.dl) { const dn = !!e.done; return { ...row, fw: dn ? 500 : 700, titleFg: dn ? '#66788A' : '#A33B2E', impOn: dn ? 'true' : 'false', impLabel: dn ? '✓ 완료' : '완료 표시', impBg: dn ? '#1F3A56' : '#FFFFFF', impFg: dn ? '#FFFFFF' : '#66788A', impBd: dn ? '#1F3A56' : '#C5D4DE',
        toggleImp: () => updRec(e.rid, (r) => ({ ...r, done: { ...(r.done || {}), [e.dl]: !dn } })) }; }
      return row; })(e)));
    const monthEv = allEv.filter((e) => e.y === s.y && e.m === s.m);
    const setF = (k) => (ev) => this.setState({ form: { ...s.form, [k]: ev.target.value } });
    const isC = s.kind === 'c';
    const vItem = s.view ? findKey(s.view) : null;
    const dLabel = (e) => { const dt = new Date(e.y, e.m, e.d); return `${e.y}년 ${e.m + 1}월 ${e.d}일 ${days[dt.getDay()]}요일`; };
    const pad = (n) => String(n).padStart(2, '0');
    const placeOf = (e) => (e.rid ? (e.dl ? '' : (recs.find((r) => r.id === e.rid) || {}).place || '') : e.t === 'c' ? e.sub : (e.sub && e.sub.indexOf(e.tag + ' · ') === 0 ? e.sub.slice(e.tag.length + 3) : ''));
    let vVals = {};
    if (vItem) {
      const e = vItem; const st = style(e); const isDl = !!e.dl; const rec = e.rid ? recs.find((r) => r.id === e.rid) : null;
      const rows = [['날짜', dLabel(e)], ['시간', isDl ? '마감일' : e.time]];
      if (isDl) { rows.push(['내용', e.sub]); rows.push(['상태', e.done ? '완료' : '진행 전']); }
      else if (e.t === 'c') { rows.push(['어르신', e.title.split(' · ')[0]]); rows.push(['상담 유형', e.title.split(' · ').slice(1).join(' · ') || '—']); rows.push(['장소', placeOf(e) || '—']); }
      else { if (rec) rows.push(['어르신', rec.child]); rows.push(['분류', e.tag]); rows.push(['장소', placeOf(e) || '—']); }
      rows.push(['중요', e.imp ? '중요 일정' : '—']);
      const askNote = rec && !isDl ? '최초접수와 함께 만들어진 처리 기한 일정 3건도 같이 삭제되고, 알림에서도 빠져요.' : '삭제하면 되돌릴 수 없어요.';
      const ask = !!s.delAsk;
      vVals = { kind: isDl ? '처리 기한' : e.t === 'c' ? '상담 방문 일정' : '개인 · 기관 일정', title: e.title, dot: st.dot, radius: st.radius, titleFg: e.imp ? '#A33B2E' : 'inherit',
        rows: rows.map(([k, v]) => ({ k, v })), isDl, canEdit: !isDl, ask, noAsk: !ask, askNote,
        doneLabel: e.done ? '✓ 완료 취소' : '완료 표시', doneCls: e.done ? 'btn-s' : 'btn-p',
        toggleDone: () => updRec(e.rid, (r) => ({ ...r, done: { ...(r.done || {}), [e.dl]: !e.done } })),
        goBase: () => { if (rec) this.setState({ y: rec.y, m: rec.m, sel: rec.d, view: { src: 'rec', id: rec.id } }); },
        askDel: () => this.setState({ delAsk: true }), cancelDel: () => this.setState({ delAsk: false }),
        del: () => { if (e.xi != null) { saveExtra(this.schedExtra().filter((x, j) => j !== e.xi)); this.setState({ view: null, delAsk: false, __ntTick: Date.now() }); } else if (e.rid) { this.ntSave(this.ntRecs().filter((r) => r.id !== e.rid)); this.setState({ view: null, delAsk: false, __ntTick: Date.now() }); } else { this.setState({ events: s.events.filter((x, j) => j !== e.i), view: null, delAsk: false }); } },
        edit: () => { const isRec = !!rec; const c = e.t === 'c'; const ttl = e.title.split(' · ');
          const CT = ['방문상담', '전화상담']; const OLD = ['정기상담', '초기상담', '내방상담', '가족 상담', '종결 상담']; const rest = ttl.slice(1).join(' · '); const ct = CT.find((x) => rest.indexOf(x) === 0) || (rest.indexOf('전화') >= 0 ? '전화상담' : '방문상담'); const oldT = OLD.find((x) => rest.indexOf(x) === 0);
          const form = { ...s.form, date: `${e.y}-${pad(e.m + 1)}-${pad(e.d)}`, time: e.time === '종일' ? '' : e.time, imp: !!e.imp, place: placeOf(e),
            child: isRec ? rec.child : (c ? ttl[0] : s.form.child), ctype: c ? ct : s.form.ctype, pcat: isRec ? '최초접수' : (c ? s.form.pcat : e.tag), title: isRec || c ? '' : e.title };
          this.setState({ adding: true, kind: c ? 'c' : 'p', form, edit: { key: keyOf(e), suffix: c && rest.indexOf(ct) === 0 ? rest.slice(ct.length) : c && oldT ? rest.slice(oldT.length) : '', allDay: e.time === '종일', done: rec ? rec.done || {} : {} }, delAsk: false }); } };
    }
    return {
      monthLabel: `${s.y}년 ${s.m + 1}월`,
      cells, dayEvents, noEvents: dayEvents.length === 0,
      selLabel: `${s.m + 1}월 ${s.sel}일 ${days[selDate.getDay()]}요일`,
      countC: monthEv.filter((e) => e.t === 'c').length,
      countP: monthEv.filter((e) => e.t === 'p').length,
      countI: monthEv.filter((e) => e.imp).length,
      fAllCls: s.filter === 'all' ? 'on' : '', fCCls: s.filter === 'c' ? 'on' : '', fPCls: s.filter === 'p' ? 'on' : '', fICls: s.filter === 'i' ? 'on' : '',
      showAll: () => this.setState({ filter: 'all' }), showC: () => this.setState({ filter: 'c' }), showP: () => this.setState({ filter: 'p' }), showI: () => this.setState({ filter: 'i' }),
      prevMonth: () => { const m = s.m === 0 ? 11 : s.m - 1; const y = s.m === 0 ? s.y - 1 : s.y; this.setState({ m, y, sel: 1 }); },
      nextMonth: () => { const m = s.m === 11 ? 0 : s.m + 1; const y = s.m === 11 ? s.y + 1 : s.y; this.setState({ m, y, sel: 1 }); },
      goToday: () => { const n = new Date(); this.setState({ y: n.getFullYear(), m: n.getMonth(), sel: n.getDate() }); },
      adding: s.adding, notAdding: !s.adding && !vItem, viewing: !s.adding && !!vItem, v: vVals, vBack: () => this.setState({ view: null, delAsk: false }),
      isEdit: !!s.edit, formTitle: s.edit ? '일정 수정' : '일정 추가', formDateLabel: s.edit ? '' : `${s.m + 1}월 ${s.sel}일 ${days[selDate.getDay()]}요일`,
      setDate: setF('date'),
      openAdd: () => this.setState({ adding: true, edit: null, form: { ...s.form, title: '', place: '', imp: false } }),
      cancelAdd: () => this.setState({ adding: false, edit: null }),
      isC, isP: !isC, isIntake: !isC && s.form.pcat === '최초접수', notIntake: !(!isC && s.form.pcat === '최초접수'),
      dlPreview: this.ntTasks().map(([n, task]) => { const dd = new Date(s.y, s.m, s.sel + n); return { n: n + '일 이내', task, due: (dd.getMonth() + 1) + '/' + dd.getDate() + '(' + days[dd.getDay()] + ')' }; }),
      kindC: () => this.setState({ kind: 'c' }), kindP: () => this.setState({ kind: 'p' }),
      kcBorder: isC ? '#1F3A56' : '#C5D4DE', kcBg: isC ? '#E8F4FC' : '#FFFFFF',
      kpBorder: !isC ? '#1F3A56' : '#C5D4DE', kpBg: !isC ? '#E8F4FC' : '#FFFFFF',
      form: s.form,
      formImpOn: s.form.imp ? 'true' : 'false', formImpBd: s.form.imp ? '#A33B2E' : '#C5D4DE', formImpBg: s.form.imp ? '#F7E4DF' : '#FFFFFF', formImpFg: s.form.imp ? '#A33B2E' : '#55687A',
      formImpBox: s.form.imp ? '#A33B2E' : '#FFFFFF', formImpMark: s.form.imp ? '✓' : '', toggleFormImp: () => this.setState({ form: { ...s.form, imp: !s.form.imp } }),
      setChild: setF('child'), setCtype: setF('ctype'), setPcat: setF('pcat'), setTitle: setF('title'), setTime: setF('time'), setPlace: setF('place'),
      save: () => {
        const f = s.form;
        if (s.edit) {
          const ed = s.edit; const dp = String(f.date || '').split('-').map((x) => parseInt(x, 10)); const ok = dp.length === 3 && dp.every((x) => x > 0);
          const Y = ok ? dp[0] : s.y, M = ok ? dp[1] - 1 : s.m, D = ok ? dp[2] : s.sel; const T = f.time || (ed.allDay ? '종일' : '10:00');
          let events = s.events; let recsN = this.ntRecs();
          if (ed.key.src === 'ev') events = events.filter((x, j) => j !== ed.key.i); else if (ed.key.src === 'ex') saveExtra(this.schedExtra().filter((x, j) => j !== ed.key.k)); else recsN = recsN.filter((r) => r.id !== ed.key.id);
          if (!isC && f.pcat === '최초접수') recsN = [...recsN, { id: ed.key.src === 'rec' ? ed.key.id : 'r' + Date.now().toString(36), child: f.child, y: Y, m: M, d: D, time: T, place: f.place || '', imp: !!f.imp, done: ed.key.src === 'rec' ? ed.done : {} }];
          else { const ev = isC ? { y: Y, m: M, d: D, time: T, t: 'c', title: `${f.child} · ${f.ctype}${ed.suffix || ''}`, sub: f.place || '장소 미정', tag: '상담', imp: !!f.imp }
              : { y: Y, m: M, d: D, time: T, t: 'p', title: f.title || f.pcat, sub: f.place ? `${f.pcat} · ${f.place}` : f.pcat, tag: f.pcat, imp: !!f.imp };
            if (ed.key.src === 'ev') { events = s.events.slice(); events.splice(ed.key.i, 1, ev); } else events = [...events, ev]; }
          this.ntSave(recsN);
          this.setState({ events, adding: false, edit: null, view: null, y: Y, m: M, sel: D, form: { ...f, title: '', place: '', imp: false }, __ntTick: Date.now() }); return;
        }
        if (!isC && f.pcat === '최초접수') { this.ntSave([...this.ntRecs(), { id: 'r' + Date.now().toString(36), child: f.child, y: s.y, m: s.m, d: s.sel, time: f.time || '10:00', place: f.place || '', imp: !!f.imp, done: {} }]);
          this.setState({ adding: false, form: { ...f, title: '', place: '', imp: false }, __ntTick: Date.now() }); return; }
        const ev = isC
          ? { y: s.y, m: s.m, d: s.sel, time: f.time || '10:00', t: 'c', title: `${f.child} · ${f.ctype}`, sub: f.place || '장소 미정', tag: '상담', imp: f.imp }
          : { y: s.y, m: s.m, d: s.sel, time: f.time || '10:00', t: 'p', title: f.title || f.pcat, sub: f.place ? `${f.pcat} · ${f.place}` : f.pcat, tag: f.pcat, imp: f.imp };
        this.setState({ events: [...s.events, ev], adding: false, form: { ...f, title: '', place: '', imp: false } });
      }
    };
  }
}
