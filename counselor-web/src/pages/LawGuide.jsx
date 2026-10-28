// 법령 · 매뉴얼
// 원본: 10/27 디자인 counselor-design/screens/LawGuide.dc.html(다솔 님, frontend261021 브랜치).
//
// 서버 연결: POST /law-guide/questions(useLawGuide). 화면에 쓸 값은 src/data/screens/lawGuide.ts(lawGuideValues),
// 참고 자료 목록은 lawGuideRefs.ts.
//  - 'AI에게 묻기' 는 질문 하나에 서버 답변 하나다. 디자인의 키워드 답변(예시) 대신 서버 답변과 근거 조문 칩을 보이고,
//    기다리는 동안 디자인의 점 세 개를 보인다. 오류는 서버 문구를 말풍선으로 보인다.
//  - '업무 단계별 참고사항 · 주요 조문' 은 디자인의 정리 문구를 그대로 보인다(서버 값 아님). 펼침 · 분류는 화면 상태다.
//    '원문보기' · 원문 자료는 국가법령정보센터로 간다.
import { useEffect, useRef } from 'react';
import { Navigate } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useLawGuide } from '../data/useLawGuide';
import { initialLawGuideState, lawGuideValues } from '../data/screens/lawGuide';
import { needsLogin } from '../data/screens/common';
import { useTheme } from '../theme';
import './LawGuide.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = initialLawGuideState();
  }
  renderVals() {
    return lawGuideValues({ ...this.props, state: this.state, setState: (patch) => this.setState(patch) });
  }
}

