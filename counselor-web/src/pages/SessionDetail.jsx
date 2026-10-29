// 탭 2 › 회차 상세 (1~4단계 처리로 바로 가기)
// 원본: 다솔 님 디자인 counselor-web-design/SessionDetail.dc.html (front_new 브랜치)
//
// 서버 연결: 화면 주소 ?case=<사례 ID>&session=<회차 ID>. 회차는 useSessionDetail, 사례 별칭 · 다른 회차는
// useCaseDetail 이 부르고, 화면에 쓸 값은 src/data/screens/sessionDetail.ts 가 만든다. 이 파일은 훅을 부르고 배치만 한다.
// '다른 회차' 를 누르면 그 회차 주소로 옮긴다. 처리 중이면 끝날 때까지 다시 조회한다.
import { Fragment, useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseDetail } from '../data/useCaseDetail';
import { useSessionDetail } from '../data/useSessionDetail';
import { useFollowupQuestions } from '../data/useFollowupQuestions';
import { needsLogin, signedIn } from '../data/screens/common';
import { readScreenIds } from '../data/screens/links';
import { useScreenGo } from '../data/screens/useScreenGo';
import { sessionCaseId, sessionDetailValues } from '../data/screens/sessionDetail';
import './SessionDetail.css';

class Logic extends DCLogic {
  renderVals() {
    return sessionDetailValues(this.props);
  }
}

/** '다른 회차' 고르기(10/29 디자인 sl-*). 바깥을 누르거나 Esc 면 닫힌다. */
function SessionPick({ label, head, items }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !(wrap.current && wrap.current.contains(e.target))) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);
  return (
    <div className="sl-wrap" ref={wrap}>
      <button
        type="button"
        className="sl-btn"
        aria-haspopup="listbox"
        aria-expanded={open ? 'true' : 'false'}
        onClick={() => setOpen(!open)}
      >
        {label}
        <svg
          className="sl-car"
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6"></path>
        </svg>
      </button>
      {open ? (
        <div className="sl-pop" role="listbox" aria-label="회차 선택">
          <div className="sl-hd">
            회차 선택 <span className="note">{head}</span>
          </div>
          <div className="sl-list">
            {items.map((o) => (
              <button
                key={o.no}
                type="button"
                role="option"
                aria-selected={o.on}
                className={`sl-opt ${o.cls}`}
                onClick={() => {
                  setOpen(false);
                  o.pick();
                }}
              >
                <b className="sl-no">{o.no}</b>
                <span className="sl-meta">{o.meta}</span>
                <span className={o.stCls} style={{ height: '22px', fontSize: '11.5px' }}>
                  {o.st}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function SessionDetail(props) {
  const session = useAuthSession();
  const ids = readScreenIds(useSearchParams()[0]);
  const go = useScreenGo(useNavigate());
  const enabled = signedIn(session);
  const detail = useSessionDetail(ids.sessionId, { enabled });
  const caseDetail = useCaseDetail(sessionCaseId(ids, detail), { enabled });
  const theme = useTheme();
  const questions = useFollowupQuestions(ids.sessionId, { enabled });
  const v = useDC(Logic, { ...props, session, ids, detail, caseDetail, questions, go });
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-SessionDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '950px',
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
            <NotiBell />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › <A to={v.caseHref}>{v.caseLabel}</A> › <A to={v.historyHref}>상담 이력</A>{' '}
            › {v.cur.no}
          </nav>
          <Notice value={v.notice} />
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 300px' }}>
              <div className="sub">{v.cur.meta}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '30px', fontWeight: '700' }}>
                {v.cur.no} · {v.alias}
              </h1>
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
            <SessionPick label={v.pickLabel} head={v.pickHead} items={v.picks || []} />
          </section>
          <nav
            aria-label="회차 처리 단계"
            style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '18px' }}
          >
            {(v.steps || []).map((t, tIndex) => {
              const body = (
                <Fragment>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <span className="bn" style={{ background: t.nBg, color: t.nFg }}>
                      {t.mark}
                    </span>
                    <b style={{ flex: '1', fontSize: '20px' }}>{t.label}</b>
                    <span className={t.stCls}>{t.st}</span>
                  </span>
                  <span style={{ fontSize: '15px', lineHeight: '1.7' }}>{t.preview}</span>
                </Fragment>
              );

              // 앞 단계가 끝나지 않은 칸은 링크가 아니다(sessionDetail.ts 의 locked). 다음 단계로는 그 화면 아래 단추로 간다.
              return t.href ? (
                <A key={tIndex} className="big" to={t.href} style={{ boxShadow: t.ring, background: t.bg }}>
                  {body}
                </A>
              ) : (
                <div
                  key={tIndex}
                  className="big lock"
                  aria-disabled="true"
                  title={t.title}
                  style={{ boxShadow: t.ring, background: t.bg }}
                >
                  {body}
                </div>
              );
            })}
          </nav>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
