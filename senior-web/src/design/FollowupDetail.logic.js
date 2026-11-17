// FollowupDetail 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/FollowupDetail.jsx)이 이어받아 데이터만 바꾼다.
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
ntTasks() { return [[3, '어르신 사후관리 전화 상담'], [7, '초기 방문 상담'], [30, '사례관리 계획서 제출']]; }
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/FollowupDetail'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) {
  super(props);
  const P = (t, due, done) => ({ t, due, done: !!done });
  const E = (d, time, type, memo) => ({ d, time, type, memo });
  this._uid = 100;
  this.state = {
    f: 'all', sel: this.fuSelRead(), toast: '', actText: '', actDue: this.fuAddDays('2026-11-17', 7), linkText: '',
    adding: false, sDate: '2026-11-24', sTime: '10:00', sType: '재방문', sMemo: '',
    people: this.fuLoad([
      { key: 'kim', name: '김순자', age: '82 · 여 · 독거', status: '재방문 필요',
        acts: [P('다리 통증 진료 연계 (보건소 방문건강관리 신청)', '2026-11-19'), P('식사 지원 서비스 안내', '2026-11-17', true), P('경로당 동행 가능 여부 확인', '2026-11-21')],
        links: [], scheds: [E('2026-11-17', '10:00', '방문', '9회차 자택 방문'), E('2026-11-19', '14:00', '재방문', '진료 연계 확인'), E('2026-11-24', '10:00', '재방문', '')] },
      { key: 'seo', name: '서복례', age: '85 · 여 · 부부', status: '후속조치 진행',
        acts: [P('보건소 수면 상담 연계 확인', '2026-11-20')],
        links: ['보건소 방문건강관리 (11/12 의뢰)'], scheds: [E('2026-11-17', '13:30', '전화', '수면 변화 확인'), E('2026-11-20', '10:30', '방문', '정기 방문')] },
      { key: 'lee', name: '이정희', age: '69 · 여 · 독거', status: '상담 완료',
        acts: [], links: [], scheds: [E('2026-11-17', '15:00', '방문', '정기 방문')] },
      { key: 'oh', name: '오금자', age: '77 · 여 · 독거', status: '후속조치 진행',
        acts: [P('아들에게 복약 상황 연락', '2026-11-21')], links: [], scheds: [E('2026-11-18', '11:00', '전화', '복약 확인')] },
      { key: 'han', name: '한옥분', age: '79 · 여 · 부부', status: '서비스 종료',
        acts: [], links: ['요양시설 입소 (11/10)'], scheds: [] }
    ])
  };
}
componentWillUnmountBase() { clearTimeout(this._toastT); }
fuAddDays(iso, n) { const p = String(iso).split('-').map(Number); const d = new Date(p[0], p[1] - 1, p[2] + n); const z = (x) => (x < 10 ? '0' : '') + x; return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate()); }
fuMD(iso) { const p = String(iso || '').split('-').map(Number); if (p.length < 3 || !p[0]) return ''; const d = new Date(p[0], p[1] - 1, p[2]); return (p[1]) + '/' + p[2] + '(' + ['일', '월', '화', '수', '목', '금', '토'][d.getDay()] + ')'; }
fuToast(msg) { clearTimeout(this._toastT); this.setState({ toast: msg }); this._toastT = setTimeout(() => this.setState({ toast: '' }), 2400); }
fuUpd(key, fn) { const people = this.state.people.map((p) => (p.key === key ? fn(Object.assign({}, p)) : p)); this.fuSave(people); this.setState({ people }); }
fuLoad(def) { try { const a = JSON.parse(this.ntGet('ispot-fu') || 'null'); if (Array.isArray(a) && a.length && a.every((p) => p && p.key && Array.isArray(p.acts) && Array.isArray(p.links) && Array.isArray(p.scheds))) return a; } catch (e) {} return def; }
fuSave(people) { try { this.ntSet('ispot-fu', JSON.stringify(people)); } catch (e) {} }
fuSelRead() { let k = ''; try { k = this.ntGet('ispot-fu-sel'); } catch (e) {} return k || 'kim'; }
fuSchedPush(name, ev) { try { let a = []; try { a = JSON.parse(this.ntGet('ispot-sched-extra') || '[]'); } catch (e) { a = []; } if (!Array.isArray(a)) a = [];
  const p = String(ev.d).split('-').map(Number); if (p.length < 3 || !p[0] || !p[1] || !p[2]) return; const ctype = ev.type === '전화' ? '전화상담' : '방문상담';
  a.push({ y: p[0], m: p[1] - 1, d: p[2], time: ev.time || '10:00', t: 'c', title: name + ' 님 · ' + ctype + (ev.memo ? ' · ' + ev.memo : ''), sub: ctype === '전화상담' ? '전화' : '어르신 댁 방문', tag: '상담', imp: false, kind: '상담 방문 일정', ctype, name, memo: ev.memo || '', src: 'followup' });
  this.ntSet('ispot-sched-extra', JSON.stringify(a)); } catch (e) {} }