export default function LawGuide(props) {
  const session = useAuthSession();
  const theme = useTheme();
  const chat = useLawGuide();
  const v = useDC(Logic, { ...props, session, chat });
  // 새 말풍선 · 기다림 점이 생기면 대화 칸을 맨 아래로 내린다(디자인의 _msgScroll). 화면 전체는 움직이지 않는다.
  const msgsRef = useRef(null);
  useEffect(() => {
    const el = msgsRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [v.chat.messages.length, v.chat.pending]);
  // '매뉴얼 목차' 를 누르면 목차 항목을 펼친 뒤 그 줄로 한 번 스크롤한다(디자인의 componentDidUpdate).
  // 디자인의 smooth 대신 바로 옮긴다 — 부드러운 스크롤은 브라우저 · 자동화 환경에 따라 무시된다(.lg-item 의 scroll-margin-top 이 여백).
  useEffect(() => {
    if (!v.scrollTo) return;
    const el = document.getElementById(v.scrollTo);
    if (el) el.scrollIntoView({ block: 'start' });
    v.clearScroll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v.scrollTo]);
  if (needsLogin(session)) return <Navigate to="/Login" replace />;
  return (
    <div className="pg-LawGuide">
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
        <Sidebar active="LawGuide" session={session} />
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
              <div className="sub">{v.sub}</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>{v.title}</h1>
            </div>
          </header>

          <section className="card lg-chat" aria-label="AI에게 묻기">
            <div className="lg-chat-hd">
              <span className="lg-ai" aria-hidden="true">
                AI
              </span>
              <div style={{ flex: '1', minWidth: '0' }}>
                <h2 className="h2">법령 · 매뉴얼 AI에게 묻기</h2>
                <span className="note">{v.chat.lead}</span>
              </div>
              <button type="button" className="btn btn-sm btn-s" onClick={v.chat.reset}>
                새 대화
              </button>
            </div>
            <div className="lg-msgs" aria-live="polite" ref={msgsRef}>
              <div className="lg-msg lg-b">
                <div className="lg-bub">
                  <span style={{ whiteSpace: 'pre-line' }}>{v.chat.intro}</span>
                </div>
              </div>
              {v.chat.messages.map((m) => (
                <div key={m.key} className={`lg-msg ${m.cls}`}>
                  <div className="lg-bub">
                    <span style={{ whiteSpace: 'pre-line' }}>{m.text}</span>
                    {m.hasRefs ? (
                      <div className="lg-refs">
                        <span className="lg-refl">근거</span>
                        {m.laws.map((w, i) =>
                          w.url ? (
                            <a key={`${w.key}-${i}`} className="lg-ref law" href={w.url} target="_blank" rel="noopener noreferrer" title={w.title}>
                              {w.label} ↗
                            </a>
                          ) : (
                            <span key={`${w.key}-${i}`} className="lg-ref law static" title={w.title}>
                              {w.label}
                            </span>
                          ),
                        )}
                        {m.manual.map((r, i) => (
                          <span key={`${r.key}-${i}`} className="lg-ref static">
                            {r.label}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
              {v.chat.pending ? (
                <div className="lg-msg lg-b">
                  <div className="lg-bub lg-typing">
                    <i />
                    <i />
                    <i />
                    <span className="note" style={{ marginLeft: '6px' }}>
                      {v.chat.pendingText}
                    </span>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="lg-sugg">
              {v.chat.suggs.map((q) => (
                <button key={q.label} type="button" className="lg-chip" onClick={q.ask} disabled={v.chat.pending}>
                  {q.label}
                </button>
              ))}
            </div>
            <form
              className="lg-ask"
              onSubmit={(e) => {
                e.preventDefault();
                v.chat.submit();
              }}
            >
              <input
                className="inp"
                type="text"
                placeholder={v.chat.placeholder}
                aria-label="질문 입력"
                value={v.chat.draft}
                maxLength={v.chat.maxLength}
                onChange={(e) => v.chat.setDraft(e.target.value)}
              />
              <button type="submit" className="btn btn-p" disabled={!v.chat.canSend}>
                보내기
              </button>
            </form>
            <p className="note" style={{ margin: '0' }}>
              {v.chat.note}
            </p>
          </section>

          <section className="card lg-refbox" aria-label="업무 단계별 참고사항">
            <div className="lg-ref-hd">
              <div style={{ flex: '1 1 280px' }}>
                <h2 className="h2">업무 단계별 참고사항 · 주요 조문</h2>
                <span className="note">{v.refsLead}</span>
              </div>
              <div className="lg-src">
                <span className="note">원문 자료</span>
                <button type="button" className="lg-chip" onClick={v.openToc}>
                  매뉴얼 목차
                </button>
                {v.sources.map((s) => (
                  <a key={s.url} className="lg-chip" href={s.url} target="_blank" rel="noopener noreferrer">
                    {s.label} ↗
                  </a>
                ))}
              </div>
            </div>
            <div className="lg-filter">
              <div className="seg" role="group" aria-label="분류">
                {v.filters.map((p) => (
                  <button key={p.key} type="button" className={p.cls} aria-pressed={p.pressed} onClick={p.pick}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            {v.refs.map((r) => (
              <div key={r.id} className={`lg-item ${r.cls}`} id={r.domId}>
                <button type="button" className="lg-row" aria-expanded={r.open} onClick={r.toggle}>
                  <span className={`lg-step ${r.stepCls}`}>{r.step}</span>
                  <span className="lg-tt">
                    <b>{r.title}</b>
                    <span className="note">{r.sum}</span>
                  </span>
                  <span className="lg-pg">{r.pages}</span>
                  <span className="lg-chev" aria-hidden="true">
                    ⌄
                  </span>
                </button>
                {r.open ? (
                  <div className="lg-body">
                    <ul>
                      {r.items.map((it, index) => (
                        <li key={index}>{it}</li>
                      ))}
                    </ul>
                    <div className="lg-refs">
                      <span className="lg-refl">근거</span>
                      <span className="lg-ref static">{r.pages}</span>
                      {r.laws.map((w, index) => (
                        <a key={`${w.label}-${index}`} className="lg-ref law" href={w.url} target="_blank" rel="noopener noreferrer">
                          {w.label} ↗
                        </a>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ))}
          </section>
          <p className="ainote">{v.footNote}</p>
        </main>
      </div>
    </div>
  );
}
