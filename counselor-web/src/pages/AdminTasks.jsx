// 관리자 · 업무 처리 현황(모든 상담사의 처리 대기 회차)
// 10/21 새 디자인의 관리자 메뉴에는 없는 화면이다. 앱에 있던 기능(옛 #/Admin?view=tasks)을 새 관리자 틀(AdminSidebar · 카드 · 표)로
// 옮겨 남겼다(팀 질문 D5 의 추천). #/AdminTasks?overdue=1 이면 '지연된 업무만' 으로 연다(관리자 홈의 '지연된 업무 보기').
//
// 서버 연결: useAdminTasks(GET /tasks — 종류 · 지연으로 거르기, 쪽) · useAdminDashboard(종류별 수). 값은 src/data/screens/admin.ts(adminTasksValues).
// 재처리(다시 변환 · 다시 분석) 요청은 넣지 않았다(관리자 대리 처리 범위는 팀 결정 D5). 회차 화면에서 담당 상담사가 처리한다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { useCallback, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminDashboard } from '../data/useAdminDashboard';
import { useAdminTasks } from '../data/useAdminTasks';
import { needsLogin } from '../data/screens/common';
import { adminTasksValues, initialTasksQuery, readOverdueOnly } from '../data/screens/admin';
import './Admin.css';

class Logic extends DCLogic {
  renderVals() {
    return adminTasksValues(this.props);
  }
}

export default function AdminTasks(props) {
  const session = useAuthSession();
  const [search] = useSearchParams();
  const [query, setQueryState] = useState(() => initialTasksQuery(readOverdueOnly(search)));
  const setQuery = useCallback((patch) => setQueryState((current) => ({ ...current, ...patch })), []);
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin).
  const dashboard = useAdminDashboard(session);
  const taskList = useAdminTasks(session, {
    taskType: query.taskType || undefined,
    overdueOnly: query.overdueOnly,
    page: query.page,
  });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, pending: dashboard.pendingTasks.value, taskList, query, setQuery });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminTasks">
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
        <AdminSidebar active="AdminTasks" session={session} />
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
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>업무 처리 현황</h1>
              <p className="sub" style={{ margin: '4px 0 0' }}>
                모든 상담사의 처리 대기 회차 · 오래 기다린 순{v.summary ? ` · ${v.summary}` : ''}
              </p>
            </div>
          </header>

          <section className="card" aria-label="업무 목록" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <select className="inp" aria-label="업무 종류" {...v.type}>
                {v.typeOptions.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <input type="checkbox" {...v.overdue} />
                지연된 업무만
              </label>
              <span className="note" style={{ marginLeft: 'auto' }}>
                재처리 요청은 {v.notReady}입니다. 회차 화면에서 담당 상담사가 처리합니다.
              </span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '860px' }}>
                <thead>
                  <tr>
                    <th scope="col">사례 ID</th>
                    <th scope="col">아동 별칭</th>
                    <th scope="col">담당 상담사</th>
                    <th scope="col">대기 시작</th>
                    <th scope="col">대기시간</th>
                    <th scope="col">처리 단계</th>
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
                    <tr key={r.key}>
                      <td className="note">{r.caseNumber}</td>
                      <td>{r.child}</td>
                      <td>{r.counselor}</td>
                      <td title={r.sinceFull} style={{ whiteSpace: 'nowrap' }}>
                        {r.since}
                      </td>
                      <td style={{ fontWeight: r.waitWeight }}>
                        {r.waiting}
                        {r.overdueText ? <span className="note"> · {r.overdueText}</span> : null}
                      </td>
                      <td>
                        <span className={r.stageCls}>{r.stage}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <A to={r.href}>회차 보기</A>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {v.pager.label ? (
              <div
                style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '12px 22px 16px', flexWrap: 'wrap' }}
              >
                <span className="note">{v.pager.label}</span>
                <span style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
                  <button type="button" className="btn btn-s btn-sm" disabled={!v.pager.canPrev} onClick={v.pager.prev}>
                    이전
                  </button>
                  <button type="button" className="btn btn-s btn-sm" disabled={!v.pager.canNext} onClick={v.pager.next}>
                    다음
                  </button>
                </span>
              </div>
            ) : null}
          </section>
        </main>
      </div>
    </div>
  );
}
