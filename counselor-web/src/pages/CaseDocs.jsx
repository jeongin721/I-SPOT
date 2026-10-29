// 탭 4 · 문서함 (기관 서식 6종 + 파일)
// 원본: 다솔 님 디자인 counselor-web-design/CaseDocs.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보 · 회차 목록은 useCaseDetail, 회차마다 녹음 · 원문 · 상담일지는
// useCaseDocuments 가 부르고, 화면에 쓸 값은 src/data/screens/caseDocs.ts(caseDocsValues)가 만든다.
// 기관 서식 작성 기록 · 브리핑 · 외부 문서 올리기는 서버에 없어 준비 중.
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useCaseSignals } from '../data/useCaseSignals';
import { useCaseDocuments } from '../data/useCaseDocuments';
import { caseDocsValues } from '../data/screens/caseDocs';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useTheme } from '../theme';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { f: 'all' };
  }
  renderVals() {
    return caseDocsValues({ ...this.props, filter: this.state.f, setFilter: (f) => this.setState({ f }) });
  }
}

export default function CaseDocs(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const enabled = signedIn(session);
  const detail = useCaseDetail(caseId, { enabled });
  const signals = useCaseSignals(detail, { enabled });
  const docs = useCaseDocuments(caseId, detail.caseInfo ? detail.sessions : null, { enabled });
  const theme = useTheme();
  const v = useDC(Logic, { ...props, session, detail, signals, docs, caseId });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseDocs">
      <div
        className={theme.cls}
        style={{
          minHeight: '1350px',
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
            <A to={v.tabs.briefing}>상담 전 브리핑</A>
            <A className="on" aria-current="page" to={v.tabs.docs}>
              문서함
            </A>
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px' }}>
            <div role="group" aria-label="문서 종류" className="seg">
              {(v.filters || []).map((f, fIndex) => (
                <Fragment key={fIndex}>
                  <button type="button" className={f.cls} onClick={f.pick}>
                    {f.label}
                  </button>
                </Fragment>
              ))}
            </div>
            <span className="note" style={{ marginLeft: 'auto' }}>
              {v.uploadNote}
            </span>
            <A className="btn btn-p" to={v.uploadHref}>
              ↑ 자료 올리기
            </A>
          </section>
          <section className="card" aria-label="기관 서식" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">기관 서식</h2>
              <span className="note" style={{ marginLeft: 'auto' }}>
                {v.formsNote}
              </span>
            </div>
            <table className="tbl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>서식</th>
                  <th>작성 시점</th>
                  <th>최근 작성</th>
                  <th>상태</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(v.forms || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                        <span className="note" style={{ display: 'block' }}>
                          {r.no}
                        </span>
                      </td>
                      <td className="note">{r.when}</td>
                      <td className="note">{r.date}</td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>{r.href ? <A to={r.href}>{r.go}</A> : null}</td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </section>

          <section className="card" aria-label="파일" style={{ overflowX: 'auto' }}>
            <div className="hd">
              <h2 className="h2">녹취 · 일지 · 외부 문서</h2>
            </div>
            <table className="tbl" style={{ minWidth: '680px' }}>
              <thead>
                <tr>
                  <th>파일</th>
                  <th>종류</th>
                  <th>회차</th>
                  <th>날짜</th>
                  <th>상태</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(v.rows || []).map((r, rIndex) => (
                  <Fragment key={rIndex}>
                    <tr>
                      <td>
                        <b style={{ fontWeight: '500' }}>{r.name}</b>
                      </td>
                      <td className="note">{r.kind}</td>
                      <td>{r.ses}</td>
                      <td className="note">{r.date}</td>
                      <td>
                        <span className={r.stCls}>{r.st}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {r.href ? <A to={r.href}>{r.go}</A> : <span className="note">{r.go}</span>}
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
            {v.rowsNote ? (
              <p className="note" style={{ margin: '12px 24px 18px' }}>
                {v.rowsNote}
              </p>
            ) : null}
          </section>
        </main>
      </div>
    </div>
  );
}
