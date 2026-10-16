// 관리자 대시보드 · 업무 처리 현황 · 상담사 계정 관리 · 접속 기록
// 원본: 다솔 님 디자인 counselor-web-design/Admin.dc.html (front_new 브랜치). 디자인은 대시보드 한 장이라 나머지 보기는
// 같은 카드 · 표 · 칩으로 만들고 왼쪽 메뉴로 옮긴다(주소 #/Admin?view=tasks · accounts · audit).
//
// 서버 연결: 관리자 훅(useAdminDashboard · useAdminTasks · useAdminAccounts · useAuditLogs)은 src/data 에 있고,
// 화면에 쓸 값은 src/data/screens/admin.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { Fragment, useCallback, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminDashboard } from '../data/useAdminDashboard';
import { useAdminTasks } from '../data/useAdminTasks';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { useAuditLogs } from '../data/useAuditLogs';
import { needsLogin } from '../data/screens/common';
import {
  DASHBOARD_TASK_ROWS,
  INITIAL_ADMIN_QUERY,
  INITIAL_ADMIN_STATE,
  adminBlockedNotice,
  adminValues,
  readAdminView,
  taskGroupTypes,
} from '../data/screens/admin';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_ADMIN_STATE;
  }
  renderVals() {
    return adminValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

// 업무 표(대시보드 · 업무 처리 현황 보기가 함께 쓴다).
function TaskTable({ t, emptyText }) {
  return (
    <table className="tbl" style={{ marginBottom: '8px' }}>
      <thead>
        <tr>
          <th scope="col">사례 ID</th>
          <th scope="col">아동 별칭</th>
          <th scope="col">담당 상담사</th>
          <th scope="col">대기 시작</th>
          <th scope="col">대기시간</th>
          <th scope="col">처리 단계</th>
          <th scope="col">작업</th>
        </tr>
      </thead>
      <tbody>
        {t.phase !== 'rows' ? (
          <tr>
            <td colSpan={7} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
              {t.phase === 'loading' ? '불러오는 중…' : null}
              {t.phase === 'empty' ? emptyText : null}
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
        ) : null}
        {(t.phase === 'rows' ? t.rows : []).map((r) => (
          <tr key={r.key}>
            <td className="note">{r.caseNumber}</td>
            <td>{r.child}</td>
            <td>{r.counselor}</td>
            <td title={r.sinceFull}>{r.since}</td>
            <td style={{ fontWeight: r.waitWeight }}>
              {r.waiting}
              {r.overdueText ? <span className="note"> · {r.overdueText}</span> : null}
            </td>
            <td>
              <span className={r.stageCls}>{r.stage}</span>
            </td>
            <td>
              <A to={r.href}>회차 보기</A>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Pager({ p }) {
  if (!p.label) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '4px 24px 18px', flexWrap: 'wrap' }}>
      <span className="note">{p.label}</span>
      <span style={{ marginLeft: 'auto', display: 'flex', gap: '6px' }}>
        <button type="button" className="btn btn-s btn-sm" disabled={!p.canPrev} onClick={p.prev}>
          이전
        </button>
        <button type="button" className="btn btn-s btn-sm" disabled={!p.canNext} onClick={p.next}>
          다음
        </button>
      </span>
    </div>
  );
}

export default function Admin(props) {
  const session = useAuthSession();
  const view = readAdminView(useSearchParams()[0]);
  const [query, setQueryState] = useState(INITIAL_ADMIN_QUERY);
  const setQuery = useCallback((patch) => setQueryState((current) => ({ ...current, ...patch })), []);
  const [typeA, typeB] = taskGroupTypes(query.group);
  // 훅은 관리자일 때만 서버를 부른다(session.isAdmin). 보기마다 필요한 것만 켠다.
  // 대시보드 숫자는 메뉴 숫자 · 탭 숫자에도 쓰여 늘 켠다.
  const dashboard = useAdminDashboard(session);
  const onDashboard = view === 'dashboard';
  const groupA = useAdminTasks(session, { enabled: onDashboard, taskType: typeA, pageSize: DASHBOARD_TASK_ROWS });
  const groupB = useAdminTasks(session, { enabled: onDashboard, taskType: typeB, pageSize: DASHBOARD_TASK_ROWS });
  const taskList = useAdminTasks(session, {
    enabled: view === 'tasks',
    taskType: query.taskType || undefined,
    overdueOnly: query.overdueOnly,
    page: query.taskPage,
  });
  const accounts = useAdminAccounts(session, { enabled: view === 'accounts' });
  const audit = useAuditLogs(session, {
    enabled: view === 'audit',
    action: query.auditAction,
    result: query.auditResult,
    startDate: query.auditStart,
    endDate: query.auditEnd,
    page: query.auditPage,
  });
  const theme = useTheme();
  const v = useDC(Logic, {
    ...props,
    session,
    view,
    dashboard,
    groupTasks: [groupA, groupB],
    taskList,
    accounts,
    audit,
    query,
    setQuery,
  });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) {
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
          <Notice value={adminBlockedNotice(session)} />
        </div>
      </div>
    );
  }
  const off = { opacity: 0.5, cursor: 'not-allowed' };
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
          <A className={v.menu.dashboard.cls} to={v.menu.dashboard.href}>
            관리자 대시보드
          </A>
          <div className="grp">데이터 · 업무 관리</div>
          <A to="/CaseList">전체 사례 현황</A>
          <A className={v.menu.tasks.cls} to={v.menu.tasks.href}>
            업무 처리 현황{v.menu.taskBadge ? <span className="badge">{v.menu.taskBadge}</span> : null}
          </A>
          <a aria-disabled="true" title={v.notReady} style={off}>
            문서 승인 관리
          </a>
          <div className="grp">권한 · 보안</div>
          <A className={v.menu.accounts.cls} to={v.menu.accounts.href}>
            상담사 계정 관리
          </A>
          <A className={v.menu.audit.cls} to={v.menu.audit.href}>
            접속 기록
          </A>
          <a aria-disabled="true" title={v.notReady} style={off}>
            보안 이벤트
          </a>
          <A to="/Stats">통계 리포트</A>
          <A to="/Main" style={{ marginTop: 'auto' }}>
            상담원 화면으로
          </A>
          <A to="/Login" style={{ color: '#7A776F' }} onClick={v.logout}>
            로그아웃
          </A>
        </aside>

        <div style={{ flex: '999 1 640px', minWidth: '0', display: 'flex', flexDirection: 'column' }}>
          <header className="top">
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
              <span className="av">{v.meInitial}</span>
              {v.meName}
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
              <h1 style={{ margin: '0', fontSize: '24px', fontWeight: '700', color: '#2B2A26' }}>{v.title}</h1>
              <p className="sub" style={{ margin: '2px 0 0' }}>
                {v.dateLabel}
              </p>
            </div>

            {v.isDashboard ? (
              <>
                <Notice value={v.statsNotice} />
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
                    <b>{v.stats.caseTotal}</b>
                  </div>
                  <div className="stat" style={{ borderRight: '1px solid #EAE7DF' }} title={v.stats.pendingTitle}>
                    <span className="sub">처리 대기 업무</span>
                    <b>
                      {v.stats.pending}
                      {v.stats.pendingNote ? (
                        <span className="sub" style={{ fontSize: '14px', fontWeight: '500' }}>
                          {' '}
                          · {v.stats.pendingNote}
                        </span>
                      ) : null}
                    </b>
                  </div>
                  <div className="stat" style={{ borderRight: '1px solid #EAE7DF' }}>
                    <span className="sub">활성 상담사</span>
                    <b>
                      {v.stats.activeCounselors}
                      <span className="sub" style={{ fontSize: '14px', fontWeight: '500' }}>
                        {v.stats.totalCounselors}
                      </span>
                    </b>
                  </div>
                  <div className="stat">
                    <span className="sub">미배정 사례</span>
                    <b title={v.notReady}>{v.stats.unassigned}</b>
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
                    {v.alerts.map((a, aIndex) => (
                      <div
                        key={a.chip}
                        className="row"
                        style={aIndex === v.alerts.length - 1 ? { borderBottom: '0' } : undefined}
                      >
                        <span className={a.cls}>{a.chip}</span>
                        <span style={{ flex: '1' }}>{a.text}</span>
                        {a.href ? (
                          <A to={a.href} onClick={a.onClick} style={{ fontSize: '13px' }}>
                            바로가기
                          </A>
                        ) : (
                          <span className="note">{a.note}</span>
                        )}
                      </div>
                    ))}
                  </section>
                  <section
                    className="card"
                    aria-label="최근 접속 활동"
                    style={{ flex: '2 1 300px', minWidth: '0', padding: '22px 24px' }}
                  >
                    <h2 className="h2" style={{ marginBottom: '4px' }}>
                      최근 접속 활동
                    </h2>
                    {v.recentText ? (
                      <p className="note" role={v.recentAlert ? 'alert' : 'status'} style={{ margin: '12px 0 0' }}>
                        {v.recentText}
                      </p>
                    ) : null}
                    {v.recent.map((r, rIndex) => (
                      <div
                        key={r.key}
                        className="row"
                        style={rIndex === v.recent.length - 1 ? { borderBottom: '0' } : undefined}
                      >
                        <span style={{ flex: '1' }}>
                          <b style={{ fontWeight: r.weight }}>{r.name}</b>
                          <span className="note" style={{ display: 'block' }}>
                            {r.meta}
                            {r.reason ? ` · ${r.reason}` : ''}
                          </span>
                        </span>
                        <span className={r.resultCls}>{r.result}</span>
                      </div>
                    ))}
                    <A to={v.menu.audit.href} style={{ fontSize: '13px', display: 'inline-block', marginTop: '10px' }}>
                      접속 기록 전체 보기
                    </A>
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
                      {v.dashTasks.tabs.map((tab) => (
                        <button
                          key={tab.key}
                          type="button"
                          role="tab"
                          aria-selected={tab.selected}
                          className={tab.cls}
                          title={tab.title}
                          onClick={tab.pick}
                        >
                          {tab.label}
                        </button>
                      ))}
                      <button
                        type="button"
                        role="tab"
                        aria-selected="false"
                        className="pill"
                        disabled
                        title={v.notReady}
                        style={off}
                      >
                        문서 승인 대기 —
                      </button>
                    </div>
                  </div>
                  <TaskTable t={v.dashTasks} emptyText="처리 대기 업무가 없습니다." />
                  <p className="note" style={{ margin: '0', padding: '0 24px 16px' }}>
                    {v.dashTasks.more} <A to={v.menu.tasks.href}>업무 처리 현황 전체 보기</A>
                  </p>
                </section>
              </>
            ) : null}

            {v.isTasks ? (
              <section className="card" aria-label="업무 목록" style={{ overflowX: 'auto' }}>
                <div
                  style={{
                    padding: '20px 24px 8px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    gap: '8px 12px',
                  }}
                >
                  <select className="inp" aria-label="업무 종류" {...v.tasks.type}>
                    {v.tasks.typeOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    <input type="checkbox" {...v.tasks.overdue} />
                    지연된 업무만
                  </label>
                  <span className="note" style={{ marginLeft: 'auto' }}>
                    재처리 요청은 {v.notReady}입니다. 회차 화면에서 담당 상담사가 처리합니다.
                  </span>
                </div>
                <TaskTable t={v.tasks} emptyText={v.tasks.emptyText} />
                <Pager p={v.tasks.pager} />
              </section>
            ) : null}

            {v.isAccounts ? (
              <>
                <form
                  className="card"
                  aria-label="새 계정 만들기"
                  onSubmit={v.accounts.create}
                  noValidate
                  style={{
                    padding: '20px 24px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'flex-end',
                    gap: '12px',
                  }}
                >
                  <h2 className="h2" style={{ flex: '1 1 100%' }}>
                    새 계정 만들기
                  </h2>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '2 1 220px' }}>
                    <span className="sub">이메일(로그인 ID)</span>
                    <input className="inp" type="email" autoComplete="off" {...v.accounts.email} />
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 160px' }}>
                    <span className="sub">이름</span>
                    <input className="inp" type="text" autoComplete="off" {...v.accounts.name} />
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '0 1 140px' }}>
                    <span className="sub">역할</span>
                    <select className="inp" {...v.accounts.role}>
                      <option value="COUNSELOR">상담원</option>
                      <option value="ADMIN">관리자</option>
                    </select>
                  </label>
                  <button type="submit" className="btn btn-p" disabled={v.accounts.busy}>
                    {v.accounts.createLabel}
                  </button>
                  <p className="note" style={{ margin: '0', flex: '1 1 100%' }}>
                    만들면 임시 비밀번호가 한 번만 보입니다. 첫 로그인 때 새 비밀번호로 바꾸게 됩니다.
                  </p>
                </form>

                {v.accounts.issued ? (
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
                    <h2 className="h2">임시 비밀번호 · {v.accounts.issued.reason}</h2>
                    <span>{v.accounts.issued.who}</span>
                    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
                      <code style={{ fontSize: '18px', fontWeight: '700', letterSpacing: '1px', userSelect: 'all' }}>
                        {v.accounts.issued.password}
                      </code>
                      <button type="button" className="btn btn-s btn-sm" onClick={v.accounts.issued.copy}>
                        {v.accounts.issued.copied ? '복사됨' : '복사'}
                      </button>
                    </div>
                    <span className="note">
                      사용 기한 {v.accounts.issued.expiresAt}. 이 안내를 닫으면 다시 볼 수 없습니다. 본인에게만 전해
                      주세요.
                    </span>
                    <div>
                      <button type="button" className="btn btn-p btn-sm" onClick={v.accounts.issued.close}>
                        전달했습니다 · 닫기
                      </button>
                    </div>
                  </section>
                ) : null}

                {v.accounts.done ? (
                  <p className="note" role="status" style={{ margin: '0' }}>
                    {v.accounts.done}
                  </p>
                ) : null}
                {v.accounts.error ? (
                  <p className="acc" role="alert" style={{ margin: '0', fontSize: '13px' }}>
                    {v.accounts.error}
                  </p>
                ) : null}
                {v.accounts.caseCountError ? (
                  <p className="note" style={{ margin: '0' }}>
                    {v.accounts.caseCountError} 담당 사례 칸은 — 로 둡니다.
                  </p>
                ) : null}

                <section className="card" aria-label="계정 목록" style={{ overflowX: 'auto' }}>
                  <table className="tbl" style={{ minWidth: '960px' }}>
                    <thead>
                      <tr>
                        <th scope="col">이름</th>
                        <th scope="col">이메일</th>
                        <th scope="col">역할</th>
                        <th scope="col">상태</th>
                        <th scope="col">담당 사례</th>
                        <th scope="col">최근 로그인</th>
                        <th scope="col">작업</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.accounts.phase !== 'rows' ? (
                        <tr>
                          <td colSpan={7} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
                            {v.accounts.phase === 'loading' ? '불러오는 중…' : null}
                            {v.accounts.phase === 'empty' ? '계정이 없습니다.' : null}
                            {v.accounts.phase === 'error' ? (
                              <button type="button" className="btn btn-s btn-sm" onClick={v.accounts.retry}>
                                다시 시도
                              </button>
                            ) : null}
                          </td>
                        </tr>
                      ) : null}
                      {(v.accounts.phase === 'rows' ? v.accounts.rows : []).map((r) => (
                        <Fragment key={r.key}>
                          <tr>
                            <td style={{ whiteSpace: 'nowrap' }}>
                              {r.name} <span className="note">{r.self}</span>
                            </td>
                            <td className="note">{r.email}</td>
                            <td style={{ whiteSpace: 'nowrap' }}>{r.role}</td>
                            <td>
                              <span style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                <span className={r.activeCls}>{r.active}</span>
                                {r.tags.map((tag) => (
                                  <span key={tag.label} className={tag.cls}>
                                    {tag.label}
                                  </span>
                                ))}
                              </span>
                              {r.lockedUntil ? <span className="note">{r.lockedUntil}</span> : null}
                            </td>
                            <td>{r.cases}</td>
                            <td className="note" style={{ whiteSpace: 'nowrap' }}>
                              {r.lastLogin}
                            </td>
                            <td>
                              <span style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                                {r.actions.map((a) => (
                                  <button
                                    key={a.label}
                                    type="button"
                                    className={a.cls}
                                    disabled={v.accounts.busy}
                                    onClick={a.onClick}
                                  >
                                    {a.label}
                                  </button>
                                ))}
                                {r.noActions ? <span className="note">{r.noActions}</span> : null}
                                {v.accounts.busyRow === r.key ? <span className="note">처리 중…</span> : null}
                              </span>
                            </td>
                          </tr>
                          {r.asking ? (
                            <tr>
                              <td colSpan={7}>
                                <span
                                  role="alertdialog"
                                  aria-label={r.askLabel}
                                  style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}
                                >
                                  <span style={{ flex: '1 1 320px' }}>{r.askText}</span>
                                  <button
                                    type="button"
                                    className="btn btn-p btn-sm"
                                    disabled={v.accounts.busy}
                                    onClick={r.confirm}
                                  >
                                    {r.askLabel}
                                  </button>
                                  <button type="button" className="btn btn-s btn-sm" onClick={v.accounts.cancelAsk}>
                                    취소
                                  </button>
                                </span>
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </section>
              </>
            ) : null}

            {v.isAudit ? (
              <section className="card" aria-label="접속 기록" style={{ overflowX: 'auto' }}>
                <div
                  style={{
                    padding: '20px 24px 8px',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'flex-end',
                    gap: '8px 12px',
                  }}
                >
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="sub">동작</span>
                    <select className="inp" {...v.audit.action}>
                      {v.audit.actionOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="sub">결과</span>
                    <select className="inp" {...v.audit.result}>
                      <option value="ALL">전체</option>
                      <option value="SUCCESS">성공</option>
                      <option value="FAILURE">실패</option>
                    </select>
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="sub">시작일</span>
                    <input className="inp" type="date" {...v.audit.start} />
                  </label>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="sub">종료일</span>
                    <input className="inp" type="date" {...v.audit.end} />
                  </label>
                  <span className="note" style={{ marginLeft: 'auto' }}>
                    보안 이벤트 심각도 · 탐지는 {v.notReady}입니다.
                  </span>
                </div>
                {v.audit.rangeError ? (
                  <p className="acc" role="alert" style={{ margin: '0', padding: '0 24px 8px', fontSize: '13px' }}>
                    {v.audit.rangeError}
                  </p>
                ) : null}
                <table className="tbl" style={{ marginBottom: '8px', minWidth: '900px' }}>
                  <thead>
                    <tr>
                      <th scope="col">일시</th>
                      <th scope="col">이름</th>
                      <th scope="col">역할(지금)</th>
                      <th scope="col">동작</th>
                      <th scope="col">결과</th>
                      <th scope="col">IP</th>
                      <th scope="col">브라우저</th>
                    </tr>
                  </thead>
                  <tbody>
                    {v.audit.phase !== 'rows' ? (
                      <tr>
                        <td colSpan={7} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
                          {v.audit.phase === 'loading' ? '불러오는 중…' : null}
                          {v.audit.phase === 'empty' ? v.audit.emptyText : null}
                          {v.audit.phase === 'error' ? (
                            <span role="alert">
                              {v.audit.errorText}{' '}
                              <button type="button" className="btn btn-s btn-sm" onClick={v.audit.retry}>
                                다시 시도
                              </button>
                            </span>
                          ) : null}
                        </td>
                      </tr>
                    ) : null}
                    {(v.audit.phase === 'rows' ? v.audit.rows : []).map((r) => (
                      <tr key={r.key}>
                        <td className="note">{r.at}</td>
                        <td>{r.name}</td>
                        <td>{r.role}</td>
                        <td>{r.action}</td>
                        <td>
                          <span className={r.resultCls}>{r.result}</span>
                          {r.reason ? <span className="note"> {r.reason}</span> : null}
                        </td>
                        <td className="note">{r.ip}</td>
                        <td className="note" title={r.userAgent}>
                          {r.browser}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Pager p={v.audit.pager} />
              </section>
            ) : null}
          </main>
        </div>
      </div>
    </div>
  );
}
