// 시작 화면(랜딩)
// 원본: 10/22 디자인 counselor-design/screens/Landing.dc.html(다솔 님). 서버를 부르지 않는 소개 화면이고, '로그인' 으로 로그인 화면에 간다.
// 디자인의 위쪽 메뉴(서비스 소개 · 상담 지원 · 이용 안내 · 자주 묻는 질문)와 아래 링크(이용약관 · 개인정보 처리방침 · 문의하기)는
// 연결할 화면 · 문서가 아직 없어 글자로만 두고 '준비 중' 을 알린다(디자인은 빈 링크 '#'). '서비스 둘러보기' 는 앱의 화면 목록으로 간다.
import A from '../components/A';
import { NOT_READY } from '../data/screens/common';
import './Landing.css';

const NAV = ['서비스 소개', '상담 지원', '이용 안내', '자주 묻는 질문'];
const FOOT = ['이용약관', '개인정보 처리방침', '문의하기'];

const CARDS = [
  {
    no: '01',
    title: '상담에 집중하고',
    text: ['일정과 사례를 한눈에 살펴보고,', '오늘 만날 아이를 차분히 준비하세요.'],
    icon: <circle cx="12" cy="12" r="10"></circle>,
  },
  {
    no: '02',
    title: '기록을 이어가고',
    text: ['상담의 맥락과 작은 변화를 기록해,', '다음 만남으로 자연스럽게 이어가세요.'],
    icon: (
      <>
        <path d="M7 7h10v10"></path>
        <path d="M7 17 17 7"></path>
      </>
    ),
  },
  {
    no: '03',
    title: '함께 돌봅니다',
    text: ['확인할 일과 후속 지원을 챙기며,', '아이의 안전과 회복을 함께 살펴보세요.'],
    icon: (
      <>
        <path d="M5 12h14"></path>
        <path d="M12 5v14"></path>
      </>
    ),
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
                  <svg className="card-icon" width="24" height="24" {...svgProps}>
                    {c.icon}
                  </svg>
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
