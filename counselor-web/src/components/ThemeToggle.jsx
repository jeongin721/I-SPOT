// 밝은 · 어두운 화면 전환 단추(디자인의 .thm-tg). 상태는 src/theme.js 가 들고 있다.
import { useTheme } from '../theme';

export default function ThemeToggle() {
  const theme = useTheme();
  return (
    <button type="button" className="thm-tg" aria-pressed={theme.dark} aria-label={theme.label} onClick={theme.toggle}>
      <span className="thm-knob">
        <svg
          className="i-sun"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
        <svg
          className="i-moon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </svg>
      </span>
    </button>
  );
}
