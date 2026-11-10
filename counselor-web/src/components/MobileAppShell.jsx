// 상담사 앱(폰) 공통 틀: 머리(작은 제목 · 제목 · 알림 · 설정) · 아래 탭 5개 · 알림 시트.
// 디자인: 앱 · 녹음 / 앱 · 업로드(2026-11-10 zip)의 header.ahd · nav.tabs · 알림 sheet 를 그대로 옮겼다(클래스만 ma- 접두어).
//  - 로그인하지 않았으면 로그인 화면으로 보내고, 로그인한 뒤 이 화면으로 돌아온다(appReturn.ts).
//  - 연결이 없어 로그인 확인이 안 되면(확인 중 · 오류) 이 폰에 기억한 같은 토큰의 계정으로 이어서 쓴다(appOffline.ts).
//    그래서 연결 없이 앱을 열어도 녹음 · 대기열이 보인다. 401(로그인 만료)은 로그인 화면으로 간다.
//  - 알림: 업로드 실패 줄(폰 대기열) + '오늘 남은 상담 N건'(오늘 일정 중 지금 뒤의 상담, 서버 일정). 디자인의
//    '상담 전 브리핑이 준비됐어요' 는 브리핑이 '준비됐는지' 정할 서버 값이 없어 넣지 않았다.
//  - 홈 · 일정 · 메모 탭과 설정 단추는 각 앱 화면으로 간다(11/10). 홈은 머리에 제목 대신 I-SPOT 표시(디자인).
import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { useAuthSession } from '../data/useAuthSession';
import { needsLogin } from '../data/screens/common';
import { rememberAppReturn } from '../data/appReturn';
import { cachedAppUserId, rememberAppUser } from '../data/appOffline';
import { retryRecording, uploadAsNewSession } from '../data/appRecordings';
import { useAppRecordings } from '../data/useAppRecordings';
import { useAppSchedule, ymd } from '../data/useAppSchedule';
import { useTheme } from '../theme';
import '../styles/mobile-app.css';

const TABS = [
  ['home', '홈', '/AppHome'],
  ['up', '업로드', '/AppUpload'],
  ['rec', '', '/AppRecord'],
  ['cal', '일정', '/AppSchedule'],
  ['memo', '메모', '/AppMemo'],
];

export function whenText(ms) {
  const d = new Date(ms);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const hm = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  if (d.toDateString() === today.toDateString()) return Date.now() - ms < 60_000 ? '방금' : `오늘 ${hm}`;
  if (d.toDateString() === yesterday.toDateString()) return `어제 ${hm}`;
  return `${d.getMonth() + 1}/${d.getDate()} ${hm}`;
}

export function sizeText(bytes) {
  return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + 'MB' : Math.max(1, Math.round(bytes / 1024)) + 'KB';
}

export function whoText(item) {
  return item.childLabel + ' · ' + (item.sessionNumber ? item.sessionNumber + '회차' : '새 회차');
}

