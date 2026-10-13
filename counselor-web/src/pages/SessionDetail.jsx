// 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기)
// 원본: I-SPOT 디자인 캔버스 보드 SessionDetail.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>&session=<회차 ID>. 회차는 useSessionDetail, 사례 별칭 · 다른 회차는
// useCaseDetail 이 부르고, 화면에 쓸 값은 src/data/screens/sessionDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// '다른 회차' 를 누르면 그 회차 주소로 옮긴다. 처리 중이면 끝날 때까지 다시 조회한다.
import { Fragment } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { sessionCaseId, sessionDetailValues } from '../data/screens/sessionDetail';
import './SessionDetail.css';

class Logic extends DCLogic {
  renderVals() {
    return sessionDetailValues(this.props);
  }
}

export default function SessionDetail(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useNavigate();
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-SessionDetail">
      <div
        style={{
          minHeight: '950px',
          background: '#FFFEFA',
          color: '#2F3A44',
          fontFamily: "'Noto Sans KR', sans-serif",
          fontSize: '14px',
          lineHeight: '1.6',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'stretch',
        }}
      >
        <aside className="side" aria-label="주 메뉴">
          <A className="logo" to="/Main">
            <span className="mk">IS</span>
            <b style={{ fontSize: '17px' }}>I-SPOT</b>
          </A>
          <A className="cta" to="/UploadModal">
            ↑ 녹취 · 자료 올리기
          </A>
          <A className="cta2" to="/CaseRegister">
            + 새 사례 등록
          </A>
          <nav className="nav" aria-label="메뉴">
            <A to="/Main">홈</A>
            <A className="on" to="/CaseList">
              사례 관리
            </A>
            <A to="/Schedule">일정</A>
            <A to="/ChildLink">
              아이 연계<span className="cnt">4</span>
            </A>
            <A to="/Closure">
              종결 검토<span className="cnt">2</span>
            </A>
            <A to="/Stats">통계</A>
            <A to="/Settings">설정</A>
          </nav>
          <div className="me">
            <span className="av">{v.meInitial}</span>
            <b style={{ fontWeight: '500' }}>{v.meName}</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }} onClick={v.logout}>
              로그아웃
            </A>
          </div>
        </aside>
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
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> ›{' '}
            <A to={v.historyHref}>상담 이력</A> › {v.cur.no}
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <div className="sub">{v.cur.meta}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '30px', fontWeight: '700' }}>{v.cur.no} · {v.alias}</h1>
            </div>
            <span className={v.cur.st} style={{ height: '28px' }}>
              {v.cur.status}
            </span>
          </header>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <A className="btn btn-sm btn-s" to={v.historyHref}>
              ← 상담 이력
            </A>
            <span className="note" style={{ marginLeft: '6px' }}>
              다른 회차
            </span>
            {(v.picks || []).map((p, pIndex) => (
              <Fragment key={pIndex}>
                <button
                  type="button"
                  className="pick"
                  onClick={p.go}
                  aria-pressed={p.on}
                  style={{ background: p.bg, borderColor: p.bd, color: p.fg, fontWeight: p.fw }}
                >
                  {p.label}
                </button>
              </Fragment>
            ))}
          </section>
          <nav
            aria-label="회차 처리 단계"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
              gap: '18px',
            }}
          >
            {(v.steps || []).map((t, tIndex) => (
              <Fragment key={tIndex}>
                <A className="big" to={t.href} style={{ boxShadow: t.ring, background: t.bg }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <span className="bn" style={{ background: t.nBg, color: t.nFg }}>
                      {t.mark}
                    </span>
                    <b style={{ flex: '1', fontSize: '20px' }}>{t.label}</b>
                    <span className={t.stCls}>{t.st}</span>
                  </span>
                  <span style={{ fontSize: '15px', lineHeight: '1.7' }}>{t.preview}</span>
                </A>
              </Fragment>
            ))}
          </nav>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
