// 관리자 · 홈(기관 현황)
// 원본: 다솔 님 10/21 디자인 counselor-design/screens/AdminHome.dc.html (origin/frontend261021)
//
// 서버 연결: useAdminDashboard(전체 사례 · 처리 대기 업무 · 상담사 수 · 최근 접속 5건) · useCaseList(진행 중 사례 수) ·
// useAdminTasks(업무 표, 두 종류씩) · useAdminAccounts(상담원별 담당 사례 수). 화면에 쓸 값은 src/data/screens/adminHome.ts.
// 디자인의 '긴급 알림 현황'(아이 연계 앱)은 서버가 없어 표를 만들지 않고, 그 자리에 앱에 있던 업무 처리 현황을 둔다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminDashboard } from '../data/useAdminDashboard';
import { useAdminTasks } from '../data/useAdminTasks';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { useCaseList } from '../data/useCaseList';
import { needsLogin } from '../data/screens/common';
import { DASHBOARD_TASK_ROWS, TASK_GROUPS, taskGroupTypes } from '../data/screens/admin';
import { adminHomeValues } from '../data/screens/adminHome';
import './Admin.css';

class Logic extends DCLogic {
  renderVals() {
    return adminHomeValues(this.props);
  }
}

// 표 본문의 불러오는 중 · 비어 있음 · 오류 한 줄.
function PhaseRow({ t, cols }) {
  if (t.phase === 'rows') return null;
  return (
    <tr>
      <td colSpan={cols} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
        {t.phase === 'loading' ? '불러오는 중…' : null}
        {t.phase === 'empty' ? t.emptyText : null}
        {t.phase === 'error' ? (
          <span role="alert">
            {t.errorText}{' '}
            <button type="button" className="btn btn-s btn-sm" onClick={t.retry}>
              다시 시도
            </button>
          </span>
        ) : null}
      </td>
    </tr>
  );
}