function TabIcon({ k }) {
  if (k === 'home')
    return (
      <>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3.5 11L12 4l8.5 7"></path><path d="M6 9.5V20h4.5v-5.5h3V20H18V9.5"></path></svg>
        <svg className="ma-fi1" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" fillRule="evenodd" d="M12 2.6 2.6 10.3c-.4.3-.6.8-.6 1.3V20a1.5 1.5 0 0 0 1.5 1.5h17A1.5 1.5 0 0 0 22 20v-8.4c0-.5-.2-1-.6-1.3zM9.8 21.5v-5.8h4.4v5.8z"></path></svg>
      </>
    );
  if (k === 'rec')
    return (
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"></rect><path d="M5 11a7 7 0 0 0 14 0M12 18v3"></path></svg>
    );
  if (k === 'up')
    return (
      <>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 15V4M7 9l5-5 5 5"></path><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"></path></svg>
        <svg className="ma-fi1" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M2.5 14h5.2l1.6 2.4h5.4l1.6-2.4h5.2V19a2 2 0 0 1-2 2h-15a2 2 0 0 1-2-2z"></path><path fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" d="M12 13V3.5M7.5 8 12 3.5 16.5 8"></path></svg>
      </>
    );
  if (k === 'cal')
    return (
      <>
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"></rect><path d="M16 3v4M8 3v4M3 10h18"></path></svg>
        <svg className="ma-fi1" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M5 4.5h14A2.5 2.5 0 0 1 21.5 7v12a2.5 2.5 0 0 1-2.5 2.5H5A2.5 2.5 0 0 1 2.5 19V7A2.5 2.5 0 0 1 5 4.5z"></path><path fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" d="M16 2.5v4M8 2.5v4"></path><path fill="none" style={{ stroke: 'var(--card)' }} strokeWidth="2" d="M2.5 10h19"></path></svg>
      </>
    );
  return (
    <>
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 3h10l4 4v14H5z"></path><path d="M9 11h6M9 15h6"></path></svg>
      <svg className="ma-fi1" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="currentColor" d="M5.5 2.5h9.6l4.4 4.4V20a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4.5 20V4A1.5 1.5 0 0 1 5.5 2.5z"></path><path fill="none" style={{ stroke: 'var(--card)' }} strokeWidth="2" strokeLinecap="round" d="M8.5 11h7M8.5 15h7"></path></svg>
    </>
  );
}

/**
 * @param cur       지금 탭('home' · 'up' · 'rec' · 'cal' · 'memo' · 'set'(설정 단추))
 * @param screen    화면 이름(맨 바깥 .ma-s-<screen>, 화면별 규칙용)
 * @param sub       제목 위 작은 글(글 · 요소, 또는 ({ userId }) => 요소 — 훅을 쓰는 작은 컴포넌트를 넣을 때)
 * @param title     제목. brand 면 제목 대신 I-SPOT 표시(홈)
 * @param head      ({ userId }) => 작은 제목 + 제목 요소(둘이 같은 서버 값을 쓸 때, 브리핑)
 * @param children  (ctx) => 본문. ctx = { userId, me, logout, items, fails, loaded, storageError, notReady }
 */
