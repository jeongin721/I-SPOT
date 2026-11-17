// AppHistory 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AppHistory.jsx)이 이어받아 데이터만 바꾼다.
/* eslint-disable */
import { DCLogic } from '../dc';

export default class DesignLogic extends DCLogic {

stGet(k) { let v = null; try { v = window.localStorage.getItem(k); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem(k); } catch (e) {} } if (!v) { try { v = (window.top.__ispotSt || {})[k]; } catch (e) {} } if (!v) v = (window.__ispotSt || {})[k]; return v || ''; }
stSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} try { window.sessionStorage.setItem(k, v); } catch (e) {} try { window.top.__ispotSt = window.top.__ispotSt || {}; window.top.__ispotSt[k] = v; } catch (e) {} window.__ispotSt = window.__ispotSt || {}; window.__ispotSt[k] = v; }
themeRead() { let v = null; try { v = window.localStorage.getItem('ispot-theme'); } catch (e) {} if (!v) { try { v = window.sessionStorage.getItem('ispot-theme'); } catch (e) {} } if (!v) { try { v = window.top.__ispotTheme; } catch (e) {} } if (!v) v = window.__ispotTheme; return v === 'dark'; }
qRead() { let a = null; try { a = JSON.parse(this.stGet('ispot-app-q') || 'null'); } catch (e) {} if (!Array.isArray(a)) { a = [
  { id: 'q1', name: '김순자_8회차_방문상담.m4a', kind: '녹음', who: '김순자 · 8회차', size: '23.4MB', status: 'fail', err: '네트워크 연결이 끊겨 올리지 못했어요', t: '오늘 15:42' },
  { id: 'q2', name: '상담동의서_사진_01.jpg', kind: '사진', who: '오금자', size: '2.1MB', status: 'done', t: '오늘 11:05' },
  { id: 'q3', name: '복지관_이용확인서.pdf', kind: '문서', who: '서복례', size: '480KB', status: 'done', t: '어제 17:20' }]; this.stSet('ispot-app-q', JSON.stringify(a)); } return a; }
qWrite(a) { this.stSet('ispot-app-q', JSON.stringify(a)); this.setState({ __q: Date.now() }); }
qSet(id, patch) { this.qWrite(this.qRead().map((x) => (x.id === id ? { ...x, ...patch } : x))); }
qRetry(id) { this.qSet(id, { status: 'run', err: '' }); setTimeout(() => { try { this.qSet(id, { status: 'done', t: '방금' }); } catch (e) {} }, 1800); }
qAdd(item) { const id = 'q' + Date.now().toString(36); this.qWrite([{ id, status: 'run', t: '방금', ...item }, ...this.qRead()]); setTimeout(() => { try { this.qSet(id, { status: 'done' }); } catch (e) {} }, 2000); return id; }
elders() { return ['김순자', '서복례', '오금자', '이정희', '윤기철', '최만석', '강덕수', '한옥분', '정말순', '박영수']; }
componentDidMount() {
  this._raw = this.stGet('ispot-app-q') + '|' + this.themeRead();
  this._t = setInterval(() => { const r = this.stGet('ispot-app-q') + '|' + this.themeRead(); if (r !== this._raw) { this._raw = r; this.setState({ __t: Date.now() }); } }, 600);
  if (this.mountExtra) this.mountExtra();
}
componentWillUnmount() { clearInterval(this._t); clearInterval(this._recT); }
commonVals(cur) {
  const q = this.qRead(); const fails = q.filter((x) => x.status === 'fail'); const st = this.state || {};
  const notes = fails.map((x) => ({ red: 'red', title: '업로드 실패 · ' + x.kind, sub: x.name + ' · ' + x.t, desc: x.err || '', hasAct: true, act: '다시 올리기', go: () => this.qRetry(x.id), hasLink: false, href: '', linkLabel: '', nav: () => {} }))
    .concat([{ red: '', title: '다음 상담 준비가 됐어요', sub: '오늘 16:00 · 김순자 · 9회차 정기상담', desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: '#/AppNext', linkLabel: '다음 상담 준비 보기', nav: () => { const f = this._self || ({ home: '#/AppHome', cases: '#/AppCases', cal: '#/AppSchedule', memo: '#/AppMemo', up: '#/AppUpload', rec: '#/AppRecord', set: '#/AppSettings' })[cur]; if (f && f !== '#/AppNext') this.stSet('ispot-app-from', f); } },
      { red: '', title: '오늘 남은 상담 2건', sub: '14:00 서복례 · 16:00 김순자', desc: '', hasAct: false, act: '', go: () => {}, hasLink: true, href: '#/AppSchedule', linkLabel: '일정 보기', nav: () => {} }]);
  return {
    rootCls: this.themeRead() ? 'app dark' : 'app',
    tabs: [['home', '홈', '#/AppHome'], ['up', '업로드', '#/AppUpload'], ['rec', '', '#/AppRecord'], ['cal', '일정', '#/AppSchedule'], ['memo', '메모', '#/AppMemo']].map(([k, label, href]) => ({ label, href, aria: k === 'rec' ? '녹음' : label, cls: 'tab' + (k === 'rec' ? ' tab-rec' : '') + (k === cur ? ' on' : ''), cur: k === cur ? 'page' : 'false', isHome: k === 'home', isRec: k === 'rec', isUp: k === 'up', isCal: k === 'cal', isMemo: k === 'memo', hasLabel: !!label })),
    homeCls: cur === 'home' ? 'ibtn on' : 'ibtn', setCls: cur === 'set' ? 'ibtn on' : 'ibtn', homeCur: cur === 'home' ? 'page' : 'false', setCur: cur === 'set' ? 'page' : 'false',
    ntCount: String(notes.length), ntHas: notes.length > 0, ntOpen: !!st.__nt, ntToggle: () => this.setState({ __nt: !st.__nt }), ntClose: () => this.setState({ __nt: false }), notes,
    failN: fails.length, hasFail: fails.length > 0, failText: '업로드 실패 ' + fails.length + '건 · 다시 올려 주세요'
  };
}


