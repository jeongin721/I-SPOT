import { Link } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, Circle, ArrowUpRight as ArrowUpRight2, Plus } from 'lucide-react';
import './Splash.css';

export default function Splash() {
  return (
    <div className="splash-container">
      {/* Navigation Bar */}
      <nav className="splash-nav">
        <div className="nav-logo">
          <span className="logo-icon">I</span>
          <span className="logo-text">·SPOT</span>
        </div>
        <ul className="nav-links">
          <li><a href="#">서비스 소개</a></li>
          <li><a href="#">상담 지원</a></li>
          <li><a href="#">이용 안내</a></li>
          <li><a href="#">자주 묻는 질문</a></li>
        </ul>
        <div className="nav-actions">
          <button className="btn-primary login-btn">로그인 <ArrowRight size={16} /></button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="hero">
        <p className="hero-subtitle">아동 보호 상담을 위한 하나의 공간</p>
        <h1 className="hero-title">
          아이의 이야기가<br />
          <strong>안전한 내일로 이어지도록.</strong>
        </h1>
        <p className="hero-description">
          아이에게 필요한 관심이, 복잡한 업무 속에서 놓치지 않도록.<br />
          상담의 준비부터 기록과 후속 지원까지, I-SPOT이 함께합니다.
        </p>
        <div className="hero-buttons">
          <Link to="/dashboard" className="btn-primary start-btn">
            상담 업무 시작하기 <ArrowRight size={18} />
          </Link>
          <button className="btn-text explore-btn">
            서비스 둘러보기 <ArrowUpRight size={18} />
          </button>
        </div>
        <p className="hero-footer-text">상담사의 집중이 아이의 회복으로 이어지는 곳</p>
      </section>

      {/* Features Section */}
      <section className="features">
        <div className="features-header">
          <h2>더 나은 돌봄을 위한, 차분한 업무의 시작</h2>
          <span className="with-ispot">WITH I-SPOT</span>
        </div>
        <div className="cards-container">
          <div className="feature-card">
            <div className="card-top">
              <span className="card-number">01</span>
              <Circle size={24} className="card-icon" />
            </div>
            <h3>상담에 집중하고</h3>
            <p>일정과 사례를 한눈에 살펴보고,<br />오늘 만날 아이를 차분히 준비하세요.</p>
          </div>
          <div className="feature-card">
            <div className="card-top">
              <span className="card-number">02</span>
              <ArrowUpRight2 size={24} className="card-icon" />
            </div>
            <h3>기록을 이어가고</h3>
            <p>상담의 맥락과 작은 변화를 기록해,<br />다음 만남으로 자연스럽게 이어가세요.</p>
          </div>
          <div className="feature-card">
            <div className="card-top">
              <span className="card-number">03</span>
              <Plus size={24} className="card-icon" />
            </div>
            <h3>함께 돌봅니다</h3>
            <p>확인할 일과 후속 지원을 챙기며,<br />아이의 안전과 회복을 함께 살펴보세요.</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="splash-footer">
        <div className="footer-left">
          <span className="footer-logo">I·SPOT</span> 아이의 안전과 회복을 함께
        </div>
        <div className="footer-right">
          <a href="#">이용약관</a>
          <a href="#">개인정보 처리방침</a>
          <a href="#">문의하기</a>
        </div>
      </footer>
    </div>
  );
}
