// SessionDetail 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/SessionDetail.jsx)이 이어받아 데이터만 바꾼다.
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
sesRead() { let v = null; try { v = window.localStorage.getItem('ispot-ses'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-ses'); } catch (e) {} } if (!v) { try { v = window.top.__ispotSes; } catch (e) {} } if (!v) v = window.__ispotSes; return v || ''; }
sesSync() { const v = this.sesRead(); if (v && v !== this._sesTok) { this._sesTok = v; const n = parseInt(String(v).split('|')[0], 10); if (n >= 1 && n <= 8 && n !== this.state.n) this.setState({ n }); } }
jobRead() { let v = null; try { v = window.localStorage.getItem('ispot-job'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-job'); } catch (e) {} } if (!v) { try { v = window.top.__ispotJob; } catch (e) {} } if (!v) v = window.__ispotJob; try { return v ? JSON.parse(v) : null; } catch (e) { return null; } }
jobPhase() { const j = this.jobRead(); if (!j || !j.t) return ''; const el = Date.now() - j.t; return el < 8000 ? 'run' : el < 11000 ? 'done' : el < 11500 ? 'out' : ''; }
jobWrite(v) { try { window.localStorage.setItem('ispot-job', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-job', v); } catch (e) {} try { window.top.__ispotJob = v; } catch (e) {} window.__ispotJob = v; }
componentDidMount() {
  this._slDoc = (e) => { if (!(this.state && this.state.__slOpen)) return; if (e.type === 'keydown' ? e.key === 'Escape' : !(e.target && e.target.closest && e.target.closest('.sl-wrap'))) this.setState({ __slOpen: false }); }; try { document.addEventListener('mousedown', this._slDoc); document.addEventListener('keydown', this._slDoc); } catch (e) {}
  this._ntRaw = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); this._ntT = setInterval(() => { const r = this.ntGet('ispot-intake') + this.ntGet('ispot-noti-read'); if (r !== this._ntRaw) { this._ntRaw = r; this.setState({ __ntTick: Date.now() }); } }, 700);
  this._ntDoc = (e) => { if (this.state && this.state.__ntOpen && !(e.target && e.target.closest && e.target.closest('.nt-wrap'))) this.setState({ __ntOpen: false }); }; try { document.addEventListener('mousedown', this._ntDoc); } catch (e) {}
  this.sesSync();
  this._thmT = setInterval(() => { this.sesSync(); if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
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
ntTasks() { return [[3, '어르신 안부 전화 상담'], [7, '가족·생활지원사 면담'], [30, '상담 계획서 작성']]; }
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
  const L = [[1, '7/31(금) 초기상담(방문)'], [2, '8/7(금) 방문상담'], [3, '8/14(금) 전화상담'], [4, '8/21(금) 방문상담'], [5, '8/28(금) 내방상담'], [6, '9/4(금) 방문상담'], [7, '9/18(금) 내방상담'], [8, '10/2(금) 방문상담']];
  const open = !!(this.state && this.state.__slOpen); const c = L.find((x) => x[0] === cur) || L[7];
  return { slOpen: open, slExp: open ? 'true' : 'false', slToggle: () => this.setState({ __slOpen: !open }), slBtn: btnFn(c), slNo: cur + '회차', slSub: c[1],
    slItems: L.slice().reverse().map(([n, meta]) => ({ no: n + '회차', meta, st: n === 8 ? '처리 중' : '확정', stCls: n === 8 ? 'chip c-check' : 'chip c-ok', on: n === cur ? 'true' : 'false', cls: n === cur ? 'on' : '', pick: () => { this.setState({ __slOpen: false }); pick(n); } })) };
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.slVals((this.state && this.state.n) || 8, (n) => this.setState({ n }), (c) => c[0] + '회차 · ' + c[1]), this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/SessionDetail'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { n: 8 }; }
renderValsBase() {
  const RAW = {
    8: { date: '2026-10-02', kind: '방문상담 · 24분', status: '처리 중', st: 'chip c-check', sig: '채택 3 · 보류 1', proc: true,
      sttState: '검수 중 · 저신뢰 3곳', sttCls: 'chip c-check',
      lines: [{ t: '00:41', sp: '어르신', s: '그 양반 가고 나서는 집이 너무 조용해요. 하루 종일 말 한마디 안 할 때도 있어요.', c: '62%' }, { t: '01:08', sp: '어르신', s: '아들한테는 말 안 해요. 바쁜 애한테 짐 되기 싫어서요.', c: '58%' }, { t: '01:36', sp: '어르신', s: '그냥 적적해요.', c: '91%' }, { t: '02:15', sp: '화자?', s: '끼니를 그냥 넘길 때가 많아요.', c: '70%' }],
      diaryState: '작성 전', diaryCls: 'chip c-check', diary: '아직 작성하지 않았어요. 회차 처리 3단계에서 AI 초안을 받아 작성해요.', diaryBtn: '상담일지 작성하러 가기',
      sumState: '작성 전', sumCls: 'chip c-check', summary: '요약은 회차 처리 3단계에서 확정돼요.',
      ai: '어르신이 배우자 사별 후 집이 조용해 외로움을 크게 느낀다고 말씀하심. 아들에게 "짐이 될까 봐" 어려움을 알리지 않는다고 하심. 식사 관련 발화는 화자 확인 필요.',
      sigs: [['정서', '우울감 · 기분 저하 · 00:41'], ['정서', '상실 · 애도 반응 · 00:41'], ['고립', '외로움 · 고립감 · 01:08, 01:36'], ['생활', '식사 · 수면 변화 (보류) · 02:15']] },
    7: { date: '2026-09-18', kind: '내방상담 · 50분', status: '확정', st: 'chip c-ok', sig: '채택 2', proc: false, sttState: '검수 완료', sttCls: 'chip c-ok',
      lines: [{ t: '02:40', sp: '어르신', s: '마음이 답답하면 생활지원사 선생님한테 전화해 볼게요.', c: '93%' }, { t: '05:10', sp: '어르신', s: '가끔은 이렇게 살아서 뭐 하나 싶어요.', c: '88%' }],
      diaryState: '확정', diaryCls: 'chip c-ok', diary: '위기 시 연락 계획을 어르신과 함께 정리함. 마음이 힘들 때 생활지원사 · 상담사에게 연락하기로 함. "이렇게 살아서 뭐 하나" 말씀이 있어 S-04 자살위험 선별을 실시함(현재 계획 · 수단 없음, 보호요인: 아들 · 경로당 지인). 109 안내함. 다음 회차에도 계속 확인하기로 함.', diaryBtn: '일지 수정',
      sumState: '확정', sumCls: 'chip c-ok', summary: '위기 시 연락 계획 수립 · 죽음 관련 언급 1건 · S-04 선별(계획 없음) · 109 안내.',
      ai: '어르신과 위기 시 연락 계획을 세움. 삶의 의미 저하와 관련된 말씀이 있어 자살위험 선별 확인이 필요함.', sigs: [['고립', '외로움 · 고립감 · 02:40'], ['위기', '죽음 관련 언급 · 05:10']] },
    6: { date: '2026-09-04', kind: '방문상담 · 45분', status: '확정', st: 'chip c-ok', sig: '채택 2', proc: false, sttState: '검수 완료', sttCls: 'chip c-ok',
      lines: [{ t: '03:20', sp: '어르신', s: '밤에 누우면 그 양반 생각이 나서 잠이 안 와요.', c: '95%' }, { t: '05:02', sp: '어르신', s: '밥은… 그냥 대충 먹어요.', c: '90%' }],
      diaryState: '확정', diaryCls: 'chip c-ok', diary: '배우자 생각에 잠들기 어렵다고 말씀하심. 식사 질문에는 "대충 먹는다"고 답하심. 식사 · 수면 변화를 기록해 둠.', diaryBtn: '일지 수정',
      sumState: '확정', sumCls: 'chip c-ok', summary: '사별 후 불면 · 식사 질문에 모호한 답.', ai: '어르신이 배우자 사별 후 불면과 그리움을 표현하심.',
      sigs: [['정서', '우울감 · 기분 저하 · 05:02'], ['고립', '외로움 · 고립감 · 03:20']] }
  };
  const DATES = ['', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-21', '2026-08-28'];
  const getS = (n) => RAW[n] || { date: DATES[n], kind: n === 1 ? '초기상담(방문) · 40분' : n === 3 ? '전화상담 · 25분' : n === 5 ? '내방상담 · 45분' : '방문상담 · 45분', status: '확정', st: 'chip c-ok', proc: false,
    sig: n <= 3 ? '신호 없음' : '채택 ' + (n === 5 ? 3 : 1), sttState: '검수 완료', sttCls: 'chip c-ok',
    lines: [{ t: '01:00', sp: '어르신', s: n <= 3 ? '복지관 점심은 가끔 먹으러 가요.' : '영감 가고 나서는 입맛이 통 없어요.', c: '94%' }],
    diaryState: '확정', diaryCls: 'chip c-ok', diary: n <= 3 ? '관계 형성 단계. 하루 일과와 이용 중인 서비스를 중심으로 대화함.' : '배우자 사별 후 입맛 저하를 처음 말씀하심. 말씀 내용을 그대로 기록함.', diaryBtn: '일지 수정',
    sumState: '확정', sumCls: 'chip c-ok', summary: n <= 3 ? '관계 형성 · 일상 파악 중심.' : '사별 후 입맛 저하 언급 · 원문 기록.',
    ai: n <= 3 ? '어르신과 라포 형성 중. 특이 사항 없음.' : '어르신이 사별 후 입맛 저하를 말씀하심.',
    sigs: n <= 3 ? [] : [['정서', '우울감 · 기분 저하 · 01:00']] };

  const s = this.state; const r = getS(s.n); const proc = r.proc;
  const picks = [1, 2, 3, 4, 5, 6, 7, 8].map((n) => ({ label: n + '회', on: n === s.n ? 'true' : 'false', bg: n === s.n ? '#E8F4FC' : '#FFFFFF', bd: n === s.n ? '#1F3A56' : '#D9E3EA', fg: n === s.n ? '#1F3A56' : '#1F3A56', fw: n === s.n ? 700 : 400, go: () => this.setState({ n }) }));
  const firstLine = r.lines[0] ? `${r.lines[0].t} "${r.lines[0].s}"` : '';
  const defs = proc ? [
    { href: '#/Step1Record', label: '기록 확인', st: '진행 중 · 저신뢰 3곳', stCls: 'chip c-check', preview: '핵심 발화 4개 · ' + firstLine, cur: true },
    { href: '#/Step2Signals', label: '정서·위기 신호 확인', st: '대기', stCls: 'chip c-normal', preview: 'AI 신호 4개 · 정서 2 · 고립 1 · 생활 1' },
    { href: '#/Step3Summary', label: '상담일지 작성', st: '작성 전', stCls: 'chip c-normal', preview: '요약 · 일지 AI 초안 준비됨' },
    { href: '#/Step4Next', label: '다음 상담 준비', st: '대기', stCls: 'chip c-normal', preview: '확인 사항 3 · 추가 질문 5 (AI 초안)' }
  ] : [
    { href: '#/Step1Record', label: '기록 확인', st: '검수 완료', stCls: 'chip c-ok', preview: firstLine },
    { href: '#/Step2Signals', label: '정서·위기 신호 확인', st: r.sig, stCls: 'chip c-ok', preview: r.sigs.length ? r.sigs.map((g) => g[0] + ' · ' + g[1]).join('  /  ') : '채택 신호 없음' },
    { href: '#/Step3Summary', label: '상담일지 작성', st: '확정', stCls: 'chip c-ok', preview: r.summary },
    { href: '#/Step4Next', label: '다음 상담 준비', st: '브리핑 반영', stCls: 'chip c-ok', preview: (s.n + 1) + '회차 브리핑' }
  ];
  const steps = defs.map((d, i) => ({ ...d, mark: !proc ? '✓' : String(i + 1),
    nBg: !proc ? '#ECF5FA' : (d.cur ? '#1F3A56' : '#DDE6EC'), nFg: !proc ? '#55687A' : (d.cur ? '#D6ECFA' : '#66788A'),
    ring: d.cur ? 'inset 0 0 0 2px #1F3A56' : 'none', bg: '#FFFFFF' }));
  return { picks, steps, cur: { no: s.n + '회차', meta: `${r.date} · ${r.kind} · 담당 이서연`, status: r.status, st: r.st } };
}
}
