// Login 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/Login.jsx)이 이어받아 데이터만 바꾼다.
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
componentDidMount() {
  this._thmT = setInterval(() => { if (this.themeRead() !== this._thmShown) this.setState({ __thmTick: Date.now() }); }, 300);
  if (this.componentDidMountBase) this.componentDidMountBase();
}
componentWillUnmount() {
  clearInterval(this._thmT);
  if (this.componentWillUnmountBase) this.componentWillUnmountBase();
}
renderVals() {
  const v = this.renderValsBase() || {};
  const dark = this.themeRead(); this._thmShown = dark;
  return Object.assign({}, v, { themeCls: dark ? 'thm-root dark' : 'thm-root', themePressed: dark ? 'true' : 'false', themeLabel: dark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggleTheme: () => { this.themeWrite(!this.themeRead()); this.setState({ __thmTick: Date.now() }); } });
}

suOpen() { clearInterval(this._cdT); this.setState({ su: 1, stage: 0, suName: '', suBirth: '', suSex: '', suPhone: '', suEmail: '', suCode: '', suSent: 0, suSentAt: 0, suName2: '', suPw: '', suPw2: '', suPwV: false, suPw2V: false }); }
suKey(k) { return (e) => { if (!e || e.key !== 'Enter') return; if (e.preventDefault) e.preventDefault(); const raw = String((e.target && e.target.value) || ''); const composing = e.isComposing || e.keyCode === 229;
  const run = () => { const v = k === 'suPhone' ? this.suFmtPhone(raw) : k === 'suBirth' ? raw.replace(/[^0-9]/g, '').slice(0, 8) : k === 'suCode' ? raw.replace(/[^0-9]/g, '').slice(0, 6) : raw; if (k === 'suEmail' && (this.state.stage || 0) === 5) { this.suVals().__go(); return; } this.setState({ [k]: v }); this.suVals({ [k]: v }).__go(); };
  if (composing) setTimeout(run, 30); else run(); }; }
