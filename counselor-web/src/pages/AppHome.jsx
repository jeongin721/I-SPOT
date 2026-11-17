// 상담사 앱(폰) · 홈
// 원본: 앱 · 홈 (시작 화면 app · 인사 · 기능 4개 · 사례 목록 · 사내 공지사항 · 알림) 2026-11-10 zip 의 AppHome.dc.html
//
// 서버 연결
//  - 인사: 로그인한 상담사 이름(GET /auth/me). 아래 줄은 오늘 날짜 · 오늘 상담 수.
//  - 내 사례 현황: 담당 사례 = 내 진행 중 사례 수(useAppCases), 이번 주 상담 · 오늘 상담 = 이번 주(월~일) · 오늘 일정 중 상담(GET /schedule/events).
//    누르면 앱 · 사례 목록.
//  - 사내 공지사항: 공지를 둘 서버 자리가 없어 '준비 중' 한 줄만 보인다(디자인의 예시 공지 3개는 넣지 않았다).
import { Link } from 'react-router-dom';
import MobileAppShell from '../components/MobileAppShell';
import { useAppCases } from '../data/useAppCases';
import { addDays, mondayOf, useAppSchedule, ymd } from '../data/useAppSchedule';

const W = ['일', '월', '화', '수', '목', '금', '토'];

function HomeBody({ userId, me }) {
  const my = useAppCases(userId);
  const now = new Date();
  const today = ymd(now);
  const mon = mondayOf(now);
  const week = useAppSchedule(!!userId, ymd(mon), ymd(addDays(mon, 6)));
  const consults = week.items.filter((e) => e.kind === 'CONSULT');
  const todayN = consults.filter((e) => e.date === today).length;
  const num = (value, loading) => (loading ? '—' : String(value));

  return (
    <>
      <section className="ma-hello" aria-label="인사">
        <span>안녕하세요,</span>
        <b>{me?.name ? `${me.name} 상담원님` : '상담원님'}</b>
        <small>{`${now.getMonth() + 1}월 ${now.getDate()}일 ${W[now.getDay()]}요일 · 오늘 상담 ${week.loading ? '—' : todayN}건`}</small>
      </section>
      <Link className="ma-hero" to="/AppCases" aria-label="사례 목록 보기">
        <span className="ma-hero-top">
          <span>내 사례 현황</span>
          <span className="ma-hero-go">
            사례 목록
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 5l7 7-7 7"></path></svg>
          </span>
        </span>
        <span className="ma-stats">
          <span className="ma-stat">
            <b>{num(my.rows.length, my.loading)}</b>
            <span>담당 사례</span>
          </span>
          <span className="ma-stat">
            <b>{num(consults.length, week.loading)}</b>
            <span>이번 주 상담</span>
          </span>
          <span className="ma-stat">
            <b>{num(todayN, week.loading)}</b>
            <span>오늘 상담</span>
          </span>
        </span>
      </Link>
      {(my.error || week.error) && <span className="ma-err">{my.error || week.error}</span>}
      <div className="ma-sec-h">
        <h2>사내 공지사항</h2>
      </div>
      <section className="ma-card ma-list" aria-label="사내 공지사항">
        <div className="ma-li" style={{ cursor: 'default' }}>
          <span className="ma-lt">
            <span className="ma-note">공지사항은 준비 중이에요</span>
          </span>
        </div>
      </section>
    </>
  );
}

export default function AppHome() {
  return (
    <MobileAppShell cur="home" screen="home" brand>
      {(ctx) => <HomeBody {...ctx} />}
    </MobileAppShell>
  );
}
