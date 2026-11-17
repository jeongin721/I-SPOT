// LoginTablet 디자인 화면 로직(예시 데이터 그대로) — tools/dc2jsx.py 가 만든 파일. 화면 파일(src/pages/LoginTablet.jsx)이 이어받아 데이터만 바꾼다.
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

renderValsBase() {
  const st = this.state || {};
  const role = st.role || 'staff';
  const email = st.email === undefined ? 'lee.seoyeon@ondam-center.kr' : st.email;
  const code = st.code || '';
  const roles = [['staff', '상담사 로그인'], ['admin', '관리자 로그인']].map(([v, l]) => ({ label: l, cls: role === v ? 'on' : '', pressed: role === v ? 'true' : 'false', pick: () => this.setState({ role: v }) }));
  return { roles, loginHref: role === 'admin' ? '#/AdminHome' : '#/Home', email, code,
    setEmail: (e) => this.setState({ email: e.target.value }), setCode: (e) => this.setState({ code: String(e.target.value).replace(/[^0-9]/g, '').slice(0, 6) }),
    codeOpen: !!st.open, openCode: () => this.setState({ open: true, code: '', sent: 1 }), closeCode: () => this.setState({ open: false, code: '' }),
    resend: () => this.setState({ sent: (st.sent || 1) + 1, code: '' }), sentNote: (st.sent || 1) > 1 ? '인증번호를 다시 보냈어요 · 유효 시간 5분' : '유효 시간 5분',
    codeOk: code.length === 6, codeWait: code.length !== 6, joined: !!st.joined, confirmCode: () => this.setState({ open: false, code: '', joined: true }) };
}
}