export default function AdminHome(props) {
  const session = useAuthSession();
  const [group, setGroup] = useState(TASK_GROUPS[0].key);
  const [typeA, typeB] = taskGroupTypes(group);
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin). 사례 목록 훅은 enabled 로 막는다.
  const dashboard = useAdminDashboard(session);
  const activeCases = useCaseList({ status: 'ACTIVE', enabled: session.isAdmin });
  const groupA = useAdminTasks(session, { taskType: typeA, pageSize: DASHBOARD_TASK_ROWS });
  const groupB = useAdminTasks(session, { taskType: typeB, pageSize: DASHBOARD_TASK_ROWS });
  const accounts = useAdminAccounts(session);
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    dashboard,
    activeCases,
    groupTasks: [groupA, groupB],
    accounts,
    group,
    setGroup,
  });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminHome">
      <div
        className={theme.cls}
        style={{
          minHeight: '1820px',
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
        <AdminSidebar active="AdminHome" session={session} />
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
              <div className="sub" style={{ fontWeight: '500' }}>
                {v.dateLabel}
              </div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>기관 현황</h1>
            </div>
          </header>
          <Notice value={v.statsNotice} />

          <section
            aria-label="오늘 요약"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            <div className="card kpi">
              <span className="sub">진행 중 사례</span>
              <b>{v.kpis.active.value}</b>
              <span className="note">{v.kpis.active.note}</span>
            </div>
            <button type="button" className="card kpi kb" title={v.kpis.pending.title} onClick={v.kpis.pending.go}>
              <span className="sub">처리 대기 업무</span>
              <b>{v.kpis.pending.value}</b>
              <span className="note">{v.kpis.pending.note}</span>
            </button>
            <A className="card kpi" to={v.kpis.counselors.href}>
              <span className="sub">활성 상담사</span>
              <b>
                {v.kpis.counselors.value}
                <span className="sub" style={{ fontSize: '15px', fontWeight: '500' }}>
                  {v.kpis.counselors.total}
                </span>
              </b>
              <span className="note">{v.kpis.counselors.note}</span>
            </A>
            <div className="card kpi" title={v.notReady}>
              <span className="sub">긴급 알림 · 확인 전</span>
              <b>{v.kpis.urgent.value}</b>
              <span className="note">{v.kpis.urgent.note}</span>
            </div>
          </section>

          <section id={v.tasksId} className="card" aria-label="업무 처리 현황" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">업무 처리 현황</h2>
              <span className="note">상담사가 처리할 차례인 회차 · 오래 기다린 순</span>
              <div style={{ marginLeft: 'auto' }}>
                <div role="group" aria-label="업무 종류" className="seg">
                  {v.tasks.tabs.map((f) => (
                    <button
                      key={f.key}
                      type="button"
                      className={f.cls}
                      aria-pressed={f.pressed}
                      title={f.title}
                      onClick={f.pick}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
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
                  <PhaseRow t={v.tasks} cols={7} />
                  {(v.tasks.phase === 'rows' ? v.tasks.rows : []).map((r) => (
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
            <p className="note" style={{ margin: '0', padding: '12px 22px 16px' }}>
              {v.tasks.more} <A to={v.tasks.moreHref}>업무 처리 현황 전체 보기</A>
              {v.tasks.overdueText ? (
                <>
                  {' '}
                  · {v.tasks.overdueText} <A to={v.tasks.overdueHref}>지연된 업무 보기</A>
                </>
              ) : null}
            </p>
          </section>

          <section className="card" aria-label="최근 접속 활동" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">최근 접속 활동</h2>
              <A to={v.recent.href} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                전체 접속 기록
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '820px' }}>
                <thead>
                  <tr>
                    <th scope="col">일시</th>
                    <th scope="col">계정</th>
                    <th scope="col">구분</th>
                    <th scope="col">접속 IP</th>
                    <th scope="col">접속 위치</th>
                  </tr>
                </thead>
                <tbody>
                  <PhaseRow t={v.recent} cols={5} />
                  {(v.recent.phase === 'rows' ? v.recent.rows : []).map((r) => (
                    <tr key={r.key}>
                      <td title={r.atFull} style={{ whiteSpace: 'nowrap' }}>
                        {r.at}
                      </td>
                      <td>
                        <b style={{ fontWeight: r.nameWeight }}>{r.name}</b>
                        {r.role ? (
                          <span className="note" style={{ display: 'block' }}>
                            {r.role}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <span className={r.evCls}>{r.ev}</span>
                        {r.reason ? (
                          <span className="note" style={{ display: 'block' }}>
                            {r.reason}
                          </span>
                        ) : null}
                      </td>
                      <td>{r.ip}</td>
                      <td title={v.notReady}>{r.net}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card" aria-label="상담원별 업무량" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">상담원별 업무량</h2>
              <A to={v.load.href} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                계정 관리
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '900px' }}>
                <thead>
                  <tr>
                    <th scope="col">상담원</th>
                    <th scope="col" style={{ width: '22%' }}>
                      담당 사례(종결 포함)
                    </th>
                    <th scope="col">위험도 상</th>
                    <th scope="col">이번 주 상담</th>
                    <th scope="col">STT 검수 대기</th>
                    <th scope="col">일지 미작성</th>
                  </tr>
                </thead>
                <tbody>
                  <PhaseRow t={v.load} cols={6} />
                  {(v.load.phase === 'rows' ? v.load.rows : []).map((r) => (
                    <tr key={r.key} style={{ opacity: r.op }}>
                      <td>
                        <A className="nm" to={r.href}>
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            <b style={{ fontWeight: '500' }}>{r.name}</b>
                            <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                              {r.rank}
                            </span>
                          </span>
                        </A>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span className="mini" style={{ flex: '1' }}>
                            <span style={{ width: r.w }}></span>
                          </span>
                          <b style={{ width: '32px' }}>{r.cases}</b>
                        </div>
                      </td>
                      <td title={v.notReady}>{r.hi}</td>
                      <td title={v.notReady}>{r.week}</td>
                      <td title={v.notReady}>{r.stt}</td>
                      <td title={v.notReady}>{r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note" style={{ margin: '0', padding: '12px 22px 16px' }}>
              {v.load.note}
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
