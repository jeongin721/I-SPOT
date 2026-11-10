// 아이 연계 › 아이 상세 (아이가 쓴 글 · 질문과 답 · 확인할 답변 · 추가 질문)
// 원본: 11/09 디자인 '아이 연계 › 아이 상세' ChildDetail.dc.html.
//
// 사례 ID 가 있으면 콩콩 앱 서버 값을 보인다(screens/childDetail.ts). 사례 ID 가 없으면 디자인 예시를 그대로 보인다.
//  - AI 초안 '확인해 볼 점' · 추가 질문은 서버가 만든 것만 보인다. 추가 질문은 상담사가 승인해야 아이 앱으로 간다.
import { Fragment } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { DCLogic, useDC } from '../dc';
import A from '../components/A';
import ChildQuestionSender from '../components/ChildQuestionSender';
import NotiBell from '../components/NotiBell';
import Notice from '../components/Notice';
import Sidebar from '../components/Sidebar';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCaseChildApp } from '../data/useCaseChildApp';
import { useCaseDetail } from '../data/useCaseDetail';
import { aiDraftNeeded, childDetailValues } from '../data/screens/childDetail';
import { readScreenIds, screenHref } from '../data/screens/links';
import { needsLogin, screenNotice } from '../data/screens/common';
import { useTheme } from '../theme';
import './ChildDetail.css';

class Logic extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { qok: {}, qe: {}, qEdit: null, dText: '', dOpts: '', ne: {}, nEdit: null, nText: '' };
  }
  renderVals() {
    const live = this.props.live;
    const K = live || {
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
          ['공통 1', '어젯밤 잘 잤어?', '조금 못 잤어', false, ['잘 잤어', '잘 잤어', '조금 못 잤어']],
          ['공통 2', '어제 누가 아프게 한 적 있어?', '없어', false, ['없어', '없어', '없어']],
          ['공통 3', '오늘 기분은?', '조금 슬퍼', false, ['좋아', '보통', '보통']],
          ['QB-N-12', '이번 주 저녁을 혼자 먹은 날은?', '5일 이상', true, ['0일', '1~2일', '1~2일']],
          ['유형 N-5', '어젯밤 집에 어른이 있었어?', '혼자 잤어', true, ['있었어', '있었어', '늦게 왔어']],
          ['유형 N-3', '오늘 학교는 갔어?', '갔어', false, ['갔어', '갔어', '갔어']],
          ['유형 N-1', '오늘 밥은 몇 번 먹었어?', '2번', false, ['3번', '3번', '2번']],
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
        const ok = q0.setApproved ? q0.approved : !!s.qok[i],
          editing = s.qEdit === i;
        return {
          id: q0.id,
          why: q0.why,
          text,
          opts,
          hasOpts: opts.length > 0,
          edited: q0.setApproved ? q0.edited : !!cur.text || !!cur.opts,
          st: ok ? (q0.sendNote ? '승인됨 · ' + q0.sendNote : '승인됨') : 'AI 초안',
          stCls: ok ? 'chip c-sel' : 'chip c-ai',
          ring: editing ? 'inset 0 0 0 2px #2B2A26' : 'none',
          okCls: ok ? 'btn-p' : 'btn-s',
          okLabel: ok ? '승인됨 ✓' : '승인',
          isEdit: editing,
          notEdit: !editing,
          draftText: s.dText,
          draftOpts: s.dOpts,
          approve: () => (q0.setApproved ? q0.setApproved(!ok) : this.setState({ qok: { ...s.qok, [i]: !ok } })),
          startEdit: () => this.setState({ qEdit: i, dText: text, dOpts: opts.join(', ') }),
          setText: (e) => this.setState({ dText: e.target.value }),
          setOpts: (e) => this.setState({ dOpts: e.target.value }),
          save: () => {
            if (q0.save) {
              this.setState({ qEdit: null });
              q0.save(
                s.dText.trim(),
                s.dOpts
                  .split(',')
                  .map((x) => x.trim())
                  .filter(Boolean),
              );
              return;
            }
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
            });
          },
          cancel: () => this.setState({ qEdit: null }),
        };
      });
    const mkNotes = (list) =>
      list.map((n0, i) => {
        if (!n0) return null;
        const server = typeof n0 === 'object';
        const text = server ? n0.text : s.ne[i] || n0;
        const editing = s.nEdit === i;
        return {
          text,
          edited: server ? n0.edited : s.ne[i] !== undefined,
          isEdit: editing,
          notEdit: !editing,
          draft: s.nText,
          startEdit: () => this.setState({ nEdit: i, nText: text }),
          setDraft: (e) => this.setState({ nText: e.target.value }),
          save: () => {
            if (server) {
              this.setState({ nEdit: null });
              n0.save(s.nText.trim());
            } else {
              this.setState({ nEdit: null, ne: { ...s.ne, [i]: s.nText } });
            }
          },
          cancel: () => this.setState({ nEdit: null }),
        };
      });

    const answers = K.answers
      .filter((a) => !/^공통/.test(a[0]))
      .map((a) => {
        const prev = a[4] || [];
        const changed = prev.length > 0 && prev[prev.length - 1] !== a[2];
        return {
          id: a[0],
          q: a[1],
          ans: a[2],
          prev,
          changed,
          fw: a[3] || changed ? 700 : 500,
          bg: a[3] ? '#F7F6F2' : 'transparent',
          flagText: a[3] ? a[5] || '확인 필요' : '',
        };
      });
    const notes = mkNotes(K.notes);
    const allQs = mkQs(K.qs);
    const flags = K.flags.map((f, i) => ({
      q: f.q,
      src: f.src,
      n: notes.at(i),
      qs: (f.qi || []).map((j) => allQs.at(j)),
      hasAi: !!notes.at(i),
      flow: f.flow.map((t, j) => ({ t, cls: j === f.flow.length - 1 ? 'v now' : 'v' })),
    }));
    return {
      k: { ...K, hasQuote: !!K.quote },
      answers,
      flags,
      flagCount: flags.length,
      isLive: !!live,
      prevLabel: K.prevLabel || '지난 답변 (3주 전 → 지난주)',
      flowLabel: K.flowLabel || '3주 전 → 이번',
    };
  }
}

