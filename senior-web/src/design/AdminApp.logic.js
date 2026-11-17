// AdminApp 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/AdminApp.jsx)이 이어받아 데이터만 바꾼다.
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
  this._thmT = setInterval(() => { if (this.jobPhase() !== this._jobPh || this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark; const jp = this.jobPhase(); this._jobPh = jp; const jj = jp ? (this.jobRead() || {}) : {};
  return Object.assign({}, v, { jobShow: !!jp, jobRun: jp === 'run', jobDone: jp === 'done' || jp === 'out', jobCls: jp === 'out' ? 'out' : '', jobName: jj.name || '', jobGo: () => this.jobWrite(''), themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

constructor(props) { super(props); this.state = { cf: 'all', sf: 'all', inv: {}, done: {} }; }
renderValsBase() {
  const s = this.state;
  const segOf = (key, cur, opts) => opts.map(([v, l]) => ({ label: l, cls: cur === v ? 'on' : '', pressed: cur === v ? 'true' : 'false', pick: () => this.setState({ [key]: v }) }));
  const C = [
    ['c1', '박영수', 'C-2026-0277', '이서연', 'on', '9/02', '오늘 08:12', 'all'], ['c2', '임춘자', 'C-2026-0366', '박지훈', 'on', '9/05', '오늘 07:50', 'part'],
    ['c3', '김순자', 'C-2026-0351', '이서연', 'on', '9/18', '어제 22:10', 'part'], ['c4', '한동길', 'C-2026-0418', '정다은', 'on', '9/22', '어제 21:40', 'no'],
    ['c5', '오정숙', 'C-2026-0402', '한승호', 'on', '9/30', '어제 20:31', 'none'], ['c6', '문병철', 'C-2026-0359', '한승호', 'on', '8/20', '10/16', 'all'],
    ['c7', '배종호', 'C-2026-0384', '박지훈', 'on', '8/30', '10/15', 'part'], ['c8', '서영자', 'C-2026-0377', '오유진', 'on', '8/15', '10/14', 'none'],
    ['c9', '윤기철', 'C-2026-0298', '이서연', 'on', '7/01', '10/13', 'all'], ['c10', '홍성택', 'C-2026-0425', '정다은', 'wait', '—', '—', 'part'],
    ['c11', '남순이', 'C-2026-0428', '박지훈', 'wait', '—', '—', 'none'], ['c12', '한옥분', 'C-2026-0251', '이서연', 'off', '—', '—', 'no'],
    ['c13', '노재만', 'C-2026-0431', '한승호', 'off', '—', '—', 'none']
  ];
  const ST = { on: ['연결됨', 'chip c-ok'], wait: ['초대 대기', 'chip c-sand'], off: ['미연결', 'chip c-check'] };
  const FAM = { all: ['가족 연결 · 공유 동의', 'chip c-ok'], part: ['가족 연결 · 일부 동의', 'chip c-sand'], no: ['가족 연결 · 미동의', 'chip c-check'], none: ['가족 미연결', 'chip c-normal'] };
  const conn = C.filter((c) => s.cf === 'all' || c[4] === s.cf).map((c) => { const sent = !!s.inv[c[0]];
    return { sr: c[1], cid: c[2], who: c[3], st: ST[c[4]][0], stCls: ST[c[4]][1], since: c[5], last: c[6], fam: FAM[c[7]][0], famCls: FAM[c[7]][1], canInvite: c[4] !== 'on',
      invLabel: sent ? '초대 코드 보냄 ✓' : (c[4] === 'wait' ? '초대 코드 다시 보내기' : '초대 코드 보내기'), invite: () => this.setState({ inv: { ...s.inv, [c[0]]: !sent } }) }; });
  const S = [
    ['s1', '윤기철', 'C-2026-0298', '이서연', '10/13', 6, 'done', '10/14 통화 · 휴대폰 글씨가 작아 앱을 잘 안 보심 → 큰 글씨 설정 · 음성 답변 안내, 주 3회 안부 전화 병행'],
    ['s2', '서영자', 'C-2026-0377', '오유진', '10/14', 5, 'open', '담당 상담사 비활성 · 재배정 후 즉시 안부 전화, 연락 안 되면 생활지원사 방문 확인 필요'],
    ['s3', '배종호', 'C-2026-0384', '박지훈', '10/15', 4, 'try', '10/17 부재중 · 가족(딸)에게 문자 남김 · 방문 확인 요청 예정'],
    ['s4', '문병철', 'C-2026-0359', '한승호', '10/16', 3, 'open', '—'],
    ['s5', '송미자', 'C-2026-0347', '정다은', '10/17', 2, 'done', '10/19 통화 · 입원 중이셨음(가족 확인) · 퇴원 후 앱 다시 사용 안내']
  ];
  const isDone = (r) => (s.done[r[0]] === undefined ? r[6] === 'done' : s.done[r[0]]);
  const silentAll = S.map((r) => { const d = isDone(r);
    return { sr: r[1], cid: r[2], who: r[3], last: r[4], days: r[5], dCls: r[5] >= 4 ? 'warn' : '', memo: r[7], open: !d,
      st: d ? '안부 확인 완료' : (r[6] === 'try' ? '연락 시도 1회' : '미처리'), stCls: d ? 'chip c-ok' : (r[6] === 'try' ? 'chip c-sand' : 'chip c-urgent'),
      btnLabel: d ? '미처리로 되돌리기' : '안부 확인 완료로 표시', btnCls: d ? 'btn-s' : 'btn-p', toggle: () => this.setState({ done: { ...s.done, [r[0]]: !d } }) }; });
  const openCnt = silentAll.filter((r) => r.open).length;
  const silent = s.sf === 'open' ? silentAll.filter((r) => r.open) : silentAll;
  return { conn, silent, silentCnt: S.length, silentOpen: openCnt,
    cFilters: segOf('cf', s.cf, [['all', '전체'], ['on', '연결됨'], ['wait', '초대 대기'], ['off', '미연결']]),
    sFilters: segOf('sf', s.sf, [['all', `전체 ${S.length}`], ['open', `미처리 ${openCnt}`]]) };
}
}
