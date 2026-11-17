// AppNext 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AppNext.jsx)이 이어받아 데이터만 바꾼다.
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


constructor(props) { super(props); this.state = { ck: { 0: true, 1: true, 2: false } }; this._self = '#/AppNext'; }
mountExtra() { this._fk = this.stGet('ispot-app-from'); this._fT = setInterval(() => { const v = this.stGet('ispot-app-from'); if (v !== this._fk) { this._fk = v; this.setState({ __f: Date.now() }); } }, 500); }
componentWillUnmount() { clearInterval(this._t); clearInterval(this._recT); clearInterval(this._fT); }
renderVals() {
  const s = this.state; const C = [['수면 변화 · 기분 저하 정도 (S-03 재확인)', '근거 · 10/6 안부 응답'], ['02:15 발화 화자 · 식사 거름 빈도', '근거 · 8회차 02:15'], ['어르신이 꺼내고 싶은 이야기부터', '근거 · 10/7 안부 앱 음성']];
  const fr = this.stGet('ispot-app-from'); const backHref = /^App[A-Za-z]+\.dc\.html$/.test(fr || '') && fr !== '#/AppNext' ? fr : '#/AppSchedule';
  return Object.assign(this.commonVals('cal'), { backHref, stop: (ev) => { if (ev && ev.stopPropagation) ev.stopPropagation(); },
    checks: C.map(([text, src], i) => ({ text, src, on: !!s.ck[i], toggle: () => this.setState({ ck: { ...this.state.ck, [i]: !this.state.ck[i] } }) })), doneN: String(C.filter((x, i) => s.ck[i]).length),
    goRec: () => this.stSet('ispot-app-rec', JSON.stringify({ elder: '김순자', t: Date.now() })) });
}

}
