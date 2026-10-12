// 4 · 추가 확인 · 질문 (모두 승인 / 수정 가능)
// 원본: I-SPOT 디자인 캔버스 보드 FollowupQ.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './FollowupQ.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = {
      tab: 'meet',
      on: { 0: true, 1: true, 2: false },
      extra: [],
      qok: {},
      qe: {},
      qEdit: null,
      dText: '',
      dOpts: '',
      ne: {},
      nEdit: null,
      nText: '',
    };
  }
  renderVals() {
    const s = this.state;
    const ALL = [
      {
        g: 'meet',
        id: '열린 질문',
        text: '등이랑 팔이 아팠던 건 지금은 어때? 누가 봐 준 적 있어?',
        opts: [],
        why: '8회차 01:08',
      },
      {
        g: 'meet',
        id: '열린 질문',
        text: '그 이야기를 하면 어떤 일이 생길 것 같아?',
        opts: [],
        why: '8회차 01:08',
      },
      { g: 'meet', id: 'QB-N-01', text: '요즘 밥은 주로 어떻게 먹어?', opts: [], why: '8회차 02:15' },
      {
        g: 'app',
        id: 'QB-N-01',
        text: '어제 밥을 몇 번 먹었어?',
        opts: ['0번', '1번', '2번', '3번', '말하기 어려워'],
        why: '8회차 02:15',
        sendNote: '오늘 저녁 발송',
      },
      {
        g: 'app',
        id: 'QB-E-05',
        text: '누가 "이 일 말하면 혼난다"처럼 겁을 준 적 있어?',
        opts: ['없어', '1번', '여러 번', '말하기 어려워'],
        why: '8회차 01:08',
        sendNote: '오늘 저녁 발송',
      },
    ];
    const hasOptsAt = (i) => (ALL.at(i).opts || []).length > 0;

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
          ring: editing ? 'inset 0 0 0 2px #A8C6E7' : 'none',
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

    const allQs = mkQs(ALL);
    const qs = allQs.filter((q, i) => ALL.at(i).g === s.tab);
    const base = [
      { t: '등 · 팔 통증 이후 치료를 받았는지', why: '8회차 01:08' },
      { t: '02:15 발화의 화자 · 식사 상황', why: '8회차 02:15 · 화자 불확실' },
      { t: '조모 연락 체계가 실제로 쓰였는지', why: '7회차 안전 계획 · 8회차 02:40' },
    ].concat(s.extra.map(() => ({ t: '새 확인 사항을 적어 주세요', why: '상담사 직접 추가' })));
    const notes = mkNotes(base.map((b) => b.t));
    const checks = base.map((b, i) => ({
      why: b.why,
      n: notes.at(i),
      on: !!s.on[i],
      ring: s.nEdit === i ? 'inset 0 0 0 2px #A8C6E7' : 'none',
      toggle: () => this.setState({ on: { ...s.on, [i]: !s.on[i] } }),
    }));
    return {
      checks,
      qs,
      meetCls: s.tab === 'meet' ? 'on' : '',
      appCls: s.tab === 'app' ? 'on' : '',
      showMeet: () => this.setState({ tab: 'meet', qEdit: null }),
      showApp: () => this.setState({ tab: 'app', qEdit: null }),
      addCheck: () => {
        const n = base.length;
        this.setState({ extra: [...s.extra, 1], on: { ...s.on, [n]: true }, nEdit: n, nText: '' });
      },
    };
  }
}

