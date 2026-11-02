// 위쪽 바 알림 종(10/29 디자인 nt-*). 알림은 최초접수 일정의 학대 판정 뒤 법정 기한(3일 유선 상담 · 7일 주변 인물 ·
// 30일 계획서, 11/02 일정 연결)이다. 내가 접수한 최초접수의 기한 중 완료 표시하지 않은 것만, 마감이 가까운 것부터 보인다.
// 읽음은 이 브라우저에만 남긴다(ispot-noti-read — 기기마다 따로, 서버에 남기지 않는다). 누르면 그 날 달력으로 간다.
// session 은 화면의 useAuthSession() 결과(종이 /auth/me 를 따로 부르지 않게). 바깥을 누르거나 Esc 를 누르면 닫힌다.
import { useEffect, useRef, useState } from 'react';
import A from './A';
import { pad2 } from '../data/time';
import { useSchedule } from '../data/useSchedule';
import { INTAKE_TASKS, DATE_PARAM } from '../data/screens/schedule';

const READ_KEY = 'ispot-noti-read';
const DAYS = ['일', '월', '화', '수', '목', '금', '토'];

function readIds() {
  try {
    const value = JSON.parse(window.localStorage.getItem(READ_KEY) || '[]');
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function writeIds(ids) {
  try {
    window.localStorage.setItem(READ_KEY, JSON.stringify(ids.slice(-500)));
  } catch {
    // 저장소를 못 쓰면 읽음만 남지 않는다.
  }
}

const ymd = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;

/** 기한 알림을 찾는 기간: 오늘 앞뒤 30일 접수(기한이 30일까지라서). */
function bellRange() {
  const now = new Date();
  return {
    from: ymd(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30)),
    to: ymd(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 30)),
  };
}

export default function NotiBell({ session }) {
  const [open, setOpen] = useState(false);
  const [read, setRead] = useState(readIds);
  const [range] = useState(bellRange);
  const wrap = useRef(null);
  const fallback = { status: 'signedOut', me: null };
  const schedule = useSchedule(session ?? fallback, range, { withCases: false });
  const myId = session?.status === 'signedIn' ? session.me?.id : null;

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !(wrap.current && wrap.current.contains(e.target))) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  const t0 = new Date();
  t0.setHours(0, 0, 0, 0);
  const items = [];
  for (const event of schedule.data?.events ?? []) {
    // 내가 접수한 최초접수의 기한만(관리자 · 공유받은 일정의 기한은 띄우지 않는다 — 민규 #131 리뷰).
    if (event.category !== 'INTAKE' || !myId || event.owner_id !== myId) continue;
    const [y, m, d] = event.date.split('-').map((part) => parseInt(part, 10));
    for (const [n, task] of INTAKE_TASKS) {
      if (event.deadline_done[String(n)]) continue;
      const due = new Date(y, m - 1, d + n);
      const diff = Math.round((due - t0) / 86400000);
      const id = `${event.id}-${n}`;
      items.push({
        id,
        due,
        diff,
        unread: !read.includes(id),
        title: `${event.child_alias ?? '—'} · ${task}`,
        sub: `판정 후 ${n}일 이내 · ${due.getMonth() + 1}/${due.getDate()}(${DAYS[due.getDay()]})까지`,
        href: `/Schedule?${DATE_PARAM}=${ymd(due)}`,
      });
    }
  }
  items.sort((a, b) => a.due - b.due);
  const unread = items.filter((x) => x.unread).length;
  const markRead = (ids) => {
    const next = [...read, ...ids.filter((id) => !read.includes(id))];
    setRead(next);
    writeIds(next);
  };

  return (
    <div className="nt-wrap" ref={wrap}>
      <button
        type="button"
        className="nt-btn"
        aria-label={unread > 0 ? `알림 ${unread}건 읽지 않음` : '알림'}
        aria-expanded={open ? 'true' : 'false'}
        aria-haspopup="true"
        onClick={() => setOpen(!open)}
      >
        <svg
          viewBox="0 0 24 24"
          width="18"
          height="18"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9.5a6 6 0 0 1 12 0c0 4.2 1.4 6 2.2 6.9a.6.6 0 0 1-.45 1H4.25a.6.6 0 0 1-.45-1C4.6 15.5 6 13.7 6 9.5z"></path>
          <path d="M10 20.2a2.2 2.2 0 0 0 4 0"></path>
        </svg>
        {unread > 0 ? <span className="nt-badge">{unread > 9 ? '9+' : String(unread)}</span> : null}
      </button>
      {open ? (
        <div className="nt-pop" role="region" aria-label="알림 목록">
          <div className="nt-hd">
            <b style={{ fontSize: '15px' }}>알림</b>
            <span className="nt-sub">{items.length ? `법정 기한 ${items.length}건` : ''}</span>
            <button type="button" className="nt-all" onClick={() => markRead(items.map((x) => x.id))}>
              모두 읽음
            </button>
          </div>
          <div className="nt-list">
            {items.map((x) => (
              <A
                key={x.id}
                className={`nt-item ${x.unread ? 'unread' : 'read'}`}
                to={x.href}
                onClick={() => {
                  markRead([x.id]);
                  setOpen(false);
                }}
              >
                <span className="nt-dot" aria-hidden="true"></span>
                <span className="nt-main">
                  <b className="nt-t">{x.title}</b>
                  <span className="nt-s">{x.sub}</span>
                </span>
                <span className={`nt-dd ${x.diff <= 0 ? 'urgent' : x.diff <= 2 ? 'soon' : ''}`}>
                  {x.diff < 0 ? '기한 지남' : x.diff === 0 ? '오늘 마감' : `D-${x.diff}`}
                </span>
              </A>
            ))}
            {items.length === 0 ? <p className="nt-empty">새 알림이 없습니다.</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
