// 통계 (기간 직접 선택 · 원형 · 가로/세로 막대 · 표)
// 원본: 다솔 님 디자인 counselor-web-design/Stats.dc.html (front_new 브랜치)
//
// 서버 연결: 사례 · 회차는 useCaseOverview(사례마다 회차 목록을 모음), 화면에 쓸 값은 src/data/screens/stats.ts(statsValues).
// 11/02 디자인(지역별 통계 · 사례관리 기간 추가)으로 맞췄다. 신고 접수(신고접수일) · 연령 비율(출생연도) · 사례관리 기간
// (사례연계일 · 담당 상담원) · 상담 서비스(상담 회차)는 서버 값으로 세고, 학대 판단 · 재신고 · 유형 · 행위자 · 지역 · AI 요약은 준비 중.
// 10/21 디자인(counselor-design/screens/Stats.dc.html): 기간 프리셋 순서(전체 · 이번 달 · 최근 3개월 · 직접 선택),
// 시작 · 종료일을 글자 입력 + 연 → 월 → 일 팝업으로(components/StatsDateField.jsx). 치는 중인 글자는 셈에 넣지 않고
// 올바른 날짜가 되었을 때만 기간에 넣는다(stats.ts). 기존 '달력'(기간을 두 번 눌러 고르기)도 디자인대로 남겼다.
import { Fragment } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import Notice from '../components/Notice';
import NotiBell from '../components/NotiBell';
import Sidebar from '../components/Sidebar';
import StatsDateField from '../components/StatsDateField';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseOverview } from '../data/useCaseOverview';
import { needsLogin } from '../data/screens/common';
import { initialStatsState, statsValues } from '../data/screens/stats';
import { useTheme } from '../theme';
import './Stats.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialStatsState();
  }
  renderVals() {
    return statsValues({ ...this.props, ui: this.state, setUi: (patch) => this.setState(patch) });
  }
}