suFmtPhone(v) { const d = String(v || '').replace(/[^0-9]/g, '').slice(0, 11); if (d.length < 4) return d; if (d.length < 8) return d.slice(0, 3) + '-' + d.slice(3); return d.slice(0, 3) + '-' + d.slice(3, d.length - 4) + '-' + d.slice(-4); }
suTick(on) { clearInterval(this._cdT); if (on) this._cdT = setInterval(() => this.setState({ __cd: Date.now() }), 1000); }
componentWillUnmountBase() { clearInterval(this._cdT); }
suVals(ov) {
  const st = Object.assign({}, this.state || {}, ov || {}); const su = st.su || 0; const stage = st.stage || 0;
  const name = st.suName || '', birth = st.suBirth || '', sex = st.suSex || '', phone = st.suPhone || '', email = st.suEmail || '', code = st.suCode || '';
  const bOk = (() => { if (!/^\d{8}$/.test(birth)) return false; const y = +birth.slice(0, 4), m = +birth.slice(4, 6), d = +birth.slice(6, 8); const dt = new Date(y, m - 1, d); return y >= 1900 && y <= 2026 && dt.getMonth() === m - 1 && dt.getDate() === d; })();
  const eOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const pOk = /^01[016789]\d{7,8}$/.test(phone.replace(/[^0-9]/g, ''));
  const left = st.suSentAt ? Math.max(0, 300 - Math.floor((Date.now() - st.suSentAt) / 1000)) : 300;
  const cOk = code.length === 6 && left > 0;
  const titles = ['이름을 입력하세요.', '생년월일 8자리를 입력하세요.', '성별을 선택하세요.', '휴대폰 번호를 입력하세요.', '이메일을 입력하세요.', '이메일로 받은 인증번호 6자리를 입력하세요.'];
  const can = [name.trim().length > 0, bOk, !!sex, pOk, false, cOk][stage];
  const cls = (k) => (stage === k ? 'on' : '');
  const send = () => { this.suTick(true); this.setState({ stage: 5, suCode: '', suSent: (this.state.suSent || 0) + 1, suSentAt: Date.now() }); };
  const next = () => { const s2 = this.state.stage || 0; if (s2 === 0) this.setState({ stage: 1 }); else if (s2 === 1) this.setState({ stage: 2 }); else if (s2 === 3) this.setState({ stage: 4 }); else if (s2 === 4) send(); else if (s2 === 5) { if ((this.state.suCode || '') !== '123456') { this.setState({ suWrong: true }); return; } this.suTick(false); this.setState({ su: 2, suName2: this.state.suName || '' }); } };
  const pw = st.suPw || '', pw2 = st.suPw2 || '', name2 = st.suName2 || '';
  const pwBad = pw2.length > 0 && pw !== pw2;
  const pwOk = pw.length >= 8 && pw.length <= 16 && /[A-Za-z]/.test(pw) && /[0-9]/.test(pw) && /[!"#$%&'()*+,\-./:;<=>?@\[\\₩\]^_`{|}~]/.test(pw) && /^[A-Za-z0-9!"#$%&'()*+,\-./:;<=>?@\[\\₩\]^_`{|}~]+$/.test(pw);
  const doneOk = name2.trim().length > 0 && pwOk && pw2.length > 0 && !pwBad;
  const mmss = String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
  return {
    __go: () => { if (su === 2) { if (doneOk) this.setState({ su: 3 }); return; } if (su !== 1) return; if (stage === 4) { if (eOk) send(); return; } if (!can) return;
      if (stage === 5) { if (code !== '123456') { this.setState({ suWrong: true }); return; } this.suTick(false); this.setState({ su: 2, suName2: name }); return; } next(); },
    suKeyName: this.suKey('suName'), suKeyBirth: this.suKey('suBirth'), suKeyEmail: this.suKey('suEmail'), suKeyCode: this.suKey('suCode'), suKeyName2: this.suKey('suName2'), suKeyPw: this.suKey('suPw'), suKeyPw2: this.suKey('suPw2'),
    suStep1: su === 1, suStep2: su === 2, suStep3: su === 3, suTitle: titles[stage],
    suShowName: stage === 0, suShowBirth: stage === 1, suShowSex: stage === 2, suShowPhone: stage === 3, suShowEmail: stage >= 4, suShowCode: stage >= 5,
    suNameCls: cls(0), suBirthCls: cls(1), suSexCls: cls(2), suPhoneCls: cls(3), suEmailCls: stage === 4 ? 'on' : (stage === 5 ? 'lock' : ''), suEmailLock: stage === 5,
    suName: name, suBirth: birth, suEmail: email, suCode: code, suBirthBad: birth.length === 8 && !bOk,
    suSetName: (e) => this.setState({ suName: e.target.value }), suSetBirth: (e) => this.setState({ suBirth: String(e.target.value).replace(/[^0-9]/g, '').slice(0, 8) }),
    suPhone: phone, suSetPhone: (e) => this.setState({ suPhone: this.suFmtPhone(e.target.value) }), suPhoneBad: phone.length > 0 && !pOk && phone.replace(/[^0-9]/g, '').length >= 10, suKeyPhone: this.suKey('suPhone'),
    suSetEmail: (e) => { if ((this.state.stage || 0) !== 5) this.setState({ suEmail: e.target.value }); }, suSetCode: (e) => this.setState({ suCode: String(e.target.value).replace(/[^0-9]/g, '').slice(0, 6) }),
    suSexOpts: [['m', '남성'], ['f', '여성']].map(([v, l]) => ({ label: l, on: sex === v ? 'true' : 'false', cls: sex === v ? 'on' : '', pick: () => this.setState({ suSex: v, stage: Math.max(this.state.stage || 0, 3) }) })),
    suTimer: mmss, suTimerCls: left > 0 ? 'sf-time' : 'sf-time out', suSentNote: left > 0 ? ((st.suSent || 1) > 1 ? '인증번호를 다시 보냈어요' : email + ' 로 보냈어요') : '인증 시간이 지났어요. 다시 보내 주세요.',
    suResend: send, suSendOn: stage === 4 && eOk, suSendOff: !(stage === 4 && eOk), suSendLabel: stage === 5 ? '발송 완료' : '인증번호 받기', suPwRuleBad: pw.length > 0 && !pwOk,
    suPwType: st.suPwV ? 'text' : 'password', suPwShow: !!st.suPwV, suPwShowN: !st.suPwV, suPwShowP: st.suPwV ? 'true' : 'false', suPwEyeLab: st.suPwV ? '비밀번호 숨기기' : '비밀번호 보기', suPwToggle: () => this.setState({ suPwV: !this.state.suPwV }),
    suPw2Type: st.suPw2V ? 'text' : 'password', suPw2Show: !!st.suPw2V, suPw2ShowN: !st.suPw2V, suPw2ShowP: st.suPw2V ? 'true' : 'false', suPw2EyeLab: st.suPw2V ? '비밀번호 숨기기' : '비밀번호 보기', suPw2Toggle: () => this.setState({ suPw2V: !this.state.suPw2V }), suNextOn: !!can && stage !== 2, suNextOff: !can || stage === 2, suNext: next,
    suName2: name2, suPw: pw, suPw2: pw2, suPwBad: pwBad, suDoneOn: doneOk, suDoneOff: !doneOk,
    suSetName2: (e) => this.setState({ suName2: e.target.value }), suSetPw: (e) => this.setState({ suPw: e.target.value }), suSetPw2: (e) => this.setState({ suPw2: e.target.value }),
    suWrong: !!st.suWrong, suWrongOk: () => this.setState({ suWrong: false, suCode: '' }), suDone: () => this.setState({ su: 3 }), suClose: () => { this.suTick(false); this.setState({ su: 0 }); } };
}
renderValsBase() {
  const st = this.state || {};
  const role = st.role || 'staff';
  const email = st.email === undefined ? 'lee.seoyeon@ondam-center.kr' : st.email;
  const code = st.code || '';
  const roles = [['staff', '상담사 로그인'], ['admin', '관리자 로그인']].map(([v, l]) => ({ label: l, cls: role === v ? 'on' : '', pressed: role === v ? 'true' : 'false', pick: () => this.setState({ role: v }) }));
  return { roles, loginHref: role === 'admin' ? '#/Soon?name=AdminHome' : '#/Home', email, code,
    setEmail: (e) => this.setState({ email: e.target.value }), setCode: (e) => this.setState({ code: String(e.target.value).replace(/[^0-9]/g, '').slice(0, 6) }),
    joined: !!st.joined, openCode: () => this.suOpen(), ...this.suVals() };
}
}