export default function FollowupQ(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-FollowupQ">
      <div
        style={{
          minHeight: '1550px',
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
            <span className="av">이</span>
            <b style={{ fontWeight: '500' }}>이서연 상담원</b>
            <A to="/Login" className="note" style={{ marginLeft: 'auto' }}>
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
            <A to="/CaseList">사례 관리</A> › <A to="/CaseDetail">이서윤 C-2026-0351</A> ›{' '}
            <A to="/CaseHistory">상담 이력</A> › <A to="/SessionDetail">8회차</A>
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '10px 14px' }}>
            <div style={{ flex: '1 1 280px' }}>
              <div className="sub">10/2(금) 방문상담</div>
              <h1 style={{ margin: '2px 0 0', fontSize: '28px', fontWeight: '700' }}>8회차 처리 · 이서윤</h1>
            </div>
          </header>
          <nav className="steps" aria-label="회차 처리 단계">
            <A className="stp done" to="/SttReview">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>STT 검수</b>
            </A>
            <A className="stp done" to="/SignalReview">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>위험 신호 검토</b>
            </A>
            <A className="stp done" to="/NoteWrite">
              <span className="sn">✓</span>
              <b style={{ fontWeight: '500' }}>요약 · 일지 작성</b>
            </A>
            <A className="stp on" to="/FollowupQ" aria-current="step">
              <span className="sn">4</span>
              <b style={{ fontWeight: '700' }}>추가 확인 · 질문</b>
            </A>
          </nav>
          <section
            className="card"
            aria-label="다음 상담 전 확인할 사항"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">다음 상담 전 확인할 사항</h2>
              <span className="chip c-ai">AI 초안</span>
            </div>
            {(v.checks || []).map((c, cIndex) => (
              <Fragment key={cIndex}>
                <div
                  className="qcard"
                  style={{ flexDirection: 'row', alignItems: 'flex-start', gap: '12px', boxShadow: c.ring }}
                >
                  <input
                    type="checkbox"
                    checked={c.on}
                    onChange={c.toggle}
                    aria-label="브리핑에 넣기"
                    style={{ width: '18px', height: '18px', marginTop: '4px', accentColor: '#7FA8D6' }}
                  />
                  <div style={{ flex: '1', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {c.n.notEdit ? (
                      <>
                        <span style={{ fontSize: '15px' }}>{c.n.text}</span>
                      </>
                    ) : null}
                    {c.n.isEdit ? (
                      <>
                        <textarea
                          className="edit-in"
                          rows="2"
                          aria-label="확인 사항 수정"
                          value={c.n.draft}
                          onChange={c.n.setDraft}
                        />
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button type="button" className="btn btn-sm btn-p" onClick={c.n.save}>
                            저장
                          </button>
                          <button type="button" className="btn btn-sm btn-s" onClick={c.n.cancel}>
                            취소
                          </button>
                        </div>
                      </>
                    ) : null}
                    <span className="note">근거 · {c.why}</span>
                  </div>
                  {c.n.edited ? (
                    <>
                      <span className="chip c-sand">상담사 수정</span>
                    </>
                  ) : null}
                  {c.n.notEdit ? (
                    <>
                      <button type="button" className="btn btn-sm btn-s" onClick={c.n.startEdit}>
                        수정
                      </button>
                    </>
                  ) : null}
                </div>
              </Fragment>
            ))}
            <button
              type="button"
              className="btn btn-sm btn-s"
              style={{ alignSelf: 'flex-start' }}
              onClick={v.addCheck}
            >
              + 확인 사항 직접 추가
            </button>
          </section>
          <section
            className="card"
            aria-label="추가 질문"
            style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '12px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px' }}>
              <h2 className="h2">추가 질문</h2>
              <span className="chip c-ai">AI 초안</span>
              <div role="tablist" className="seg" style={{ marginLeft: 'auto' }}>
                <button type="button" role="tab" className={v.meetCls} onClick={v.showMeet}>
                  다음 상담에서 직접
                </button>
                <button type="button" role="tab" className={v.appCls} onClick={v.showApp}>
                  아이 앱으로 먼저
                </button>
              </div>
            </div>
            {(v.qs || []).map((q, qIndex) => (
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
                        />
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
          </section>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
            <A className="btn btn-s" to="/NoteWrite">
              ← 요약 · 일지 작성
            </A>
            <A className="btn btn-p" to="/PreBriefing" style={{ marginLeft: 'auto' }}>
              8회차 처리 완료 · 브리핑 보기
            </A>
          </div>
          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
