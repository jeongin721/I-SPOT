// 시작 화면(랜딩)
// 원본: 10/22 · 10/27 디자인 counselor-design/screens/Landing.dc.html(다솔 님). 서버를 부르지 않는 소개 화면이고, '로그인' 으로 로그인 화면에 간다.
// 10/27 판은 기능 카드 오른쪽 위 장식 도형(동그라미 · 화살표 · 더하기)을 뺐다.
// 디자인의 위쪽 메뉴(서비스 소개 · 상담 지원 · 이용 안내 · 자주 묻는 질문)와 아래 링크(이용약관 · 개인정보 처리방침 · 문의하기)는
// 연결할 화면 · 문서가 아직 없어 글자로만 두고 '준비 중' 을 알린다(디자인은 빈 링크 '#'). '서비스 둘러보기' 는 앱의 화면 목록으로 간다.
import { useEffect, useRef } from 'react';
import A from '../components/A';
import { NOT_READY } from '../data/screens/common';
import './Landing.css';

// 11/19 디자인: 대표 문구 뒤 흰 반투명 곡선 리본(canvas). 왼쪽 → 오른쪽으로 느리게 흐르며 모양이 바뀐다. 동작 줄이기 설정이면 한 장만 그린다.
// 리본: 세로 위치, 진폭, 파장, 속도, 비틀림 주기, 폭, 선 수, 위상(디자인 값 그대로)
const RIBBONS = [
  { y: -0.1, a: 46, f: 0.0042, s: 0.16, tw: 0.0021, w: 70, n: 30, p: 0.0, q: 1.3 },
  { y: 0.04, a: 60, f: 0.0031, s: 0.11, tw: 0.0016, w: 96, n: 34, p: 2.1, q: 0.4 },
  { y: 0.16, a: 38, f: 0.0055, s: 0.2, tw: 0.0028, w: 54, n: 24, p: 4.0, q: 2.6 },
  { y: -0.02, a: 80, f: 0.0022, s: 0.08, tw: 0.0012, w: 120, n: 26, p: 5.2, q: 3.7 },
];

function LandingSilk() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current;
    const ctx = cv && cv.getContext ? cv.getContext('2d') : null;
    if (!ctx) return undefined;
    let W = 0;
    let H = 0;
    const size = () => {
      const r = cv.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width;
      H = r.height;
      cv.width = Math.round(W * dpr);
      cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    size();
    window.addEventListener('resize', size);
    let reduce = false;
    try {
      reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      reduce = false;
    }
    const draw = (t) => {
      ctx.clearRect(0, 0, W, H);
      const cy = H * 0.5;
      const step = 8;
      RIBBONS.forEach((r, ri) => {
        const sway = Math.sin(t * 0.00021 + ri * 1.7) * 18;
        for (let j = 0; j < r.n; j++) {
          const u = j / (r.n - 1) - 0.5;
          const edge = Math.abs(u) * 2;
          const path = () => {
            ctx.beginPath();
            for (let x = -20; x <= W + 20; x += step) {
              const T = t * 0.001;
              const lag = u * 0.9;
              const ph = x * r.f - T * r.s + r.p;
              const amp = r.a * (0.65 + 0.35 * Math.sin(T * 0.23 + x * 0.0017 + r.p));
              const w2 = 0.32 * r.a * Math.sin(x * r.f * 1.85 - T * r.s * 1.7 + r.q + lag);
              const w3 = 0.16 * r.a * Math.sin(x * r.f * 3.1 + T * 0.41 + r.p * 1.3 - lag * 1.6);
              const tw = Math.cos(x * r.tw - T * r.s * 0.55 + r.q + Math.sin(T * 0.19 + ri) * 1.4);
              const drift = 16 * Math.sin(x * 0.0013 + T * 0.27 + ri * 1.9);
              const env = 0.55 + 0.45 * Math.sin((x / W) * Math.PI);
              const y =
                cy + r.y * H + sway + drift + env * (amp * Math.sin(ph + lag * 0.35) + w2 + w3) +
                u * r.w * tw * (0.8 + 0.2 * Math.sin(T * 0.31 + x * 0.002));
              if (x === -20) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }
          };
          const rim = j === 0 || j === r.n - 1;
          // 그림자 선(입체감)
          if (rim) {
            ctx.save();
            ctx.translate(0, 3);
            path();
            ctx.strokeStyle = 'rgba(140,115,64,0.07)';
            ctx.lineWidth = 2.2;
            ctx.stroke();
            ctx.restore();
          }
          path();
          ctx.strokeStyle = `rgba(255,255,255,${(0.16 + 0.34 * (1 - edge) * (1 - edge)).toFixed(3)})`;
          ctx.lineWidth = rim ? 1.6 : 1;
          ctx.stroke();
        }
      });
    };
    let raf = 0;
    const loop = (t) => {
      draw(t);
      raf = requestAnimationFrame(loop);
    };
    if (reduce) draw(0);
    else raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', size);
    };
  }, []);
  return <canvas ref={ref} className="lp-silk" aria-hidden="true"></canvas>;
}

