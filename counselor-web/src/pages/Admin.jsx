// 관리자 대시보드
// 원본: 다솔 님 디자인 counselor-web-design/Admin.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(useAuthSession 의 isAdmin).
// 관리자 데이터 훅(useAdminDashboard 등, README '서버 연결')은 아직 이 화면에 붙이지 않았다.
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { needsLogin, notice, screenNotice, sidebarValues } from '../data/screens/common';
import './Admin.css';

class Logic extends DCLogic {
  renderVals() {
    return {};
  }
}

export default function Admin(props) {
  const session = useAuthSession();
  const theme = useTheme();
  const v = useDC(Logic, props);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) {
    const blocked =
      screenNotice({ session }) ??
      notice('관리자 계정만 볼 수 있는 화면입니다.', { href: '/Main', hrefLabel: '홈으로' });
    return (
      <div className="pg-Admin">
        <div
          className={theme.cls}
          style={{
            minHeight: '100vh',
            background: '#F2F2F0',
            color: '#2B2A26',
            fontFamily: "'IBM Plex Sans KR', sans-serif",
            fontSize: '14px',
            lineHeight: '1.6',
            padding: '48px 36px',
          }}
        >
          <Notice value={blocked} />
        </div>
      </div>
    );
  }
  const me = sidebarValues(session);
  return (
    <div className="pg-Admin">
      <div
        className={theme.cls}
        style={{
          minHeight: '1000px',
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
        <aside className="side" aria-label="관리자 메뉴">
          <A to="/Admin" style={{ minHeight: 'auto', padding: '2px 6px 16px', color: '#2B2A26' }}>
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="on" to="/Admin">
            관리자 대시보드
          </A>
          <div className="grp">데이터 · 업무 관리</div>
          <A to="/Admin">전체 사례 현황</A>
          <A to="/Admin">
            업무 처리 현황<span className="badge">3</span>
          </A>
          <A to="/Admin">문서 승인 관리</A>
          <div className="grp">권한 · 보안</div>
          <A to="/Admin">상담사 계정 관리</A>
          <A to="/Admin">접속 기록</A>
          <A to="/Admin">
            보안 이벤트<span className="badge">1</span>
          </A>
          <A to="/Admin">통계 리포트</A>
          <A to="/Login" style={{ marginTop: 'auto', color: '#7A776F' }} onClick={me.logout}>
            로그아웃
          </A>
        </aside>

        <div style={{ flex: '999 1 640px', minWidth: '0', display: 'flex', flexDirection: 'column' }}>
          <header className="top">
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <span className="av">{me.meInitial}</span>
              {me.meName}
            </span>
            <ThemeToggle />
          </header>

          <main
            style={{
              padding: '26px 36px 56px',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              maxWidth: '1240px',
              width: '100%',
            }}
          >
            <div>
              <h1 style={{ margin: '0', fontSize: '24px', fontWeight: '700', color: '#2B2A26' }}>관리자 대시보드</h1>
              <p className="sub" style={{ margin: '2px 0 0' }}>
                10월 7일 (수)
              </p>
            </div>

            <section
              className="card"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                overflow: 'hidden',
              }}
            >
              <div className="stat" style={{ borderRight: '1px solid #EAE7DF' }}>
                <span className="sub">전체 관리 사례</span>
                <b>10</b>
              </div>
              <div className="stat" style={{ borderRight: '1px solid #EAE7DF' }}>
                <span className="sub">처리 대기 업무</span>
                <b>8</b>
              </div>
              <div className="stat" style={{ borderRight: '1px solid #EAE7DF' }}>
                <span className="sub">활성 상담사</span>
                <b>
                  4
                  <span className="sub" style={{ fontSize: '14px', fontWeight: '500' }}>
                    {' '}
                    / 5
                  </span>
                </b>
              </div>
              <div className="stat">
                <span className="sub">미배정 사례</span>
                <b>3</b>
              </div>
            </section>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px', alignItems: 'flex-start' }}>
              <section
                className="card"
                aria-label="즉시 확인 필요"
                style={{ flex: '3 1 440px', minWidth: '0', padding: '22px 24px' }}
              >
                <h2 className="h2" style={{ marginBottom: '4px' }}>
                  즉시 확인 필요
                </h2>
                <div className="row">
                  <span className="chip c-urgent">보안</span>
                  <span style={{ flex: '1' }}>외부 IP 반복 로그인 실패 감지</span>
                  <A to="/Admin" style={{ fontSize: '13px' }}>
                    바로가기
                  </A>
                </div>
                <div className="row">
                  <span className="chip c-check">사례</span>
                  <span style={{ flex: '1' }}>근거 확인 필요 사례 4건</span>
                  <A to="/Admin" style={{ fontSize: '13px' }}>
                    바로가기
                  </A>
                </div>
                <div className="row">
                  <span className="chip c-ing">승인</span>
                  <span style={{ flex: '1' }}>문서 승인 대기 2건</span>
                  <A to="/Admin" style={{ fontSize: '13px' }}>
                    바로가기
                  </A>
                </div>
                <div className="row" style={{ borderBottom: '0' }}>
                  <span className="chip c-type">배정</span>
                  <span style={{ flex: '1' }}>미배정 신규 사례 3건</span>
                  <A to="/Admin" style={{ fontSize: '13px' }}>
                    바로가기
                  </A>
                </div>
              </section>
              <section
                className="card"
                aria-label="최근 접속 활동"
                style={{ flex: '2 1 300px', minWidth: '0', padding: '22px 24px' }}
              >
                <h2 className="h2" style={{ marginBottom: '4px' }}>
                  최근 접속 활동
                </h2>
                <div className="row">
                  <span style={{ flex: '1' }}>
                    <b style={{ fontWeight: '500' }}>이서연</b>
                    <span className="note" style={{ display: 'block' }}>
                      10-07 09:14 · 192.168.1.12
                    </span>
                  </span>
                  <span className="chip c-ok">성공</span>
                </div>
                <div className="row">
                  <span style={{ flex: '1' }}>
                    <b style={{ fontWeight: '500' }}>정다은</b>
                    <span className="note" style={{ display: 'block' }}>
                      10-07 09:01 · 192.168.1.8
                    </span>
                  </span>
                  <span className="chip c-ok">성공</span>
                </div>
                <div className="row">
                  <span style={{ flex: '1' }}>
                    <b style={{ fontWeight: '700' }}>unknown</b>
                    <span className="note" style={{ display: 'block' }}>
                      10-07 08:47 · 203.0.113.44
                    </span>
                  </span>
                  <span className="chip c-check">실패</span>
                </div>
                <div className="row" style={{ borderBottom: '0' }}>
                  <span style={{ flex: '1' }}>
                    <b style={{ fontWeight: '700' }}>unknown</b>
                    <span className="note" style={{ display: 'block' }}>
                      10-07 08:46 · 203.0.113.44
                    </span>
                  </span>
                  <span className="chip c-check">실패</span>
                </div>
              </section>
            </div>

            <section className="card" aria-label="업무 처리 현황" style={{ overflowX: 'auto' }}>
              <div
                style={{
                  padding: '20px 24px 8px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px 12px',
                }}
              >
                <h2 className="h2">업무 처리 현황</h2>
                <div
                  role="tablist"
                  aria-label="업무 종류"
                  style={{ marginLeft: 'auto', display: 'flex', flexWrap: 'wrap', gap: '6px' }}
                >
                  <button type="button" role="tab" aria-selected="true" className="pill on">
                    STT 처리 대기 3
                  </button>
                  <button type="button" role="tab" aria-selected="false" className="pill">
                    상담사 검토 대기 2
                  </button>
                  <button type="button" role="tab" aria-selected="false" className="pill">
                    문서 승인 대기 2
                  </button>
                </div>
              </div>
              <table className="tbl" style={{ marginBottom: '8px' }}>
                <thead>
                  <tr>
                    <th scope="col">사례 ID</th>
                    <th scope="col">아동명</th>
                    <th scope="col">담당 상담사</th>
                    <th scope="col">제출 시각</th>
                    <th scope="col">대기시간</th>
                    <th scope="col">처리 단계</th>
                    <th scope="col">작업</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="note">C-2026-0451</td>
                    <td>황OO</td>
                    <td>한승호</td>
                    <td>10-06 16:44</td>
                    <td style={{ fontWeight: '700' }}>17시간 52분</td>
                    <td>
                      <span className="chip c-check">오류</span>
                    </td>
                    <td>
                      <A to="/Admin">재처리 요청</A>
                    </td>
                  </tr>
                  <tr>
                    <td className="note">C-2026-0395</td>
                    <td>최OO</td>
                    <td>박지훈</td>
                    <td>10-07 05:20</td>
                    <td>4시간 38분</td>
                    <td>
                      <span className="chip c-normal">처리 대기</span>
                    </td>
                    <td>
                      <A to="/Admin">상세 보기</A>
                    </td>
                  </tr>
                  <tr>
                    <td className="note">C-2026-0412</td>
                    <td>김도현</td>
                    <td>이서연</td>
                    <td>10-07 07:50</td>
                    <td>2시간 15분</td>
                    <td>
                      <span className="chip c-ing">처리 중</span>
                    </td>
                    <td>
                      <A to="/Admin">상세 보기</A>
                    </td>
                  </tr>
                </tbody>
              </table>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}
