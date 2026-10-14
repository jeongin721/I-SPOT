// 밝은 · 어두운 화면 전환. 이 브라우저(localStorage)에만 기억하고 서버에는 저장하지 않는다.
// - 화면 맨 바깥 div 에 useTheme().cls 를 붙이면 .thm-root(.dark) 가 되어 common.css 의 다크 모드 규칙이 걸린다.
// - 한 화면에서 바꾸면 같은 탭의 다른 부분과 다른 탭도 함께 바뀐다(storage 이벤트).
// 디자인 원본(.dc.html)은 0.3초마다 저장값을 다시 읽었는데, 여기서는 바꿀 때 알리는 방식으로 옮겼다.
import { useSyncExternalStore } from 'react';

const KEY = 'ispot-theme';
const listeners = new Set();

function read() {
  try {
    return window.localStorage.getItem(KEY) === 'dark';
  } catch {
    return false;
  }
}

let dark = typeof window === 'undefined' ? false : read();

function apply() {
  if (typeof document !== 'undefined') document.documentElement.classList.toggle('thm-dark', dark);
  listeners.forEach((fn) => fn());
}

function setDark(next) {
  dark = next;
  try {
    window.localStorage.setItem(KEY, next ? 'dark' : 'light');
  } catch {
    // 저장이 막힌 브라우저(사생활 보호 창 등)에서는 이 탭에서만 바뀐다.
  }
  apply();
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    // key 가 null 이면 다른 탭이 저장소를 통째로 비운 것(localStorage.clear())이라 다시 읽는다.
    if (e.key !== null && e.key !== KEY) return;
    dark = read();
    apply();
  });
  apply();
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useTheme() {
  const isDark = useSyncExternalStore(subscribe, () => dark);
  return {
    dark: isDark,
    cls: isDark ? 'thm-root dark' : 'thm-root',
    label: isDark ? '라이트 모드로 전환' : '다크 모드로 전환',
    toggle: () => setDark(!dark),
  };
}
