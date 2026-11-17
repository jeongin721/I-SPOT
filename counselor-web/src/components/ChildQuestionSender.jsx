// 콩콩 '질문 보내기'(1개 이상 골라 아이 앱으로). 사례 아이 연계 · 아이 상세 · 다음 상담 준비 '아이 앱으로 먼저' 탭이 같이 쓴다.
// app 은 useCaseChildApp 의 값. bare 면 바깥 카드 없이 안쪽만 그린다(다른 카드 안에 넣을 때).
// 연결 전이면 아이 연계(아이 상세)에서 연결하라고 안내한다.
import { useState } from 'react';
import A from './A';
import { useSentToast } from './SentToast';
import { screenHref } from '../data/screens/links';

export default function ChildQuestionSender({ app, caseId, bare = false }) {
  const [picked, setPicked] = useState([]);
  const [toast, showToast] = useSentToast();
  const [hint, setHint] = useState('');
  const data = app.data;
  if (!data) return toast;

  const toggle = (id) => {
    setHint('');
    setPicked((cur) => (cur.includes(id) ? cur.filter((item) => item !== id) : [...cur, id]));
  };
  const countOk = picked.length >= 1;
  // 꺼진 단추 모양이 따로 없어 눌러도 아무 일 없는 것처럼 보였다(11/10). 단추는 두고, 하나도 안 골랐으면 이유를 알린다.
  const send = async () => {
    if (app.busy) return;
    const count = picked.length;
    if (!countOk) {
      setHint('보낼 질문을 하나 이상 골라 주세요.');
      return;
    }
    if (await app.sendQuestions(picked)) {
      setPicked([]);
      showToast(`아이에게 질문 ${count}개를 보냈어요`);
    }
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
        {data.bank.map((item) => (
          <label key={item.id} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', cursor: 'pointer' }}>
            <input type="checkbox" checked={picked.includes(item.id)} onChange={() => toggle(item.id)} />
            <span>
              <span className="chip c-sand">{item.category}</span> {item.text}
            </span>
          </label>
        ))}
        {data.has_pending_questions ? (
          <div className="note">아이가 아직 답하지 않은 질문이 있어요. 보내면 새 질문으로 바뀝니다.</div>
        ) : null}
        <div>
          <button type="button" className="btn btn-p" aria-disabled={!countOk || app.busy} style={countOk && !app.busy ? undefined : { opacity: 0.5 }} onClick={send}>
            {app.busy ? '보내는 중…' : '아이에게 보내기'}
          </button>
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
