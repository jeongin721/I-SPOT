import { Search, ArrowRight, Plus, FileText, ArrowUpRight } from 'lucide-react';
import Header from '../components/Header';
import { mockData } from '../data/mockData';
import './Dashboard.css';

export default function Dashboard() {
  return (
    <div className="dashboard-container">
      {/* Reusable Header */}
      <Header />

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Welcome Section */}
        <section className="welcome-section">
          <div className="welcome-text">
            <p className="date-text">2026년 9월 28일 월요일</p>
            <h1>{mockData.user.name} 선생님, 안녕하세요.</h1>
            <p className="subtitle">오늘의 만남과 아이들에게 필요한 다음 걸음을 살펴보세요.</p>
          </div>
          <div className="search-bar">
            <Search size={18} className="search-icon" />
            <input type="text" placeholder="이름 또는 사례번호 검색" />
          </div>
        </section>

        {/* Alert Banner */}
        <div className="alert-banner">
          <div className="alert-content">
            <span className="alert-dot"></span>
            <strong>우선 확인할 사례 {mockData.reviews.length}건이 있어요.</strong>
            <span>새로 접수된 자료와 보호 상황을 확인해 주세요.</span>
          </div>
          <button className="btn-text alert-btn">사례 확인 <ArrowRight size={16} /></button>
        </div>

        {/* Grid Layout */}
        <div className="dashboard-grid">
          {/* Left Column: Today's Counseling */}
          <div className="col-left">
            <div className="card today-card">
              <div className="card-header">
                <h2>오늘의 상담 <span className="count-badge blue">{mockData.schedules.filter(s => s.status === 'upcoming').length}건</span></h2>
                <button className="btn-outline btn-sm"><Plus size={14} /> 상담 예약</button>
              </div>
              
              {/* Calendar */}
              <div className="calendar-strip">
                <div className="cal-day active"><span className="date">28</span><span className="day">월</span></div>
                <div className="cal-day"><span className="date">29</span><span className="day">화</span></div>
                <div className="cal-day"><span className="date">30</span><span className="day">수</span></div>
                <div className="cal-day"><span className="date">1</span><span className="day">목</span></div>
                <div className="cal-day"><span className="date">2</span><span className="day">금</span></div>
                <div className="cal-day"><span className="date">3</span><span className="day">토</span></div>
                <div className="cal-day"><span className="date">4</span><span className="day">일</span></div>
              </div>

              {/* Schedule List */}
              <div className="schedule-list">
                {mockData.schedules.filter(s => s.status === 'upcoming').map((schedule, idx) => (
                  <div key={schedule.id} className={`schedule-item ${idx === 0 ? 'upcoming' : ''}`}>
                    {idx === 0 && <div className="item-badge">다가오는 상담</div>}
                    {idx === 0 && <div className="room">상담실 02</div>}
                    <div className="schedule-content">
                      <div className="time">
                        <h3>{schedule.time}</h3>
                        <p>{schedule.time} - {schedule.endTime}</p>
                      </div>
                      <div className="details">
                        <div className="person">
                          <h4>{schedule.childName}</h4>
                          {schedule.type.includes('정기') && <span className="tag blue">{schedule.type}</span>}
                        </div>
                        <p className="desc">{schedule.desc}</p>
                      </div>
                      {idx === 0 ? (
                        <button className="btn-primary">상담 준비 <ArrowRight size={16} /></button>
                      ) : (
                        <button className="btn-outline">{schedule.type.includes('면담') ? '면담 준비' : '상담 준비'}</button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              <div className="card-footer-link">
                <span>이번 주 상담 {mockData.schedules.length}건</span>
                <a href="#">전체 일정 보기 <ArrowUpRight size={16} /></a>
              </div>
            </div>
          </div>

          {/* Right Column: Actions */}
          <div className="col-right">
            {/* Action Card 1 */}
            <div className="card action-card">
              <div className="card-header border-bottom">
                <h2>먼저 확인해 주세요</h2>
                <span className="count-badge red">{mockData.reviews.length}건</span>
              </div>
              
              <div className="action-list">
                {mockData.reviews.map(review => (
                  <div key={review.id} className="action-item">
                    <div className="action-top">
                      <h4>{review.childName} · {review.age}세</h4>
                      <span className={`tag ${review.tag === '우선 검토' ? 'red' : 'outline-blue'}`}>{review.tag}</span>
                    </div>
                    <p>{review.title}</p>
                    <div className="action-bottom">
                      <span className="meta">{review.date}</span>
                      <button className="btn-text">확인하기 <ArrowRight size={14} /></button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Action Card 2 */}
            <div className="card action-card">
              <div className="card-header border-bottom">
                <h2>기록 마무리</h2>
                <span className="count-badge grey">{mockData.records.filter(r => r.status !== '작성 완료').length}건</span>
              </div>
              
              <div className="doc-list">
                {mockData.records.filter(r => r.status !== '작성 완료').map(record => (
                  <div key={record.id} className="doc-item">
                    <div className="doc-icon"><FileText size={20} /></div>
                    <div className="doc-info">
                      <h4>{record.title}</h4>
                      <p>{record.date} · {record.status}</p>
                    </div>
                    <button className="btn-text">작성 <ArrowUpRight size={14} /></button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="dashboard-footer">
        <div className="footer-stats">
          <span>담당 사례 {mockData.cases.length}건</span>
          <span className="dot-divider">·</span>
          <span>후속 확인 {mockData.reviews.length}건</span>
        </div>
        <div className="footer-brand">
          <span className="logo">I·SPOT</span> 아이의 안전과 회복을 함께
        </div>
      </footer>
    </div>
  );
}
