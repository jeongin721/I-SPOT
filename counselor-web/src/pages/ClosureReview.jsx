// 종결 검토 › ① 전체 상담 내역 검토 (핵심 요약 + 근거 · 확인 후 보고서로)
// 원본: 10/30 디자인 ClosureReview.dc.html(프론트팀 zip). 화면 주소 ?case=<사례 ID>(종결 검토 목록에서 연다).
//
// 서버 연결(2026-10-30): 머리 · 한눈에(상담 횟수 · 유형별 수 · 새 학대 진술) · 회차별 흐름은 useCaseDetail · useSignalHistory ·
// useApprovedSummaries 의 값으로 src/data/screens/closureReview.ts 가 만든다(디자인 칸 → 서버 값은 그 파일 머리).
// 핵심 요약 · 서로 다른 진술(여러 회차를 묶는 AI) · 아이 연계 · 위험수준 척도는 서버에 없어 준비 중 — 실제 사례 옆에 예시 문장을
// 보이지 않는다.
import { Fragment, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useApprovedSummaries } from '../data/useApprovedSummaries';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSignalHistory } from '../data/useSignalHistory';
import { closureReviewValues } from '../data/screens/closureReview';
import { NOT_READY, needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useTheme } from '../theme';
import './ClosureReview.css';

export default function ClosureReview() {
  const session = useAuthSession();
  const theme = useTheme();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const enabled = signedIn(session);
  const detail = useCaseDetail(caseId, { enabled });
  const history = useSignalHistory(caseId, { enabled });
  const approved = useApprovedSummaries(history.sessions, { enabled, max: 100 });
  const [all, setAll] = useState(false);
  const v = closureReviewValues({ caseId, detail, history, approved, all });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-ClosureReview">
      <div
        className={theme.cls}
        style={{
          minHeight: '2300px',
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
            <NotiBell />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/Closure">종결 검토</A> › {v.crumb}
          </nav>
          <Notice value={v.notice ? { text: v.notice } : null} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
            <A className="btn btn-sm btn-s" to="/Closure">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
              </div>
              <div className="note">{v.sub}</div>
            </div>
            <A className="btn btn-s" to={v.historyHref}>
              상담 이력 원본
            </A>
          </header>
          <nav className="steps" aria-label="종결 검토 단계">
            <A className="stp on" to={v.reviewHref} aria-current="step">
              <span className="sn">1</span>
              <b style={{ fontWeight: '700' }}>전체 상담 내역 검토</b>
            </A>
            <A className="stp" to={v.detailHref}>
              <span className="sn">2</span>
              <b style={{ fontWeight: '500' }}>종결보고서 작성</b>
            </A>
          </nav>

          <section
            aria-label="한눈에"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}
          >
            {v.kpis.map((k) => (
              <div key={k.label} className="kpi">
                <span className="note">{k.label}</span>
                <b>{k.value}</b>
                <span className="src">{k.src}</span>
              </div>
            ))}
          </section>

          <section className="card" aria-label="핵심 요약" style={{ padding: '20px 24px' }}>
            <div
              style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px', marginBottom: '4px' }}
            >
              <h2 className="h2">핵심 요약</h2>
            </div>
            <p className="note" style={{ margin: '8px 0 0' }}>
              {v.aiNote}
            </p>
          </section>

          <section
            className="card"
            aria-label="서로 다른 진술"
            style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <h2 className="h2">
              서로 다른 진술{' '}
              <span className="note" style={{ fontWeight: '400' }}>
                합치지 않고 그대로
              </span>
            </h2>
            <p className="note" style={{ margin: 0 }}>
              회차 · 사람마다 다른 진술을 모아 보여 주는 것은 {NOT_READY}입니다(여러 회차를 묶는 AI 가 아직 없음).
            </p>
          </section>

          <section className="card" aria-label="회차별 흐름" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">회차별 흐름</h2>
              {v.canFold ? (
                <button type="button" className="btn btn-sm btn-s" style={{ marginLeft: 'auto' }} onClick={() => setAll(!all)}>
                  {v.tlLabel}
                </button>
              ) : null}
            </div>
            <table className="tbl tl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>회차</th>
                  <th>날짜</th>
                  <th>유형</th>
                  <th>핵심</th>
                  <th>근거</th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b>{r.no}</b>
                      </td>
                      <td className="note">{r.date}</td>
                      <td className="note">{r.kind}</td>
                      <td>{r.key}</td>
                      <td>
                        <span className="src" style={{ margin: '0' }}>
                          {r.src}
                        </span>
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
            {v.flowNote ? (
              <p className="note" style={{ margin: '8px 0 0' }}>
                {v.flowNote}
              </p>
            ) : null}
          </section>

          <section
            className="card"
            aria-label="아이 연계"
            style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <h2 className="h2">아이 연계</h2>
            <p className="note" style={{ margin: 0 }}>
              아이가 쓴 글 · 체크인 응답은 {NOT_READY}입니다(아이 앱이 서버에 없음).
            </p>
          </section>

          <section
            className="card"
            style={{ padding: '18px 22px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}
          >
            <div style={{ flex: '1 1 300px' }}>
              <b>종결보고서 작성</b>
              <span className="note" style={{ display: 'block' }}>
                회차별 흐름을 확인한 뒤 종결보고서(서식 29)를 작성합니다.
              </span>
            </div>
            <A className="btn btn-p" to={v.detailHref}>
              종결보고서 작성 →
            </A>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
