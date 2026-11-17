// CaseForm 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/CaseForm.jsx)이 이어받아 데이터만 바꾼다.
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
  this.formSync();
  this._thmT = setInterval(() => { this.formSync(); if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
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
  return Object.assign({}, v, this.ntVals(), { copyMenu: (e) => { const l = e && e.currentTarget && e.currentTarget.closest ? e.currentTarget.closest('label') : null; if (!l) return; const was = l.classList.contains('cp-open'); try { document.querySelectorAll('label.cp-open').forEach((x) => x.classList.remove('cp-open')); } catch (er) {} if (!was) l.classList.add('cp-open'); }, copyRaw: (e) => this.cpDo(e, false), copyMask: (e) => this.cpDo(e, true), jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/CaseForm'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

formRead() { let v = null; try { v = window.localStorage.getItem('ispot-form'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-form'); } catch (e) {} } if (!v) { try { v = window.top.__ispotForm; } catch (e) {} } if (!v) v = window.__ispotForm; return v || ''; }
formSync() { const v = this.formRead(); if (v && v !== this._formTok) { this._formTok = v; const k = String(v).split('|')[0]; if (['A', 'B', 'C', 'D', 'E', 'F'].includes(k) && k !== this.state.tab) this.setState({ tab: k }); } }
constructor(props) { super(props); this.state = { tab: 'A', sa: {}, key: '있음', res: '', ck: {}, sc: {}, who: '어르신', fam: {}, gd: { 1: '아니오', 2: '예', 3: '예', 4: '예', 5: '아니오', 6: '아니오', 7: '아니오', 8: '아니오', 9: '예', 10: '예', 11: '예', 12: '아니오', 13: '아니오', 14: '아니오', 15: '아니오' }, sr: { 1: '아니오', 2: '아니오', 3: '아니오', 4: '아니오', 5: '예', 7: '예', 8: '예', 9: '예' } }; }
renderValsBase() {
  const s = this.state;
  const sel = (on) => ({ bg: on ? '#E8F4FC' : 'transparent', fg: on ? '#1F3A56' : '#55687A', fw: on ? 700 : 400, bd: on ? 'inset 0 0 0 1px #1F3A56' : 'none' });
  const tabs = [['A', 'S-02 욕구 · 자원 사정'], ['B', '사례관리 점검표'], ['C', '위기도 평가표'], ['D', '가족 지지 · 관계 척도'], ['E', 'S-03 SGDS-K'], ['F', 'S-04 자살위험 선별']].map(([k, label]) => ({ label, ...sel(s.tab === k), cls: s.tab === k ? 'on' : '', on: s.tab === k ? 'true' : 'false', pick: () => this.setState({ tab: k }) }));
  // S-02 욕구 · 자원 사정 (영역별 욕구)
  const SA = [
    ['정서 · 건강 · 인지', [
      ['정서: 우울감 · 상실감에 대한 정서 지원 욕구', '높음', '3회차(9/18) "그 양반 가고 나서는 밥맛이 없어요" · SGDS-K 9점'],
      ['건강: 만성질환 관리 · 통증 · 수면', '보통', '초기상담지 · 고혈압, 수면유도제 복용 · 불면 호소'],
      ['인지: 기억력 변화에 대한 확인 욕구', '낮음', '본인 "요즘 깜빡깜빡해요" 1회 언급 · 대화에 어려움 없음 (상담사는 진단하지 않음)']]],
    ['사회관계 · 가족', [
      ['사회관계: 교류 · 외출 · 모임 참여 욕구', '높음', '노인복지관 프로그램 이용 중단 후 외출 주 1회 미만'],
      ['가족: 가족과의 정서적 연결', '보통', '아들과 주 1회 통화 · "바쁜 애한테 짐 되기 싫어요"'],
      ['가족 갈등 · 서운함', '', ''],
      ['주 돌봄자(가족)의 부양 부담 · 지원 필요', '낮음', '아들 타 지역 거주 · 상담 일정 안내 공유 동의'],
      ['상담 · 서비스 이용에 대한 어르신의 태도', '보통', '상담 일정 2회 미루신 뒤 3회차부터 참여 (9/18, 10/2)']]],
    ['경제 · 주거 · 여가', [
      ['경제: 생활비 · 의료비 부담', '', ''],
      ['주거: 낙상 위험 · 난방 · 위생', '', ''],
      ['여가 · 생활 적응: 하루 일과 · 의미 있는 활동', '보통', '3회차 04:10 "하루 종일 텔레비전만 봐요"']]]
  ];
  let idx = 0;
  const safety = SA.map(([name, items]) => ({ name, items: items.map(([q, ai, ev]) => { const k = idx++; const cur = s.sa[k] !== undefined ? s.sa[k] : ai;
    return { q, ai, ev, hasEv: !!ai, opts: ['높음', '보통', '낮음'].map((o) => ({ label: o, ...sel(cur === o), pick: () => this.setState({ sa: { ...s.sa, [k]: cur === o ? '' : o } }) })) }; }) }));
  const keyOpts = ['있음', '없음'].map((o) => ({ label: o, ...sel(s.key === o), pick: () => this.setState({ key: o }) }));
  const scoreRows = ['어르신 응답', '가족(주 돌봄자) 응답', '상담사 관찰'].map((who) => ({ who }));
  const resultOpts = ['위기', '집중', '관심', '일반'].map((o) => ({ label: o, ...sel(s.res === o), pick: () => this.setState({ res: s.res === o ? '' : o }) }));
  // 사례관리 점검표 (시니어)
  const CK = [
    ['사례관리 계획에 따라 서비스가 적절하게 제공되고 있는가?', '아니오', '노인복지관 프로그램 연계 후 2회 불참 (9/18, 10/2)'],
    ['어르신의 비공식 지지망(가족 · 이웃)과 공식 돌봄 서비스의 노력이 적절한가?', '예', '아들 주 1회 통화 · 맞춤돌봄 생활지원사 주 1회 방문'],
    ['어르신의 정서 · 위기 신호가 줄고 일상이 안정되고 있는가? (소견에 구체적 근거 작성)', '아니오', '4회차(10/2) 식사 거름 반복 · 안부 앱 기분 응답 "그저 그래요" 2주'],
    ['제공되는 서비스에 대해 어르신과 가족이 만족하고 있는가?', '', ''],
    ['다른 서비스 욕구가 발생하였는가?', '예', '무릎 통증 진료 여부 미확인 (4회차 01:08) → 방문건강관리 연계 검토'],
    ['사례관리 지속이 필요한가?', '예', '위 3번 근거'],
    ['재사정이 필요한가?', '예', '식사 · 수면 변화로 욕구 변화'],
    ['사례관리 계획은 수정되어야 하는가?', '예', '방문형 프로그램 · 의료 연계 반영 필요'],
    ['어르신 본인이 상담 · 사례관리 지속을 원하시는가? (자기결정 확인)', '예', '4회차 "다음에도 와 주면 좋지요"'],
    ['사례는 종결되어야 하는가?', '아니오', '위 3번 근거']
  ];
  const checks = CK.map(([q, ai, ev], i) => { const cur = s.ck[i] !== undefined ? s.ck[i] : ai;
    return { q: `${i + 1}. ${q}`, ai, ev, hasEv: !!ai, opts: ['예', '아니오'].map((o) => ({ label: o, ...sel(cur === o), pick: () => this.setState({ ck: { ...s.ck, [i]: cur === o ? '' : o } }) })) }; });
  // 위기도 평가표 · 43문항 (위험요인 1~21 · 보호요인 22~43)
  const Q = ['어르신이 우울감 · 기분 저하를 호소한다.', '죽음이나 자살에 대한 생각을 표현한 적이 있다.', '과거 자해 · 자살 시도 경험이 있다.', '최근 1년 안에 배우자 · 가족 사별 등 중요한 상실이 있었다.', '혼자 살며 하루 대부분을 혼자 보낸다.', '가족 · 이웃과의 교류가 거의 없다.', '식사를 자주 거르거나 체중이 줄었다.', '잠들기 어렵거나 자주 깨는 등 수면에 어려움이 있다.', '만성질환 · 통증으로 일상생활이 힘들다.', '최근 낙상 · 입원 경험이 있다.', '복용 약을 제대로 챙기지 못한다.', '기억력 · 판단력의 변화가 관찰된다.', '음주 문제가 있다.', '경제적 어려움으로 생활비 · 의료비 부담이 크다.', '주거환경이 안전하지 않거나 불안정하다 (난방 · 위생 · 낙상 위험).', '가족 갈등이나 서운함으로 정서적 고통이 크다.', '주 돌봄자의 부양 부담이 크다.', '도움 요청이나 서비스 이용을 꺼린다.', '안부 연락에 오래 응답하지 않은 적이 있다.', '위급할 때 연락할 사람이 없다.', '학대 정황이 의심된다 (노인보호전문기관 연계 검토).',
    '어르신은 자신의 어려움을 말로 표현할 수 있다.', '어르신은 상담 · 서비스 이용에 수용적이다.', '정기적으로 연락하는 가족이 있다.', '가까이에 의지할 수 있는 이웃 · 지인이 있다.', '경로당 · 노인복지관 등 모임에 참여한다.', '규칙적인 식사와 생활 리듬을 유지한다.', '진료 · 복약 등 건강 관리를 스스로 할 수 있다.', '혼자 외출하고 이동할 수 있다.', '식사 준비 · 청소 등 일상생활을 스스로 할 수 있다.', '즐거움을 주는 취미 · 여가 활동이 있다.', '종교 · 신념 등 마음의 버팀목이 있다.', '삶의 의미나 살아갈 이유를 말할 수 있다.', '과거 어려움을 이겨낸 경험이 있다.', '가족이 어르신의 결정을 존중한다.', '주 돌봄자가 상담에 협조적이다.', '노인맞춤돌봄 · 장기요양 등 공식 돌봄 서비스를 이용 중이다.', '생활지원사 · 방문간호 등 정기적으로 찾아오는 사람이 있다.', '기초연금 등 안정적인 소득이 있다.', '주거가 안정적이다.', '위기 때 연락할 곳(109 · 119 등)을 알고 있다.', '안부 앱 · 전화 등 연락 수단을 사용할 수 있다.', '어르신 스스로 변화하려는 마음이 있다.'];
  const AIV = { 1: [2, '3회차(9/18) "요즘은 그냥 기운이 없어요" · SGDS-K 9점'], 2: [0, '4회차(10/2) S-04 선별 · "그런 생각은 안 해요" (상담사 확인)'], 4: [3, '초기상담지 · 배우자 사별 1년'], 5: [2, '독거 · 낮 시간 대부분 혼자 지내심'], 7: [2, '3회차 02:15 "혼자 먹으려니 밥을 잘 안 하게 돼요"'], 8: [2, '수면유도제 복용 · 불면 호소'], 18: [1, '상담 일정 2회 미루신 뒤 참여'], 20: [1, '아들 타 지역 거주 · 이웃 1명'], 24: [2, '아들 주 1회 통화'], 25: [1, '옆집 이웃이 가끔 들여다봄'], 37: [2, '노인맞춤돌봄 생활지원사 주 1회 방문'], 43: [1, '3회차 "복지관에 다시 나가 볼까" 언급'] };
  const LBL = ['매우 아니다', '아니다', '그렇다', '매우 그렇다'];
  let rs = 0, ps = 0, filled = 0;
  const scale = Q.map((q, i) => { const n = i + 1; const ai = AIV[n]; const v = s.sc[n] !== undefined ? s.sc[n] : (ai ? ai[0] : null);
    if (v !== null && v !== '') { filled++; if (n <= 21) rs += v; else ps += v; }
    return { n, q, head: n === 1 || n === 22, hid: n === 1 ? 'scale-risk' : 'scale-prot', headLabel: n === 1 ? '위험요인 (1~21)' : '보호요인 (22~43)', ev: ai ? `AI 제안 ${LBL[ai[0]]} · ${ai[1]}` : '',
      opts: [0, 1, 2, 3].map((o) => ({ label: LBL[o], ...sel(v === o), pick: () => this.setState({ sc: { ...s.sc, [n]: v === o ? '' : o } }) })) }; });
  // 가족 지지 · 관계 척도 · 15문항
  const F = ['우리 가족은 서로 대화가 잘 된다', '우리 가족은 어려운 일을 함께 해결하려고 노력한다', '우리 가족은 서로의 형편을 잘 알고 있다', '가족은 내 건강과 생활에 관심을 가진다', '도움이 필요할 때 가족에게 언제든지 도움을 청할 수 있다', '가족과 함께 보내는 시간이 즐겁다', '가족과 정서적으로 가깝게 느낀다', '가족은 내 결정을 존중한다', '가족은 나를 지지하고 격려해 준다', '가족에게 내 생각과 느낌을 편하게 말할 수 있다', '집안일을 정할 때 내 의견도 반영된다', '가족은 나를 있는 그대로 인정한다', '가족과의 연락이 정기적으로 이어진다', '우리 가족은 서로 다른 의견을 존중한다', '가족에게 짐이 된다는 느낌 없이 지낼 수 있다'];
  let fs = 0, fn = 0;
  const fam = F.map((q, i) => { const v = s.fam[i]; if (v) { fs += v; fn++; }
    return { n: i + 1, q, opts: [1, 2, 3, 4, 5].map((o) => ({ label: String(o), ...sel(v === o), pick: () => this.setState({ fam: { ...s.fam, [i]: v === o ? 0 : o } }) })) }; });
  const resp = ['어르신', '주 돌봄자', '기타 가족'].map((o) => ({ label: o, ...sel(s.who === o), pick: () => this.setState({ who: o }) }));
  // S-03 SGDS-K · 15문항 요약 (r: 1점이 되는 응답)
  const GD = [['삶에 대체로 만족', '아니오'], ['활동 · 흥미 감소', '예'], ['공허감', '예'], ['지루함', '예'], ['대체로 기분 좋음', '아니오'], ['나쁜 일이 생길까 걱정', '예'], ['대체로 행복', '아니오'], ['무력감', '예'], ['외출보다 집에 머묾', '예'], ['기억력 문제 느낌', '예'], ['살아 있어 기쁨', '아니오'], ['가치 없다고 느낌', '예'], ['기력 충분', '아니오'], ['희망 없다고 느낌', '예'], ['남들이 나보다 낫다고 느낌', '예']];
  const gdS = s.gd || {}; let gdSum = 0, gdN = 0;
  const gds = GD.map(([q, r], i) => { const n = i + 1; const v = gdS[n] || ''; if (v) { gdN++; if (v === r) gdSum++; }
    return { n, q, rule: `'${r}' 응답 시 1점`, opts: ['예', '아니오'].map((o) => ({ label: o, ...sel(v === o), pick: () => this.setState({ gd: { ...(this.state.gd || {}), [n]: v === o ? '' : o } }) })) }; });
  // S-04 자살위험 선별
  const SR = ['최근 죽음이나 자살에 대해 생각한 적이 있다', '자살에 대한 구체적인 계획이 있다', '자살 수단(약 · 농약 · 끈 등)에 쉽게 접근할 수 있다', '과거 자살 시도 경험이 있다', '최근 중요한 상실(사별 · 건강 악화 · 이사 · 경제적 손실)이 있었다', '신변 정리 · 작별 인사 등 주변을 정리하는 행동이 보인다', '의지할 가족 · 이웃이 있다', '살아갈 이유(가족 · 신앙 · 반려동물 등)를 말씀하신다', '도움을 받을 의향이 있다'];
  const srS = s.sr || {}; let srN = 0;
  const srItem = (q, i) => { const n = i + 1; const v = srS[n] || ''; if (v) srN++;
    return { q: `${n}. ${q}`, opts: ['예', '아니오'].map((o) => ({ label: o, ...sel(v === o), pick: () => this.setState({ sr: { ...(this.state.sr || {}), [n]: v === o ? '' : o } }) })) }; };
  const srAll = SR.map(srItem); const yes = (n) => srS[n] === '예';
  const srLevel = (yes(1) && (yes(2) || yes(3))) || yes(6) ? '위기 · 즉시 개입' : (yes(1) || yes(4)) ? '집중 확인 필요' : '현재 위기 신호 확인되지 않음';
  const srGuide = srLevel === '위기 · 즉시 개입' ? '지금 바로 109 안내 · 정신건강복지센터 연계 · 필요 시 119 요청을 진행하고, 가족 연락은 안전을 위해 필요한 범위에서 합니다.' : srLevel === '집중 확인 필요' ? '1주 안에 다시 확인하고 정신건강복지센터 연계를 검토합니다. 109 번호를 안내해 드립니다.' : '정기 상담 · 안부 연계로 계속 살핍니다. 상실 · 고립 신호가 있으면 다시 선별합니다.';
  const saveDone = () => { const v = JSON.stringify({ tab: s.tab, sa: s.sa, key: s.key, res: s.res, ck: s.ck, sc: s.sc, fam: s.fam, who: s.who, gd: s.gd, sr: s.sr, t: Date.now() }); try { window.localStorage.setItem('ispot-cf-save', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-cf-save', v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt['ispot-cf-save'] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt['ispot-cf-save'] = v; };
  return { saveDone, tabs, tA: s.tab === 'A', tB: s.tab === 'B', tC: s.tab === 'C', tD: s.tab === 'D', tE: s.tab === 'E', tF: s.tab === 'F', goC: () => this.setState({ tab: 'C' }),
    safety, keyOpts, scoreRows, resultOpts, checks, scale, riskSum: rs, protSum: ps, filled, fam, resp,
    famAvg: fn ? (fs / 15).toFixed(2) : '—', famN: fn,
    gds, gdSum, gdN, srRisk: srAll.slice(0, 6), srProt: srAll.slice(6), srN, srLevel, srGuide };
}
}
