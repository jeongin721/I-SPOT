// Home 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Home.jsx)이 이어받아 데이터만 바꾼다.
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Home'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { now: new Date(), editing: false, quick: ['upload', 'schedule', 'closure', 'search'] }; }
componentDidMountBase() { this.timer = setInterval(() => this.setState({ now: new Date() }), 20000); }
componentWillUnmountBase() { clearInterval(this.timer); }
renderValsBase() {
  const s = this.state; const now = s.now;
  const pad = (n) => String(n).padStart(2, '0');
  const mins = now.getHours() * 60 + now.getMinutes();
  const days = ['일', '월', '화', '수', '목', '금', '토'];
  const dateLabel = `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일 ${days[now.getDay()]}요일`;
  const clock = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const events = [
    { m: 600, t: 'p', title: '기관 사례회의', sub: '회의실 2', href: '#/Schedule' },
    { m: 780, t: 'c', title: '서복례 님 · 정기상담 4회차', sub: '상담실 A', href: '#/Schedule' },
    { m: 870, t: 'c', title: '최만석 님 · 초기상담', sub: '방문 상담', href: '#/Schedule' },
    { m: 960, t: 'c', title: '김순자 님 · 정기상담 9회차', sub: '상담실 B · 브리핑 준비됨', href: '#/CaseInfo?sec=brief' },
    { m: 1050, t: 'p', title: '슈퍼비전', sub: '팀장 면담 · 30분', href: '#/Schedule' }
  ];
  const nowH = now.getHours();
  const hours = [];
  for (let h = 9; h <= 18; h++) {
    const evs = events.filter((e) => Math.floor(e.m / 60) === h).map((e) => {
      const c = e.t === 'c';
      return { time: `${pad(Math.floor(e.m / 60))}:${pad(e.m % 60)}`, title: e.title, sub: e.sub, href: e.href,
        dot: c ? '#66788A' : '#C5D4DE', radius: c ? '50%' : '2px', bg: '#F8FBFD' };
    });
    const isNowHour = h === nowH;
    hours.push({ label: `${pad(h)}:00`, events: evs, isNowHour, bg: isNowHour ? '#F8FBFD' : '#FFFFFF', op: h < nowH ? 0.5 : 1,
      labelFg: isNowHour ? '#1F3A56' : '#66788A', labelFw: isNowHour ? 700 : 400 });
  }
  const next = events.find((e) => e.t === 'c' && e.m > mins);
  let remain = '오늘 남은 상담 없음', nextTitle = '내일 첫 상담 10:00 · 윤기철 님 전화상담';
  if (next) {
    const d = next.m - mins; const hh = Math.floor(d / 60); const mm = d % 60;
    remain = hh > 0 ? `${hh}시간 ${mm}분 남음` : `${mm}분 남음`;
    nextTitle = `${pad(Math.floor(next.m / 60))}:${pad(next.m % 60)} ${next.title}`;
  }
  const pool = {
    upload: { label: '녹취 올리기', icon: '↑', href: '#/Upload' },
    schedule: { label: '일정 추가', icon: '+', href: '#/Schedule' },
    closure: { label: '후속관리', icon: '✓', href: '#/Followup' },
    search: { label: '대상자 찾기', icon: '⌕', href: '#/CaseList' },
    stats: { label: '통계', icon: '▦', href: '#/Stats' },
    briefing: { label: '상담 전 브리핑', icon: '☰', href: '#/CaseInfo?sec=brief' }
  };
  const quick = s.quick.map((k) => ({ ...pool[k], rmLabel: `${pool[k].label} 빼기`, remove: (ev) => { if (ev && ev.preventDefault) ev.preventDefault(); this.setState({ quick: s.quick.filter((x) => x !== k) }); } }));
  const addable = Object.keys(pool).filter((k) => !s.quick.includes(k)).map((k) => ({ label: pool[k].label, add: () => this.setState({ quick: [...s.quick, k] }) }));
  return { hours, clock, dateLabel, remain, nextTitle, quick, addable, editing: s.editing,
    editLabel: s.editing ? '완료' : '편집', toggleEdit: () => this.setState({ editing: !s.editing }) };
}
}
