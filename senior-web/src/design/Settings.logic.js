// Settings 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Settings.jsx)이 이어받아 데이터만 바꾼다.
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), leaveReset: () => this.setState({ view: 'home', edit: null, draft: '', pw: false, mailSent: false }), markBack: () => { const v = '#/Settings'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { view: 'home', name: '이서연', mail: 'lee.seoyeon@ondam-center.kr', phone: '010-1234-5678', phoneErr: false, edit: null, draft: '', mailSent: false, pw: false, t: { urgent: true, noreply: true, brief: true, done: false }, batch: '09:00' }; }
renderValsBase() {
  const s = this.state;
  const sw = (on) => ({ bg: on ? '#1F3A56' : '#C5D4DE', x: on ? '23px' : '3px', on: on ? 'true' : 'false' });
  const defs = [['urgent', '위기 신호 즉시 알림 (자살 생각 표현 · 급격한 기분 저하 · 낙상 언급)'], ['noreply', '안부 무응답 알림 (48시간 무응답 시)'], ['brief', '상담 30분 전 브리핑 알림'], ['done', 'STT 분석 완료 알림']];
  const toggles = defs.map(([k, label]) => ({ label, ...sw(s.t[k]), flip: () => this.setState({ t: { ...s.t, [k]: !s.t[k] } }) }));
  const titles = { home: '설정', account: '계정', notify: '알림 설정' };
  return { title: titles[s.view], subTitle: titles[s.view], atHome: s.view === 'home', inSub: s.view !== 'home', isAccount: s.view === 'account', isNotify: s.view === 'notify',
    goHome: () => this.setState({ view: 'home', edit: null }), goAccount: () => this.setState({ pwOpen: true, pwIn: '' }), pwOpen: !!s.pwOpen, pwIn: s.pwIn || '', setPwIn: (e) => this.setState({ pwIn: e.target.value }), pwOk: !!(s.pwIn || '').length, pwWait: !(s.pwIn || '').length, closePw: () => this.setState({ pwOpen: false, pwIn: '' }), submitPw: () => { if ((this.state.pwIn || '').length) this.setState({ pwOpen: false, pwIn: '', view: 'account' }); }, goNotify: () => this.setState({ view: 'notify' }),
    name: s.name, mail: s.mail, draft: s.draft, mailSent: s.mailSent,
    phone: s.phone, phoneView: s.edit !== 'phone', phoneEdit: s.edit === 'phone', phoneErr: !!s.phoneErr,
    editPhone: () => this.setState({ edit: 'phone', draft: s.phone, phoneErr: false }),
    setPhoneDraft: (e) => { const d = String(e.target.value || '').replace(/\D/g, '').slice(0, 11); const v = d.length < 4 ? d : d.length < 8 ? d.slice(0, 3) + '-' + d.slice(3) : d.slice(0, 3) + '-' + d.slice(3, d.length - 4) + '-' + d.slice(-4); this.setState({ draft: v, phoneErr: false }); },
    savePhone: () => { const d = String(this.state.draft || '').replace(/\D/g, ''); if (!/^01[016789]\d{7,8}$/.test(d)) { this.setState({ phoneErr: true }); return; } this.setState({ edit: null, phone: this.state.draft, phoneErr: false }); },
    nameView: s.edit !== 'name', nameEdit: s.edit === 'name', mailView: s.edit !== 'mail', mailEdit: s.edit === 'mail',
    editName: () => this.setState({ edit: 'name', draft: s.name }), editMail: () => this.setState({ edit: 'mail', draft: s.mail, mailSent: false }),
    setDraft: (e) => this.setState({ draft: e.target.value }), cancel: () => this.setState({ edit: null }),
    saveName: () => this.setState({ edit: null, name: s.draft || s.name }), saveMail: () => this.setState({ edit: null, mailSent: true }),
    pwText: s.pw ? '재설정 링크 발송됨 · 30분 유효' : '마지막 변경 2026-08-12', pwLabel: s.pw ? '다시 보내기' : '비밀번호 재설정', pwCls: s.pw ? 'btn-s' : 'btn-p', resetPw: () => this.setState({ pw: true }),
    toggles, urgentOff: !s.t.urgent, batch: s.batch, setBatch: (e) => this.setState({ batch: e.target.value }) };
}
}
