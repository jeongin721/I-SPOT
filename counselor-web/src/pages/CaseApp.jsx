// 내담자 정보 › 아이 연계 (아이 상세와 같은 화면). 10/21 디자인에서 탭에서 빠지고 '아이 연계 →' 단추로 들어온다
// 원본: 다솔 님 디자인 counselor-web-design/CaseApp.dc.html (front_new 브랜치). 화면 값은 아직 예시(가상) 데이터다.
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCarryHref } from '../data/useCarryHref';
import { useTheme } from '../theme';
import './CaseApp.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { qok: {}, qe: {}, qEdit: null, dText: '', dOpts: '', ne: {}, nEdit: null, nText: '' };
  }
  renderVals() {
    const K = {
      name: '이서윤',
      short: '서윤',
      ini: '이',
      age: '13세',
      types: '신체 · 정서',
      id: 'C-2026-0351',
      reason: '아이가 보낸 말',
      rCls: 'chip c-sky',
      last: '어제 22:10',
      count: '19 / 21일',
      next: '오늘 16:00 9회차',
      urgent: false,
      quote: '다음 상담 때 말할 게 있어요',
      quoteAt: '어제 22:10',
      answers: [
        ['공통 1', '어젯밤 잘 잤어?', '괜찮았어', false],
        ['공통 2', '어제 누가 아프게 한 적 있어?', '없어', false],
        ['공통 3', '오늘 기분은?', '조금 걱정돼', true],
        ['QB-E-05', '누가 "말하면 혼난다"처럼 겁을 준 적 있어?', '1번', true],
        ['유형 P-2', '몸에 다친 곳 있어?', '없어', false],
        ['유형 E-3', '집에 있을 때 마음은?', '조금 불편해', false],
      ],
      flags: [
        {
          q: '누가 "말하면 혼난다"처럼 겁을 준 적 있어? (QB-E-05)',
          flow: ['없어', '없어', '없어', '1번'],
          src: '10/6 응답 · 8회차 01:08',
          qi: [0],
        },
        {
          q: '오늘 기분은? (공통 3)',
          flow: ['보통', '보통', '조금 걱정돼', '조금 걱정돼'],
          src: '공통 3 · 최근 2주 12회',
          qi: [1],
        },
      ],
      notes: [
        '8회차 상담에서 나온 함구 요구 진술과 같은 내용이 체크인에서 처음 나왔어요.',
        '2주째 "조금 걱정돼"가 이어지고 있어요. 아이가 보낸 말과 함께 다음 상담 시작에서 다뤄 보세요.',
      ],
      qs: [
        {
          id: 'QB-E-06',
          text: '그런 말을 들었을 때 어떤 마음이었어?',
          opts: ['무서웠어', '괜찮았어', '잘 모르겠어', '말하기 어려워'],
          why: 'QB-E-05 응답',
          sendNote: '오늘 저녁 발송',
        },
        {
          id: 'QB-E-07',
          text: '걱정되는 일이 있을 때 누구에게 말할 수 있어?',
          opts: ['선생님', '가족', '친구', '없어', '말하기 어려워'],
          why: '공통 3 응답 흐름',
          sendNote: '오늘 저녁 발송',
        },
      ],
    };
    const s = this.state;
    const hasOptsAt = (i) => (K.qs.at(i).opts || []).length > 0;

    const mkQs = (list) =>
      list.map((q0, i) => {
        const cur = s.qe[i] || {};
        const text = cur.text || q0.text;
        const opts = cur.opts || q0.opts || [];
        const ok = !!s.qok[i],
          editing = s.qEdit === i;
        return {
          id: q0.id,
          why: q0.why,
          text,
          opts,
          hasOpts: opts.length > 0,
          edited: !!cur.text || !!cur.opts,
          st: ok ? (q0.sendNote ? '승인됨 · ' + q0.sendNote : '승인됨') : 'AI 초안',
          stCls: ok ? 'chip c-sel' : 'chip c-ai',
          ring: editing ? 'inset 0 0 0 2px #2B2A26' : 'none',
          okCls: ok ? 'btn-p' : 'btn-s',
          okLabel: ok ? '승인됨 ✓' : '승인',
          isEdit: editing,
          notEdit: !editing,
          draftText: s.dText,
          draftOpts: s.dOpts,
          approve: () => this.setState({ qok: { ...s.qok, [i]: !ok } }),
          startEdit: () => this.setState({ qEdit: i, dText: text, dOpts: opts.join(', ') }),
          setText: (e) => this.setState({ dText: e.target.value }),
          setOpts: (e) => this.setState({ dOpts: e.target.value }),
          save: () =>
            this.setState({
              qEdit: null,
              qok: { ...s.qok, [i]: false },
              qe: {
                ...s.qe,
                [i]: {
                  text: s.dText,
                  opts: hasOptsAt(i)
                    ? s.dOpts
                        .split(',')
                        .map((x) => x.trim())
                        .filter(Boolean)
                    : null,
                },
              },
            }),
          cancel: () => this.setState({ qEdit: null }),
        };
      });
    const mkNotes = (list) =>
      list.map((n0, i) => {
        const text = s.ne[i] || n0;
        const editing = s.nEdit === i;
        return {
          text,
          edited: s.ne[i] !== undefined,
          isEdit: editing,
          notEdit: !editing,
          draft: s.nText,
          startEdit: () => this.setState({ nEdit: i, nText: text }),
          setDraft: (e) => this.setState({ nText: e.target.value }),
          save: () => this.setState({ nEdit: null, ne: { ...s.ne, [i]: s.nText } }),
          cancel: () => this.setState({ nEdit: null }),
        };
      });

    const answers = K.answers.map((a) => ({
      id: a[0],
      q: a[1],
      ans: a[2],
      fw: a[3] ? 700 : 500,
      bg: a[3] ? '#F7F6F2' : 'transparent',
      flagText: a[3] ? '확인 필요' : '',
    }));
    const notes = mkNotes(K.notes);
    const allQs = mkQs(K.qs);
    const flags = K.flags.map((f, i) => ({
      q: f.q,
      src: f.src,
      n: notes.at(i),
      qs: (f.qi || []).map((j) => allQs.at(j)),
      flow: f.flow.map((t, j) => ({ t, cls: j === f.flow.length - 1 ? 'v now' : 'v' })),
    }));
    return { k: { ...K, hasQuote: !!K.quote }, answers, flags, flagCount: flags.length };
  }
}

