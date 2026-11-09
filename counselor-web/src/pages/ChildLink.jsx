// 아이 연계 · 긴급 알림 + 아이 목록 (응답 · 상태)
// 원본: 다솔 님 디자인 counselor-web-design/ChildLink.dc.html. 담당 사례의 콩콩 연결 상태를 서버 값으로 보인다(API_CONTRACT 24절).
// 연결 전 사례는 콩콩 탭으로 가서 연결 코드를 만들고, 연결된 사례는 아이 상세로 간다.
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
  if (row.open_alert_reason) return { reason: '긴급', rCls: 'chip c-urgent', need: true };
  if (row.status === 'NOT_LINKED') return { reason: '앱 미연결 · 초대 전', rCls: 'chip c-normal', need: false };
  if (row.status === 'INVITED') return { reason: '초대 대기', rCls: 'chip c-normal', need: false };
  if (row.level === 'RED' || row.level === 'AMBER') return { reason: '확인 필요', rCls: 'chip c-check', need: true };
  return { reason: '정상', rCls: 'chip c-normal', need: false };
}

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    // null 이면 확인할 아이가 있을 때 그쪽을, 없으면 전체를 보인다(연결을 시작할 사례가 가려지지 않게).
    this.state = { f: null, q: '' };
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
        // 연결 전에는 콩콩 탭(연결 코드 만들기)으로, 연결 뒤에는 아이 상세로 간다.
        to: screenHref(linked ? '/ChildDetail' : '/CaseApp', { caseId: row.case_id }),
        alert: row.open_alert_reason
          ? { at: childDateTime(row.open_alert_at), text: CHILD_ALERT_TEXT[row.open_alert_reason] || CHILD_ALERT_TEXT.NEEDS_CHECK }
          : null,
      };
    });
    const need = all.filter((row) => row.need);
    const filter = s.f || (need.length ? 'need' : 'all');
    const term = s.q.trim();
    const rows = (filter === 'need' ? need : all).filter((row) => !term || row.name.includes(term) || row.id.includes(term));
    const filters = [
      ['need', `확인할 아이 ${need.length}`],
      ['all', `전체 ${all.length}`],
    ].map(([value, label]) => ({ label, cls: filter === value ? 'on' : '', pick: () => this.setState({ f: value }) }));
    return {
      rows,
      filters,
      alert: all.find((row) => row.alert) || null,
      search: s.q,
      setSearch: (e) => this.setState({ q: e.target.value }),
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
        </main>
      </div>
    </div>
  );
}