constructor(props) { super(props); this.state = {}; this._self = '#/AppHistory'; }
mountExtra() { this._hk = this.stGet('ispot-app-hist'); this._hT = setInterval(() => { const v = this.stGet('ispot-app-hist'); if (v !== this._hk) { this._hk = v; this.setState({ __h: Date.now() }); } }, 500); }
componentWillUnmount() { clearInterval(this._t); clearInterval(this._recT); clearInterval(this._hT); }
renderVals() {
  const c = this.commonVals('cases'); let h = null; try { h = JSON.parse(this.stGet('ispot-app-hist') || 'null'); } catch (e) {}
  const id = (h && h.id) || 'C-2026-0351';
  const CS = { 'C-2026-0277': ['박영수', 4], 'C-2026-0351': ['김순자', 8], 'C-2026-0412': ['오금자', 7], 'C-2026-0389': ['서복례', 5], 'C-2026-0338': ['이정희', 4], 'C-2026-0374': ['최만석', 2], 'C-2026-0298': ['윤기철', 5], 'C-2026-0229': ['정말순', 6], 'C-2026-0312': ['강덕수', 6], 'C-2026-0251': ['한옥분', 5] };
  const cs = CS[id] || ['김순자', 8]; const N = cs[1];
  // 웹 탭 2 · 상담 이력(CaseHistory)과 같은 데이터
  const RAW = {
    8: { date: '2026-10-02', kind: '방문상담 · 24분', st: '처리 중', stCls: 'chip gold', sum: '', ai: '어르신은 배우자 사별 후 밤에 잠들기 어렵고 혼자 식사하는 것이 힘들다고 말씀하심. 아들과 통화가 줄어 서운함을 표현하심. 식사 거름 관련 발화는 화자 확인 필요. (AI 요약은 확인 제안이며 판단이 아님)', diary: '',
      lines: [['00:41', '어르신', '밤에 누우면 영감 생각이 나서 잠이 안 와요.'], ['01:08', '어르신', '아들이 바쁘니까… 전화도 요즘은 잘 안 해요.'], ['02:15', '화자 확인 중', '혼자 먹으니 밥 생각이 없어요.']], sigs: ['정서 · 우울감', '수면 변화', '식사 변화 · 확인 중', '고립 · 외로움'] },
    7: { date: '2026-09-18', kind: '정기상담 · 50분', st: '확정', stCls: 'chip', sum: 'S-03 우울척도 재검 · 비상연락 체계 확인 · 생활지원사 방문 주 2회로 조정.', diary: '어르신과 함께 힘들 때 연락할 곳을 정리함. 아들(이정훈)과 생활지원사를 비상연락처로 다시 확인하고, 109 안내 카드를 전화기 옆에 붙여 드림. 가족 정보 공유는 본인 동의 범위(일정 · 건강 상태)에서만 하기로 함.',
      lines: [['02:40', '어르신', '힘들면 아들한테 전화하면 되겠지요.'], ['05:10', '어르신', '아들한테 걱정 끼치기 싫어서 말을 못 했어요.']], sigs: ['정서 · 우울감', '가족관계 · 연락 감소'] },
    6: { date: '2026-09-04', kind: '정기상담 · 45분', st: '확정', stCls: 'chip', sum: '사별 후 애도 · 외출 감소 · 복지관 이용 중단.', diary: '배우자를 보낸 뒤 외출이 줄고 복지관 프로그램도 그만두셨다고 말씀하심. 자살 생각은 없다고 하셨으며, 다음 회차에 기분 변화를 다시 확인하기로 함.',
      lines: [['03:20', '어르신', '복지관 가도 그 사람 생각만 나서 안 가게 돼요.'], ['05:02', '어르신', '그런 생각까지는… 안 해 봤어요.']], sigs: ['상실 · 애도', '고립 · 외출 감소'] } };
  const DATES = ['', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-21', '2026-08-28'];
  const gen = (n) => ({ date: DATES[n] || '', kind: n === 1 ? '초기상담 · 40분' : '정기상담 · 45분', st: '확정', stCls: 'chip', sum: n <= 3 ? '관계 형성 · 일상생활 중심.' : '사별 후 정서 변화 · 말씀 기록.',
    diary: n <= 3 ? '관계 형성 단계. 하루 일과와 경로당 · 이웃 교류를 중심으로 대화함. 보청기 착용, 천천히 말씀드림.' : '배우자 사별 후 기분 저하와 불면을 처음 자세히 말씀하심. 어르신 말씀을 그대로 기록함.',
    lines: [['01:00', '어르신', n <= 3 ? '경로당에 가끔 나가서 화투도 치고 그래요.' : '그 사람 가고 나서는 밥을 혼자 먹으니 대충 먹게 돼요.']], sigs: n <= 3 ? [] : ['정서 · 우울감'] });
  const isSY = id === 'C-2026-0351';
  const OD = ['2026-07-30', '2026-08-13', '2026-08-27', '2026-09-10', '2026-09-24', '2026-10-08', '2026-10-20'];
  const other = (n) => ({ date: OD[n - 1] || '', kind: n === 1 ? '초기상담 · 40분' : '정기상담 · 45분', st: '확정', stCls: 'chip', sum: n === 1 ? '초기상담 · 상담 동의 확인 · 생활 리듬과 건강 상태 확인.' : n === N ? '최근 생활 변화 확인 · 다음 상담 목표 정리.' : '일상생활 · 건강 점검 · 정서 상태 확인.',
    diary: n === 1 ? '어르신과 첫 만남. 상담 · 녹음 동의를 확인하고 생활 리듬, 복용 약, 돌봄 상황을 중심으로 대화함.' : '지난 상담 이후 변화를 확인함. 특이 사항 없음.', lines: [], sigs: [] });
  const ses = []; for (let n = N; n >= 1; n--) { const r = isSY ? (RAW[n] || gen(n)) : other(n);
    ses.push({ no: n + '회차', date: r.date, kind: r.kind, st: r.st, stCls: r.stCls, sumLb: r.sum ? '상담 요약' : 'AI 요약 (웹에서 확정 전)', sum: r.sum || r.ai, hasDiary: !!r.diary, diary: r.diary,
      hasLines: r.lines.length > 0, lines: r.lines.map(([t, sp, s]) => ({ t, sp, s })), hasSig: r.sigs.length > 0, sigs: r.sigs }); }
  const flow = isSY ? [['1~3회차', '관계 형성 · 일상생활', '라포 형성 · 특이 사항 없음'], ['4~6회차', '사별 후 상실 · 애도', '식사 거름 · 외출 감소 첫 언급'], ['7~8회차', '우울감 · 가족관계', '"걱정 끼치기 싫어서" · 최근']]
    : [['1회차', '초기상담', '상담 동의 · 생활 리듬 확인'], ['2~' + N + '회차', '생활 점검 · 정서 확인', '특이 사항 없음']];
  const bars = isSY ? [['상실 · 애도', 38], ['정서 · 우울', 27], ['가족관계', 20], ['고립 · 외로움', 10], ['식사 · 건강', 5]] : [];
  const last = ses[0]; const first = ses[ses.length - 1];
  return Object.assign(c, { stop: (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); },
    sub: cs[0] + ' · ' + id, range: '총 ' + N + '회 · ' + first.date.slice(5).replace('-', '/') + ' ~ ' + last.date.slice(5).replace('-', '/'), aiRange: N > 1 ? '1~' + N + '회차' : '1회차',
    flow: flow.map(([k, t, d]) => ({ k, t, d })), hasBars: bars.length > 0, bars: bars.map(([k, v]) => ({ k, v: String(v) })), count: String(N), ses });
}

}
