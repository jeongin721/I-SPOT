// AppCases 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AppCases.jsx)이 이어받아 데이터만 바꾼다.
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


constructor(props) { super(props); this.state = { q: '', f: 'all', open: null }; }
renderVals() {
  const s = this.state; const c = this.commonVals('cases');
  const D = [
    ['C-2026-0277', '박영수', '박영수', '만 76세 · 남 · 부부', '2026-06-02', '위기', ''], ['C-2026-0351', '김순자', '김순자', '만 82세 · 여 · 독거', '2026-07-28', '집중', '10/29(목) 16:00 · 정기상담 9회차', 1],
    ['C-2026-0412', '오금자', '오금자', '만 77세 · 여 · 독거', '2026-08-19', '집중', '10/27(화) 16:00 · 정기상담 8회차'], ['C-2026-0389', '서복례', '서복례', '만 85세 · 여 · 자녀동거', '2026-09-03', '관심', '10/29(목) 14:00 · 정기상담 6회차'],
    ['C-2026-0338', '이정희', '이정희', '만 69세 · 여 · 자녀동거', '2026-08-05', '관심', '10/28(수) 13:00 · 방문상담'], ['C-2026-0374', '최만석', '최만석', '만 88세 · 남 · 독거', '2026-09-25', '집중', ''],
    ['C-2026-0298', '윤기철', '윤기철', '만 73세 · 남 · 부부', '2026-06-20', '관심', '10/30(금) 15:00 · 전화상담'], ['C-2026-0229', '정말순', '정말순', '만 91세 · 여 · 독거', '2026-05-14', '일반', ''],
    ['C-2026-0312', '강덕수', '강덕수', '만 80세 · 남 · 독거', '2026-04-08', '일반', ''], ['C-2026-0251', '한옥분', '한옥분', '만 79세 · 여 · 부부', '2026-05-30', '일반', '']];
  const RC = { '위기': 'chip red', '집중': 'chip red', '관심': 'chip gold', '일반': 'chip' };
  const q = (s.q || '').trim();
  const list = D.filter((r) => (s.f === 'wk' ? !!r[6] : true) && (!q || r[1].includes(q) || r[0].toLowerCase().includes(q.toLowerCase())));
  const cur = s.open ? D.find((r) => r[0] === s.open) : null;
  let MM = null; try { MM = JSON.parse(this.stGet('ispot-app-memo') || 'null'); } catch (e) {} if (!Array.isArray(MM)) MM = [{ id: 'm1', elder: '김순자', text: '방문 상담 메모: 보청기 착용, 천천히 말씀드리기.\n약 봉투 확인 — 혈압약 이틀분 남음. 다음 방문 때 아드님 연락처 다시 확인하기.', t: '오늘 15:20' }, { id: 'm2', elder: '', text: '금요일 오전 슈퍼비전 자료 준비', t: '어제 18:02' }, { id: 'm3', elder: '오금자', text: '복지관 담당 사회복지사와 통화 예정 (11/2 오전) · 프로그램 재참여 문의', t: '10/27 09:40' }];
  const myM = cur ? MM.filter((m) => m.elder === cur[2]) : []; const memo = myM.length ? myM.map((m) => m.text + ' (' + m.t + ')').join('\n\n') : '-';
  const F = [['all', '전체'], ['wk', '이번 주 상담']];
  return Object.assign(c, { stop: (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); }, total: String(D.length),
    q: s.q, setQ: (ev) => this.setState({ q: ev.target.value }),
    fs: F.map(([k, label]) => ({ label, sel: s.f === k ? 'true' : 'false', cls: s.f === k ? 'on' : '', pick: () => this.setState({ f: k }) })),
    countLabel: list.length + '명', noRows: list.length === 0,
    rows: list.map((r) => ({ id: r[0], name: r[1], age: r[3], date: r[4], rk: r[5], rkCls: RC[r[5]], next: r[6] ? '다음 상담 ' + r[6] : '예정된 상담 없음', nextCls: r[6] ? 'cs-next' : 'cs-next none', aria: r[1] + ' 사례 요약 보기', open: () => this.setState({ open: r[0] }) })),
    shOpen: !!cur, shClose: () => this.setState({ open: null }),
    v: cur ? { name: cur[1] + ' · ' + cur[3], rk: cur[5], rkCls: RC[cur[5]], brief: !!cur[7], noBrief: !cur[7],
      kv: [['사례 ID', cur[0]], ['접수일', cur[4]], ['다음 상담', cur[6] || '예정 없음'], ['메모', memo]].map(([k, v]) => ({ k, v, cls: k === '메모' ? 'kv-memo' : '' })),
      toBrief: () => this.stSet('ispot-app-from', '#/AppCases'),
      hist: () => this.stSet('ispot-app-hist', JSON.stringify({ id: cur[0], t: Date.now() })),
      rec: () => this.stSet('ispot-app-rec', JSON.stringify({ elder: cur[2], t: Date.now() })) } : {} });
}

}
