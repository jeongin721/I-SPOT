// 관리자 · 통계 · 보고(기관 단위)
// 원본: 다솔 님 10/21 디자인 counselor-design/screens/AdminStats.dc.html (origin/frontend261021)
//
// 서버 연결: useCaseOverview(기관 전체 사례 + 사례마다 회차) · useAdminAccounts(상담원 목록). 값은 src/data/screens/adminStats.ts.
// 지금 셀 수 있는 것: 기간 안 사례 등록(등록일 기준 — 신고접수일 아님) · 등록 추이, 기간 안 상담 회차, 지금 종결 수,
// 상담원별 지금 담당 · 기간 안 회차 · 지금 종결, 아동 연령대(출생연도 기준). 나머지 보고 항목 · 엑셀 · PDF 는 준비 중이다.
// 관리자 계정만 본다: 로그인하지 않았으면 로그인 화면으로, 상담원 계정이면 안내만 보인다(훅도 서버를 부르지 않는다).
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import AdminSidebar, { AdminBlocked } from '../components/AdminSidebar';
import Notice from '../components/Notice';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useAdminAccounts } from '../data/useAdminAccounts';
import { useCaseOverview } from '../data/useCaseOverview';
import { needsLogin } from '../data/screens/common';
import { adminOnly } from '../data/screens/admin';
import { INITIAL_ADMIN_STATS_UI, adminStatsValues } from '../data/screens/adminStats';
import './Admin.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = INITIAL_ADMIN_STATS_UI;
  }
  renderVals() {
    return adminStatsValues({ ...this.props, ui: this.state, setUi: (patch) => this.setState(patch) });
  }
}

// 서버에 원천 데이터가 없어 제목 · 안내만 보이는 카드.
function PendingCard({ c, notReady }) {
  return (
    <section
      className="card"
      aria-label={c.title}
      style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
        <h2 className="h2">{c.title}</h2>
        {c.note ? <span className="note">{c.note}</span> : null}
      </div>
      <p className="sub" style={{ margin: '0' }}>
        {notReady} · {c.text}
      </p>
    </section>
  );
}