export default function Stats(props) {
  const session = useAuthSession();
  const overview = useCaseOverview(session, 'sessions');
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, overview });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  const k = v.k || {};
  return (
    <div className="pg-Stats">
      <div
        className={theme.cls}
        style={{
          minHeight: '1990px',
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
        <Sidebar active="Stats" session={session} />
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
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>통계</h1>
            </div>
          </header>
          <Notice value={v.notice} />
          <p className="note" style={{ margin: '-8px 0 0' }}>
            {v.scopeLabel}
            {(v.notes || []).map((t, tIndex) => (
              <Fragment key={tIndex}> · {t}</Fragment>
            ))}
          </p>

          <section
            className="card"
            aria-label="기간 선택"
            style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 14px' }}>
              <div role="group" aria-label="빠른 기간" className="seg">
                {(v.presets || []).map((p, pIndex) => (
                  <Fragment key={pIndex}>
                    <button type="button" className={p.cls} onClick={p.pick}>
                      {p.label}
                    </button>
                  </Fragment>
                ))}
              </div>
              <StatsDateField label="시작" name="시작일" field={v.fromField} />
              <span className="note">~</span>
              <StatsDateField label="종료" name="종료일" field={v.toField} align="end" />
              <button type="button" className={`btn btn-sm ${v.calCls}`} onClick={v.toggleCal}>
                달력
              </button>
              <span className="brn" style={{ marginLeft: 'auto', fontWeight: '700' }}>
                {v.rangeLabel}
              </span>
            </div>
            {v.dateHint ? (
              <p className="note" role="status" style={{ margin: '0' }}>
                {v.dateHint}
              </p>
            ) : null}
            {v.showCal ? (
              <>
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '24px',
                    paddingTop: '6px',
                    borderTop: '1px solid #EAE7DF',
                  }}
                >
                  <div style={{ flex: '0 1 320px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calPrev} aria-label="이전 달">
                        ‹
                      </button>
                      <b style={{ flex: '1', textAlign: 'center' }}>{v.calLabel}</b>
                      <button type="button" className="btn btn-sm btn-s" onClick={v.calNext} aria-label="다음 달">
                        ›
                      </button>
                    </div>
                    <div className="cal note" style={{ textAlign: 'center', marginBottom: '2px' }}>
                      <span>일</span>
                      <span>월</span>
                      <span>화</span>
                      <span>수</span>
                      <span>목</span>
                      <span>금</span>
                      <span>토</span>
                    </div>
                    <div className="cal">
                      {(v.cal || []).map((d, dIndex) => (
                        <Fragment key={dIndex}>
                          <button
                            type="button"
                            onClick={d.pick}
                            disabled={d.off}
                            aria-label={d.aria}
                            style={{ background: d.bg, color: d.fg, fontWeight: d.fw }}
                          >
                            {d.n}
                          </button>
                        </Fragment>
                      ))}
                    </div>
                  </div>
                  <p className="note" style={{ flex: '1 1 220px', margin: '0', alignSelf: 'center' }}>
                    {v.pickHint}
                  </p>
                </div>
              </>
            ) : null}
          </section>

          <section
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}
          >
            <div className="card kpi">
              <div className="sub">신고 접수</div>
              <b className="brn">{k.total}건</b>
              <div className="note">하루 평균 {k.perDay}건</div>
            </div>
            <div className="card kpi">
              <div className="sub">학대 판단 사례</div>
              <b className="brn">{k.judged}건</b>
              <div className="note">접수 중 {k.judgedPct}</div>
            </div>
            <div className="card kpi">
              <div className="sub">재신고 사례</div>
              <b className="brn">{k.repeat}건</b>
            </div>
            <div className="card kpi">
              <div className="sub">서비스 제공</div>
              <b className="brn">{k.services}회</b>
              <div className="note">완료율 {k.donePct}</div>
            </div>
          </section>

          <section className="card" aria-label="신고 접수" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px' }}>
              <h2 className="h2">신고 접수 추이</h2>
              <span className="note">{v.binLabel}</span>
            </div>
            <div className="vb" style={{ marginTop: '14px' }} role="img" aria-label={v.trendAria}>
              {(v.trend || []).map((t, tIndex) => (
                <div key={tIndex} className="col" title={t.tip}>
                  <span className="note" style={{ color: '#2B2A26' }}>
                    {t.v}
                  </span>
                  <span className="b" style={{ height: t.h }}></span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
              {(v.trend || []).map((t, tIndex) => (
                <span
                  key={tIndex}
                  className="note"
                  style={{ flex: '1', minWidth: '0', textAlign: 'center', overflow: 'hidden', whiteSpace: 'nowrap' }}
                >
                  {t.label}
                </span>
              ))}
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section
              className="card"
              aria-label="학대 유형별 사례 수"
              style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
            >
              <h2 className="h2">학대 유형별 사례 수</h2>
              {(v.types || []).map((g, gIndex) => (
                <div key={gIndex} className="hb" title={g.tip}>
                  <span>{g.name}</span>
                  <span className="track">
                    <span style={{ width: g.w }}></span>
                  </span>
                  <span className="note" style={{ color: '#2B2A26' }}>
                    {g.v}건 · {g.p}
                  </span>
                </div>
              ))}
              {(v.types || []).length === 0 ? (
                <p className="note" style={{ margin: '0' }}>
                  {v.pendingNote}
                </p>
              ) : null}
            </section>

            <section className="card" aria-label="아동 연령 비율" style={{ padding: '20px 22px' }}>
              <h2 className="h2">학대 피해 아동 연령 비율</h2>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '22px', marginTop: '12px' }}>
                <svg viewBox="0 0 200 200" width="190" height="190" role="img" aria-label={v.ageAria}>
                  {(v.ages || []).map((a, aIndex) => (
                    <path key={aIndex} d={a.d} fill={a.c} stroke="#FFFFFF" strokeWidth="2">
                      <title>{a.tip}</title>
                    </path>
                  ))}
                </svg>
                <div style={{ flex: '1 1 160px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(v.ages || []).map((a, aIndex) => (
                    <div key={aIndex} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <span
                        style={{ width: '12px', height: '12px', borderRadius: '3px', background: a.c, flex: 'none' }}
                      ></span>
                      <span style={{ flex: '1' }}>{a.name}</span>
                      <b>{a.p}</b>
                      <span className="note" style={{ width: '44px', textAlign: 'right' }}>
                        {a.v}명
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>

          <section className="card" aria-label="학대 행위자 상황" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">학대 행위자 상황</h2>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '700px' }}>
                <thead>
                  <tr>
                    <th>아동과의 관계</th>
                    <th>건수</th>
                    <th style={{ width: '26%' }}>비율</th>
                    <th>가장 많이 확인된 상황</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.actors || []).map((r, rIndex) => (
                    <tr key={rIndex}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                      </td>
                      <td>{r.v}건</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span className="mini" style={{ flex: '1' }}>
                            <span style={{ width: r.w }}></span>
                          </span>
                          <span className="note" style={{ width: '44px' }}>
                            {r.p}
                          </span>
                        </div>
                      </td>
                      <td>{r.top}</td>
                    </tr>
                  ))}
                  {(v.actors || []).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="note">
                        {v.pendingNote}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card" aria-label="지역별 통계" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">지역별 통계</h2>
              <span className="note">아동 거주 구 기준 · 보호자가 다른 기관 관할에 살면 두 기관이 공동사례관리</span>
              <span className="note" style={{ marginLeft: 'auto' }}>
                {v.rgSum}
              </span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tbl" style={{ minWidth: '760px' }}>
                <thead>
                  <tr>
                    <th>아동 거주 지역</th>
                    <th>관할 기관</th>
                    <th>사례 수</th>
                    <th style={{ width: '22%' }}>비율</th>
                    <th>보호자 타 지역 거주</th>
                    <th>공동사례관리</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.regions || []).map((r, rIndex) => (
                    <tr key={rIndex}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                      </td>
                      <td className="note">{r.org}</td>
                      <td>{r.v}건</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span className="mini" style={{ flex: '1' }}>
                            <span style={{ width: r.w }}></span>
                          </span>
                          <span className="note" style={{ width: '44px' }}>
                            {r.p}
                          </span>
                        </div>
                      </td>
                      <td>{r.away}건</td>
                      <td>
                        <b className="brn">{r.joint}건</b>
                      </td>
                    </tr>
                  ))}
                  {(v.regions || []).length === 0 ? (
                    <tr>
                      <td colSpan={6} className="note">
                        {v.regionNote}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            <div
              style={{
                padding: '16px 22px 20px',
                borderTop: '1px solid #EAE7DF',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <b style={{ fontSize: '14px' }}>공동사례관리 현황</b>
              {(v.joints || []).map((j, jIndex) => (
                <div key={jIndex} className="rg-pair">
                  <span>
                    <b style={{ fontWeight: '500' }}>아동</b> {j.cg} · {j.co}
                  </span>
                  <span className="note" aria-hidden="true">
                    ↔
                  </span>
                  <span>
                    <b style={{ fontWeight: '500' }}>보호자</b> {j.pg} · {j.po}
                  </span>
                  <b className="brn" style={{ marginLeft: 'auto' }}>
                    {j.v}건
                  </b>
                </div>
              ))}
              {v.noJoint ? <span className="note">이 기간 공동사례관리 사례 없음</span> : null}
              {(v.joints || []).length === 0 && !v.noJoint ? <span className="note">{v.regionNote}</span> : null}
            </div>
          </section>

          <section className="card" aria-label="사례관리 기간" style={{ overflow: 'hidden' }}>
            <div className="hd">
              <h2 className="h2">사례관리 기간</h2>
              <span className="note">{v.mgAsOf} 기준 관리 중 사례</span>
              <label className="rg-std">
                <span>1인당 적정 사례 수</span>
                <input
                  className="inp"
                  type="number"
                  min="1"
                  max="99"
                  value={v.mgStd}
                  onChange={v.setMgStd}
                  aria-label="1인당 적정 사례 수"
                />
                <span>건</span>
              </label>
            </div>
            <div
              style={{
                padding: '18px 22px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '12px',
              }}
            >
              {(v.mgKpi || []).map((m, mIndex) => (
                <div key={mIndex} className="rg-kpi">
                  <div className="sub">{m.label}</div>
                  <b className="brn" style={{ fontSize: '24px' }}>
                    {m.v}
                  </b>
                  <div className="note">{m.note}</div>
                </div>
              ))}
            </div>
            <div style={{ padding: '0 22px 18px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {(v.mgBins || []).map((g, gIndex) => (
                <div key={gIndex} className="hb" style={{ gridTemplateColumns: '110px 1fr 96px' }} title={g.tip}>
                  <span>{g.name}</span>
                  <span className="track">
                    <span style={{ width: g.w }}></span>
                  </span>
                  <span className="note" style={{ color: '#2B2A26' }}>
                    {g.v}건 · {g.p}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ overflowX: 'auto', borderTop: '1px solid #EAE7DF' }}>
              <table className="tbl" style={{ minWidth: '720px' }}>
                <thead>
                  <tr>
                    <th>상담원</th>
                    <th>관리 중</th>
                    <th style={{ width: '26%' }}>적정 사례 수 대비</th>
                    <th>6개월 이상</th>
                    <th>1년 이상</th>
                    <th>평균 기간</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.mgStaff || []).map((r, rIndex) => (
                    <tr key={rIndex}>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                      </td>
                      <td>{r.v}건</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span className="mini" style={{ flex: '1' }}>
                            <span style={{ width: r.w, background: r.bar }}></span>
                          </span>
                          <span className={`chip ${r.cls}`} style={{ height: '22px', fontSize: '11.5px' }}>
                            {r.state}
                          </span>
                        </div>
                      </td>
                      <td>{r.m6}건</td>
                      <td>{r.y1}건</td>
                      <td>{r.avg}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}>
            <section className="card" aria-label="서비스 제공 현황" style={{ padding: '20px 22px' }}>
              <h2 className="h2">서비스 제공 현황</h2>
              <div className="vb" style={{ marginTop: '14px', height: '200px' }} role="img" aria-label={v.svcAria}>
                {(v.svc || []).map((t, tIndex) => (
                  <div key={tIndex} className="col" title={t.tip}>
                    <span className="note" style={{ color: '#2B2A26' }}>
                      {t.v}
                    </span>
                    <span className="b" style={{ height: t.h }}></span>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: '8px', padding: '6px 4px 0' }}>
                {(v.svc || []).map((t, tIndex) => (
                  <span
                    key={tIndex}
                    className="note"
                    style={{ flex: '1', minWidth: '0', textAlign: 'center', lineHeight: '1.3' }}
                  >
                    {t.label}
                  </span>
                ))}
              </div>
            </section>
            <section className="card" aria-label="서비스 진행 표" style={{ overflow: 'hidden' }}>
              <div className="hd">
                <h2 className="h2">서비스 진행 상태</h2>
              </div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>서비스</th>
                    <th>대상</th>
                    <th>완료</th>
                    <th>진행 중</th>
                    <th>완료율</th>
                  </tr>
                </thead>
                <tbody>
                  {(v.svc || []).map((t, tIndex) => (
                    <tr key={tIndex}>
                      <td>{t.label}</td>
                      <td className="note">{t.target}</td>
                      <td>{t.done}</td>
                      <td>{t.ing}</td>
                      <td>
                        <b className="brn">{t.rate}</b>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </div>

          <section
            className="card"
            aria-label="AI 분석"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">AI가 본 이 기간</h2>
              <span className="chip c-ai">AI 초안</span>
            </div>
            {(v.insights || []).map((t, tIndex) => (
              <div key={tIndex} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#DAD5C9',
                    marginTop: '8px',
                    flex: 'none',
                  }}
                ></span>
                <span>{t}</span>
              </div>
            ))}
            {(v.insights || []).length === 0 ? (
              <p className="note" style={{ margin: '0' }}>
                {v.notReadyNote}
              </p>
            ) : null}
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
