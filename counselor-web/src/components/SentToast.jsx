// 아이 앱으로 질문을 보낸 뒤 화면 위쪽에 잠깐 뜨는 작은 확인 알림(11/10 — 상담사가 보내졌는지 알기 어렵다는 의견).
// 모양은 '분석 완료' 알림(.job-toast · .job-ok)을 그대로 쓴다. 3초 뒤 위로 사라진다.
// 카드 안 배치(overflow · transform)에 가려지지 않게 body 에 붙인다.
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

const SHOW_MS = 3000;
const OUT_MS = 450;

export function useSentToast() {
  const [toast, setToast] = useState(null);
  const timers = useRef([]);

  const clear = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const show = useCallback((text) => {
    clear();
    setToast({ text, out: false });
    timers.current.push(setTimeout(() => setToast((cur) => (cur ? { ...cur, out: true } : cur)), SHOW_MS));
    timers.current.push(setTimeout(() => setToast(null), SHOW_MS + OUT_MS));
  }, []);

  useEffect(() => clear, []);

  const element = toast ? createPortal(
    <div className={`job-toast${toast.out ? ' out' : ''}`} role="status" aria-live="polite">
      <span className="job-ok" aria-hidden="true">
        ✓
      </span>
      <span>{toast.text}</span>
    </div>,
    document.body,
  ) : null;

  return [element, show];
}
