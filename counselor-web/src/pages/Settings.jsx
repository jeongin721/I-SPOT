// 설정 · 계정 / 알림 설정
// 원본: 다솔 님 디자인 counselor-web-design/Settings.dc.html (front_new 브랜치)
//
// 서버 연결: 내 정보는 useAuthSession, 비밀번호 변경은 usePasswordChange 가 하고, 화면에 쓸 값은
// src/data/screens/settings.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
//  - 이름 · 이메일 바꾸기, 소속 기관, 마지막 비밀번호 변경일, 알림 설정은 서버에 없어 '—' · 준비 중이다.
//  - 비밀번호는 현재 비밀번호를 넣고 바꾼다. 바꾸면 로그아웃되어 로그인 화면으로 간다.
import { Fragment } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { usePasswordChange } from '../data/usePasswordChange';
import { needsLogin } from '../data/screens/common';
import { INITIAL_SETTINGS_STATE, settingsValues } from '../data/screens/settings';
import { useTheme } from '../theme';
import './Settings.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_SETTINGS_STATE;
  }
  renderVals() {
    return settingsValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function Settings(props) {
  const session = useAuthSession();
  const pwChange = usePasswordChange();
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, pwChange });
  // 로그인하지 않았거나 임시 비밀번호 상태면 로그인 화면(비밀번호 변경 단계)으로 보낸다. 비밀번호를 바꾼 뒤에도 여기로 간다.
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  const off = { opacity: 0.5, cursor: 'not-allowed' };
  return (
    <div className="pg-Settings">
      <div
        className={theme.cls}
        style={{
          minHeight: '800px',
          background: '#E9E7E1',
          color: '#2B2A26',
          fontFamily: "'IBM Plex Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <Sidebar active="Settings" session={session} />
        <main
          style={{
            flex: '999 1 640px',
            minWidth: '0',
            padding: '30px 36px 56px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          <div className="thm-bar">
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <nav aria-label="위치" className="note">
                {v.inSub ? (
                  <>
                    <A to="/Settings" onClick={v.goHome}>
                      설정
                    </A>{' '}
                    › {v.subTitle}
                  </>
                ) : null}
                {v.atHome ? <>설정</> : null}
              </nav>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
            </div>
            {v.inSub ? (
              <>
                <button type="button" className="btn btn-s" onClick={v.goHome}>
                  ← 설정
                </button>
              </>
            ) : null}
          </header>
          <Notice value={v.notice} />

          {v.atHome ? (
            <>
              <section
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                  gap: '18px',
                  maxWidth: '900px',
                }}
              >
                <button type="button" className="pick" onClick={v.goAccount}>
                  <b style={{ fontSize: '20px' }}>계정</b>
                </button>
                <button type="button" className="pick" onClick={v.goNotify}>
                  <b style={{ fontSize: '20px' }}>알림 설정</b>
                </button>
              </section>
            </>
          ) : null}

          {v.isAccount ? (
            <>
              <section className="card" aria-label="계정" style={{ padding: '6px 26px 14px', maxWidth: '900px' }}>
                <div className="row">
                  <span className="lab">이름</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>{v.name}</b>
                  <button type="button" className="btn btn-sm btn-s" disabled title={v.notReady} style={off}>
                    수정
                  </button>
                </div>
                <div className="row">
                  <span className="lab">계정 (연결된 이메일)</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>{v.mail}</b>
                  <button type="button" className="btn btn-sm btn-s" disabled title={v.notReady} style={off}>
                    변경
                  </button>
                </div>
                <div className="row">
                  <span className="lab">역할</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>{v.role}</b>
                </div>
                <div className="row">
                  <span className="lab">비밀번호</span>
                  <span style={{ flex: '1' }} className="sub">
                    {v.pwText}
                  </span>
                  <button type="button" className={`btn btn-sm ${v.pwCls}`} onClick={v.togglePw}>
                    {v.pwLabel}
                  </button>
                </div>
                {v.pwOpen ? (
                  <form
                    onSubmit={v.submitPw}
                    noValidate
                    aria-label="비밀번호 바꾸기"
                    className="row"
                    style={{ flexDirection: 'column', alignItems: 'stretch', maxWidth: '420px' }}
                  >
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lab">현재 비밀번호</span>
                      <input className="edit-in" type="password" autoComplete="current-password" {...v.current} />
                    </label>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lab">새 비밀번호</span>
                      <input className="edit-in" type="password" autoComplete="new-password" {...v.next} />
                    </label>
                    <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span className="lab">새 비밀번호 확인</span>
                      <input className="edit-in" type="password" autoComplete="new-password" {...v.confirm} />
                    </label>
                    <p className="note" style={{ margin: '0' }}>
                      {v.ruleText} 바꾸면 모든 기기에서 로그아웃되고 새 비밀번호로 다시 로그인합니다.
                    </p>
                    {v.pwErrors.length > 0 ? (
                      <ul role="alert" className="acc" style={{ margin: '0', paddingLeft: '18px', fontSize: '13px' }}>
                        {v.pwErrors.map((message) => (
                          <li key={message}>{message}</li>
                        ))}
                      </ul>
                    ) : null}
                    <div>
                      <button type="submit" className="btn btn-sm btn-p" disabled={v.pwBusy}>
                        {v.pwSubmitLabel}
                      </button>
                    </div>
                  </form>
                ) : null}
                <div className="row">
                  <span className="lab">계정 만든 날</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>{v.joined}</b>
                </div>
                <div className="row" style={{ borderBottom: '0' }}>
                  <span className="lab">소속 기관</span>
                  <b style={{ flex: '1', fontWeight: '500' }}>{v.organization}</b>
                </div>
              </section>
              <p className="note" style={{ margin: '0' }}>
                이름 · 이메일 바꾸기와 소속 기관 · 마지막 비밀번호 변경일은 {v.notReady}입니다(서버에 아직 없음). 이름은
                관리자가 바꿀 수 있습니다.
              </p>
            </>
          ) : null}

          {v.isNotify ? (
            <>
              <section className="card" aria-label="알림 설정" style={{ padding: '6px 26px 14px', maxWidth: '900px' }}>
                {(v.toggles || []).map((t, tIndex) => (
                  <Fragment key={tIndex}>
                    <div className="row">
                      <b style={{ flex: '1', fontWeight: '500' }}>{t.label}</b>
                      <button
                        type="button"
                        className="sw"
                        role="switch"
                        aria-checked={t.on}
                        aria-label={t.label}
                        disabled
                        title={v.notReady}
                        style={{ background: t.bg, ...off }}
                      >
                        <span style={{ left: t.x }}></span>
                      </button>
                    </div>
                  </Fragment>
                ))}
                <div className="row" style={{ borderBottom: '0' }}>
                  <b style={{ flex: '1', fontWeight: '500' }}>아이 체크인 묶음 시간</b>
                  <select className="inp" aria-label="묶음 시간" disabled title={v.notReady} style={off} defaultValue="">
                    <option value="">—</option>
                  </select>
                </div>
              </section>
              <p className="note" style={{ margin: '0' }}>
                알림 설정은 {v.notReady}입니다(서버에 아직 없음).
              </p>
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
