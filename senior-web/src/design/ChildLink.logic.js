// ChildLink 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/ChildLink.jsx)이 이어받아 데이터만 바꾼다.
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
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '초기 방문 상담'], [30, '사례관리 계획서 제출']]; }
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
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/ChildLink'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { f: 'need' }; }
renderValsBase() {
  const KIDS = {
    minjun: { name: '박영수', short: '박영수 님', age: '만 76세 · 남 · 부부', id: 'C-2026-0277', risk: '위기', types: '정서·우울 · 상실·애도', reason: '긴급', rCls: 'chip c-urgent', last: '오늘 08:12', urgent: true, connected: true,
      days: '111011111101111111111', next: '10/29 정기상담',
      now: [['공통 3', '오늘 기분은 어떠세요?', '그저 그래요', '이제 그만 살고 싶어요'], ['공통 2', '식사는 잘 하셨어요?', '조금 먹었어요', '안 먹었어요'], ['공통 1', '어젯밤 잠은 잘 주무셨어요?', '자다 깼어요', '한숨도 못 잤어요']],
      quote: '', ai: '죽음·자살과 관련된 표현이 음성 답변에서 처음 나왔어요. 지난 3주 동안 같은 문항 답은 "그저 그래요"였어요. 오늘 바로 안부 전화로 안전을 확인하고, 필요하면 109 · 정신건강복지센터 연계를 검토해 주세요. AI는 확인을 제안할 뿐 판단하거나 연락하지 않아요.',
      state: '근거 확인 필요', stCls: 'chip c-check', src: '오늘 08:12 음성 안부 · 공통 1 · 2 · 3',
      related: '7회차(9/14) 상담 · 어르신 말씀 "아내 먼저 보내고 나니 사는 재미가 없어요" (상담사 확인 완료)',
      hist: [['오늘 기분', ['그저 그래요', '그저 그래요', '울적해요', '그만 살고 싶어요']], ['식사', ['잘 먹었어요', '조금 먹었어요', '조금 먹었어요', '안 먹었어요']], ['잠', ['자다 깼어요', '자다 깼어요', '밤에 자꾸 깨요', '한숨도 못 잤어요']]],
      q: ['SQ-E-04', '요즘 마음이 많이 힘드실 때 누구에게 이야기하세요?'] },
    jiho: { name: '서복례', short: '서복례 님', age: '만 85세 · 여 · 독거', id: 'C-2026-0389', risk: '집중', types: '고립·외로움 · 건강·인지', reason: '식사 거름 반복', rCls: 'chip c-check', last: '어제 21:05', connected: true,
      days: '111111011111111111111', next: '10/22 정기상담 5회차',
      now: [['SQ-M-02', '이번 주에 식사를 거르신 날은 며칠이에요?', '1~2일', '5일 이상'], ['SQ-S-03', '어제 누구와 이야기 나누셨어요?', '복지관 선생님', '아무도 없었어요'], ['공통 3', '오늘 기분은 어떠세요?', '그저 그래요', '울적해요']],
      quote: '혼자 먹으니 밥맛이 없어요', ai: '식사를 거르는 날이 3주째 늘고 있어요. 3회차 상담 말씀과 같은 방향이에요. 다음 상담에서 식사 준비와 도시락·반찬 지원 연계를 확인해 보세요.',
      state: '확인 중', stCls: 'chip c-ing', src: '어제 21:05 SQ-M-02 · SQ-S-03 응답 · 21:06 음성 말씀',
      related: '3회차(9/30) 상담일지 · 어르신 말씀 "요즘은 저녁을 그냥 건너뛰어요"',
      hist: [['식사 거름', ['0일', '1~2일', '1~2일', '5일 이상']], ['대화 상대', ['복지관 선생님', '딸', '복지관 선생님', '아무도 없었어요']], ['오늘 기분', ['좋아요', '그저 그래요', '그저 그래요', '울적해요']]],
      q: ['SQ-M-04', '요즘 끼니는 주로 어떻게 챙겨 드세요?'] },
    dohyun: { name: '오금자', short: '오금자 님', age: '만 77세 · 여 · 독거', id: 'C-2026-0412', risk: '집중', types: '건강·인지 · 생활 적응', reason: '낙상 언급', rCls: 'chip c-check', last: '어제 19:40', connected: true,
      days: '110111111111011111111', next: '10/12 정기상담 7회차',
      now: [['공통 4', '요즘 몸이 불편한 곳이 있으세요?', '무릎이 아파요', '화장실에서 넘어졌어요'], ['연락 버튼', '상담 선생님과 통화하고 싶으세요?', '—', '전화 좀 주세요']],
      quote: '어제 화장실에서 미끄러졌는데 허리가 아파요', ai: '낙상과 통증을 직접 말씀하셨어요. 오늘 안에 안부 전화로 상태를 확인하고, 필요하면 방문건강관리(보건소)나 진료 연계를 검토해 보세요. 6회차 기록 확인이 아직 남아 있어요.',
      state: '확인 중', stCls: 'chip c-ing', src: '어제 19:40 음성 안부 · 공통 4 · 연락 요청 버튼',
      related: '6회차(10/6) 녹취 00:38 · 어르신 말씀 "요즘 다리에 힘이 없어요"',
      hist: [['몸 불편', ['괜찮아요', '무릎이 아파요', '무릎이 아파요', '넘어졌어요']], ['잠', ['잘 잤어요', '잘 잤어요', '자다 깼어요', '자다 깼어요']], ['연락 요청', ['—', '—', '—', '요청']]],
      q: ['SQ-H-05', '넘어지신 뒤로 걷거나 움직이실 때 불편하세요?'] },
    yerin: { name: '이정희', short: '이정희 님', age: '만 69세 · 여 · 자녀동거', id: 'C-2026-0338', risk: '관심', types: '가족관계 · 정서·우울', reason: '확인 필요', rCls: 'chip c-check', last: '어제 20:30', connected: true,
      days: '111111111111111111111', next: '미정',
      now: [['공통 3', '오늘 기분은 어떠세요?', '울적해요', '울적해요'], ['공통 2', '식사는 잘 하셨어요?', '두 끼 먹었어요', '한 끼 먹었어요']],
      quote: '', ai: '한 번이 아니라 2주 동안 "울적해요"가 이어지고 있어요(14일 중 9일). 식사 횟수도 줄었어요. 다음 상담 전에 안부 전화를 해 보세요.',
      state: '근거 확인 필요', stCls: 'chip c-check', src: '9/28~어제 안부 공통 3 · 공통 2 (14회)',
      related: '4회차(10/7) 상담일지 · "며느리랑 말을 안 한 지 오래됐어요"',
      hist: [['오늘 기분', ['좋아요', '그저 그래요', '울적해요', '울적해요']], ['식사', ['세 끼 먹었어요', '두 끼 먹었어요', '두 끼 먹었어요', '한 끼 먹었어요']], ['잠', ['잘 잤어요', '잘 잤어요', '밤에 자꾸 깨요', '잘 잤어요']]],
      q: ['SQ-F-02', '요즘 집에서 가족분들과 이야기는 좀 나누세요?'] },
    seoyun: { name: '김순자', short: '김순자 님', age: '만 82세 · 여 · 독거', id: 'C-2026-0351', risk: '집중', types: '상실·애도 · 정서·우울', reason: '어르신이 남긴 말씀', rCls: 'chip c-sky', last: '어제 22:10', connected: true,
      days: '111101111111110111111', next: '오늘 16:00 9회차',
      now: [['SQ-E-05', '요즘 혼자 계실 때 영감님 생각이 많이 나세요?', '가끔요', '매일 나요'], ['공통 3', '오늘 기분은 어떠세요?', '그저 그래요', '조금 울적해요']],
      quote: '다음에 오시면 드릴 말씀이 있어요', ai: '8회차 상담에서 나온 사별 이야기와 같은 내용의 답이 안부 앱에서 처음 나왔어요. 어르신이 먼저 말씀을 꺼내실 수 있도록 다음 상담 시작을 열어 두세요.',
      state: '확인 중', stCls: 'chip c-ing', src: '10/6 SQ-E-05 응답 · 어제 22:10 음성 말씀',
      related: '8회차(10/2) 녹취 01:08 · 어르신 말씀 "그 양반 가고 나서 밥을 해 먹을 맛이 안 나요"',
      hist: [['영감님 생각', ['가끔요', '가끔요', '가끔요', '매일 나요']], ['오늘 기분', ['그저 그래요', '그저 그래요', '조금 울적해요', '조금 울적해요']], ['잠', ['자다 깼어요', '자다 깼어요', '밤에 자꾸 깨요', '밤에 자꾸 깨요']]],
      q: ['공통 2', '식사는 잘 하셨어요?'] },
    haeun: { name: '윤기철', short: '윤기철 님', age: '만 73세 · 남 · 독거', id: 'C-2026-0298', risk: '관심', types: '고립·외로움', reason: '무응답 48시간+', rCls: 'chip c-sand', last: '그저께 09:20', connected: true,
      days: '111111111111111111100', next: '10/13 전화상담',
      now: [], quote: '', ai: '48시간 넘게 안부 응답이 없어요. 오늘 안부 전화를 드리고, 연락이 닿지 않으면 생활지원사·가족에게 방문 확인을 요청해 보세요(고독사 예방). 앱 알림이 꺼졌거나 휴대폰 사용이 어려운 경우일 수도 있어요.',
      state: '확인 중', stCls: 'chip c-ing', src: '마지막 응답 그저께 09:20 · 이후 무응답',
      related: '5회차(9/26) 상담일지 · "휴대폰 글씨가 작아서 잘 안 봐요"',
      hist: [['오늘 기분', ['그저 그래요', '좋아요', '그저 그래요', '']], ['잠', ['잘 잤어요', '잘 잤어요', '자다 깼어요', '']], ['복지관', ['다녀왔어요', '다녀왔어요', '안 갔어요', '']]],
      q: ['', ''] },
    yuna: { name: '정말순', short: '정말순 님', age: '만 91세 · 여 · 자녀동거', id: 'C-2026-0229', risk: '일반', types: '생활 적응·여가', reason: '일반', rCls: 'chip c-normal', last: '어제 20:02', connected: true,
      days: '110110101101011011011', next: '10/20 방문상담',
      now: [['공통 3', '오늘 기분은 어떠세요?', '좋아요', '좋아요']], quote: '', ai: '최근 응답에 변화가 없어요. 따로 확인할 점이 없어요. 가족(딸)이 대신 입력을 돕고 있어요.',
      state: '확인 완료', stCls: 'chip c-ok', src: '최근 3주 안부 14회', related: '—',
      hist: [['오늘 기분', ['좋아요', '좋아요', '그저 그래요', '좋아요']], ['잠', ['잘 잤어요', '잘 잤어요', '잘 잤어요', '잘 잤어요']]], q: ['', ''] },
    siwoo: { name: '강덕수', short: '강덕수 님', age: '만 80세 · 남 · 부부', id: 'C-2026-0312', risk: '일반', types: '정서·우울', reason: '안정 · 후속관리 중', rCls: 'chip c-ok', last: '어제 19:15', connected: true,
      days: '111111111111111111111', next: '10/14 종결 상담',
      now: [['공통 3', '오늘 기분은 어떠세요?', '좋아요', '좋아요']], quote: '', ai: '4주 연속 기분 응답이 "좋아요 · 그저 그래요"예요. 후속관리서 근거로 들어가 있어요.',
      state: '확인 완료', stCls: 'chip c-ok', src: '안부 공통 3 · 28회', related: '12회차(10/1) · 어르신이 경로당 모임을 다시 나가기 시작하셨다고 말씀하심',
      hist: [['오늘 기분', ['좋아요', '좋아요', '그저 그래요', '좋아요']], ['잠', ['잘 잤어요', '잘 잤어요', '잘 잤어요', '잘 잤어요']]], q: ['', ''] },
    harin: { name: '한옥분', short: '한옥분 님', age: '만 79세 · 여 · 부부', id: 'C-2026-0251', risk: '일반', types: '가족관계', reason: '앱 미연결 · 초대 전', rCls: 'chip c-normal', last: '—', connected: false,
      days: '', next: '10/15 정기상담', now: [], quote: '', ai: '아직 안부 앱을 연결하지 않으셨어요. 다음 상담에서 큰 글씨 · 음성 답변 사용법과 초대 코드를 안내할 수 있어요. 앱이 어려우시면 가족 연계나 안부 전화로 대신할 수 있어요.', state: '—', stCls: 'chip c-normal', src: '—', related: '—', hist: [], q: ['', ''] }
  };
  const ORDER = ['minjun', 'jiho', 'dohyun', 'yerin', 'seoyun', 'haeun', 'yuna', 'siwoo', 'harin'];
  const COLS = ['3주 전', '2주 전', '지난주', '이번'];
  const FAM = { minjun: ['배우자 · 공유 동의', 'chip c-ok'], jiho: ['딸 · 일부 동의', 'chip c-sand'], dohyun: ['미연결', 'chip c-normal'], yerin: ['아들 · 미동의', 'chip c-check'], seoyun: ['아들 · 일부 동의', 'chip c-sand'], haeun: ['조카 · 공유 동의', 'chip c-ok'], yuna: ['딸 · 공유 동의', 'chip c-ok'], siwoo: ['배우자 · 일부 동의', 'chip c-sand'], harin: ['미연결', 'chip c-normal'] };

  const s = this.state;
  const needKeys = ['minjun', 'jiho', 'dohyun', 'yerin', 'seoyun', 'haeun'];
  const keys = s.f === 'need' ? ORDER.filter((x) => needKeys.includes(x)) : ORDER;
  const rows = keys.map((key) => { const k = KIDS[key]; const ds = (k.days || '').split('');
    return { name: k.name, age: k.age, id: k.id, ini: k.name.slice(0, 1), last: k.last, reason: k.reason, rCls: k.reason === '긴급' ? 'chip c-urgent' : (k.reason === '무응답 48시간+' ? 'chip c-sand' : 'chip c-normal'),
      count: k.connected ? `${ds.filter((c) => c === '1').length} / 21일` : '미연결', fam: FAM[key][0], famCls: FAM[key][1] }; });
  const filters = [['need', '확인할 어르신 6'], ['all', '전체 9']].map(([v, l]) => ({ label: l, cls: s.f === v ? 'on' : '', pick: () => this.setState({ f: v }) }));
  return { rows, filters, alertName: KIDS.minjun.name, silentName: KIDS.haeun.name, real: !!s.real, tgBg: s.real ? '#1F3A56' : '#C5D4DE', tgX: s.real ? '16px' : '2px', toggleReal: () => this.setState({ real: !s.real }) };
}
}
