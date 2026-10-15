// 종결 검토 · 대상 아동 목록
// 원본: 다솔 님 디자인 counselor-web-design/Closure.dc.html (front_new 브랜치)
//
// 서버 연결: 사례 기본정보 · 회차 수는 useCaseOverview(mode 'counts'), 화면에 쓸 값은 src/data/screens/closure.ts(closureValues).
// 종결 검토 등록 · 진행 단계 · 내역 검토 진행률은 서버에 없어 준비 중. 이 목록은 종결 검토 대상 목록이 아니다
// (종결 사례를 '검토 대기' 로 쓰지 않는다). 이름을 누르면 사례 상세로 간다.
import { Fragment, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseOverview } from '../data/useCaseOverview';
import { closureValues } from '../data/screens/closure';
import { needsLogin } from '../data/screens/common';
import { useTheme } from '../theme';
import './Closure.css';

class Logic extends DCLogic {
  renderVals() {
    return closureValues(this.props);
  }
}

export default function Closure(props) {
  const session = useAuthSession();
  const overview = useCaseOverview(session, 'counts');
  const [search, setSearch] = useState('');
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, overview, search, setSearch });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-Closure">
      <div
        className={theme.cls}
        style={{
          minHeight: '640px',
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
        <Sidebar active="Closure" session={session} />
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
          <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>종결 검토</h1>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="별칭 또는 사례 ID 검색"
              placeholder="별칭 · 사례 ID 검색"
              style={{ flex: '1 1 240px' }}
              value={v.search.value}
              onChange={v.search.onChange}
            />
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
                ></span>
              </span>
              실명 보기
            </button>
          </section>
          <p className="note" style={{ margin: '-8px 0 0' }}>
            {v.listNote} 실명 보기도 {v.notReady}입니다.
            {v.countLabel ? <> · {v.countLabel}</> : null}
          </p>
          <section className="card" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '600px' }}>
              <thead>
                <tr>
                  <th scope="col">아동 별칭</th>
                  <th scope="col">상담 회차</th>
                  <th scope="col">사례 등록일</th>
                  <th scope="col">진행 단계</th>
                  <th scope="col">내역 검토</th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <A className="nm" to={r.href}>
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name} <span className="note">{r.age}</span>
                            <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                              {r.sub}
                            </span>
                          </span>
                        </A>
                      </td>
                      <td>{r.sessions}</td>
                      <td>{r.date}</td>
                      <td>
                        <span className={r.stageCls}>{r.stage}</span>
                      </td>
                      <td className="note">{r.review}</td>
                    </tr>
                  </Fragment>
                ))}
                {v.emptyText ? (
                  <tr>
                    <td colSpan={5} className="note">
                      {v.emptyText}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
