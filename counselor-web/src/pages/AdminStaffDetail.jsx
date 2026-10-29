// 관리자 · 상담사 상세(계정 · 접속 정보 · 알림 설정)
// 원본: 다솔 님 10/21 디자인 counselor-design/screens/AdminStaffDetail.dc.html (origin/frontend261021)
//
// 주소: #/AdminStaffDetail?user=<계정 ID>(계정 목록의 이름 · '상세'). 디자인은 브라우저 저장소로 넘기지만 앱은 주소 쿼리로 받는다.
// 서버 연결: useAdminAccounts(계정 목록에서 이 계정을 찾음 — 한 계정만 받는 API 는 없다, 요청 6종). 값은 src/data/screens/adminStaffDetail.ts.
// 비활성화 · 비밀번호 초기화 · 휴면 해제 · 강제 로그아웃은 한 번 더 묻고, 임시 비밀번호는 이 화면 상태에만 한 번 보인다.
// 비밀번호 마지막 변경일 · 소속 기관 · 접속 IP · 알림 설정은 서버에 없어 '—' · 준비 중이고, OTP 줄은 두지 않는다(OTP 없음, 팀 결정 D1).
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { needsLogin } from '../data/screens/common';
import { readStaffId } from '../data/screens/admin';
import { INITIAL_STAFF_DETAIL_UI, adminStaffDetailValues } from '../data/screens/adminStaffDetail';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_STAFF_DETAIL_UI;
  }
  renderVals() {
    return adminStaffDetailValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function AdminStaffDetail(props) {
  const session = useAuthSession();
  const staffId = readStaffId(useSearchParams()[0]);
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin).
  const accounts = useAdminAccounts(session);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, staffId, accounts });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminStaffDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '900px',
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
        <AdminSidebar active="AdminAccounts" session={session} />
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
          {!v.found ? (
            <>
              <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
                <A className="btn btn-sm btn-s" to={v.listHref}>
                  ← 목록
                </A>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>상담사 상세</h1>
              </header>
              <Notice value={v.notice} />
            </>
          ) : (
            <>
              <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
                <A className="btn btn-sm btn-s" to={v.listHref}>
                  ← 목록
                </A>
                <span className="av" style={{ width: '52px', height: '52px', fontSize: '20px' }}>
                  {v.ini}
                </span>
                <div style={{ flex: '1 1 320px' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                    <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>
                      {v.name} <span className="note">{v.self}</span>
                    </h1>
                    {v.chips.map((c) => (
                      <span key={c.label} className={c.cls}>
                        {c.label}
                      </span>
                    ))}
                  </div>
                  <div className="note">
                    {v.sub}
                    {v.lockedUntil ? ` · ${v.lockedUntil}` : ''}
                  </div>
                </div>
                {v.toggle ? (
                  <button type="button" className="btn btn-s" disabled={v.toggle.disabled} onClick={v.toggle.onClick}>
                    {v.toggle.label}
                  </button>
                ) : null}
              </header>

              {v.asking ? (
                <section
                  className="card"
                  role="alertdialog"
                  aria-label={v.asking.label}
                  style={{
                    padding: '16px 22px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '8px 12px',
                  }}
                >
                  <span style={{ flex: '1 1 320px' }}>{v.asking.text}</span>
                  <button type="button" className="btn btn-p btn-sm" disabled={v.busy} onClick={v.asking.confirm}>
                    {v.asking.label}
                  </button>
                  <button type="button" className="btn btn-s btn-sm" onClick={v.asking.cancel}>
                    취소
                  </button>
                </section>
              ) : null}

              {v.issued ? (
                <section
                  className="card"
                  aria-label="임시 비밀번호"
                  role="status"
                  style={{
                    padding: '20px 24px',
                    border: '1px solid #C2A36B',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <h2 className="h2">임시 비밀번호 · {v.issued.reason}</h2>
                  <span>{v.issued.who}</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                    <code style={{ fontSize: '18px', fontWeight: '700', letterSpacing: '1px', userSelect: 'all' }}>
                      {v.issued.password}
                    </code>
                    <button type="button" className="btn btn-s btn-sm" onClick={v.issued.copy}>
                      {v.issued.copied ? '복사됨' : '복사'}
                    </button>
                  </div>
                  <span className="note">
                    사용 기한 {v.issued.expiresAt}. 이 안내를 닫으면 다시 볼 수 없습니다. 본인에게만 전해 주세요.
                  </span>
                  <div>
                    <button type="button" className="btn btn-p btn-sm" onClick={v.issued.close}>
                      전달했습니다 · 닫기
                    </button>
                  </div>
                </section>
              ) : null}

              {v.done ? (
                <p className="note" role="status" style={{ margin: '-8px 0 0', color: '#2B2A26' }}>
                  {v.done}
                </p>
              ) : null}
              {v.error ? (
                <p className="acc" role="alert" style={{ margin: '0', fontSize: '13px' }}>
                  {v.error}
                </p>
              ) : null}
              {v.busyText ? (
                <p className="note" role="status" style={{ margin: '0' }}>
                  {v.busyText}
                </p>
              ) : null}

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
                  gap: '18px',
                  alignItems: 'start',
                }}
              >
                <section className="card" aria-label="계정" style={{ overflow: 'hidden' }}>
                  <div className="hd">
                    <h2 className="h2">계정</h2>
                    <span className="note">계정 정보 · 상태</span>
                  </div>
                  <div style={{ padding: '6px 22px 10px' }}>
                    <div className="row">
                      <span className="lab">상담사 이름</span>
                      <b style={{ fontWeight: '500' }}>{v.name}</b>
                    </div>
                    <div className="row">
                      <span className="lab">계정 (로그인 이메일)</span>
                      <b style={{ fontWeight: '500' }}>{v.email}</b>
                    </div>
                    <div className="row">
                      <span className="lab">역할</span>
                      <b style={{ fontWeight: '500' }}>{v.role}</b>
                    </div>
                    <div className="row">
                      <span className="lab">비밀번호</span>
                      <span style={{ flex: '1' }} className="sub">
                        {v.pwText}
                        {v.resetNote ? <span className="note" style={{ display: 'block' }}>{v.resetNote}</span> : null}
                      </span>
                      {v.reset ? (
                        <button type="button" className="btn btn-sm btn-s" disabled={v.busy} onClick={v.reset.onClick}>
                          {v.reset.label}
                        </button>
                      ) : null}
                    </div>
                    <div className="row">
                      <span className="lab">소속 기관</span>
                      <b style={{ fontWeight: '500' }} title={v.notReady}>
                        {v.org}
                      </b>
                    </div>
                    <div className="row" style={{ borderBottom: '0' }}>
                      <span className="lab">계정 요청</span>
                      <span style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', flex: '1' }}>
                        {v.stateActions.map((a) => (
                          <button
                            key={a.key}
                            type="button"
                            className="btn btn-sm btn-s"
                            disabled={v.busy}
                            onClick={a.onClick}
                          >
                            {a.label}
                          </button>
                        ))}
                        {v.stateNote ? <span className="note">{v.stateNote}</span> : null}
                      </span>
                    </div>
                  </div>
                </section>

                <section className="card" aria-label="접속 정보" style={{ overflow: 'hidden' }}>
                  <div className="hd">
                    <h2 className="h2">접속 정보</h2>
                    <A to={v.securityHref} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                      전체 접속 기록
                    </A>
                  </div>
                  <div style={{ padding: '6px 22px 10px' }}>
                    <div className="row">
                      <span className="lab">계정 생성일</span>
                      <b style={{ fontWeight: '500' }}>{v.created}</b>
                    </div>
                    <div className="row">
                      <span className="lab">최근 접속</span>
                      <b style={{ fontWeight: '500' }}>{v.last}</b>
                    </div>
                    <div className="row" style={{ borderBottom: '0' }}>
                      <span className="lab">접속 IP</span>
                      <b style={{ fontWeight: '500' }} title={v.notReady}>
                        {v.ip}
                      </b>
                    </div>
                  </div>
                </section>

                <section className="card" aria-label="알림 설정" style={{ overflow: 'hidden' }}>
                  <div className="hd">
                    <h2 className="h2">알림 설정</h2>
                    <span className="note">상담사가 설정한 값</span>
                  </div>
                  <div style={{ padding: '6px 22px 10px' }}>
                    <div className="row" style={{ borderBottom: '0' }}>
                      <span className="sub">{v.notReady} · 알림 설정을 저장하는 서버 기능이 없습니다.</span>
                    </div>
                  </div>
                </section>
              </div>
              {v.caseCountError ? (
                <p className="note" style={{ margin: '0' }}>
                  {v.caseCountError} 담당 사례는 — 로 둡니다.
                </p>
              ) : null}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
