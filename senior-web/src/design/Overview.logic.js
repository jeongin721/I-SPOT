// Overview 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Overview.jsx)이 이어받아 데이터만 바꾼다.
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Overview'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

renderValsBase() {
  const TODAY = '2026-11-17'; const WK0 = '2026-11-16', WK1 = '2026-11-22'; const ORG = '온담 시니어상담센터';
  const DOW = ['일', '월', '화', '수', '목', '금', '토'];
  const md = (d) => { const x = new Date(d + 'T00:00:00'); return (x.getMonth() + 1) + '/' + x.getDate() + '(' + DOW[x.getDay()] + ')'; };
  const md0 = (d) => { const x = new Date(d + 'T00:00:00'); return (x.getMonth() + 1) + '/' + x.getDate(); };
  const STAFF = [{ id: 's1', name: '이서연', role: '상담사' }, { id: 's2', name: '한승호', role: '상담사' }, { id: 's3', name: '박지훈', role: '상담사' }];
  const ELDERS = [
    { name: '김순자', age: 82, st: '재방문 필요', who: 's1', acts: [{ t: '다리 통증 진료 연계 (보건소 방문건강관리 신청)', due: '2026-11-19', done: false }, { t: '식사 지원 서비스 안내', due: '2026-11-17', done: true }, { t: '경로당 동행 가능 여부 확인', due: '2026-11-21', done: false }] },
    { name: '서복례', age: 85, st: '후속조치 진행', who: 's1', acts: [{ t: '보건소 수면 상담 연계 확인', due: '2026-11-20', done: false }] },
    { name: '이정희', age: 69, st: '상담 완료', who: 's2', acts: [] },
    { name: '오금자', age: 77, st: '후속조치 진행', who: 's2', acts: [{ t: '아들에게 복약 상황 연락', due: '2026-11-21', done: false }] },
    { name: '한옥분', age: 79, st: '서비스 종료', who: 's3', acts: [] }
  ];
  const SCHED = [['2026-11-17', '김순자', '방문'], ['2026-11-17', '서복례', '전화'], ['2026-11-17', '이정희', '방문'], ['2026-11-18', '오금자', '전화'], ['2026-11-19', '김순자', '재방문'], ['2026-11-20', '서복례', '방문'], ['2026-11-24', '김순자', '재방문']]
    .map(([d, name, type]) => ({ d, name, type }));
  const INTAKE = ['최만석', '강덕수'];
  const staffName = {}; STAFF.forEach((p) => { staffName[p.id] = p.name + ' ' + p.role; });
  const week = SCHED.filter((e) => e.d >= WK0 && e.d <= WK1);
  const active = ELDERS.filter((e) => e.st !== '서비스 종료');
  const open = ELDERS.flatMap((e) => e.acts.filter((a) => !a.done).map((a) => ({ ...a, elder: e.name, who: e.who }))).sort((a, b) => (a.due < b.due ? -1 : a.due > b.due ? 1 : 0));
  const overdue = open.filter((a) => a.due < TODAY).length;
  const weekLeft = week.filter((e) => e.d >= TODAY).length;
  const kpis = [
    { label: '관리 대상자', v: active.length + '명', note: '서비스 종료 ' + (ELDERS.length - active.length) + '명 제외' },
    { label: '이번 주 방문 · 상담', v: week.length + '건', note: md0(WK0) + ' ~ ' + md0(WK1) + ' · 오늘 이후 ' + weekLeft + '건' },
    { label: '미처리 조치', v: open.length + '건', note: overdue ? '기한 지남 ' + overdue + '건' : (open.length ? '가장 빠른 기한 ' + md(open[0].due) : '모두 처리됨') },
    { label: '신규 연계 대기', v: INTAKE.length + '명', note: INTAKE.join(' · ') }
  ];
  const staffRows = STAFF.map((p) => { const mine = ELDERS.filter((e) => e.who === p.id); const names = mine.map((e) => e.name);
    const re = mine.filter((e) => e.st === '재방문 필요').length; const act = open.filter((a) => a.who === p.id).length;
    return { name: p.name, role: p.role, elders: mine.length, sched: week.filter((e) => names.indexOf(e.name) >= 0).length, re, act, hasRe: re > 0, noRe: re === 0, hasAct: act > 0, noAct: act === 0 }; });
  const ST = [['재방문 필요', '#A33B2E'], ['후속조치 진행', '#5FA4D6'], ['상담 완료', '#235E8C'], ['서비스 종료', '#B5C8D5']];
  const tot = ELDERS.length;
  const pct = (x) => (tot ? Math.round(x / tot * 100) : 0) + '%';
  const dist = ST.map(([name, c]) => { const v = ELDERS.filter((e) => e.st === name).length; return { name, c, v, p: pct(v), w: pct(v), tip: name + ' ' + v + '명' }; });
  const pending = open.map((a) => ({ due: md(a.due), elder: a.elder, t: a.t, who: staffName[a.who] || '' }));
  return { orgLine: ORG + ' · ' + md0(WK0) + ' 주', weekLabel: '이번 주 ' + md0(WK0) + ' ~ ' + md0(WK1) + ' 기준', kpis, staffRows, dist, totalElders: tot, pending, noPending: pending.length === 0 };
}
}
