// 아이 연계 · 긴급 알림 + 아이 목록 (응답 · 상태)
// 원본: 다솔 님 디자인 counselor-web-design/ChildLink.dc.html. 담당 사례의 콩콩 연결 상태를 서버 값으로 보인다(API_CONTRACT 24절).
// 사례를 누르면 아이 상세로 간다. 연결 전이면 아이 상세에서 연결 코드를 만든다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useTheme } from '../theme';
import { childApp } from '../api/endpoints';
import Notice from '../components/Notice';
import { CHILD_ALERT_TEXT } from '../data/useCaseChildApp';
import { screenHref } from '../data/screens/links';
import { needsLogin, screenNotice } from '../data/screens/common';
import { useRemote } from '../data/useRemote';
import { Navigate } from 'react-router-dom';
import './ChildLink.css';

const childDateTime = (iso) => (iso ? new Date(iso).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—');

function rowState(row) {
  // 긴급 알림 · 바로 확인 답만 '긴급', 글 · 연락 요청 · 추가 질문 답은 '확인 필요'(민규 #165 리뷰 6).
  if (row.open_alert_urgent) return { reason: '긴급', rCls: 'chip c-urgent', need: true };
  if (row.open_alert_reason) return { reason: '확인 필요', rCls: 'chip c-check', need: true };
  if (row.status === 'NOT_LINKED') return { reason: '앱 미연결 · 초대 전', rCls: 'chip c-normal', need: false };
  if (row.status === 'INVITED') return { reason: '초대 대기', rCls: 'chip c-normal', need: false };
  // 바로 확인할 답(RED)은 늘 확인 처리를 거치므로, 열린 알림이 없으면 확인을 마친 것(멘토 피드백 11/12).
  if (row.level === 'RED') {
    return { reason: `확인 완료${row.last_acked_at ? ` ${childDateTime(row.last_acked_at)}` : ''}`, rCls: 'chip c-ok', need: false, acked: true };
  }
  if (row.level === 'AMBER') return { reason: '확인 필요', rCls: 'chip c-check', need: true };
  return { reason: '정상', rCls: 'chip c-normal', need: false };
}

const PER_PAGE = 10;
const PAGE_BLOCK = 4;

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // null 이면 확인할 아이가 있을 때 그쪽을, 없으면 전체를 보인다(연결을 시작할 사례가 가려지지 않게).
    this.state = { f: null, q: '', page: 1 };
  }
  renderVals() {
    const s = this.state;
    const all = (this.props.list || []).map((row) => {
      const state = rowState(row);
      const linked = row.status === 'LINKED';
      return {
        ...state,
        name: row.child_alias,
        age: row.child_birth_year ? `${row.child_birth_year}년생` : '',
        id: row.case_number,
        ini: row.child_alias.slice(0, 1),
        last: childDateTime(row.last_response_at),
        count: linked ? (row.recent_answers === null ? '—' : `응답 ${row.recent_answers}번`) : '미연결',
        // 늘 아이 상세(아이 연계 메뉴 안)로 간다. 연결 전이면 그 화면에서 연결 코드를 만든다(11/10 경진님).
        to: screenHref('/ChildDetail', { caseId: row.case_id }),
        // 상담사가 알림 · 답을 확인했는지(멘토 피드백 11/12). 열린 알림이 있으면 확인 전, 없고 가장 최근 것을 확인했으면 그 시각.
        ack: state.acked
          ? null
          : row.open_alert_reason
          ? { text: '확인 전', cls: 'chip c-sand' }
          : row.last_acked_at
            ? { text: `확인 완료 ${childDateTime(row.last_acked_at)}`, cls: 'chip c-ok' }
            : null,
        alert: row.open_alert_urgent
          ? { at: childDateTime(row.open_alert_at), text: CHILD_ALERT_TEXT[row.open_alert_reason] || CHILD_ALERT_TEXT.NEEDS_CHECK }
          : null,
      };
    });
    const need = all.filter((row) => row.need);
    const filter = s.f || (need.length ? 'need' : 'all');
    const term = s.q.trim();
    const matched = (filter === 'need' ? need : all).filter((row) => !term || row.name.includes(term) || row.id.includes(term));
    // 쪽 번호(사례 관리 목록과 같게 10줄씩, 번호는 4개씩 묶음).
    const totalPages = Math.max(1, Math.ceil(matched.length / PER_PAGE));
    const current = Math.min(Math.max(1, s.page), totalPages);
    const rows = matched.slice((current - 1) * PER_PAGE, current * PER_PAGE);
    const go = (n) => () => this.setState({ page: Math.min(Math.max(1, n), totalPages) });
    const blockStart = Math.floor((current - 1) / PAGE_BLOCK) * PAGE_BLOCK + 1;
    const blockEnd = Math.min(blockStart + PAGE_BLOCK - 1, totalPages);
    const pages = [];
    if (blockStart > 1) pages.push({ label: '…', cls: 'pg-n pg-gap', go: go(blockStart - 1), aria: `${blockStart - 1}쪽` });
    for (let n = blockStart; n <= blockEnd; n++) {
      pages.push({ label: String(n), cls: n === current ? 'pg-n on' : 'pg-n', go: go(n), aria: `${n}쪽`, cur: n === current ? 'page' : undefined });
    }
    if (blockEnd < totalPages) pages.push({ label: '…', cls: 'pg-n pg-gap', go: go(blockEnd + 1), aria: `${blockEnd + 1}쪽` });
    const pager = {
      show: matched.length > PER_PAGE,
      pages,
      first: go(1),
      prev: go(current - 1),
      next: go(current + 1),
      last: go(totalPages),
      atStart: current === 1,
      atEnd: current === totalPages,
    };
    const filters = [
      ['need', `확인할 아이 ${need.length}`],
      ['all', `전체 ${all.length}`],
    ].map(([value, label]) => ({ label, cls: filter === value ? 'on' : '', pick: () => this.setState({ f: value, page: 1 }) }));
    return {
      rows,
      filters,
      alert: all.find((row) => row.alert) || null,
      search: s.q,
      setSearch: (e) => this.setState({ q: e.target.value, page: 1 }),
      pager,
      empty: rows.length === 0,
    };
  }
}

