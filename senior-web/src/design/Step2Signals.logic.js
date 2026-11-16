// Step2Signals 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Step2Signals.jsx)이 이어받아 데이터만 바꾼다.
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
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, this.ntVals(), { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), markBack: () => { const v = '#/Step2Signals'; try { window.localStorage.setItem('ispot-back', v); } catch (e) {} try { window.sessionStorage.setItem('ispot-back', v); } catch (e) {} try { window.top.__ispotBack = v; } catch (e) {} window.__ispotBack = v; }, themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { lv: '', sev: {}, open: {} }; }
renderValsBase() {
  const s = this.state;
  const A = {
    mood: ['일시적인 기분 저하, 일상은 유지', '기분 저하가 잦으나 일상은 대체로 유지', '우울감 · 흥미 감소 지속, 사별 등 상실 후 회복이 더딤', '우울감으로 식사 · 수면 · 외출 등 일상 기능이 뚜렷이 떨어짐', '심한 무기력 · 절망감, 죽음 관련 언급 동반'],
    suicide: ['죽음에 대한 일반적인 언급', '살고 싶지 않다는 수동적 표현, 단발', '수동적 죽음 바람 반복 또는 최근 상실 동반', '자살 생각 표현 · 방법 언급', '계획 · 수단 접근 · 과거 시도 확인 — 즉시 109 · 119 연계'],
    daily: ['가끔 식사를 거르거나 잠을 설침', '식사량 · 수면 시간 감소 반복, 건강 영향 없음', '하루 한 끼 수준 · 새벽 각성 지속, 체중 감소 우려', '식사 · 수면 변화로 기력 저하 · 건강 영향', '탈수 · 영양 결핍 등 건강 위험 수준'],
    isolation: ['교류는 줄었으나 연락할 사람이 있음', '외출 · 모임 감소, 가족 연락 주 1회 이하', '외로움 · 서운함 표현, 기관 이용 중단', '대부분 혼자 지내고 연락할 사람이 거의 없음', '장기간 교류 단절 · 안부 무응답 (고독사 위험)'],
    cognition: ['가벼운 건망증 호소', '같은 질문을 가끔 반복', '날짜 혼동 · 약 복용 잊음 반복', '길 잃음 · 일상 수행 어려움', '안전이 위협되는 혼동 — 치매안심센터 연계 우선']
  };
  const T = [
    { k: 'mood', label: '우울감', ev: '직접 근거', ai: 3, flag: '', refs: ['8회차 01:36 어르신 "쓸쓸하지요."', '8회차 00:20 어르신 "복지관은 요새 통 못 나갔어요."'] },
    { k: 'suicide', label: '자살 생각', ev: '확인 필요', ai: 0, flag: 'S1', refs: ['8회차 02:15 화자 불확실 "이렇게 사느니 그만 가도 괜찮겠다 싶어요." · 신뢰도 0.70', '화자 확인 후 S-04 자살위험 선별 · 필요 시 109 안내'] },
    { k: 'daily', label: '식사·수면 변화', ev: '직접 근거', ai: 3, flag: 'S3', refs: ['8회차 00:41 어르신 "하루 한 끼 먹을까 말까 해요."', '8회차 01:08 어르신 "새벽 세 시면 깨서 그냥 앉아 있어요."'] },
    { k: 'isolation', label: '고립·외로움', ev: '직접 근거', ai: 2, flag: '', refs: ['8회차 01:08 어르신 "전화도 내가 먼저 해야 받아요."'] },
    { k: 'cognition', label: '인지 변화', ev: '언급 없음', ai: 0, flag: '', refs: ['언급 없음 ≠ 변화 없음 · 관찰하거나 여쭙지 않았을 수 있음 · 상담사는 진단하지 않음'] }
  ];
  const evTone = { '직접 근거': ['#1F3A56', '#FFFFFF'], '확인 필요': ['#ECF5FA', '#55687A'], '언급 없음': ['#FFFFFF', '#8094A3'] };
  const types = T.map((t) => {
    const cur = s.sev[t.k] !== undefined ? s.sev[t.k] : t.ai;
    const open = !!s.open[t.k];
    return { label: t.label, ev: t.ev, evBg: evTone[t.ev][0], evFg: evTone[t.ev][1], flag: !!t.flag, flagText: '위기 확인 플래그 ' + t.flag,
      sevText: cur ? String(cur) : '–', sevSuffix: cur ? '/ 5' : (t.ev === '확인 필요' ? '확인 후 판단' : ''), fixed: s.sev[t.k] !== undefined && s.sev[t.k] !== t.ai,
      boxes: [1, 2, 3, 4, 5].map((n) => ({ n, aria: t.label + ' 우려 정도 ' + n, bg: n <= cur ? (cur >= 4 ? '#A33B2E' : '#5FA4D6') : '#FFFFFF', fg: n <= cur ? '#FFFFFF' : '#8094A3', bd: n <= cur ? 'transparent' : '#C5D4DE',
        pick: () => this.setState({ sev: { ...s.sev, [t.k]: cur === n ? 0 : n } }) })),
      matched: cur ? cur + '단계 · ' + A[t.k][cur - 1] : (t.ev === '확인 필요' ? '화자 · 근거 확인 전이라 단계를 매기지 않았어요 · 먼저 확인해 주세요' : '해당 내용 없음'),
      refs: t.refs, open, toggleLabel: open ? '기준 닫기' : '기준 보기', toggle: () => this.setState({ open: { ...s.open, [t.k]: !open } }),
      anchors: A[t.k].map((text, i) => ({ n: i + 1, text, bg: i + 1 === cur ? '#E8F4FC' : 'transparent', fg: i + 1 === cur ? '#1F3A56' : '#66788A', fw: i + 1 === cur ? 700 : 400 })) };
  });
  const levels = ['위기', '집중', '관심', '일반'].map((l) => { const on = s.lv === l; const tone = (l === '위기' || l === '집중') ? '#A33B2E' : (l === '관심' ? '#235E8C' : '#55687A');
    return { label: l, on: on ? 'true' : 'false', bg: on ? ((l === '위기' || l === '집중') ? '#F7E4DF' : l === '관심' ? '#E6F3FC' : '#ECF5FA') : '#FFFFFF', bd: on ? tone : '#C5D4DE', fg: on ? tone : '#55687A', pick: () => this.setState({ lv: on ? '' : l }) }; });
  return { types, levels, decisionNote: s.lv ? (s.lv === '집중' ? 'AI 제안과 같음 · 상담사 확정' : 'AI 제안(집중)과 다름 · 상담사 판단으로 저장') + (s.lv === '위기' ? ' · 109 · 정신건강복지센터 연계 안내' : '') : '',
    decisionShort: s.lv || '선택 전' };
}
}
