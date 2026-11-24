// 콩콩 '질문 보내기'(1개 이상 골라 아이 앱으로). 사례 아이 연계 · 아이 상세 · 다음 상담 준비 '아이 앱으로 먼저' 탭이 같이 쓴다.
// app 은 useCaseChildApp 의 값. bare 면 바깥 카드 없이 안쪽만 그린다(다른 카드 안에 넣을 때).
// 연결 전이면 아이 연계(아이 상세)에서 연결하라고 안내한다.
// 11/10 디자인(FollowupQ '승인' → '발송 예약') · #173: 단추는 '발송 예약'(deliver EVENING — 그날 저녁 시각부터 아이 앱에 보이고,
// 그 시각이 지났으면 서버가 바로 보낸다). 예약해 둔 질문(scheduled_questions)이 있으면 '발송 예약 · 오늘 18:00 발송' 과 '예약 취소'.
// 알림 문구는 보낸 뒤 다시 받은 값으로 정한다(예약됐는지 · 바로 갔는지는 서버가 정하므로).
// 낮에 급하게 확인할 때를 위해 '지금 보내기'(deliver NOW)도 둔다 — 화면 기본은 예약(민규 #186 리뷰, #173 스펙).
// 11/24: 고정 8문항만 있어 회차마다 질문이 같았다 → 위에 '이번 회차 맞춤 질문'(가장 최근 분석 회차로 만든 AI 초안)을 두고
// 고정 문항과 함께 고른다. 만들기는 상담사가 '맞춤 질문 만들기' 를 눌렀을 때만(회차 내용이 외부 AI 로 가므로 — 민규 #195 리뷰),
// 한 번 만든 뒤에는 열 때마다 바로 보인다. 이유(reason)는 상담사에게만 보인다. 맞춤 질문 답은 건너뛰지 않으면 모두 살펴볼 답.
// 맞춤 질문은 '고치기'로 문장 · 보기를 고칠 수 있다(아이 추가 질문 고치기와 같은 칸 모양 — ChildDetail).
import { useEffect, useState } from 'react';
import A from './A';
import { useSentToast } from './SentToast';
import { screenHref } from '../data/screens/links';

// 문항 형식 칩(콩콩 디자인 '질문 보내기' 의 카테고리 옆 칩).
const TYPE_NAME = { scale: '표정 5단계', choice: '선택지', text: '짧은 글' };

/** 예약 시각 '오늘 18:00' · 다른 날이면 '11/20 18:00'. */
function deliverLabel(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  return d.toDateString() === new Date().toDateString() ? `오늘 ${hm}` : `${d.getMonth() + 1}/${d.getDate()} ${hm}`;
}

