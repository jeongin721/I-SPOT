// 탭 3 · 상담 전 브리핑
// 원본: 10/27 디자인 counselor-design/screens/PreBriefing.dc.html (frontend261021 브랜치).
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 · 회차는 useCaseDetail, 분석이 끝난 가장 최근 회차의 확인 메모 · 위험도는
// useCaseSignals 가 부르고, 화면에 쓸 값은 src/data/screens/preBriefing.ts 가 만든다(디자인 칸 → 서버 값 대응도 그 파일 머리에).
// 이 파일은 훅을 부르고 배치만 한다. 아이 앱 · 회차 비교 · 질문 은행 · 일정은 서버에 없어 준비 중 · '—'.
// 10/27 디자인은 예전 판의 '신변안전 확인' · '그대로 남겨 둔 진술' 칸을 뺐다.
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { preBriefingValues } from '../data/screens/preBriefing';
import './PreBriefing.css';

class Logic extends DCLogic {
  renderVals() {
    return preBriefingValues(this.props);
  }
}

export default function PreBriefing(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const signals = useCaseSignals(detail, { enabled: signedIn(session) });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, detail, signals, caseId });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-PreBriefing">
      <div
        className={theme.cls}
        style={{
          minHeight: '1550px',
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
        <Sidebar active="CaseList" session={session} />
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className={`chip ${v.riskCls}`}>{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <A className="btn btn-s" to={v.uploadHref}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={v.tabs.detail}>내담자 정보</A>
            <A to={v.tabs.history}>상담 이력</A>
            <A className="on" aria-current="page" to={v.tabs.briefing}>
              상담 전 브리핑
            </A>
            <A to={v.tabs.docs}>문서함</A>
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 20px' }}>
            <div style={{ flex: '1 1 380px' }}>
              <div className="sub">{v.lead}</div>
              <h2 style={{ margin: '2px 0 0', fontSize: '22px', fontWeight: '700' }}>상담 전 브리핑</h2>
            </div>
            <button type="button" className="btn btn-s" onClick={v.print}>
              인쇄 · PDF
            </button>
          </section>

          <section
            aria-label="먼저 볼 것"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}
          >
            {(v.firstCards || []).map((c) => (
              <div
                key={c.key}
                className="card"
                style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '4px' }}
              >
                <span className="note">{c.title}</span>
                <span className="src">{c.note}</span>
              </div>
            ))}
          </section>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '18px' }}>
            <section
              className="card"
              aria-label="확인할 사항"
              style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">확인할 사항</h2>
                <span className="chip c-ai">AI 초안</span>
              </div>
              {v.checksNote ? <span className="note">{v.checksNote}</span> : null}
              {(v.checks || []).map((c) => (
                <div key={c.key} className="rq">
                  <span>
                    {c.text}
                    {c.href ? (
                      <A className="src" to={c.href}>
                        근거 · {c.why}
                      </A>
                    ) : (
                      <span className="src">근거 · {c.why}</span>
                    )}
                  </span>
                </div>
              ))}
              {v.checksError ? (
                <span className="note" role="alert" style={{ color: '#A33B2E' }}>
                  {v.checksError}
                </span>
              ) : null}
            </section>
            <section
              className="card"
              aria-label="추가 질문"
              style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: '10px' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">추가 질문</h2>
                <span className="chip c-ai">AI 초안</span>
                {v.questionHref ? (
                  <A to={v.questionHref} style={{ marginLeft: 'auto', fontSize: '13px' }}>
                    질문 수정
                  </A>
                ) : null}
              </div>
              <span className="note">{v.questionNote}</span>
            </section>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
