// Step3Summary 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Step3Summary.jsx)이 이어받아 데이터만 바꾼다.
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
  this._cpDoc = (e) => { if (e.type === 'keydown' && e.key !== 'Escape') return; if (e.type === 'mousedown' && e.target && e.target.closest && e.target.closest('.cp-btn, .cp-menu')) return; try { document.querySelectorAll('label.cp-open').forEach((x) => x.classList.remove('cp-open')); } catch (er) {} }; try { document.addEventListener('mousedown', this._cpDoc); document.addEventListener('keydown', this._cpDoc); } catch (e) {}
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  try { document.removeEventListener('mousedown', this._cpDoc); document.removeEventListener('keydown', this._cpDoc); } catch (e) {}
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
nmMask(t) { let r = String(t || ''); const F = ['박영수', '김순자', '오금자', '서복례', '이정희', '최만석', '윤기철', '정말순', '강덕수', '한옥분']; F.forEach((n) => { r = r.split(n).join(n[0] + '○' + n.slice(2)); }); F.forEach((n) => { const g = n.slice(1); r = r.split(g).join(g[0] + '○'); }); return r; }
cpDo(e, mask) { const l = e && e.currentTarget && e.currentTarget.closest ? e.currentTarget.closest('label') : null; if (!l) return; l.classList.remove('cp-open'); const b = l.querySelector('.cp-btn'); const ta = l.querySelector('textarea'); if (!ta || !b) return; const t = mask ? this.nmMask(ta.value || '') : (ta.value || '');
  const ok = () => { b.classList.add('done'); b.setAttribute('aria-label', mask ? '이름 가려서 복사됨' : '복사됨'); b.title = mask ? '이름 가려서 복사됨' : '복사됨'; clearTimeout(b._cpT); b._cpT = setTimeout(() => { b.classList.remove('done'); b.setAttribute('aria-label', '내용 복사'); b.title = '복사'; }, 1500); };
  const fb = () => { try { const x = document.createElement('textarea'); x.value = t; x.setAttribute('readonly', ''); x.style.position = 'fixed'; x.style.left = '-9999px'; document.body.appendChild(x); x.select(); document.execCommand('copy'); document.body.removeChild(x); ok(); } catch (err) {} };
  try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(ok, fb); else fb(); } catch (err) { fb(); } }
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { copyMenu: (e) => { const l = e && e.currentTarget && e.currentTarget.closest ? e.currentTarget.closest('label') : null; if (!l) return; const was = l.classList.contains('cp-open'); try { document.querySelectorAll('label.cp-open').forEach((x) => x.classList.remove('cp-open')); } catch (er) {} if (!was) l.classList.add('cp-open'); }, copyRaw: (e) => this.cpDo(e, false), copyMask: (e) => this.cpDo(e, true), jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Step3Summary'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { tr: {}, hm: {}, trEdit: false, hmEdit: false, trDraft: {}, hmDraft: {} }; }
renderValsBase() {
  const s = this.state;
  const sums = [
    { k: '지난 상담 이후 변화', v: '6회차 "그냥 그렇지요"였던 식사 이야기가 8회차에 "혼자 먹으니 잘 넘어가질 않아요"로 구체화됨. 두 말씀 모두 원문대로 남김.', src: '6회차 05:02 · 8회차 00:41' },
    { k: '어르신의 강점과 자원', v: '아들 이정훈 님과 주 1회 통화를 이어가고 있음. 복지관 노래교실 이야기를 할 때 목소리가 밝아짐.', src: '7회차 02:40 · 8회차 02:40' },
    { k: '욕구와 우려 요인', v: '사별 후 식사 거름 · 불면 · 외출 감소가 이어짐("밤에 자꾸 깨요"). 죽음 관련 언급(02:15)은 의미 확인 필요.', src: '8회차 00:41 · 01:08 · 02:15' },
    { k: '어르신이 원하는 변화 · 필요한 서비스/지원', v: '어르신: "다시 복지관에 나가 보고 싶어요". 서비스: 식사 지원(밑반찬 배달) · 수면 관련 방문건강관리 연계 검토.', src: '8회차 02:40 · 01:08' }
  ];
  const T = ['우울감', '불안', '외로움 · 고립감', '상실 · 애도', '무력감', '수면 문제', '식사 거름 · 식욕 저하', '기억력 저하 걱정', '만성 통증 · 질환', '낙상 위험', '자살 생각 표현', '특성없음'];
  const TAI = { '우울감': '01:36 "말 안 했어요" · 안부 앱 "기분이 그저 그래요" 2주', '수면 문제': '01:08 "밤에 자꾸 깨요"', '식사 거름 · 식욕 저하': '00:41 "잘 넘어가질 않아요"' };
  const pickList = (key, L, AI) => { const base = (t) => (s[key][t] !== undefined ? s[key][t] : !!AI[t]); const dk = key + 'Draft'; const ek = key + 'Edit';
    const cur = (t) => (s[ek] && s[dk][t] !== undefined ? s[dk][t] : base(t));
    const all = L.map((t) => { const on = cur(t); return { label: t, pressed: on ? 'true' : 'false', mark: on ? '✓' : '+', bg: on ? '#E8F4FC' : '#FFFFFF', bd: on ? '#1F3A56' : '#C5D4DE', fg: '#1F3A56', fw: on ? 700 : 400, toggle: () => this.setState({ [dk]: { ...this.state[dk], [t]: !on } }) }; });
    const onList = L.filter(base).map((t) => ({ label: t }));
    const toggleEdit = () => { if (s[ek]) { const next = { ...s[key] }; L.forEach((t) => { if (s[dk][t] !== undefined) next[t] = s[dk][t]; }); this.setState({ [key]: next, [ek]: false, [dk]: {} }); } else this.setState({ [ek]: true, [dk]: {} }); };
    return { all, onList, toggleEdit, edit: !!s[ek] }; };
  const TR = pickList('tr', T, TAI);
  const traits = TR.all;
  const H = ['독거', '배우자 사별', '가족 연락 감소', '가족 갈등', '돌봄자 부양 부담', '경제적 어려움', '사회적 고립', '주거 환경 불편', '특성없음'];
  const HAI = { '배우자 사별': '00:41 "그 양반 가고 나서는"', '독거': 'S-01 초기상담지 가구형태' };
  const HM = pickList('hm', H, HAI);
  const homes = HM.all;
  const ui = (k, R) => ({ [k + 'Edit']: R.edit, [k + 'View']: !R.edit, [k + 'Editing']: R.edit ? 'true' : 'false', [k + 'BtnLabel']: R.edit ? '확인' : '수정', [k + 'BtnCls']: R.edit ? 'btn-p' : 'btn-s', [k + 'ToggleEdit']: R.toggleEdit, [k + 'None']: R.onList.length === 0 });
  return { sums, traits, homes, traitsOn: TR.onList, homesOn: HM.onList, ...ui('tr', TR), ...ui('hm', HM), traitEv: Object.keys(TAI).map((k) => ({ label: k, ev: TAI[k] })), homeEv: Object.keys(HAI).map((k) => ({ label: k, ev: HAI[k] })) };
}
}