export default function ChildQuestionSender({ app, caseId, bare = false }) {
  const [picked, setPicked] = useState([]);
  const sq = app.data?.session_questions ?? null;
  const { createSessionQuestions } = app;
  const [toast, showToast] = useSentToast();
  const [hint, setHint] = useState('');
  // 예약을 보낸 뒤 다시 받은 값이 오면 알림을 띄운다({ count, data: 보내기 전 값 }).
  const [sent, setSent] = useState(null);
  // 누른 단추('EVENING' · 'NOW'). 보내는 중 문구를 그 단추에만 보인다.
  const [going, setGoing] = useState(null);
  const data = app.data;
  useEffect(() => {
    if (!sent || !data || data === sent.data) return;
    const sq = data.scheduled_questions;
    showToast(sq ? `질문 ${sent.count}개를 발송 예약했어요 · ${deliverLabel(sq.deliver_at)} 발송` : `아이에게 질문 ${sent.count}개를 보냈어요`);
    setSent(null);
  }, [data, sent, showToast]);
  if (!data) return toast;
  const scheduled = data.can_read_feed ? data.scheduled_questions ?? null : null;

  const toggle = (id) => {
    setHint('');
    setPicked((cur) => (cur.includes(id) ? cur.filter((item) => item !== id) : [...cur, id]));
  };
  const countOk = picked.length >= 1;
  // 꺼진 단추 모양이 따로 없어 눌러도 아무 일 없는 것처럼 보였다(11/10). 단추는 두고, 하나도 안 골랐으면 이유를 알린다.
  const send = async (deliver) => {
    if (app.busy) return;
    const count = picked.length;
    if (!countOk) {
      setHint(deliver === 'NOW' ? '보낼 질문을 하나 이상 골라 주세요.' : '발송 예약할 질문을 하나 이상 골라 주세요.');
      return;
    }
    const before = data;
    setGoing(deliver);
    const ok = await app.sendQuestions(picked, deliver);
    setGoing(null);
    if (!ok) return;
    setPicked([]);
    if (deliver === 'NOW') showToast(`아이에게 질문 ${count}개를 보냈어요`);
    else setSent({ count, data: before });
  };
  // 고치는 중인 맞춤 질문 id 와 그 칸 값(보기는 쉼표로 구분, 건너뛰기는 아이 앱에 따로 있다).
  const [editId, setEditId] = useState(null);
  const [draft, setDraft] = useState({ text: '', opts: '' });
  const splitList = (value) =>
    value
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean);
  const startEdit = (item) => {
    setEditId(item.id);
    setDraft({
      text: item.text,
      opts: item.options.join(', '),
    });
  };
  const saveEdit = async (item) => {
    if (app.busy) return;
    const choice = item.type === 'choice';
    const ok = await app.saveSessionQuestion(
      item.id,
      draft.text.trim(),
      choice ? splitList(draft.opts) : [],
    );
    if (ok) setEditId(null);
  };
  const regenerate = async () => {
    if (app.sqCreating) return;
    if (sq?.items.some((item) => item.edited) && !window.confirm('고친 맞춤 질문도 새 초안으로 바뀌어요. 다시 만들까요?')) return;
    setEditId(null);
    // 다시 만들면 앞 초안의 질문 번호는 보낼 수 없다.
    setPicked((cur) => cur.filter((id) => !id.startsWith('sq_')));
    await createSessionQuestions(true);
  };
  const cancel = async () => {
    if (app.busy || !scheduled) return;
    if (await app.cancelScheduled(scheduled.id)) showToast('발송 예약을 취소했어요');
  };

  let body;
  if (!data.can_read_feed) {
    body = <div className="note">질문은 담당 상담사가 보내요.</div>;
  } else if (data.status !== 'LINKED') {
    body = (
      <div className="note">
        아이 앱이 연결된 뒤에 보낼 수 있어요.{' '}
        {caseId ? <A to={screenHref('/ChildDetail', { caseId })}>아이 연계에서 연결하기 →</A> : null}
      </div>
    );
  } else {
    body = (
      <>
        {sq ? (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              <b>이번 회차 맞춤 질문</b>
              <span className="chip c-ai">AI 제안</span>
              <span className="note">{sq.session_label} 상담 내용으로 만든 초안이에요. 골라야 아이에게 가요. 답하면 살펴볼 답으로 떠요.</span>
              <button type="button" className="btn btn-sm btn-s" aria-disabled={app.sqCreating} onClick={regenerate} style={{ marginLeft: 'auto' }}>
                {app.sqCreating ? '만드는 중…' : '다시 만들기'}
              </button>
            </div>
            <div className="note acc">아이 폰은 가족이 볼 수 있어요. 회차에서 나온 일 · 사람이 드러나는 질문은 고르지 마세요.</div>
            {sq.items.map((item) =>
              editId === item.id ? (
                <div key={item.id} style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '24px' }}>
                  <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <span className="note">질문 문장 · 아이 폰은 다른 가족이 볼 수 있어요. 사건 · 사람 이름은 넣지 마세요.</span>
                    <textarea
                      className="edit-in"
                      rows="2"
                      aria-label="맞춤 질문 문장 수정"
                      value={draft.text}
                      onChange={(e) => setDraft({ ...draft, text: e.target.value })}
                    ></textarea>
                  </label>
                  {item.type === 'choice' ? (
                    <>
                      <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <span className="note">답 보기 (쉼표로 구분, 2~5개 · 건너뛰기는 아이 앱에 따로 있어요)</span>
                        <input
                          className="edit-in"
                          type="text"
                          aria-label="맞춤 질문 답 보기 수정"
                          value={draft.opts}
                          onChange={(e) => setDraft({ ...draft, opts: e.target.value })}
                        />
                      </label>
                    </>
                  ) : null}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button
                      type="button"
                      className="btn btn-sm btn-p"
                      aria-disabled={app.busy || !draft.text.trim()}
                      onClick={() => saveEdit(item)}
                    >
                      저장
                    </button>
                    <button type="button" className="btn btn-sm btn-s" onClick={() => setEditId(null)}>
                      취소
                    </button>
                  </div>
                </div>
              ) : (
              <div key={item.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <label style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer', flex: 1 }}>
                <input type="checkbox" checked={picked.includes(item.id)} onChange={() => toggle(item.id)} />
                <span>
                  <span className="chip c-sand">{item.category}</span>{' '}
                  {TYPE_NAME[item.type] ? <span className="chip c-sand">{TYPE_NAME[item.type]}</span> : null}{' '}
                  {item.edited ? <span className="chip c-sel">고침</span> : null} {item.text}
                  {item.options.length ? <span className="note"> · {item.options.join(' / ')}</span> : null}
                  {item.reason ? (
                    <span className="note" style={{ display: 'block', fontSize: '12px' }}>
                      왜: {item.reason}
                    </span>
                  ) : null}
                </span>
              </label>
              <button type="button" className="btn btn-sm btn-s" onClick={() => startEdit(item)}>
                고치기
              </button>
              </div>
              ),
            )}
            <b>기본 문항</b>
          </>
        ) : data.session_questions_available ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <b>이번 회차 맞춤 질문</b>
            <span className="note">
              {app.sqCreating
                ? '이번 회차 상담 내용으로 맞춤 질문을 만드는 중이에요…'
                : '이번 회차 상담 내용(이름은 가림)을 AI 에 보내 아이에게 물어볼 질문 초안을 만들어요.'}
            </span>
            {app.sqError ? <span className="note acc">{app.sqError}</span> : null}
            <button
              type="button"
              className="btn btn-sm btn-s"
              aria-disabled={app.sqCreating}
              onClick={() => (app.sqCreating ? null : createSessionQuestions(false))}
              style={{ marginLeft: 'auto' }}
            >
              {app.sqCreating ? '만드는 중…' : '맞춤 질문 만들기'}
            </button>
          </div>
        ) : null}
        {data.bank.map((item) => (
          <label key={item.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer' }}>
            <input type="checkbox" checked={picked.includes(item.id)} onChange={() => toggle(item.id)} />
            <span>
              <span className="chip c-sand">{item.category}</span>{' '}
              {TYPE_NAME[item.type] ? <span className="chip c-sand">{TYPE_NAME[item.type]}</span> : null} {item.text}
            </span>
          </label>
        ))}
        {scheduled ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <span className="chip c-sel">발송 예약 · {deliverLabel(scheduled.deliver_at)} 발송</span>
            <span className="note">질문 {scheduled.count}개 · 다시 예약하거나 지금 보내면 앞 예약은 취소돼요.</span>
            <button type="button" className="btn btn-sm btn-s" aria-disabled={app.busy} onClick={cancel} style={{ marginLeft: 'auto' }}>
              예약 취소
            </button>
          </div>
        ) : data.has_pending_questions ? (
          <div className="note">아이가 아직 답하지 않은 질문이 있어요. 새로 보낸 질문이 아이 앱에 보이면(예약은 예약 시각부터) 그 질문으로 바뀝니다.</div>
        ) : null}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
          <button type="button" className="btn btn-p" aria-disabled={!countOk || app.busy} style={countOk && !app.busy ? undefined : { opacity: 0.5 }} onClick={() => send('EVENING')}>
            {going === 'EVENING' ? '예약하는 중…' : '발송 예약'}
          </button>
          <button type="button" className="btn btn-s" aria-disabled={!countOk || app.busy} style={countOk && !app.busy ? undefined : { opacity: 0.5 }} onClick={() => send('NOW')}>
            {going === 'NOW' ? '보내는 중…' : '지금 보내기'}
          </button>
          <span className="note">발송 예약은 오늘 저녁부터 아이 앱에 보여요. 급하면 지금 보내기.</span>
        </div>
        {hint ? (
          <p className="note acc" role="alert" style={{ margin: '0' }}>
            {hint}
          </p>
        ) : null}
        {app.actionError ? (
          <p className="note acc" role="alert" style={{ margin: '0' }}>
            {app.actionError}
          </p>
        ) : null}
      </>
    );
  }

  const title = data.status === 'LINKED' && data.can_read_feed ? `질문 보내기 · ${picked.length}개 선택` : '질문 보내기';
  if (bare) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {toast}
        <b>{title}</b>
        {body}
      </div>
    );
  }
  return (
    <section className="card" aria-label="질문 보내기" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {toast}
      <h2 className="h2">{title}</h2>
      {body}
    </section>
  );
}
