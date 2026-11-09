// 통합 사례 관리 (사례 ID · 이름 · 신고접수일 · 위험도)
// 원본: 다솔 님 디자인 counselor-web-design/CaseList.dc.html (front_new 브랜치)
//
// 서버 연결: 로그인 상태(useAuthSession)와 사례 목록(useCaseList)은 src/data 의 훅이 하고,
// 화면에 쓸 값은 src/data/screens/caseList.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 디자인을 바꿀 때는 아래 CaseList 함수의 훅과 Logic 을 그대로 두고 JSX 만 갈아 끼우면 된다.
import { Fragment, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAccountSearch } from '../data/useAccountSearch';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseList } from '../data/useCaseList';
import { CASE_LIST_PER_PAGE, caseListValues } from '../data/screens/caseList';
import { needsLogin, signedIn } from '../data/screens/common';
import './CaseList.css';

class Logic extends DCLogic {
  renderVals() {
    return caseListValues(this.props);
  }
}

export default function CaseList(props) {
  const session = useAuthSession();
  // 검색어는 계정에 묶는다 — 다른 계정으로 바뀌면 앞 계정이 친 이름이 남지 않는다(Codex #130 H1).
  const [search, setSearchValue] = useAccountSearch(session);
  // 사용자 정보까지 확인된 뒤에만 부른다 — 다른 탭의 다시 로그인으로 사용자 정보가 먼저 비는 사이에 새 토큰으로 한 번 더
  // 부르지 않게(Codex #130 재검수 N4).
  const [sort, setSortValue] = useState(null);
  const [order, setOrder] = useState('desc');
  const [page, setPage] = useState(1);
  // 조건이 바뀌면 1쪽부터(디자인).
  const setSearch = (value) => {
    setSearchValue(value);
    setPage(1);
  };
  const setSort = (nextSort, nextOrder) => {
    setSortValue(nextSort);
    setOrder(nextOrder);
    setPage(1);
  };
  const list = useCaseList({
    search,
    enabled: session.status === 'signedIn' && session.me !== null,
    withNames: true,
    sort: sort ?? undefined,
    order,
    page,
    pageSize: CASE_LIST_PER_PAGE,
  });
  // 사례가 줄어 지금 쪽이 없어졌으면 마지막 쪽으로 옮긴다.
  useEffect(() => {
    if (list.total === null || list.loading) return;
    const last = Math.max(1, Math.ceil(list.total / CASE_LIST_PER_PAGE));
    if (page > last) setPage(last);
  }, [list.total, list.loading, page]);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, list, search, setSearch, sort, order, setSort, page, setPage });
  // 로그인하지 않았거나 임시 비밀번호 상태면 로그인 화면(비밀번호 변경 단계)으로 보낸다.
  if (session.status === 'signedOut' || session.status === 'mustChangePassword') {
    return <Navigate to="/Login" replace />;
  }
  return (
    <div className="pg-CaseList">
      <div
        className={theme.cls}
        style={{
          minHeight: '960px',
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
        <Sidebar active="CaseList" session={session} />
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
            <div role="group" aria-label="정렬" className="seg">
              <span className="seg-lb">정렬</span>
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button
                    type="button"
                    className={f.cls}
                    aria-pressed={f.cls === 'on'}
                    onClick={f.pick}
                  >
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
          </section>
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
          {v.pager.show ? (
            <nav className="pager" aria-label="사례 목록 페이지">
              <button type="button" className="pg-n pg-ar" aria-label="첫 페이지" disabled={v.pager.atStart} onClick={v.pager.first}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M12 6l-6 6 6 6M19 6l-6 6 6 6"></path>
                </svg>
              </button>
              <button type="button" className="pg-n pg-ar" aria-label="이전 페이지" disabled={v.pager.atStart} onClick={v.pager.prev}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M15 6l-6 6 6 6"></path>
                </svg>
              </button>
              {v.pager.pages.map((p) => (
                <button key={p.aria + p.label} type="button" className={p.cls} aria-label={p.aria} aria-current={p.cur} onClick={p.go}>
                  {p.label}
                </button>
              ))}
              <button type="button" className="pg-n pg-ar" aria-label="다음 페이지" disabled={v.pager.atEnd} onClick={v.pager.next}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M9 6l6 6-6 6"></path>
                </svg>
              </button>
              <button type="button" className="pg-n pg-ar" aria-label="마지막 페이지" disabled={v.pager.atEnd} onClick={v.pager.last}>
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 6l6 6-6 6M12 6l6 6-6 6"></path>
                </svg>
              </button>
            </nav>
          ) : null}
        </main>
      </div>
    </div>
  );
}
