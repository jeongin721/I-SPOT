// 콩콩 '질문 보내기'(1개 이상 골라 아이 앱으로). 사례 아이 연계 · 아이 상세 · 다음 상담 준비 '아이 앱으로 먼저' 탭이 같이 쓴다.
// app 은 useCaseChildApp 의 값. bare 면 바깥 카드 없이 안쪽만 그린다(다른 카드 안에 넣을 때).
// 연결 전이면 아이 연계(아이 상세)에서 연결하라고 안내한다.
// 11/10 디자인(FollowupQ '승인' → '발송 예약') · #173: 단추는 '발송 예약'(deliver EVENING — 그날 저녁 시각부터 아이 앱에 보이고,
// 그 시각이 지났으면 서버가 바로 보낸다). 예약해 둔 질문(scheduled_questions)이 있으면 '발송 예약 · 오늘 18:00 발송' 과 '예약 취소'.
// 알림 문구는 보낸 뒤 다시 받은 값으로 정한다(예약됐는지 · 바로 갔는지는 서버가 정하므로).
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
  const [toast, showToast] = useSentToast();
  const [hint, setHint] = useState('');
  // 예약을 보낸 뒤 다시 받은 값이 오면 알림을 띄운다({ count, data: 보내기 전 값 }).
  const [sent, setSent] = useState(null);
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
  const send = async () => {
    if (app.busy) return;
    const count = picked.length;
    if (!countOk) {
      setHint('발송 예약할 질문을 하나 이상 골라 주세요.');
      return;
    }
    const before = data;
    if (await app.sendQuestions(picked, 'EVENING')) {
      setPicked([]);
      setSent({ count, data: before });
    }
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
            <span className="note">질문 {scheduled.count}개 · 다시 예약하면 앞 예약은 취소돼요.</span>
            <button type="button" className="btn btn-sm btn-s" aria-disabled={app.busy} onClick={cancel} style={{ marginLeft: 'auto' }}>
              예약 취소
            </button>
          </div>
        ) : data.has_pending_questions ? (
          <div className="note">아이가 아직 답하지 않은 질문이 있어요. 예약한 질문이 아이 앱에 보이면 새 질문으로 바뀝니다.</div>
        ) : null}
        <div>
          <button type="button" className="btn btn-p" aria-disabled={!countOk || app.busy} style={countOk && !app.busy ? undefined : { opacity: 0.5 }} onClick={send}>
            {app.busy ? '예약하는 중…' : '발송 예약'}
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
