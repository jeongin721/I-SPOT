// Start 화면 마크업 — tools/dc2jsx.py 가 디자인(Start.dc.html)에서 만든 파일. 손으로 고치지 말고 디자인을 다시 풀어 만든다.
/* eslint-disable */
import { Fragment } from 'react';
import './Start.css';

export default function View({ v }) {
  return (
    <div className="pg-Start">
      <div className="lp" style={{ background: "linear-gradient(180deg, #EAF5FC 0%, #FFFFFF 100%)", color: "#1F3A56", fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif", WebkitFontSmoothing: "antialiased", fontSize: "14px", display: "flex", flexDirection: "column", minHeight: "100vh", padding: "0 40px", overflowX: "hidden" }}>
        <nav className="splash-nav" aria-label="주 메뉴">
          <div className="nav-logo">
            <span className="logo-icon">
              온
            </span>
            <span className="logo-text">
              ·담
            </span>
          </div>
          <ul className="nav-links">
            <li>
              <a href="#">
                서비스 소개
              </a>
            </li>
            <li>
              <a href="#">
                상담 지원
              </a>
            </li>
            <li>
              <a href="#">
                이용 안내
              </a>
            </li>
            <li>
              <a href="#">
                자주 묻는 질문
              </a>
            </li>
          </ul>
          <div className="nav-actions">
            <a className="btn-primary login-btn" href="#/Login">
              {"로그인 "}
              <svg width="16" height="16" viewBox={"0 0 24 24"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14" />
                <path d="m12 5 7 7-7 7" />
              </svg>
            </a>
          </div>
        </nav>
        <section className="hero">
          <p className="hero-subtitle">
            시니어 상담을 위한 따뜻한 공간
          </p>
          <h1 className="hero-title">
            어르신의 이야기가
            <br />
            <strong>
              따뜻한 일상으로 이어지도록.
            </strong>
          </h1>
          <p className="hero-description">
            어르신께 필요한 관심과 안부가, 바쁜 업무 속에서도 놓치지 않도록.
            <br />
            상담의 준비부터 기록과 후속 지원까지, 온담이 함께합니다.
          </p>
          <div className="hero-buttons">
            <button type="button" className="btn-text explore-btn">
              {"서비스 둘러보기 "}
              <svg width="18" height="18" viewBox={"0 0 24 24"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M7 7h10v10" />
                <path d="M7 17 17 7" />
              </svg>
            </button>
          </div>
          <p className="hero-footer-text">
            상담사의 귀 기울임이 어르신의 편안한 하루로 이어지는 곳
          </p>
        </section>
        <section className="features">
          <div className="features-header">
            <h2>
              더 나은 돌봄을 위한, 차분한 업무의 시작
            </h2>
            <span className="with-ispot">
              WITH ONDAM
            </span>
          </div>
          <div className="cards-container">
            <div className="feature-card">
              <div className="card-top">
                <span className="card-number">
                  01
                </span>
              </div>
              <h3>
                상담에 집중하고
              </h3>
              <p>
                일정과 사례를 한눈에 살펴보고,
                <br />
                오늘 만날 어르신을 차분히 준비하세요.
              </p>
            </div>
            <div className="feature-card">
              <div className="card-top">
                <span className="card-number">
                  02
                </span>
              </div>
              <h3>
                기록을 이어가고
              </h3>
              <p>
                상담의 맥락과 작은 변화를 기록해,
                <br />
                다음 만남으로 자연스럽게 이어가세요.
              </p>
            </div>
            <div className="feature-card">
              <div className="card-top">
                <span className="card-number">
                  03
                </span>
              </div>
              <h3>
                함께 돌봅니다
              </h3>
              <p>
                확인할 일과 후속 지원을 챙기며,
                <br />
                어르신의 안부와 일상 회복을 함께 살펴보세요.
              </p>
            </div>
          </div>
        </section>
        <footer className="splash-footer">
          <div className="footer-left">
            <span className="footer-logo">
              온·담
            </span>
            {" 어르신의 따뜻한 일상을 함께"}
          </div>
          <div className="footer-right">
            <a href="#">
              이용약관
            </a>
            <a href="#">
              개인정보 처리방침
            </a>
            <a href="#">
              문의하기
            </a>
          </div>
        </footer>
      </div>
    </div>
  );
}
