// CaseIntake 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/CaseIntake.jsx)이 이어받아 데이터만 바꾼다.
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
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '가족 · 주변 자원 면담'], [30, '사례관리 계획서 작성']]; }
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
nmMask(t) { let r = String(t || ''); const F = ['박영수', '김순자', '오금자', '서복례', '이정희', '최만석', '윤기철', '정말순', '강덕수', '한옥분']; F.forEach((n) => { r = r.split(n).join(n[0] + '○' + n.slice(2)); }); F.forEach((n) => { const g = n.slice(1); r = r.split(g).join(g[0] + '○'); }); return r; }
cpDo(e, mask) { const l = e && e.currentTarget && e.currentTarget.closest ? e.currentTarget.closest('label') : null; if (!l) return; l.classList.remove('cp-open'); const b = l.querySelector('.cp-btn'); const ta = l.querySelector('textarea'); if (!ta || !b) return; const t = mask ? this.nmMask(ta.value || '') : (ta.value || '');
  const ok = () => { b.classList.add('done'); b.setAttribute('aria-label', mask ? '이름 가려서 복사됨' : '복사됨'); b.title = mask ? '이름 가려서 복사됨' : '복사됨'; clearTimeout(b._cpT); b._cpT = setTimeout(() => { b.classList.remove('done'); b.setAttribute('aria-label', '내용 복사'); b.title = '복사'; }, 1500); };
  const fb = () => { try { const x = document.createElement('textarea'); x.value = t; x.setAttribute('readonly', ''); x.style.position = 'fixed'; x.style.left = '-9999px'; document.body.appendChild(x); x.select(); document.execCommand('copy'); document.body.removeChild(x); ok(); } catch (err) {} };
  try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t).then(ok, fb); else fb(); } catch (err) { fb(); } }
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { copyMenu: (e) => { const l = e && e.currentTarget && e.currentTarget.closest ? e.currentTarget.closest('label') : null; if (!l) return; const was = l.classList.contains('cp-open'); try { document.querySelectorAll('label.cp-open').forEach((x) => x.classList.remove('cp-open')); } catch (er) {} if (!was) l.classList.add('cp-open'); }, copyRaw: (e) => this.cpDo(e, false), copyMask: (e) => this.cpDo(e, true), jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/CaseIntake'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { tab: 'A', ty: {}, hm: { '우울감·기분 저하': true, '사별·상실': true, '외출 감소': true, '식사 거름': true, '수면 문제': true }, hmEdit: false, hmDraft: '', hmOther: '', trEdit: false, trDraft: '', trOther: '', tr: { '식사 준비': true, '장보기': true }, fam: '독거', hs: { dis: '유', dsb: '무', hosp: '유', hospT: { '통원': true }, psy: '무', med: '', cns: '무' }, rows: 2, tried: false, f: { report: '2026-07-28', link: '2026-07-28', no: 'C-2026-0351', name: '김순자', sex: '여', birth: '1944-03-14', target: '이정훈', rel: '아들', m1: '노인맞춤돌봄 수행기관(생활지원사)', m2: '상실·애도', how: '배우자와 1년 전 사별하신 뒤 식사를 자주 거르시고 외출이 줄었음. 밤에 잠을 잘 못 주무시고 기분이 가라앉는다고 말씀하심. 맞춤돌봄 생활지원사가 안부 확인 중 상담 의뢰.', first: '2026-07-29', tbirth: '1972-05-22', consent: '본인 동의', share: '일부 동의' } }; }
dpBuild(k, val, set, minS, maxS, defY) {
  const st = this.state.dp || {}; const open = st.k === k;
  const p = (x) => String(x).padStart(2, '0');
  const parse = (v) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(v || '')); return m ? { y: +m[1], m: +m[2], d: +m[3] } : null; };
  const cur = parse(val); const mn = parse(minS); const mx = parse(maxS);
  const key = (y, m, d) => y * 10000 + m * 100 + d; const mnK = mn ? key(mn.y, mn.m, mn.d) : 0; const mxK = mx ? key(mx.y, mx.m, mx.d) : 99999999;
  const go = (o) => this.setState({ dp: { ...(this.state.dp || {}), ...o } });
  const vy = open && st.y ? st.y : (cur ? cur.y : defY); const vm = open && st.m ? st.m : (cur ? cur.m : 1);
  const mode = open ? (st.mode || 'y') : 'y';
  const years = []; for (let y = mx.y; y >= mn.y; y--) years.push({ label: String(y), id: 'dpy-' + k + '-' + y, cls: y === vy ? 'on' : '', on: y === vy ? 'true' : 'false', pick: () => go({ y, mode: 'm' }) });
  const months = Array.from({ length: 12 }, (_, i) => { const m = i + 1; const dis = key(vy, m, 31) < mnK || key(vy, m, 1) > mxK; const on = cur && cur.y === vy && cur.m === m;
    return { label: m + '월', cls: on ? 'on' : '', dis, pick: () => { if (!dis) go({ m, mode: 'd' }); } }; });
  const first = new Date(vy, vm - 1, 1).getDay(); const last = new Date(vy, vm, 0).getDate();
  const days = []; for (let i = 0; i < first; i++) days.push({ blank: true, real: false });
  for (let d = 1; d <= last; d++) { const kk = key(vy, vm, d); const dis = kk < mnK || kk > mxK; const on = cur && cur.y === vy && cur.m === vm && cur.d === d;
    days.push({ blank: false, real: true, n: d, aria: vy + '년 ' + vm + '월 ' + d + '일', cls: on ? 'on' : '', dis, pick: () => { if (dis) return; set(vy + '-' + p(vm) + '-' + p(d)); this.setState({ dp: {} }); } }); }
  const prevY = vm === 1 ? vy - 1 : vy, prevM = vm === 1 ? 12 : vm - 1, nextY = vm === 12 ? vy + 1 : vy, nextM = vm === 12 ? 1 : vm + 1;
  return { open, exp: open ? 'true' : 'false', isY: mode === 'y', isM: mode === 'm', isD: mode === 'd', listId: 'dpl-' + k,
    toggle: () => { if (open) this.setState({ dp: {} }); else { this._dpScroll = 'dpy-' + k + '-' + (cur ? cur.y : defY); this.setState({ dp: { k, mode: 'y', y: cur ? cur.y : defY, m: cur ? cur.m : 1 } }); } },
    close: () => this.setState({ dp: {} }), toY: () => { this._dpScroll = 'dpy-' + k + '-' + vy; go({ mode: 'y' }); }, toM: () => go({ mode: 'm' }),
    years, months, days, dows: ['일', '월', '화', '수', '목', '금', '토'], yLabel: vy + '년', ymLabel: vy + '년 ' + vm + '월',
    prevDis: key(prevY, prevM, 31) < mnK, nextDis: key(nextY, nextM, 1) > mxK,
    prev: () => go({ y: prevY, m: prevM }), next: () => go({ y: nextY, m: nextM }) };
}
componentDidUpdate() { if (this._dpScroll) { const id = this._dpScroll; this._dpScroll = null; setTimeout(() => { try { const el = document.getElementById(id); if (el && el.parentNode) el.parentNode.scrollTop = el.offsetTop - el.parentNode.offsetTop - 80; } catch (e) {} }, 0); } }
renderValsBase() {
  const s = this.state;
  const on = (v) => ({ bg: v ? '#E8F4FC' : '#FFFFFF', bd: v ? '#1F3A56' : '#C5D4DE', fg: v ? '#1F3A56' : '#1F3A56', fw: v ? 700 : 400, mark: v ? '✓' : '+' });
  const multi = (list, key) => list.map((label) => { const v = !!s[key][label]; return { label, ...on(v), toggle: () => this.setState({ [key]: { ...s[key], [label]: !v } }) }; });
  const TY = ['정서·우울', '상실·애도', '고립·외로움', '건강·인지', '가족관계', '경제·주거', '생활 적응·여가', '삶의 정리·죽음 준비'];
  const HM = ['우울감·기분 저하', '자살 생각 표현', '사별·상실', '외로움·고립', '외출 감소', '식사 거름', '수면 문제', '기억력 저하 걱정', '건강 악화·통증', '최근 낙상', '퇴원 후 적응 어려움', '가족 갈등', '가족 부양 부담', '경제적 어려움', '주거 불안', '음주 문제', '여가·활동 감소', '삶의 정리·죽음 준비 고민', '학대 정황(노인보호전문기관 연계 검토)', '특성없음', '기타'];
  const FAM = ['독거', '독거(자녀 인근 거주)', '부부', '자녀동거', '조손', '형제 · 친척 동거', '비혈연 동거', '시설 거주', '기타'];
  const TR = ['식사하기', '옷 입기', '세수 · 목욕', '화장실 이용', '실내 이동', '계단 오르기', '식사 준비', '장보기', '청소 · 빨래', '약 챙겨 먹기', '전화 사용', '금전 관리', '교통수단 이용', '혼자 외출', '도움 필요 없음', '기타'];
  const EDITF = { '시설 거주': 1, '기타': 1 };
  const fams = FAM.map((label) => ({ label: s.fam === label && !s.famEdit && s.famOther ? label + ': ' + s.famOther : label, ...on(s.fam === label), pick: () => { if (s.fam === label) { this.setState({ fam: '', famEdit: '', famDraft: '', famOther: '' }); return; } this.setState(EDITF[label] ? { fam: label, famEdit: label, famDraft: '', famOther: '' } : { fam: label, famEdit: '', famDraft: '', famOther: '' }); } }));
  const NAMES = { report: '상담 접수일', link: '의뢰일', no: '사례번호', name: '성명', sex: '성별', birth: '생년월일', target: '주 돌봄자', rel: '관계', m1: '의뢰 경로', m2: '주 상담 영역', how: '주호소', consent: '상담 동의', share: '가족 정보 공유 범위' };
  const miss = Object.keys(NAMES).filter((k) => { const v = String(s.f[k] || '').trim(); return !v || v === '선택'; });
  const go = (k) => { if (k === 'B' && miss.length) { this.setState({ tab: 'A', tried: true }); return; } this.setState({ tab: k }); };
  const fv = {}, fs = {}, fe = {}, fi = {};
  Object.keys(NAMES).forEach((k) => { fv[k] = s.f[k]; fs[k] = (e) => this.setState({ f: { ...this.state.f, [k]: e.target.value } }); const bad = s.tried && miss.includes(k); fe[k] = bad ? '#A33B2E' : ''; fi[k] = bad ? 'true' : 'false'; });
  fv.first = s.f.first || ''; fs.first = (e) => this.setState({ f: { ...this.state.f, first: e.target.value } });
  fv.tbirth = s.f.tbirth || ''; fs.tbirth = (e) => this.setState({ f: { ...this.state.f, tbirth: e.target.value } });
  const fd = {}; ['report', 'link', 'birth', 'first', 'tbirth'].forEach((k) => { fd[k] = s.f[k] ? '' : 'empty'; });
  const dp = {}; ['report', 'link', 'birth', 'first', 'tbirth'].forEach((k) => { dp[k] = this.dpBuild(k, s.f[k], (v) => this.setState({ f: { ...this.state.f, [k]: v } }), (k === 'tbirth' || k === 'birth') ? '1925-01-01' : '2000-01-01', '2026-12-31', k === 'birth' ? 1944 : k === 'tbirth' ? 1972 : 2026); });
  const tabs = [['A', '① 기본 정보 · 동의 (필수)'], ['B', '② 초기상담 내용']].map(([k, label]) => ({ label, sel: s.tab === k ? 'true' : 'false', bd: s.tab === k ? '#5FA4D6' : 'transparent', fg: s.tab === k ? '#1F3A56' : '#55687A', fw: s.tab === k ? 700 : 400, go: () => go(k) }));
  const saveDone = () => { const v = JSON.stringify({ f: s.f, ty: s.ty, hm: s.hm, tr: s.tr, fam: s.fam, hs: s.hs, t: Date.now() }); try { window.localStorage.setItem('ispot-ci-save', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-ci-save', v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt['ispot-ci-save'] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt['ispot-ci-save'] = v; };
  return { saveDone, dp, tabs, fv, fs, fe, fi, fd, showMiss: s.tab === 'A' && s.tried && miss.length > 0, missText: miss.map((k) => NAMES[k]).join(', '), isA: s.tab === 'A', isB: s.tab === 'B', homes: multi(HM, 'hm').map((o) => o.label !== '기타' ? o : { ...o, label: !s.hmEdit && s.hm['기타'] && s.hmOther ? '기타: ' + s.hmOther : '기타', toggle: () => { if (this.state.hm['기타']) { this.setState({ hm: { ...this.state.hm, '기타': false }, hmEdit: false, hmDraft: '', hmOther: '' }); } else { this.setState({ hm: { ...this.state.hm, '기타': true }, hmEdit: true, hmDraft: '' }); } } }),
    hmEdit: s.hmEdit, hmDraft: s.hmDraft, hmDraftSet: (e) => this.setState({ hmDraft: e.target.value }),
    hmOk: () => { const t = String(this.state.hmDraft || '').trim(); if (!t) return; this.setState({ hmEdit: false, hmOther: t }); },
    hmCancel: () => this.setState({ hm: { ...this.state.hm, '기타': false }, hmEdit: false, hmDraft: '', hmOther: '' }),
    hmShowOther: !s.hmEdit && !!s.hm['기타'] && !!s.hmOther, hmOther: s.hmOther, traits: multi(TR, 'tr').map((o) => o.label !== '기타' ? o : { ...o, label: !s.trEdit && s.tr['기타'] && s.trOther ? '기타: ' + s.trOther : '기타', toggle: () => { if (this.state.tr['기타']) { this.setState({ tr: { ...this.state.tr, '기타': false }, trEdit: false, trDraft: '', trOther: '' }); } else { this.setState({ tr: { ...this.state.tr, '기타': true }, trEdit: true, trDraft: '' }); } } }),
    trEdit: s.trEdit, trDraft: s.trDraft, trDraftSet: (e) => this.setState({ trDraft: e.target.value }),
    trOk: () => { const t = String(this.state.trDraft || '').trim(); if (!t) return; this.setState({ trEdit: false, trOther: t }); },
    trCancel: () => this.setState({ tr: { ...this.state.tr, '기타': false }, trEdit: false, trDraft: '', trOther: '' }),
    hs: (() => { const H = s.hs || {}; const set = (k, v) => this.setState({ hs: { ...(this.state.hs || {}), [k]: v } });
      const one = (k, vals) => vals.map((v) => ({ label: v, ...on(H[k] === v), on: H[k] === v ? 'true' : 'false', pick: () => set(k, H[k] === v ? '' : v) }));
      const T = H.hospT || {}; const yes = (k) => H[k] === '유';
      return { dis: one('dis', ['무', '유']), dsb: one('dsb', ['무', '유']), dsbLv: one('dsbLv', ['심한', '심하지 않은']), hosp: one('hosp', ['무', '유']), psy: one('psy', ['무', '유']), med: one('med', ['무', '유']), cns: one('cns', ['무', '유']),
        hospT: ['입원', '통원'].map((v) => ({ label: v, ...on(!!T[v]), on: T[v] ? 'true' : 'false', pick: () => set('hospT', { ...T, [v]: !T[v] }) })),
        off: { dis: !yes('dis'), dsb: !yes('dsb'), hosp: !yes('hosp'), psy: !yes('psy'), med: !yes('med'), cns: !yes('cns') } }; })(),
    trShowOther: !s.trEdit && !!s.tr['기타'] && !!s.trOther, trOther: s.trOther, fams,
    famEdit: !!s.famEdit, famIsInst: s.famEdit === '시설 거주', famPh: s.famEdit === '시설 거주' ? '거주 중인 시설 이름 입력' : '기타 내용 직접 입력', famAria: s.famEdit === '시설 거주' ? '거주 시설 입력' : '가족유형 기타 직접 입력',
    famDraft: s.famDraft || '', famDraftSet: (e) => this.setState({ famDraft: e.target.value }),
    famOk: () => { const t = String(this.state.famDraft || '').trim(); if (!t) return; this.setState({ famEdit: '', famOther: t }); },
    famCancel: () => this.setState({ fam: '', famEdit: '', famDraft: '', famOther: '' }),
    famShowOther: !s.famEdit && !!EDITF[s.fam] && !!s.famOther, famOtherText: '✓ ' + (s.fam === '시설 거주' ? '시설 거주 · 시설: ' : '기타 · ') + (s.famOther || ''),
    famRows: Array.from({ length: s.rows }, (_, i) => i), addRow: () => this.setState({ rows: s.rows + 1 }),
    midLabel: s.tab === 'A' ? '초기상담 내용 →' : '← 기본 정보', goB: () => go(s.tab === 'A' ? 'B' : 'A') };
}
}