export default function CaseApp(props) {
  // 사이드바의 내 정보 · 로그아웃 · '관리자 메뉴'(관리자일 때만)에만 쓴다. 이 화면의 값은 아직 예시 데이터다.
  const session = useAuthSession();
  const carry = useCarryHref();
  const theme = useTheme();
  const v = useDC(Logic, props);
  return (
    <div className="pg-CaseApp">
      <div
        className={theme.cls}
        style={{
          minHeight: '1650px',
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
            <A to="/CaseList">사례 관리</A> › 이서윤 C-2026-0351
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '14px 18px' }}>
            <A className="btn btn-sm btn-s" to="/CaseList">
              ← 목록
            </A>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>이서윤</h1>
                <span className="sub">13세 · 중1</span>
                <span className="chip c-hi">위험도 상</span>
              </div>
              <div className="note">C-2026-0351 · 다음 상담 오늘 16:00</div>
            </div>
            <A className="btn btn-s" to={carry('/UploadModal')}>
              ↑ 녹취 올리기
            </A>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={carry('/CaseDetail')}>내담자 정보</A>
            <A to={carry('/CaseHistory')}>상담 이력</A>
            <A to={carry('/CaseDocs')}>문서함</A>
          </nav>
          {v.k.hasQuote ? (
            <>
              <section aria-label="아이가 쓴 글" className="quote">
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                  <b style={{ fontSize: '15px' }}>아이가 쓴 글</b>
                  <span style={{ fontSize: '12px' }}>{v.k.quoteAt}</span>
                </div>
                <div style={{ fontSize: '24px', fontWeight: '700', lineHeight: '1.5' }}>"{v.k.quote}"</div>
              </section>
            </>
          ) : null}

          <section className="card" aria-label="질문과 아이의 답" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">질문과 아이의 답</h2>
              <span className="note" style={{ marginLeft: 'auto' }}>
                {v.k.last} 체크인
              </span>
            </div>
            <div className="qa-row note" style={{ padding: '8px 0' }}>
              <span>문항</span>
              <span>질문</span>
              <span>아이의 답</span>
              <span></span>
            </div>
            {(v.answers || []).map((a, aIndex) => (
              <Fragment key={aIndex}>
                <div className="qa-row" style={{ background: a.bg }}>
                  <span className="note">{a.id}</span>
                  <span>{a.q}</span>
                  <b style={{ fontWeight: a.fw }}>{a.ans}</b>
                  <span className="note">{a.flagText}</span>
                </div>
              </Fragment>
            ))}
          </section>

          <section
            className="card"
            aria-label="확인해 봐야 할 답변"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">확인해 봐야 할 답변 · 추가 질문</h2>
              <span className="chip c-check">{v.flagCount}개</span>
            </div>
            {(v.flags || []).map((f, fIndex) => (
              <Fragment key={fIndex}>
                <div className="flag">
                  <b style={{ fontSize: '15px' }}>{f.q}</b>
                  <div className="flow">
                    <span className="note" style={{ marginRight: '4px' }}>
                      3주 전 → 이번
                    </span>
                    {(f.flow || []).map((v, vIndex) => (
                      <Fragment key={vIndex}>
                        <span className={v.cls}>{v.t}</span>
                      </Fragment>
                    ))}
                  </div>
                  <div className="aibox">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="chip c-ai">AI 초안</span>
                      <b style={{ fontSize: '13px' }}>확인해 볼 점</b>
                      {f.n.edited ? (
                        <>
                          <span className="chip c-sand">상담사 수정</span>
                        </>
                      ) : null}
                      {f.n.notEdit ? (
                        <>
                          <button
                            type="button"
                            className="btn btn-sm btn-s"
                            style={{ marginLeft: 'auto', minHeight: '30px' }}
                            onClick={f.n.startEdit}
                          >
                            수정
                          </button>
                        </>
                      ) : null}
                    </div>
                    {f.n.notEdit ? (
                      <>
                        <span style={{ fontSize: '14px', lineHeight: '1.7' }}>{f.n.text}</span>
                      </>
                    ) : null}
                    {f.n.isEdit ? (
                      <>
                        <textarea
                          className="edit-in"
                          rows="3"
                          aria-label="확인해 볼 점 수정"
                          value={f.n.draft}
                          onChange={f.n.setDraft}
                        ></textarea>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button type="button" className="btn btn-sm btn-p" onClick={f.n.save}>
                            저장
                          </button>
                          <button type="button" className="btn btn-sm btn-s" onClick={f.n.cancel}>
                            취소
                          </button>
                        </div>
                      </>
                    ) : null}
                    <span className="note">근거 · {f.src}</span>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      paddingLeft: '14px',
                      borderLeft: '3px solid #E7E4DC',
                    }}
                  >
                    <b style={{ fontSize: '13px' }}>추가 질문</b>
                    {(f.qs || []).map((q, qIndex) => (
                      <Fragment key={qIndex}>
                        <div className="qcard" style={{ boxShadow: q.ring }}>
                          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                            <span className="chip c-sky">{q.id}</span>
                            <span className={q.stCls}>{q.st}</span>
                            {q.edited ? (
                              <>
                                <span className="chip c-sand">상담사 수정</span>
                              </>
                            ) : null}
                            <span className="note" style={{ marginLeft: 'auto' }}>
                              근거 · {q.why}
                            </span>
                          </div>
                          {q.notEdit ? (
                            <>
                              <div style={{ fontSize: '16px', fontWeight: '500' }}>"{q.text}"</div>
                              {q.hasOpts ? (
                                <>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                    {(q.opts || []).map((o, oIndex) => (
                                      <Fragment key={oIndex}>
                                        <span className="opt">{o}</span>
                                      </Fragment>
                                    ))}
                                  </div>
                                </>
                              ) : null}
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                                <button type="button" className={`btn btn-sm ${q.okCls}`} onClick={q.approve}>
                                  {q.okLabel}
                                </button>
                                <button type="button" className="btn btn-sm btn-s" onClick={q.startEdit}>
                                  수정
                                </button>
                              </div>
                            </>
                          ) : null}
                          {q.isEdit ? (
                            <>
                              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <span className="note">질문 문장</span>
                                <textarea
                                  className="edit-in"
                                  rows="2"
                                  aria-label="질문 문장 수정"
                                  value={q.draftText}
                                  onChange={q.setText}
                                ></textarea>
                              </label>
                              {q.hasOpts ? (
                                <>
                                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                    <span className="note">답 보기 (쉼표로 구분)</span>
                                    <input
                                      className="edit-in"
                                      type="text"
                                      aria-label="답 보기 수정"
                                      value={q.draftOpts}
                                      onChange={q.setOpts}
                                    />
                                  </label>
                                </>
                              ) : null}
                              <div style={{ display: 'flex', gap: '8px' }}>
                                <button type="button" className="btn btn-sm btn-p" onClick={q.save}>
                                  저장
                                </button>
                                <button type="button" className="btn btn-sm btn-s" onClick={q.cancel}>
                                  취소
                                </button>
                              </div>
                            </>
                          ) : null}
                        </div>
                      </Fragment>
                    ))}
                  </div>
                </div>
              </Fragment>
            ))}
          </section>

          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
