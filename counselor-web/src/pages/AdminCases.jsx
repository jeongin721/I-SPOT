// 관리자 · 사례 목록(상담원별 담당 사례 전체)
// 원본: 10/30 디자인 counselor-design/screens/AdminCases.dc.html(다솔 님, frontend261021 브랜치). 관리자 메뉴의 홈 다음.
//
// 서버 연결: useAdminCases(GET /cases 전체 쪽 + GET /auth/users). 값은 src/data/screens/adminCases.ts(adminCasesValues).
//  - 상담원 거르기 · 검색은 받은 목록에서 한다. 담당 상담원을 누르면 상담사 상세(#/AdminStaffDetail?user=)로 간다.
//  - 위험도 · 신고접수일 · 관리 기간 · 최근 상담 · 진행 단계는 서버에 없어 '—' 이고, 위험도 거르기 · 정렬은 준비 중이다.
//  - '관리' 칸(2026-11-03, 디자인에 없어 더함): '상담 이력'(회차 삭제는 거기 '전 회차 보기' 창)과 사례 '삭제'.
//    삭제는 사례 번호를 입력하는 확인 창(components/DeleteConfirmDialog, data/useAdminDelete)을 거치고, 지우면 목록을 다시 부른다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAccountSearch } from '../data/useAccountSearch';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminCases } from '../data/useAdminCases';
import { useAdminDelete } from '../data/useAdminDelete';
import { needsLogin } from '../data/screens/common';
import { adminCasesValues, initialAdminCasesState } from '../data/screens/adminCases';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialAdminCasesState();
  }
  renderVals() {
    return adminCasesValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

function Seg({ label, items, lead, notReady }) {
  return (
    <div role="group" aria-label={label} className="seg">
      {lead ? <span className="ac-lb">{lead}</span> : null}
      {items.map((f) => (
        <button
          key={f.key}
          type="button"
          className={f.cls}
          aria-pressed={f.pressed}
          onClick={f.pick}
          disabled={f.disabled}
          title={f.disabled ? notReady : undefined}
          style={f.disabled ? { opacity: 0.5, cursor: 'not-allowed' } : undefined}
        >
          {f.label}
        </button>
      ))}
    </div>
  );
}

export default function AdminCases(props) {
  const session = useAuthSession();
  // 관리자 훅은 관리자일 때만 서버를 부른다(session.isAdmin).
  const list = useAdminCases(session);
  // 검색어는 계정에 묶는다 — 다른 관리자 계정으로 바뀌면 앞 계정이 친 이름이 남지 않는다(Codex #130 H1).
  const [search, setSearch] = useAccountSearch(session);
  const theme = useTheme();
  const del = useAdminDelete(list.reload);
  const v = useDC(Logic, { ...props, session, list, search, setSearch, askDelete: del.ask });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminCases">
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
        <AdminSidebar active="AdminCases" session={session} />
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
              <div className="sub">상담원별 담당 사례 전체</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>사례 목록</h1>
            </div>
          </header>
          <Notice value={v.notice} />
          {del.done ? (
            <p className="note" role="status" style={{ margin: 0 }}>
              {del.done}
            </p>
          ) : null}

          <section
            aria-label="사례 요약"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            {v.kpis.map((k) => (
              <div key={k.label} className="card kpi">
                <span className="sub">{k.label}</span>
                <b style={{ fontSize: '28px', lineHeight: '1.2' }}>{k.v}</b>
                <span className="note">{k.note}</span>
              </div>
            ))}
          </section>

          <section style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 12px' }}>
              <input
                className="inp"
                type="search"
                aria-label="아동 이름 또는 사례 ID 검색"
                placeholder="아동 이름 · 사례 ID 검색"
                value={v.q}
                onChange={v.setQ}
                style={{ flex: '1 1 240px' }}
              />
              <Seg label="위험도" items={v.riskF} notReady={v.notReady} />
              <Seg label="정렬" lead="정렬" items={v.sortF} notReady={v.notReady} />
            </div>
            <div style={{ alignSelf: 'flex-start' }}>
              <Seg label="담당 상담원" items={v.staffF} notReady={v.notReady} />
            </div>
            {v.usersError ? (
              <p className="note" role="status" style={{ margin: '0' }}>
                {v.usersError} 상담원 거르기는 사례에 적힌 담당자만 보입니다.
              </p>
            ) : null}
          </section>

          <section className="card" aria-label="사례 목록" style={{ overflowX: 'auto' }}>
            <table className="tbl" style={{ minWidth: '1120px' }}>
              <thead>
                <tr>
                  <th scope="col">사례 ID</th>
                  <th scope="col">아동</th>
                  <th scope="col">담당 상담원</th>
                  <th scope="col">위험도</th>
                  <th scope="col">신고접수일</th>
                  <th scope="col">관리 기간</th>
                  <th scope="col">최근 상담</th>
                  <th scope="col">진행 단계</th>
                  <th scope="col">관리</th>
                </tr>
              </thead>
              <tbody>
                {v.rows.map((r) => (
                  <tr key={r.key}>
                    <td className="note">{r.id}</td>
                    <td>
                      <span className="nm" style={{ cursor: 'default' }}>
                        <span className="av" style={{ width: '34px', height: '34px', fontSize: '13px' }}>
                          {r.ini}
                        </span>
                        <span>
                          {r.name} <span className="note">{r.age}</span>
                        </span>
                      </span>
                    </td>
                    <td>{r.whoHref ? <A to={r.whoHref}>{r.who}</A> : r.who}</td>
                    <td className="note">{r.risk}</td>
                    <td className="note">{r.date}</td>
                    <td className="note">{r.period}</td>
                    <td className="note">{r.last}</td>
                    <td>
                      <span className={r.stCls}>{r.stage}</span>
                    </td>
                    <td>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                        <A className="btn btn-sm btn-s" to={r.historyHref}>
                          상담 이력
                        </A>
                        <button
                          type="button"
                          className="btn btn-sm btn-s rm-del"
                          aria-label={`${r.id} 사례 삭제`}
                          onClick={r.del}
                        >
                          삭제
                        </button>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {v.empty ? (
              <p className="note" style={{ margin: '0', padding: '22px', textAlign: 'center' }}>
                조건에 맞는 사례가 없어요.
              </p>
            ) : null}
          </section>
          <p className="note" style={{ margin: '-8px 0 0' }}>
            {v.countLabel ? <>{v.countLabel} · </> : null}
            {v.dataNote}
          </p>
          {del.target ? <DeleteConfirmDialog key={del.target.id} del={del} /> : null}
        </main>
      </div>
    </div>
  );
}
