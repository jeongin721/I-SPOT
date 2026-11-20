// 상담사 앱(폰) · 홈
// 원본: 앱 · 홈 (시작 화면 app · 인사 · 기능 4개 · 사례 목록 · 사내 공지사항 · 알림) 2026-11-10 zip 의 AppHome.dc.html
//
// 서버 연결
//  - 인사: 로그인한 상담사 이름(GET /auth/me). 아래 줄은 오늘 날짜 · 오늘 상담 수.
//  - 내 사례 현황: 담당 사례 = 내 진행 중 사례 수(useAppCases), 이번 주 상담 · 오늘 상담 = 이번 주(월~일) · 오늘 일정 중 상담(GET /schedule/events).
//    누르면 앱 · 사례 목록.
//  - 사내 공지사항: GET /notices(28절, 최신 20건). 누르면 내용 창, 읽은 공지는 디자인처럼 폰에 둔다(ispot-app-notice).
//    '중요' 는 빨간 표시. 아래 줄은 '날짜 · 부서'(부서가 없으면 쓴 사람). 공지가 없으면 한 줄 안내.
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { closeWithAnim } from '../components/MobileAppShellMotion';
import { notices as noticesApi } from '../api/endpoints';
import { useRemote } from '../data/useRemote';
import { useAppCases } from '../data/useAppCases';
import { addDays, mondayOf, useAppSchedule, ymd } from '../data/useAppSchedule';

const W = ['일', '월', '화', '수', '목', '금', '토'];
const READ_KEY = 'ispot-app-notice';

function readMarks() {
  try {
    const value = JSON.parse(localStorage.getItem(READ_KEY) || '{}');
    return value && typeof value === 'object' ? value : {};
  } catch {
    return {};
  }
}

function noticeMeta(n) {
  const d = new Date(n.created_at);
  const who = n.team || n.author_name;
  return `${d.getMonth() + 1}/${d.getDate()}${who ? ` · ${who}` : ''}`;
}

function Notices() {
  const list = useRemote('notices', () => noticesApi.list(20), '공지사항을 불러오지 못했습니다.', () => false);
  const [read, setRead] = useState(readMarks);
  const [open, setOpen] = useState(null);
  const ovRef = useRef(null);
  const rows = list.data || [];
  const unread = rows.filter((n) => !read[n.id]).length;
  const cur = open ? rows.find((n) => n.id === open) : null;
  const show = (n) => {
    const next = { ...read, [n.id]: 1 };
    // 읽음 표시가 너무 쌓이지 않게 지금 목록에 있는 공지만 남긴다.
    const kept = Object.fromEntries(rows.filter((r) => next[r.id]).map((r) => [r.id, 1]));
    setRead(kept);
    try {
      localStorage.setItem(READ_KEY, JSON.stringify(kept));
    } catch {
      // 저장이 막힌 브라우저 — 이번 화면에서만 읽음으로 둔다.
    }
    setOpen(n.id);
  };
  const close = () => closeWithAnim(ovRef.current, () => setOpen(null));
  const stop = (ev) => ev.stopPropagation();

  return (
    <>
      <div className="ma-sec-h">
        <h2>사내 공지사항</h2>
        {rows.length > 0 && <span className="ma-note">{unread ? `읽지 않음 ${unread}건` : '모두 읽음'}</span>}
      </div>
      <section className="ma-card ma-list" aria-label="사내 공지사항">
        {rows.map((n) => (
          <button key={n.id} type="button" className={read[n.id] ? 'ma-li' : 'ma-li ma-unread'} onClick={() => show(n)}>
            <span className="ma-lt">
              <b>{n.title}</b>
              <span className="ma-note">{noticeMeta(n)}</span>
            </span>
            {n.important && <span className="ma-chip ma-red">중요</span>}
          </button>
        ))}
        {rows.length === 0 && (
          <div className="ma-li" style={{ cursor: 'default' }}>
            <span className="ma-lt">
              <span className="ma-note">{list.loading ? '불러오는 중입니다' : list.error || '공지사항이 없습니다'}</span>
            </span>
          </div>
        )}
      </section>
      {cur && (
        <div className="ma-ov" ref={ovRef} onClick={close}>
          <section className="ma-sheet" role="dialog" aria-modal="true" aria-label="공지사항" onClick={stop}>
            <span className="ma-grab" aria-hidden="true"></span>
            <div className="ma-sh-hd">
              <b>{cur.title}</b>
            </div>
            <span className="ma-note">{noticeMeta(cur)}</span>
            <p className="ma-body">{cur.body}</p>
            <button type="button" className="ma-btn ma-btn-block" onClick={close}>
              닫기
            </button>
          </section>
        </div>
      )}
    </>
  );
}

function HomeBody({ userId, me }) {
  const my = useAppCases(userId);
  const now = new Date();
  const today = ymd(now);
  const mon = mondayOf(now);
  const week = useAppSchedule(!!userId, ymd(mon), ymd(addDays(mon, 6)));
  const consults = week.items.filter((e) => e.kind === 'CONSULT');
  const todayN = consults.filter((e) => e.date === today).length;
  const num = (value, loading) => (loading ? '—' : String(value));

  return (
    <>
      <section className="ma-hello" aria-label="인사">
        <span>안녕하세요,</span>
        <b>{me?.name ? `${me.name} 상담원님` : '상담원님'}</b>
        <small>{`${now.getMonth() + 1}월 ${now.getDate()}일 ${W[now.getDay()]}요일 · 오늘 상담 ${week.loading ? '—' : todayN}건`}</small>
      </section>
      <Link className="ma-hero" to="/AppCases" aria-label="사례 목록 보기">
        <span className="ma-hero-top">
          <span>내 사례 현황</span>
          <span className="ma-hero-go">
            사례 목록
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"></path></svg>
          </span>
        </span>
        <span className="ma-stats">
          <span className="ma-stat">
            <b>{num(my.rows.length, my.loading)}</b>
            <span>담당 사례</span>
          </span>
          <span className="ma-stat">
            <b>{num(consults.length, week.loading)}</b>
            <span>이번 주 상담</span>
          </span>
          <span className="ma-stat">
            <b>{num(todayN, week.loading)}</b>
            <span>오늘 상담</span>
          </span>
        </span>
      </Link>
      {(my.error || week.error) && <span className="ma-err">{my.error || week.error}</span>}
      <Notices />
    </>
  );
}

export default function AppHome() {
  return (
    <MobileAppShell cur="home" screen="home" brand>
      {(ctx) => <HomeBody {...ctx} />}
    </MobileAppShell>
  );
}
