// 실제 사례의 아이 연계 탭. 콩콩 앱과 같은 구조(연결 · 아이가 보낸 것 · 질문 보내기)로 서버 값을 보인다.
// 사례 ID 가 없는 예시 화면은 CaseApp.jsx 의 디자인 목업을 그대로 쓴다.
import { useState } from 'react';
import A from '../components/A';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCarryHref } from '../data/useCarryHref';
import { useCaseChildApp } from '../data/useCaseChildApp';
import { useCaseDetail } from '../data/useCaseDetail';
import { useTheme } from '../theme';
import './CaseApp.css';

const STATUS = {
  NOT_LINKED: ['미연결', 'chip c-check'],
  INVITED: ['초대 대기', 'chip c-sand'],
  LINKED: ['연결됨', 'chip c-ok'],
};
const LEVEL = { RED: ['바로 확인', 'chip c-urgent'], AMBER: ['살펴볼 답', 'chip c-check'], SKIP: ['답하기 어려움', 'chip c-sand'] };
const dateTime = (value) =>
  value ? new Date(value).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—';

function LevelChip({ level }) {
  const item = LEVEL[level];
  return item ? <span className={item[1]}>{item[0]}</span> : null;
}

function FeedItem({ event }) {
  if (event.kind !== 'ANSWERS') {
    const label = event.kind === 'LINKED' ? '아이가 앱을 연결했어요' : `질문 ${event.payload.count}개를 보냈어요`;
    return (
      <div className="note" style={{ padding: '10px 0', borderTop: '1px solid #E8E5DD' }}>
        {dateTime(event.created_at)} · {label}
      </div>
    );
  }
  return (
    <div style={{ padding: '12px 0', borderTop: '1px solid #E8E5DD', display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <LevelChip level={event.level} />
        <b>질문 답변</b>
        <span className="note">{dateTime(event.created_at)}</span>
      </div>
      {event.payload.items.map((item) => (
        <div key={item.question_id} style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '4px 16px' }}>
          <span className="sub">{item.question}</span>
          <span style={{ fontWeight: 600 }}>
            {item.answer} <LevelChip level={item.level} />
          </span>
        </div>
      ))}
    </div>
  );
}

export default function CaseChildApp({ caseId }) {
  const session = useAuthSession();
  const carry = useCarryHref();
  const theme = useTheme();
  const enabled = session.status === 'signedIn';
  const detail = useCaseDetail(caseId, { enabled });
  const app = useCaseChildApp(caseId, enabled);
  const [picked, setPicked] = useState([]);
  const data = app.data;
  const status = STATUS[data?.status] ?? STATUS.NOT_LINKED;
  const canSend = picked.length >= 3 && picked.length <= 4 && !app.busy;
  const toggle = (id) => setPicked((cur) => (cur.includes(id) ? cur.filter((item) => item !== id) : [...cur, id]));
  const send = async () => {
    if (await app.sendQuestions(picked)) setPicked([]);
  };
  const info = detail.caseInfo;

  return (
    <div className="pg-CaseApp">
      <div
        className={theme.cls}
        style={{
          minHeight: '100vh',
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
        <main style={{ flex: '999 1 640px', minWidth: '0', padding: '30px 36px 56px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="thm-bar">
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          <nav aria-label="위치" className="note">
            <A to="/CaseList">사례 관리</A> › {info ? `${info.name} ${info.caseNumber}` : '…'}
          </nav>
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{info?.name ?? '…'}</h1>
            <span className={status[1]}>{status[0]}</span>
          </section>
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={carry('/CaseDetail')}>내담자 정보</A>
            <A to={carry('/CaseHistory')}>상담 이력</A>
            <A to={carry('/CaseDocs')}>문서함</A>
          </nav>

          {app.error ? <p role="alert">{app.error}</p> : null}
          {app.actionError ? <p role="alert">{app.actionError}</p> : null}

          {data ? (
            <>
              <section className="card" aria-label="앱 연결" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <h2 className="h2">콩콩 앱 연결</h2>
                {data.status === 'LINKED' ? (
                  <div className="sub">
                    연결 {dateTime(data.linked_at)} · 마지막 응답 {dateTime(data.last_response_at)}
                  </div>
                ) : (
                  <>
                    <div className="sub">코드를 만들어 아이에게 직접 알려 주세요. 코드는 72시간 동안, 한 번만 쓸 수 있어요.</div>
                    {app.invite ? (
                      <div style={{ fontSize: '24px', fontWeight: 700, letterSpacing: '1px' }}>{app.invite.code}</div>
                    ) : null}
                    <div>
                      <button type="button" className="btn btn-s" disabled={app.busy} onClick={app.createInvite}>
                        {data.status === 'INVITED' ? '코드 다시 만들기' : '연결 코드 만들기'}
                      </button>
                    </div>
                  </>
                )}
              </section>

              {data.can_read_feed ? (
                <section className="card" aria-label="아이가 보낸 것" style={{ padding: '20px 22px' }}>
                  <h2 className="h2" style={{ marginBottom: '8px' }}>아이가 보낸 것</h2>
                  {data.feed.length ? (
                    data.feed.map((event) => <FeedItem key={event.id} event={event} />)
                  ) : (
                    <div className="note">아직 받은 내용이 없어요.</div>
                  )}
                </section>
              ) : (
                <p className="note">아이가 보낸 내용은 담당 상담사만 볼 수 있어요.</p>
              )}

              {data.status === 'LINKED' ? (
                <section className="card" aria-label="질문 보내기" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <h2 className="h2">질문 보내기 · {picked.length}개 선택 (3~4개)</h2>
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
                </section>
              ) : null}
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
