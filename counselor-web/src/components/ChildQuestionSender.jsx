// 콩콩 '질문 보내기'(3~4개 골라 아이 앱으로). 사례 아이 연계 · 아이 상세 · 다음 상담 준비 '아이 앱으로 먼저' 탭이 같이 쓴다.
// app 은 useCaseChildApp 의 값. bare 면 바깥 카드 없이 안쪽만 그린다(다른 카드 안에 넣을 때).
// 연결 전이면 아이 연계(아이 상세)에서 연결하라고 안내한다.
import { useState } from 'react';
import A from './A';
import { screenHref } from '../data/screens/links';

export default function ChildQuestionSender({ app, caseId, bare = false }) {
  const [picked, setPicked] = useState([]);
  const data = app.data;
  if (!data) return null;

  const toggle = (id) => setPicked((cur) => (cur.includes(id) ? cur.filter((item) => item !== id) : [...cur, id]));
  const canSend = picked.length >= 3 && picked.length <= 4 && !app.busy;
  const send = async () => {
    if (await app.sendQuestions(picked)) setPicked([]);
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
          <button type="button" className="btn btn-p" disabled={!canSend} onClick={send}>
            아이에게 보내기
          </button>
        </div>
      </>
    );
  }

  const title = data.status === 'LINKED' && data.can_read_feed ? `질문 보내기 · ${picked.length}개 선택 (3~4개)` : '질문 보내기';
  if (bare) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <b>{title}</b>
        {body}
      </div>
    );
  }
  return (
    <section className="card" aria-label="질문 보내기" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <h2 className="h2">{title}</h2>
      {body}
    </section>
  );
}
