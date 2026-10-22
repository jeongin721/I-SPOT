// 관리자 · 상담사 계정 관리(만들기 · 목록 → 상세)
// 원본: 다솔 님 10/21 디자인 counselor-design/screens/AdminAccounts.dc.html (origin/frontend261021)
//
// 서버 연결: useAdminAccounts(계정 목록 · 담당 사례 수 · 계정 만들기). 화면에 쓸 값은 src/data/screens/adminAccounts.ts.
// 만들면 임시 비밀번호를 한 번만 보이고 '닫기' 로 버린다. 이름을 누르면 상담사 상세(#/AdminStaffDetail?user=<계정 ID>)로 가고,
// 비밀번호 초기화 · 잠금 해제 · 휴면 해제 · 비활성화 · 강제 로그아웃은 그 화면에서 한다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { needsLogin } from '../data/screens/common';
import { INITIAL_ACCOUNTS_UI, adminAccountsValues } from '../data/screens/adminAccounts';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_ACCOUNTS_UI;
  }
  renderVals() {
    return adminAccountsValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function AdminAccounts(props) {
  const session = useAuthSession();
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin).
  const accounts = useAdminAccounts(session);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, accounts });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminAccounts">
      <div
        className={theme.cls}
        style={{
          minHeight: '1100px',
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}>
            <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700', flex: '1 1 260px' }}>상담사 계정 관리</h1>
            <button type="button" className={v.formBtnCls} aria-expanded={v.formOpen} onClick={v.toggleForm}>
              {v.formBtnLabel}
            </button>
          </header>

          {v.formOpen ? (
            <form
              className="card"
              aria-label="계정 생성"
              onSubmit={v.create}
              noValidate
              style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}
            >
              <h2 className="h2">새 계정 만들기</h2>
              <div
                style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
              >
                <label className="fl">
                  <span className="lb">이메일(로그인 ID)</span>
                  <input
                    className="inp"
                    type="email"
                    autoComplete="off"
                    placeholder="예: name@example.org"
                    {...v.email}
                  />
                </label>
                <label className="fl">
                  <span className="lb">이름</span>
                  <input className="inp" type="text" autoComplete="off" placeholder="예: 홍길동" {...v.name} />
                </label>
                <label className="fl">
                  <span className="lb">역할</span>
                  <select className="inp" {...v.role}>
                    <option value="COUNSELOR">상담원</option>
                    <option value="ADMIN">관리자</option>
                  </select>
                </label>
              </div>
              <p className="note" style={{ margin: '0' }}>
                만들면 임시 비밀번호가 한 번만 보입니다. 첫 로그인 때 새 비밀번호로 바꾸게 됩니다.
              </p>
              {v.actionError ? (
                <p className="acc" role="alert" style={{ margin: '0', fontSize: '13px' }}>
                  {v.actionError}
                </p>
              ) : null}
              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-s" onClick={v.toggleForm}>
                  취소
                </button>
                <button type="submit" className="btn btn-p" disabled={v.busy}>
                  {v.createLabel}
                </button>
              </div>
            </form>
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
            <p className="note" role="status" style={{ margin: '-6px 0 0', color: '#2B2A26' }}>
              {v.done}
            </p>
          ) : null}
          {v.actionError && !v.formOpen ? (
            <p className="acc" role="alert" style={{ margin: '0', fontSize: '13px' }}>
              {v.actionError}
            </p>
          ) : null}
          {v.caseCountError ? (
            <p className="note" style={{ margin: '0' }}>
              {v.caseCountError} 담당 사례 칸은 — 로 둡니다.
            </p>
          ) : null}

          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 이메일 검색"
              placeholder="이름 · 이메일 검색"
              style={{ flex: '1 1 240px' }}
              {...v.search}
            />
            <div role="group" aria-label="계정 상태" className="seg">
              {v.filters.map((f) => (
                <button key={f.key} type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                  {f.label}
                </button>
              ))}
            </div>
          </section>

          <section className="card" aria-label="계정 목록" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '880px' }}>
              <thead>
                <tr>
                  <th scope="col">이름</th>
                  <th scope="col">이메일(로그인 ID)</th>
                  <th scope="col">역할</th>
                  <th scope="col">담당 사례</th>
                  <th scope="col">최근 접속</th>
                  <th scope="col">상태</th>
                  <th scope="col">
                    <span style={{ position: 'absolute', left: '-9999px' }}>작업</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {v.phase !== 'rows' ? (
                  <tr>
                    <td colSpan={7} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
                      {v.phase === 'loading' ? '불러오는 중…' : null}
                      {v.phase === 'empty' ? v.emptyText : null}
                      {v.phase === 'error' ? (
                        <span role="alert">
                          {v.errorText}{' '}
                          <button type="button" className="btn btn-s btn-sm" onClick={v.retry}>
                            다시 시도
                          </button>
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ) : null}
                {(v.phase === 'rows' ? v.rows : []).map((r) => (
                  <tr key={r.key} style={{ opacity: r.op }}>
                    <td>
                      <A className="nm" to={r.href}>
                        <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                          {r.ini}
                        </span>
                        <span>
                          {r.name} <span className="note">{r.self}</span>
                        </span>
                      </A>
                    </td>
                    <td className="note">{r.email}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{r.role}</td>
                    <td>{r.cases}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{r.last}</td>
                    <td>
                      <span style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {r.chips.map((c) => (
                          <span key={c.label} className={c.cls}>
                            {c.label}
                          </span>
                        ))}
                      </span>
                      {r.lockedUntil ? <span className="note">{r.lockedUntil}</span> : null}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <A to={r.href}>상세</A>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
}
