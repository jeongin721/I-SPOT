// 실제 사례의 아이 연계 탭. 콩콩 앱과 같은 구조(연결 · 아이가 보낸 것 · 질문 보내기)로 서버 값을 보인다.
// 사례 ID 가 없는 예시 화면은 CaseApp.jsx 의 디자인 목업을 그대로 쓴다.
import A from '../components/A';
import ChildQuestionSender from '../components/ChildQuestionSender';
import Sidebar from '../components/Sidebar';
import NotiBell from '../components/NotiBell';
import ThemeToggle from '../components/ThemeToggle';
import { useAuthSession } from '../data/useAuthSession';
import { useCarryHref } from '../data/useCarryHref';
import { CHILD_ALERT_TEXT, useCaseChildApp } from '../data/useCaseChildApp';
import { useCaseDetail } from '../data/useCaseDetail';
import { useTheme } from '../theme';
import { screenHref } from '../data/screens/links';
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
  if (event.kind === 'ALERT') {
    return (
      <div style={{ padding: '12px 0', borderTop: '1px solid #E8E5DD', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
        <span className="chip c-urgent">긴급</span>
        <b>급하다고 알림</b>
        <span className="note">
          {dateTime(event.created_at)}
          {event.payload.repeat_count ? ` · ${event.payload.repeat_count}번 더 누름(마지막 ${dateTime(event.payload.last_at)})` : ''}
          {event.acknowledged_at ? ` · 확인 ${dateTime(event.acknowledged_at)}` : ' · 확인 전'}
        </span>
      </div>
    );
  }
  if (event.kind !== 'ANSWERS') {
    const label =
      event.kind === 'LINKED'
        ? '아이가 앱을 연결했어요'
        : event.kind === 'UNLINKED'
          ? '아이가 앱 연결을 해지했어요'
        : event.payload.withdrawn
          ? `보낸 질문 ${event.payload.count}개를 취소했어요`
          : `질문 ${event.payload.count}개를 보냈어요`;
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
        <span className="note">
          {dateTime(event.created_at)}
          {event.needs_ack ? (event.acknowledged_at ? ` · 확인 ${dateTime(event.acknowledged_at)}` : ' · 확인 전') : ''}
        </span>
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

export default function CaseChildApp({ caseId, fromChild = false }) {
  const session = useAuthSession();
  const carry = useCarryHref();
  const theme = useTheme();
  const enabled = session.status === 'signedIn';
  const detail = useCaseDetail(caseId, { enabled });
  const app = useCaseChildApp(caseId, enabled);
  const data = app.data;
  const status = STATUS[data?.status] ?? STATUS.NOT_LINKED;
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
        <Sidebar active={fromChild ? 'ChildLink' : 'CaseList'} session={session} />
        <main style={{ flex: '999 1 640px', minWidth: '0', padding: '30px 36px 56px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="thm-bar">
            <NotiBell session={session} />
            <ThemeToggle />
          </div>
          {fromChild ? (
            <nav aria-label="위치" className="note">
              <A to="/ChildLink">아이 연계</A> › <A to={screenHref('/ChildDetail', { caseId })}>{info?.name ?? '…'}</A> › 과거 답변 기록
            </nav>
          ) : (
            <nav aria-label="위치" className="note">
              <A to="/CaseList">사례 관리</A> › {info ? `${info.name} ${info.caseNumber}` : '…'}
            </nav>
          )}
          <section style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ margin: '0', fontSize: '28px', fontWeight: '700' }}>{info?.name ?? '…'}</h1>
            <span className={status[1]}>{status[0]}</span>
            <A className="btn btn-sm btn-s" to={screenHref('/ChildDetail', { caseId })} style={{ marginLeft: 'auto' }}>
              {fromChild ? '← 아이 상세' : '아이 상세 보기 →'}
            </A>
          </section>
          {/* 아이 연계에서 왔으면 사례 상세 탭(사례 관리 메뉴로 가는 길)을 두지 않는다. */}
          {fromChild ? null : (
          <nav className="tabs" aria-label="사례 상세 메뉴">
            <A to={carry('/CaseDetail')}>내담자 정보</A>
            <A to={carry('/CaseHistory')}>상담 이력</A>
            <A to={carry('/CaseDocs')}>문서함</A>
          </nav>
          )}

          {app.error ? <p role="alert">{app.error}</p> : null}
          {app.actionError ? <p role="alert">{app.actionError}</p> : null}

          {data ? (
            <>
              {data.open_alerts.map((alert) => (
                <section
                  key={alert.id}
                  role="alert"
                  aria-label="긴급 알림"
                  style={{ background: '#F8E6DF', border: '1.5px solid #B0452C', borderRadius: '14px', padding: '14px 18px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 16px', color: '#2B2A26' }}
                >
                  <div style={{ flex: '1 1 320px' }}>
                    <b style={{ color: '#B0452C' }}>긴급 · {dateTime(alert.last_at ?? alert.created_at)}</b>
                    <br />
                    {CHILD_ALERT_TEXT[alert.reason]}
                    {alert.repeat_count ? ` ${alert.repeat_count}번 더 눌렀어요.` : ''}
                    {data.can_read_feed ? ' 아이의 안전을 고려해 연락 방법을 판단해 주세요.' : ' 담당 상담사에게 전달해 주세요.'}
                  </div>
                  {alert.can_ack ? (
                    <button type="button" className="btn btn-p" disabled={app.busy} onClick={() => app.acknowledge(alert.id)}>
                      확인했어요
                    </button>
                  ) : null}
                </section>
              ))}
              <section className="card" aria-label="앱 연결" style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <h2 className="h2">콩콩 앱 연결</h2>
                {data.status === 'LINKED' ? (
                  <div className="sub">
                    연결 {dateTime(data.linked_at)} · 마지막 응답 {dateTime(data.last_response_at)}
                    <br />
                    아이 앱에 다음 상담 날짜 · 시간이 보여요. 장소는 정기 · 초기 · 종결 상담만 보여요.
                  </div>
                ) : !data.can_read_feed ? (
                  <div className="sub">코드는 담당 상담사가 만들어요.</div>
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

              <ChildQuestionSender app={app} caseId={caseId} />
            </>
          ) : null}
        </main>
      </div>
    </div>
  );
}
