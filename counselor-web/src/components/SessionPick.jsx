// 회차 처리 화면 '다른 회차' 고르기(10/29 디자인 sl-*) — 회차 상세 · 기록 확인. 값은 sessionDetail.ts 의 sessionPickValues.
import { useEffect, useRef, useState } from 'react';
import './SessionPick.css';

/** '다른 회차' 고르기(10/29 디자인 sl-*). 바깥을 누르거나 Esc 면 닫힌다. */
export default function SessionPick({ label, head, items }) {
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
    <div className="sl-wrap" ref={wrap}>
      <button
        type="button"
        className="sl-btn"
        aria-haspopup="listbox"
        aria-expanded={open ? 'true' : 'false'}
        onClick={() => setOpen(!open)}
      >
        {label}
        <svg
          className="sl-car"
          viewBox="0 0 24 24"
          width="14"
          height="14"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 9l6 6 6-6"></path>
        </svg>
      </button>
      {open ? (
        <div className="sl-pop" role="listbox" aria-label="회차 선택">
          <div className="sl-hd">
            회차 선택 <span className="note">{head}</span>
          </div>
          <div className="sl-list">
            {items.map((o) => (
              <button
                key={o.no}
                type="button"
                role="option"
                aria-selected={o.on}
                className={`sl-opt ${o.cls}`}
                onClick={() => {
                  setOpen(false);
                  o.pick();
                }}
              >
                <b className="sl-no">{o.no}</b>
                <span className="sl-meta">{o.meta}</span>
                <span className={o.stCls} style={{ height: '22px', fontSize: '11.5px' }}>
                  {o.st}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