fuUpcoming(p) { const TODAY = '2026-11-17'; return p.scheds.filter((e) => e.d >= TODAY).slice().sort((a, b) => (a.d + a.time < b.d + b.time ? -1 : a.d + a.time > b.d + b.time ? 1 : 0)); }
renderValsBase() {
  const s = this.state; const TODAY = '2026-11-17';
  const STS = ['재방문 필요', '후속조치 진행', '상담 완료', '서비스 종료'];
  const CLS = { '재방문 필요': 'chip c-hi', '후속조치 진행': 'chip c-mid', '상담 완료': 'chip c-ok', '서비스 종료': 'chip c-ai' };
  const people = s.people;
  const sp = people.find((p) => p.key === s.sel) || people.find((p) => p.name === s.sel) || people.find((p) => p.key === 'kim') || people[0] || null;
  const out = { todayLabel: this.fuMD(TODAY),
    toast: s.toast || '', hasToast: !!s.toast,
    actText: s.actText, actDue: s.actDue, linkText: s.linkText,
    setActText: (e) => this.setState({ actText: e.target.value }), setActDue: (e) => this.setState({ actDue: e.target.value }),
    setLinkText: (e) => this.setState({ linkText: e.target.value }),
    adding: !!s.adding, notAdding: !s.adding, sDate: s.sDate, sTime: s.sTime, sType: s.sType, sMemo: s.sMemo,
    setSDate: (e) => this.setState({ sDate: e.target.value }), setSTime: (e) => this.setState({ sTime: e.target.value }),
    setSType: (e) => this.setState({ sType: e.target.value }), setSMemo: (e) => this.setState({ sMemo: e.target.value }),
    openAdd: () => this.setState({ adding: true, sDate: this.fuAddDays(TODAY, 7), sTime: '10:00', sType: '재방문', sMemo: '' }),
    closeAdd: () => this.setState({ adding: false }),
    selName: '', selAge: '', selStatus: '', selStCls: 'chip c-normal', acts: [], noActs: true, scheds: [], noScheds: true, links: [], noLinks: true,
    setStatus: () => {}, addAct: () => {}, saveSched: () => {}, addLink: () => {} };
  if (!sp) return out;
  const key = sp.key;
  const up = this.fuUpcoming(sp);
  return Object.assign(out, {
    selName: sp.name, selStatus: sp.status, selStCls: CLS[sp.status] || 'chip c-normal',
    selAge: (() => { const a = String(sp.age || '').split(' · '); return a.length && /^\d+$/.test(a[0]) ? ['만 ' + a[0] + '세'].concat(a.slice(1)).join(' · ') : String(sp.age || ''); })(),
    setStatus: (e) => { const v = e && e.target ? e.target.value : ''; if (STS.indexOf(v) < 0 || v === sp.status) return; this.fuUpd(key, (p) => Object.assign(p, { status: v })); this.fuToast('상태를 “' + v + '”(으)로 바꿨어요'); },
    acts: sp.acts.map((a, i) => ({ text: a.t, done: a.done, sub: a.done ? '처리 완료' : '기한 ' + this.fuMD(a.due),
      txtStyle: a.done ? 'text-decoration: line-through; color: #8094A3;' : 'color: #1F3A56;',
      toggle: () => { const nd = !a.done; this.fuUpd(key, (p) => Object.assign(p, { acts: p.acts.map((x, j) => (j === i ? Object.assign({}, x, { done: nd }) : x)) })); this.fuToast(nd ? '처리 완료로 표시했어요' : '미처리로 되돌렸어요'); } })),
    noActs: sp.acts.length === 0,
    addAct: () => { const t = String(s.actText || '').trim(); if (!t) { this.fuToast('조치사항을 입력해 주세요'); return; } const due = s.actDue || this.fuAddDays(TODAY, 7);
      this.fuUpd(key, (p) => Object.assign(p, { acts: p.acts.concat([{ t, due, done: false }]) })); this.setState({ actText: '', actDue: this.fuAddDays(TODAY, 7) }); this.fuToast('조치사항을 추가했어요'); },
    scheds: up.map((e) => ({ text: this.fuMD(e.d) + ' ' + e.time + ' · ' + e.type + (e.memo ? ' · ' + e.memo : '') })),
    noScheds: up.length === 0,
    saveSched: () => { if (!s.sDate) { this.fuToast('날짜를 입력해 주세요'); return; } const ev = { d: s.sDate, time: s.sTime || '10:00', type: s.sType || '재방문', memo: String(s.sMemo || '').trim() };
      this.fuUpd(key, (p) => Object.assign(p, { scheds: p.scheds.concat([ev]) })); this.fuSchedPush(sp.name, ev); this.setState({ adding: false }); this.fuToast('일정을 등록했어요 · 일정 메뉴에도 추가됐어요'); },
    links: sp.links.map((t) => ({ text: t })), noLinks: sp.links.length === 0,
    addLink: () => { const t = String(s.linkText || '').trim(); if (!t) { this.fuToast('연계 내용을 입력해 주세요'); return; }
      this.fuUpd(key, (p) => Object.assign(p, { links: p.links.concat([t]) })); this.setState({ linkText: '' }); this.fuToast('연계 기록을 남겼어요'); }
  });
}
}
