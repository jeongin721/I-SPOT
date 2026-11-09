// 아이가 콩콩 앱에서 '급하다고 알리기' 를 보내면 어느 화면에서든 보이는 위쪽 배너. 상담사 · 관리자 사이드바가 띄운다.
// 담당 상담사는 자기 사례, 관리자는 전체(API_CONTRACT 23절). 확인 처리는 사례의 아이 연계 탭에서 한다.
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import A from './A';
import { childApp } from '../api/endpoints';
import { screenHref } from '../data/screens/links';
import { CHILD_ALERTS_CHANGED, CHILD_ALERT_TEXT } from '../data/useCaseChildApp';
import { useRemote } from '../data/useRemote';

const REFRESH_MS = 30_000;
// 서버 스위치가 꺼져 있으면 잠시 묻지 않는다. 켠 뒤 열려 있던 탭도 알림을 받도록 5분 뒤 다시 묻는다.
const OFF_RETRY_MS = 5 * 60_000;
let offUntil = 0;

const loadAlerts = () =>
  Date.now() < offUntil
    ? Promise.resolve([])
    : childApp.openAlerts().catch((caught) => {
        if (caught?.code !== 'CHILD_APP_DISABLED') throw caught;
        offUntil = Date.now() + OFF_RETRY_MS;
        return [];
      });

export default function ChildAlertBanner({ session }) {
  const userId = session?.status === 'signedIn' ? session.me?.id ?? null : null;
  const remote = useRemote(userId, loadAlerts, '긴급 알림을 불러오지 못했습니다.', () => false);
  const { refresh } = remote;

  useEffect(() => {
    if (!userId) return undefined;
    const timer = window.setInterval(() => {
      if (Date.now() >= offUntil) refresh();
    }, REFRESH_MS);
    window.addEventListener(CHILD_ALERTS_CHANGED, refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener(CHILD_ALERTS_CHANGED, refresh);
    };
  }, [userId, refresh]);

  const alerts = remote.data ?? [];
  if (!alerts.length) return null;
  const first = alerts[0];
  const time = new Date(first.last_at ?? first.created_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' });

  // 사이드바의 쌓임 맥락에 갇히면 위쪽 도구 막대에 가려 단추가 눌리지 않는다.
  return createPortal(
    <div
      role="alert"
      style={{
        position: 'fixed',
        top: '12px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        width: 'min(640px, calc(100vw - 32px))',
        background: '#F8E6DF',
        border: '1.5px solid #B0452C',
        borderRadius: '14px',
        padding: '12px 16px',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: '8px 14px',
        color: '#2B2A26',
        fontSize: '14px',
        boxShadow: '0 8px 24px rgba(46,43,40,.22)',
      }}
    >
      <span style={{ flex: '1 1 300px' }}>
        <b style={{ color: '#B0452C' }}>긴급 · {time}</b> {first.child_alias} ({first.case_number}) {CHILD_ALERT_TEXT[first.reason]}
        {first.repeat_count ? ` ${first.repeat_count}번 더 눌렀어요.` : ''}
        {alerts.length > 1 ? ` 외 ${alerts.length - 1}건` : ''}
      </span>
      <A className="btn btn-sm btn-p" to={screenHref('/CaseApp', { caseId: first.case_id })}>
        확인하러 가기 →
      </A>
    </div>,
    document.body,
  );
}