export default function ChildDetail(props) {
  const session = useAuthSession();
  const theme = useTheme();
  const { caseId } = readScreenIds(useSearchParams()[0]);
  const enabled = session.status === 'signedIn' && !!caseId;
  const detail = useCaseDetail(caseId, { enabled });
  const app = useCaseChildApp(caseId, enabled);
  const info = detail.caseInfo;
  const live =
    caseId && app.data && info
      ? childDetailValues(app.data, info, {
          saveNote: app.saveAiNote,
          saveQuestion: app.saveAiQuestion,
          setApproval: app.setAiApproval,
        })
      : null;
  // 아이 글이 외부 AI 로 나가므로 상담사가 단추를 누를 때만 만든다(민규 #165 리뷰 4).
  const needed = app.data ? aiDraftNeeded(app.data) : null;
  const { createAiDraft } = app;
  const v = useDC(Logic, { ...props, live });
  if (caseId && needsLogin(session)) return <Navigate to="/Login" replace />;
  const notice = caseId
    ? screenNotice({
        session,
        loading: (app.loading && !app.data) || (detail.loading && !info),
        error: app.error || detail.error,
        retry: app.reload,
      })
    : null;
  const caseHref = caseId ? screenHref('/CaseDetail', { caseId }) : '/CaseDetail';
  const historyHref = caseId ? screenHref('/CaseApp', { caseId }) : '/CaseApp';
  const adminOnly = caseId && app.data && !app.data.can_read_feed;
  // 미연결 · 초대 대기면 이 화면(아이 연계)에서 바로 연결 코드를 만든다. 질문 · 답 칸은 연결 뒤에 보인다(11/10 경진님).
  const notLinked = !!(caseId && app.data && app.data.status !== 'LINKED');
  const noAnswers = caseId && app.data && app.data.can_read_feed && !notLinked && v.answers.length === 0;
  const expires = app.data?.code_expires_at ? new Date(app.data.code_expires_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
  return (
    <div className="pg-ChildDetail">
      <div
        className={theme.cls}
        style={{
          minHeight: '1600px',
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
        <Sidebar active="ChildLink" session={session} />
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
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/ChildLink">아이 연계</A> › {v.k.short}
          </nav>
          <header style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 16px' }}>
            <A className="btn btn-sm btn-s" to="/ChildLink">
              ← 목록
            </A>
            <span className="av" style={{ width: '52px', height: '52px', fontSize: '20px' }}>
              {v.k.short0}
            </span>
            <div style={{ flex: '1 1 320px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{v.k.name}</h1>
                <span className="sub">
                  {v.k.age}
                  {v.k.types ? ` · ${v.k.types}` : ''}
                </span>
                <span className={v.k.rCls}>{v.k.reason}</span>
              </div>
              <div className="note">
                {v.k.id} · 마지막 응답 {v.k.last} · 최근 3주 {v.k.count} · 다음 상담 {v.k.next}
              </div>
            </div>
            <A className="btn btn-s" to={caseHref}>
              사례 상세 보기
            </A>
          </header>
          {notice ? <Notice value={notice} /> : null}
          {adminOnly ? <p className="note">아이가 보낸 내용은 담당 상담사만 볼 수 있어요.</p> : null}
          {noAnswers ? <p className="note">아직 아이가 보낸 답이 없어요.</p> : null}
          {notLinked ? (
            <section className="card" aria-label="앱 연결" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <h2 className="h2">콩콩 앱 연결</h2>
              {!app.data.can_read_feed ? (
                <div className="sub">코드는 담당 상담사가 만들어요.</div>
              ) : (
                <>
                  <div className="sub">
                    {app.data.status === 'INVITED' && !app.invite
                      ? `연결 코드를 보냈고 아이가 아직 연결하지 않았어요${expires ? ` (코드는 ${expires}까지)` : ''}. 코드를 잊었으면 새로 만들어 주세요.`
                      : '코드를 만들어 아이에게 직접 알려 주세요. 코드는 72시간 동안, 한 번만 쓸 수 있어요.'}
                  </div>
                  {app.invite ? (
                    <div style={{ fontSize: '24px', fontWeight: 700, letterSpacing: '1px' }}>{app.invite.code}</div>
                  ) : null}
                  <div>
                    <button type="button" className="btn btn-s" disabled={app.busy} onClick={app.createInvite}>
                      {app.data.status === 'INVITED' ? '코드 다시 만들기' : '연결 코드 만들기'}
                    </button>
                  </div>
                  {app.actionError ? <p className="note acc" role="alert" style={{ margin: '0' }}>{app.actionError}</p> : null}
                </>
              )}
            </section>
          ) : null}
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

          {notLinked ? null : (
            <>
          <section className="card" aria-label="질문 및 답변" style={{ padding: '20px 22px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <h2 className="h2">질문 및 답변</h2>
              <span className="note" style={{ marginLeft: 'auto' }}>
                {v.k.last} 체크인
              </span>
              <A className="btn btn-sm btn-s" to={historyHref}>
                과거 답변 기록 →
              </A>
            </div>
            <div className="qa-row note" style={{ padding: '8px 0' }}>
              <span>문항</span>
              <span>질문</span>
              <span>{v.prevLabel}</span>
              <span>이번 답변</span>
              <span></span>
            </div>
            {(v.answers || []).map((a, aIndex) => (
              <Fragment key={aIndex}>
                <div className="qa-row" style={{ background: a.bg }}>
                  <span className="note">{a.id}</span>
                  <span>{a.q}</span>
                  <span className="prev">
                    {(a.prev || []).map((p, pIndex) => (
                      <span key={pIndex} className="pv">
                        {p}
                      </span>
                    ))}
                  </span>
                  <b style={{ fontWeight: a.fw }}>
                    {a.ans}
                    {a.changed ? <span className="chg">바뀜</span> : null}
                  </b>
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
            {needed && !app.aiCreating && !app.aiError ? (
              <p className="note" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', margin: '0' }}>
                <button type="button" className="btn btn-sm btn-s" onClick={createAiDraft}>
                  AI 초안 만들기
                </button>
                이름을 가린 뒤 외부 AI 로 보내 확인해 볼 점 · 추가 질문 초안을 만들어요.
              </p>
            ) : null}
            {app.aiCreating ? <p className="note" role="status">AI 초안을 만드는 중이에요…</p> : null}
            {app.aiError ? (
              <p className="note" role="alert" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', margin: '0' }}>
                {app.aiError}
                <button type="button" className="btn btn-sm btn-s" onClick={createAiDraft}>
                  다시 시도
                </button>
              </p>
            ) : null}
            {app.actionError ? <p className="note acc" role="alert" style={{ margin: '0' }}>{app.actionError}</p> : null}
            {(v.flags || []).map((f, fIndex) => (
              <Fragment key={fIndex}>
                <div className="flag">
                  <b style={{ fontSize: '15px' }}>{f.q}</b>
                  <div className="flow">
                    <span className="note" style={{ marginRight: '4px' }}>
                      {v.flowLabel}
                    </span>
                    {(f.flow || []).map((t, tIndex) => (
                      <Fragment key={tIndex}>
                        <span className={t.cls}>{t.t}</span>
                      </Fragment>
                    ))}
                  </div>
                  {f.hasAi ? (
                  <>
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
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                          <button type="button" className="btn btn-sm btn-p" onClick={f.n.save}>
                            저장
                          </button>
                          <button type="button" className="btn btn-sm btn-s" onClick={f.n.cancel}>
                            취소
                          </button>
                        </div>
                      </>
                    ) : null}
                    {v.isLive ? (
                      <span className="note">근거 · {f.src}</span>
                    ) : (
                      <A className="note srcl" to="/SttReview" title="STT 원문 위치로 이동">
                        근거 · {f.src} ↗
                      </A>
                    )}
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
                    {(f.qs || []).length ? <b style={{ fontSize: '13px' }}>추가 질문</b> : null}
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
                            {v.isLive ? (
                              <span className="note" style={{ marginLeft: 'auto' }}>
                                근거 · {q.why}
                              </span>
                            ) : (
                              <A className="note srcl" to="/SttReview" style={{ marginLeft: 'auto' }} title="STT 원문 위치로 이동">
                                근거 · {q.why} ↗
                              </A>
                            )}
                          </div>
                          {q.notEdit ? (
                            <>
                              <div style={{ fontSize: '16px', fontWeight: '500' }}>"{q.text}"</div>
                              {q.hasOpts ? (
                                <>
                                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '6px' }}>
                                    <span className="note" style={{ fontWeight: '700' }}>
                                      답변:
                                    </span>
                                    {(q.opts || []).map((o, oIndex) => (
                                      <Fragment key={oIndex}>
                                        <span className="opt">{o}</span>
                                      </Fragment>
                                    ))}
                                  </div>
                                </>
                              ) : null}
                              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: '8px' }}>
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
                              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
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
                  </>
                  ) : null}
                </div>
              </Fragment>
            ))}
          </section>

              {/* 디자인에 없는 칸: 질문 보내기(11/10 경진님 — 아이 연계 안에서 연결 · 질문 · 답 확인을 끝내게). */}
              <ChildQuestionSender app={app} caseId={caseId} />
            </>
          )}

          <p className="ainote">AI 분석은 참고용이며, 최종 판단은 상담사가 합니다.</p>
        </main>
      </div>
    </div>
  );
}
