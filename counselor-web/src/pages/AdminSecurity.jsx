// 관리자 · 접속 기록 · 보안 이벤트
// 원본: 다솔 님 10/21 디자인 counselor-design/screens/AdminSecurity.dc.html (origin/frontend261021)
//
// 서버 연결: useAuditLogs(목록 + 오늘 로그인 실패 수) · useAdminAccounts(지금 잠긴 계정 · 잠금 해제). 값은 src/data/screens/adminSecurity.ts.
// 요약 카드는 디자인처럼 누르면 목록을 거른다. 앱에 있던 자세한 조건(동작 · 결과 · 기간 · 쪽)은 그대로 둔다.
// 외부 IP · 접속 위치 · 심각도 · IP 차단은 서버에 없어 '—' · 준비 중, OTP 실패는 OTP 가 없어(팀 결정 D1) 두지 않는다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { useCallback, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAuditLogs } from '../data/useAuditLogs';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { needsLogin } from '../data/screens/common';
import {
  INITIAL_SECURITY_QUERY,
  INITIAL_SECURITY_UI,
  adminSecurityValues,
  todayFailureOptions,
} from '../data/screens/adminSecurity';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_SECURITY_UI;
  }
  renderVals() {
    return adminSecurityValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function AdminSecurity(props) {
  const session = useAuthSession();
  const [query, setQueryState] = useState(INITIAL_SECURITY_QUERY);
  const setQuery = useCallback((patch) => setQueryState((current) => ({ ...current, ...patch })), []);
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin).
  const audit = useAuditLogs(session, {
    action: query.action,
    result: query.result,
    startDate: query.start,
    endDate: query.end,
    page: query.page,
  });
  const todayFailures = useAuditLogs(session, todayFailureOptions(new Date()));
  const accounts = useAdminAccounts(session);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, audit, todayFailures, accounts, query, setQuery });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminSecurity">
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
        <AdminSidebar active="AdminSecurity" session={session} />
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
          <header>
            <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>접속 기록 · 보안 이벤트</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              로그인 · 계정 관리 기록입니다. 보안 이벤트 심각도 · 탐지와 IP 차단은 {v.notReady}입니다.
            </p>
          </header>

          <section
            aria-label="보안 요약"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            <button
              type="button"
              className={v.kpis.fail.cls}
              aria-pressed={v.kpis.fail.pressed}
              onClick={v.kpis.fail.pick}
              style={{ boxShadow: 'inset 0 4px 0 #A33B2E' }}
            >
              <span className="sub acc" style={{ fontWeight: '700' }}>
                로그인 실패 (오늘)
              </span>
              <b className="acc">{v.kpis.fail.value}</b>
              <span className="note">{v.kpis.fail.note}</span>
            </button>
            <div className="card kpi" title={v.notReady}>
              <span className="sub">외부 IP 접속</span>
              <b>{v.kpis.external.value}</b>
              <span className="note">{v.kpis.external.note}</span>
            </div>
            <button
              type="button"
              className={v.kpis.lock.cls}
              aria-pressed={v.kpis.lock.pressed}
              onClick={v.kpis.lock.pick}
            >
              <span className="sub">잠긴 계정</span>
              <b>{v.kpis.lock.value}</b>
              <span className="note">{v.kpis.lock.note}</span>
            </button>
          </section>

          {v.lockedList.show ? (
            <section className="card" aria-label="지금 잠긴 계정" style={{ overflow: 'hidden' }}>
              <div className="hd">
                <h2 className="h2">지금 잠긴 계정</h2>
                {v.lockedList.busy ? <span className="note">처리 중…</span> : null}
              </div>
              {v.lockedList.rows.length === 0 ? (
                <p className="note" style={{ margin: '0', padding: '16px 22px' }}>
                  {v.lockedList.emptyText}
                </p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="tbl" style={{ minWidth: '640px' }}>
                    <thead>
                      <tr>
                        <th scope="col">계정</th>
                        <th scope="col">이메일</th>
                        <th scope="col">풀리는 때</th>
                        <th scope="col">
                          <span style={{ position: 'absolute', left: '-9999px' }}>작업</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.lockedList.rows.map((r) => (
                        <tr key={r.key}>
                          <td>
                            <A to={r.href}>{r.name}</A>
                          </td>
                          <td className="note">{r.email}</td>
                          <td>{r.lockedUntil}</td>
                          <td style={{ textAlign: 'right' }}>
                            <button
                              type="button"
                              className="btn btn-sm btn-s"
                              disabled={v.lockedList.busy}
                              onClick={r.unlock}
                            >
                              {v.lockedList.busyRow === r.key ? '푸는 중…' : '잠금 해제'}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ) : null}
          {v.done ? (
            <p className="note" role="status" style={{ margin: '-6px 0 0', color: '#2B2A26' }}>
              {v.done}
            </p>
          ) : null}
          {v.actionError ? (
            <p className="acc" role="alert" style={{ margin: '0', fontSize: '13px' }}>
              {v.actionError}
            </p>
          ) : null}

          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <div role="group" aria-label="기록 종류" className="seg">
              {v.quickSeg.map((f) => (
                <button key={f.key} type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                  {f.label}
                </button>
              ))}
            </div>
          </section>

          <section className="card" aria-label="접속 기록" style={{ overflow: 'hidden' }}>
            <div className="hd" style={{ alignItems: 'flex-end' }}>
              <label className="fl">
                <span className="lb">동작</span>
                <select className="inp" {...v.action}>
                  {v.actionOptions.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="fl">
                <span className="lb">결과</span>
                <select className="inp" {...v.result}>
                  <option value="ALL">전체</option>
                  <option value="SUCCESS">성공</option>
                  <option value="FAILURE">실패</option>
                </select>
              </label>
              <label className="fl">
                <span className="lb">시작일</span>
                <input className="inp" type="date" {...v.start} />
              </label>
              <label className="fl">
                <span className="lb">종료일</span>
                <input className="inp" type="date" {...v.end} />
              </label>
            </div>
            {v.rangeError ? (
              <p className="acc" role="alert" style={{ margin: '0', padding: '12px 22px 0', fontSize: '13px' }}>
                {v.rangeError}
              </p>
            ) : null}
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '1000px' }}>
                <thead>
                  <tr>
                    <th scope="col">일시</th>
                    <th scope="col">계정</th>
                    <th scope="col">구분</th>
                    <th scope="col">접속 IP</th>
                    <th scope="col">접속 위치</th>
                    <th scope="col">처리 결과</th>
                    <th scope="col">브라우저</th>
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
                      <td style={{ whiteSpace: 'nowrap' }}>{r.at}</td>
                      <td>
                        <b style={{ fontWeight: r.nameWeight }}>{r.name}</b>
                        {r.role ? (
                          <span className="note" style={{ display: 'block' }}>
                            {r.role}
                          </span>
                        ) : null}
                      </td>
                      <td>{r.ev}</td>
                      <td>{r.ip}</td>
                      <td title={v.notReady}>{r.net}</td>
                      <td>
                        <span className={r.resultCls}>{r.result}</span>
                        {r.reason ? (
                          <span className="note" style={{ display: 'block' }}>
                            {r.reason}
                          </span>
                        ) : null}
                      </td>
                      <td className="note" title={r.userAgent}>
                        {r.browser}
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
