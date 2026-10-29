// 위쪽 바 알림 종(10/29 디자인 nt-*). 디자인의 알림은 학대 판정 뒤 법정 기한(3일 유선 상담 · 7일 주변 인물 · 30일
// 계획서)인데, 판정일 · 기한을 서버가 주지 않아 지금은 늘 '새 알림이 없습니다.' 다(알림을 지어내지 않음).
// 바깥을 누르거나 Esc 를 누르면 닫힌다.
import { useEffect, useRef, useState } from 'react';

export default function NotiBell() {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null);

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

  return (
    <div className="nt-wrap" ref={wrap}>
      <button
        type="button"
        className="nt-btn"
        aria-label="알림"
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
      </button>
      {open ? (
        <div className="nt-pop" role="region" aria-label="알림 목록">
          <div className="nt-hd">
            <b style={{ fontSize: '15px' }}>알림</b>
            <span className="nt-sub"></span>
            <button type="button" className="nt-all" onClick={() => setOpen(false)}>
              모두 읽음
            </button>
          </div>
          <div className="nt-list">
            <p className="nt-empty">새 알림이 없습니다.</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
