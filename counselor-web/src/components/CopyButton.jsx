// 칸 복사 단추(10/29 디자인 cp-btn · cp-menu). 같은 <label> 안 textarea 의 글을 '그대로' 또는 '이름 가려서' 복사한다.
// 단추는 그 label 의 마지막 자식으로 둔다(디자인 CSS 가 label:has(> .cp-btn) 로 자리를 잡는다).
// 바깥 누름 · Esc 로 메뉴가 닫히고, 복사되면 1.5초 동안 ✓ 로 바뀐다.
// 가릴 이름은 names(그 사례에 등록된 이름 전부 — 실명 · 가족 · 별칭)가 있으면 그것, 없으면 name 하나다.
import { useEffect, useRef, useState } from 'react';
import { maskName, maskNames } from '../data/maskName';
import './CopyButton.css';

function writeClipboard(text) {
  const fallback = () => {
    const x = document.createElement('textarea');
    x.value = text;
    x.setAttribute('readonly', '');
    x.style.position = 'fixed';
    x.style.left = '-9999px';
    document.body.appendChild(x);
    x.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(x);
    return ok ? Promise.resolve() : Promise.reject(new Error('copy'));
  };
  if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).catch(fallback);
  return fallback();
}

export default function CopyButton({ name, names }) {
  const list = names && names.length ? names : name ? [name] : [];
  const sample = list[0] || '이서윤';
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(null);
  const btn = useRef(null);
  const menu = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => {
      if (e.type === 'keydown' ? e.key === 'Escape' : !(btn.current?.contains(e.target) || menu.current?.contains(e.target)))
        setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  useEffect(() => {
    if (!done) return undefined;
    const t = setTimeout(() => setDone(null), 1500);
    return () => clearTimeout(t);
  }, [done]);

  const copy = (e, mask) => {
    e.preventDefault();
    setOpen(false);
    const area = btn.current?.closest('label')?.querySelector('textarea');
    if (!area) return;
    const text = mask ? maskNames(area.value, list) : area.value;
    writeClipboard(text).then(
      () => setDone(mask ? '이름 가려서 복사됨' : '복사됨'),
      () => {},
    );
  };

  return (
    <>
      <button
        ref={btn}
        type="button"
        className={`cp-btn${done ? ' done' : ''}`}
        title={done || '복사'}
        aria-label={done || '내용 복사'}
        aria-haspopup="true"
        onClick={(e) => {
          e.preventDefault();
          setOpen(!open);
        }}
      >
        <svg
          className="cp-i"
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M8.5 7.5V5.5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2"></path>
          <rect x="3.5" y="9.5" width="11" height="11" rx="2"></rect>
        </svg>
        <svg
          className="cp-ok"
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M5 12.5l4.5 4.5L19 7.5"></path>
        </svg>
      </button>
      <span ref={menu} className={`cp-menu${open ? ' open' : ''}`} role="menu" aria-label="복사 방식">
        <button type="button" role="menuitem" onClick={(e) => copy(e, false)}>
          그대로 복사
        </button>
        <button type="button" role="menuitem" onClick={(e) => copy(e, true)}>
          이름 가려서 복사<span className="cp-ex">예) {maskName(sample, sample)}</span>
        </button>
      </span>
    </>
  );
}