export default function MobileAppShell({ cur, screen, sub, title, titleStyle, brand, head, children }) {
  const session = useAuthSession();
  const { pathname } = useLocation();
  const theme = useTheme();
  const signedId = session.status === 'signedIn' ? session.me?.id ?? null : null;
  const userId = signedId ?? (session.status === 'checking' || session.status === 'error' ? cachedAppUserId() : null);
  const { items, loaded, storageError } = useAppRecordings(userId);
  const [ntOpen, setNtOpen] = useState(false);
  const [toast, setToast] = useState('');
  const today = ymd(new Date());
  const todaySchedule = useAppSchedule(!!signedId, today, today);
  const toastTimer = useRef(null);

  useEffect(() => () => window.clearTimeout(toastTimer.current), []);
  useEffect(() => {
    if (signedId) rememberAppUser(signedId);
  }, [signedId]);

  if (needsLogin(session)) {
    rememberAppReturn(pathname);
    return <Navigate to="/Login" replace />;
  }

  const notReady = (name) => {
    setToast(`${name} 화면은 준비 중이에요`);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(''), 1800);
  };

  const fails = items.filter((x) => x.status === 'fail');
  const notes = fails.map((x) => ({
    id: x.id,
    title: '업로드 실패 · 녹음',
    sub: x.fileName + ' · ' + whenText(x.updatedAt),
    desc: x.error || '',
    act: x.needNewSession ? '새 회차로 올리기' : '다시 올리기',
    go: () => void (x.needNewSession ? uploadAsNewSession(x.id) : retryRecording(x.id)),
  }));
  const nowHm = new Date().toTimeString().slice(0, 5);
  const leftToday = todaySchedule.items.filter((e) => e.kind === 'CONSULT' && (!e.time || e.time >= nowHm));
  if (leftToday.length > 0) {
    notes.push({
      id: 'today',
      plain: true,
      title: `오늘 남은 상담 ${leftToday.length}건`,
      sub: leftToday.map((e) => [e.time, e.child_alias].filter(Boolean).join(' ')).join(' · '),
      desc: '',
      href: '/AppSchedule',
      linkLabel: '일정 보기',
    });
  }
  const stop = (ev) => ev.stopPropagation();
  const rootCls = 'ma-app' + (screen ? ' ma-s-' + screen : '') + (theme.dark ? ' ma-dark' : '');

  return (
    <div className={rootCls}>
      <header className="ma-ahd">
        <div className="ma-tl">
          {head ? (
            head({ userId })
          ) : brand ? (
            <span className="ma-brand">
              <span className="ma-mk">IS</span>I-SPOT
            </span>
          ) : (
            <>
              <div className="ma-sub">{typeof sub === 'function' ? sub({ userId }) : sub}</div>
              <h1 style={titleStyle}>{title}</h1>
            </>
          )}
        </div>
        <button type="button" className="ma-ibtn" aria-label={`알림 ${notes.length}건`} onClick={() => setNtOpen(!ntOpen)}>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9.5a6 6 0 0 1 12 0c0 4.2 1.4 6 2.2 6.9a.6.6 0 0 1-.45 1H4.25a.6.6 0 0 1-.45-1C4.6 15.5 6 13.7 6 9.5z"></path><path d="M10 20.2a2.2 2.2 0 0 0 4 0"></path></svg>
          {notes.length > 0 && <span className="ma-badge">{notes.length}</span>}
        </button>
        <Link className={cur === 'set' ? 'ma-ibtn ma-on' : 'ma-ibtn'} to="/AppSettings" aria-label="설정" aria-current={cur === 'set' ? 'page' : 'false'}>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
        </Link>
      </header>
      <main className="ma-amain">{children({ userId, me: session.me, logout: session.logout, items, fails, loaded: loaded && !!userId, storageError, notReady })}</main>
      <nav className="ma-tabs" aria-label="앱 메뉴">
        {TABS.map(([k, label, to]) => {
          const cls = 'ma-tab' + (k === 'rec' ? ' ma-tab-rec' : '') + (k === cur ? ' ma-on' : '');
          const inner = (
            <>
              <span className="ma-ti">
                <TabIcon k={k} />
              </span>
              {label && <span>{label}</span>}
            </>
          );
          const aria = k === 'rec' ? '녹음' : label;
          return to ? (
            <Link key={k} className={cls} to={to} aria-label={aria} aria-current={k === cur ? 'page' : 'false'}>
              {inner}
            </Link>
          ) : (
            <a key={k} className={cls} href="#" aria-label={aria} aria-current="false" onClick={(ev) => { ev.preventDefault(); notReady(label); }}>
              {inner}
            </a>
          );
        })}
      </nav>
      {ntOpen && (
        <div className="ma-ov" onClick={() => setNtOpen(false)}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="알림" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>알림</b>
              <button type="button" className="ma-btn ma-btn-sm" onClick={() => setNtOpen(false)}>
                닫기
              </button>
            </div>
            {notes.length === 0 && <span className="ma-note">새 알림이 없어요</span>}
            {notes.map((n) => (
              <div key={n.id} className={n.plain ? 'ma-nt' : 'ma-nt ma-red'}>
                <b>{n.title}</b>
                <span className="ma-note">{n.sub}</span>
                {n.desc && <span style={{ fontSize: '13.5px' }}>{n.desc}</span>}
                {n.go && (
                  <button type="button" className="ma-btn ma-btn-sm ma-btn-p" style={{ alignSelf: 'flex-start' }} onClick={n.go}>
                    {n.act}
                  </button>
                )}
                {n.href && (
                  <Link className="ma-btn ma-btn-sm" style={{ alignSelf: 'flex-start' }} to={n.href} onClick={() => setNtOpen(false)}>
                    {n.linkLabel}
                  </Link>
                )}
              </div>
            ))}
          </section>
        </div>
      )}
      {toast && (
        <div className="ma-toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