export default function AdminStats(props) {
  const session = useAuthSession();
  // 사례 모음 훅은 enabled 조건이 없어, 관리자가 아니면 '확인 중' 으로 넘겨 부르지 않게 한다(adminOnly).
  const overview = useCaseOverview(adminOnly(session), 'sessions');
  const accounts = useAdminAccounts(session);
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, overview, accounts });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  if (!session.isAdmin) return <AdminBlocked session={session} />;
  return (
    <div className="pg-Admin pg-AdminStats">
      <div
        className={theme.cls}
        style={{
          minHeight: '2400px',
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
        <AdminSidebar active="AdminStats" session={session} />
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
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>통계 · 보고</h1>
              <p className="sub" style={{ margin: '4px 0 0' }}>
                {v.scopeLabel}
              </p>
            </div>
            <button type="button" className="btn btn-s" disabled title={v.notReady}>
              엑셀로 내려받기 · {v.notReady}
            </button>
            <button type="button" className="btn btn-p" disabled title={v.notReady}>
              보고서 PDF 만들기 · {v.notReady}
            </button>
          </header>
          <Notice value={v.notice} />

          <section
            className="card"
            aria-label="기간 선택"
            style={{ padding: '14px 18px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}
          >
            <div role="group" aria-label="기간" className="seg">
              {v.periods.map((f) => (
                <button key={f.key} type="button" className={f.cls} aria-pressed={f.pressed} onClick={f.pick}>
                  {f.label}
                </button>
              ))}
            </div>
            <span className="note" style={{ marginLeft: 'auto' }}>
              {v.rangeLabel}
            </span>
          </section>

          <section
            aria-label="핵심 지표"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(136px, 1fr))', gap: '12px' }}
          >
            {v.kpis.map((k) => (
              <div key={k.label} className="card kpi sm-k">
                <span className="sub">{k.label}</span>
                <b>{k.v}</b>
                <span className="note">{k.sub}</span>
              </div>
            ))}
          </section>

          <section className="card" aria-label="사례 등록 추이" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 16px' }}>
              <h2 className="h2">사례 등록 · 종결 추이</h2>
              <span className="lg">
                <i style={{ background: '#C2A36B' }}></i>사례 등록(등록일 기준)
              </span>
              <span className="lg">
                <i style={{ background: '#2B2A26' }}></i>종결 · {v.notReady}(종결일 없음)
              </span>
            </div>
            <div className="vb" style={{ marginTop: '16px' }} role="img" aria-label={v.trendAria}>
              {v.trend.map((t) => (
                <div key={t.key} className="col" title={t.tip}>
                  <div className="bx">
                    <span>{t.a}</span>
                    <span className="b" style={{ height: t.ha, background: '#C2A36B' }}></span>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '10px', padding: '6px 4px 0' }}>
              {v.trend.map((t) => (
                <span
                  key={t.key}
                  className="note"
                  style={{ flex: '1', minWidth: '0', textAlign: 'center', whiteSpace: 'nowrap', overflow: 'hidden' }}
                >
                  {t.label}
                </span>
              ))}
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <PendingCard c={v.pendingTypes} notReady={v.notReady} />
            <PendingCard c={v.pendingRisk} notReady={v.notReady} />
          </div>

          <section className="card" aria-label="상담원별" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">상담원별</h2>
              <span className="note">{v.periodLabel}</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '860px' }}>
                <thead>
                  <tr>
                    <th scope="col">상담원</th>
                    <th scope="col">현재 담당 사례</th>
                    <th scope="col" style={{ width: '24%' }}>
                      상담 회차
                    </th>
                    <th scope="col">일지 기한 내 작성률</th>
                    <th scope="col">종결(지금)</th>
                  </tr>
                </thead>
                <tbody>
                  {v.staffText ? (
                    <tr>
                      <td colSpan={5} className="note" style={{ textAlign: 'center', padding: '24px 12px' }}>
                        {v.staffText}
                      </td>
                    </tr>
                  ) : null}
                  {(v.staffText ? [] : v.staff).map((r) => (
                    <tr key={r.key}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                        <span className="note" style={{ display: 'block' }}>
                          {r.rank}
                        </span>
                      </td>
                      <td>{r.cases}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span className="mini" style={{ flex: '1' }}>
                            <span style={{ width: r.w }}></span>
                          </span>
                          <b style={{ width: '40px' }}>{r.ses}</b>
                        </div>
                      </td>
                      <td title={v.notReady}>{r.rate}</td>
                      <td>{r.closed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="note" style={{ margin: '0', padding: '12px 22px 16px' }}>
              {v.staffNote} 일지 기한 내 작성률은 {v.notReady}입니다(기한 정의 없음).
            </p>
          </section>

          <div className="g3">
            <section
              className="card"
              aria-label="아동 연령대별"
              style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
                <h2 className="h2">아동 연령대별</h2>
                <span className="note">기간 안 등록 사례 · 출생연도로 센 나이</span>
              </div>
              {v.ages.map((g) => (
                <div key={g.key} className="hb sm" title={g.tip}>
                  <span>{g.name}</span>
                  <span className="track">
                    <span style={{ width: g.w }}></span>
                  </span>
                  <span className="note" style={{ color: '#2B2A26' }}>
                    {g.v} · {g.p}
                  </span>
                </div>
              ))}
              {v.ageNote ? <span className="note">{v.ageNote}</span> : null}
            </section>
            {v.pendingMore.map((c) => (
              <PendingCard key={c.title} c={c} notReady={v.notReady} />
            ))}
          </div>

          <p className="note" style={{ margin: '0' }}>
            기관 전체 사례 기준입니다. 사례 등록일은 신고접수일이 아닙니다. {v.notReady} 항목은 원천 데이터 · 지표 정의가 팀 결정
            전입니다.
            {v.notesText ? ` ${v.notesText}` : ''}
          </p>
        </main>
      </div>
    </div>
  );
}
