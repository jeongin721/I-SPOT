// 로그인
// 원본: I-SPOT 디자인 캔버스 보드 Login.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './Login.css';

class Logic extends DCLogic {
  renderVals() {
    return {};
  }
}

export default function Login(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-Login">
      <div
        style={{
          minHeight: '720px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '48px 24px',
        }}
      >
        <form
          style={{
            width: '100%',
            maxWidth: '400px',
            background: '#FFFFFF',
            border: '1px solid #E7E0CE',
            borderRadius: '20px',
            padding: '36px 34px',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span className="mk">IS</span>
            <b style={{ fontSize: '20px' }}>I-SPOT</b>
          </div>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span className="lb">기관 ID</span>
            <input className="inp" type="text" defaultValue="lee.seoyeon" />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span className="lb">비밀번호</span>
            <input className="inp" type="password" defaultValue="password" />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span className="lb">OTP 인증번호</span>
            <input className="inp" type="text" inputMode="numeric" placeholder="6자리" />
          </label>
          <A className="btn btn-p" to="/Main" style={{ width: '100%', marginTop: '4px' }}>
            로그인
          </A>
        </form>
      </div>
    </div>
  );
}
