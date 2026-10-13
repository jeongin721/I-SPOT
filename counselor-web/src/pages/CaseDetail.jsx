// 탭 1 · 내담자 정보 + 기관 서식 + 종결 검토 등록
// 원본: I-SPOT 디자인 캔버스 보드 CaseDetail.dc.html (자동 변환 후 다듬어 쓰세요)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>. 사례 정보 · 회차는 useCaseDetail 이 부르고, 화면에 쓸 값은
// src/data/screens/caseDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다(피그마 화면이 오면 JSX 만 바꾼다).
// 서버에 없는 값(위험도 · 사례관리대상자 · 신고접수일 · 서비스 · 일정 등)은 '—', 종결 검토 등록은 준비 중.
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { caseDetailValues } from '../data/screens/caseDetail';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import './CaseDetail.css';

class Logic extends DCLogic {
  renderVals() {
    return caseDetailValues(this.props);
  }
}

export default function CaseDetail(props) {
  const session = useAuthSession();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const detail = useCaseDetail(caseId, { enabled: signedIn(session) });
  const v = useDC(Logic, { ...props, session, detail, caseId });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-CaseDetail">
      <div
        style={{
          minHeight: '1350px',
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
            <A to="/CaseList">사례 관리</A> › {v.crumb}
          </nav>
          <Notice value={v.notice} />
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
                <span className="sub">{v.sub}</span>
                <span className="chip c-normal">{v.riskChip}</span>
              </div>
              <div className="note">{v.meta}</div>
            </div>
            <A className="btn btn-s" to={v.uploadHref}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A className="on" aria-current="page" to={v.tabs.detail}>
              내담자 정보
            </A>
            <A to={v.tabs.history}>상담 이력</A>
            <A to={v.tabs.briefing}>상담 전 브리핑</A>
            <A to={v.tabs.app}>아이 연계</A>
            <A to={v.tabs.docs}>문서함</A>
          </nav>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '18px',
            }}
          >
            <section className="card" aria-label="기본 정보" style={{ padding: '22px 24px' }}>
              <h2 className="h2">기본 정보</h2>
              <dl className="kv" style={{ gridTemplateColumns: '120px 1fr' }}>
                {(v.basics || []).map((b, bIndex) => (
                  <Fragment key={bIndex}>
                    <dt>{b.label}</dt>
                    <dd style={b.strong ? { fontWeight: '700' } : undefined}>{b.value}</dd>
                  </Fragment>
                ))}
              </dl>
            </section>
            <section className="card" aria-label="주요 위험 요인" style={{ padding: '22px 24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 className="h2">주요 위험 요인</h2>
                <span className="chip c-normal" style={{ marginLeft: 'auto' }}>
                  {v.riskChip}
                </span>
              </div>
              <div className="note" style={{ marginTop: '4px', textAlign: 'right' }}>
                상담사 지정 · {v.riskBy}
              </div>
              <div className="note" style={{ marginTop: '10px' }}>
                학대 유형
              </div>
              <div style={{ margin: '6px 0 16px', display: 'flex', gap: '6px' }}>
                {(v.abuseTypes || []).map((t, tIndex) => (
                  <span key={tIndex} className="chip c-normal">
                    {t}
                  </span>
                ))}
              </div>
              <div className="note">주요 키워드</div>
              <div style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {(v.keywords || []).map((k, kIndex) => (
                  <span key={kIndex} className="chip c-normal">
                    {k}
                  </span>
                ))}
              </div>
              <div
                style={{
                  marginTop: '14px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <span className="note">사정결과</span>
                <b>{v.assessment}</b>
              </div>
            </section>
          </div>
          <section className="card" aria-label="현재 진행 상황" style={{ padding: '22px 24px' }}>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '16px',
              }}
            >
              <h2 className="h2">현재 진행 상황</h2>
              <span className="note">{v.latestLabel}</span>
              <A className="btn btn-p btn-sm" to={v.continueHref} style={{ marginLeft: 'auto' }}>
                {v.continueLabel}
              </A>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <div
                style={{
                  minWidth: '660px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(5, minmax(0, 1fr))',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: '10%',
                    right: '10%',
                    top: '17px',
                    height: '2px',
                    background: '#E7E0CE',
                  }}
                />
                {(v.progress || []).map((p, pIndex) => (
                  <div key={pIndex} className="st">
                    <span className="sd" style={p.dot}>
                      {p.mark}
                    </span>
                    {p.done ? p.label : null}
                    {p.current ? <b style={{ fontWeight: '700', color: '#2E5687' }}>{p.label}</b> : null}
                    {p.pending ? <span style={{ color: '#6F7880' }}>{p.label}</span> : null}
                    {p.chip ? <span className="chip c-check">{p.chip}</span> : null}
                  </div>
                ))}
              </div>
            </div>
            <div
              style={{
                marginTop: '18px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: '12px',
              }}
            >
              {(v.services || []).map((sv, svIndex) => (
                <div key={svIndex} className="box">
                  <div className="note">{sv.label}</div>
                  <b>{sv.value}</b>
                </div>
              ))}
              <div className="box">
                <div className="note">다음 일정</div>
                <b style={{ fontWeight: '500' }}>{v.nextSchedule}</b>
                <div>
                  <A to={v.briefingHref} style={{ fontSize: '13px' }}>
                    상담 전 브리핑
                  </A>
                </div>
              </div>
            </div>
          </section>
          <section
            className="card"
            aria-label="기관 서식"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <b style={{ flex: '1 1 200px' }}>기관 서식</b>
            <span className="chip c-check">{v.formsChip}</span>
            <A className="btn btn-p" to={v.formsHref}>
              기관 서식 작성
            </A>
          </section>
          <section
            className="card"
            aria-label="종결 검토 등록"
            style={{
              padding: '20px 24px',
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <b style={{ flex: '1 1 200px' }}>종결 검토</b>
            <button
              type="button"
              className="btn btn-y"
              disabled
              title={v.notReady}
              style={{ opacity: 0.5, cursor: 'not-allowed' }}
            >
              종결 검토 등록 · {v.notReady}
            </button>
          </section>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
