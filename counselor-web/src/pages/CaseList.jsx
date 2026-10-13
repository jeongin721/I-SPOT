// 통합 사례 관리 (사례 ID · 이름 · 신고접수일 · 위험도)
// 원본: I-SPOT 디자인 캔버스 보드 CaseList.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 로그인 상태(useAuthSession)와 사례 목록(useCaseList)은 src/data 의 훅이 하고,
// 화면에 쓸 값은 src/data/screens/caseList.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 피그마 화면으로 바꿀 때는 아래 CaseList 함수의 훅과 Logic 을 그대로 두고 JSX 만 갈아 끼우면 된다.
import { Fragment, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseList } from '../data/useCaseList';
import { caseListValues } from '../data/screens/caseList';
import { needsLogin, signedIn } from '../data/screens/common';
import './CaseList.css';

class Logic extends DCLogic {
  renderVals() {
    return caseListValues(this.props);
  }
}

export default function CaseList(props) {
  const session = useAuthSession();
  const [search, setSearch] = useState('');
  const list = useCaseList({ search, enabled: session.status === 'signedIn' });
  const v = useDC(Logic, { ...props, session, list, search, setSearch });
  // 로그인하지 않았거나 임시 비밀번호 상태면 로그인 화면(비밀번호 변경 단계)으로 보낸다.
  if (session.status === 'signedOut' || session.status === 'mustChangePassword') {
    return <Navigate to="/Login" replace />;
  }
  return (
    <div className="pg-CaseList">
      <div
        style={{
          minHeight: '960px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">{v.meInitial}</span>
            <b style={{ fontWeight: '500' }}>{v.meName}</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }} onClick={v.logout}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 260px' }}>
              <div className="sub">{v.countLabel}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>통합 사례 관리</h1>
            </div>
          </header>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 사례 ID 검색"
              placeholder="이름 · 사례 ID 검색"
              style={{ flex: '1 1 240px' }}
              {...v.search}
            />
            <div role="group" aria-label="위험도" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button
                    type="button"
                    className={f.cls}
                    disabled={f.disabled}
                    title={f.disabled ? v.notReady : undefined}
                    style={f.disabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
                  >
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <button
              type="button"
              className="tg"
              aria-pressed={v.real}
              disabled
              title={v.notReady}
              style={{ opacity: 0.5, cursor: 'not-allowed' }}
            >
              <span
                style={{
                  width: '34px',
                  height: '20px',
                  borderRadius: '10px',
                  background: v.tgBg,
                  position: 'relative',
                  display: 'inline-block',
                }}
              >
                <span
                  style={{
                    position: 'absolute',
                    top: '2px',
                    left: v.tgX,
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    background: '#FFFFFF',
                    boxShadow: '0 1px 2px rgba(0,0,0,.2)',
                  }}
                />
              </span>
              실명 보기
            </button>
          </section>
          <p className="note" style={{ margin: '-8px 0 0' }}>
            위험도 · 실명 보기 · 신고접수일은 {v.notReady}입니다(서버에 아직 없는 값).
          </p>
          <section className="card" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '640px' }}>
              <thead>
                <tr>
                  <th scope="col">사례 ID</th>
                  <th scope="col">이름</th>
                  <th scope="col">신고접수일</th>
                  <th scope="col">위험도</th>
                  <th scope="col">
                    <span style={{ position: 'absolute', left: '-9999px' }}>상세</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {v.phase !== 'rows' ? (
                  <tr>
                    <td colSpan={5} className="note" style={{ textAlign: 'center', padding: '28px 12px' }}>
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
                {(v.phase === 'rows' ? v.rows : []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td className="note">{r.id}</td>
                      <td>
                        <A className="nm" to={r.href}>
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name} <span className="note">{r.age}</span>
                          </span>
                        </A>
                      </td>
                      <td>{r.date}</td>
                      <td>
                        <span className={r.cls} style={{ minWidth: '44px', justifyContent: 'center' }}>
                          {r.risk}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <A to={r.href}>상세</A>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>
        </main>
      </div>
    </div>
  );
}
