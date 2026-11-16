// Step1Record 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Step1Record.jsx)이 이어받아 데이터만 바꾼다.
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
sttRead() { let v = null; try { v = window.localStorage.getItem('ispot-stt'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-stt'); } catch (e) {} } if (!v) { try { v = window.top.__ispotStt; } catch (e) {} } if (!v) v = window.__ispotStt; return v || ''; }
sttSync(first) { const v = this.sttRead(); if (first) { const ts = parseInt(String(v).split('|')[1] || '0', 10); if (!v || Date.now() - ts > 5000) { this._sttTok = v; return; } } if (v && v !== this._sttTok) { this._sttTok = v; const t = String(v).split('|')[0]; const quiet = String(v).split('|')[2] === 'q'; clearTimeout(this._toastT); this._scrollTo = t; if (quiet) { this.setState({ pct: 100, view: 'all', focusT: t }); return; } this.setState({ pct: 100, view: 'all', focusT: t, toast: '근거 원문 위치 ' + t + '(으)로 이동했어요' }); this._toastT = setTimeout(() => this.setState({ toast: '' }), 2400); } }
componentDidUpdate() { if (this._scrollTo) { const id = 'ln-' + this._scrollTo.replace(':', ''); this._scrollTo = null; setTimeout(() => { try { const el = document.getElementById(id); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (e) {} }, 60); } }
jobRead() { let v = null; try { v = window.localStorage.getItem('ispot-job'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-job'); } catch (e) {} } if (!v) { try { v = window.top.__ispotJob; } catch (e) {} } if (!v) v = window.__ispotJob; try { return v ? JSON.parse(v) : null; } catch (e) { return null; } }
jobPhase() { const j = this.jobRead(); if (!j || !j.t) return ''; const el = Date.now() - j.t; return el < 8000 ? 'run' : el < 11000 ? 'done' : el < 11500 ? 'out' : ''; }
jobWrite(v) { try { window.localStorage.setItem('ispot-job', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-job', v); } catch (e) {} try { window.top.__ispotJob = v; } catch (e) {} window.__ispotJob = v; }
componentDidMount() {
  this._slDoc = (e) => { if (!(this.state && this.state.__slOpen)) return; if (e.type === 'keydown' ? e.key === 'Escape' : !(e.target && e.target.closest && e.target.closest('.sl-wrap'))) this.setState({ __slOpen: false }); }; try { document.addEventListener('mousedown', this._slDoc); document.addEventListener('keydown', this._slDoc); } catch (e) {}
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this.sttSync(true);
  this._thmT = setInterval(() => { this.sttSync(false); if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  try { document.removeEventListener('mousedown', this._slDoc); document.removeEventListener('keydown', this._slDoc); } catch (e) {}
  clearInterval(this._ntT); try { document.removeEventListener('mousedown', this._ntDoc); } catch (e) {}
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
ntGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
ntSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
ntRecs() { try { const a = JSON.parse(this.ntGet('ispot-intake') || '[]'); return Array.isArray(a) ? a : []; } catch (e) { return []; } }
ntSave(a) { this.ntSet('ispot-intake', JSON.stringify(a)); }
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '가족 · 지역 자원 확인'], [30, '상담 계획 수립']]; }
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
slVals(cur, pick, btnFn) {
  const L = [[1, '7/31(금) 초기상담'], [2, '8/7(금) 정기상담'], [3, '8/14(금) 정기상담'], [4, '8/21(금) 정기상담'], [5, '8/28(금) 정기상담'], [6, '9/4(금) 정기상담'], [7, '9/18(금) 정기상담'], [8, '10/2(금) 방문상담']];
  const open = !!(this.state && this.state.__slOpen); const c = L.find((x) => x[0] === cur) || L[7];
  return { slOpen: open, slExp: open ? 'true' : 'false', slToggle: () => this.setState({ __slOpen: !open }), slBtn: btnFn(c), slNo: cur + '회차', slSub: c[1],
    slItems: L.slice().reverse().map(([n, meta]) => ({ no: n + '회차', meta, st: n === 8 ? '처리 중' : '확정', stCls: n === 8 ? 'chip c-check' : 'chip c-ok', on: n === cur ? 'true' : 'false', cls: n === cur ? 'on' : '', pick: () => { this.setState({ __slOpen: false }); pick(n); } })) };
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.slVals((this.state && this.state.__sn) || 8, (n) => this.setState({ __sn: n }), () => '회차 선택'), this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Step1Record'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { pct: 100, pl: false, pos: 0, view: 'key', ok: {}, sp: {}, dec: { 0: 'adopt', 1: 'adopt', 2: 'adopt', 3: 'hold' } }; }
componentDidMountBase() {}
plRun(on) { clearInterval(this._plT); if (on) this._plT = setInterval(() => { const p = this.state.pos + 0.25; if (p >= 200) { clearInterval(this._plT); this.setState({ pos: 200, pl: false }); } else this.setState({ pos: p }); }, 250); }
componentWillUnmountBase() { clearInterval(this.timer); clearInterval(this._plT); clearTimeout(this._toastT); }
renderValsBase() {
  const s = this.state;
  const fmtT = (x) => { const t = Math.floor(x); return String(Math.floor(t / 60)).padStart(2, '0') + ':' + String(t % 60).padStart(2, '0'); };
  const all = [
    { t: '00:12', sp: '상담사', text: '어르신, 오늘은 댁에서 뵙네요. 요즘 어떻게 지내셨어요?', c: 0.97 },
    { t: '00:20', sp: '어르신(내담자)', text: '그냥… 그럭저럭 지내요. 복지관은 요새 통 못 나갔어요.', c: 0.94 },
    { t: '00:35', sp: '상담사', text: '식사는 좀 챙겨 드시고 계세요?', c: 0.98 },
    { t: '00:41', sp: '어르신(내담자)', text: '영감 가고 나서는 혼자 먹기가 싫어서… 하루 한 끼 먹을까 말까 해요.', c: 0.62, key: true, hint: '"한 끼" / "한 기" 불분명 · 00:38부터 다시 듣기', laws: ['S-02', 'S-03'], cues: [['떨림', '', '‘영감 가고 나서는’'], ['작게 말함', '', '‘한 끼 먹을까 말까’']] },
    { t: '00:58', sp: '상담사', text: '그러셨군요. 밤에 잠은 좀 주무세요?', c: 0.96 },
    { t: '01:08', sp: '어르신(내담자)', text: '새벽 세 시면 깨서 그냥 앉아 있어요. 아들은 바빠서… 전화도 내가 먼저 해야 받아요.', c: 0.58, key: true, hint: '뒤 문장 겹침', laws: ['S-02', 'S-05'], cues: [['작게 말함', '', '‘전화도 내가 먼저 해야’']] },
    { t: '01:30', sp: '상담사', text: '그렇게 혼자 깨어 계실 때는 어떤 마음이 드세요?', c: 0.95 },
    { t: '01:36', sp: '어르신(내담자)', text: '쓸쓸하지요.', c: 0.91, key: true, short: true },
    { t: '02:15', sp: '화자?', text: '이렇게 사느니 그만 가도 괜찮겠다 싶어요.', c: 0.70, key: true, hint: '화자 불확실 · 확인 전 근거 제외 · 죽음 관련 언급이라 먼저 확인해 주세요', laws: ['S-04'], hold: '화자를 어르신(내담자)으로 확인하면 확인 서식(S-04 자살위험 선별)과 목소리 신호가 표시됩니다' },
    { t: '02:40', sp: '상담사', text: '그만큼 마음이 힘드셨다는 말씀으로 들려요. 혹시 스스로를 해치고 싶은 생각까지 드신 적이 있으세요?', c: 0.89 },
    { t: '03:05', sp: '가족(보호자)', text: '(스피커폰 통화) 어머니, 저 정훈이에요. 상담 선생님 와 계신 거예요?', c: 0.81, key: true, safe: true },
    { t: '03:12', sp: '어르신(내담자)', text: '…응, 별일 없다.', c: 0.88, short: true }
  ].map((l, i) => ({ ...l, i, low: l.c < 0.75 }));
  const pick = s.view === 'all' ? all : s.view === 'low' ? all.filter((l) => l.low) : all.filter((l) => l.key);
  const SPK = ['어르신(내담자)', '상담사', '가족(보호자)', '생활지원사', '화자?'];
  const LAW = { 'S-02': ['식사·수면', '욕구·자원 사정에 식사 · 수면 변화 기록 · 맞춤돌봄 식사 지원 연계 검토'], 'S-03': ['우울감', '단축형 노인우울척도(SGDS-K)로 선별 확인 권장 · 선별 결과이며 진단이 아님'],
    'S-05': ['고립', '교류 빈도 · 연락할 사람 유무 확인 · 노인복지관 · 경로당 프로그램 연계 검토'], 'S-04': ['자살 생각', '죽음 · 자살 생각을 차분히 직접 확인 · 위기 시 109 · 정신건강복지센터 안내'] };
  const play = (t) => () => { const [mm, ss] = t.split(':').map(Number); this.plRun(true); this.setState({ pos: mm * 60 + ss, pl: true }); };
  const cnt = {}; const numOf = {};
  all.forEach((l) => { const v = s.sp[l.i] || l.sp; if (v === '화자?') return; cnt[v] = (cnt[v] || 0) + 1; numOf[l.i] = cnt[v]; });
  const lines = pick.map((l) => { const done = !!s.ok[l.i]; const edit = s.view !== 'key' && l.low;
    const sp = s.sp[l.i] || l.sp;
    const spLabel = numOf[l.i] ? `${sp} ${numOf[l.i]}` : sp; const open = s.spOpen === l.i;
    const spOpts = SPK.map((o) => ({ label: o, sel: o === sp ? 'true' : 'false', cls: o === sp ? 'spopt on' : 'spopt',
      pick: () => { const next = { ...this.state.sp }; if (o === l.sp) delete next[l.i]; else next[l.i] = o; this.setState({ sp: next, spOpen: null }); } }));
    const elder = sp === '어르신(내담자)';
    const laws = elder && l.laws ? l.laws.map((n) => ({ no: n, sig: LAW[n][0], sum: LAW[n][1] })) : [];
    const cues = elder && l.cues ? l.cues.map((c) => ({ name: c[0], num: '', hasNum: false, at: c[2] })) : [];
    const focus = s.focusT === l.t;
    return { lid: 'ln-' + l.t.replace(':', ''), ring: focus ? 'inset 0 0 0 2px #5FA4D6' : 'none', t: l.t, play: play(l.t), laws, hasLaws: laws.length > 0, cues, hasCues: cues.length > 0, hold: l.hold || '', hasHold: !!l.hold && !elder, sp, text: l.text, aria: `${l.t} 발화 고치기`, spFw: sp === '어르신(내담자)' ? 700 : 500, spFix: !!s.sp[l.i], spLabel, spMenu: open, spDir: open && s.spUp ? 'up' : '', spExp: open ? 'true' : 'false', spOpts, toggleSp: (e) => { if (open) { this.setState({ spOpen: null }); return; } let up = false; try { const b = e && e.currentTarget; if (b && b.getBoundingClientRect) { const r = b.getBoundingClientRect(); let lo = window.innerHeight || document.documentElement.clientHeight, hi = 0; const box = b.closest ? b.closest('.ln-box') : null; if (box) { const br = box.getBoundingClientRect(); const cs = window.getComputedStyle(box); if (/(auto|scroll|hidden)/.test(cs.overflowY)) { lo = Math.min(lo, br.bottom); hi = Math.max(hi, br.top); } } const need = Math.min(150, 8 + 34 * 5) + 6; const below = lo - r.bottom, above = r.top - hi; up = below < need && above > below; } } catch (er) {} this.setState({ spOpen: l.i, spUp: up }); }, conf: `${Math.round(l.c * 100)}%`,
      edit, read: !edit, hint: done ? '확인했어요' : (l.low ? (l.hint || '') : (l.safe ? '가족 통화 시작 후 어르신 발화 감소 · 가족 공유는 동의 범위 안에서만' : '')), hintFg: !done && !l.low && l.safe ? '#A33B2E' : '#66788A',
      bg: l.low && !done && s.view !== 'key' ? '#C0DEF0' : '#FFFFFF', okLabel: done ? '확인됨 ✓' : '확인', ok: () => this.setState({ ok: { ...s.ok, [l.i]: !done } }) }; });
  const lowLeft = all.filter((l) => l.low && !s.ok[l.i]).length;
  const stages = ['화자 구분 중', '전사 중', '신뢰도 계산 중', '핵심 발화 고르는 중', '거의 끝났어요', '완료'];
  const titles = { key: '1차 임시 핵심 발화', all: '전체 STT', low: '확인 필요 구간' };
  const sigDefs = [
    { type: '식사·수면', title: '식사 거름', at: '00:41', quote: '하루 한 끼 먹을까 말까 해요', why: '배우자 사별 후 식사량이 줄었다고 직접 말씀하심 (세부 신호 3)', check: '원문 일치 ✓', ok: true },
    { type: '식사·수면', title: '수면 변화', at: '01:08', quote: '새벽 세 시면 깨서 그냥 앉아 있어요', why: '이른 새벽에 깨는 일이 반복됨 (세부 신호 4)', check: '원문 일치 ✓', ok: true },
    { type: '우울감·고립', title: '외로움 · 가족 서운함', at: '01:08 · 01:36', quote: '전화도 내가 먼저 해야 받아요 / 쓸쓸하지요', why: '아들과의 교류 감소와 쓸쓸함 표현이 이어짐 (세부 신호 9)', check: '원문 일치 ✓ · 발화별 보관', ok: true },
    { type: '자살 생각', title: '수동적 죽음 언급', at: '02:15', quote: '그만 가도 괜찮겠다 싶어요', why: '죽음 관련 언급 · S-04 자살위험 선별로 확인 필요 (세부 신호 12)', check: '화자 불확실 · 보류 · 확인 우선', ok: false }
  ];
  const sigs = sigDefs.map((g, i) => { const d = s.dec[i]; const set = (v) => () => this.setState({ dec: { ...s.dec, [i]: v } });
    const st = d === 'adopt' ? ['채택', 'chip c-ok', 'inset 4px 0 0 #1F3A56'] : d === 'hold' ? ['보류', 'chip c-check', 'none'] : ['제외', 'chip c-normal', 'none'];
    return { ...g, st: st[0], stCls: st[1], bar: st[2],
      aCls: d === 'adopt' ? 'on' : '', hCls: d === 'hold' ? 'on' : '', dCls: d === 'drop' ? 'on' : '', adopt: set('adopt'), hold: set('hold'), drop: set('drop') }; });
  const decV = Object.values(s.dec);
  return { sigs, nA: decV.filter((x) => x === 'adopt').length, nH: decV.filter((x) => x === 'hold').length, nD: decV.filter((x) => x === 'drop').length, portal: '#/Soon?name=LawGuide', toast: s.toast || '', hasToast: !!s.toast, analyzing: s.pct < 100, done: s.pct >= 100, pct: s.pct, pctW: s.pct + '%', stageLabel: stages[Math.floor(s.pct / 20)],
    skip: () => this.setState({ pct: 100 }), lines, lowLeft: lowLeft + '곳', viewTitle: titles[s.view],
    chipText: s.view === 'key' ? '임시 · 검수 전' : (lowLeft ? `확인 필요 ${lowLeft}` : '모두 확인'), chipCls: s.view === 'key' ? 'chip c-sand' : (lowLeft ? 'chip c-check' : 'chip c-ok'),
    boxCls: s.view === 'all' ? 'scroll' : '', allCls: s.view === 'all' ? 'btn-p' : 'btn-s', lowCls: s.view === 'low' ? 'btn-p' : 'btn-s',
    plMarks: all.filter((l) => l.low && !s.ok[l.i]).map((l) => { const [mm, ss] = l.t.split(':').map(Number); const sec = mm * 60 + ss;
      return { t: l.t, left: (sec / 2) + '%', go: () => { this._scrollTo = l.t; this.setState({ view: 'low', focusT: l.t, pos: sec }); } }; }),
    xaShow: s.view === 'all' && all.some((l) => l.short), xaText: `음향 분석 제외 ${all.filter((l) => l.short).length}개 구간(1초 미만)`,
    xaItems: all.filter((l) => l.short).map((l) => ({ t: l.t, text: l.text, go: () => { this._scrollTo = l.t; this.setState({ view: 'all', focusT: l.t }); } })),
    plHasMarks: lowLeft > 0, plMarkCount: lowLeft,
    plOn: s.pl, plOff: !s.pl, plPlayLabel: s.pl ? '일시정지' : '재생', plPos: Math.floor(s.pos), plMax: 200, plPct: (s.pos / 2) + '%', plCur: fmtT(s.pos), plDur: fmtT(200),
    plToggle: () => { if (this.state.pl) { this.plRun(false); this.setState({ pl: false }); } else { const p = this.state.pos >= 200 ? 0 : this.state.pos; this.plRun(true); this.setState({ pl: true, pos: p }); } },
    plStop: () => { this.plRun(false); this.setState({ pl: false, pos: 0 }); },
    plBack: () => this.setState({ pos: Math.max(0, this.state.pos - 5) }), plFwd: () => this.setState({ pos: Math.min(200, this.state.pos + 5) }),
    plSeek: (e) => this.setState({ pos: Math.max(0, Math.min(200, Number(e.target.value) || 0)) }),
    showAll: () => this.setState({ view: s.view === 'all' ? 'key' : 'all' }), showLow: () => this.setState({ view: s.view === 'low' ? 'key' : 'low' }) };
}
}