const NAV = ['서비스 소개', '상담 지원', '이용 안내', '자주 묻는 질문'];
const FOOT = ['이용약관', '개인정보 처리방침', '문의하기'];

const CARDS = [
  {
    no: '01',
    title: '상담에 집중하고',
    text: ['일정과 사례를 한눈에 살펴보고,', '오늘 만날 아이를 차분히 준비하십시오.'],
  },
  {
    no: '02',
    title: '기록을 이어가고',
    text: ['상담의 맥락과 작은 변화를 기록해,', '다음 만남으로 자연스럽게 이어가십시오.'],
  },
  {
    no: '03',
    title: '함께 돌봅니다',
    text: ['확인할 일과 후속 지원을 챙기며,', '아이의 안전과 회복을 함께 살펴보십시오.'],
  },
];

const svgProps = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: '2',
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': 'true',
};

export default function Landing() {
  return (
    <div className="pg-Landing">
      <div className="lp">
        <nav className="splash-nav" aria-label="주 메뉴">
          <div className="nav-logo">
            <span className="logo-icon">I</span>
            <span className="logo-text">·SPOT</span>
          </div>
          <ul className="nav-links">
            {NAV.map((label) => (
              <li key={label}>
                <span title={NOT_READY}>{label}</span>
              </li>
            ))}
          </ul>
          <div className="nav-actions">
            <A className="btn-primary login-btn" to="/Login">
              로그인{' '}
              <svg width="16" height="16" {...svgProps}>
                <path d="M5 12h14"></path>
                <path d="m12 5 7 7-7 7"></path>
              </svg>
            </A>
          </div>
        </nav>
        <section className="hero">
          <LandingSilk />
          <p className="hero-subtitle">아동 보호 상담을 위한 하나의 공간</p>
          <h1 className="hero-title">
            아이의 이야기가
            <br />
            <strong>안전한 내일로 이어지도록.</strong>
          </h1>
          <p className="hero-description">
            아이에게 필요한 관심이, 복잡한 업무 속에서 놓치지 않도록.
            <br />
            상담의 준비부터 기록과 후속 지원까지, I-SPOT이 함께합니다.
          </p>
          <div className="hero-buttons">
            <A className="btn-text explore-btn" to="/">
              서비스 둘러보기{' '}
              <svg width="18" height="18" {...svgProps}>
                <path d="M7 7h10v10"></path>
                <path d="M7 17 17 7"></path>
              </svg>
            </A>
          </div>
          <p className="hero-footer-text">상담사의 집중이 아이의 회복으로 이어지는 곳</p>
        </section>
        <section className="features">
          <div className="features-header">
            <h2>더 나은 돌봄을 위한, 차분한 업무의 시작</h2>
            <span className="with-ispot">WITH I-SPOT</span>
          </div>
          <div className="cards-container">
            {CARDS.map((c) => (
              <div key={c.no} className="feature-card">
                <div className="card-top">
                  <span className="card-number">{c.no}</span>
                </div>
                <h3>{c.title}</h3>
                <p>
                  {c.text[0]}
                  <br />
                  {c.text[1]}
                </p>
              </div>
            ))}
          </div>
        </section>
        <footer className="splash-footer">
          <div className="footer-left">
            <span className="footer-logo">I·SPOT</span> 아이의 안전과 회복을 함께
          </div>
          <div className="footer-right">
            {FOOT.map((label) => (
              <span key={label} title={NOT_READY}>
                {label}
              </span>
            ))}
          </div>
        </footer>
      </div>
    </div>
  );
}
