// 아이 연계 › 아이 상세 (아이가 쓴 글 · 질문과 답 · 확인할 답변 · 추가 질문)
// 원본: I-SPOT 디자인 캔버스 보드 ChildDetail.dc.html (자동 변환 후 다듬어 쓰세요)
import { Fragment } from 'react';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import './ChildDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { qok: {}, qe: {}, qEdit: null, dText: '', dOpts: '', ne: {}, nEdit: null, nText: '' };
  }
  renderVals() {
    const K = {
      ...{
        name: '박지호',
        short: '지호',
        ini: '박',
        age: '11세',
        types: '방임 · 정서',
        id: 'C-2026-0389',
        reason: '확인 필요',
        rCls: 'chip c-check',
        last: '어제 21:05',
        count: '20 / 21일',
        next: '10/22 정기상담 5회차',
        urgent: false,
        quote: '엄마가 요즘 밤에 집에 안 들어와',
        quoteAt: '어제 21:06',
        answers: [
          ['공통 1', '어젯밤 잘 잤어?', '조금 못 잤어', false],
          ['공통 2', '어제 누가 아프게 한 적 있어?', '없어', false],
          ['공통 3', '오늘 기분은?', '조금 슬퍼', false],
          ['QB-N-12', '이번 주 저녁을 혼자 먹은 날은?', '5일 이상', true],
          ['유형 N-5', '어젯밤 집에 어른이 있었어?', '혼자 잤어', true],
          ['유형 N-3', '오늘 학교는 갔어?', '갔어', false],
          ['유형 N-1', '오늘 밥은 몇 번 먹었어?', '2번', false],
        ],
        flags: [
          {
            q: '이번 주 저녁을 혼자 먹은 날은? (QB-N-12)',
            flow: ['0일', '1~2일', '1~2일', '5일 이상'],
            src: '어제 21:05 응답 · 3회차 상담일지',
            qi: [1],
          },
          {
            q: '어젯밤 집에 어른이 있었어? (유형 N-5)',
            flow: ['있었어', '있었어', '늦게 왔어', '혼자 잤어'],
            src: '어제 21:05 응답 · 21:06 아이가 쓴 글',
            qi: [0],
          },
        ],
        notes: [
          '3주째 늘고 있고, 이번에 처음 "5일 이상"이 나왔어요. 3회차 상담 진술과 같은 방향이에요. 다음 상담에서 저녁 시간 돌봄을 확인해 보세요.',
          '밤에 어른 없이 혼자 잤다는 답이 처음 나왔어요. 아이가 쓴 글과 같은 내용이에요.',
        ],
        qs: [
          {
            id: 'QB-N-14',
            text: '이번 주에 밤에 집에 어른이 없었던 날은 며칠이야?',
            opts: ['없었어', '1~2일', '3~4일', '5일 이상', '말하기 어려워'],
            why: 'N-5 응답 · 아이가 쓴 글',
            sendNote: '오늘 저녁 발송',
          },
          {
            id: 'QB-N-07',
            text: '배고플 때 집에 먹을 것이 있어?',
            opts: ['항상 있어', '가끔 없어', '자주 없어', '말하기 어려워'],
            why: 'QB-N-12 응답',
            sendNote: '오늘 저녁 발송',
          },
        ],
      },
      short0: '지',
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

    const answers = K.answers.map((a) => ({
      id: a[0],
      q: a[1],
      ans: a[2],
      fw: a[3] ? 700 : 500,
      bg: a[3] ? '#F8F5EC' : 'transparent',
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

export default function ChildDetail(props) {
  const v = useDC(Logic, props);
  return (
    <div className="pg-ChildDetail">
      <div
        style={{
          minHeight: '1600px',
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
            <A to="/CaseList">사례 관리</A>
            <A to="/Schedule">일정</A>
            <A className="on" to="/ChildLink">
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
            <A to="/ChildLink">아이 연계</A> › {v.k.short}
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
            <span className="av" style={{ width: '52px', height: '52px', fontSize: '20px' }}>
              {v.k.short0}
            </span>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.k.name}</h1>
                <span className="sub">
                  {v.k.age} · {v.k.types}
                </span>
                <span className={v.k.rCls}>{v.k.reason}</span>
              </div>
              <div className="note">
                {v.k.id} · 마지막 응답 {v.k.last} · 최근 3주 {v.k.count} · 다음 상담 {v.k.next}
              </div>
            </div>
            <A className="btn btn-s" to="/CaseDetail">
              사례 상세 보기
            </A>
          </header>
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
              <span />
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
                        />
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
                      borderLeft: '3px solid #E7E0CE',
                    }}
                  >
                    <b style={{ fontSize: '13px' }}>추가 질문</b>
                    {(f.qs || []).map((q, qIndex) => (
                      <Fragment key={qIndex}>
                        <div className="qcard" style={{ boxShadow: q.ring }}>
                          <div
                            style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}
                          >
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