export default function ChildLink(props) {
  const session = useAuthSession();
  const theme = useTheme();
  const key = session.status === 'signedIn' ? `child-link:${session.me.id}` : null;
  const remote = useRemote(key, () => childApp.listCases(), '아이 연계 목록을 불러오지 못했습니다.', () => false);
  const v = useDC(Logic, { ...props, list: remote.data });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  const notice = screenNotice({ session, loading: remote.loading && !remote.data, error: remote.error, retry: remote.reload });
  return (
    <div className="pg-ChildLink">
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
        <Sidebar active="ChildLink" session={session} />
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
          <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>아이 연계</h1>
          <Notice value={notice} />

          {v.alert ? (
          <A
            role="alert"
            to={v.alert.to}
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '10px 14px',
              padding: '16px 20px',
              borderRadius: '16px',
              background: '#F7E4DF',
              textDecoration: 'none',
              color: '#A33B2E',
            }}
          >
            <span className="chip c-urgent" style={{ background: '#FFFFFF' }}>
              긴급
            </span>
            <span style={{ flex: '1 1 320px' }}>
              <b>{v.alert.name}</b> · {v.alert.alert.at} {v.alert.alert.text}
            </span>
            <b style={{ fontSize: '14px' }}>바로 확인 →</b>
          </A>
          ) : null}

          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
            <input
              className="inp"
              type="search"
              aria-label="이름 또는 사례 ID 검색"
              placeholder="이름 · 사례 ID 검색"
              value={v.search}
              onChange={v.setSearch}
              style={{ flex: '1 1 240px' }}
            />
            <div role="group" aria-label="상태" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button type="button" className={f.cls} onClick={f.pick}>
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
                  <th scope="col">아동 이름</th>
                  <th scope="col">최근 3주 응답</th>
                  <th scope="col">마지막 응답</th>
                  <th scope="col">상태</th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <A className="nm" to={r.to}>
                          <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                            {r.ini}
                          </span>
                          <span>
                            {r.name} <span className="note">{r.age}</span>
                            <span className="note" style={{ display: 'block', fontWeight: '400' }}>
                              {r.id}
                            </span>
                          </span>
                        </A>
                      </td>
                      <td>
                        <b>{r.count}</b>
                      </td>
                      <td>{r.last}</td>
                      <td>
                        <span className={r.rCls}>{r.reason}</span>
                        {r.ack ? (
                          <>
                            {' '}
                            <span className={r.ack.cls}>{r.ack.text}</span>
                          </>
                        ) : null}
                      </td>
                    </tr>
                  </Fragment>
                ))}
                {v.empty ? (
                  <tr>
                    <td colSpan={4} className="note">
                      보일 사례가 없어요.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </section>
          {v.pager.show ? (
            <nav className="pager" aria-label="아이 목록 페이지">
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
